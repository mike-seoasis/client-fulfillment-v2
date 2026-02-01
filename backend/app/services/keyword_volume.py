"""KeywordVolumeService for batch keyword volume lookup with caching.

Implements Step 2 of the keyword research workflow: batch volume lookup
using Keywords Everywhere API with Redis caching.

Features:
- Batch keyword volume lookups via Keywords Everywhere API
- Redis caching with 30-day TTL (cache-first approach)
- Graceful degradation when cache or API unavailable
- Comprehensive cache statistics (hits, misses, errors)
- Parallel batch processing with concurrency control

RAILWAY DEPLOYMENT REQUIREMENTS:
- Connect via REDIS_URL environment variable (Railway provides this)
- Handle Redis connection failures gracefully (cache is optional)
- Use SSL/TLS for Redis connections in production
- Implement connection retry logic for cold starts

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.integrations.keywords_everywhere import (
    KeywordData,
    KeywordsEverywhereClient,
    get_keywords_everywhere,
)
from app.services.keyword_cache import (
    CachedKeywordData,
    CacheStats,
    KeywordCacheService,
    get_keyword_cache_service,
)

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000

# Default concurrency for batch API calls
DEFAULT_MAX_CONCURRENT = 5


class KeywordVolumeServiceError(Exception):
    """Base exception for KeywordVolumeService errors."""

    pass


class KeywordVolumeValidationError(KeywordVolumeServiceError):
    """Raised when input validation fails."""

    def __init__(self, field: str, value: str, message: str) -> None:
        super().__init__(f"Validation error for {field}: {message}")
        self.field = field
        self.value = value
        self.message = message


class KeywordVolumeLookupError(KeywordVolumeServiceError):
    """Raised when volume lookup fails."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


@dataclass
class KeywordVolumeData:
    """Volume data for a single keyword.

    Attributes:
        keyword: The keyword string
        volume: Monthly search volume (None if unknown)
        cpc: Cost per click (None if unknown)
        competition: Competition score 0-1 (None if unknown)
        trend: Monthly trend data (None if unknown)
        from_cache: Whether this data came from cache
    """

    keyword: str
    volume: int | None = None
    cpc: float | None = None
    competition: float | None = None
    trend: list[int] | None = None
    from_cache: bool = False

    @classmethod
    def from_keyword_data(cls, data: KeywordData, from_cache: bool = False) -> "KeywordVolumeData":
        """Create from KeywordData."""
        return cls(
            keyword=data.keyword,
            volume=data.volume,
            cpc=data.cpc,
            competition=data.competition,
            trend=data.trend,
            from_cache=from_cache,
        )

    @classmethod
    def from_cached_data(cls, data: CachedKeywordData) -> "KeywordVolumeData":
        """Create from CachedKeywordData."""
        return cls(
            keyword=data.keyword,
            volume=data.volume,
            cpc=data.cpc,
            competition=data.competition,
            trend=data.trend,
            from_cache=True,
        )


@dataclass
class VolumeStats:
    """Statistics for a volume lookup operation."""

    total_keywords: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    api_lookups: int = 0
    api_errors: int = 0
    cached_after_lookup: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_keywords == 0:
            return 0.0
        return self.cache_hits / self.total_keywords


@dataclass
class KeywordVolumeResult:
    """Result of a keyword volume lookup operation.

    Attributes:
        success: Whether the operation succeeded
        keywords: List of keyword volume data
        stats: Statistics for the lookup
        error: Error message if failed
        duration_ms: Total time taken
        credits_used: API credits used (if any)
        project_id: Project ID for logging context
        page_id: Page ID for logging context
    """

    success: bool
    keywords: list[KeywordVolumeData] = field(default_factory=list)
    stats: VolumeStats = field(default_factory=VolumeStats)
    error: str | None = None
    duration_ms: float = 0.0
    credits_used: int | None = None
    project_id: str | None = None
    page_id: str | None = None


class KeywordVolumeService:
    """Service for batch keyword volume lookup with caching.

    Implements a cache-first approach:
    1. Check Redis cache for keyword volumes
    2. For cache misses, batch lookup via Keywords Everywhere API
    3. Cache API results for future lookups
    4. Return combined results with statistics

    Example usage:
        service = KeywordVolumeService()

        result = await service.lookup_volumes(
            keywords=["coffee storage", "airtight containers"],
            country="us",
            data_source="gkp",
            project_id="abc-123",
            page_id="page-456",
        )

        for kw in result.keywords:
            print(f"{kw.keyword}: {kw.volume} (cache: {kw.from_cache})")
    """

    def __init__(
        self,
        cache_service: KeywordCacheService | None = None,
        api_client: KeywordsEverywhereClient | None = None,
    ) -> None:
        """Initialize the keyword volume service.

        Args:
            cache_service: Redis cache service (uses global if None)
            api_client: Keywords Everywhere API client (uses global if None)
        """
        logger.debug(
            "KeywordVolumeService.__init__ called",
            extra={
                "has_custom_cache": cache_service is not None,
                "has_custom_api": api_client is not None,
            },
        )

        self._cache_service = cache_service
        self._api_client = api_client

        logger.debug("KeywordVolumeService initialized")

    def _get_cache_service(self) -> KeywordCacheService:
        """Get the cache service instance."""
        if self._cache_service is not None:
            return self._cache_service
        return get_keyword_cache_service()

    async def _get_api_client(self) -> KeywordsEverywhereClient | None:
        """Get the Keywords Everywhere API client."""
        if self._api_client is not None:
            return self._api_client
        try:
            return await get_keywords_everywhere()
        except Exception as e:
            logger.warning(
                "Failed to get Keywords Everywhere client",
                extra={"error": str(e)},
            )
            return None

    def _normalize_keyword(self, keyword: str) -> str:
        """Normalize a keyword for consistent lookup.

        Args:
            keyword: Raw keyword string

        Returns:
            Normalized keyword (lowercase, stripped, single spaces)
        """
        return " ".join(keyword.lower().strip().split())

    async def lookup_volumes(
        self,
        keywords: list[str],
        country: str = "us",
        data_source: str = "gkp",
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> KeywordVolumeResult:
        """Look up search volumes for a list of keywords.

        Uses cache-first approach:
        1. Check Redis cache for all keywords
        2. Batch lookup cache misses via Keywords Everywhere API
        3. Cache API results
        4. Return combined results

        Args:
            keywords: List of keywords to look up
            country: Country code (e.g., 'us', 'uk')
            data_source: Data source ('gkp' or 'cli')
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            KeywordVolumeResult with volume data and statistics
        """
        start_time = time.monotonic()

        logger.debug(
            "lookup_volumes() called",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "keyword_count": len(keywords),
                "country": country,
                "data_source": data_source,
            },
        )

        # Validate inputs
        if not keywords:
            logger.warning(
                "Validation failed: empty keywords list",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "field": "keywords",
                    "rejected_value": "[]",
                },
            )
            return KeywordVolumeResult(
                success=False,
                error="No keywords provided",
                project_id=project_id,
                page_id=page_id,
            )

        # Normalize and deduplicate keywords
        normalized_keywords: list[str] = []
        keyword_map: dict[str, str] = {}  # normalized -> original
        seen: set[str] = set()

        for kw in keywords:
            if not kw or not isinstance(kw, str):
                continue
            normalized = self._normalize_keyword(kw)
            if normalized and normalized not in seen:
                normalized_keywords.append(normalized)
                keyword_map[normalized] = kw
                seen.add(normalized)

        if not normalized_keywords:
            logger.warning(
                "Validation failed: no valid keywords after normalization",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "field": "keywords",
                    "rejected_value": f"{len(keywords)} invalid keywords",
                },
            )
            return KeywordVolumeResult(
                success=False,
                error="No valid keywords after normalization",
                project_id=project_id,
                page_id=page_id,
            )

        # Initialize stats
        stats = VolumeStats(total_keywords=len(normalized_keywords))
        results: list[KeywordVolumeData] = []
        keywords_to_lookup: list[str] = []

        # Step 1: Check cache
        cache_service = self._get_cache_service()

        logger.debug(
            "Checking cache for keywords",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "keyword_count": len(normalized_keywords),
                "cache_available": cache_service.available,
            },
        )

        cached_data, missed_keywords = await cache_service.get_many(
            normalized_keywords,
            country=country,
            data_source=data_source,
        )

        # Process cache hits
        for cached in cached_data:
            results.append(KeywordVolumeData.from_cached_data(cached))
            stats.cache_hits += 1

        stats.cache_misses = len(missed_keywords)
        keywords_to_lookup = missed_keywords

        logger.debug(
            "Cache lookup complete",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "cache_hits": stats.cache_hits,
                "cache_misses": stats.cache_misses,
                "hit_rate": round(stats.cache_hit_rate, 3),
            },
        )

        # Step 2: API lookup for cache misses
        api_results: list[KeywordData] = []
        credits_used: int | None = None

        if keywords_to_lookup:
            api_client = await self._get_api_client()

            if api_client and api_client.available:
                logger.debug(
                    "Looking up volumes via API",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword_count": len(keywords_to_lookup),
                    },
                )

                # Use batch method for automatic chunking (max 100 per request)
                api_result = await api_client.get_keyword_data_batch(
                    keywords=keywords_to_lookup,
                    country=country,
                    data_source=data_source,
                )

                stats.api_lookups = len(keywords_to_lookup)

                if api_result.success:
                    api_results = api_result.keywords
                    credits_used = api_result.credits_used

                    logger.debug(
                        "API lookup successful",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "results_count": len(api_results),
                            "credits_used": credits_used,
                            "duration_ms": round(api_result.duration_ms, 2),
                        },
                    )

                    # Add API results to output
                    for kw_data in api_results:
                        results.append(
                            KeywordVolumeData.from_keyword_data(kw_data, from_cache=False)
                        )
                else:
                    stats.api_errors = len(keywords_to_lookup)
                    logger.warning(
                        "API lookup failed",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "error": api_result.error,
                            "keyword_count": len(keywords_to_lookup),
                        },
                    )

                    # Add keywords with no volume data for failed lookups
                    for kw in keywords_to_lookup:
                        results.append(
                            KeywordVolumeData(keyword=kw, from_cache=False)
                        )
            else:
                # API not available - add keywords with no volume data
                logger.warning(
                    "Keywords Everywhere API not available",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "reason": "client_unavailable" if api_client else "not_configured",
                        "missed_keywords": len(keywords_to_lookup),
                    },
                )

                for kw in keywords_to_lookup:
                    results.append(KeywordVolumeData(keyword=kw, from_cache=False))
                stats.api_errors = len(keywords_to_lookup)

        # Step 3: Cache API results
        if api_results:
            cached_count = await cache_service.set_many(
                api_results,
                country=country,
                data_source=data_source,
            )
            stats.cached_after_lookup = cached_count

            logger.debug(
                "Cached API results",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "cached_count": cached_count,
                    "total_results": len(api_results),
                },
            )

        duration_ms = (time.monotonic() - start_time) * 1000

        # Log completion at INFO level (state transition)
        logger.info(
            "Volume lookup complete",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "total_keywords": stats.total_keywords,
                "cache_hits": stats.cache_hits,
                "cache_misses": stats.cache_misses,
                "cache_hit_rate": round(stats.cache_hit_rate, 3),
                "api_lookups": stats.api_lookups,
                "api_errors": stats.api_errors,
                "cached_after_lookup": stats.cached_after_lookup,
                "credits_used": credits_used,
                "duration_ms": round(duration_ms, 2),
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow volume lookup operation",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    "keyword_count": stats.total_keywords,
                },
            )

        return KeywordVolumeResult(
            success=True,
            keywords=results,
            stats=stats,
            duration_ms=round(duration_ms, 2),
            credits_used=credits_used,
            project_id=project_id,
            page_id=page_id,
        )

    async def lookup_single(
        self,
        keyword: str,
        country: str = "us",
        data_source: str = "gkp",
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> KeywordVolumeData | None:
        """Look up volume for a single keyword.

        Convenience method for single keyword lookups.

        Args:
            keyword: Keyword to look up
            country: Country code (e.g., 'us', 'uk')
            data_source: Data source ('gkp' or 'cli')
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            KeywordVolumeData if found, None otherwise
        """
        result = await self.lookup_volumes(
            keywords=[keyword],
            country=country,
            data_source=data_source,
            project_id=project_id,
            page_id=page_id,
        )

        if result.success and result.keywords:
            return result.keywords[0]
        return None

    def get_cache_stats(self) -> CacheStats:
        """Get cache statistics from the underlying cache service."""
        return self._get_cache_service().stats


# Global singleton instance
_keyword_volume_service: KeywordVolumeService | None = None


def get_keyword_volume_service() -> KeywordVolumeService:
    """Get the global keyword volume service instance (singleton).

    Usage:
        from app.services.keyword_volume import get_keyword_volume_service
        service = get_keyword_volume_service()
        result = await service.lookup_volumes(["keyword1", "keyword2"])
    """
    global _keyword_volume_service
    if _keyword_volume_service is None:
        _keyword_volume_service = KeywordVolumeService()
        logger.info("KeywordVolumeService singleton created")
    return _keyword_volume_service


# Convenience functions
async def lookup_keyword_volumes(
    keywords: list[str],
    country: str = "us",
    data_source: str = "gkp",
    project_id: str | None = None,
    page_id: str | None = None,
) -> KeywordVolumeResult:
    """Look up keyword volumes using the global service.

    Args:
        keywords: List of keywords to look up
        country: Country code (e.g., 'us', 'uk')
        data_source: Data source ('gkp' or 'cli')
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        KeywordVolumeResult with volume data and statistics

    Example:
        >>> result = await lookup_keyword_volumes(
        ...     keywords=["coffee storage", "airtight containers"],
        ...     country="us",
        ...     project_id="abc-123",
        ... )
        >>> for kw in result.keywords:
        ...     print(f"{kw.keyword}: {kw.volume}")
    """
    service = get_keyword_volume_service()
    return await service.lookup_volumes(
        keywords=keywords,
        country=country,
        data_source=data_source,
        project_id=project_id,
        page_id=page_id,
    )
