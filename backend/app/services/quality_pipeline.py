"""Quality pipeline orchestrator — unified Tier 1 + Tier 2 quality checks.

Single entry point that:
1. Runs deterministic Tier 1 checks (content_quality.py)
2. Optionally runs LLM judge Tier 2 checks (llm_judge.py)
3. Computes a composite score (0-100)
4. Returns a structured PipelineResult

Feature-flagged: Tier 2 is OFF by default (QUALITY_TIER2_ENABLED=false).
When disabled, only Tier 1 runs but results now include numeric score.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.content_quality import (
    CONTENT_FIELDS,
    QualityIssue,
    QualityResult,
    run_blog_quality_checks,
    run_fields_quality_checks,
    run_quality_checks,
)
from app.services.llm_judge import run_llm_judge_checks

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Score computation constants
# ---------------------------------------------------------------------------

CRITICAL_ISSUE_TYPES: frozenset[str] = frozenset(
    {
        "tier1_ai_word",
        "banned_word",
        "competitor_name",
        "bible_banned_claim",
        "bible_wrong_attribution",
    }
)

# Points deducted per occurrence of each issue type
DEDUCTION_MAP: dict[str, int] = {
    # Critical (higher penalty)
    "tier1_ai_word": 5,
    "banned_word": 5,
    "competitor_name": 5,
    "bible_banned_claim": 5,
    "bible_wrong_attribution": 5,
    # Moderate
    "em_dash": 2,
    "ai_pattern": 3,
    "triplet_excess": 2,
    "rhetorical_excess": 2,
    "tier2_ai_excess": 2,
    "negation_contrast": 2,
    # Bible
    "bible_preferred_term": 3,
    "bible_term_context": 3,
    # Blog-specific
    "tier3_banned_phrase": 3,
    "empty_signpost": 2,
    "missing_direct_answer": 3,
    "business_jargon": 2,
    # LLM judge
    "llm_naturalness": 5,
    "llm_brief_adherence": 5,
    "llm_heading_structure": 3,
}

# These types are deducted once regardless of count
PER_PIECE_TYPES: frozenset[str] = frozenset(
    {
        "triplet_excess",
        "rhetorical_excess",
        "tier2_ai_excess",
        "negation_contrast",
        "missing_direct_answer",
        "llm_naturalness",
        "llm_brief_adherence",
        "llm_heading_structure",
    }
)

SCORE_TIERS: list[tuple[int, str]] = [
    (90, "publish_ready"),
    (70, "minor_issues"),
    (50, "needs_attention"),
    (0, "needs_rewrite"),
]

# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Result from the full quality pipeline."""

    passed: bool
    score: int  # 0-100
    score_tier: str
    issues: list[QualityIssue] = field(default_factory=list)
    checked_at: str = ""
    bibles_matched: list[str] = field(default_factory=list)
    tier2: dict[str, Any] | None = None
    short_circuited: bool = False
    rewrite: dict[str, Any] | None = None
    versions: dict[str, Any] | None = None
    final_fields: dict[str, str] | None = None  # transient, not serialized

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "passed": self.passed,
            "score": self.score,
            "score_tier": self.score_tier,
            "issues": [issue.to_dict() for issue in self.issues],
            "checked_at": self.checked_at,
        }
        if self.bibles_matched:
            d["bibles_matched"] = self.bibles_matched
        if self.tier2 is not None:
            d["tier2"] = self.tier2
        if self.short_circuited:
            d["short_circuited"] = True
        if self.rewrite is not None:
            d["rewrite"] = self.rewrite
        if self.versions is not None:
            d["versions"] = self.versions
        return d


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------


def _compute_score(issues: list[QualityIssue]) -> int:
    """Compute composite score (0-100) from list of issues."""
    score = 100
    seen_per_piece: set[str] = set()

    for issue in issues:
        issue_type = issue.type
        deduction = DEDUCTION_MAP.get(issue_type, 2)

        if issue_type in PER_PIECE_TYPES:
            if issue_type in seen_per_piece:
                continue
            seen_per_piece.add(issue_type)

        score -= deduction

    return max(0, score)


def _get_score_tier(score: int) -> str:
    """Map a score to its tier label."""
    for threshold, tier in SCORE_TIERS:
        if score >= threshold:
            return tier
    return "needs_rewrite"


# ---------------------------------------------------------------------------
# Main pipeline entry point
# ---------------------------------------------------------------------------


async def run_quality_pipeline(
    content: Any | None = None,
    brand_config: dict[str, Any] | None = None,
    primary_keyword: str = "",
    content_brief: Any | None = None,
    is_blog: bool = False,
    fields: dict[str, str] | None = None,
    matched_bibles: list[Any] | None = None,
) -> PipelineResult:
    """Run the full quality pipeline (Tier 1 + optional Tier 2).

    Args:
        content: PageContent object (for onboarding pages). Mutually exclusive with fields.
        brand_config: BrandConfig.v2_schema dict.
        primary_keyword: Primary keyword for the page.
        content_brief: POP content brief object (for Tier 2 brief adherence).
        is_blog: If True, use blog quality checks for Tier 1.
        fields: Dict of field_name -> text (for blog posts). Mutually exclusive with content.
        matched_bibles: List of matched bible objects for domain-specific checks.

    Returns:
        PipelineResult with score, tier, issues, and optional tier2 data.
    """
    if content is not None and fields is not None:
        raise ValueError("Provide either 'content' or 'fields', not both.")

    settings = get_settings()
    brand = brand_config or {}

    # --- Tier 1: Deterministic checks ---
    if is_blog and fields is not None:
        tier1_result = run_blog_quality_checks(
            fields, brand, matched_bibles=matched_bibles
        )
    elif content is not None:
        tier1_result = run_quality_checks(content, brand, matched_bibles=matched_bibles)
    else:
        # Fallback — empty check
        tier1_result = QualityResult(
            passed=True,
            issues=[],
            checked_at=datetime.now(UTC).isoformat(),
        )

    all_issues = list(tier1_result.issues)
    bibles_matched = tier1_result.bibles_matched
    tier2_data: dict[str, Any] | None = None
    short_circuited = False

    # --- Tier 2: LLM judge (optional) ---
    if settings.quality_tier2_enabled:
        # Check for critical issues -> short-circuit
        has_critical = any(issue.type in CRITICAL_ISSUE_TYPES for issue in all_issues)

        if has_critical:
            short_circuited = True
            logger.info(
                "Tier 2 short-circuited due to critical Tier 1 issues",
                extra={"issue_count": len(all_issues)},
            )
        else:
            # Get content text for LLM judge
            content_text = ""
            if content is not None:
                # PageContent object — concatenate fields
                for fname in (
                    "page_title",
                    "meta_description",
                    "top_description",
                    "bottom_description",
                ):
                    val = getattr(content, fname, None)
                    if val:
                        content_text += val + "\n\n"
            elif fields is not None:
                content_text = "\n\n".join(fields.values())

            if content_text.strip():
                try:
                    judge_result = await run_llm_judge_checks(
                        content_text=content_text,
                        content_brief=content_brief,
                        primary_keyword=primary_keyword,
                    )

                    # Add LLM issues to all_issues
                    all_issues.extend(judge_result.issues)

                    tier2_data = {
                        "model": judge_result.model,
                        "naturalness": judge_result.naturalness,
                        "brief_adherence": judge_result.brief_adherence,
                        "heading_structure": judge_result.heading_structure,
                        "cost_usd": judge_result.cost_usd,
                        "latency_ms": judge_result.latency_ms,
                    }
                    if judge_result.error:
                        tier2_data["error"] = judge_result.error

                except Exception as exc:
                    logger.error(
                        "Tier 2 LLM judge failed",
                        extra={"error": str(exc)},
                        exc_info=True,
                    )
                    tier2_data = {"error": f"LLM judge error: {type(exc).__name__}"}

    # --- Compute final score ---
    score = _compute_score(all_issues)
    score_tier = _get_score_tier(score)

    result = PipelineResult(
        passed=len(all_issues) == 0,
        score=score,
        score_tier=score_tier,
        issues=all_issues,
        checked_at=datetime.now(UTC).isoformat(),
        bibles_matched=bibles_matched,
        tier2=tier2_data,
        short_circuited=short_circuited,
    )

    # --- Auto-rewrite (if enabled and score below threshold) ---
    if (
        settings.quality_auto_rewrite_enabled
        and score < settings.quality_auto_rewrite_threshold
    ):
        # Build fields dict from content object if needed
        pipeline_fields = fields
        if pipeline_fields is None and content is not None:
            pipeline_fields = _extract_fields_from_content(content)

        if pipeline_fields:
            # Separate Tier 2 issues (carried forward) from Tier 1 issues
            tier2_issues = [i for i in all_issues if i.type.startswith("llm_")]
            issue_dicts = [i.to_dict() for i in all_issues]

            (
                rewrite_meta,
                versions_meta,
                final_fields,
                fixed_issues,
            ) = await _attempt_auto_rewrite(
                fields=pipeline_fields,
                issues=issue_dicts,
                score=score,
                brand_config=brand,
                is_blog=is_blog,
                matched_bibles=matched_bibles,
                tier2_issues=tier2_issues,
            )

            result.rewrite = rewrite_meta
            result.versions = versions_meta
            result.final_fields = final_fields

            # If fixed version was kept, update the result's score AND issues
            if rewrite_meta.get("kept_version") == "fixed" and fixed_issues is not None:
                fixed_score = rewrite_meta["fixed_score"]
                result.score = fixed_score
                result.score_tier = _get_score_tier(fixed_score)
                result.passed = fixed_score == 100
                result.issues = fixed_issues

    # Store in content.qa_results if content object is provided
    if content is not None:
        content.qa_results = result.to_dict()

    return result


# ---------------------------------------------------------------------------
# Auto-rewrite helpers
# ---------------------------------------------------------------------------


def _extract_fields_from_content(content: Any) -> dict[str, str]:
    """Extract content fields as a dict from a PageContent object."""
    result: dict[str, str] = {}
    for fname in CONTENT_FIELDS:
        val = getattr(content, fname, None)
        if val:
            result[fname] = val
    return result


async def _attempt_auto_rewrite(
    fields: dict[str, str],
    issues: list[dict[str, Any]],
    score: int,
    brand_config: dict[str, Any],
    is_blog: bool,
    matched_bibles: list[Any] | None,
    tier2_issues: list[QualityIssue],
) -> tuple[
    dict[str, Any], dict[str, Any] | None, dict[str, str], list[QualityIssue] | None
]:
    """Attempt a single auto-rewrite pass on content.

    1. Filter to fixable issues
    2. Call quality_fixer.fix_content()
    3. Apply fixed fields to content copy
    4. Re-run Tier 1 + Tier 1b checks
    5. Re-compute score (carrying forward Tier 2 issues)
    6. Keep whichever version scores higher

    Returns:
        Tuple of (rewrite_metadata, versions_metadata, final_fields, fixed_issues).
        fixed_issues is the combined Tier 1 + Tier 2 issue list from the fixed version,
        or None if the original version was kept.
    """
    from app.services.quality_fixer import filter_fixable_issues, fix_content

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
            None,
        )

    # Snapshot original content (only fields that have fixable issues, truncated)
    _SNAPSHOT_MAX_CHARS = 500
    fields_with_issues = {
        issue["field"] for issue in fixable_issues if issue.get("field") in fields
    }
    original_snapshot = {
        fname: fields[fname][:_SNAPSHOT_MAX_CHARS]
        + ("..." if len(fields[fname]) > _SNAPSHOT_MAX_CHARS else "")
        for fname in fields_with_issues
        if fname in fields
    }

    # Attempt the fix
    fix_result = await fix_content(
        fields=fields,
        issues=issues,
    )

    if not fix_result.fixed_fields:
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
            None,
        )

    # Apply fixed fields to a copy
    fixed_fields = dict(fields)
    for field_name, fixed_content in fix_result.fixed_fields.items():
        fixed_fields[field_name] = fixed_content

    # Re-run Tier 1 + Tier 1b on fixed content (use matching check function)
    try:
        if is_blog:
            recheck_result = run_blog_quality_checks(
                fixed_fields, brand_config, matched_bibles=matched_bibles
            )
        else:
            recheck_result = run_fields_quality_checks(
                fixed_fields, brand_config, matched_bibles=matched_bibles
            )
        fixed_tier1_issues = list(recheck_result.issues)
    except Exception as exc:
        logger.error(
            "Re-check after auto-rewrite failed",
            extra={"error": str(exc)},
            exc_info=True,
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
                "error": f"Re-check failed: {exc}",
            },
            None,
            fields,
            None,
        )

    # Combine fixed Tier 1 issues with original Tier 2 issues, compute score
    all_fixed_issues = fixed_tier1_issues + tier2_issues
    fixed_score = _compute_score(all_fixed_issues)

    # Count resolved / remaining / new issues
    # Use `or ""` for consistent None/empty-string handling across dicts and objects
    original_fixable_keys = {
        (i["type"], i.get("field") or "", i.get("context") or "")
        for i in fixable_issues
    }
    fixed_issue_keys = {
        (i.type, i.field or "", i.context or "") for i in fixed_tier1_issues
    }
    original_tier1_keys = {
        (i["type"], i.get("field") or "", i.get("context") or "")
        for i in issues
        if not i.get("type", "").startswith("llm_")
    }

    issues_resolved = len(original_fixable_keys - fixed_issue_keys)
    issues_remaining = len(fixed_issue_keys)
    new_issues = len(fixed_issue_keys - original_tier1_keys)

    # Keep the better version (ties → keep original)
    if fixed_score > score:
        kept_version = "fixed"
        final_fields = fixed_fields
        kept_issues = all_fixed_issues
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
        kept_issues = None
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

    return rewrite_metadata, versions_metadata, final_fields, kept_issues
