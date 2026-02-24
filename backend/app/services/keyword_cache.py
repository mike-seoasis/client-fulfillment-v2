"""Keyword volume caching service using Redis.

Caches keyword data from Keywords Everywhere API with 30-day TTL.
Handles Redis connection failures gracefully (cache is optional).

RAILWAY DEPLOYMENT REQUIREMENTS:
- Connect via REDIS_URL environment variable (Railway provides this)
- Handle Redis connection failures gracefully (cache is optional)
- Use SSL/TLS for Redis connections in production
- Implement connection retry logic for cold starts

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (keyword) in all service logs
- Log validation failures with field names and rejected values
- Log cache hit/miss statistics at INFO level
- Add timing logs for operations >1 second
"""

import json
import time
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import redis_manager
from app.integrations.keywords_everywhere import KeywordData

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
CACHE_KEY_PREFIX = "kw_vol:"


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
class CachedKeywordData:
    """Cached keyword data with metadata."""

    keyword: str
    volume: int | None = None
    cpc: float | None = None
    competition: float | None = None
    trend: list[int] | None = None
    country: str = "us"
    data_source: str = "gkp"
    cached_at: float = field(default_factory=time.time)

    def to_keyword_data(self) -> KeywordData:
        """Convert to KeywordData for API response."""
        return KeywordData(
            keyword=self.keyword,
            volume=self.volume,
            cpc=self.cpc,
            competition=self.competition,
            trend=self.trend,
        )


@dataclass
class KeywordCacheResult:
    """Result of a cache operation."""

    success: bool
    data: list[CachedKeywordData] = field(default_factory=list)
    error: str | None = None
    cache_hit: bool = False
    duration_ms: float = 0.0


class KeywordCacheServiceError(Exception):
    """Base exception for keyword cache service errors."""

    pass


class KeywordCacheValidationError(KeywordCacheServiceError):
    """Raised when validation fails."""

    def __init__(self, field: str, value: str, message: str) -> None:
        super().__init__(f"Validation error for {field}: {message}")
        self.field = field
        self.value = value
        self.message = message


class KeywordCacheService:
    """Service for caching keyword volume data in Redis.

    Features:
    - 30-day TTL for cached keyword data
    - Graceful degradation when Redis is unavailable
    - Comprehensive logging per requirements
    - Support for country and data_source variations

    Cache key format: kw_vol:{country}:{data_source}:{keyword}
    """

    def __init__(self, ttl_days: int | None = None) -> None:
        """Initialize keyword cache service.

        Args:
            ttl_days: TTL for cached data in days. Defaults to settings.
        """
        settings = get_settings()
        self._ttl_seconds = (ttl_days or settings.keyword_cache_ttl_days) * 86400  # days to seconds
        self._stats = CacheStats()

        logger.debug(
            "KeywordCacheService initialized",
            extra={
                "ttl_days": ttl_days or settings.keyword_cache_ttl_days,
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

    def _build_cache_key(
        self, keyword: str, country: str = "us", data_source: str = "gkp"
    ) -> str:
        """Build cache key for a keyword.

        Format: kw_vol:{country}:{data_source}:{keyword_normalized}
        """
        # Normalize keyword: lowercase, strip whitespace
        normalized = keyword.lower().strip()
        return f"{CACHE_KEY_PREFIX}{country}:{data_source}:{normalized}"

    def _serialize_data(self, data: CachedKeywordData) -> str:
        """Serialize cached data to JSON."""
        return json.dumps({
            "keyword": data.keyword,
            "volume": data.volume,
            "cpc": data.cpc,
            "competition": data.competition,
            "trend": data.trend,
            "country": data.country,
            "data_source": data.data_source,
            "cached_at": data.cached_at,
        })

    def _deserialize_data(self, json_str: str) -> CachedKeywordData:
        """Deserialize JSON to cached data."""
        data = json.loads(json_str)
        return CachedKeywordData(
            keyword=data["keyword"],
            volume=data.get("volume"),
            cpc=data.get("cpc"),
            competition=data.get("competition"),
            trend=data.get("trend"),
            country=data.get("country", "us"),
            data_source=data.get("data_source", "gkp"),
            cached_at=data.get("cached_at", 0.0),
        )

    async def get(
        self,
        keyword: str,
        country: str = "us",
        data_source: str = "gkp",
    ) -> KeywordCacheResult:
        """Get cached keyword data.

        Args:
            keyword: The keyword to look up
            country: Country code (e.g., 'us', 'uk')
            data_source: Data source ('gkp' or 'cli')

        Returns:
            KeywordCacheResult with cached data if found
        """
        start_time = time.monotonic()

        logger.debug(
            "Cache get started",
            extra={
                "keyword": keyword[:50],
                "country": country,
                "data_source": data_source,
            },
        )

        if not self.available:
            logger.debug(
                "Cache get skipped - Redis unavailable",
                extra={"keyword": keyword[:50]},
            )
            return KeywordCacheResult(
                success=True,
                cache_hit=False,
                error="Redis unavailable",
            )

        cache_key = self._build_cache_key(keyword, country, data_source)

        try:
            cached_bytes = await redis_manager.get(cache_key)
            duration_ms = (time.monotonic() - start_time) * 1000

            if cached_bytes is None:
                self._stats.misses += 1
                logger.debug(
                    "Cache miss",
                    extra={
                        "keyword": keyword[:50],
                        "cache_key": cache_key[:100],
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return KeywordCacheResult(
                    success=True,
                    cache_hit=False,
                    duration_ms=duration_ms,
                )

            # Deserialize cached data
            cached_str = cached_bytes.decode("utf-8")
            cached_data = self._deserialize_data(cached_str)

            self._stats.hits += 1
            logger.debug(
                "Cache hit",
                extra={
                    "keyword": keyword[:50],
                    "cache_key": cache_key[:100],
                    "duration_ms": round(duration_ms, 2),
                    "cached_at": cached_data.cached_at,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow cache get operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return KeywordCacheResult(
                success=True,
                data=[cached_data],
                cache_hit=True,
                duration_ms=duration_ms,
            )

        except json.JSONDecodeError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "Cache deserialization error",
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
            return KeywordCacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache deserialization failed: {e}",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "Cache get error",
                extra={
                    "keyword": keyword[:50],
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return KeywordCacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache error: {e}",
                duration_ms=duration_ms,
            )

    async def set(
        self,
        keyword_data: KeywordData,
        country: str = "us",
        data_source: str = "gkp",
    ) -> bool:
        """Cache keyword data.

        Args:
            keyword_data: KeywordData to cache
            country: Country code
            data_source: Data source

        Returns:
            True if cached successfully, False otherwise
        """
        start_time = time.monotonic()

        logger.debug(
            "Cache set started",
            extra={
                "keyword": keyword_data.keyword[:50],
                "country": country,
                "data_source": data_source,
                "volume": keyword_data.volume,
            },
        )

        if not self.available:
            logger.debug(
                "Cache set skipped - Redis unavailable",
                extra={"keyword": keyword_data.keyword[:50]},
            )
            return False

        if not keyword_data.keyword:
            logger.warning(
                "Cache set validation failed - empty keyword",
                extra={"field": "keyword", "value": ""},
            )
            raise KeywordCacheValidationError("keyword", "", "Keyword cannot be empty")

        cache_key = self._build_cache_key(keyword_data.keyword, country, data_source)

        try:
            cached_data = CachedKeywordData(
                keyword=keyword_data.keyword,
                volume=keyword_data.volume,
                cpc=keyword_data.cpc,
                competition=keyword_data.competition,
                trend=keyword_data.trend,
                country=country,
                data_source=data_source,
                cached_at=time.time(),
            )

            serialized = self._serialize_data(cached_data)
            result = await redis_manager.set(cache_key, serialized, ex=self._ttl_seconds)

            duration_ms = (time.monotonic() - start_time) * 1000

            if result:
                logger.debug(
                    "Cache set success",
                    extra={
                        "keyword": keyword_data.keyword[:50],
                        "cache_key": cache_key[:100],
                        "ttl_seconds": self._ttl_seconds,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
            else:
                logger.warning(
                    "Cache set failed",
                    extra={
                        "keyword": keyword_data.keyword[:50],
                        "cache_key": cache_key[:100],
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow cache set operation",
                    extra={
                        "keyword": keyword_data.keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return bool(result)

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "Cache set error",
                extra={
                    "keyword": keyword_data.keyword[:50],
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return False

    async def get_many(
        self,
        keywords: list[str],
        country: str = "us",
        data_source: str = "gkp",
    ) -> tuple[list[CachedKeywordData], list[str]]:
        """Get multiple keywords from cache.

        Args:
            keywords: List of keywords to look up
            country: Country code
            data_source: Data source

        Returns:
            Tuple of (cached_data, missed_keywords)
        """
        start_time = time.monotonic()

        logger.debug(
            "Cache get_many started",
            extra={
                "keyword_count": len(keywords),
                "country": country,
                "data_source": data_source,
            },
        )

        if not self.available:
            logger.debug(
                "Cache get_many skipped - Redis unavailable",
                extra={"keyword_count": len(keywords)},
            )
            return [], keywords

        cached_data: list[CachedKeywordData] = []
        missed_keywords: list[str] = []

        for keyword in keywords:
            result = await self.get(keyword, country, data_source)
            if result.cache_hit and result.data:
                cached_data.append(result.data[0])
            else:
                missed_keywords.append(keyword)

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Cache get_many complete",
            extra={
                "keyword_count": len(keywords),
                "hits": len(cached_data),
                "misses": len(missed_keywords),
                "hit_rate": round(len(cached_data) / len(keywords), 3) if keywords else 0,
                "duration_ms": round(duration_ms, 2),
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow cache get_many operation",
                extra={
                    "keyword_count": len(keywords),
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                },
            )

        return cached_data, missed_keywords

    async def set_many(
        self,
        keyword_data_list: list[KeywordData],
        country: str = "us",
        data_source: str = "gkp",
    ) -> int:
        """Cache multiple keyword data entries.

        Args:
            keyword_data_list: List of KeywordData to cache
            country: Country code
            data_source: Data source

        Returns:
            Number of successfully cached entries
        """
        start_time = time.monotonic()

        logger.debug(
            "Cache set_many started",
            extra={
                "keyword_count": len(keyword_data_list),
                "country": country,
                "data_source": data_source,
            },
        )

        if not self.available:
            logger.debug(
                "Cache set_many skipped - Redis unavailable",
                extra={"keyword_count": len(keyword_data_list)},
            )
            return 0

        success_count = 0
        for keyword_data in keyword_data_list:
            if await self.set(keyword_data, country, data_source):
                success_count += 1

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Cache set_many complete",
            extra={
                "keyword_count": len(keyword_data_list),
                "success_count": success_count,
                "failure_count": len(keyword_data_list) - success_count,
                "duration_ms": round(duration_ms, 2),
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow cache set_many operation",
                extra={
                    "keyword_count": len(keyword_data_list),
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                },
            )

        return success_count

    async def delete(
        self,
        keyword: str,
        country: str = "us",
        data_source: str = "gkp",
    ) -> bool:
        """Delete cached keyword data.

        Args:
            keyword: Keyword to delete
            country: Country code
            data_source: Data source

        Returns:
            True if deleted, False otherwise
        """
        if not self.available:
            return False

        cache_key = self._build_cache_key(keyword, country, data_source)

        try:
            result = await redis_manager.delete(cache_key)
            logger.debug(
                "Cache delete",
                extra={
                    "keyword": keyword[:50],
                    "cache_key": cache_key[:100],
                    "deleted": bool(result),
                },
            )
            return bool(result)
        except Exception as e:
            logger.error(
                "Cache delete error",
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
        country: str = "us",
        data_source: str = "gkp",
    ) -> int | None:
        """Get remaining TTL for a cached keyword.

        Args:
            keyword: Keyword to check
            country: Country code
            data_source: Data source

        Returns:
            Remaining TTL in seconds, or None if not cached
        """
        if not self.available:
            return None

        cache_key = self._build_cache_key(keyword, country, data_source)

        try:
            ttl = await redis_manager.ttl(cache_key)
            # Redis returns -2 if key doesn't exist, -1 if no TTL
            if ttl is None or ttl < 0:
                return None
            return ttl
        except Exception as e:
            logger.error(
                "Cache TTL check error",
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
_keyword_cache_service: KeywordCacheService | None = None


def get_keyword_cache_service() -> KeywordCacheService:
    """Get the global keyword cache service instance.

    Usage:
        from app.services.keyword_cache import get_keyword_cache_service
        cache = get_keyword_cache_service()
        result = await cache.get("python tutorial")
    """
    global _keyword_cache_service
    if _keyword_cache_service is None:
        _keyword_cache_service = KeywordCacheService()
        logger.info("KeywordCacheService singleton created")
    return _keyword_cache_service


# Convenience functions
async def cache_keyword_data(
    keyword_data: KeywordData,
    country: str = "us",
    data_source: str = "gkp",
) -> bool:
    """Cache keyword data using the global service.

    Args:
        keyword_data: KeywordData to cache
        country: Country code
        data_source: Data source

    Returns:
        True if cached successfully
    """
    service = get_keyword_cache_service()
    return await service.set(keyword_data, country, data_source)


async def get_cached_keyword(
    keyword: str,
    country: str = "us",
    data_source: str = "gkp",
) -> KeywordCacheResult:
    """Get cached keyword data using the global service.

    Args:
        keyword: Keyword to look up
        country: Country code
        data_source: Data source

    Returns:
        KeywordCacheResult with cached data if found
    """
    service = get_keyword_cache_service()
    return await service.get(keyword, country, data_source)
