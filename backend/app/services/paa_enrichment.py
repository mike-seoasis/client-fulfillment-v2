"""PAA (People Also Ask) enrichment service with fan-out strategy.

Implements fan-out strategy for PAA question discovery:
1. Fetch initial PAA questions for a keyword using DataForSEO SERP API
2. Optionally search each initial PAA question for nested questions (fan-out)
3. De-duplicate and collect all discovered questions

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
from enum import Enum
from typing import Any

from app.core.logging import get_logger
from app.integrations.dataforseo import (
    DataForSEOClient,
    DataForSEOError,
    get_dataforseo,
)

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
DEFAULT_PAA_CLICK_DEPTH = 2  # 1-4, each click costs $0.00015
DEFAULT_MAX_CONCURRENT_FANOUT = 5
DEFAULT_MAX_FANOUT_QUESTIONS = 10  # Limit fanout to first N initial questions


class PAAQuestionIntent(Enum):
    """Intent categories for PAA questions.

    Used for categorizing questions by user intent.
    Actual categorization is handled by separate service (story c3y.60).
    """

    BUYING = "buying"
    USAGE = "usage"
    CARE = "care"
    COMPARISON = "comparison"
    UNKNOWN = "unknown"


@dataclass
class PAAQuestion:
    """A single PAA question with metadata."""

    question: str
    answer_snippet: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    position: int | None = None
    is_nested: bool = False  # True if from fan-out
    parent_question: str | None = None  # The question that led to this one
    intent: PAAQuestionIntent = PAAQuestionIntent.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "question": self.question,
            "answer_snippet": self.answer_snippet,
            "source_url": self.source_url,
            "source_domain": self.source_domain,
            "position": self.position,
            "is_nested": self.is_nested,
            "parent_question": self.parent_question,
            "intent": self.intent.value,
        }


@dataclass
class PAAEnrichmentResult:
    """Result of PAA enrichment operation."""

    success: bool
    keyword: str
    questions: list[PAAQuestion] = field(default_factory=list)
    initial_count: int = 0  # Count from initial search
    nested_count: int = 0  # Count from fan-out
    error: str | None = None
    cost: float | None = None
    duration_ms: float = 0.0
    request_id: str | None = None

    @property
    def total_count(self) -> int:
        """Total number of questions discovered."""
        return len(self.questions)


class PAAEnrichmentServiceError(Exception):
    """Base exception for PAA enrichment service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class PAAValidationError(PAAEnrichmentServiceError):
    """Raised when validation fails."""

    def __init__(
        self,
        field_name: str,
        value: str,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(f"Validation error for {field_name}: {message}", project_id, page_id)
        self.field_name = field_name
        self.value = value


class PAAEnrichmentService:
    """Service for PAA enrichment with fan-out strategy.

    Features:
    - Fetches PAA questions from DataForSEO SERP API
    - Uses people_also_ask_click_depth for nested questions
    - Fan-out strategy: search initial questions for more related questions
    - De-duplication of discovered questions
    - Comprehensive logging per requirements

    Usage:
        service = PAAEnrichmentService()
        result = await service.enrich_keyword(
            keyword="best hiking boots",
            fanout_enabled=True,
            max_fanout_questions=5,
        )
    """

    def __init__(
        self,
        client: DataForSEOClient | None = None,
        paa_click_depth: int = DEFAULT_PAA_CLICK_DEPTH,
        max_concurrent_fanout: int = DEFAULT_MAX_CONCURRENT_FANOUT,
    ) -> None:
        """Initialize PAA enrichment service.

        Args:
            client: DataForSEO client instance. If None, uses global instance.
            paa_click_depth: Click depth for PAA expansion (1-4).
            max_concurrent_fanout: Max concurrent fan-out requests.
        """
        self._client = client
        self._paa_click_depth = min(max(paa_click_depth, 1), 4)  # Clamp to 1-4
        self._max_concurrent_fanout = max_concurrent_fanout
        self._seen_questions: set[str] = set()

        logger.debug(
            "PAAEnrichmentService initialized",
            extra={
                "paa_click_depth": self._paa_click_depth,
                "max_concurrent_fanout": self._max_concurrent_fanout,
            },
        )

    async def _get_client(self) -> DataForSEOClient:
        """Get DataForSEO client instance."""
        if self._client is None:
            self._client = await get_dataforseo()
        return self._client

    def _normalize_question(self, question: str) -> str:
        """Normalize question for deduplication."""
        return question.lower().strip().rstrip("?")

    def _is_duplicate(self, question: str) -> bool:
        """Check if question is a duplicate."""
        normalized = self._normalize_question(question)
        return normalized in self._seen_questions

    def _mark_seen(self, question: str) -> None:
        """Mark question as seen for deduplication."""
        normalized = self._normalize_question(question)
        self._seen_questions.add(normalized)

    def _parse_paa_items(
        self,
        items: list[dict[str, Any]],
        is_nested: bool = False,
        parent_question: str | None = None,
    ) -> list[PAAQuestion]:
        """Parse PAA items from SERP API response.

        Args:
            items: List of SERP items from API response
            is_nested: Whether these are from fan-out
            parent_question: The parent question for nested items

        Returns:
            List of PAAQuestion objects
        """
        questions: list[PAAQuestion] = []

        for item in items:
            # Check for people_also_ask type
            if item.get("type") != "people_also_ask":
                continue

            # PAA items contain nested items
            paa_items = item.get("items", [])
            for idx, paa_item in enumerate(paa_items):
                if paa_item.get("type") != "people_also_ask_element":
                    continue

                question_text = paa_item.get("title", "").strip()
                if not question_text:
                    continue

                # Skip duplicates
                if self._is_duplicate(question_text):
                    logger.debug(
                        "Skipping duplicate PAA question",
                        extra={"question": question_text[:50]},
                    )
                    continue

                self._mark_seen(question_text)

                # Extract answer from expanded_element
                answer_snippet = None
                source_url = None
                source_domain = None

                expanded = paa_item.get("expanded_element", [])
                if expanded and len(expanded) > 0:
                    first_expanded = expanded[0]
                    # Handle standard expanded element
                    if first_expanded.get("type") == "people_also_ask_expanded_element":
                        answer_snippet = first_expanded.get("description")
                        source_url = first_expanded.get("url")
                        source_domain = first_expanded.get("domain")
                    # Handle AI overview expanded element
                    elif first_expanded.get("type") == "people_also_ask_ai_overview_expanded_element":
                        ai_items = first_expanded.get("items", [])
                        if ai_items:
                            answer_snippet = ai_items[0].get("text")
                            refs = ai_items[0].get("references", [])
                            if refs:
                                source_url = refs[0].get("url")
                                source_domain = refs[0].get("source")

                questions.append(
                    PAAQuestion(
                        question=question_text,
                        answer_snippet=answer_snippet,
                        source_url=source_url,
                        source_domain=source_domain,
                        position=idx + 1,
                        is_nested=is_nested,
                        parent_question=parent_question,
                    )
                )

        return questions

    async def _fetch_paa_for_keyword(
        self,
        keyword: str,
        location_code: int,
        language_code: str,
        is_nested: bool = False,
        parent_question: str | None = None,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> tuple[list[PAAQuestion], float | None]:
        """Fetch PAA questions for a keyword.

        Args:
            keyword: Keyword to search
            location_code: Location code (e.g., 2840 for US)
            language_code: Language code (e.g., 'en')
            is_nested: Whether this is a fan-out search
            parent_question: Parent question for nested searches
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Tuple of (list of PAAQuestion, API cost)
        """
        start_time = time.monotonic()
        client = await self._get_client()

        logger.debug(
            "Fetching PAA for keyword",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "language_code": language_code,
                "is_nested": is_nested,
                "paa_click_depth": self._paa_click_depth,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Build request payload for advanced endpoint
        payload = [
            {
                "keyword": keyword,
                "location_code": location_code,
                "language_code": language_code,
                "depth": 10,  # Only need top results for PAA
                "people_also_ask_click_depth": self._paa_click_depth,
            }
        ]

        endpoint = "/v3/serp/google/organic/live/advanced"

        try:
            response_data, request_id = await client._make_request(endpoint, payload)
            cost = response_data.get("cost")

            # Parse PAA items from response
            questions: list[PAAQuestion] = []
            tasks = response_data.get("tasks", [])
            for task in tasks:
                task_results = task.get("result", [])
                for task_result in task_results:
                    items = task_result.get("items", [])
                    questions.extend(
                        self._parse_paa_items(items, is_nested, parent_question)
                    )

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "PAA fetch complete",
                extra={
                    "keyword": keyword[:50],
                    "questions_found": len(questions),
                    "duration_ms": round(duration_ms, 2),
                    "cost": cost,
                    "is_nested": is_nested,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow PAA fetch operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return questions, cost

        except DataForSEOError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "PAA fetch failed",
                extra={
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "is_nested": is_nested,
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise

    async def enrich_keyword(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        fanout_enabled: bool = True,
        max_fanout_questions: int = DEFAULT_MAX_FANOUT_QUESTIONS,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> PAAEnrichmentResult:
        """Enrich a keyword with PAA questions using fan-out strategy.

        Args:
            keyword: Primary keyword to enrich
            location_code: Location code (e.g., 2840 for US)
            language_code: Language code (e.g., 'en')
            fanout_enabled: Whether to search initial questions for nested
            max_fanout_questions: Max initial questions to fan-out on
            project_id: Project ID for logging context
            page_id: Page ID for logging context

        Returns:
            PAAEnrichmentResult with discovered questions
        """
        start_time = time.monotonic()

        # Reset seen questions for this enrichment run
        self._seen_questions.clear()

        logger.debug(
            "PAA enrichment started",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "language_code": language_code,
                "fanout_enabled": fanout_enabled,
                "max_fanout_questions": max_fanout_questions,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate inputs
        if not keyword or not keyword.strip():
            logger.warning(
                "PAA enrichment validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise PAAValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        keyword = keyword.strip()
        total_cost: float = 0.0

        try:
            # Step 1: Fetch initial PAA questions
            logger.info(
                "Fetching initial PAA questions",
                extra={
                    "keyword": keyword[:50],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            initial_questions, initial_cost = await self._fetch_paa_for_keyword(
                keyword=keyword,
                location_code=location_code,
                language_code=language_code,
                is_nested=False,
                project_id=project_id,
                page_id=page_id,
            )

            if initial_cost:
                total_cost += initial_cost

            all_questions = list(initial_questions)
            initial_count = len(initial_questions)

            logger.info(
                "Initial PAA questions fetched",
                extra={
                    "keyword": keyword[:50],
                    "initial_count": initial_count,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Step 2: Fan-out on initial questions
            nested_count = 0
            if fanout_enabled and initial_questions:
                # Limit fan-out to first N questions
                fanout_questions = initial_questions[:max_fanout_questions]

                logger.info(
                    "Starting PAA fan-out",
                    extra={
                        "keyword": keyword[:50],
                        "fanout_count": len(fanout_questions),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

                # Use semaphore for rate limiting
                semaphore = asyncio.Semaphore(self._max_concurrent_fanout)

                async def fanout_search(question: PAAQuestion) -> tuple[list[PAAQuestion], float]:
                    """Search a question for nested PAA."""
                    async with semaphore:
                        try:
                            nested, cost = await self._fetch_paa_for_keyword(
                                keyword=question.question,
                                location_code=location_code,
                                language_code=language_code,
                                is_nested=True,
                                parent_question=question.question,
                                project_id=project_id,
                                page_id=page_id,
                            )
                            return nested, cost or 0.0
                        except DataForSEOError as e:
                            logger.warning(
                                "Fan-out search failed for question",
                                extra={
                                    "question": question.question[:50],
                                    "error": str(e),
                                    "project_id": project_id,
                                    "page_id": page_id,
                                },
                            )
                            return [], 0.0

                # Execute fan-out searches
                fanout_tasks = [fanout_search(q) for q in fanout_questions]
                fanout_results = await asyncio.gather(*fanout_tasks)

                for nested_questions, cost in fanout_results:
                    all_questions.extend(nested_questions)
                    nested_count += len(nested_questions)
                    total_cost += cost

                logger.info(
                    "PAA fan-out complete",
                    extra={
                        "keyword": keyword[:50],
                        "nested_count": nested_count,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.info(
                "PAA enrichment complete",
                extra={
                    "keyword": keyword[:50],
                    "initial_count": initial_count,
                    "nested_count": nested_count,
                    "total_count": len(all_questions),
                    "duration_ms": round(duration_ms, 2),
                    "total_cost": total_cost,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow PAA enrichment operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return PAAEnrichmentResult(
                success=True,
                keyword=keyword,
                questions=all_questions,
                initial_count=initial_count,
                nested_count=nested_count,
                cost=total_cost if total_cost > 0 else None,
                duration_ms=duration_ms,
            )

        except PAAValidationError:
            raise
        except DataForSEOError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "PAA enrichment failed",
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
            return PAAEnrichmentResult(
                success=False,
                keyword=keyword,
                error=str(e),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "PAA enrichment unexpected error",
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
            return PAAEnrichmentResult(
                success=False,
                keyword=keyword,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
            )

    async def enrich_keywords_batch(
        self,
        keywords: list[str],
        location_code: int = 2840,
        language_code: str = "en",
        fanout_enabled: bool = True,
        max_fanout_questions: int = DEFAULT_MAX_FANOUT_QUESTIONS,
        max_concurrent: int = 5,
        project_id: str | None = None,
    ) -> list[PAAEnrichmentResult]:
        """Enrich multiple keywords with PAA questions.

        Args:
            keywords: List of keywords to enrich
            location_code: Location code
            language_code: Language code
            fanout_enabled: Whether to enable fan-out
            max_fanout_questions: Max questions to fan-out per keyword
            max_concurrent: Max concurrent keyword enrichments
            project_id: Project ID for logging

        Returns:
            List of PAAEnrichmentResult, one per keyword
        """
        start_time = time.monotonic()

        logger.info(
            "Batch PAA enrichment started",
            extra={
                "keyword_count": len(keywords),
                "fanout_enabled": fanout_enabled,
                "max_concurrent": max_concurrent,
                "project_id": project_id,
            },
        )

        if not keywords:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_one(keyword: str) -> PAAEnrichmentResult:
            async with semaphore:
                return await self.enrich_keyword(
                    keyword=keyword,
                    location_code=location_code,
                    language_code=language_code,
                    fanout_enabled=fanout_enabled,
                    max_fanout_questions=max_fanout_questions,
                    project_id=project_id,
                )

        tasks = [enrich_one(kw) for kw in keywords]
        results = await asyncio.gather(*tasks)

        duration_ms = (time.monotonic() - start_time) * 1000
        success_count = sum(1 for r in results if r.success)
        total_questions = sum(r.total_count for r in results)

        logger.info(
            "Batch PAA enrichment complete",
            extra={
                "keyword_count": len(keywords),
                "success_count": success_count,
                "total_questions": total_questions,
                "duration_ms": round(duration_ms, 2),
                "project_id": project_id,
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch PAA enrichment operation",
                extra={
                    "keyword_count": len(keywords),
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                },
            )

        return list(results)


# Global singleton instance
_paa_enrichment_service: PAAEnrichmentService | None = None


def get_paa_enrichment_service() -> PAAEnrichmentService:
    """Get the global PAA enrichment service instance.

    Usage:
        from app.services.paa_enrichment import get_paa_enrichment_service
        service = get_paa_enrichment_service()
        result = await service.enrich_keyword("hiking boots")
    """
    global _paa_enrichment_service
    if _paa_enrichment_service is None:
        _paa_enrichment_service = PAAEnrichmentService()
        logger.info("PAAEnrichmentService singleton created")
    return _paa_enrichment_service


async def enrich_keyword_paa(
    keyword: str,
    location_code: int = 2840,
    language_code: str = "en",
    fanout_enabled: bool = True,
    max_fanout_questions: int = DEFAULT_MAX_FANOUT_QUESTIONS,
    project_id: str | None = None,
    page_id: str | None = None,
) -> PAAEnrichmentResult:
    """Convenience function for PAA keyword enrichment.

    Args:
        keyword: Keyword to enrich
        location_code: Location code
        language_code: Language code
        fanout_enabled: Whether to enable fan-out
        max_fanout_questions: Max questions for fan-out
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        PAAEnrichmentResult with discovered questions
    """
    service = get_paa_enrichment_service()
    return await service.enrich_keyword(
        keyword=keyword,
        location_code=location_code,
        language_code=language_code,
        fanout_enabled=fanout_enabled,
        max_fanout_questions=max_fanout_questions,
        project_id=project_id,
        page_id=page_id,
    )


async def enrich_keyword_paa_cached(
    keyword: str,
    location_code: int = 2840,
    language_code: str = "en",
    fanout_enabled: bool = True,
    max_fanout_questions: int = DEFAULT_MAX_FANOUT_QUESTIONS,
    project_id: str | None = None,
    page_id: str | None = None,
) -> PAAEnrichmentResult:
    """PAA keyword enrichment with Redis caching (24h TTL).

    This function checks the Redis cache first before making API calls.
    If cached data is found, it returns immediately without API costs.
    On cache miss, it fetches from the API and caches the result.

    Args:
        keyword: Keyword to enrich
        location_code: Location code
        language_code: Language code
        fanout_enabled: Whether to enable fan-out
        max_fanout_questions: Max questions for fan-out
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        PAAEnrichmentResult with discovered questions
    """
    # Import here to avoid circular imports
    from app.services.paa_cache import get_paa_cache_service

    start_time = time.monotonic()
    cache = get_paa_cache_service()

    # Try cache first
    cache_result = await cache.get(
        keyword, location_code, language_code, project_id, page_id
    )

    if cache_result.cache_hit and cache_result.data:
        logger.debug(
            "PAA cache hit - returning cached result",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "cache_duration_ms": round(cache_result.duration_ms, 2),
                "project_id": project_id,
                "page_id": page_id,
            },
        )
        # Convert cached data back to PAAEnrichmentResult
        questions = [
            PAAQuestion(
                question=q.get("question", ""),
                answer_snippet=q.get("answer_snippet"),
                source_url=q.get("source_url"),
                source_domain=q.get("source_domain"),
                position=q.get("position"),
                is_nested=q.get("is_nested", False),
                parent_question=q.get("parent_question"),
                intent=PAAQuestionIntent(q.get("intent", "unknown")),
            )
            for q in cache_result.data.questions
        ]
        return PAAEnrichmentResult(
            success=True,
            keyword=cache_result.data.keyword,
            questions=questions,
            initial_count=cache_result.data.initial_count,
            nested_count=cache_result.data.nested_count,
            duration_ms=cache_result.duration_ms,
        )

    logger.debug(
        "PAA cache miss - fetching from API",
        extra={
            "keyword": keyword[:50],
            "location_code": location_code,
            "project_id": project_id,
            "page_id": page_id,
        },
    )

    # Cache miss - fetch from API
    result = await enrich_keyword_paa(
        keyword=keyword,
        location_code=location_code,
        language_code=language_code,
        fanout_enabled=fanout_enabled,
        max_fanout_questions=max_fanout_questions,
        project_id=project_id,
        page_id=page_id,
    )

    # Cache successful results
    if result.success and result.questions:
        questions_dicts = [q.to_dict() for q in result.questions]
        cached = await cache.set(
            keyword=keyword,
            questions=questions_dicts,
            initial_count=result.initial_count,
            nested_count=result.nested_count,
            location_code=location_code,
            language_code=language_code,
            project_id=project_id,
            page_id=page_id,
        )
        if cached:
            logger.debug(
                "PAA result cached successfully",
                extra={
                    "keyword": keyword[:50],
                    "questions_count": len(result.questions),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
        else:
            logger.debug(
                "PAA result caching failed (Redis may be unavailable)",
                extra={
                    "keyword": keyword[:50],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

    total_duration_ms = (time.monotonic() - start_time) * 1000
    logger.info(
        "PAA lookup complete",
        extra={
            "keyword": keyword[:50],
            "cache_hit": False,
            "questions_count": len(result.questions) if result.success else 0,
            "duration_ms": round(total_duration_ms, 2),
            "api_cost": result.cost,
            "project_id": project_id,
            "page_id": page_id,
        },
    )

    return result
