# 18f: Auto-Rewrite

## Overview

When the quality pipeline (18e) scores content below a configurable threshold (default: 70), automatically attempt a single targeted rewrite pass. The rewriter filters to issues Claude can surgically fix, builds a per-field prompt listing specific problems, sends it to Claude, re-runs Tier 1 + Tier 1b quality checks on the result, and keeps whichever version scores higher. Maximum one rewrite attempt -- no cascading retries.

**Dependency:** 18e (quality_pipeline.py, llm_judge.py) must be complete. The pipeline orchestrator computes the composite score that triggers this step.

**Feature flag:** `QUALITY_AUTO_REWRITE_ENABLED=false` by default. When disabled, the pipeline stores the score and stops. When enabled, scores below the threshold trigger the fixer.

**Cost estimate:** ~$0.01-0.02 per rewrite (1-2 Claude calls per page, targeting only fields with fixable issues). At an estimated 20% rewrite rate, average cost increase is ~$0.004 per article.

---

## Decisions (from Planner/Advocate Debate)

### 1. Which issue types are fixable?

**Planner:** Only send issues where Claude can make a targeted word/phrase swap without restructuring the content. The FIXABLE set is the 9 deterministic regex types plus 4 bible types.

**Advocate:** What about `tier2_ai_excess`? That's "too many Tier 2 AI words" -- Claude could remove some, but the issue spans multiple locations. And `triplet_excess` means "too many X, Y, and Z patterns" -- Claude could rewrite some into other structures, but which ones?

**Resolution:** Include both `tier2_ai_excess` and `triplet_excess` as fixable. The issue objects already contain per-instance context (field + location). We group all issues for a field into one prompt, so Claude sees "you have 4 triplet lists, rewrite at least 2 of them" -- that is actionable. Exclude `rhetorical_excess` because deciding which question to remove requires editorial judgment. Exclude all `llm_*` types (subjective) and `sentence_starters` (too structural).

### 2. Should we re-run Tier 2 (LLM judge) on fixed content?

**Planner:** Re-run only Tier 1 + Tier 1b (free, <10ms). The LLM judge adds ~$0.035 and ~2s latency. Since most fixable issues are deterministic (AI words, banned words, em dashes), Tier 1 re-run is sufficient to verify the fix.

**Advocate:** If the original score was 52 with LLM naturalness at 0.4, the Tier 1 fixes alone won't raise naturalness. The fixed score will still look low even if every regex issue is resolved. The scoring formula will still deduct for the old LLM scores since they aren't re-evaluated.

**Resolution:** Re-run Tier 1 + Tier 1b only. Carry forward the original Tier 2 scores unchanged into the fixed version's score calculation. This means the "fixed_score" reflects resolved deterministic issues with unchanged LLM assessment. This is correct behavior: if the LLM said naturalness is 0.4, fixing a banned word doesn't change that. The cost savings ($0.035/article) outweigh the marginal accuracy gain. If the fixed version still scores below threshold, it goes to the operator -- which is the right outcome for content that has deep quality problems.

### 3. Storing full HTML in qa_results.versions.original.content_snapshot?

**Planner:** Store the full content of every field that was modified so operators can "View Original."

**Advocate:** A 1500-word bottom_description is ~8-10KB of HTML. With 4 fields, that's ~40KB in a JSONB column. Multiplied by hundreds of pages, that's megabytes of JSONB bloat. PostgreSQL JSONB is stored inline (no TOAST optimization for individual keys).

**Resolution:** Store only the fields that were actually modified (not all 4). Most rewrites touch 1-2 fields, so the typical snapshot is 10-20KB. PostgreSQL TOAST will compress and externalize JSONB values over ~2KB automatically, so this is fine. If we later find bloat is a problem, we can move snapshots to S3 and store a reference URL instead. For MVP, inline JSONB is simpler and avoids an S3 dependency.

### 4. Concurrent generation -- two pages being fixed simultaneously?

**Planner:** Each page has its own database session and its own PageContent row. No shared state between pages.

**Advocate:** The existing pipeline already uses `asyncio.Semaphore(concurrency)` for content generation. If auto-rewrite runs inside the same per-page pipeline, it inherits the same semaphore gating. No additional concurrency control needed.

**Resolution:** Correct. The fixer is called within `quality_pipeline.py` which is called within `_process_single_page()` which is already gated by the semaphore. No concurrency issues.

### 5. How do we compute "changes_made"?

**Planner:** Have Claude list what it changed in a structured response.

**Advocate:** Claude's self-reported changes could be inaccurate (hallucinated or missed). A diff would be more reliable.

**Resolution:** Use both approaches. Ask Claude to return a JSON response with `fixed_content` and `changes_made` list. The `changes_made` list is informational (displayed in the UI rewrite banner). The actual fix verification comes from re-running Tier 1 checks -- if the issue no longer fires, it was resolved. We do NOT compute a text diff ourselves (too complex for HTML, not worth the code). Claude's self-reported changes are good enough for the UI summary.

### 6. Should the fix prompt include bible context?

**Planner:** The fix prompt tells Claude what is wrong and what to fix. For bible issues like `bible_preferred_term`, the issue description already says 'Use "needle grouping" not "needle configuration"' -- that is sufficient instruction.

**Advocate:** What if fixing a bible_term_context issue requires understanding WHY the context is wrong? The issue says "membranes + ink savings is wrong" but Claude needs to know what IS right (backflow prevention) to write a good replacement.

**Resolution:** Include bible context in the fix prompt for bible-type issues. The `QualityIssue.description` field already contains the explanation from the bible rule (e.g., "Membranes prevent backflow, they don't save ink"). This is sufficient -- we don't need to inject the full bible markdown. The fix prompt template includes each issue's description verbatim, which carries the domain knowledge needed for the fix.

### 7. What if the Claude API call for fixing fails?

**Planner:** Keep the original content. The fix is an optimization, not a requirement.

**Advocate:** Agreed. But should we mark it in qa_results so the operator knows a fix was attempted and failed?

**Resolution:** Yes. If the fix call fails, set `rewrite.triggered = true`, `rewrite.error = "<error message>"`, `rewrite.kept_version = "original"`. The operator sees "Auto-rewrite attempted but failed" instead of nothing.

### 8. Is the threshold of 70 right?

**Planner:** 70 is the "Minor Issues" / "Needs Attention" boundary from the scoring tiers. Content at 69 gets rewritten, content at 70 does not.

**Advocate:** Score 70 is already "Minor Issues" (acceptable). Score 69 is "Needs Attention." The boundary seems right -- anything in "Needs Attention" or worse gets a rewrite attempt.

**Resolution:** 70 is correct as the default. It is configurable via `QUALITY_AUTO_REWRITE_THRESHOLD` for tuning. Strict comparison: `score < threshold` triggers rewrite.

### 9. Does the same fixer work for blog content?

**Planner:** Blog posts have different field names (`title`, `meta_description`, `content`) vs page content (`page_title`, `meta_description`, `top_description`, `bottom_description`). The fixer operates on a `dict[str, str]` of field names to content, so it is field-name agnostic. The pipeline orchestrator passes in the right fields.

**Advocate:** Blog content has a single `content` field that can be 2000+ words. Sending 2000 words to Claude with "fix 3 words" is wasteful token-wise.

**Resolution:** The fixer works on whatever fields are passed. For blog posts, the `content` field may be large, but the fix prompt explicitly says "change ONLY the listed issues, return the full corrected content." Claude is good at targeted edits. The token cost is marginal (~$0.005 for a 2000-word input). Not worth building a "paragraph extraction" optimization for MVP.

### 10. Should we track rewrite costs separately?

**Planner:** The rewrite metadata already includes `cost_usd` calculated from Claude's token usage response.

**Advocate:** That only tracks the fix call cost, not the re-run quality check cost (which is $0 for Tier 1 but would be $0.035 if we re-ran Tier 2).

**Resolution:** Track the Claude API call cost in `rewrite.cost_usd`. Since we only re-run Tier 1 (free), this accurately represents the incremental cost of the rewrite. If we later add Tier 2 re-evaluation, update the cost tracking to include it.

---

## quality_fixer.py -- Full Implementation

```python
"""Quality fixer for auto-rewriting content that scores below threshold.

Filters quality issues to fixable types, groups them by field, sends
targeted fix prompts to Claude, and returns the fixed content. The caller
(quality_pipeline.py) is responsible for re-running checks and deciding
which version to keep.

Design: One Claude call per field that has fixable issues. All issues for
a field are batched into a single prompt. Max 1 rewrite attempt total.
"""

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
        issue_type = issue.get("type", "unknown")
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
    import json

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
```

---

## Fix Prompt Template (Complete Text)

### System Prompt

```
You are a precise content editor. You will receive HTML content and a numbered list of specific issues to fix. Your job:

1. Fix ONLY the listed issues. Do not change anything else.
2. Preserve ALL HTML structure, tags, headings, links, and formatting exactly.
3. Preserve the overall meaning, tone, and length of the content.
4. When replacing a word or phrase, choose a natural alternative that fits the surrounding context. Do not introduce new AI-sounding language.
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

Do not include markdown code fences. Return raw JSON only.
```

### User Prompt (Template)

```
## Content to Fix

[field: {field_name}]
{field_content}

## Issues to Fix

1. [{field_name}] Tier 1 AI word "leverage" detected (context: "...why leverage cartridge needles...")
2. [{field_name}] AI opener pattern detected: "In today's world" (context: "...In today's world, the membrane technology...")
3. [{field_name}] Wrong Attribution: Membrane is a cartridge needle feature, not a pen feature (context: "...membrane technology in tattoo pens...")
4. [{field_name}] Term context: "membrane" + "saves ink" is wrong -- membranes prevent backflow for hygiene (context: "...membrane technology saves ink...")

Fix each issue. Change nothing else. Return JSON with fixed_content and changes_made.
```

### Example Response

```json
{
  "fixed_content": "<h2>Why Choose Cartridge Needles for Your Studio</h2>\n<p>The built-in membrane in cartridge needles prevents cross-contamination by blocking backflow between clients.</p>",
  "changes_made": [
    "\"leverage\" replaced with \"choose\" in heading",
    "\"In today's world\" removed, sentence restructured",
    "\"tattoo pens\" corrected to \"cartridge needles\" for membrane attribution",
    "\"saves ink\" replaced with \"prevents cross-contamination by blocking backflow\" for accurate membrane description"
  ]
}
```

---

## Pipeline Integration

The auto-rewrite logic lives in `quality_pipeline.py` (created in 18e). The following shows the integration point within the pipeline orchestrator.

### quality_pipeline.py Changes (~40 lines added)

```python
# In quality_pipeline.py, after score computation (STEP 5):

async def run_quality_pipeline(
    fields: dict[str, str],
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None = None,
    matched_bibles: list[Any] | None = None,
    content_type: str = "page",  # "page" or "blog"
) -> QualityPipelineResult:
    """Run the full quality pipeline on content fields.

    Steps:
    1. Collect inputs
    2. Tier 1: Deterministic checks
    3. Tier 1b: Bible rule checks
    4. Short-circuit check for critical failures
    5. Tier 2: LLM Judge (if enabled)
    6. Merge results + compute score
    7. Auto-rewrite (if enabled and score < threshold)

    Returns QualityPipelineResult with all results and rewrite metadata.
    """
    settings = get_settings()

    # ... Steps 1-6 already implemented in 18e ...

    # STEP 7: Auto-rewrite (if enabled and score below threshold)
    rewrite_metadata = None
    versions_metadata = None

    if (
        settings.quality_auto_rewrite_enabled
        and pipeline_result.score < settings.quality_auto_rewrite_threshold
    ):
        rewrite_metadata, versions_metadata, fields = await _attempt_auto_rewrite(
            fields=fields,
            issues=pipeline_result.all_issues,
            score=pipeline_result.score,
            brand_config=brand_config,
            matched_bibles=matched_bibles,
            tier2_scores=pipeline_result.tier2_scores,  # Carried forward unchanged
        )

    # Build final qa_results
    pipeline_result.rewrite = rewrite_metadata
    pipeline_result.versions = versions_metadata
    pipeline_result.final_fields = fields  # May be updated by rewrite

    return pipeline_result


async def _attempt_auto_rewrite(
    fields: dict[str, str],
    issues: list[dict[str, Any]],
    score: int,
    brand_config: dict[str, Any],
    matched_bibles: list[Any] | None,
    tier2_scores: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, str]]:
    """Attempt a single auto-rewrite pass on content.

    1. Filter to fixable issues
    2. Call quality_fixer.fix_content()
    3. Apply fixed fields to content
    4. Re-run Tier 1 + Tier 1b checks
    5. Re-compute score (carrying forward Tier 2 scores)
    6. Keep whichever version scores higher

    Args:
        fields: Current content fields dict.
        issues: All quality issues from initial run.
        score: Original composite score.
        brand_config: Brand config for re-running checks.
        matched_bibles: Matched bibles for re-running bible checks.
        tier2_scores: Original Tier 2 LLM scores (carried forward).

    Returns:
        Tuple of (rewrite_metadata, versions_metadata, final_fields).
        final_fields is either the original or fixed fields.
    """
    from app.services.quality_fixer import (
        FixResult,
        filter_fixable_issues,
        fix_content,
    )

    logger.info(
        "Auto-rewrite triggered",
        extra={"original_score": score, "total_issues": len(issues)},
    )

    # Check if there are any fixable issues
    fixable_issues = filter_fixable_issues(issues)
    if not fixable_issues:
        logger.info("No fixable issues found, skipping rewrite")
        return (
            {
                "triggered": True,
                "original_score": score,
                "fixed_score": None,
                "issues_sent": 0,
                "issues_resolved": 0,
                "issues_remaining": len(issues),
                "new_issues_introduced": 0,
                "cost_usd": 0.0,
                "latency_ms": 0.0,
                "kept_version": "original",
                "skip_reason": "no_fixable_issues",
            },
            None,
            fields,
        )

    # Snapshot original content (only fields that have fixable issues)
    fields_with_issues = {
        issue["field"]
        for issue in fixable_issues
        if issue.get("field") in fields
    }
    original_snapshot = {
        fname: fields[fname]
        for fname in fields_with_issues
        if fname in fields
    }

    # Attempt the fix
    fix_result: FixResult = await fix_content(
        fields=fields,
        issues=issues,
    )

    if not fix_result.success or not fix_result.fixed_fields:
        logger.warning(
            "Auto-rewrite fix call failed",
            extra={"error": fix_result.error},
        )
        return (
            {
                "triggered": True,
                "original_score": score,
                "fixed_score": None,
                "issues_sent": fix_result.issues_sent,
                "issues_resolved": 0,
                "issues_remaining": len(issues),
                "new_issues_introduced": 0,
                "cost_usd": fix_result.cost_usd,
                "latency_ms": fix_result.latency_ms,
                "kept_version": "original",
                "error": fix_result.error,
            },
            None,
            fields,
        )

    # Apply fixed fields to a copy of the content
    fixed_fields = dict(fields)
    for field_name, fixed_content in fix_result.fixed_fields.items():
        fixed_fields[field_name] = fixed_content

    # Re-run Tier 1 + Tier 1b on fixed content (free, <10ms)
    fixed_tier1_issues = _run_tier1_checks(fixed_fields, brand_config)
    fixed_tier1b_issues = _run_tier1b_checks(fixed_fields, matched_bibles)
    fixed_all_issues = fixed_tier1_issues + fixed_tier1b_issues

    # Re-compute score carrying forward original Tier 2 scores
    fixed_score = _compute_score(
        tier1_issues=fixed_all_issues,
        tier2_scores=tier2_scores,
    )

    # Count resolved / remaining / new issues
    original_issue_types_and_fields = {
        (i["type"], i["field"], i.get("context", ""))
        for i in fixable_issues
    }
    fixed_issue_types_and_fields = {
        (i["type"], i["field"], i.get("context", ""))
        for i in fixed_all_issues
    }

    issues_resolved = len(original_issue_types_and_fields - fixed_issue_types_and_fields)
    issues_remaining = len(
        [i for i in fixed_all_issues if i.get("type") in {
            issue["type"] for issue in fixable_issues
        }]
    )
    new_issues = len(fixed_issue_types_and_fields - original_issue_types_and_fields)

    # Keep the better version
    if fixed_score > score:
        kept_version = "fixed"
        final_fields = fixed_fields
        logger.info(
            "Auto-rewrite improved score, keeping fixed version",
            extra={
                "original_score": score,
                "fixed_score": fixed_score,
                "issues_resolved": issues_resolved,
            },
        )
    else:
        kept_version = "original"
        final_fields = fields
        logger.info(
            "Auto-rewrite did not improve score, keeping original",
            extra={
                "original_score": score,
                "fixed_score": fixed_score,
            },
        )

    rewrite_metadata = {
        "triggered": True,
        "original_score": score,
        "fixed_score": fixed_score,
        "issues_sent": fix_result.issues_sent,
        "issues_resolved": issues_resolved,
        "issues_remaining": issues_remaining,
        "new_issues_introduced": new_issues,
        "cost_usd": fix_result.cost_usd,
        "latency_ms": fix_result.latency_ms,
        "kept_version": kept_version,
    }

    versions_metadata = {
        "original": {
            "score": score,
            "content_snapshot": original_snapshot,
        },
        "fixed": {
            "score": fixed_score,
            "changes_made": fix_result.changes_made,
        },
    }

    return rewrite_metadata, versions_metadata, final_fields
```

### Applying Fixed Fields Back to the Database

After `run_quality_pipeline()` returns, the caller (in `content_generation.py` or `blog_content_generation.py`) applies the results:

```python
# In content_generation.py, _process_single_page(), after quality pipeline:

pipeline_result = await run_quality_pipeline(
    fields=_get_content_fields_dict(written_content),
    brand_config=brand_config,
    content_brief=content_brief,
    matched_bibles=matched_bibles,
)

# Apply final fields back to PageContent (may be original or fixed)
if pipeline_result.final_fields:
    for field_name, value in pipeline_result.final_fields.items():
        if hasattr(written_content, field_name):
            setattr(written_content, field_name, value)

# Recompute word count if content changed
if pipeline_result.rewrite and pipeline_result.rewrite.get("kept_version") == "fixed":
    written_content.word_count = _compute_word_count(pipeline_result.final_fields)

# Store qa_results with rewrite and version metadata
written_content.qa_results = pipeline_result.to_qa_results_dict()

from sqlalchemy.orm.attributes import flag_modified
flag_modified(written_content, "qa_results")
# If content fields were updated, flag them too
if pipeline_result.rewrite and pipeline_result.rewrite.get("kept_version") == "fixed":
    for field_name in pipeline_result.rewrite_fields_changed:
        flag_modified(written_content, field_name)

written_content.status = ContentStatus.COMPLETE.value
written_content.generation_completed_at = datetime.now(UTC)
await db.commit()
```

### Helper: Extract Content Fields as Dict

```python
def _get_content_fields_dict(content: PageContent) -> dict[str, str]:
    """Extract content fields as a dict for the quality pipeline."""
    fields: dict[str, str] = {}
    for field_name in ("page_title", "meta_description", "top_description", "bottom_description"):
        value = getattr(content, field_name, None)
        if value:
            fields[field_name] = value
    return fields
```

For blog posts, the equivalent extracts `title`, `meta_description`, `content`:

```python
def _get_blog_fields_dict(post: BlogPost) -> dict[str, str]:
    """Extract blog content fields as a dict for the quality pipeline."""
    fields: dict[str, str] = {}
    if post.title:
        fields["title"] = post.title
    if post.meta_description:
        fields["meta_description"] = post.meta_description
    if post.content:
        fields["content"] = post.content
    return fields
```

---

## Version Tracking & Storage

### qa_results JSONB Structure (Updated)

After auto-rewrite, the `qa_results` column contains the following shape:

```json
{
  "passed": true,
  "score": 88,
  "checked_at": "2026-03-06T14:30:00Z",
  "issues": [
    {
      "type": "tier2_ai_excess",
      "field": "bottom_description",
      "description": "Tier 2 AI word \"seamless\" (3 total, max 1)",
      "context": "...seamless integration...",
      "confidence": 1.0,
      "tier": 1
    }
  ],
  "tier2": {
    "model": "gpt-5.4",
    "naturalness": 0.82,
    "brief_adherence": 0.88,
    "heading_structure": 0.92,
    "cost_usd": 0.035,
    "latency_ms": 1800
  },
  "bibles_matched": ["tattoo-cartridge-needles"],
  "rewrite": {
    "triggered": true,
    "original_score": 52,
    "fixed_score": 88,
    "issues_sent": 4,
    "issues_resolved": 3,
    "issues_remaining": 1,
    "new_issues_introduced": 0,
    "cost_usd": 0.018,
    "latency_ms": 4200,
    "kept_version": "fixed"
  },
  "versions": {
    "original": {
      "score": 52,
      "content_snapshot": {
        "top_description": "<h2>Why Leverage Cartridge Needles...</h2><p>In today's world...</p>",
        "bottom_description": "<p>The membrane in tattoo pens saves ink...</p>"
      }
    },
    "fixed": {
      "score": 88,
      "changes_made": [
        "\"leverage\" replaced with \"choose\" in heading",
        "\"In today's world\" removed, sentence restructured",
        "\"tattoo pens\" corrected to \"cartridge needles\"",
        "\"saves ink\" replaced with \"prevents backflow\""
      ]
    }
  }
}
```

### When No Rewrite is Triggered (Score >= Threshold)

The `rewrite` and `versions` keys are absent from qa_results. The structure is identical to pre-18f format. Backward compatible.

### When Rewrite is Triggered but Fails

```json
{
  "rewrite": {
    "triggered": true,
    "original_score": 52,
    "fixed_score": null,
    "issues_sent": 4,
    "issues_resolved": 0,
    "issues_remaining": 4,
    "new_issues_introduced": 0,
    "cost_usd": 0.002,
    "latency_ms": 1500,
    "kept_version": "original",
    "error": "Fix failed for top_description: Request timed out after 120s"
  },
  "versions": null
}
```

### When Rewrite is Triggered but Makes Content Worse

```json
{
  "rewrite": {
    "triggered": true,
    "original_score": 62,
    "fixed_score": 58,
    "issues_sent": 3,
    "issues_resolved": 2,
    "issues_remaining": 1,
    "new_issues_introduced": 2,
    "cost_usd": 0.015,
    "latency_ms": 3800,
    "kept_version": "original"
  },
  "versions": {
    "original": {
      "score": 62,
      "content_snapshot": { ... }
    },
    "fixed": {
      "score": 58,
      "changes_made": [
        "\"leverage\" replaced with \"utilize\"",
        "\"In today's world\" replaced with \"In the current landscape\""
      ]
    }
  }
}
```

### When No Fixable Issues Exist

```json
{
  "rewrite": {
    "triggered": true,
    "original_score": 55,
    "fixed_score": null,
    "issues_sent": 0,
    "issues_resolved": 0,
    "issues_remaining": 3,
    "new_issues_introduced": 0,
    "cost_usd": 0.0,
    "latency_ms": 0.0,
    "kept_version": "original",
    "skip_reason": "no_fixable_issues"
  },
  "versions": null
}
```

---

## Config Settings

Add to `backend/app/core/config.py` in the `Settings` class:

```python
# Quality auto-rewrite settings
quality_auto_rewrite_enabled: bool = Field(
    default=False,
    description="Enable automatic content rewriting for low-scoring content (score < threshold)",
)
quality_auto_rewrite_threshold: int = Field(
    default=70,
    description="Quality score below which auto-rewrite is triggered (0-100). Content at or above this score is not rewritten.",
)
```

**Environment variables:**
```
QUALITY_AUTO_REWRITE_ENABLED=false    # Feature flag (default: off)
QUALITY_AUTO_REWRITE_THRESHOLD=70     # Score threshold (default: 70)
```

---

## Error Handling

### Claude API Failure During Fix

If the Claude `complete()` call fails for a field:
1. Log a warning with the field name and error.
2. Continue processing other fields (partial fix).
3. If ALL fields fail, `FixResult.success = False`.
4. The pipeline keeps the original content.
5. `rewrite.error` stores the error message.
6. `rewrite.kept_version = "original"`.

### Parse Failure (Claude Returns Invalid JSON)

If `_parse_fix_response()` cannot parse the JSON:
1. Log a warning with the response preview.
2. That field is skipped.
3. Other fields may still succeed.

### Suspiciously Short Response

If the fixed content is less than 50% the length of the original:
1. Reject that field's fix.
2. Log a warning.
3. This guards against Claude accidentally truncating or summarizing.

### Score Re-computation Failure

If Tier 1/1b re-run raises an exception:
1. Catch and log the error.
2. Keep the original content.
3. Store the error in `rewrite.error`.

### Database Transaction Safety

The auto-rewrite runs within the same database session as the rest of the pipeline (inside `_process_single_page()`). The fields are updated on the ORM model and committed once at the end. If any part fails, the session rollback in the outer exception handler reverts everything, including the fix. No partial state is persisted.

---

## Test Plan

All tests go in `backend/tests/services/test_quality_fixer.py`.

### Test 1: Content Passes (No Rewrite Needed)

```python
class TestNoRewriteNeeded:
    """When score >= threshold, no rewrite should be triggered."""

    def test_score_at_threshold_no_rewrite(self):
        """Score exactly at threshold (70) should NOT trigger rewrite."""
        # Verify _attempt_auto_rewrite is never called when score >= 70
        pass

    def test_score_above_threshold_no_rewrite(self):
        """Score above threshold (85) should NOT trigger rewrite."""
        pass

    def test_rewrite_disabled_no_rewrite(self):
        """Even with low score, disabled flag prevents rewrite."""
        # QUALITY_AUTO_REWRITE_ENABLED=false
        pass
```

### Test 2: Content Fails, Rewrite Fixes It

```python
class TestRewriteFixesContent:
    """When score < 70 and rewrite improves it, keep fixed version."""

    async def test_successful_rewrite_keeps_fixed(self):
        """
        Setup:
        - original fields with banned words / AI words
        - mock Claude to return clean fixed content
        - mock Tier 1 re-check returns fewer issues
        Verify:
        - rewrite.triggered = True
        - rewrite.kept_version = "fixed"
        - rewrite.fixed_score > rewrite.original_score
        - versions.original.content_snapshot has original content
        - versions.fixed.changes_made has descriptions
        - final_fields contains the fixed content
        """
        pass

    async def test_multiple_fields_fixed(self):
        """Fix issues across top_description and bottom_description."""
        pass

    async def test_word_count_recalculated(self):
        """Word count is recomputed after fix."""
        pass
```

### Test 3: Content Fails, Rewrite Makes It Worse

```python
class TestRewriteWorsensContent:
    """When rewrite introduces new issues, keep original."""

    async def test_worse_score_keeps_original(self):
        """
        Setup:
        - original has 1 banned word
        - mock Claude replaces it with another AI word
        - fixed_score <= original_score
        Verify:
        - rewrite.kept_version = "original"
        - final_fields == original fields
        - versions.original and versions.fixed both stored
        - rewrite.new_issues_introduced > 0
        """
        pass

    async def test_equal_score_keeps_original(self):
        """If fixed_score == original_score, keep original (conservative)."""
        pass
```

### Test 4: Only Non-Fixable Issues

```python
class TestOnlyNonFixableIssues:
    """When all issues are non-fixable types, skip rewrite."""

    async def test_llm_issues_only_no_rewrite(self):
        """
        Setup:
        - score < 70 but all issues are llm_naturalness, llm_brief_adherence
        Verify:
        - rewrite.triggered = True
        - rewrite.skip_reason = "no_fixable_issues"
        - rewrite.issues_sent = 0
        - rewrite.kept_version = "original"
        """
        pass

    async def test_mixed_issues_only_fixable_sent(self):
        """
        Setup:
        - 2 fixable issues (banned_word, em_dash)
        - 1 non-fixable (llm_naturalness)
        Verify:
        - rewrite.issues_sent = 2 (not 3)
        """
        pass
```

### Test 5: Max 1 Retry Verification

```python
class TestMaxOneRetry:
    """Verify the pipeline only attempts one rewrite, never cascading."""

    async def test_single_rewrite_attempt(self):
        """
        Setup:
        - mock fix_content() called once
        - fixed content still scores below threshold
        Verify:
        - fix_content called exactly once
        - No second fix attempt
        - rewrite.kept_version = "original" (since fixed didn't beat original)
        """
        pass
```

### Test 6: Filter and Group Functions

```python
class TestFilterFixableIssues:
    """Unit tests for filter_fixable_issues()."""

    def test_filters_to_fixable_types(self):
        """Only FIXABLE_ISSUE_TYPES are returned."""
        issues = [
            {"type": "banned_word", "field": "top_description", "description": "test"},
            {"type": "llm_naturalness", "field": "all", "description": "test"},
            {"type": "tier1_ai_word", "field": "bottom_description", "description": "test"},
        ]
        result = filter_fixable_issues(issues)
        assert len(result) == 2
        assert all(i["type"] in FIXABLE_ISSUE_TYPES for i in result)

    def test_empty_issues_returns_empty(self):
        result = filter_fixable_issues([])
        assert result == []

    def test_all_non_fixable_returns_empty(self):
        issues = [{"type": "llm_naturalness", "field": "all", "description": "test"}]
        result = filter_fixable_issues(issues)
        assert result == []


class TestGroupIssuesByField:
    """Unit tests for group_issues_by_field()."""

    def test_groups_by_field_name(self):
        issues = [
            {"type": "banned_word", "field": "top_description"},
            {"type": "em_dash", "field": "top_description"},
            {"type": "tier1_ai_word", "field": "bottom_description"},
        ]
        grouped = group_issues_by_field(issues)
        assert len(grouped) == 2
        assert len(grouped["top_description"]) == 2
        assert len(grouped["bottom_description"]) == 1

    def test_empty_returns_empty(self):
        assert group_issues_by_field([]) == {}
```

### Test 7: Fix Prompt Building

```python
class TestBuildFixPrompt:
    """Unit tests for _build_fix_prompt()."""

    def test_prompt_includes_field_content(self):
        prompt = _build_fix_prompt(
            "top_description",
            "<p>Test content</p>",
            [{"type": "banned_word", "description": "Banned word 'cheap'", "context": "...cheap..."}],
        )
        assert "[field: top_description]" in prompt
        assert "<p>Test content</p>" in prompt
        assert "Banned word 'cheap'" in prompt

    def test_multiple_issues_numbered(self):
        issues = [
            {"type": "banned_word", "description": "Issue 1", "context": "ctx1"},
            {"type": "em_dash", "description": "Issue 2", "context": "ctx2"},
        ]
        prompt = _build_fix_prompt("field", "content", issues)
        assert "1. [field] Issue 1" in prompt
        assert "2. [field] Issue 2" in prompt
```

### Test 8: Parse Fix Response

```python
class TestParseFixResponse:
    """Unit tests for _parse_fix_response()."""

    def test_parses_valid_json(self):
        response = '{"fixed_content": "<p>Fixed</p>", "changes_made": ["change 1"]}'
        content, changes = _parse_fix_response(response)
        assert content == "<p>Fixed</p>"
        assert changes == ["change 1"]

    def test_handles_markdown_fences(self):
        response = '```json\n{"fixed_content": "<p>Fixed</p>", "changes_made": []}\n```'
        content, changes = _parse_fix_response(response)
        assert content == "<p>Fixed</p>"

    def test_returns_none_on_invalid_json(self):
        content, changes = _parse_fix_response("not json at all")
        assert content is None
        assert changes == []

    def test_handles_missing_changes_made(self):
        response = '{"fixed_content": "<p>Fixed</p>"}'
        content, changes = _parse_fix_response(response)
        assert content == "<p>Fixed</p>"
        assert changes == []
```

### Test 9: Fix Content Integration

```python
class TestFixContent:
    """Integration tests for fix_content() with mocked Claude."""

    async def test_successful_fix(self):
        """
        Mock Claude to return valid fix response.
        Verify fixed_fields, changes_made, cost_usd populated.
        """
        pass

    async def test_no_fixable_issues_returns_early(self):
        """When no fixable issues, returns success with empty fixed_fields."""
        result = await fix_content(
            fields={"top_description": "<p>Content</p>"},
            issues=[{"type": "llm_naturalness", "field": "all", "description": "Low naturalness"}],
        )
        assert result.success is True
        assert result.fixed_fields == {}
        assert result.issues_sent == 0

    async def test_claude_failure_returns_error(self):
        """When Claude call fails, returns error with kept original."""
        pass

    async def test_suspiciously_short_response_rejected(self):
        """Fix response less than 50% of original length is rejected."""
        pass

    async def test_partial_field_fix(self):
        """When one field fix succeeds and another fails, partial result returned."""
        pass

    async def test_no_api_key_returns_error(self):
        """When no API key, returns error immediately."""
        pass
```

### Test 10: Bible Issue Types Are Fixable

```python
class TestBibleIssuesFiaxble:
    """Verify bible issue types are in FIXABLE_ISSUE_TYPES."""

    def test_all_bible_types_fixable(self):
        bible_types = {
            "bible_preferred_term",
            "bible_banned_claim",
            "bible_wrong_attribution",
            "bible_term_context",
        }
        assert bible_types.issubset(FIXABLE_ISSUE_TYPES)
```

### Test 11: Blog Content Fix

```python
class TestBlogContentFix:
    """Verify fixer works with blog field names."""

    async def test_fixes_blog_content_field(self):
        """Blog 'content' field (large HTML) can be fixed."""
        pass

    async def test_fixes_blog_title_field(self):
        """Blog 'title' field can be fixed."""
        pass
```

---

## Files to Create

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `backend/app/services/quality_fixer.py` | ~230 | Fix module: filter, group, prompt, parse, fix_content() |
| `backend/tests/services/test_quality_fixer.py` | ~350 | Unit + integration tests for all fixer functionality |

## Files to Modify

| File | Changes | Lines Added (est.) |
|------|---------|-------------------|
| `backend/app/services/quality_pipeline.py` | Add `_attempt_auto_rewrite()`, wire into pipeline after score computation | ~80 |
| `backend/app/services/content_generation.py` | Apply `pipeline_result.final_fields` back to PageContent, recompute word count, store rewrite metadata | ~20 |
| `backend/app/services/blog_content_generation.py` | Same as above for BlogPost | ~20 |
| `backend/app/core/config.py` | Add `quality_auto_rewrite_enabled`, `quality_auto_rewrite_threshold` | ~10 |

---

## Verification Checklist

- [ ] `QUALITY_AUTO_REWRITE_ENABLED=false` (default): no rewrite triggered, pipeline behaves identically to 18e
- [ ] `QUALITY_AUTO_REWRITE_ENABLED=true` + score >= 70: no rewrite triggered
- [ ] `QUALITY_AUTO_REWRITE_ENABLED=true` + score < 70 + fixable issues: rewrite triggers
- [ ] `QUALITY_AUTO_REWRITE_ENABLED=true` + score < 70 + only non-fixable issues: rewrite triggered but skipped (`skip_reason: "no_fixable_issues"`)
- [ ] Only fixable issue types sent to Claude (not LLM scores, not rhetorical_excess)
- [ ] Fix prompt is surgical: "fix ONLY the listed issues"
- [ ] Claude response parsed correctly (handles both raw JSON and markdown-fenced JSON)
- [ ] Re-run Tier 1 + Tier 1b on fixed content produces updated score
- [ ] Tier 2 scores carried forward unchanged (not re-evaluated)
- [ ] Better version kept: fixed_score > original_score -> keep fixed
- [ ] Worse version discarded: fixed_score <= original_score -> keep original
- [ ] Content fields updated on PageContent/BlogPost when fixed version kept
- [ ] Word count recomputed when fixed version kept
- [ ] qa_results.rewrite metadata populated correctly
- [ ] qa_results.versions.original.content_snapshot stores original HTML for changed fields only
- [ ] qa_results.versions.fixed.changes_made populated from Claude response
- [ ] Max 1 rewrite attempt -- no cascading retries
- [ ] Claude API failure during fix: keeps original, stores error in rewrite metadata
- [ ] Suspiciously short fix response (< 50% of original): rejected
- [ ] Blog content works with same fixer (title, meta_description, content fields)
- [ ] All existing tests still pass (backward compatibility)
- [ ] New tests in test_quality_fixer.py all pass
- [ ] Feature flag can be toggled without code changes (env var only)
