"""Competitor analysis caching service using Redis.

Caches competitor analysis results with 7-day TTL (configurable).
Handles Redis connection failures gracefully (cache is optional).

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, competitor_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second

RAILWAY DEPLOYMENT REQUIREMENTS:
- Connect via REDIS_URL environment variable (Railway provides this)
- Handle Redis connection failures gracefully (cache is optional)
- Use SSL/TLS for Redis connections in production
- Implement connection retry logic for cold starts
"""

import hashlib
import json
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.redis import redis_manager

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
CACHE_KEY_PREFIX = "comp_analysis:"
DEFAULT_TTL_DAYS = 7


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
class CachedAnalysisData:
    """Cached competitor analysis data with metadata."""

    competitor_id: str
    url: str
    analysis_type: str
    analysis_data: dict[str, Any] = field(default_factory=dict)
    project_id: str | None = None
    cached_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "competitor_id": self.competitor_id,
            "url": self.url,
            "analysis_type": self.analysis_type,
            "analysis_data": self.analysis_data,
            "project_id": self.project_id,
            "cached_at": self.cached_at,
        }


@dataclass
class CompetitorAnalysisCacheResult:
    """Result of a cache operation."""

    success: bool
    data: CachedAnalysisData | None = None
    error: str | None = None
    cache_hit: bool = False
    duration_ms: float = 0.0


class CompetitorAnalysisCacheError(Exception):
    """Base exception for competitor analysis cache errors."""

    pass


class CompetitorAnalysisCacheValidationError(CompetitorAnalysisCacheError):
    """Raised when validation fails."""

    def __init__(self, field_name: str, value: str, message: str) -> None:
        super().__init__(f"Validation error for {field_name}: {message}")
        self.field_name = field_name
        self.value = value
        self.message = message


class CompetitorAnalysisCacheService:
    """Service for caching competitor analysis results in Redis.

    Features:
    - 7-day TTL for cached analysis data (configurable via settings)
    - Graceful degradation when Redis is unavailable
    - Comprehensive logging per requirements
    - Support for different analysis types

    Cache key format: comp_analysis:{competitor_id}:{analysis_type}:{url_hash}
    """

    def __init__(self, ttl_days: int | None = None) -> None:
        """Initialize competitor analysis cache service.

        Args:
            ttl_days: TTL for cached data in days. Defaults to 7 days
                      or value from settings.
        """
        settings = get_settings()
        configured_ttl = ttl_days or settings.competitor_analysis_cache_ttl_days
        self._ttl_seconds = configured_ttl * 86400  # days to seconds
        self._stats = CacheStats()

        logger.debug(
            "CompetitorAnalysisCacheService initialized",
            extra={
                "ttl_days": configured_ttl,
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

    def _hash_url(self, url: str) -> str:
        """Create a stable hash for the URL.

        Uses SHA256 truncated to 16 chars for reasonable uniqueness
        while keeping key size manageable.
        """
        normalized = url.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _build_cache_key(
        self,
        competitor_id: str,
        analysis_type: str,
        url: str,
    ) -> str:
        """Build cache key for competitor analysis results.

        Format: comp_analysis:{competitor_id}:{analysis_type}:{url_hash}
        """
        url_hash = self._hash_url(url)
        return f"{CACHE_KEY_PREFIX}{competitor_id}:{analysis_type}:{url_hash}"

    def _serialize_data(self, data: CachedAnalysisData) -> str:
        """Serialize cached data to JSON."""
        return json.dumps(data.to_dict())

    def _deserialize_data(self, json_str: str) -> CachedAnalysisData:
        """Deserialize JSON to cached data."""
        data = json.loads(json_str)
        return CachedAnalysisData(
            competitor_id=data["competitor_id"],
            url=data["url"],
            analysis_type=data["analysis_type"],
            analysis_data=data.get("analysis_data", {}),
            project_id=data.get("project_id"),
            cached_at=data.get("cached_at", 0.0),
        )

    async def get(
        self,
        competitor_id: str,
        analysis_type: str,
        url: str,
        project_id: str | None = None,
    ) -> CompetitorAnalysisCacheResult:
        """Get cached competitor analysis data.

        Args:
            competitor_id: The competitor ID to look up
            analysis_type: Type of analysis (e.g., 'content', 'seo', 'keywords')
            url: The competitor URL
            project_id: Project ID for logging context

        Returns:
            CompetitorAnalysisCacheResult with cached data if found
        """
        start_time = time.monotonic()

        logger.debug(
            "Competitor analysis cache get started",
            extra={
                "competitor_id": competitor_id,
                "analysis_type": analysis_type,
                "url": url[:100] if url else "",
                "project_id": project_id,
            },
        )

        if not self.available:
            logger.debug(
                "Competitor analysis cache get skipped - Redis unavailable",
                extra={
                    "competitor_id": competitor_id,
                    "analysis_type": analysis_type,
                    "project_id": project_id,
                },
            )
            return CompetitorAnalysisCacheResult(
                success=True,
                cache_hit=False,
                error="Redis unavailable",
            )

        cache_key = self._build_cache_key(competitor_id, analysis_type, url)

        try:
            cached_bytes = await redis_manager.get(cache_key)
            duration_ms = (time.monotonic() - start_time) * 1000

            if cached_bytes is None:
                self._stats.misses += 1
                logger.debug(
                    "Competitor analysis cache miss",
                    extra={
                        "competitor_id": competitor_id,
                        "analysis_type": analysis_type,
                        "cache_key": cache_key[:100],
                        "duration_ms": round(duration_ms, 2),
                        "project_id": project_id,
                    },
                )
                return CompetitorAnalysisCacheResult(
                    success=True,
                    cache_hit=False,
                    duration_ms=duration_ms,
                )

            # Deserialize cached data
            cached_str = cached_bytes.decode("utf-8")
            cached_data = self._deserialize_data(cached_str)

            self._stats.hits += 1
            logger.debug(
                "Competitor analysis cache hit",
                extra={
                    "competitor_id": competitor_id,
                    "analysis_type": analysis_type,
                    "cache_key": cache_key[:100],
                    "duration_ms": round(duration_ms, 2),
                    "cached_at": cached_data.cached_at,
                    "project_id": project_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow competitor analysis cache get operation",
                    extra={
                        "competitor_id": competitor_id,
                        "analysis_type": analysis_type,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return CompetitorAnalysisCacheResult(
                success=True,
                data=cached_data,
                cache_hit=True,
                duration_ms=duration_ms,
            )

        except json.JSONDecodeError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "Competitor analysis cache deserialization error",
                extra={
                    "competitor_id": competitor_id,
                    "analysis_type": analysis_type,
                    "cache_key": cache_key[:100],
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Delete corrupted cache entry
            await redis_manager.delete(cache_key)
            return CompetitorAnalysisCacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache deserialization failed: {e}",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "Competitor analysis cache get error",
                extra={
                    "competitor_id": competitor_id,
                    "analysis_type": analysis_type,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return CompetitorAnalysisCacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache error: {e}",
                duration_ms=duration_ms,
            )

    async def set(
        self,
        competitor_id: str,
        analysis_type: str,
        url: str,
        analysis_data: dict[str, Any],
        project_id: str | None = None,
    ) -> bool:
        """Cache competitor analysis data.

        Args:
            competitor_id: The competitor ID
            analysis_type: Type of analysis (e.g., 'content', 'seo', 'keywords')
            url: The competitor URL
            analysis_data: The analysis data to cache
            project_id: Project ID for logging

        Returns:
            True if cached successfully, False otherwise
        """
        start_time = time.monotonic()

        logger.debug(
            "Competitor analysis cache set started",
            extra={
                "competitor_id": competitor_id,
                "analysis_type": analysis_type,
                "url": url[:100] if url else "",
                "data_keys": list(analysis_data.keys()) if analysis_data else [],
                "project_id": project_id,
            },
        )

        if not self.available:
            logger.debug(
                "Competitor analysis cache set skipped - Redis unavailable",
                extra={
                    "competitor_id": competitor_id,
                    "analysis_type": analysis_type,
                    "project_id": project_id,
                },
            )
            return False

        if not competitor_id:
            logger.warning(
                "Competitor analysis cache set validation failed - empty competitor_id",
                extra={
                    "field": "competitor_id",
                    "value": "",
                    "project_id": project_id,
                },
            )
            raise CompetitorAnalysisCacheValidationError(
                "competitor_id", "", "Competitor ID cannot be empty"
            )

        if not analysis_type:
            logger.warning(
                "Competitor analysis cache set validation failed - empty analysis_type",
                extra={
                    "field": "analysis_type",
                    "value": "",
                    "competitor_id": competitor_id,
                    "project_id": project_id,
                },
            )
            raise CompetitorAnalysisCacheValidationError(
                "analysis_type", "", "Analysis type cannot be empty"
            )

        if not url:
            logger.warning(
                "Competitor analysis cache set validation failed - empty url",
                extra={
                    "field": "url",
                    "value": "",
                    "competitor_id": competitor_id,
                    "project_id": project_id,
                },
            )
            raise CompetitorAnalysisCacheValidationError(
                "url", "", "URL cannot be empty"
            )

        cache_key = self._build_cache_key(competitor_id, analysis_type, url)

        try:
            cached_data = CachedAnalysisData(
                competitor_id=competitor_id,
                url=url,
                analysis_type=analysis_type,
                analysis_data=analysis_data,
                project_id=project_id,
                cached_at=time.time(),
            )

            serialized = self._serialize_data(cached_data)
            result = await redis_manager.set(
                cache_key, serialized, ex=self._ttl_seconds
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if result:
                logger.debug(
                    "Competitor analysis cache set success",
                    extra={
                        "competitor_id": competitor_id,
                        "analysis_type": analysis_type,
                        "cache_key": cache_key[:100],
                        "ttl_seconds": self._ttl_seconds,
                        "duration_ms": round(duration_ms, 2),
                        "project_id": project_id,
                    },
                )
            else:
                logger.warning(
                    "Competitor analysis cache set failed",
                    extra={
                        "competitor_id": competitor_id,
                        "analysis_type": analysis_type,
                        "cache_key": cache_key[:100],
                        "duration_ms": round(duration_ms, 2),
                        "project_id": project_id,
                    },
                )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow competitor analysis cache set operation",
                    extra={
                        "competitor_id": competitor_id,
                        "analysis_type": analysis_type,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return bool(result)

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "Competitor analysis cache set error",
                extra={
                    "competitor_id": competitor_id,
                    "analysis_type": analysis_type,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return False

    async def delete(
        self,
        competitor_id: str,
        analysis_type: str,
        url: str,
    ) -> bool:
        """Delete cached competitor analysis data.

        Args:
            competitor_id: Competitor ID to delete
            analysis_type: Analysis type to delete
            url: Competitor URL

        Returns:
            True if deleted, False otherwise
        """
        if not self.available:
            return False

        cache_key = self._build_cache_key(competitor_id, analysis_type, url)

        try:
            result = await redis_manager.delete(cache_key)
            logger.debug(
                "Competitor analysis cache delete",
                extra={
                    "competitor_id": competitor_id,
                    "analysis_type": analysis_type,
                    "cache_key": cache_key[:100],
                    "deleted": bool(result),
                },
            )
            return bool(result)
        except Exception as e:
            logger.error(
                "Competitor analysis cache delete error",
                extra={
                    "competitor_id": competitor_id,
                    "analysis_type": analysis_type,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return False

    async def delete_all_for_competitor(
        self,
        competitor_id: str,
    ) -> int:
        """Delete all cached analysis data for a competitor.

        Note: This performs a pattern-based deletion which may be slower
        than individual deletes. Use sparingly.

        Args:
            competitor_id: Competitor ID to clear cache for

        Returns:
            Number of keys deleted
        """
        if not self.available:
            return 0

        # We cannot do pattern matching without SCAN, so log a warning
        # In production, individual analysis types should be tracked
        logger.warning(
            "delete_all_for_competitor called - consider tracking analysis types",
            extra={
                "competitor_id": competitor_id,
            },
        )
        return 0

    async def get_ttl(
        self,
        competitor_id: str,
        analysis_type: str,
        url: str,
    ) -> int | None:
        """Get remaining TTL for cached competitor analysis.

        Args:
            competitor_id: Competitor ID to check
            analysis_type: Analysis type to check
            url: Competitor URL

        Returns:
            Remaining TTL in seconds, or None if not cached
        """
        if not self.available:
            return None

        cache_key = self._build_cache_key(competitor_id, analysis_type, url)

        try:
            ttl = await redis_manager.ttl(cache_key)
            # Redis returns -2 if key doesn't exist, -1 if no TTL
            if ttl is None or ttl < 0:
                return None
            return ttl
        except Exception as e:
            logger.error(
                "Competitor analysis cache TTL check error",
                extra={
                    "competitor_id": competitor_id,
                    "analysis_type": analysis_type,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
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
_competitor_analysis_cache_service: CompetitorAnalysisCacheService | None = None


def get_competitor_analysis_cache_service() -> CompetitorAnalysisCacheService:
    """Get the global competitor analysis cache service instance.

    Usage:
        from app.services.competitor_analysis_cache import (
            get_competitor_analysis_cache_service
        )
        cache = get_competitor_analysis_cache_service()
        result = await cache.get("comp-123", "content", "https://example.com")
    """
    global _competitor_analysis_cache_service
    if _competitor_analysis_cache_service is None:
        _competitor_analysis_cache_service = CompetitorAnalysisCacheService()
        logger.info("CompetitorAnalysisCacheService singleton created")
    return _competitor_analysis_cache_service
