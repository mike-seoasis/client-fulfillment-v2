"""PAA (People Also Ask) result caching service using Redis.

Caches PAA enrichment results from DataForSEO API with 24-hour TTL.
Handles Redis connection failures gracefully (cache is optional).

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

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
CACHE_KEY_PREFIX = "paa:"
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
class CachedPAAData:
    """Cached PAA data with metadata."""

    keyword: str
    questions: list[dict[str, Any]] = field(default_factory=list)
    initial_count: int = 0
    nested_count: int = 0
    location_code: int = 2840  # Default: US
    language_code: str = "en"
    cached_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "keyword": self.keyword,
            "questions": self.questions,
            "initial_count": self.initial_count,
            "nested_count": self.nested_count,
            "location_code": self.location_code,
            "language_code": self.language_code,
            "cached_at": self.cached_at,
        }


@dataclass
class PAACacheResult:
    """Result of a cache operation."""

    success: bool
    data: CachedPAAData | None = None
    error: str | None = None
    cache_hit: bool = False
    duration_ms: float = 0.0


class PAACacheServiceError(Exception):
    """Base exception for PAA cache service errors."""

    pass


class PAACacheValidationError(PAACacheServiceError):
    """Raised when validation fails."""

    def __init__(self, field_name: str, value: str, message: str) -> None:
        super().__init__(f"Validation error for {field_name}: {message}")
        self.field_name = field_name
        self.value = value
        self.message = message


class PAACacheService:
    """Service for caching PAA enrichment results in Redis.

    Features:
    - 24-hour TTL for cached PAA data
    - Graceful degradation when Redis is unavailable
    - Comprehensive logging per requirements
    - Support for location and language variations

    Cache key format: paa:{location}:{language}:{keyword_hash}
    """

    def __init__(self, ttl_hours: int | None = None) -> None:
        """Initialize PAA cache service.

        Args:
            ttl_hours: TTL for cached data in hours. Defaults to 24 hours.
        """
        self._ttl_seconds = (ttl_hours or DEFAULT_TTL_HOURS) * 3600  # hours to seconds
        self._stats = CacheStats()

        logger.debug(
            "PAACacheService initialized",
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
    ) -> str:
        """Build cache key for PAA results.

        Format: paa:{location}:{language}:{keyword_hash}
        """
        keyword_hash = self._hash_keyword(keyword)
        return f"{CACHE_KEY_PREFIX}{location_code}:{language_code}:{keyword_hash}"

    def _serialize_data(self, data: CachedPAAData) -> str:
        """Serialize cached data to JSON."""
        return json.dumps(data.to_dict())

    def _deserialize_data(self, json_str: str) -> CachedPAAData:
        """Deserialize JSON to cached data."""
        data = json.loads(json_str)
        return CachedPAAData(
            keyword=data["keyword"],
            questions=data.get("questions", []),
            initial_count=data.get("initial_count", 0),
            nested_count=data.get("nested_count", 0),
            location_code=data.get("location_code", 2840),
            language_code=data.get("language_code", "en"),
            cached_at=data.get("cached_at", 0.0),
        )

    async def get(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> PAACacheResult:
        """Get cached PAA data.

        Args:
            keyword: The keyword to look up
            location_code: Location code (e.g., 2840 for US)
            language_code: Language code (e.g., 'en')
            project_id: Project ID for logging context
            page_id: Page ID for logging context

        Returns:
            PAACacheResult with cached data if found
        """
        start_time = time.monotonic()

        logger.debug(
            "PAA cache get started",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "language_code": language_code,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        if not self.available:
            logger.debug(
                "PAA cache get skipped - Redis unavailable",
                extra={
                    "keyword": keyword[:50],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return PAACacheResult(
                success=True,
                cache_hit=False,
                error="Redis unavailable",
            )

        cache_key = self._build_cache_key(keyword, location_code, language_code)

        try:
            cached_bytes = await redis_manager.get(cache_key)
            duration_ms = (time.monotonic() - start_time) * 1000

            if cached_bytes is None:
                self._stats.misses += 1
                logger.debug(
                    "PAA cache miss",
                    extra={
                        "keyword": keyword[:50],
                        "cache_key": cache_key[:100],
                        "duration_ms": round(duration_ms, 2),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return PAACacheResult(
                    success=True,
                    cache_hit=False,
                    duration_ms=duration_ms,
                )

            # Deserialize cached data
            cached_str = cached_bytes.decode("utf-8")
            cached_data = self._deserialize_data(cached_str)

            self._stats.hits += 1
            logger.debug(
                "PAA cache hit",
                extra={
                    "keyword": keyword[:50],
                    "cache_key": cache_key[:100],
                    "duration_ms": round(duration_ms, 2),
                    "cached_at": cached_data.cached_at,
                    "questions_count": len(cached_data.questions),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow PAA cache get operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return PAACacheResult(
                success=True,
                data=cached_data,
                cache_hit=True,
                duration_ms=duration_ms,
            )

        except json.JSONDecodeError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "PAA cache deserialization error",
                extra={
                    "keyword": keyword[:50],
                    "cache_key": cache_key[:100],
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Delete corrupted cache entry
            await redis_manager.delete(cache_key)
            return PAACacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache deserialization failed: {e}",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "PAA cache get error",
                extra={
                    "keyword": keyword[:50],
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return PAACacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache error: {e}",
                duration_ms=duration_ms,
            )

    async def set(
        self,
        keyword: str,
        questions: list[dict[str, Any]],
        initial_count: int,
        nested_count: int,
        location_code: int = 2840,
        language_code: str = "en",
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> bool:
        """Cache PAA data.

        Args:
            keyword: The keyword
            questions: List of PAA questions (as dicts)
            initial_count: Number of initial questions
            nested_count: Number of nested questions
            location_code: Location code
            language_code: Language code
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            True if cached successfully, False otherwise
        """
        start_time = time.monotonic()

        logger.debug(
            "PAA cache set started",
            extra={
                "keyword": keyword[:50],
                "location_code": location_code,
                "language_code": language_code,
                "questions_count": len(questions),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        if not self.available:
            logger.debug(
                "PAA cache set skipped - Redis unavailable",
                extra={
                    "keyword": keyword[:50],
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return False

        if not keyword:
            logger.warning(
                "PAA cache set validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise PAACacheValidationError("keyword", "", "Keyword cannot be empty")

        cache_key = self._build_cache_key(keyword, location_code, language_code)

        try:
            cached_data = CachedPAAData(
                keyword=keyword,
                questions=questions,
                initial_count=initial_count,
                nested_count=nested_count,
                location_code=location_code,
                language_code=language_code,
                cached_at=time.time(),
            )

            serialized = self._serialize_data(cached_data)
            result = await redis_manager.set(
                cache_key, serialized, ex=self._ttl_seconds
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if result:
                logger.debug(
                    "PAA cache set success",
                    extra={
                        "keyword": keyword[:50],
                        "cache_key": cache_key[:100],
                        "ttl_seconds": self._ttl_seconds,
                        "duration_ms": round(duration_ms, 2),
                        "questions_count": len(questions),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
            else:
                logger.warning(
                    "PAA cache set failed",
                    extra={
                        "keyword": keyword[:50],
                        "cache_key": cache_key[:100],
                        "duration_ms": round(duration_ms, 2),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow PAA cache set operation",
                    extra={
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return bool(result)

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            self._stats.errors += 1
            logger.error(
                "PAA cache set error",
                extra={
                    "keyword": keyword[:50],
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return False

    async def delete(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
    ) -> bool:
        """Delete cached PAA data.

        Args:
            keyword: Keyword to delete
            location_code: Location code
            language_code: Language code

        Returns:
            True if deleted, False otherwise
        """
        if not self.available:
            return False

        cache_key = self._build_cache_key(keyword, location_code, language_code)

        try:
            result = await redis_manager.delete(cache_key)
            logger.debug(
                "PAA cache delete",
                extra={
                    "keyword": keyword[:50],
                    "cache_key": cache_key[:100],
                    "deleted": bool(result),
                },
            )
            return bool(result)
        except Exception as e:
            logger.error(
                "PAA cache delete error",
                extra={
                    "keyword": keyword[:50],
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return False

    async def get_ttl(
        self,
        keyword: str,
        location_code: int = 2840,
        language_code: str = "en",
    ) -> int | None:
        """Get remaining TTL for a cached PAA result.

        Args:
            keyword: Keyword to check
            location_code: Location code
            language_code: Language code

        Returns:
            Remaining TTL in seconds, or None if not cached
        """
        if not self.available:
            return None

        cache_key = self._build_cache_key(keyword, location_code, language_code)

        try:
            ttl = await redis_manager.ttl(cache_key)
            # Redis returns -2 if key doesn't exist, -1 if no TTL
            if ttl is None or ttl < 0:
                return None
            return ttl
        except Exception as e:
            logger.error(
                "PAA cache TTL check error",
                extra={
                    "keyword": keyword[:50],
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
_paa_cache_service: PAACacheService | None = None


def get_paa_cache_service() -> PAACacheService:
    """Get the global PAA cache service instance.

    Usage:
        from app.services.paa_cache import get_paa_cache_service
        cache = get_paa_cache_service()
        result = await cache.get("hiking boots")
    """
    global _paa_cache_service
    if _paa_cache_service is None:
        _paa_cache_service = PAACacheService()
        logger.info("PAACacheService singleton created")
    return _paa_cache_service
