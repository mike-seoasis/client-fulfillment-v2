"""Quality fixer for auto-rewriting content that scores below threshold.

Filters quality issues to fixable types, groups them by field, sends
targeted fix prompts to Claude, and returns the fixed content. The caller
(quality_pipeline.py) is responsible for re-running checks and deciding
which version to keep.

Design: One Claude call per field that has fixable issues. All issues for
a field are batched into a single prompt. Max 1 rewrite attempt total.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_api_key

logger = get_logger(__name__)

# Claude model and settings for fix calls (same as content writing)
FIX_MODEL = "claude-sonnet-4-5"
FIX_MAX_TOKENS = 8192
FIX_TEMPERATURE = 0.3  # Lower than writing (0.7) for more conservative edits
FIX_TIMEOUT = 120.0  # Shorter than writing (180s) since fixes are targeted

# Issue types that Claude can fix with targeted edits.
# These are all deterministic check types where the issue description contains
# enough information for Claude to make a specific change.
FIXABLE_ISSUE_TYPES: set[str] = {
    # Tier 1: Deterministic content checks
    "banned_word",
    "em_dash",
    "ai_pattern",
    "tier1_ai_word",
    "tier2_ai_excess",
    "triplet_excess",
    "negation_contrast",
    "competitor_name",
    "tier3_banned_phrase",
    "empty_signpost",
    "business_jargon",
    # Tier 1b: Bible rule checks
    "bible_preferred_term",
    "bible_banned_claim",
    "bible_wrong_attribution",
    "bible_term_context",
}

# Issue types that are NOT fixable via auto-rewrite.
# Kept as documentation -- these are reported but never sent to Claude.
# - "rhetorical_excess": deciding which question to remove is editorial
# - "missing_direct_answer": restructuring the opening is too structural
# - "llm_naturalness": subjective score, "be more natural" is too vague
# - "llm_brief_adherence": adding missing brief coverage is too structural
# - "llm_heading_structure": restructuring headings changes the whole piece


# --- Fix prompt template ---

FIX_SYSTEM_PROMPT = """\
You are a precise content editor. You will receive HTML content and a numbered \
list of specific issues to fix. Your job:

1. Fix ONLY the listed issues. Do not change anything else.
2. Preserve ALL HTML structure, tags, headings, links, and formatting exactly.
3. Preserve the overall meaning, tone, and length of the content.
4. When replacing a word or phrase, choose a natural alternative that fits the \
surrounding context. Do not introduce new AI-sounding language.
5. When removing a phrase, merge the surrounding text so it reads naturally.
6. Do not add new content, paragraphs, or sections.
7. Do not remove content beyond what is needed to fix the listed issues.

Respond with ONLY a JSON object in this exact format:
{
  "fixed_content": "<the full corrected HTML content>",
  "changes_made": [
    "description of change 1",
    "description of change 2"
  ]
}

Do not include markdown code fences. Return raw JSON only."""

FIX_USER_PROMPT_TEMPLATE = """\
## Content to Fix

[field: {field_name}]
{field_content}

## Issues to Fix

{issues_list}

Fix each issue. Change nothing else. Return JSON with fixed_content and changes_made."""


@dataclass
class FixResult:
    """Result of attempting to fix content for one or more fields."""

    success: bool
    fixed_fields: dict[str, str] = field(default_factory=dict)
    changes_made: list[str] = field(default_factory=list)
    issues_sent: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None


def filter_fixable_issues(
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter quality issues to only those that can be auto-fixed.

    Args:
        issues: List of issue dicts from qa_results["issues"].

    Returns:
        Subset of issues whose type is in FIXABLE_ISSUE_TYPES.
    """
    return [i for i in issues if i.get("type") in FIXABLE_ISSUE_TYPES]


def group_issues_by_field(
    issues: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group fixable issues by their field name.

    Args:
        issues: List of fixable issue dicts (already filtered).

    Returns:
        Dict mapping field_name -> list of issues for that field.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for issue in issues:
        field_name = issue.get("field", "unknown")
        grouped.setdefault(field_name, []).append(issue)
    return grouped


def _build_fix_prompt(
    field_name: str,
    field_content: str,
    issues: list[dict[str, Any]],
) -> str:
    """Build the user prompt for fixing a single field.

    Args:
        field_name: Name of the content field (e.g., "top_description").
        field_content: Current HTML content of the field.
        issues: List of issue dicts for this field.

    Returns:
        Formatted user prompt string.
    """
    issues_lines: list[str] = []
    for i, issue in enumerate(issues, 1):
        description = issue.get("description", "")
        context = issue.get("context", "")

        line = f"{i}. [{field_name}] {description}"
        if context:
            line += f' (context: "{context}")'
        issues_lines.append(line)

    return FIX_USER_PROMPT_TEMPLATE.format(
        field_name=field_name,
        field_content=field_content,
        issues_list="\n".join(issues_lines),
    )


def _parse_fix_response(response_text: str) -> tuple[str | None, list[str]]:
    """Parse Claude's fix response JSON.

    Handles both raw JSON and markdown-fenced JSON responses.

    Args:
        response_text: Raw response text from Claude.

    Returns:
        Tuple of (fixed_content, changes_made). Returns (None, []) on parse failure.
    """
    text = response_text.strip()

    # Handle markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
        fixed_content = parsed.get("fixed_content")
        if not isinstance(fixed_content, str):
            fixed_content = None
        changes_made = parsed.get("changes_made", [])
        if not isinstance(changes_made, list):
            changes_made = []
        return fixed_content, [str(c) for c in changes_made]
    except json.JSONDecodeError as e:
        logger.warning(
            "Failed to parse fix response JSON",
            extra={"error": str(e), "response_preview": text[:200]},
        )
        return None, []


async def fix_content(
    fields: dict[str, str],
    issues: list[dict[str, Any]],
    claude_client: ClaudeClient | None = None,
) -> FixResult:
    """Fix content fields by sending targeted fix prompts to Claude.

    Filters to fixable issues, groups by field, sends one Claude call per
    field, and returns the fixed content. Calls are made sequentially to
    keep token usage predictable (typically 1-2 fields).

    Args:
        fields: Dict of field_name -> current HTML content.
        issues: List of all quality issue dicts (will be filtered to fixable).
        claude_client: Optional ClaudeClient instance. Created if not provided.

    Returns:
        FixResult with fixed fields and metadata.
    """
    start_time = time.monotonic()

    # Filter and group
    fixable = filter_fixable_issues(issues)
    if not fixable:
        return FixResult(
            success=True,
            issues_sent=0,
            latency_ms=0.0,
        )

    grouped = group_issues_by_field(fixable)

    # Create Claude client if not provided
    if claude_client is None:
        api_key = get_api_key()
        if not api_key:
            return FixResult(
                success=False,
                error="Claude API key not configured",
            )
        claude_client = ClaudeClient(api_key=api_key)

    result = FixResult(
        success=True,
        issues_sent=len(fixable),
    )

    total_input_tokens = 0
    total_output_tokens = 0

    # Process each field with issues
    for field_name, field_issues in grouped.items():
        field_content = fields.get(field_name)
        if not field_content:
            logger.warning(
                "Field referenced in issues but not found in content",
                extra={"field_name": field_name},
            )
            continue

        # Build and send fix prompt
        user_prompt = _build_fix_prompt(field_name, field_content, field_issues)

        logger.info(
            "Sending fix request to Claude",
            extra={
                "field_name": field_name,
                "issue_count": len(field_issues),
            },
        )

        completion = await claude_client.complete(
            user_prompt=user_prompt,
            system_prompt=FIX_SYSTEM_PROMPT,
            model=FIX_MODEL,
            max_tokens=FIX_MAX_TOKENS,
            temperature=FIX_TEMPERATURE,
            timeout=FIX_TIMEOUT,
        )

        if not completion.success:
            logger.warning(
                "Fix request failed for field",
                extra={
                    "field_name": field_name,
                    "error": completion.error,
                },
            )
            result.success = False
            result.error = f"Fix failed for {field_name}: {completion.error}"
            # Continue with other fields -- partial fix is better than none
            continue

        # Track tokens
        if completion.input_tokens:
            total_input_tokens += completion.input_tokens
        if completion.output_tokens:
            total_output_tokens += completion.output_tokens

        # Parse response
        fixed_content, changes = _parse_fix_response(completion.text or "")

        if fixed_content is None:
            logger.warning(
                "Failed to parse fix response for field",
                extra={"field_name": field_name},
            )
            result.success = False
            result.error = f"Failed to parse fix response for {field_name}"
            continue

        # Sanity check: fixed content should not be empty or dramatically shorter
        if len(fixed_content.strip()) < len(field_content.strip()) * 0.5:
            logger.warning(
                "Fix response is suspiciously short -- rejecting",
                extra={
                    "field_name": field_name,
                    "original_len": len(field_content),
                    "fixed_len": len(fixed_content),
                },
            )
            result.success = False
            result.error = f"Fix for {field_name} produced suspiciously short content"
            continue

        result.fixed_fields[field_name] = fixed_content
        result.changes_made.extend(changes)

    # Compute cost (Claude Sonnet 4.5 pricing: $3/1M input, $15/1M output)
    result.cost_usd = (total_input_tokens * 3.0 / 1_000_000) + (
        total_output_tokens * 15.0 / 1_000_000
    )
    result.latency_ms = (time.monotonic() - start_time) * 1000

    # If no fields were successfully fixed, mark as failed
    if not result.fixed_fields and result.issues_sent > 0:
        result.success = False
        if not result.error:
            result.error = "No fields were successfully fixed"

    logger.info(
        "Fix content complete",
        extra={
            "fields_fixed": len(result.fixed_fields),
            "issues_sent": result.issues_sent,
            "changes_made": len(result.changes_made),
            "cost_usd": round(result.cost_usd, 4),
            "latency_ms": round(result.latency_ms, 1),
        },
    )

    return result
