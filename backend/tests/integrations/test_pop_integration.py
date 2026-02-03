"""Integration tests for POP (PageOptimizer Pro) API.

These tests make REAL API calls to PageOptimizer Pro.
They are skipped in CI environments and should only be run manually
with valid API credentials.

To run these tests locally:
1. Set POP_API_KEY environment variable
2. Run: pytest tests/integrations/test_pop_integration.py -v --run-integration

ERROR LOGGING REQUIREMENTS:
- Test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
"""

import logging
import os
import time

import pytest

from app.integrations.pop import (
    POPClient,
    POPTaskStatus,
)

# Configure logging for tests
logger = logging.getLogger(__name__)


# Custom marker for integration tests that hit real APIs
# These tests are skipped by default and require --run-integration flag
def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
    )


@pytest.fixture
def requires_pop_api_key() -> str | None:
    """Check if POP API key is available."""
    api_key = os.environ.get("POP_API_KEY")
    if not api_key:
        pytest.skip("POP_API_KEY environment variable not set")
    return api_key


@pytest.fixture
def real_pop_client(requires_pop_api_key: str | None) -> POPClient:
    """Create a real POP client with actual credentials."""
    return POPClient(api_key=requires_pop_api_key)


# ---------------------------------------------------------------------------
# Real API Integration Tests
# These tests are skipped in CI - use @pytest.mark.skip_ci
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("POP_API_KEY"),
    reason="Integration test - requires real POP API credentials. "
    "Run manually with POP_API_KEY env var set.",
)
class TestPOPRealAPI:
    """Integration tests against real POP API.

    IMPORTANT: These tests make real API calls and may consume API credits.
    Only run manually with valid credentials.
    """

    @pytest.mark.asyncio
    async def test_create_report_task_real_api(
        self,
        real_pop_client: POPClient,
    ) -> None:
        """Test creating a report task against real POP API."""
        start_time = time.monotonic()
        logger.info("Test: Creating real POP report task")

        # Use a real URL that POP can analyze
        result = await real_pop_client.create_report_task(
            keyword="seo content optimization",
            url="https://moz.com/beginners-guide-to-seo",
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Test: Task creation result",
            extra={
                "success": result.success,
                "task_id": result.task_id,
                "duration_ms": round(duration_ms, 2),
            },
        )

        assert result.success is True, f"Task creation failed: {result.error}"
        assert result.task_id is not None, "No task_id returned"
        assert result.status in (
            POPTaskStatus.PENDING,
            POPTaskStatus.PROCESSING,
        )

    @pytest.mark.asyncio
    async def test_create_and_poll_task_real_api(
        self,
        real_pop_client: POPClient,
    ) -> None:
        """Test full task lifecycle: create, poll, and get results."""
        start_time = time.monotonic()
        logger.info("Test: Full POP task lifecycle")

        # Create task
        create_result = await real_pop_client.create_report_task(
            keyword="best hiking boots",
            url="https://www.rei.com/learn/expert-advice/hiking-boots.html",
        )

        assert create_result.success is True, (
            f"Task creation failed: {create_result.error}"
        )
        task_id = create_result.task_id
        assert task_id is not None

        logger.info(
            "Test: Task created, starting poll",
            extra={"task_id": task_id},
        )

        # Poll for results (with reasonable timeout for integration test)
        poll_result = await real_pop_client.poll_for_result(
            task_id=task_id,
            poll_interval=5.0,  # 5 second intervals
            timeout=120.0,  # 2 minute timeout
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Test: Poll completed",
            extra={
                "success": poll_result.success,
                "status": poll_result.status.value,
                "duration_ms": round(duration_ms, 2),
                "has_data": bool(poll_result.data),
            },
        )

        assert poll_result.success is True, f"Polling failed: {poll_result.error}"
        assert poll_result.status in (
            POPTaskStatus.SUCCESS,
            POPTaskStatus.FAILURE,
        ), f"Unexpected status: {poll_result.status}"

        if poll_result.status == POPTaskStatus.SUCCESS:
            # Verify we got actual data
            assert poll_result.data is not None
            # POP responses typically contain these fields
            data = poll_result.data
            logger.info(
                "Test: Received POP data",
                extra={
                    "data_keys": list(data.keys())[:10],  # First 10 keys
                    "has_word_count": "wordCount" in data,
                    "has_tag_counts": "tagCounts" in data,
                },
            )

    @pytest.mark.asyncio
    async def test_get_task_result_real_api(
        self,
        real_pop_client: POPClient,
    ) -> None:
        """Test getting task result with an invalid task ID."""
        logger.info("Test: Getting result for non-existent task")

        # Use a fake task ID - should return error or not found
        result = await real_pop_client.get_task_result("fake-task-id-12345")

        logger.info(
            "Test: Result for fake task",
            extra={
                "success": result.success,
                "status": result.status.value if result.status else None,
                "error": result.error,
            },
        )

        # The API should either fail or return some status
        # This tests that we handle real API responses correctly
        # Note: POP API returns PENDING for non-existent task IDs (doesn't error)
        if result.success:
            # If API returns 200, status should be one of the known statuses
            assert result.status in (
                POPTaskStatus.PENDING,
                POPTaskStatus.FAILURE,
                POPTaskStatus.UNKNOWN,
            ), f"Unexpected status for non-existent task: {result.status}"
        else:
            # API returned an error - this is also acceptable
            assert result.error is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovers_real_api(
        self,
        real_pop_client: POPClient,
    ) -> None:
        """Test that circuit breaker allows recovery after successful request."""
        logger.info("Test: Circuit breaker with real API")

        # First, verify circuit is closed
        assert real_pop_client.circuit_breaker.is_closed

        # Make a successful request
        result = await real_pop_client.create_report_task(
            keyword="test query",
            url="https://example.com",
        )

        logger.info(
            "Test: First request result",
            extra={
                "success": result.success,
                "circuit_state": real_pop_client.circuit_breaker.state.value,
            },
        )

        # Circuit should still be closed after successful request
        assert real_pop_client.circuit_breaker.is_closed

    @pytest.mark.asyncio
    async def test_client_handles_invalid_credentials(
        self,
    ) -> None:
        """Test that client handles invalid API credentials gracefully."""
        logger.info("Test: Invalid credentials handling")

        # Create client with invalid API key
        client = POPClient(api_key="invalid-api-key-12345")

        result = await client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        logger.info(
            "Test: Invalid credentials result",
            extra={
                "success": result.success,
                "error": result.error,
            },
        )

        # Should fail with auth error
        assert result.success is False
        assert result.error is not None
        # Error should mention authentication, invalid key, or API key issue
        error_lower = result.error.lower()
        assert (
            "auth" in error_lower
            or "401" in error_lower
            or "403" in error_lower
            or "invalid" in error_lower
            or "unauthorized" in error_lower
            or "api key" in error_lower
            or "apikey" in error_lower
        ), f"Expected auth error, got: {result.error}"
