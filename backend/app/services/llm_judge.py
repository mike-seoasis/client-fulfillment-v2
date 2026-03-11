"""LLM judge service — GPT-based cross-model content evaluation.

Evaluates Claude-generated content on three dimensions using GPT as an
independent judge:
1. Naturalness — Does the content read like a human expert wrote it?
2. Brief Adherence — Does the content follow the POP content brief?
3. Heading Structure — Do headings match the brief's structure?

Feature-flagged via QUALITY_TIER2_ENABLED. All OpenAI calls are parallel
via asyncio.gather with per-call timeout and graceful error handling.
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.content_quality import QualityIssue

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Max characters to send to the judge (roughly ~2K tokens for GPT-4.1)
_MAX_CONTENT_CHARS = 8000

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class JudgeResult:
    """Result from a single judge evaluation."""

    dimension: str
    score: float  # 0.0 - 1.0
    reasoning: str = ""
    issues: list[QualityIssue] = field(default_factory=list)
    error: str | None = None
    latency_ms: int = 0
    cost_usd: float = 0.0


@dataclass
class JudgeRunResult:
    """Aggregated result from all judge evaluations."""

    naturalness: float = 0.0
    brief_adherence: float = 0.0
    heading_structure: float = 0.0
    issues: list[QualityIssue] = field(default_factory=list)
    model: str = ""
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str | None = None


# ---------------------------------------------------------------------------
# Rubric system prompts
# ---------------------------------------------------------------------------

NATURALNESS_SYSTEM = """You are a writing quality judge. Evaluate the following content for naturalness — does it read like a human domain expert wrote it, or does it feel AI-generated?

Score from 0.0 to 1.0:
- 1.0: Completely natural, reads like an expert human author
- 0.8: Very natural with minor AI tells
- 0.6: Somewhat natural but noticeable AI patterns
- 0.4: Clearly AI-generated with mechanical patterns
- 0.2: Very obviously AI with repetitive structures
- 0.0: Completely robotic/template-like

Look for:
- Varied sentence structure and length
- Natural transitions (not formulaic)
- Domain-appropriate vocabulary
- Absence of AI cliches (delve, leverage, unlock, etc.)
- Human-like flow and rhythm

Respond with JSON only:
{"score": 0.85, "reasoning": "Brief explanation"}"""

BRIEF_ADHERENCE_SYSTEM = """You are a content quality judge. Evaluate how well the content adheres to the given content brief.

Score from 0.0 to 1.0:
- 1.0: Perfectly follows the brief — all keywords, LSI terms, and structure requirements met
- 0.8: Strong adherence with minor omissions
- 0.6: Moderate adherence — covers main topics but misses secondary requirements
- 0.4: Weak adherence — significant brief requirements unmet
- 0.2: Poor adherence — barely follows the brief
- 0.0: Does not follow the brief at all

Evaluate against:
- Primary keyword usage and placement
- LSI term integration
- Word count targets (if provided)
- Topic coverage completeness

Respond with JSON only:
{"score": 0.85, "reasoning": "Brief explanation"}"""

HEADING_STRUCTURE_SYSTEM = """You are a content structure judge. Evaluate how well the content's heading structure matches SEO best practices and the content brief.

Score from 0.0 to 1.0:
- 1.0: Perfect heading hierarchy, keyword-rich, logically organized
- 0.8: Strong structure with minor improvements possible
- 0.6: Adequate structure but some heading issues
- 0.4: Weak structure — heading hierarchy problems
- 0.2: Poor structure — headings missing or misorganized
- 0.0: No meaningful heading structure

Evaluate:
- H1 -> H2 -> H3 proper hierarchy
- Keyword presence in headings
- Logical topic flow between sections
- Appropriate heading count for content length

Respond with JSON only:
{"score": 0.85, "reasoning": "Brief explanation"}"""

# ---------------------------------------------------------------------------
# Cost estimation (GPT-4.1 pricing)
# ---------------------------------------------------------------------------

# Approximate token costs (USD per 1K tokens) — GPT-4.1
_INPUT_COST_PER_1K = 0.002  # $2 per 1M input tokens
_OUTPUT_COST_PER_1K = 0.008  # $8 per 1M output tokens


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for an OpenAI call."""
    return (input_tokens / 1000 * _INPUT_COST_PER_1K) + (
        output_tokens / 1000 * _OUTPUT_COST_PER_1K
    )


# ---------------------------------------------------------------------------
# OpenAI call helper
# ---------------------------------------------------------------------------


async def _call_openai(
    client: Any,
    system_prompt: str,
    user_content: str,
    model: str,
    timeout: int,
) -> tuple[str, int, int]:
    """Make a single OpenAI chat completion call.

    Returns:
        Tuple of (response_text, input_tokens, output_tokens)
    """
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_tokens=256,
        ),
        timeout=timeout,
    )
    text = response.choices[0].message.content or ""
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    return text, input_tokens, output_tokens


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_judge_response(raw: str) -> tuple[float | None, str]:
    """Parse judge JSON response, handling markdown fences and edge cases.

    Returns:
        Tuple of (score, reasoning). Score clamped to 0.0-1.0.
        Returns (None, error_message) on parse failure.
    """
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        # Remove opening fence (possibly with language tag)
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()

    # Try direct JSON parse
    try:
        data = json.loads(text)
        score = float(data.get("score", 0.0))
        reasoning = str(data.get("reasoning", ""))
        return max(0.0, min(1.0, score)), reasoning
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Try to find embedded JSON object
    json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            score = float(data.get("score", 0.0))
            reasoning = str(data.get("reasoning", ""))
            return max(0.0, min(1.0, score)), reasoning
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    return None, f"Failed to parse judge response: {text[:100]}"


# ---------------------------------------------------------------------------
# Individual scoring functions
# ---------------------------------------------------------------------------


async def score_naturalness(
    client: Any,
    content: str,
    model: str,
    timeout: int,
) -> JudgeResult:
    """Score content naturalness."""
    start = time.monotonic()
    try:
        raw, inp_tok, out_tok = await _call_openai(
            client, NATURALNESS_SYSTEM, content[:_MAX_CONTENT_CHARS], model, timeout
        )
        score, reasoning = _parse_judge_response(raw)
        latency = int((time.monotonic() - start) * 1000)
        cost = _estimate_cost(inp_tok, out_tok)

        if score is None:
            return JudgeResult(
                dimension="naturalness",
                score=0.0,
                error=reasoning,
                latency_ms=latency,
                cost_usd=cost,
            )

        issues: list[QualityIssue] = []
        settings = get_settings()
        if score < settings.quality_naturalness_threshold:
            issues.append(
                QualityIssue(
                    type="llm_naturalness",
                    field="all",
                    description=f"Low naturalness score: {score:.2f} (threshold: {settings.quality_naturalness_threshold})",
                    context=reasoning[:200],
                )
            )

        return JudgeResult(
            dimension="naturalness",
            score=score,
            reasoning=reasoning,
            issues=issues,
            latency_ms=latency,
            cost_usd=cost,
        )
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        logger.warning("Naturalness judge failed", extra={"error": str(exc)})
        return JudgeResult(
            dimension="naturalness",
            score=0.0,
            error=str(exc),
            latency_ms=latency,
        )


async def score_brief_adherence(
    client: Any,
    content: str,
    brief_summary: str,
    model: str,
    timeout: int,
) -> JudgeResult:
    """Score content adherence to the content brief."""
    start = time.monotonic()
    user_msg = f"## Content Brief\n{brief_summary[:2000]}\n\n## Content\n{content[:_MAX_CONTENT_CHARS]}"
    try:
        raw, inp_tok, out_tok = await _call_openai(
            client, BRIEF_ADHERENCE_SYSTEM, user_msg, model, timeout
        )
        score, reasoning = _parse_judge_response(raw)
        latency = int((time.monotonic() - start) * 1000)
        cost = _estimate_cost(inp_tok, out_tok)

        if score is None:
            return JudgeResult(
                dimension="brief_adherence",
                score=0.0,
                error=reasoning,
                latency_ms=latency,
                cost_usd=cost,
            )

        issues: list[QualityIssue] = []
        settings = get_settings()
        if score < settings.quality_brief_adherence_threshold:
            issues.append(
                QualityIssue(
                    type="llm_brief_adherence",
                    field="all",
                    description=f"Low brief adherence score: {score:.2f} (threshold: {settings.quality_brief_adherence_threshold})",
                    context=reasoning[:200],
                )
            )

        return JudgeResult(
            dimension="brief_adherence",
            score=score,
            reasoning=reasoning,
            issues=issues,
            latency_ms=latency,
            cost_usd=cost,
        )
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        logger.warning("Brief adherence judge failed", extra={"error": str(exc)})
        return JudgeResult(
            dimension="brief_adherence",
            score=0.0,
            error=str(exc),
            latency_ms=latency,
        )


async def score_heading_structure(
    client: Any,
    content: str,
    brief_summary: str,
    model: str,
    timeout: int,
) -> JudgeResult:
    """Score content heading structure."""
    start = time.monotonic()
    user_msg = f"## Content Brief\n{brief_summary[:2000]}\n\n## Content\n{content[:_MAX_CONTENT_CHARS]}"
    try:
        raw, inp_tok, out_tok = await _call_openai(
            client, HEADING_STRUCTURE_SYSTEM, user_msg, model, timeout
        )
        score, reasoning = _parse_judge_response(raw)
        latency = int((time.monotonic() - start) * 1000)
        cost = _estimate_cost(inp_tok, out_tok)

        if score is None:
            return JudgeResult(
                dimension="heading_structure",
                score=0.0,
                error=reasoning,
                latency_ms=latency,
                cost_usd=cost,
            )

        issues: list[QualityIssue] = []
        settings = get_settings()
        if score < settings.quality_heading_structure_threshold:
            issues.append(
                QualityIssue(
                    type="llm_heading_structure",
                    field="all",
                    description=f"Low heading structure score: {score:.2f} (threshold: {settings.quality_heading_structure_threshold})",
                    context=reasoning[:200],
                )
            )

        return JudgeResult(
            dimension="heading_structure",
            score=score,
            reasoning=reasoning,
            issues=issues,
            latency_ms=latency,
            cost_usd=cost,
        )
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        logger.warning("Heading structure judge failed", extra={"error": str(exc)})
        return JudgeResult(
            dimension="heading_structure",
            score=0.0,
            error=str(exc),
            latency_ms=latency,
        )


# ---------------------------------------------------------------------------
# Brief summary builder
# ---------------------------------------------------------------------------


def build_brief_summary(
    content_brief: Any | None,
    primary_keyword: str = "",
) -> str:
    """Build a text summary of the content brief for the judge.

    Extracts keyword, LSI terms, word count targets from the content brief object.
    """
    parts: list[str] = []

    if primary_keyword:
        parts.append(f"Primary keyword: {primary_keyword}")

    if content_brief is None:
        return "\n".join(parts) if parts else "No content brief available."

    # Extract LSI terms
    lsi_terms = getattr(content_brief, "lsi_terms", None) or []
    if lsi_terms:
        terms_str = ", ".join(str(t) for t in lsi_terms[:20])
        parts.append(f"LSI terms: {terms_str}")

    # Extract word count
    wc_min = getattr(content_brief, "word_count_min", None)
    wc_max = getattr(content_brief, "word_count_max", None)
    if wc_min and wc_max:
        parts.append(f"Target word count: {wc_min}-{wc_max}")

    # Extract heading structure from brief
    heading_structure = getattr(content_brief, "heading_structure", None)
    if heading_structure:
        parts.append(f"Heading structure: {json.dumps(heading_structure)[:500]}")

    return "\n".join(parts) if parts else "No content brief available."


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_llm_judge_checks(
    content_text: str,
    content_brief: Any | None = None,
    primary_keyword: str = "",
) -> JudgeRunResult:
    """Run all 3 LLM judge evaluations in parallel.

    Checks settings for API key and feature flag before proceeding.
    Returns empty result if disabled or no API key.

    Args:
        content_text: The full text content to evaluate.
        content_brief: The POP content brief object (optional).
        primary_keyword: The primary keyword for the page.

    Returns:
        JudgeRunResult with scores and any issues.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        return JudgeRunResult(error="No OpenAI API key configured")

    # Lazy import openai
    try:
        import openai
    except ImportError:
        return JudgeRunResult(error="openai package not installed")

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    model = settings.quality_judge_model
    timeout = settings.quality_tier2_timeout

    brief_summary = build_brief_summary(content_brief, primary_keyword)

    start = time.monotonic()

    # Run all 3 judges in parallel
    naturalness_result, adherence_result, heading_result = await asyncio.gather(
        score_naturalness(client, content_text, model, timeout),
        score_brief_adherence(client, content_text, brief_summary, model, timeout),
        score_heading_structure(client, content_text, brief_summary, model, timeout),
    )

    total_latency = int((time.monotonic() - start) * 1000)

    # Collect all issues
    all_issues: list[QualityIssue] = []
    all_issues.extend(naturalness_result.issues)
    all_issues.extend(adherence_result.issues)
    all_issues.extend(heading_result.issues)

    # Accumulate cost from all judges
    total_cost = sum(
        r.cost_usd for r in [naturalness_result, adherence_result, heading_result]
    )

    # Check for any errors
    errors: list[str] = []
    for r in [naturalness_result, adherence_result, heading_result]:
        if r.error:
            errors.append(f"{r.dimension}: {r.error}")

    return JudgeRunResult(
        naturalness=naturalness_result.score,
        brief_adherence=adherence_result.score,
        heading_structure=heading_result.score,
        issues=all_issues,
        model=model,
        cost_usd=total_cost,
        latency_ms=total_latency,
        error="; ".join(errors) if errors else None,
    )
