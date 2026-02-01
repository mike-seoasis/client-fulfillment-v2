"""SERP result caching service using Redis.

Caches SERP results from DataForSEO API with 24-hour TTL.
Handles Redis connection failures gracefully (cache is optional).

RAILWAY DEPLOYMENT REQUIREMENTS:
- Connect via REDIS_URL environment variable (Railway provides this)
- Handle Redis connection failures gracefully (cache is optional)
- Use SSL/TLS for Redis connections in production
- Implement connection retry logic for cold starts

ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Log API quota/credit usage if available
- Mask API keys and tokens in all logs
- Log circuit breaker state changes
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.core.redis import redis_manager
from app.integrations.dataforseo import SerpResult, SerpSearchResult

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
CACHE_KEY_PREFIX = "serp:"
DEFAULT_TTL_HOURS = 24


@dataclass
class CacheStats:
    """Statistics for cache operations."""

    hits: int = 0
    misses: int = 0
    errors: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


@dataclass
class CachedSerpData:
    """Cached SERP data with metadata."""

    keyword: str
    results: list[dict[str, Any]] = field(default_factory=list)
    total_results: int | None = None
    location_code: int = 2840  # Default: US
    language_code: str = "en"
    search_engine: str = "google"
    cached_at: float = field(default_factory=time.time)

    def to_serp_result(self) -> SerpSearchResult:
        """Convert to SerpSearchResult for API response."""
        serp_results = [
            SerpResult(
                position=r.get("position", 0),
                url=r.get("url", ""),
                title=r.get("title", ""),
                description=r.get("description"),
                domain=r.get("domain"),
            )
            for r in self.results
        ]
        return SerpSearchResult(
            success=True,
            keyword=self.keyword,
            results=serp_results,
            total_results=self.total_results,
        )


@dataclass
class SerpCacheResult:
    """Result of a cache operation."""

    success: bool
    data: CachedSerpData | None = None
    error: str | None = None
    cache_hit: bool = False
    duration_ms: float = 0.0


class SerpCacheServiceError(Exception):
    """Base exception for SERP cache service errors."""

    pass


class SerpCacheValidationError(SerpCacheServiceError):
    """Raised when validation fails."""

    def __init__(self, field_name: str, value: str, message: str) -> None:
        super().__init__(f"Validation error for {field_name}: {message}")
        self.field_name = field_name
        self.value = value
        self.message = message


class SerpCacheService:
    """Service for caching SERP results in Redis.

    Features:
    - 24-hour TTL for cached SERP data
    - Graceful degradation when Redis is unavailable
    - Comprehensive logging per requirements
    - Support for location, language, and search engine variations

    Cache key format: serp:{search_engine}:{location}:{language}:{keyword_hash}
    """

    def __init__(self, ttl_hours: int | None = None) -> None:
        """Initialize SERP cache service.

        Args:
            ttl_hours: TTL for cached data in hours. Defaults to 24 hours.
        """
        self._ttl_seconds = (ttl_hours or DEFAULT_TTL_HOURS) * 3600  # hours to seconds
        self._stats = CacheStats()

        logger.debug(
            "SerpCacheService initialized",
            extra={
                "ttl_hours": ttl_hours or DEFAULT_TTL_HOURS,
                "ttl_seconds": self._ttl_seconds,
            },
        )

    @property
    def available(self) -> bool:
        """Check if Redis cache is available."""
        return redis_manager.available

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    def _hash_keyword(self, keyword: str) -> str:
        """Create a stable hash for the keyword.

        Uses SHA256 truncated to 16 chars for reasonable uniqueness
        while keeping key size manageable.
        """
        normalized = keyword.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _build_cache_key(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        search_engine: str = "google",
    ) -> str:
        """Build cache key for SERP results.

        Format: serp:{search_engine}:{location}:{language}:{keyword_hash}
        """
        keyword_hash = self._hash_keyword(keyword)
        return f"{CACHE_KEY_PREFIX}{search_engine}:{location_code}:{language_code}:{keyword_hash}"

    def _serialize_data(self, data: CachedSerpData) -> str:
        """Serialize cached data to JSON."""
        return json.dumps(
            {
                "keyword": data.keyword,
                "results": data.results,
                "total_results": data.total_results,
                "location_code": data.location_code,
                "language_code": data.language_code,
                "search_engine": data.search_engine,
                "cached_at": data.cached_at,
            }
        )

    def _deserialize_data(self, json_str: str) -> CachedSerpData:
        """Deserialize JSON to cached data."""
        data = json.loads(json_str)
        return CachedSerpData(
            keyword=data["keyword"],
            results=data.get("results", []),
            total_results=data.get("total_results"),
            location_code=data.get("location_code", 2840),
            language_code=data.get("language_code", "en"),
            search_engine=data.get("search_engine", "google"),
            cached_at=data.get("cached_at", 0.0),
        )

    async def get(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        search_engine: str = "google",
    ) -> SerpCacheResult:
        """Get cached SERP data.

        Args:
            keyword: The keyword to look up
            location_code: Location code (e.g., 2840 for US)
            language_code: Language code (e.g., 'en')
            search_engine: Search engine ('google', 'bing')

        Returns:
            SerpCacheResult with cached data if found
        """
        start_time = time.monotonic()

        logger.debug(
            "SERP cache get started",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "language_code": language_code,
                "search_engine": search_engine,
            },
        )

        if not self.available:
            logger.debug(
                "SERP cache get skipped - Redis unavailable",
                extra={"keyword": keyword[:50]},
            )
            return SerpCacheResult(
                success=True,
                cache_hit=False,
                error="Redis unavailable",
            )

        cache_key = self._build_cache_key(
            keyword, location_code, language_code, search_engine
        )

        try:
            cached_bytes = await redis_manager.get(cache_key)
            duration_ms = (time.monotonic() - start_time) * 1000

            if cached_bytes is None:
                self._stats.misses += 1
                logger.debug(
                    "SERP cache miss",
                    extra={
                        "keyword": keyword[:50],
                        "cache_key": cache_key[:100],
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return SerpCacheResult(
                    success=True,
                    cache_hit=False,
                    duration_ms=duration_ms,
                )

            # Deserialize cached data
            cached_str = cached_bytes.decode("utf-8")
            cached_data = self._deserialize_data(cached_str)

            self._stats.hits += 1
            logger.debug(
                "SERP cache hit",
                extra={
                    "keyword": keyword[:50],
                    "cache_key": cache_key[:100],
                    "duration_ms": round(duration_ms, 2),
                    "cached_at": cached_data.cached_at,
                    "results_count": len(cached_data.results),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow SERP cache get operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return SerpCacheResult(
                success=True,
                data=cached_data,
                cache_hit=True,
                duration_ms=duration_ms,
            )

        except json.JSONDecodeError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "SERP cache deserialization error",
                extra={
                    "keyword": keyword[:50],
                    "cache_key": cache_key[:100],
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            # Delete corrupted cache entry
            await redis_manager.delete(cache_key)
            return SerpCacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache deserialization failed: {e}",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "SERP cache get error",
                extra={
                    "keyword": keyword[:50],
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return SerpCacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache error: {e}",
                duration_ms=duration_ms,
            )

    async def set(
        self,
        serp_data: SerpSearchResult,
        location_code: int = 2840,
        language_code: str = "en",
        search_engine: str = "google",
    ) -> bool:
        """Cache SERP data.

        Args:
            serp_data: SerpSearchResult to cache
            location_code: Location code
            language_code: Language code
            search_engine: Search engine

        Returns:
            True if cached successfully, False otherwise
        """
        start_time = time.monotonic()

        logger.debug(
            "SERP cache set started",
            extra={
                "keyword": serp_data.keyword[:50],
                "location_code": location_code,
                "language_code": language_code,
                "search_engine": search_engine,
                "results_count": len(serp_data.results),
            },
        )

        if not self.available:
            logger.debug(
                "SERP cache set skipped - Redis unavailable",
                extra={"keyword": serp_data.keyword[:50]},
            )
            return False

        if not serp_data.keyword:
            logger.warning(
                "SERP cache set validation failed - empty keyword",
                extra={"field": "keyword", "value": ""},
            )
            raise SerpCacheValidationError("keyword", "", "Keyword cannot be empty")

        cache_key = self._build_cache_key(
            serp_data.keyword, location_code, language_code, search_engine
        )

        try:
            # Convert SerpResult objects to dicts for serialization
            results_dicts = [
                {
                    "position": r.position,
                    "url": r.url,
                    "title": r.title,
                    "description": r.description,
                    "domain": r.domain,
                }
                for r in serp_data.results
            ]

            cached_data = CachedSerpData(
                keyword=serp_data.keyword,
                results=results_dicts,
                total_results=serp_data.total_results,
                location_code=location_code,
                language_code=language_code,
                search_engine=search_engine,
                cached_at=time.time(),
            )

            serialized = self._serialize_data(cached_data)
            result = await redis_manager.set(
                cache_key, serialized, ex=self._ttl_seconds
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if result:
                logger.debug(
                    "SERP cache set success",
                    extra={
                        "keyword": serp_data.keyword[:50],
                        "cache_key": cache_key[:100],
                        "ttl_seconds": self._ttl_seconds,
                        "duration_ms": round(duration_ms, 2),
                        "results_count": len(serp_data.results),
                    },
                )
            else:
                logger.warning(
                    "SERP cache set failed",
                    extra={
                        "keyword": serp_data.keyword[:50],
                        "cache_key": cache_key[:100],
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow SERP cache set operation",
                    extra={
                        "keyword": serp_data.keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return bool(result)

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "SERP cache set error",
                extra={
                    "keyword": serp_data.keyword[:50],
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return False

    async def delete(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        search_engine: str = "google",
    ) -> bool:
        """Delete cached SERP data.

        Args:
            keyword: Keyword to delete
            location_code: Location code
            language_code: Language code
            search_engine: Search engine

        Returns:
            True if deleted, False otherwise
        """
        if not self.available:
            return False

        cache_key = self._build_cache_key(
            keyword, location_code, language_code, search_engine
        )

        try:
            result = await redis_manager.delete(cache_key)
            logger.debug(
                "SERP cache delete",
                extra={
                    "keyword": keyword[:50],
                    "cache_key": cache_key[:100],
                    "deleted": bool(result),
                },
            )
            return bool(result)
        except Exception as e:
            logger.error(
                "SERP cache delete error",
                extra={
                    "keyword": keyword[:50],
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            return False

    async def get_ttl(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        search_engine: str = "google",
    ) -> int | None:
        """Get remaining TTL for a cached SERP result.

        Args:
            keyword: Keyword to check
            location_code: Location code
            language_code: Language code
            search_engine: Search engine

        Returns:
            Remaining TTL in seconds, or None if not cached
        """
        if not self.available:
            return None

        cache_key = self._build_cache_key(
            keyword, location_code, language_code, search_engine
        )

        try:
            ttl = await redis_manager.ttl(cache_key)
            # Redis returns -2 if key doesn't exist, -1 if no TTL
            if ttl is None or ttl < 0:
                return None
            return ttl
        except Exception as e:
            logger.error(
                "SERP cache TTL check error",
                extra={
                    "keyword": keyword[:50],
                    "error_type": type(e).__name__,
                    "error": str(e),
                },
                exc_info=True,
            )
            return None

    def get_stats_summary(self) -> dict[str, float | int]:
        """Get cache statistics summary."""
        return {
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "errors": self._stats.errors,
            "hit_rate": round(self._stats.hit_rate, 3),
            "total_requests": self._stats.hits + self._stats.misses,
        }


# Global singleton instance
_serp_cache_service: SerpCacheService | None = None


def get_serp_cache_service() -> SerpCacheService:
    """Get the global SERP cache service instance.

    Usage:
        from app.services.serp_cache import get_serp_cache_service
        cache = get_serp_cache_service()
        result = await cache.get("python tutorial")
    """
    global _serp_cache_service
    if _serp_cache_service is None:
        _serp_cache_service = SerpCacheService()
        logger.info("SerpCacheService singleton created")
    return _serp_cache_service


# Convenience functions for DataForSEO integration
async def cache_serp_result(
    serp_data: SerpSearchResult,
    location_code: int = 2840,
    language_code: str = "en",
    search_engine: str = "google",
) -> bool:
    """Cache SERP result using the global service.

    Args:
        serp_data: SerpSearchResult to cache
        location_code: Location code
        language_code: Language code
        search_engine: Search engine

    Returns:
        True if cached successfully
    """
    service = get_serp_cache_service()
    return await service.set(serp_data, location_code, language_code, search_engine)


async def get_cached_serp(
    keyword: str,
    location_code: int = 2840,
    language_code: str = "en",
    search_engine: str = "google",
) -> SerpCacheResult:
    """Get cached SERP result using the global service.

    Args:
        keyword: Keyword to look up
        location_code: Location code
        language_code: Language code
        search_engine: Search engine

    Returns:
        SerpCacheResult with cached data if found
    """
    service = get_serp_cache_service()
    return await service.get(keyword, location_code, language_code, search_engine)
