"""Brand research caching and rate limiting service using Redis.

Caches Perplexity brand research results with 24-hour TTL.
Implements rate limiting of 5 requests per hour per project.

Features:
- 24-hour cache TTL for research results
- Rate limiting: 5 requests per hour per project
- Cache bypass option for force refresh
- Graceful degradation when Redis is unavailable
"""

import hashlib
import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.core.redis import redis_manager

logger = get_logger(__name__)

# Constants
CACHE_KEY_PREFIX = "brand_research:"
RATE_LIMIT_KEY_PREFIX = "brand_research_rate:"
CACHE_TTL_HOURS = 24
CACHE_TTL_SECONDS = CACHE_TTL_HOURS * 3600  # 24 hours in seconds
RATE_LIMIT_MAX_REQUESTS = 5
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour


@dataclass
class CachedBrandResearch:
    """Cached brand research data with metadata."""

    domain: str
    project_id: str
    research_data: dict[str, Any] = field(default_factory=dict)
    raw_text: str | None = None
    citations: list[str] = field(default_factory=list)
    cached_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + CACHE_TTL_SECONDS)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "domain": self.domain,
            "project_id": self.project_id,
            "research_data": self.research_data,
            "raw_text": self.raw_text,
            "citations": self.citations,
            "cached_at": self.cached_at,
            "expires_at": self.expires_at,
        }

    @property
    def cached_at_datetime(self) -> datetime:
        """Get cached_at as datetime."""
        return datetime.fromtimestamp(self.cached_at)

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time.time() > self.expires_at


@dataclass
class BrandResearchCacheResult:
    """Result of a cache lookup operation."""

    success: bool
    data: CachedBrandResearch | None = None
    error: str | None = None
    cache_hit: bool = False
    from_cache: bool = False
    cached_at: datetime | None = None


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    requests_remaining: int
    requests_used: int
    reset_at: datetime | None = None
    error: str | None = None


class BrandResearchCacheService:
    """Service for caching brand research results and enforcing rate limits.

    Features:
    - 24-hour TTL for cached research data
    - Rate limiting: 5 requests per hour per project
    - Cache bypass option for force refresh
    - Graceful degradation when Redis is unavailable

    Cache key format: brand_research:{project_id}:{domain_hash}
    Rate limit key format: brand_research_rate:{project_id}
    """

    def __init__(
        self,
        cache_ttl_hours: int = CACHE_TTL_HOURS,
        rate_limit_max: int = RATE_LIMIT_MAX_REQUESTS,
        rate_limit_window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        """Initialize brand research cache service.

        Args:
            cache_ttl_hours: TTL for cached data in hours. Defaults to 24.
            rate_limit_max: Maximum requests per window. Defaults to 5.
            rate_limit_window_seconds: Rate limit window in seconds. Defaults to 3600 (1 hour).
        """
        self._cache_ttl_seconds = cache_ttl_hours * 3600
        self._rate_limit_max = rate_limit_max
        self._rate_limit_window = rate_limit_window_seconds

        logger.debug(
            "BrandResearchCacheService initialized",
            extra={
                "cache_ttl_hours": cache_ttl_hours,
                "rate_limit_max": rate_limit_max,
                "rate_limit_window_seconds": rate_limit_window_seconds,
            },
        )

    @property
    def available(self) -> bool:
        """Check if Redis cache is available."""
        return redis_manager.available

    def _hash_domain(self, domain: str) -> str:
        """Create a stable hash for the domain.

        Normalizes domain and creates SHA256 hash truncated to 16 chars.
        """
        # Normalize: lowercase, strip protocol and trailing slashes
        normalized = domain.lower().strip()
        normalized = normalized.replace("https://", "").replace("http://", "")
        normalized = normalized.rstrip("/").split("/")[0]  # Get just the domain
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _build_cache_key(self, project_id: str, domain: str) -> str:
        """Build cache key for brand research results.

        Format: brand_research:{project_id}:{domain_hash}
        """
        domain_hash = self._hash_domain(domain)
        return f"{CACHE_KEY_PREFIX}{project_id}:{domain_hash}"

    def _build_rate_limit_key(self, project_id: str) -> str:
        """Build rate limit key for a project.

        Format: brand_research_rate:{project_id}
        """
        return f"{RATE_LIMIT_KEY_PREFIX}{project_id}"

    def _serialize_data(self, data: CachedBrandResearch) -> str:
        """Serialize cached data to JSON."""
        return json.dumps(data.to_dict())

    def _deserialize_data(self, json_str: str) -> CachedBrandResearch:
        """Deserialize JSON to cached data."""
        data = json.loads(json_str)
        return CachedBrandResearch(
            domain=data["domain"],
            project_id=data["project_id"],
            research_data=data.get("research_data", {}),
            raw_text=data.get("raw_text"),
            citations=data.get("citations", []),
            cached_at=data.get("cached_at", time.time()),
            expires_at=data.get("expires_at", time.time() + self._cache_ttl_seconds),
        )

    async def check_rate_limit(self, project_id: str) -> RateLimitResult:
        """Check if a project has exceeded its rate limit.

        Args:
            project_id: The project ID to check

        Returns:
            RateLimitResult indicating if request is allowed
        """
        if not self.available:
            # If Redis unavailable, allow the request but log warning
            logger.warning(
                "Rate limit check skipped - Redis unavailable",
                extra={"project_id": project_id},
            )
            return RateLimitResult(
                allowed=True,
                requests_remaining=self._rate_limit_max,
                requests_used=0,
                error="Redis unavailable - rate limiting disabled",
            )

        rate_key = self._build_rate_limit_key(project_id)

        try:
            # Get current count
            count_bytes = await redis_manager.get(rate_key)

            if count_bytes is None:
                # No requests yet in this window
                return RateLimitResult(
                    allowed=True,
                    requests_remaining=self._rate_limit_max,
                    requests_used=0,
                )

            current_count = int(count_bytes.decode("utf-8"))

            # Get TTL to determine reset time
            ttl = await redis_manager.ttl(rate_key)
            reset_at = None
            if ttl and ttl > 0:
                reset_at = datetime.fromtimestamp(time.time() + ttl)

            if current_count >= self._rate_limit_max:
                logger.warning(
                    "Brand research rate limit exceeded",
                    extra={
                        "project_id": project_id,
                        "current_count": current_count,
                        "max_requests": self._rate_limit_max,
                        "reset_in_seconds": ttl,
                    },
                )
                return RateLimitResult(
                    allowed=False,
                    requests_remaining=0,
                    requests_used=current_count,
                    reset_at=reset_at,
                )

            return RateLimitResult(
                allowed=True,
                requests_remaining=self._rate_limit_max - current_count,
                requests_used=current_count,
                reset_at=reset_at,
            )

        except Exception as e:
            logger.error(
                "Rate limit check error",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # On error, allow the request
            return RateLimitResult(
                allowed=True,
                requests_remaining=self._rate_limit_max,
                requests_used=0,
                error=f"Rate limit check failed: {e}",
            )

    async def increment_rate_limit(self, project_id: str) -> bool:
        """Increment the rate limit counter for a project.

        Should be called after a successful research request.

        Args:
            project_id: The project ID

        Returns:
            True if increment successful, False otherwise
        """
        if not self.available:
            return False

        rate_key = self._build_rate_limit_key(project_id)

        try:
            # Increment counter
            new_count = await redis_manager.incr(rate_key)

            # Set expiry on first increment (if key was just created)
            if new_count == 1:
                await redis_manager.expire(rate_key, self._rate_limit_window)

            logger.debug(
                "Brand research rate limit incremented",
                extra={
                    "project_id": project_id,
                    "new_count": new_count,
                    "max_requests": self._rate_limit_max,
                },
            )
            return True

        except Exception as e:
            logger.error(
                "Rate limit increment error",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return False

    async def get(
        self,
        project_id: str,
        domain: str,
    ) -> BrandResearchCacheResult:
        """Get cached brand research data.

        Args:
            project_id: The project ID
            domain: The domain that was researched

        Returns:
            BrandResearchCacheResult with cached data if found
        """
        if not self.available:
            logger.debug(
                "Brand research cache get skipped - Redis unavailable",
                extra={"project_id": project_id, "domain": domain},
            )
            return BrandResearchCacheResult(
                success=True,
                cache_hit=False,
                error="Redis unavailable",
            )

        cache_key = self._build_cache_key(project_id, domain)

        try:
            cached_bytes = await redis_manager.get(cache_key)

            if cached_bytes is None:
                logger.debug(
                    "Brand research cache miss",
                    extra={
                        "project_id": project_id,
                        "domain": domain,
                        "cache_key": cache_key[:50],
                    },
                )
                return BrandResearchCacheResult(
                    success=True,
                    cache_hit=False,
                )

            # Deserialize cached data
            cached_str = cached_bytes.decode("utf-8")
            cached_data = self._deserialize_data(cached_str)

            logger.info(
                "Brand research cache hit",
                extra={
                    "project_id": project_id,
                    "domain": domain,
                    "cached_at": cached_data.cached_at,
                },
            )

            return BrandResearchCacheResult(
                success=True,
                data=cached_data,
                cache_hit=True,
                from_cache=True,
                cached_at=cached_data.cached_at_datetime,
            )

        except json.JSONDecodeError as e:
            logger.error(
                "Brand research cache deserialization error",
                extra={
                    "project_id": project_id,
                    "domain": domain,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Delete corrupted cache entry
            await redis_manager.delete(cache_key)
            return BrandResearchCacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache deserialization failed: {e}",
            )

        except Exception as e:
            logger.error(
                "Brand research cache get error",
                extra={
                    "project_id": project_id,
                    "domain": domain,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return BrandResearchCacheResult(
                success=False,
                cache_hit=False,
                error=f"Cache error: {e}",
            )

    async def set(
        self,
        project_id: str,
        domain: str,
        research_data: dict[str, Any] | None = None,
        raw_text: str | None = None,
        citations: list[str] | None = None,
    ) -> bool:
        """Cache brand research data.

        Args:
            project_id: The project ID
            domain: The domain that was researched
            research_data: Structured research data (if synthesized)
            raw_text: Raw research text from Perplexity
            citations: List of citation URLs

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.available:
            logger.debug(
                "Brand research cache set skipped - Redis unavailable",
                extra={"project_id": project_id, "domain": domain},
            )
            return False

        cache_key = self._build_cache_key(project_id, domain)

        try:
            cached_data = CachedBrandResearch(
                domain=domain,
                project_id=project_id,
                research_data=research_data or {},
                raw_text=raw_text,
                citations=citations or [],
                cached_at=time.time(),
                expires_at=time.time() + self._cache_ttl_seconds,
            )

            serialized = self._serialize_data(cached_data)
            result = await redis_manager.set(
                cache_key, serialized, ex=self._cache_ttl_seconds
            )

            if result:
                logger.info(
                    "Brand research cached",
                    extra={
                        "project_id": project_id,
                        "domain": domain,
                        "ttl_hours": self._cache_ttl_seconds / 3600,
                        "has_raw_text": bool(raw_text),
                        "citation_count": len(citations or []),
                    },
                )
            else:
                logger.warning(
                    "Brand research cache set failed",
                    extra={"project_id": project_id, "domain": domain},
                )

            return bool(result)

        except Exception as e:
            logger.error(
                "Brand research cache set error",
                extra={
                    "project_id": project_id,
                    "domain": domain,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return False

    async def delete(self, project_id: str, domain: str) -> bool:
        """Delete cached brand research data (for force refresh).

        Args:
            project_id: The project ID
            domain: The domain to clear cache for

        Returns:
            True if deleted, False otherwise
        """
        if not self.available:
            return False

        cache_key = self._build_cache_key(project_id, domain)

        try:
            result = await redis_manager.delete(cache_key)
            logger.info(
                "Brand research cache deleted",
                extra={
                    "project_id": project_id,
                    "domain": domain,
                    "deleted": bool(result),
                },
            )
            return bool(result)
        except Exception as e:
            logger.error(
                "Brand research cache delete error",
                extra={
                    "project_id": project_id,
                    "domain": domain,
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return False

    async def get_cache_info(
        self, project_id: str, domain: str
    ) -> dict[str, Any] | None:
        """Get cache metadata without retrieving full data.

        Args:
            project_id: The project ID
            domain: The domain

        Returns:
            Dict with cache info (cached_at, ttl_remaining) or None
        """
        if not self.available:
            return None

        cache_key = self._build_cache_key(project_id, domain)

        try:
            ttl = await redis_manager.ttl(cache_key)
            if ttl is None or ttl < 0:
                return None

            return {
                "cached": True,
                "ttl_seconds": ttl,
                "ttl_hours": round(ttl / 3600, 1),
                "expires_at": datetime.fromtimestamp(time.time() + ttl).isoformat(),
            }
        except Exception:
            return None


# Global singleton instance
_brand_research_cache_service: BrandResearchCacheService | None = None


def get_brand_research_cache_service() -> BrandResearchCacheService:
    """Get the global brand research cache service instance.

    Usage:
        from app.services.brand_research_cache import get_brand_research_cache_service
        cache = get_brand_research_cache_service()
        result = await cache.get("project-123", "example.com")
    """
    global _brand_research_cache_service
    if _brand_research_cache_service is None:
        _brand_research_cache_service = BrandResearchCacheService()
        logger.info("BrandResearchCacheService singleton created")
    return _brand_research_cache_service
