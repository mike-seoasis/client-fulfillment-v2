"""Phase 5A: Content plan builder service.

Builds content plans by combining PAA analysis with Perplexity research:
- PAA analysis provides main angle recommendation and priority questions
- Perplexity research provides benefits and competitive differentiators
- Output is a synthesized content plan for content creation

Features:
- Combines PAA enrichment, categorization, and analysis
- Integrates Perplexity web research for benefits extraction
- Produces actionable content plan with main angle, benefits, and questions

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import asyncio
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.perplexity import CompletionResult, get_perplexity
from app.services.paa_analysis import (
    ContentAngleRecommendation,
    PAAAnalysisResult,
    get_paa_analysis_service,
)
from app.services.paa_enrichment import (
    PAAEnrichmentResult,
    PAAQuestion,
    enrich_keyword_paa,
    enrich_keyword_paa_cached,
)

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
DEFAULT_MAX_BENEFITS = 5
DEFAULT_MAX_PRIORITY_QUESTIONS = 5


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class Benefit:
    """A single benefit extracted from research."""

    benefit: str
    source: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "benefit": self.benefit,
            "source": self.source,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class PriorityQuestion:
    """A prioritized PAA question for content planning."""

    question: str
    intent: str
    priority_rank: int
    answer_snippet: str | None = None
    source_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "question": self.question,
            "intent": self.intent,
            "priority_rank": self.priority_rank,
            "answer_snippet": self.answer_snippet,
            "source_url": self.source_url,
        }


@dataclass
class ContentPlanResult:
    """Result of Phase 5A content plan building."""

    success: bool
    keyword: str
    main_angle: ContentAngleRecommendation | None = None
    benefits: list[Benefit] = field(default_factory=list)
    priority_questions: list[PriorityQuestion] = field(default_factory=list)
    intent_distribution: dict[str, float] = field(default_factory=dict)
    total_questions_analyzed: int = 0
    perplexity_used: bool = False
    perplexity_citations: list[str] = field(default_factory=list)
    error: str | None = None
    partial_success: bool = False
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "keyword": self.keyword,
            "main_angle": self.main_angle.to_dict() if self.main_angle else None,
            "benefits": [b.to_dict() for b in self.benefits],
            "priority_questions": [q.to_dict() for q in self.priority_questions],
            "intent_distribution": self.intent_distribution,
            "total_questions_analyzed": self.total_questions_analyzed,
            "perplexity_used": self.perplexity_used,
            "perplexity_citations": self.perplexity_citations,
            "error": self.error,
            "partial_success": self.partial_success,
            "duration_ms": round(self.duration_ms, 2),
            "project_id": self.project_id,
            "page_id": self.page_id,
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================


class ContentPlanServiceError(Exception):
    """Base exception for content plan service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class ContentPlanValidationError(ContentPlanServiceError):
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


# =============================================================================
# PERPLEXITY PROMPTS
# =============================================================================


BENEFITS_SYSTEM_PROMPT = """You are an expert content strategist. Your task is to extract key product/service benefits from web research that would be valuable for content planning.

Focus on:
1. Concrete, specific benefits (not vague claims)
2. Benefits that address user pain points or needs
3. Unique differentiators and competitive advantages
4. Benefits supported by evidence or data

Return ONLY a JSON array of benefit strings. Each benefit should be:
- Clear and concise (1-2 sentences max)
- Actionable for content creation
- Focused on customer value

Example format:
["Benefit 1 statement here", "Benefit 2 statement here", "Benefit 3 statement here"]"""


def _build_benefits_prompt(keyword: str, max_benefits: int) -> str:
    """Build the user prompt for benefits extraction."""
    return f"""Research the topic "{keyword}" and extract the top {max_benefits} key benefits that customers care about.

Consider:
- What problems does this product/service solve?
- What makes it valuable compared to alternatives?
- What do customers appreciate most about it?
- What unique advantages does it offer?

Return ONLY a JSON array with exactly {max_benefits} benefit strings (or fewer if not enough found).
Do not include any explanation or markdown formatting - just the JSON array."""


# =============================================================================
# SERVICE
# =============================================================================


class ContentPlanService:
    """Service for Phase 5A content plan building.

    Combines PAA analysis with Perplexity research to create content plans:
    1. Enriches keyword with PAA questions
    2. Categorizes and analyzes questions for main angle
    3. Uses Perplexity to research benefits
    4. Synthesizes into actionable content plan

    Usage:
        service = ContentPlanService()
        result = await service.build_content_plan(
            keyword="hiking boots",
            project_id="...",
        )
    """

    def __init__(
        self,
        max_benefits: int = DEFAULT_MAX_BENEFITS,
        max_priority_questions: int = DEFAULT_MAX_PRIORITY_QUESTIONS,
    ) -> None:
        """Initialize content plan service.

        Args:
            max_benefits: Maximum benefits to extract from research.
            max_priority_questions: Maximum priority questions to include.
        """
        self._max_benefits = max_benefits
        self._max_priority_questions = max_priority_questions

        logger.debug(
            "ContentPlanService initialized",
            extra={
                "max_benefits": self._max_benefits,
                "max_priority_questions": self._max_priority_questions,
            },
        )

    async def _enrich_and_analyze_paa(
        self,
        keyword: str,
        location_code: int,
        language_code: str,
        fanout_enabled: bool,
        use_cache: bool,
        project_id: str | None,
        page_id: str | None,
    ) -> tuple[PAAEnrichmentResult | None, PAAAnalysisResult | None]:
        """Enrich keyword with PAA and analyze by intent.

        Args:
            keyword: Keyword to enrich
            location_code: Location code
            language_code: Language code
            fanout_enabled: Whether to fan-out PAA questions
            use_cache: Whether to use cached results
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Tuple of (enrichment result, analysis result)
        """
        logger.debug(
            "Starting PAA enrichment and analysis",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "fanout_enabled": fanout_enabled,
                "use_cache": use_cache,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        try:
            # Step 1: Enrich keyword with PAA questions
            if use_cache:
                enrichment_result = await enrich_keyword_paa_cached(
                    keyword=keyword,
                    location_code=location_code,
                    language_code=language_code,
                    fanout_enabled=fanout_enabled,
                    categorize_enabled=True,  # Need intent for analysis
                    project_id=project_id,
                    page_id=page_id,
                )
            else:
                enrichment_result = await enrich_keyword_paa(
                    keyword=keyword,
                    location_code=location_code,
                    language_code=language_code,
                    fanout_enabled=fanout_enabled,
                    categorize_enabled=True,
                    project_id=project_id,
                    page_id=page_id,
                )

            if not enrichment_result.success:
                logger.warning(
                    "PAA enrichment failed",
                    extra={
                        "keyword": keyword[:50],
                        "error": enrichment_result.error,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return enrichment_result, None

            logger.debug(
                "PAA enrichment complete",
                extra={
                    "keyword": keyword[:50],
                    "question_count": len(enrichment_result.questions),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Step 2: Analyze questions by intent
            if enrichment_result.questions:
                analysis_service = get_paa_analysis_service()
                analysis_result = await analysis_service.analyze_paa_questions(
                    questions=enrichment_result.questions,
                    keyword=keyword,
                    project_id=project_id,
                    page_id=page_id,
                )

                logger.debug(
                    "PAA analysis complete",
                    extra={
                        "keyword": keyword[:50],
                        "content_angle": (
                            analysis_result.content_angle.primary_angle
                            if analysis_result.content_angle
                            else None
                        ),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

                return enrichment_result, analysis_result
            else:
                logger.debug(
                    "No PAA questions to analyze",
                    extra={
                        "keyword": keyword[:50],
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return enrichment_result, None

        except Exception as e:
            logger.error(
                "PAA enrichment/analysis failed",
                extra={
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return None, None

    async def _research_benefits(
        self,
        keyword: str,
        max_benefits: int,
        project_id: str | None,
        page_id: str | None,
    ) -> tuple[list[Benefit], list[str]]:
        """Research benefits using Perplexity.

        Args:
            keyword: Keyword to research
            max_benefits: Maximum benefits to extract
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Tuple of (list of benefits, list of citations)
        """
        logger.debug(
            "Starting Perplexity benefits research",
            extra={
                "keyword": keyword[:50],
                "max_benefits": max_benefits,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        try:
            perplexity = await get_perplexity()

            if not perplexity.available:
                logger.info(
                    "Perplexity not available, skipping benefits research",
                    extra={
                        "keyword": keyword[:50],
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return [], []

            # Build and send prompt
            user_prompt = _build_benefits_prompt(keyword, max_benefits)
            result: CompletionResult = await perplexity.complete(
                user_prompt=user_prompt,
                system_prompt=BENEFITS_SYSTEM_PROMPT,
                temperature=0.3,  # Slightly higher for variety
                return_citations=True,
            )

            if not result.success or not result.text:
                logger.warning(
                    "Perplexity benefits research failed",
                    extra={
                        "keyword": keyword[:50],
                        "error": result.error,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return [], []

            # Parse benefits from JSON response
            benefits = self._parse_benefits_response(
                result.text, result.citations, project_id, page_id
            )

            logger.debug(
                "Perplexity benefits research complete",
                extra={
                    "keyword": keyword[:50],
                    "benefits_count": len(benefits),
                    "citations_count": len(result.citations),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            return benefits, result.citations

        except Exception as e:
            logger.error(
                "Perplexity benefits research error",
                extra={
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return [], []

    def _parse_benefits_response(
        self,
        response_text: str,
        citations: list[str],
        project_id: str | None,
        page_id: str | None,
    ) -> list[Benefit]:
        """Parse benefits from Perplexity response.

        Args:
            response_text: Raw response text from Perplexity
            citations: Citations from the response
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            List of Benefit objects
        """
        import json

        benefits: list[Benefit] = []

        try:
            # Try to parse as JSON array
            # Handle potential markdown code blocks
            text = response_text.strip()
            if text.startswith("```"):
                # Remove markdown code blocks
                lines = text.split("\n")
                text = "\n".join(
                    line for line in lines if not line.startswith("```")
                ).strip()

            # Remove any "json" label
            if text.startswith("json"):
                text = text[4:].strip()

            parsed = json.loads(text)

            if isinstance(parsed, list):
                for idx, item in enumerate(parsed):
                    if isinstance(item, str) and item.strip():
                        # Assign source from citations if available
                        source = citations[idx] if idx < len(citations) else "research"
                        benefits.append(
                            Benefit(
                                benefit=item.strip(),
                                source=source,
                                confidence=0.8,  # Default confidence for research
                            )
                        )

            logger.debug(
                "Parsed benefits from response",
                extra={
                    "benefits_count": len(benefits),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse benefits JSON",
                extra={
                    "error": str(e),
                    "response_preview": response_text[:200],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            # Fallback: try to extract bullet points
            benefits = self._extract_benefits_fallback(response_text)

        return benefits

    def _extract_benefits_fallback(self, text: str) -> list[Benefit]:
        """Fallback extraction of benefits from non-JSON text.

        Args:
            text: Response text to parse

        Returns:
            List of Benefit objects
        """
        benefits: list[Benefit] = []
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            # Look for bullet points or numbered items
            if line.startswith(("-", "*", "•")) or (
                len(line) > 2 and line[0].isdigit() and line[1] in ".)"
            ):
                # Remove bullet/number
                benefit_text = line.lstrip("-*•0123456789.) ").strip()
                if benefit_text and len(benefit_text) > 10:  # Filter short fragments
                    benefits.append(
                        Benefit(
                            benefit=benefit_text,
                            source="research",
                            confidence=0.6,  # Lower confidence for fallback
                        )
                    )

        return benefits

    def _convert_paa_to_priority_questions(
        self,
        paa_questions: list[PAAQuestion],
        max_questions: int,
    ) -> list[PriorityQuestion]:
        """Convert PAA questions to priority questions.

        Args:
            paa_questions: PAA questions from analysis (already prioritized)
            max_questions: Maximum questions to include

        Returns:
            List of PriorityQuestion objects
        """
        priority_questions: list[PriorityQuestion] = []

        for idx, paa in enumerate(paa_questions[:max_questions]):
            priority_questions.append(
                PriorityQuestion(
                    question=paa.question,
                    intent=paa.intent.value,
                    priority_rank=idx + 1,
                    answer_snippet=paa.answer_snippet,
                    source_url=paa.source_url,
                )
            )

        return priority_questions

    async def build_content_plan(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        include_perplexity_research: bool = True,
        max_benefits: int | None = None,
        max_priority_questions: int | None = None,
        fanout_enabled: bool = True,
        use_cache: bool = True,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> ContentPlanResult:
        """Build a content plan for a keyword.

        Phase 5A content plan building:
        1. Enrich keyword with PAA questions (via DataForSEO)
        2. Categorize questions by intent (via Claude)
        3. Analyze to determine main angle and priority questions
        4. Research benefits via Perplexity (optional)
        5. Synthesize into content plan

        Args:
            keyword: Primary keyword for content planning
            location_code: Location code (e.g., 2840 for US)
            language_code: Language code (e.g., 'en')
            include_perplexity_research: Whether to include Perplexity research
            max_benefits: Maximum benefits to extract (None = use default)
            max_priority_questions: Maximum priority questions (None = use default)
            fanout_enabled: Whether to fan-out PAA questions
            use_cache: Whether to use cached PAA results
            project_id: Project ID for logging context
            page_id: Page ID for logging context

        Returns:
            ContentPlanResult with content plan or error
        """
        start_time = time.monotonic()
        max_benefits = max_benefits or self._max_benefits
        max_priority_questions = max_priority_questions or self._max_priority_questions

        logger.debug(
            "Phase 5A content plan building started",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "language_code": language_code,
                "include_perplexity_research": include_perplexity_research,
                "max_benefits": max_benefits,
                "max_priority_questions": max_priority_questions,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate inputs
        if not keyword or not keyword.strip():
            logger.warning(
                "Content plan validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise ContentPlanValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        keyword = keyword.strip()

        try:
            # Log phase transition
            logger.info(
                "Phase 5A: Content plan builder - in_progress",
                extra={
                    "keyword": keyword[:50],
                    "phase": "5A",
                    "status": "in_progress",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Run PAA enrichment/analysis and Perplexity research concurrently
            paa_task = self._enrich_and_analyze_paa(
                keyword=keyword,
                location_code=location_code,
                language_code=language_code,
                fanout_enabled=fanout_enabled,
                use_cache=use_cache,
                project_id=project_id,
                page_id=page_id,
            )

            if include_perplexity_research:
                benefits_task = self._research_benefits(
                    keyword=keyword,
                    max_benefits=max_benefits,
                    project_id=project_id,
                    page_id=page_id,
                )
                # Run both tasks concurrently
                (enrichment_result, analysis_result), (benefits, citations) = (
                    await asyncio.gather(paa_task, benefits_task)
                )
            else:
                enrichment_result, analysis_result = await paa_task
                benefits = []
                citations = []

            # Build result
            main_angle: ContentAngleRecommendation | None = None
            priority_questions: list[PriorityQuestion] = []
            intent_distribution: dict[str, float] = {}
            total_questions_analyzed = 0
            partial_success = False

            if analysis_result and analysis_result.success:
                main_angle = analysis_result.content_angle
                intent_distribution = analysis_result.intent_distribution
                total_questions_analyzed = analysis_result.total_questions

                # Convert priority questions
                if analysis_result.priority_questions:
                    priority_questions = self._convert_paa_to_priority_questions(
                        analysis_result.priority_questions,
                        max_priority_questions,
                    )
            elif enrichment_result:
                # Partial success: enrichment worked but analysis didn't
                partial_success = True
                total_questions_analyzed = len(enrichment_result.questions)

            # Determine overall success
            success = (
                (analysis_result is not None and analysis_result.success)
                or len(benefits) > 0
                or len(priority_questions) > 0
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log completion
            logger.info(
                "Phase 5A: Content plan builder - completed",
                extra={
                    "keyword": keyword[:50],
                    "success": success,
                    "partial_success": partial_success,
                    "main_angle": main_angle.primary_angle if main_angle else None,
                    "benefits_count": len(benefits),
                    "questions_count": len(priority_questions),
                    "total_questions_analyzed": total_questions_analyzed,
                    "perplexity_used": include_perplexity_research and len(benefits) > 0,
                    "duration_ms": round(duration_ms, 2),
                    "phase": "5A",
                    "status": "completed",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow Phase 5A content plan operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            return ContentPlanResult(
                success=success,
                keyword=keyword,
                main_angle=main_angle,
                benefits=benefits,
                priority_questions=priority_questions,
                intent_distribution=intent_distribution,
                total_questions_analyzed=total_questions_analyzed,
                perplexity_used=include_perplexity_research and len(benefits) > 0,
                perplexity_citations=citations,
                partial_success=partial_success,
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

        except ContentPlanValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Phase 5A content plan unexpected error",
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
            return ContentPlanResult(
                success=False,
                keyword=keyword,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

    async def build_content_plans_batch(
        self,
        keywords: list[str],
        location_code: int = 2840,
        language_code: str = "en",
        include_perplexity_research: bool = True,
        max_benefits: int | None = None,
        max_priority_questions: int | None = None,
        max_concurrent: int = 3,
        project_id: str | None = None,
    ) -> list[ContentPlanResult]:
        """Build content plans for multiple keywords.

        Args:
            keywords: Keywords to build plans for
            location_code: Location code
            language_code: Language code
            include_perplexity_research: Whether to include Perplexity research
            max_benefits: Maximum benefits per keyword
            max_priority_questions: Maximum priority questions per keyword
            max_concurrent: Maximum concurrent plan builds
            project_id: Project ID for logging

        Returns:
            List of ContentPlanResult, one per keyword
        """
        start_time = time.monotonic()

        logger.info(
            "Batch content plan building started",
            extra={
                "keyword_count": len(keywords),
                "include_perplexity_research": include_perplexity_research,
                "max_concurrent": max_concurrent,
                "project_id": project_id,
            },
        )

        if not keywords:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        async def build_one(keyword: str) -> ContentPlanResult:
            async with semaphore:
                return await self.build_content_plan(
                    keyword=keyword,
                    location_code=location_code,
                    language_code=language_code,
                    include_perplexity_research=include_perplexity_research,
                    max_benefits=max_benefits,
                    max_priority_questions=max_priority_questions,
                    project_id=project_id,
                )

        tasks = [build_one(kw) for kw in keywords]
        results = await asyncio.gather(*tasks)

        duration_ms = (time.monotonic() - start_time) * 1000
        success_count = sum(1 for r in results if r.success)

        logger.info(
            "Batch content plan building complete",
            extra={
                "keyword_count": len(keywords),
                "success_count": success_count,
                "duration_ms": round(duration_ms, 2),
                "project_id": project_id,
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch content plan operation",
                extra={
                    "keyword_count": len(keywords),
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                },
            )

        return list(results)


# =============================================================================
# SINGLETON
# =============================================================================


_content_plan_service: ContentPlanService | None = None


def get_content_plan_service() -> ContentPlanService:
    """Get the global content plan service instance.

    Usage:
        from app.services.content_plan import get_content_plan_service
        service = get_content_plan_service()
        result = await service.build_content_plan("hiking boots")
    """
    global _content_plan_service
    if _content_plan_service is None:
        _content_plan_service = ContentPlanService()
        logger.info("ContentPlanService singleton created")
    return _content_plan_service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def build_content_plan(
    keyword: str,
    location_code: int = 2840,
    language_code: str = "en",
    include_perplexity_research: bool = True,
    max_benefits: int | None = None,
    max_priority_questions: int | None = None,
    fanout_enabled: bool = True,
    use_cache: bool = True,
    project_id: str | None = None,
    page_id: str | None = None,
) -> ContentPlanResult:
    """Convenience function for Phase 5A content plan building.

    Args:
        keyword: Primary keyword for content planning
        location_code: Location code
        language_code: Language code
        include_perplexity_research: Whether to include Perplexity research
        max_benefits: Maximum benefits to extract
        max_priority_questions: Maximum priority questions
        fanout_enabled: Whether to fan-out PAA questions
        use_cache: Whether to use cached PAA results
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        ContentPlanResult with content plan
    """
    service = get_content_plan_service()
    return await service.build_content_plan(
        keyword=keyword,
        location_code=location_code,
        language_code=language_code,
        include_perplexity_research=include_perplexity_research,
        max_benefits=max_benefits,
        max_priority_questions=max_priority_questions,
        fanout_enabled=fanout_enabled,
        use_cache=use_cache,
        project_id=project_id,
        page_id=page_id,
    )
