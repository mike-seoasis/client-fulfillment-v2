"""POP Content Score service for scoring content against POP API.

Fetches content scoring data from PageOptimizer Pro API and manages storage.
Content scores provide page score, keyword analysis, LSI coverage, heading
analysis, and recommendations for content optimization.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.pop import (
    POPClient,
    POPError,
    POPTaskStatus,
    get_pop_client,
)

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000


@dataclass
class POPContentScoreResult:
    """Result of a POP content score operation."""

    success: bool
    keyword: str
    content_url: str
    task_id: str | None = None
    score_id: str | None = None  # Database record ID after persistence
    page_score: float | None = None
    passed: bool | None = None
    keyword_analysis: dict[str, Any] = field(default_factory=dict)
    lsi_coverage: dict[str, Any] = field(default_factory=dict)
    word_count_current: int | None = None
    word_count_target: int | None = None  # Target word count for comparison
    heading_analysis: dict[str, Any] = field(default_factory=dict)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    fallback_used: bool = False
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


class POPContentScoreServiceError(Exception):
    """Base exception for POP content score service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class POPContentScoreValidationError(POPContentScoreServiceError):
    """Raised when validation fails."""

    def __init__(
        self,
        field_name: str,
        value: str,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Validation error for {field_name}: {message}", project_id, page_id
        )
        self.field_name = field_name
        self.value = value


class POPContentScoreService:
    """Service for scoring content using POP API.

    Features:
    - Scores content against PageOptimizer Pro API
    - Creates POP tasks and polls for results
    - Parses and normalizes score data
    - Comprehensive logging per requirements

    Usage:
        service = POPContentScoreService()
        result = await service.score_content(
            project_id="uuid",
            page_id="uuid",
            keyword="best hiking boots",
            content_url="https://example.com/hiking-boots",
        )
    """

    def __init__(
        self,
        client: POPClient | None = None,
    ) -> None:
        """Initialize POP content score service.

        Args:
            client: POP client instance. If None, uses global instance.
        """
        self._client = client

        logger.debug(
            "POPContentScoreService initialized",
            extra={
                "client_provided": client is not None,
            },
        )

    async def _get_client(self) -> POPClient:
        """Get POP client instance."""
        if self._client is None:
            self._client = await get_pop_client()
        return self._client

    def _parse_score_data(
        self,
        raw_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse raw POP API response into structured score data.

        Extracts structured data from POP API responses following their schema:
        - pageScore/pageScoreValue: overall content score (0-100)
        - wordCount: {current, target} - word count comparison
        - tagCounts: [{tagLabel, min, max, signalCnt}] - heading structure analysis
        - cleanedContentBrief: {title, pageTitle, subHeadings, p} - keyword density analysis
        - lsaPhrases: [{phrase, weight, averageCount, targetCount}] - LSI term coverage

        Args:
            raw_data: Raw API response data

        Returns:
            Dictionary with parsed score fields
        """
        return {
            "page_score": self._extract_page_score(raw_data),
            "keyword_analysis": self._extract_keyword_analysis(raw_data),
            "lsi_coverage": self._extract_lsi_coverage(raw_data),
            "word_count_current": self._extract_word_count_current(raw_data),
            "word_count_target": self._extract_word_count_target(raw_data),
            "heading_analysis": self._extract_heading_analysis(raw_data),
            "recommendations": [],  # Populated separately via recommendations endpoint
        }

    def _extract_page_score(self, raw_data: dict[str, Any]) -> float | None:
        """Extract page score (0-100) from POP response.

        POP API provides pageScore or pageScoreValue at top level
        or within cleanedContentBrief. The score indicates how well
        the content is optimized compared to competitors.
        """
        # Try cleanedContentBrief first (most common location)
        content_brief = raw_data.get("cleanedContentBrief")
        if isinstance(content_brief, dict):
            page_score = content_brief.get("pageScore")
            if isinstance(page_score, (int, float)):
                return float(page_score)

            page_score_value = content_brief.get("pageScoreValue")
            if page_score_value is not None:
                try:
                    return float(page_score_value)
                except (ValueError, TypeError):
                    pass

        # Try top-level pageScore
        page_score = raw_data.get("pageScore")
        if isinstance(page_score, (int, float)):
            return float(page_score)

        # Try top-level pageScoreValue
        page_score_value = raw_data.get("pageScoreValue")
        if page_score_value is not None:
            try:
                return float(page_score_value)
            except (ValueError, TypeError):
                pass

        return None

    def _extract_keyword_analysis(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extract keyword density analysis by section from cleanedContentBrief.

        POP API provides cleanedContentBrief with sections:
        - title: keyword analysis for meta title
        - pageTitle: keyword analysis for page title (H1)
        - subHeadings: keyword analysis for H2/H3
        - p: keyword analysis for paragraph content

        Each section has arrays with:
        - term: {phrase, type, weight}
        - contentBrief: {current, target}

        And totals like titleTotal, pageTitleTotal, etc. with {current, min, max}
        """
        analysis: dict[str, Any] = {
            "sections": [],
            "section_totals": [],
        }
        content_brief = raw_data.get("cleanedContentBrief")

        if not isinstance(content_brief, dict):
            return analysis

        # Map section names to our normalized section names
        section_mapping = {
            "title": "title",
            "pageTitle": "h1",
            "subHeadings": "h2",  # POP treats subHeadings as H2+H3
            "p": "paragraph",
        }

        # Extract per-keyword analysis for each section
        for pop_section, our_section in section_mapping.items():
            section_data = content_brief.get(pop_section, [])
            if not isinstance(section_data, list):
                continue

            for item in section_data:
                if not isinstance(item, dict):
                    continue

                term = item.get("term", {})
                if not isinstance(term, dict):
                    continue

                phrase = term.get("phrase")
                if not phrase:
                    continue

                brief = item.get("contentBrief", {})
                current_count = (
                    brief.get("current") if isinstance(brief, dict) else None
                )
                target_count = brief.get("target") if isinstance(brief, dict) else None

                term_weight = term.get("weight")
                analysis["sections"].append(
                    {
                        "keyword": str(phrase),
                        "section": our_section,
                        "current_count": int(current_count)
                        if isinstance(current_count, (int, float))
                        else None,
                        "target_count": int(target_count)
                        if isinstance(target_count, (int, float))
                        else None,
                        "weight": float(term_weight)
                        if isinstance(term_weight, (int, float))
                        else None,
                    }
                )

        # Extract section totals
        total_sections = {
            "titleTotal": "title",
            "pageTitleTotal": "h1",
            "subHeadingsTotal": "h2",
            "pTotal": "paragraph",
        }

        for pop_total, our_section in total_sections.items():
            total_data = content_brief.get(pop_total, {})
            if not isinstance(total_data, dict):
                continue

            current_val = total_data.get("current")
            min_val = total_data.get("min")
            max_val = total_data.get("max")

            if current_val is not None or min_val is not None or max_val is not None:
                analysis["section_totals"].append(
                    {
                        "section": our_section,
                        "current": int(current_val)
                        if isinstance(current_val, (int, float))
                        else None,
                        "min": int(min_val)
                        if isinstance(min_val, (int, float))
                        else None,
                        "max": int(max_val)
                        if isinstance(max_val, (int, float))
                        else None,
                    }
                )

        return analysis

    def _extract_lsi_coverage(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extract LSI term coverage from lsaPhrases array.

        POP API provides lsaPhrases with:
        - phrase: the LSI term
        - weight: importance weight
        - averageCount: average count in competitors
        - targetCount: recommended target count (also represents current count for scoring)

        For scoring, we need both current and target counts to measure coverage.
        """
        coverage: dict[str, Any] = {
            "terms": [],
            "total_terms": 0,
            "covered_terms": 0,
            "coverage_percentage": None,
        }
        lsa_phrases = raw_data.get("lsaPhrases", [])

        if not isinstance(lsa_phrases, list):
            return coverage

        covered_count = 0
        for item in lsa_phrases:
            if not isinstance(item, dict):
                continue

            phrase = item.get("phrase")
            if not phrase:
                continue

            weight = item.get("weight")
            avg_count = item.get("averageCount")
            target_count = item.get("targetCount")

            # targetCount represents the current count on the target page
            current_count = target_count
            # averageCount represents the target (competitor average)
            target = avg_count

            # Calculate current_count with proper type narrowing
            term_current: int = (
                int(current_count) if isinstance(current_count, (int, float)) else 0
            )
            term_entry = {
                "phrase": str(phrase),
                "current_count": term_current,
                "target_count": int(target)
                if isinstance(target, (int, float))
                else None,
                "weight": float(weight) if isinstance(weight, (int, float)) else None,
            }
            coverage["terms"].append(term_entry)

            # Count as covered if current > 0
            if term_current > 0:
                covered_count += 1

        coverage["total_terms"] = len(coverage["terms"])
        coverage["covered_terms"] = covered_count

        if coverage["total_terms"] > 0:
            coverage["coverage_percentage"] = round(
                (covered_count / coverage["total_terms"]) * 100, 2
            )

        return coverage

    def _extract_word_count_current(self, raw_data: dict[str, Any]) -> int | None:
        """Extract current word count from POP response.

        POP API provides wordCount.current for the current word count
        of the target page being scored.
        """
        word_count = raw_data.get("wordCount")
        if isinstance(word_count, dict):
            current = word_count.get("current")
            if current is not None:
                return int(current) if isinstance(current, (int, float)) else None
        return None

    def _extract_word_count_target(self, raw_data: dict[str, Any]) -> int | None:
        """Extract target word count from POP response.

        POP API provides wordCount.target for the recommended word count
        based on competitor analysis.
        """
        word_count = raw_data.get("wordCount")
        if isinstance(word_count, dict):
            target = word_count.get("target")
            if target is not None:
                return int(target) if isinstance(target, (int, float)) else None
        return None

    def _extract_heading_analysis(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extract heading structure analysis from tagCounts.

        POP API provides tagCounts array with entries like:
        - tagLabel: 'H1 tag total', 'H2 tag total', 'H3 tag total', 'H4 tag total'
        - min: minimum count required
        - max: maximum count required
        - mean: average count across competitors
        - signalCnt: current count on target page
        - comment: text recommendation
        """
        analysis: dict[str, Any] = {
            "levels": [],
            "issues": [],
        }
        tag_counts = raw_data.get("tagCounts", [])

        if not isinstance(tag_counts, list):
            return analysis

        # Map tag labels to heading levels
        heading_labels = {
            "h1": ["h1 tag", "h1 total", "h1 tag total"],
            "h2": ["h2 tag", "h2 total", "h2 tag total"],
            "h3": ["h3 tag", "h3 total", "h3 tag total"],
            "h4": ["h4 tag", "h4 total", "h4 tag total"],
        }

        for tag in tag_counts:
            if not isinstance(tag, dict):
                continue

            tag_label = str(tag.get("tagLabel", "")).lower()

            for level, patterns in heading_labels.items():
                if any(pattern in tag_label for pattern in patterns):
                    current_raw = tag.get("signalCnt")
                    min_raw = tag.get("min")
                    max_raw = tag.get("max")
                    mean_raw = tag.get("mean")
                    comment = tag.get("comment")

                    # Convert to typed values for comparison
                    current_val: int | None = (
                        int(current_raw)
                        if isinstance(current_raw, (int, float))
                        else None
                    )
                    min_val: int | None = (
                        int(min_raw) if isinstance(min_raw, (int, float)) else None
                    )
                    max_val: int | None = (
                        int(max_raw) if isinstance(max_raw, (int, float)) else None
                    )
                    mean_val: float | None = (
                        float(mean_raw) if isinstance(mean_raw, (int, float)) else None
                    )

                    level_entry = {
                        "level": level,
                        "current": current_val,
                        "min": min_val,
                        "max": max_val,
                        "mean": mean_val,
                    }
                    analysis["levels"].append(level_entry)

                    # Track issues (current outside min/max range)
                    if (
                        current_val is not None
                        and min_val is not None
                        and current_val < min_val
                    ):
                        analysis["issues"].append(
                            {
                                "level": level,
                                "issue": "below_minimum",
                                "current": current_val,
                                "expected_min": min_val,
                                "comment": comment,
                            }
                        )
                    elif (
                        current_val is not None
                        and max_val is not None
                        and current_val > max_val
                    ):
                        analysis["issues"].append(
                            {
                                "level": level,
                                "issue": "above_maximum",
                                "current": current_val,
                                "expected_max": max_val,
                                "comment": comment,
                            }
                        )

                    break  # Found the level, move to next tag

        return analysis

    def _extract_recommendations(
        self, recommendations_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract recommendations from custom recommendations endpoint response.

        POP API provides recommendations grouped by type:
        - exactKeyword: recommendations for exact keyword placement
        - lsi: recommendations for LSI term usage
        - pageStructure: recommendations for heading/tag structure
        - variations: recommendations for keyword variations

        Each recommendation has:
        - signal: the signal/area being addressed (e.g., "Meta Title", "H2")
        - comment: the recommendation text
        - target: target count
        - editedCount/current: current count on page
        - competitorsAvg/mean: average across competitors
        """
        recommendations: list[dict[str, Any]] = []

        if not isinstance(recommendations_data, dict):
            return recommendations

        recs = recommendations_data.get("recommendations", {})
        if not isinstance(recs, dict):
            return recommendations

        # Process each recommendation category
        category_mapping = {
            "exactKeyword": "keyword",
            "lsi": "lsi",
            "pageStructure": "structure",
            "variations": "variations",
        }

        for pop_category, our_category in category_mapping.items():
            category_recs = recs.get(pop_category, [])
            if not isinstance(category_recs, list):
                continue

            for idx, rec in enumerate(category_recs):
                if not isinstance(rec, dict):
                    continue

                signal = rec.get("signal")
                comment = rec.get("comment")

                if not comment:
                    continue

                # Skip "Leave As Is" recommendations (not actionable)
                if (
                    isinstance(comment, str)
                    and comment.strip().lower() == "leave as is"
                ):
                    continue

                target = rec.get("target")
                # Different fields for current count depending on category
                current = (
                    rec.get("editedCount")
                    or rec.get("current")
                    or rec.get("targetKeywordCnt")
                    or rec.get("targetVariationCnt")
                    or rec.get("signalCnt")
                )
                competitors_avg = rec.get("competitorsAvg") or rec.get("mean")

                recommendations.append(
                    {
                        "category": our_category,
                        "signal": str(signal) if signal else None,
                        "recommendation": str(comment),
                        "target": int(target)
                        if isinstance(target, (int, float))
                        else None,
                        "current": int(current)
                        if isinstance(current, (int, float))
                        else None,
                        "competitors_avg": float(competitors_avg)
                        if isinstance(competitors_avg, (int, float))
                        else None,
                        "priority": idx + 1,  # Priority based on order in API response
                    }
                )

        return recommendations

    def _determine_pass_fail(
        self,
        page_score: float | None,
        recommendations: list[dict[str, Any]],
    ) -> tuple[bool, list[dict[str, Any]]]:
        """Determine if content passes the scoring threshold.

        Content passes if page_score >= configurable threshold (default 70).
        When content fails, returns prioritized recommendations.

        Args:
            page_score: The page score from POP (0-100)
            recommendations: List of recommendations from POP

        Returns:
            Tuple of (passed: bool, prioritized_recommendations: list)
            - passed is True if page_score >= threshold
            - prioritized_recommendations is non-empty only when passed is False
        """
        settings = get_settings()
        threshold = settings.pop_pass_threshold

        # Cannot determine pass/fail without a score
        if page_score is None:
            logger.warning(
                "Cannot determine pass/fail - page_score is None",
                extra={"threshold": threshold},
            )
            return False, recommendations

        passed = page_score >= threshold

        logger.info(
            "pass_fail_determination",
            extra={
                "page_score": page_score,
                "threshold": threshold,
                "passed": passed,
            },
        )

        # Return prioritized recommendations only when failed
        if passed:
            return True, []

        # Prioritize recommendations by category importance
        # Order: structure > keyword > lsi > variations
        category_priority = {
            "structure": 1,
            "keyword": 2,
            "lsi": 3,
            "variations": 4,
        }

        prioritized = sorted(
            recommendations,
            key=lambda r: (
                category_priority.get(r.get("category", ""), 99),
                r.get("priority", 999),
            ),
        )

        return False, prioritized

    async def score_content(
        self,
        project_id: str,
        page_id: str,
        keyword: str,
        content_url: str,
    ) -> POPContentScoreResult:
        """Score content from POP API for a keyword/URL.

        Creates a POP scoring task, polls for completion, and parses
        the results into a structured content score.

        Args:
            project_id: Project ID for logging context
            page_id: Page ID for logging context
            keyword: Target keyword for scoring
            content_url: URL of the content to score

        Returns:
            POPContentScoreResult with score data or error
        """
        start_time = time.monotonic()

        # Method entry log with sanitized parameters
        logger.debug(
            "score_content method entry",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "keyword": keyword[:50] if keyword else "",
                "content_url": content_url[:100] if content_url else "",
            },
        )

        # Validate inputs
        if not keyword or not keyword.strip():
            logger.warning(
                "Content score validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise POPContentScoreValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        if not content_url or not content_url.strip():
            logger.warning(
                "Content score validation failed - empty content_url",
                extra={
                    "field": "content_url",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise POPContentScoreValidationError(
                "content_url",
                "",
                "Content URL cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        keyword = keyword.strip()
        content_url = content_url.strip()

        try:
            client = await self._get_client()

            # Phase transition: score_started
            logger.info(
                "score_started",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "content_url": content_url[:100],
                },
            )

            # Step 1: Create report task for content scoring
            logger.info(
                "Creating POP report task for content scoring",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                },
            )

            task_result = await client.create_report_task(
                keyword=keyword,
                url=content_url,
            )

            if not task_result.success or not task_result.task_id:
                duration_ms = (time.monotonic() - start_time) * 1000
                logger.error(
                    "Failed to create POP report task for scoring",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "error": task_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                # Method exit log on task creation failure
                logger.debug(
                    "score_content method exit",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "success": False,
                        "score_id": None,
                        "error": task_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPContentScoreResult(
                    success=False,
                    keyword=keyword,
                    content_url=content_url,
                    error=task_result.error or "Failed to create report task",
                    duration_ms=duration_ms,
                    request_id=task_result.request_id,
                )

            task_id = task_result.task_id

            logger.info(
                "POP report task created, polling for results",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "task_id": task_id,
                },
            )

            # Step 2: Poll for task completion
            poll_result = await client.poll_for_result(task_id)

            if not poll_result.success:
                duration_ms = (time.monotonic() - start_time) * 1000
                logger.error(
                    "POP task polling failed for scoring",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "task_id": task_id,
                        "error": poll_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                # Method exit log on polling failure
                logger.debug(
                    "score_content method exit",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "task_id": task_id,
                        "success": False,
                        "score_id": None,
                        "error": poll_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPContentScoreResult(
                    success=False,
                    keyword=keyword,
                    content_url=content_url,
                    task_id=task_id,
                    error=poll_result.error or "Task polling failed",
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    request_id=poll_result.request_id,
                )

            if poll_result.status == POPTaskStatus.FAILURE:
                duration_ms = (time.monotonic() - start_time) * 1000
                error_msg = poll_result.data.get("error") if poll_result.data else None
                logger.error(
                    "POP task failed for scoring",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "task_id": task_id,
                        "error": error_msg,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                # Method exit log on task failure
                logger.debug(
                    "score_content method exit",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "task_id": task_id,
                        "success": False,
                        "score_id": None,
                        "error": error_msg,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPContentScoreResult(
                    success=False,
                    keyword=keyword,
                    content_url=content_url,
                    task_id=task_id,
                    error=error_msg or "Task failed",
                    raw_response=poll_result.data or {},
                    duration_ms=duration_ms,
                    request_id=poll_result.request_id,
                )

            # Step 3: Parse the response data
            raw_data = poll_result.data or {}
            parsed = self._parse_score_data(raw_data)

            duration_ms = (time.monotonic() - start_time) * 1000

            # Score extraction stats at INFO level
            logger.info(
                "score_extraction_stats",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "task_id": task_id,
                    "page_score": parsed.get("page_score"),
                    "word_count_current": parsed.get("word_count_current"),
                    "word_count_target": parsed.get("word_count_target"),
                    "lsi_term_count": len(
                        parsed.get("lsi_coverage", {}).get("terms", [])
                    ),
                    "lsi_coverage_percentage": parsed.get("lsi_coverage", {}).get(
                        "coverage_percentage"
                    ),
                    "keyword_section_count": len(
                        parsed.get("keyword_analysis", {}).get("sections", [])
                    ),
                    "heading_level_count": len(
                        parsed.get("heading_analysis", {}).get("levels", [])
                    ),
                    "heading_issue_count": len(
                        parsed.get("heading_analysis", {}).get("issues", [])
                    ),
                },
            )

            # Phase transition: score_completed
            logger.info(
                "score_completed",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "task_id": task_id,
                    "page_score": parsed.get("page_score"),
                    "success": True,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow content score operation",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "task_id": task_id,
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            # Determine pass/fail and get prioritized recommendations
            page_score = parsed.get("page_score")
            all_recommendations = parsed.get("recommendations", [])
            passed, prioritized_recs = self._determine_pass_fail(
                page_score, all_recommendations
            )

            result = POPContentScoreResult(
                success=True,
                keyword=keyword,
                content_url=content_url,
                task_id=task_id,
                page_score=page_score,
                passed=passed,
                keyword_analysis=parsed.get("keyword_analysis", {}),
                lsi_coverage=parsed.get("lsi_coverage", {}),
                word_count_current=parsed.get("word_count_current"),
                word_count_target=parsed.get("word_count_target"),
                heading_analysis=parsed.get("heading_analysis", {}),
                recommendations=prioritized_recs if not passed else all_recommendations,
                raw_response=raw_data,
                duration_ms=duration_ms,
                request_id=poll_result.request_id,
            )

            # Method exit log with result summary
            logger.debug(
                "score_content method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "task_id": task_id,
                    "success": True,
                    "passed": passed,
                    "score_id": None,  # Not saved yet at this point
                    "page_score": result.page_score,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return result

        except POPContentScoreValidationError:
            raise
        except POPError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "POP API error during content scoring",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Method exit log on error
            logger.debug(
                "score_content method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "success": False,
                    "score_id": None,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return POPContentScoreResult(
                success=False,
                keyword=keyword,
                content_url=content_url,
                error=str(e),
                duration_ms=duration_ms,
                request_id=getattr(e, "request_id", None),
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Unexpected error during content scoring",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Method exit log on unexpected error
            logger.debug(
                "score_content method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "success": False,
                    "score_id": None,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return POPContentScoreResult(
                success=False,
                keyword=keyword,
                content_url=content_url,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
            )


# Global singleton instance
_pop_content_score_service: POPContentScoreService | None = None


def get_pop_content_score_service() -> POPContentScoreService:
    """Get the global POP content score service instance.

    Usage:
        from app.services.pop_content_score import get_pop_content_score_service
        service = get_pop_content_score_service()
        result = await service.score_content(
            project_id="uuid",
            page_id="uuid",
            keyword="hiking boots",
            content_url="https://example.com/hiking-boots",
        )
    """
    global _pop_content_score_service
    if _pop_content_score_service is None:
        _pop_content_score_service = POPContentScoreService()
        logger.info("POPContentScoreService singleton created")
    return _pop_content_score_service


async def score_content(
    project_id: str,
    page_id: str,
    keyword: str,
    content_url: str,
) -> POPContentScoreResult:
    """Convenience function for scoring content.

    Args:
        project_id: Project ID for logging context
        page_id: Page ID for logging context
        keyword: Target keyword for scoring
        content_url: URL of the content to score

    Returns:
        POPContentScoreResult with score data or error
    """
    service = get_pop_content_score_service()
    return await service.score_content(
        project_id=project_id,
        page_id=page_id,
        keyword=keyword,
        content_url=content_url,
    )
