"""Related Searches fallback service with LLM semantic filtering.

When PAA enrichment returns insufficient results, this service provides
a fallback mechanism using Google's "related searches" from SERP data.

Features:
- Extracts related_searches from DataForSEO SERP API response
- Uses Claude LLM to semantically filter related searches for relevance
- Converts filtered searches to question format (PAA-style)
- Caches results with 24h TTL
- Comprehensive logging per requirements

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import hashlib
import json
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.core.redis import redis_manager
from app.integrations.claude import ClaudeClient, get_claude
from app.integrations.dataforseo import (
    DataForSEOClient,
    DataForSEOError,
    get_dataforseo,
)

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
CACHE_KEY_PREFIX = "related_searches:"
DEFAULT_TTL_HOURS = 24
MIN_RELEVANCE_SCORE = 0.6  # Minimum score for LLM-filtered related searches


@dataclass
class RelatedSearch:
    """A single related search term with metadata."""

    search_term: str
    question_form: str | None = None  # Converted to question format
    relevance_score: float = 0.0  # LLM-assigned relevance (0.0-1.0)
    position: int = 0
    is_filtered: bool = False  # True if passed LLM semantic filter

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "search_term": self.search_term,
            "question_form": self.question_form,
            "relevance_score": self.relevance_score,
            "position": self.position,
            "is_filtered": self.is_filtered,
        }


@dataclass
class RelatedSearchesResult:
    """Result of related searches extraction and filtering."""

    success: bool
    keyword: str
    raw_searches: list[RelatedSearch] = field(default_factory=list)
    filtered_searches: list[RelatedSearch] = field(default_factory=list)
    error: str | None = None
    api_cost: float | None = None
    llm_input_tokens: int | None = None
    llm_output_tokens: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None

    @property
    def raw_count(self) -> int:
        """Count of raw related searches found."""
        return len(self.raw_searches)

    @property
    def filtered_count(self) -> int:
        """Count of filtered (relevant) searches."""
        return len(self.filtered_searches)


@dataclass
class CachedRelatedSearchesData:
    """Cached related searches data with metadata."""

    keyword: str
    raw_searches: list[dict[str, Any]] = field(default_factory=list)
    filtered_searches: list[dict[str, Any]] = field(default_factory=list)
    location_code: int = 2840  # Default: US
    language_code: str = "en"
    cached_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "keyword": self.keyword,
            "raw_searches": self.raw_searches,
            "filtered_searches": self.filtered_searches,
            "location_code": self.location_code,
            "language_code": self.language_code,
            "cached_at": self.cached_at,
        }


@dataclass
class RelatedSearchesCacheResult:
    """Result of a cache operation."""

    success: bool
    data: CachedRelatedSearchesData | None = None
    error: str | None = None
    cache_hit: bool = False
    duration_ms: float = 0.0


class RelatedSearchesServiceError(Exception):
    """Base exception for Related Searches service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class RelatedSearchesValidationError(RelatedSearchesServiceError):
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


# System prompt for semantic filtering
SEMANTIC_FILTER_SYSTEM_PROMPT = """You are a semantic relevance expert. Your task is to evaluate whether related search terms are semantically relevant to a product or topic keyword.

For each related search, assess:
1. Topic relevance: Is it about the same product/topic?
2. User intent alignment: Would someone searching for the original keyword also care about this?
3. Question potential: Can this be naturally converted to a useful question?

Respond ONLY with valid JSON in this exact format:
{
  "evaluations": [
    {
      "search_term": "<original search term>",
      "relevance_score": <0.0-1.0>,
      "question_form": "<converted to question format or null>",
      "reasoning": "<brief explanation>"
    }
  ]
}

Guidelines:
- Score 0.8-1.0: Highly relevant, directly about the product/topic
- Score 0.6-0.8: Moderately relevant, related aspect or use case
- Score 0.4-0.6: Tangentially relevant, might be useful
- Score 0.0-0.4: Not relevant, different topic or intent
- Convert to natural questions when possible (e.g., "best hiking boots" -> "What are the best hiking boots?")
- Return null for question_form if conversion doesn't make sense"""


class RelatedSearchesService:
    """Service for extracting and filtering related searches as PAA fallback.

    Features:
    - Extracts related_searches from DataForSEO SERP Advanced endpoint
    - Uses Claude LLM to semantically filter for relevance
    - Converts to question format for PAA-style content
    - Comprehensive logging per requirements

    Usage:
        service = RelatedSearchesService()
        result = await service.get_related_searches(
            keyword="hiking boots",
            min_relevance=0.6,
        )
    """

    def __init__(
        self,
        dataforseo_client: DataForSEOClient | None = None,
        claude_client: ClaudeClient | None = None,
        min_relevance_score: float = MIN_RELEVANCE_SCORE,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> None:
        """Initialize Related Searches service.

        Args:
            dataforseo_client: DataForSEO client instance. If None, uses global.
            claude_client: Claude client instance. If None, uses global.
            min_relevance_score: Minimum LLM relevance score to include (0.0-1.0).
            ttl_hours: Cache TTL in hours.
        """
        self._dataforseo_client = dataforseo_client
        self._claude_client = claude_client
        self._min_relevance_score = min_relevance_score
        self._ttl_seconds = ttl_hours * 3600

        logger.debug(
            "RelatedSearchesService initialized",
            extra={
                "min_relevance_score": self._min_relevance_score,
                "ttl_hours": ttl_hours,
            },
        )

    async def _get_dataforseo_client(self) -> DataForSEOClient:
        """Get DataForSEO client instance."""
        if self._dataforseo_client is None:
            self._dataforseo_client = await get_dataforseo()
        return self._dataforseo_client

    async def _get_claude_client(self) -> ClaudeClient:
        """Get Claude client instance."""
        if self._claude_client is None:
            self._claude_client = await get_claude()
        return self._claude_client

    def _hash_keyword(self, keyword: str) -> str:
        """Create a stable hash for the keyword."""
        normalized = keyword.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _build_cache_key(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
    ) -> str:
        """Build cache key for related searches results."""
        keyword_hash = self._hash_keyword(keyword)
        return f"{CACHE_KEY_PREFIX}{location_code}:{language_code}:{keyword_hash}"

    def _parse_related_searches(
        self,
        items: list[dict[str, Any]],
    ) -> list[RelatedSearch]:
        """Parse related searches from SERP API response.

        Args:
            items: List of SERP items from API response

        Returns:
            List of RelatedSearch objects
        """
        searches: list[RelatedSearch] = []

        for item in items:
            # Check for related_searches type
            if item.get("type") != "related_searches":
                continue

            # related_searches items contain nested items
            search_items = item.get("items", [])
            for idx, search_item in enumerate(search_items):
                search_term = search_item.get("title", "").strip()
                if not search_term:
                    continue

                searches.append(
                    RelatedSearch(
                        search_term=search_term,
                        position=idx + 1,
                    )
                )

        return searches

    async def _fetch_serp_related_searches(
        self,
        keyword: str,
        location_code: int,
        language_code: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> tuple[list[RelatedSearch], float | None]:
        """Fetch related searches from SERP API.

        Args:
            keyword: Keyword to search
            location_code: Location code (e.g., 2840 for US)
            language_code: Language code (e.g., 'en')
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Tuple of (list of RelatedSearch, API cost)
        """
        start_time = time.monotonic()
        client = await self._get_dataforseo_client()

        logger.debug(
            "Fetching related searches from SERP",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "language_code": language_code,
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
                "depth": 10,  # We only need related_searches
            }
        ]

        endpoint = "/v3/serp/google/organic/live/advanced"

        try:
            response_data, request_id = await client._make_request(endpoint, payload)
            cost = response_data.get("cost")

            # Parse related searches from response
            searches: list[RelatedSearch] = []
            tasks = response_data.get("tasks", [])
            for task in tasks:
                task_results = task.get("result", [])
                for task_result in task_results:
                    items = task_result.get("items", [])
                    searches.extend(self._parse_related_searches(items))

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "Related searches fetch complete",
                extra={
                    "keyword": keyword[:50],
                    "searches_found": len(searches),
                    "duration_ms": round(duration_ms, 2),
                    "cost": cost,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow related searches fetch operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return searches, cost

        except DataForSEOError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Related searches fetch failed",
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
            raise

    async def _apply_semantic_filter(
        self,
        keyword: str,
        searches: list[RelatedSearch],
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> tuple[list[RelatedSearch], int | None, int | None]:
        """Apply LLM semantic filter to related searches.

        Args:
            keyword: Original keyword for context
            searches: List of raw related searches
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Tuple of (filtered searches, input_tokens, output_tokens)
        """
        if not searches:
            return [], None, None

        start_time = time.monotonic()
        claude = await self._get_claude_client()

        logger.debug(
            "Applying semantic filter to related searches",
            extra={
                "keyword": keyword[:50],
                "searches_count": len(searches),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Build user prompt with search terms
        search_terms = [s.search_term for s in searches]
        search_list = "\n".join(f"- {term}" for term in search_terms)

        user_prompt = f"""Evaluate the relevance of these related search terms to the keyword "{keyword}".

Related search terms:
{search_list}

For each term, provide:
1. relevance_score (0.0-1.0)
2. question_form (natural question format, or null if not applicable)
3. brief reasoning

Respond with JSON only."""

        result = await claude.complete(
            user_prompt=user_prompt,
            system_prompt=SEMANTIC_FILTER_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic
            max_tokens=2048,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        if not result.success:
            logger.warning(
                "LLM semantic filter failed, returning unfiltered results",
                extra={
                    "keyword": keyword[:50],
                    "error": result.error,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            # Return original searches without filtering
            return searches, result.input_tokens, result.output_tokens

        # Parse LLM response
        try:
            response_text = result.text or ""
            json_text = response_text.strip()

            # Handle markdown code blocks
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                lines = lines[1:]  # Remove first line
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                json_text = "\n".join(lines)

            parsed = json.loads(json_text)
            evaluations = parsed.get("evaluations", [])

            # Build lookup by search term
            eval_lookup: dict[str, dict[str, Any]] = {}
            for evaluation in evaluations:
                term = evaluation.get("search_term", "")
                eval_lookup[term.lower().strip()] = evaluation

            # Apply evaluations to searches
            filtered_searches: list[RelatedSearch] = []
            for search in searches:
                eval_data = eval_lookup.get(search.search_term.lower().strip(), {})
                relevance = float(eval_data.get("relevance_score", 0.0))
                question_form = eval_data.get("question_form")

                search.relevance_score = relevance
                search.question_form = question_form
                search.is_filtered = relevance >= self._min_relevance_score

                if search.is_filtered:
                    filtered_searches.append(search)

            logger.info(
                "Semantic filter applied",
                extra={
                    "keyword": keyword[:50],
                    "raw_count": len(searches),
                    "filtered_count": len(filtered_searches),
                    "min_relevance": self._min_relevance_score,
                    "duration_ms": round(duration_ms, 2),
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow semantic filter operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return filtered_searches, result.input_tokens, result.output_tokens

        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse LLM semantic filter response",
                extra={
                    "keyword": keyword[:50],
                    "error": str(e),
                    "response": (result.text or "")[:500],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            # Return original searches without filtering
            return searches, result.input_tokens, result.output_tokens

    async def _get_from_cache(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> RelatedSearchesCacheResult:
        """Get cached related searches data.

        Args:
            keyword: Keyword to look up
            location_code: Location code
            language_code: Language code
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            RelatedSearchesCacheResult with cached data if found
        """
        start_time = time.monotonic()

        if not redis_manager.available:
            return RelatedSearchesCacheResult(
                success=True,
                cache_hit=False,
                error="Redis unavailable",
            )

        cache_key = self._build_cache_key(keyword, location_code, language_code)

        try:
            cached_bytes = await redis_manager.get(cache_key)
            duration_ms = (time.monotonic() - start_time) * 1000

            if cached_bytes is None:
                logger.debug(
                    "Related searches cache miss",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return RelatedSearchesCacheResult(
                    success=True,
                    cache_hit=False,
                    duration_ms=duration_ms,
                )

            # Deserialize
            cached_str = cached_bytes.decode("utf-8")
            data = json.loads(cached_str)
            cached_data = CachedRelatedSearchesData(
                keyword=data["keyword"],
                raw_searches=data.get("raw_searches", []),
                filtered_searches=data.get("filtered_searches", []),
                location_code=data.get("location_code", 2840),
                language_code=data.get("language_code", "en"),
                cached_at=data.get("cached_at", 0.0),
            )

            logger.debug(
                "Related searches cache hit",
                extra={
                    "keyword": keyword[:50],
                    "duration_ms": round(duration_ms, 2),
                    "filtered_count": len(cached_data.filtered_searches),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            return RelatedSearchesCacheResult(
                success=True,
                data=cached_data,
                cache_hit=True,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Related searches cache get error",
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
            return RelatedSearchesCacheResult(
                success=False,
                cache_hit=False,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def _save_to_cache(
        self,
        keyword: str,
        raw_searches: list[RelatedSearch],
        filtered_searches: list[RelatedSearch],
        location_code: int = 2840,
        language_code: str = "en",
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> bool:
        """Save related searches to cache.

        Args:
            keyword: The keyword
            raw_searches: All raw related searches
            filtered_searches: Filtered relevant searches
            location_code: Location code
            language_code: Language code
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            True if cached successfully
        """
        if not redis_manager.available:
            return False

        cache_key = self._build_cache_key(keyword, location_code, language_code)

        try:
            cached_data = CachedRelatedSearchesData(
                keyword=keyword,
                raw_searches=[s.to_dict() for s in raw_searches],
                filtered_searches=[s.to_dict() for s in filtered_searches],
                location_code=location_code,
                language_code=language_code,
                cached_at=time.time(),
            )

            serialized = json.dumps(cached_data.to_dict())
            result = await redis_manager.set(
                cache_key, serialized, ex=self._ttl_seconds
            )

            logger.debug(
                "Related searches cached",
                extra={
                    "keyword": keyword[:50],
                    "raw_count": len(raw_searches),
                    "filtered_count": len(filtered_searches),
                    "ttl_seconds": self._ttl_seconds,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            return bool(result)

        except Exception as e:
            logger.error(
                "Related searches cache set error",
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
            return False

    async def get_related_searches(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        skip_llm_filter: bool = False,
        use_cache: bool = True,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> RelatedSearchesResult:
        """Get related searches with semantic filtering.

        Args:
            keyword: Primary keyword to search
            location_code: Location code (e.g., 2840 for US)
            language_code: Language code (e.g., 'en')
            skip_llm_filter: Skip LLM semantic filtering (return raw results)
            use_cache: Use Redis cache
            project_id: Project ID for logging context
            page_id: Page ID for logging context

        Returns:
            RelatedSearchesResult with filtered related searches
        """
        start_time = time.monotonic()

        logger.debug(
            "Related searches lookup started",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "language_code": language_code,
                "skip_llm_filter": skip_llm_filter,
                "use_cache": use_cache,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate input
        if not keyword or not keyword.strip():
            logger.warning(
                "Related searches validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise RelatedSearchesValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        keyword = keyword.strip()

        # Check cache first
        if use_cache:
            cache_result = await self._get_from_cache(
                keyword, location_code, language_code, project_id, page_id
            )

            if cache_result.cache_hit and cache_result.data:
                duration_ms = (time.monotonic() - start_time) * 1000

                # Convert cached dicts back to RelatedSearch objects
                raw_searches = [
                    RelatedSearch(**s) for s in cache_result.data.raw_searches
                ]
                filtered_searches = [
                    RelatedSearch(**s) for s in cache_result.data.filtered_searches
                ]

                logger.info(
                    "Related searches cache hit",
                    extra={
                        "keyword": keyword[:50],
                        "raw_count": len(raw_searches),
                        "filtered_count": len(filtered_searches),
                        "duration_ms": round(duration_ms, 2),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

                return RelatedSearchesResult(
                    success=True,
                    keyword=keyword,
                    raw_searches=raw_searches,
                    filtered_searches=filtered_searches,
                    duration_ms=duration_ms,
                )

        try:
            # Fetch from SERP API
            raw_searches, api_cost = await self._fetch_serp_related_searches(
                keyword=keyword,
                location_code=location_code,
                language_code=language_code,
                project_id=project_id,
                page_id=page_id,
            )

            logger.info(
                "Related searches fetched from API",
                extra={
                    "keyword": keyword[:50],
                    "raw_count": len(raw_searches),
                    "api_cost": api_cost,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Apply semantic filter (unless skipped)
            api_filtered_searches: list[RelatedSearch] = []
            input_tokens: int | None = None
            output_tokens: int | None = None

            if raw_searches and not skip_llm_filter:
                (
                    api_filtered_searches,
                    input_tokens,
                    output_tokens,
                ) = await self._apply_semantic_filter(
                    keyword=keyword,
                    searches=raw_searches,
                    project_id=project_id,
                    page_id=page_id,
                )
            elif raw_searches and skip_llm_filter:
                # Return all searches without filtering
                api_filtered_searches = raw_searches

            duration_ms = (time.monotonic() - start_time) * 1000

            # Cache results
            if use_cache and (raw_searches or api_filtered_searches):
                await self._save_to_cache(
                    keyword=keyword,
                    raw_searches=raw_searches,
                    filtered_searches=api_filtered_searches,
                    location_code=location_code,
                    language_code=language_code,
                    project_id=project_id,
                    page_id=page_id,
                )

            logger.info(
                "Related searches lookup complete",
                extra={
                    "keyword": keyword[:50],
                    "raw_count": len(raw_searches),
                    "filtered_count": len(api_filtered_searches),
                    "api_cost": api_cost,
                    "llm_tokens": (input_tokens or 0) + (output_tokens or 0),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow related searches operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return RelatedSearchesResult(
                success=True,
                keyword=keyword,
                raw_searches=raw_searches,
                filtered_searches=api_filtered_searches,
                api_cost=api_cost,
                llm_input_tokens=input_tokens,
                llm_output_tokens=output_tokens,
                duration_ms=duration_ms,
            )

        except RelatedSearchesValidationError:
            raise
        except DataForSEOError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Related searches lookup failed",
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
            return RelatedSearchesResult(
                success=False,
                keyword=keyword,
                error=str(e),
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Related searches unexpected error",
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
            return RelatedSearchesResult(
                success=False,
                keyword=keyword,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
            )


# Global singleton instance
_related_searches_service: RelatedSearchesService | None = None


def get_related_searches_service() -> RelatedSearchesService:
    """Get the global Related Searches service instance.

    Usage:
        from app.services.related_searches import get_related_searches_service
        service = get_related_searches_service()
        result = await service.get_related_searches("hiking boots")
    """
    global _related_searches_service
    if _related_searches_service is None:
        _related_searches_service = RelatedSearchesService()
        logger.info("RelatedSearchesService singleton created")
    return _related_searches_service


async def get_related_searches(
    keyword: str,
    location_code: int = 2840,
    language_code: str = "en",
    skip_llm_filter: bool = False,
    use_cache: bool = True,
    project_id: str | None = None,
    page_id: str | None = None,
) -> RelatedSearchesResult:
    """Convenience function for getting related searches.

    Args:
        keyword: Keyword to search
        location_code: Location code
        language_code: Language code
        skip_llm_filter: Skip LLM filtering
        use_cache: Use Redis cache
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        RelatedSearchesResult with filtered related searches
    """
    service = get_related_searches_service()
    return await service.get_related_searches(
        keyword=keyword,
        location_code=location_code,
        language_code=language_code,
        skip_llm_filter=skip_llm_filter,
        use_cache=use_cache,
        project_id=project_id,
        page_id=page_id,
    )
