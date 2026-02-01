"""Phase 5A: PAA analysis by intent categorization service.

Analyzes PAA (People Also Ask) questions by grouping them according to user intent
and producing analysis output for content planning decisions.

Features:
- Groups PAA questions by intent category (buying, usage, care, comparison)
- Prioritizes questions: buying → care → usage (per content-generation spec)
- Selects top priority questions for content plan
- Provides intent distribution analysis for content angle decisions

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

from app.core.logging import get_logger
from app.services.paa_enrichment import PAAQuestion, PAAQuestionIntent

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
DEFAULT_TOP_PRIORITY_COUNT = 5


@dataclass
class IntentGroup:
    """A group of PAA questions sharing the same intent."""

    intent: PAAQuestionIntent
    questions: list[PAAQuestion] = field(default_factory=list)
    count: int = 0
    percentage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "intent": self.intent.value,
            "questions": [q.to_dict() for q in self.questions],
            "count": self.count,
            "percentage": round(self.percentage, 2),
        }


@dataclass
class ContentAngleRecommendation:
    """Recommended content angle based on PAA question distribution."""

    primary_angle: str
    reasoning: str
    focus_areas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "primary_angle": self.primary_angle,
            "reasoning": self.reasoning,
            "focus_areas": self.focus_areas,
        }


@dataclass
class PAAAnalysisResult:
    """Result of Phase 5A PAA analysis operation."""

    success: bool
    keyword: str
    total_questions: int = 0
    categorized_count: int = 0
    uncategorized_count: int = 0
    intent_groups: dict[str, IntentGroup] = field(default_factory=dict)
    priority_questions: list[PAAQuestion] = field(default_factory=list)
    content_angle: ContentAngleRecommendation | None = None
    intent_distribution: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "keyword": self.keyword,
            "total_questions": self.total_questions,
            "categorized_count": self.categorized_count,
            "uncategorized_count": self.uncategorized_count,
            "intent_groups": {k: v.to_dict() for k, v in self.intent_groups.items()},
            "priority_questions": [q.to_dict() for q in self.priority_questions],
            "content_angle": self.content_angle.to_dict() if self.content_angle else None,
            "intent_distribution": self.intent_distribution,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "project_id": self.project_id,
            "page_id": self.page_id,
        }


class PAAAnalysisServiceError(Exception):
    """Base exception for PAA analysis service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class PAAAnalysisValidationError(PAAAnalysisServiceError):
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


class PAAAnalysisService:
    """Service for Phase 5A PAA analysis by intent categorization.

    Analyzes PAA questions by:
    - Grouping by intent category
    - Prioritizing for content planning
    - Recommending content angle based on distribution

    Priority order (per content-generation spec):
    1. buying - Purchase decision questions (highest priority)
    2. care - Maintenance/longevity questions
    3. usage - How-to/instructional questions
    4. comparison - Comparison questions (included if top slots available)

    Usage:
        service = PAAAnalysisService()
        result = await service.analyze_paa_questions(
            questions=paa_questions,
            keyword="hiking boots",
            project_id="...",
        )
    """

    def __init__(
        self,
        top_priority_count: int = DEFAULT_TOP_PRIORITY_COUNT,
    ) -> None:
        """Initialize PAA analysis service.

        Args:
            top_priority_count: Number of top priority questions to select.
        """
        self._top_priority_count = top_priority_count

        logger.debug(
            "PAAAnalysisService initialized",
            extra={
                "top_priority_count": self._top_priority_count,
            },
        )

    def _group_by_intent(
        self,
        questions: list[PAAQuestion],
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> dict[str, IntentGroup]:
        """Group PAA questions by intent category.

        Args:
            questions: List of PAA questions (with intent already set)
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Dictionary mapping intent names to IntentGroup objects
        """
        logger.debug(
            "Grouping PAA questions by intent",
            extra={
                "question_count": len(questions),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Initialize groups for all intent types
        groups: dict[str, IntentGroup] = {}
        for intent in PAAQuestionIntent:
            groups[intent.value] = IntentGroup(intent=intent)

        # Assign questions to groups
        for question in questions:
            intent_value = question.intent.value
            groups[intent_value].questions.append(question)

        # Calculate counts and percentages
        total = len(questions)
        for group in groups.values():
            group.count = len(group.questions)
            group.percentage = (group.count / total * 100) if total > 0 else 0.0

        logger.debug(
            "PAA questions grouped by intent",
            extra={
                "question_count": len(questions),
                "buying_count": groups["buying"].count,
                "care_count": groups["care"].count,
                "usage_count": groups["usage"].count,
                "comparison_count": groups["comparison"].count,
                "unknown_count": groups["unknown"].count,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return groups

    def _select_priority_questions(
        self,
        groups: dict[str, IntentGroup],
        top_count: int,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> list[PAAQuestion]:
        """Select top priority questions for content planning.

        Priority order per content-generation spec:
        1. buying questions first
        2. care questions second
        3. usage questions third
        4. comparison questions if slots remain

        Args:
            groups: Intent groups from _group_by_intent
            top_count: Number of top questions to select
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            List of priority-ordered PAA questions
        """
        logger.debug(
            "Selecting priority PAA questions",
            extra={
                "top_count": top_count,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        priority_order = ["buying", "care", "usage", "comparison"]
        selected: list[PAAQuestion] = []

        for intent_name in priority_order:
            if len(selected) >= top_count:
                break

            group = groups.get(intent_name)
            if group and group.questions:
                remaining_slots = top_count - len(selected)
                # Take questions from this group, up to remaining slots
                selected.extend(group.questions[:remaining_slots])

        logger.debug(
            "Priority PAA questions selected",
            extra={
                "selected_count": len(selected),
                "top_count": top_count,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return selected

    def _determine_content_angle(
        self,
        groups: dict[str, IntentGroup],
        keyword: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> ContentAngleRecommendation:
        """Determine recommended content angle based on question distribution.

        From content-generation spec:
        - More care questions → focus on storage/freshness/longevity
        - More buying questions → focus on purchase decision/value
        - More usage questions → focus on practical benefits

        Args:
            groups: Intent groups from _group_by_intent
            keyword: The keyword being analyzed
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            ContentAngleRecommendation with primary angle and reasoning
        """
        logger.debug(
            "Determining content angle from question distribution",
            extra={
                "keyword": keyword[:50],
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Get counts for each primary intent
        buying_count = groups.get("buying", IntentGroup(PAAQuestionIntent.BUYING)).count
        care_count = groups.get("care", IntentGroup(PAAQuestionIntent.CARE)).count
        usage_count = groups.get("usage", IntentGroup(PAAQuestionIntent.USAGE)).count
        comparison_count = groups.get("comparison", IntentGroup(PAAQuestionIntent.COMPARISON)).count

        # Determine primary angle based on highest category
        if buying_count >= care_count and buying_count >= usage_count:
            primary_angle = "purchase_decision"
            reasoning = (
                f"Buying-focused questions dominate ({buying_count} questions). "
                "Content should emphasize value proposition, quality, and purchase guidance."
            )
            focus_areas = [
                "Product quality and value",
                "Buying recommendations",
                "Price comparison guidance",
                "Customer decision support",
            ]
        elif care_count >= buying_count and care_count >= usage_count:
            primary_angle = "longevity_maintenance"
            reasoning = (
                f"Care-focused questions dominate ({care_count} questions). "
                "Content should emphasize storage, maintenance, and product longevity."
            )
            focus_areas = [
                "Storage and preservation tips",
                "Maintenance instructions",
                "Product lifespan optimization",
                "Care best practices",
            ]
        elif usage_count >= buying_count and usage_count >= care_count:
            primary_angle = "practical_benefits"
            reasoning = (
                f"Usage-focused questions dominate ({usage_count} questions). "
                "Content should emphasize practical how-to guidance and benefits."
            )
            focus_areas = [
                "How-to instructions",
                "Practical applications",
                "Usage tips and techniques",
                "Benefit explanations",
            ]
        else:
            # Balanced distribution - default to purchase decision
            primary_angle = "balanced"
            reasoning = (
                "Question distribution is balanced across categories. "
                "Content should address buying decisions while touching on care and usage."
            )
            focus_areas = [
                "Balanced coverage of benefits",
                "Purchase guidance",
                "Basic care information",
                "Usage highlights",
            ]

        # Add comparison focus if significant comparison questions
        if comparison_count >= 3:
            focus_areas.append("Comparison with alternatives")

        recommendation = ContentAngleRecommendation(
            primary_angle=primary_angle,
            reasoning=reasoning,
            focus_areas=focus_areas,
        )

        logger.debug(
            "Content angle determined",
            extra={
                "keyword": keyword[:50],
                "primary_angle": primary_angle,
                "buying_count": buying_count,
                "care_count": care_count,
                "usage_count": usage_count,
                "comparison_count": comparison_count,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        return recommendation

    def _calculate_intent_distribution(
        self,
        groups: dict[str, IntentGroup],
    ) -> dict[str, float]:
        """Calculate percentage distribution of intents.

        Args:
            groups: Intent groups from _group_by_intent

        Returns:
            Dictionary mapping intent names to percentages
        """
        return {
            intent_name: round(group.percentage, 2)
            for intent_name, group in groups.items()
        }

    async def analyze_paa_questions(
        self,
        questions: list[PAAQuestion],
        keyword: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> PAAAnalysisResult:
        """Analyze PAA questions by intent categorization for Phase 5A.

        Takes PAA questions (with intents already assigned via categorization)
        and produces analysis output for content planning:
        - Groups by intent category
        - Selects priority questions
        - Recommends content angle

        Args:
            questions: List of PAA questions with intent field populated
            keyword: The keyword these questions are associated with
            project_id: Project ID for logging context
            page_id: Page ID for logging context

        Returns:
            PAAAnalysisResult with grouped questions, priorities, and recommendations
        """
        start_time = time.monotonic()

        logger.debug(
            "Phase 5A PAA analysis started",
            extra={
                "keyword": keyword[:50],
                "question_count": len(questions),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate inputs
        if not keyword or not keyword.strip():
            logger.warning(
                "PAA analysis validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise PAAAnalysisValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        keyword = keyword.strip()

        # Handle empty questions list
        if not questions:
            logger.info(
                "PAA analysis completed - no questions to analyze",
                extra={
                    "keyword": keyword[:50],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return PAAAnalysisResult(
                success=True,
                keyword=keyword,
                total_questions=0,
                project_id=project_id,
                page_id=page_id,
                duration_ms=0.0,
            )

        try:
            # Log phase transition
            logger.info(
                "Phase 5A: PAA analysis by intent categorization - in_progress",
                extra={
                    "keyword": keyword[:50],
                    "question_count": len(questions),
                    "phase": "5A",
                    "status": "in_progress",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Step 1: Group questions by intent
            intent_groups = self._group_by_intent(
                questions=questions,
                project_id=project_id,
                page_id=page_id,
            )

            # Step 2: Select priority questions
            priority_questions = self._select_priority_questions(
                groups=intent_groups,
                top_count=self._top_priority_count,
                project_id=project_id,
                page_id=page_id,
            )

            # Step 3: Determine content angle recommendation
            content_angle = self._determine_content_angle(
                groups=intent_groups,
                keyword=keyword,
                project_id=project_id,
                page_id=page_id,
            )

            # Step 4: Calculate intent distribution
            intent_distribution = self._calculate_intent_distribution(intent_groups)

            # Calculate counts
            total_questions = len(questions)
            categorized_count = sum(
                1 for q in questions if q.intent != PAAQuestionIntent.UNKNOWN
            )
            uncategorized_count = total_questions - categorized_count

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log completion
            logger.info(
                "Phase 5A: PAA analysis by intent categorization - completed",
                extra={
                    "keyword": keyword[:50],
                    "total_questions": total_questions,
                    "categorized_count": categorized_count,
                    "uncategorized_count": uncategorized_count,
                    "priority_questions_count": len(priority_questions),
                    "content_angle": content_angle.primary_angle,
                    "duration_ms": round(duration_ms, 2),
                    "phase": "5A",
                    "status": "completed",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow Phase 5A PAA analysis operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            return PAAAnalysisResult(
                success=True,
                keyword=keyword,
                total_questions=total_questions,
                categorized_count=categorized_count,
                uncategorized_count=uncategorized_count,
                intent_groups=intent_groups,
                priority_questions=priority_questions,
                content_angle=content_angle,
                intent_distribution=intent_distribution,
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

        except PAAAnalysisValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Phase 5A PAA analysis unexpected error",
                extra={
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return PAAAnalysisResult(
                success=False,
                keyword=keyword,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

    async def analyze_enrichment_result(
        self,
        keyword: str,
        questions: list[PAAQuestion],
        project_id: str | None = None,
        page_id: str | None = None,
        categorize_if_needed: bool = True,
    ) -> PAAAnalysisResult:
        """Analyze PAA questions from an enrichment result.

        Convenience method that takes PAAQuestion objects directly.
        If questions lack intent categorization and categorize_if_needed=True,
        it will call the categorization service first.

        Args:
            keyword: The keyword being analyzed
            questions: List of PAAQuestion objects
            project_id: Project ID for logging
            page_id: Page ID for logging
            categorize_if_needed: Whether to categorize uncategorized questions

        Returns:
            PAAAnalysisResult with analysis output
        """
        logger.debug(
            "Analyzing PAA enrichment result",
            extra={
                "keyword": keyword[:50],
                "question_count": len(questions),
                "categorize_if_needed": categorize_if_needed,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Check if questions need categorization
        uncategorized_count = sum(
            1 for q in questions if q.intent == PAAQuestionIntent.UNKNOWN
        )

        if categorize_if_needed and uncategorized_count > 0:
            logger.info(
                "Categorizing uncategorized PAA questions before analysis",
                extra={
                    "keyword": keyword[:50],
                    "uncategorized_count": uncategorized_count,
                    "total_count": len(questions),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Import here to avoid circular imports
            from app.services.paa_categorization import get_paa_categorization_service

            cat_service = get_paa_categorization_service()
            questions = await cat_service.categorize_paa_questions(
                paa_questions=questions,
                keyword=keyword,
                project_id=project_id,
                page_id=page_id,
            )

        return await self.analyze_paa_questions(
            questions=questions,
            keyword=keyword,
            project_id=project_id,
            page_id=page_id,
        )


# Global singleton instance
_paa_analysis_service: PAAAnalysisService | None = None


def get_paa_analysis_service() -> PAAAnalysisService:
    """Get the global PAA analysis service instance.

    Usage:
        from app.services.paa_analysis import get_paa_analysis_service
        service = get_paa_analysis_service()
        result = await service.analyze_paa_questions(questions, keyword)
    """
    global _paa_analysis_service
    if _paa_analysis_service is None:
        _paa_analysis_service = PAAAnalysisService()
        logger.info("PAAAnalysisService singleton created")
    return _paa_analysis_service


async def analyze_paa_questions(
    questions: list[PAAQuestion],
    keyword: str,
    project_id: str | None = None,
    page_id: str | None = None,
) -> PAAAnalysisResult:
    """Convenience function for Phase 5A PAA analysis.

    Args:
        questions: List of PAA questions with intent populated
        keyword: The keyword these questions are for
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        PAAAnalysisResult with grouped questions and content angle
    """
    service = get_paa_analysis_service()
    return await service.analyze_paa_questions(
        questions=questions,
        keyword=keyword,
        project_id=project_id,
        page_id=page_id,
    )
