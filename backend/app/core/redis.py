"""Redis client with connection pooling and circuit breaker pattern.

Features:
- Connection pooling via redis-py
- Circuit breaker for fault tolerance
- SSL/TLS support for production (Railway)
- Graceful degradation when Redis is unavailable
- Connection retry logic for cold starts
- Comprehensive logging per requirements
"""

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import (
    AuthenticationError,
    RedisError,
)
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
)
from redis.exceptions import (
    TimeoutError as RedisTimeoutError,
)

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import get_logger, redis_logger

logger = get_logger(__name__)


class RedisManager:
    """Manages Redis connections with pooling and circuit breaker."""

    def __init__(self) -> None:
        self._pool: ConnectionPool | None = None
        self._client: Redis | None = None
        self._circuit_breaker: CircuitBreaker | None = None
        self._available = False

    @property
    def available(self) -> bool:
        """Check if Redis is available."""
        return self._available and self._client is not None

    @property
    def circuit_breaker(self) -> CircuitBreaker | None:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    async def init_redis(self) -> bool:
        """Initialize Redis connection pool.

        Returns True if Redis is available, False otherwise.
        Redis is optional - the app should work without it.
        """
        settings = get_settings()

        if not settings.redis_url:
            logger.info("Redis URL not configured, Redis features disabled")
            self._available = False
            return False

        redis_url = str(settings.redis_url)

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            config=CircuitBreakerConfig(
                failure_threshold=settings.redis_circuit_failure_threshold,
                recovery_timeout=settings.redis_circuit_recovery_timeout,
            ),
            name="redis",
        )

        try:
            # Create connection pool
            self._pool = ConnectionPool.from_url(
                redis_url,
                max_connections=settings.redis_pool_size,
                socket_connect_timeout=settings.redis_connect_timeout,
                socket_timeout=settings.redis_socket_timeout,
                retry_on_timeout=settings.redis_retry_on_timeout,
                health_check_interval=settings.redis_health_check_interval,
            )

            # Create client with pool
            self._client = Redis(connection_pool=self._pool)

            # Test connection with retry logic for cold starts
            await self._connect_with_retry(redis_url)

            self._available = True
            redis_logger.connection_success()
            return True

        except Exception as e:
            redis_logger.connection_error(e, redis_url)
            self._available = False
            # Don't raise - Redis is optional
            return False

    async def _connect_with_retry(
        self,
        redis_url: str,  # noqa: ARG002
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        """Connect to Redis with retry logic for Railway cold starts."""
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                if self._client:
                    await self._client.ping()  # type: ignore[misc]
                    return
            except (RedisConnectionError, RedisTimeoutError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"Redis connection attempt {attempt + 1} failed, "
                        f"retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay_seconds": delay,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(delay)

        if last_error:
            raise last_error

    async def close(self) -> None:
        """Close Redis connections."""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None
        self._available = False
        logger.info("Redis connections closed")

    async def execute(self, operation: str, *args: Any, **kwargs: Any) -> Any | None:
        """Execute a Redis operation with circuit breaker protection.

        Returns None if Redis is unavailable (graceful degradation).
        """
        if not self._client or not self._circuit_breaker:
            redis_logger.graceful_fallback(operation, "Redis not initialized")
            return None

        if not await self._circuit_breaker.can_execute():
            redis_logger.graceful_fallback(operation, "Circuit breaker open")
            return None

        start_time = time.monotonic()
        key = str(args[0]) if args else ""

        try:
            method = getattr(self._client, operation)
            result = await method(*args, **kwargs)

            duration_ms = (time.monotonic() - start_time) * 1000
            redis_logger.operation(operation, key, duration_ms, success=True)
            await self._circuit_breaker.record_success()
            return result

        except RedisTimeoutError:
            duration_ms = (time.monotonic() - start_time) * 1000
            settings = get_settings()
            redis_logger.timeout(operation, key, settings.redis_socket_timeout)
            redis_logger.operation(operation, key, duration_ms, success=False)
            await self._circuit_breaker.record_failure()
            return None

        except AuthenticationError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            settings = get_settings()
            redis_logger.connection_error(e, str(settings.redis_url))
            redis_logger.operation(operation, key, duration_ms, success=False)
            await self._circuit_breaker.record_failure()
            return None

        except RedisConnectionError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            settings = get_settings()
            redis_logger.connection_error(e, str(settings.redis_url))
            redis_logger.operation(operation, key, duration_ms, success=False)
            await self._circuit_breaker.record_failure()
            return None

        except RedisError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            redis_logger.operation(operation, key, duration_ms, success=False)
            await self._circuit_breaker.record_failure()
            logger.error(
                f"Redis error during {operation}",
                extra={
                    "operation": operation,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            return None

    # Convenience methods for common operations

    async def get(self, key: str) -> bytes | None:
        """Get a value from Redis."""
        return await self.execute("get", key)

    async def set(
        self,
        key: str,
        value: str | bytes,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool | None:
        """Set a value in Redis."""
        kwargs: dict[str, Any] = {}
        if ex is not None:
            kwargs["ex"] = ex
        if px is not None:
            kwargs["px"] = px
        if nx:
            kwargs["nx"] = nx
        if xx:
            kwargs["xx"] = xx
        result = await self.execute("set", key, value, **kwargs)
        return result is not None

    async def delete(self, *keys: str) -> int | None:
        """Delete keys from Redis."""
        return await self.execute("delete", *keys)

    async def exists(self, *keys: str) -> int | None:
        """Check if keys exist in Redis."""
        return await self.execute("exists", *keys)

    async def expire(self, key: str, seconds: int) -> bool | None:
        """Set expiration on a key."""
        return await self.execute("expire", key, seconds)

    async def ttl(self, key: str) -> int | None:
        """Get TTL of a key."""
        return await self.execute("ttl", key)

    async def incr(self, key: str) -> int | None:
        """Increment a key."""
        return await self.execute("incr", key)

    async def decr(self, key: str) -> int | None:
        """Decrement a key."""
        return await self.execute("decr", key)

    async def hget(self, name: str, key: str) -> bytes | None:
        """Get a hash field."""
        return await self.execute("hget", name, key)

    async def hset(
        self,
        name: str,
        key: str | None = None,
        value: Any = None,
        mapping: dict[str, Any] | None = None,
    ) -> int | None:
        """Set hash field(s)."""
        if mapping:
            return await self.execute("hset", name, mapping=mapping)
        return await self.execute("hset", name, key, value)

    async def hgetall(self, name: str) -> dict[str, Any] | None:
        """Get all hash fields."""
        return await self.execute("hgetall", name)

    async def lpush(self, name: str, *values: Any) -> int | None:
        """Push values to list head."""
        return await self.execute("lpush", name, *values)

    async def rpush(self, name: str, *values: Any) -> int | None:
        """Push values to list tail."""
        return await self.execute("rpush", name, *values)

    async def lpop(self, name: str, count: int | None = None) -> Any | None:
        """Pop from list head."""
        if count:
            return await self.execute("lpop", name, count)
        return await self.execute("lpop", name)

    async def lrange(self, name: str, start: int, end: int) -> list[Any] | None:
        """Get list range."""
        return await self.execute("lrange", name, start, end)

    async def ping(self) -> bool:
        """Ping Redis to check connection."""
        result = await self.execute("ping")
        return result is True or result == b"PONG"

    async def check_health(self) -> bool:
        """Check if Redis connection is healthy."""
        if not self._available:
            return False
        try:
            return await self.ping()
        except Exception:
            return False


# Global Redis manager instance
redis_manager = RedisManager()


async def get_redis() -> RedisManager:
    """Dependency for getting Redis client.

    Usage:
        @app.get("/items")
        async def get_items(redis: RedisManager = Depends(get_redis)):
            value = await redis.get("key")
            ...
    """
    return redis_manager


@asynccontextmanager
async def redis_operation(operation_name: str) -> AsyncGenerator[RedisManager, None]:
    """Context manager for Redis operations with timing.

    Usage:
        async with redis_operation("cache_lookup") as redis:
            if redis.available:
                value = await redis.get("key")
    """
    start_time = time.monotonic()
    try:
        yield redis_manager
    finally:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.debug(
            "Redis operation block completed",
            extra={
                "operation": operation_name,
                "duration_ms": round(duration_ms, 2),
            },
        )
