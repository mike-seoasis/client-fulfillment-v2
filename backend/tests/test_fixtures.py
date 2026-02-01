"""Tests to verify pytest fixtures work correctly."""

import pytest
from sqlalchemy import text


class TestDatabaseFixtures:
    """Tests for database fixtures."""

    @pytest.mark.asyncio
    async def test_db_session_creates_session(self, db_session):
        """Verify db_session fixture provides a working session."""
        result = await db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_db_session_rollback_between_tests_1(self, db_session):
        """First test to verify session isolation."""
        # Create a table in this test
        await db_session.execute(
            text("CREATE TABLE IF NOT EXISTS test_isolation (id INTEGER PRIMARY KEY)")
        )
        await db_session.execute(text("INSERT INTO test_isolation (id) VALUES (1)"))
        result = await db_session.execute(text("SELECT COUNT(*) FROM test_isolation"))
        count = result.scalar()
        # Should have 1 row
        assert count == 1

    @pytest.mark.asyncio
    async def test_mock_db_manager(self, mock_db_manager):
        """Verify mock_db_manager provides access to test database."""
        from app.core.database import db_manager

        # Should be the same instance
        assert db_manager is mock_db_manager
        # Engine should be available
        assert db_manager._engine is not None


class TestRedisFixtures:
    """Tests for Redis fixtures."""

    @pytest.mark.asyncio
    async def test_mock_redis_set_get(self, mock_redis):
        """Verify mock Redis supports set/get operations."""
        await mock_redis.set("test_key", "test_value")
        result = await mock_redis.get("test_key")
        assert result == b"test_value"

    @pytest.mark.asyncio
    async def test_mock_redis_incr_decr(self, mock_redis):
        """Verify mock Redis supports incr/decr operations."""
        # Incr creates key if not exists
        result = await mock_redis.incr("counter")
        assert result == 1
        result = await mock_redis.incr("counter")
        assert result == 2
        result = await mock_redis.decr("counter")
        assert result == 1

    @pytest.mark.asyncio
    async def test_mock_redis_hash_operations(self, mock_redis):
        """Verify mock Redis supports hash operations."""
        await mock_redis.hset("user:1", "name", "Alice")
        await mock_redis.hset("user:1", mapping={"age": "30", "city": "NYC"})

        name = await mock_redis.hget("user:1", "name")
        assert name == b"Alice"

        all_data = await mock_redis.hgetall("user:1")
        assert "name" in all_data
        assert "age" in all_data

    @pytest.mark.asyncio
    async def test_mock_redis_list_operations(self, mock_redis):
        """Verify mock Redis supports list operations."""
        await mock_redis.lpush("queue", "first", "second")
        await mock_redis.rpush("queue", "third")

        items = await mock_redis.lrange("queue", 0, -1)
        assert len(items) == 3
        # lpush adds to front in reverse order
        assert items[0] == "second"
        assert items[2] == "third"

    @pytest.mark.asyncio
    async def test_mock_redis_manager(self, mock_redis_manager):
        """Verify mock_redis_manager is configured correctly."""
        from app.core.redis import redis_manager

        assert redis_manager is mock_redis_manager
        assert redis_manager.available is True
        assert redis_manager.circuit_breaker is not None

    @pytest.mark.asyncio
    async def test_mock_redis_unavailable(self, mock_redis_unavailable):
        """Verify mock_redis_unavailable simulates Redis being down."""
        from app.core.redis import redis_manager

        assert redis_manager.available is False
        assert redis_manager._client is None


class TestClientFixtures:
    """Tests for FastAPI client fixtures."""

    def test_sync_client_health_check(self, client):
        """Verify sync test client works with health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_async_client_health_check(self, async_client):
        """Verify async test client works with health endpoint."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestSettingsFixtures:
    """Tests for settings fixtures."""

    def test_test_settings(self, test_settings):
        """Verify test settings are configured correctly."""
        assert test_settings.environment == "test"
        assert test_settings.debug is True
        assert test_settings.app_name == "Test App"
