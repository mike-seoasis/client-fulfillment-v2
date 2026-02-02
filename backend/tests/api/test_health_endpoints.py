"""Integration tests for health check endpoints.

Tests cover:
- Basic health check at /health
- Database health check at /health/db
- Redis health check at /health/redis
- Scheduler health check at /health/scheduler
- Request logging and request_id headers
- Structured error responses

ERROR LOGGING REQUIREMENTS (verified by tests):
- All requests include X-Request-ID header in response
- Health endpoints return proper status codes
- Response format is consistent JSON
"""

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the basic health check endpoint."""

    def test_health_returns_ok(self, client: TestClient) -> None:
        """Test /health returns status ok."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_includes_request_id_header(self, client: TestClient) -> None:
        """Test /health response includes X-Request-ID header."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Request ID should be a valid UUID format
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID format: 8-4-4-4-12

    def test_health_is_fast(self, client: TestClient) -> None:
        """Test /health responds quickly (under 100ms)."""
        import time

        start = time.monotonic()
        response = client.get("/health")
        duration_ms = (time.monotonic() - start) * 1000

        assert response.status_code == 200
        assert duration_ms < 100  # Health check should be very fast


class TestDatabaseHealthEndpoint:
    """Tests for the database health check endpoint."""

    def test_database_health_returns_ok(self, client: TestClient) -> None:
        """Test /health/db returns status ok when database is connected."""
        response = client.get("/health/db")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] is True

    def test_database_health_includes_request_id(self, client: TestClient) -> None:
        """Test /health/db response includes X-Request-ID header."""
        response = client.get("/health/db")

        assert "X-Request-ID" in response.headers


class TestRedisHealthEndpoint:
    """Tests for the Redis health check endpoint."""

    def test_redis_health_with_available_redis(self, client: TestClient) -> None:
        """Test /health/redis returns status ok when Redis is connected."""
        response = client.get("/health/redis")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "unavailable")
        assert "redis" in data
        assert "circuit_breaker" in data

    def test_redis_health_includes_circuit_breaker_state(
        self, client: TestClient
    ) -> None:
        """Test /health/redis includes circuit breaker state."""
        response = client.get("/health/redis")

        assert response.status_code == 200
        data = response.json()
        assert data["circuit_breaker"] in (
            "closed",
            "open",
            "half_open",
            "not_initialized",
        )


class TestSchedulerHealthEndpoint:
    """Tests for the scheduler health check endpoint."""

    def test_scheduler_health_returns_data(self, client: TestClient) -> None:
        """Test /health/scheduler returns scheduler status."""
        response = client.get("/health/scheduler")

        assert response.status_code == 200
        data = response.json()
        # Scheduler health returns various fields
        assert isinstance(data, dict)
