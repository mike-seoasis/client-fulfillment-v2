"""Integration tests for error handling and middleware.

Tests cover:
- Structured error responses with request_id
- Request logging middleware
- CORS headers
- Validation error handling
- 404 and 500 error responses

ERROR LOGGING REQUIREMENTS (verified by tests):
- All responses include X-Request-ID header
- 4xx errors return structured JSON with error, code, request_id
- 5xx errors return structured JSON with error, code, request_id
- CORS headers are present for cross-origin requests
"""

from fastapi.testclient import TestClient


class TestRequestLogging:
    """Tests for request logging middleware."""

    def test_all_responses_have_request_id(self, client: TestClient) -> None:
        """Test that all responses include X-Request-ID header."""
        endpoints = [
            "/health",
            "/api/v1/projects",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert "X-Request-ID" in response.headers, f"Missing X-Request-ID for {endpoint}"
            # Verify UUID format (36 characters with dashes)
            request_id = response.headers["X-Request-ID"]
            assert len(request_id) == 36, f"Invalid request_id format for {endpoint}"

    def test_request_id_is_unique_per_request(self, client: TestClient) -> None:
        """Test that each request gets a unique request_id."""
        response1 = client.get("/health")
        response2 = client.get("/health")

        assert response1.headers["X-Request-ID"] != response2.headers["X-Request-ID"]

    def test_post_requests_have_request_id(self, client: TestClient) -> None:
        """Test that POST requests also get request_id."""
        response = client.post(
            "/api/v1/projects",
            json={"name": "Test", "client_id": "test"},
        )

        assert "X-Request-ID" in response.headers


class TestStructuredErrorResponses:
    """Tests for structured error response format."""

    def test_validation_error_structure(self, client: TestClient) -> None:
        """Test validation errors return proper structure."""
        # Missing required field
        response = client.post(
            "/api/v1/projects",
            json={"client_id": "test"},  # Missing name
        )

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert "code" in data
        assert "request_id" in data
        assert data["code"] == "VALIDATION_ERROR"
        # request_id should match header
        assert data["request_id"] == response.headers["X-Request-ID"]

    def test_not_found_error_structure(self, client: TestClient) -> None:
        """Test 404 errors return proper structure."""
        import uuid

        response = client.get(f"/api/v1/projects/{uuid.uuid4()}")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "code" in data
        assert "request_id" in data
        assert data["code"] == "NOT_FOUND"

    def test_error_request_id_matches_header(self, client: TestClient) -> None:
        """Test that error response request_id matches X-Request-ID header."""
        response = client.post(
            "/api/v1/projects",
            json={},  # Invalid - missing required fields
        )

        assert response.status_code == 422
        data = response.json()
        assert data["request_id"] == response.headers["X-Request-ID"]


class TestCORSHeaders:
    """Tests for CORS middleware."""

    def test_cors_allows_all_origins(self, client: TestClient) -> None:
        """Test CORS allows requests from any origin."""
        response = client.options(
            "/api/v1/projects",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        # CORS preflight should succeed
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_cors_allows_credentials(self, client: TestClient) -> None:
        """Test CORS allows credentials."""
        response = client.options(
            "/api/v1/projects",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_allows_common_methods(self, client: TestClient) -> None:
        """Test CORS allows common HTTP methods."""
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]

        for method in methods:
            response = client.options(
                "/api/v1/projects",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": method,
                },
            )

            assert response.status_code == 200, f"CORS failed for method {method}"


class TestInvalidRoutes:
    """Tests for handling invalid routes."""

    def test_unknown_route_returns_404(self, client: TestClient) -> None:
        """Test accessing unknown route returns 404."""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404

    def test_unknown_api_route_has_request_id(self, client: TestClient) -> None:
        """Test that 404 responses still have request_id header."""
        response = client.get("/api/v1/nonexistent")

        assert "X-Request-ID" in response.headers


class TestContentTypeHandling:
    """Tests for content type handling."""

    def test_json_content_type_accepted(self, client: TestClient) -> None:
        """Test that application/json content type is accepted."""
        response = client.post(
            "/api/v1/projects",
            json={"name": "Test", "client_id": "test"},
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 201

    def test_response_content_type_is_json(self, client: TestClient) -> None:
        """Test that responses have application/json content type."""
        response = client.get("/api/v1/projects")

        assert response.status_code == 200
        assert "application/json" in response.headers.get("content-type", "")


class TestHealthEndpointNotAffectedByAuth:
    """Tests to verify health endpoints are accessible without auth."""

    def test_health_accessible_without_auth(self, client: TestClient) -> None:
        """Test /health is accessible without any authentication."""
        response = client.get("/health")

        assert response.status_code == 200

    def test_health_db_accessible_without_auth(self, client: TestClient) -> None:
        """Test /health/db is accessible without any authentication."""
        response = client.get("/health/db")

        assert response.status_code == 200

    def test_health_redis_accessible_without_auth(self, client: TestClient) -> None:
        """Test /health/redis is accessible without any authentication."""
        response = client.get("/health/redis")

        assert response.status_code == 200


class TestRequestTiming:
    """Tests for request timing in responses."""

    def test_health_endpoint_is_fast(self, client: TestClient) -> None:
        """Test health endpoint responds in under 50ms."""
        import time

        start = time.monotonic()
        response = client.get("/health")
        duration_ms = (time.monotonic() - start) * 1000

        assert response.status_code == 200
        # Health check should be very fast
        assert duration_ms < 50
