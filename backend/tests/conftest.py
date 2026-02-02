"""Pytest configuration and fixtures.

Provides fixtures for:
- Database mocking with SQLite in-memory
- Redis mocking
- FastAPI test client
- Settings override for testing
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import JSON, String

from app.core.config import Settings, get_settings
from app.core.database import Base, DatabaseManager, db_manager
from app.core.redis import CircuitBreaker, CircuitBreakerConfig, RedisManager

# ---------------------------------------------------------------------------
# SQLite Type Compatibility
# ---------------------------------------------------------------------------


def _adapt_postgres_types_for_sqlite() -> None:
    """Adapt PostgreSQL-specific column types and defaults to work with SQLite.

    This allows tests to use SQLite for fast in-memory testing while
    production uses PostgreSQL with its native types.
    """
    # For each table, replace PostgreSQL-specific types and defaults
    for table in Base.metadata.tables.values():
        for column in table.columns:
            # Replace PostgreSQL UUID with String
            if isinstance(column.type, UUID):
                column.type = String(36)
            # Replace JSONB with JSON
            elif isinstance(column.type, JSONB):
                column.type = JSON()

            # Clear PostgreSQL-specific server defaults that SQLite can't handle
            if column.server_default is not None:
                default_text = str(column.server_default.arg) if hasattr(column.server_default, 'arg') else str(column.server_default)
                # Check for PostgreSQL-specific defaults
                postgres_defaults = (
                    'gen_random_uuid()',
                    '::jsonb',
                    'now()',
                    'CURRENT_TIMESTAMP',
                )
                if any(pg_default in default_text for pg_default in postgres_defaults):
                    column.server_default = None

# ---------------------------------------------------------------------------
# Settings Fixtures
# ---------------------------------------------------------------------------


def get_test_settings() -> Settings:
    """Get test settings with SQLite database."""
    return Settings(
        app_name="Test App",
        app_version="0.0.1",
        debug=True,
        environment="test",
        database_url="postgresql://test:test@localhost:5432/test",  # type: ignore[arg-type]
        log_level="DEBUG",
        log_format="text",
    )


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Session-scoped test settings."""
    return get_test_settings()


# ---------------------------------------------------------------------------
# Database Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for session-scoped async fixtures."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create async SQLite engine for testing.

    Uses SQLite with aiosqlite driver for fast, in-memory testing.
    StaticPool ensures the same connection is reused within the session.
    """
    # Adapt PostgreSQL types (UUID, JSONB) to SQLite-compatible types
    _adapt_postgres_types_for_sqlite()

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="session")
def async_session_factory(
    async_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create async session factory for testing."""
    return async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def db_session(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for each test.

    Each test gets a fresh session with automatic rollback,
    so tests don't affect each other.
    """
    async with async_session_factory() as session:
        yield session
        # Rollback any uncommitted changes after each test
        await session.rollback()


@pytest.fixture
def mock_db_manager(
    async_engine: AsyncEngine,
    async_session_factory: async_sessionmaker[AsyncSession],
) -> Generator[DatabaseManager, None, None]:
    """Mock the global database manager for testing."""
    # Store original state
    original_engine = db_manager._engine
    original_factory = db_manager._session_factory

    # Set test engine and factory
    db_manager._engine = async_engine
    db_manager._session_factory = async_session_factory

    yield db_manager

    # Restore original state
    db_manager._engine = original_engine
    db_manager._session_factory = original_factory


# ---------------------------------------------------------------------------
# Redis Fixtures
# ---------------------------------------------------------------------------


class MockRedis:
    """Mock Redis client for testing.

    Implements common Redis operations with in-memory storage.
    """

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._hashes: dict[str, dict[str, Any]] = {}
        self._lists: dict[str, list[Any]] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> bytes | None:
        value = self._data.get(key)
        if value is None:
            return None
        return value if isinstance(value, bytes) else str(value).encode()

    async def set(
        self,
        key: str,
        value: str | bytes,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        if nx and key in self._data:
            return False
        if xx and key not in self._data:
            return False
        self._data[key] = value
        if ex:
            self._ttls[key] = ex
        return True

    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
            self._ttls.pop(key, None)
        return count

    async def exists(self, *keys: str) -> int:
        return sum(1 for key in keys if key in self._data)

    async def expire(self, key: str, seconds: int) -> bool:
        if key in self._data:
            self._ttls[key] = seconds
            return True
        return False

    async def ttl(self, key: str) -> int:
        if key not in self._data:
            return -2
        return self._ttls.get(key, -1)

    async def incr(self, key: str) -> int:
        if key not in self._data:
            self._data[key] = 0
        self._data[key] = int(self._data[key]) + 1
        return self._data[key]

    async def decr(self, key: str) -> int:
        if key not in self._data:
            self._data[key] = 0
        self._data[key] = int(self._data[key]) - 1
        return self._data[key]

    async def hget(self, name: str, key: str) -> bytes | None:
        if name not in self._hashes:
            return None
        value = self._hashes[name].get(key)
        if value is None:
            return None
        return value if isinstance(value, bytes) else str(value).encode()

    async def hset(
        self,
        name: str,
        key: str | None = None,
        value: Any = None,
        mapping: dict | None = None,
    ) -> int:
        if name not in self._hashes:
            self._hashes[name] = {}

        count = 0
        if mapping:
            for k, v in mapping.items():
                if k not in self._hashes[name]:
                    count += 1
                self._hashes[name][k] = v
        elif key is not None:
            if key not in self._hashes[name]:
                count = 1
            self._hashes[name][key] = value
        return count

    async def hgetall(self, name: str) -> dict:
        return self._hashes.get(name, {})

    async def lpush(self, name: str, *values: Any) -> int:
        if name not in self._lists:
            self._lists[name] = []
        for value in values:
            self._lists[name].insert(0, value)
        return len(self._lists[name])

    async def rpush(self, name: str, *values: Any) -> int:
        if name not in self._lists:
            self._lists[name] = []
        self._lists[name].extend(values)
        return len(self._lists[name])

    async def lpop(self, name: str, count: int | None = None) -> Any:
        if name not in self._lists or not self._lists[name]:
            return None
        if count:
            result = self._lists[name][:count]
            self._lists[name] = self._lists[name][count:]
            return result
        return self._lists[name].pop(0)

    async def lrange(self, name: str, start: int, end: int) -> list:
        if name not in self._lists:
            return []
        if end == -1:
            return self._lists[name][start:]
        return self._lists[name][start : end + 1]

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self._data.clear()
        self._hashes.clear()
        self._lists.clear()
        self._ttls.clear()

    def clear(self) -> None:
        """Clear all stored data (useful between tests)."""
        self._data.clear()
        self._hashes.clear()
        self._lists.clear()
        self._ttls.clear()


@pytest.fixture
def mock_redis() -> MockRedis:
    """Create a mock Redis client."""
    return MockRedis()


@pytest.fixture
def mock_redis_manager(mock_redis: MockRedis) -> Generator[RedisManager, None, None]:
    """Mock the global Redis manager for testing."""
    from app.core.redis import redis_manager

    # Store original state
    original_pool = redis_manager._pool
    original_client = redis_manager._client
    original_circuit = redis_manager._circuit_breaker
    original_available = redis_manager._available

    # Create mock circuit breaker
    circuit_config = CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
    )

    # Set mock state
    redis_manager._pool = MagicMock()
    redis_manager._client = mock_redis  # type: ignore[assignment]
    redis_manager._circuit_breaker = CircuitBreaker(circuit_config)
    redis_manager._available = True

    yield redis_manager

    # Restore original state
    redis_manager._pool = original_pool
    redis_manager._client = original_client
    redis_manager._circuit_breaker = original_circuit
    redis_manager._available = original_available


@pytest.fixture
def mock_redis_unavailable() -> Generator[RedisManager, None, None]:
    """Mock Redis manager in unavailable state (for testing graceful degradation)."""
    from app.core.redis import redis_manager

    # Store original state
    original_pool = redis_manager._pool
    original_client = redis_manager._client
    original_circuit = redis_manager._circuit_breaker
    original_available = redis_manager._available

    # Set unavailable state
    redis_manager._pool = None
    redis_manager._client = None
    redis_manager._circuit_breaker = None
    redis_manager._available = False

    yield redis_manager

    # Restore original state
    redis_manager._pool = original_pool
    redis_manager._client = original_client
    redis_manager._circuit_breaker = original_circuit
    redis_manager._available = original_available


# ---------------------------------------------------------------------------
# FastAPI Test Client Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create FastAPI app for testing."""
    from app.main import create_app

    return create_app()


@pytest.fixture
def client(
    app,
    mock_db_manager: DatabaseManager,
    mock_redis_manager: RedisManager,
) -> Generator[TestClient, None, None]:
    """Create synchronous test client with mocked dependencies."""
    # Override settings
    app.dependency_overrides[get_settings] = get_test_settings

    # Use Starlette TestClient (handles ASGI app internally)
    test_client = TestClient(app)
    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(
    app,
    mock_db_manager: DatabaseManager,
    mock_redis_manager: RedisManager,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client for testing async endpoints."""
    # Override settings
    app.dependency_overrides[get_settings] = get_test_settings

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Utility Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_logger() -> Generator[MagicMock, None, None]:
    """Mock the logger for testing log output."""
    with patch("app.core.logging.get_logger") as mock:
        mock_logger_instance = MagicMock()
        mock.return_value = mock_logger_instance
        yield mock_logger_instance


@pytest.fixture
def freeze_time():
    """Fixture for freezing time in tests.

    Usage:
        def test_something(freeze_time):
            with freeze_time("2024-01-15 12:00:00"):
                # time is frozen
                ...
    """
    import time as time_module
    from contextlib import contextmanager
    from datetime import datetime
    from unittest.mock import patch

    @contextmanager
    def _freeze_time(time_str: str):
        frozen_time = datetime.fromisoformat(time_str)
        frozen_timestamp = frozen_time.timestamp()

        with (
            patch.object(time_module, "time", return_value=frozen_timestamp),
            patch.object(time_module, "monotonic", return_value=frozen_timestamp),
        ):
            yield frozen_time

    return _freeze_time
