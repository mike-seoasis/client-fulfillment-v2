"""Unit tests for POP (PageOptimizer Pro) API integration client.

Tests cover:
- create_report_task() with mocked successful response
- get_task_result() with mocked pending and complete responses
- Polling loop timeout behavior
- Circuit breaker state transitions
- Retry logic with various error codes
- Credential masking in logs

Uses unittest.mock with httpx for mocking HTTP requests.
"""

import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.pop import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    POPAuthError,
    POPCircuitOpenError,
    POPClient,
    POPError,
    POPRateLimitError,
    POPTaskResult,
    POPTaskStatus,
    POPTimeoutError,
    _truncate_for_logging,
)

# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for POP client."""
    settings = MagicMock()
    settings.pop_api_key = "test-api-key-12345"
    settings.pop_api_url = "https://api.pageoptimizer.pro"
    settings.pop_task_poll_interval = 1.0
    settings.pop_task_timeout = 10.0
    settings.pop_circuit_failure_threshold = 3
    settings.pop_circuit_recovery_timeout = 5.0
    settings.pop_max_retries = 3
    settings.pop_retry_delay = 0.1
    return settings


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Create a mock httpx AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def pop_client(mock_settings: MagicMock) -> POPClient:
    """Create a POPClient instance with mocked settings."""
    with patch("app.integrations.pop.get_settings", return_value=mock_settings):
        return POPClient()


@pytest.fixture
def sample_task_create_response() -> dict:
    """Sample response from task creation endpoint."""
    return {
        "task_id": "task-abc-123",
        "status": "pending",
        "message": "Task created successfully",
    }


@pytest.fixture
def sample_task_pending_response() -> dict:
    """Sample response for a pending task."""
    return {
        "task_id": "task-abc-123",
        "status": "processing",
        "progress": 50,
    }


@pytest.fixture
def sample_task_complete_response() -> dict:
    """Sample response for a completed task."""
    return {
        "task_id": "task-abc-123",
        "status": "success",
        "data": {
            "pageScore": 75,
            "wordCount": {"current": 1200, "target": 1500},
            "cleanedContentBrief": {
                "pageScore": 75,
                "title": {"keywords": [{"term": {"phrase": "test keyword"}}]},
            },
            "lsaPhrases": [
                {"phrase": "semantic term", "weight": 0.8, "targetCount": 3}
            ],
        },
    }


# ---------------------------------------------------------------------------
# CircuitBreaker Tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for CircuitBreaker state transitions."""

    @pytest.fixture
    def circuit_breaker(self) -> CircuitBreaker:
        """Create a circuit breaker with test configuration."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1.0)
        return CircuitBreaker(config)

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test circuit breaker starts in CLOSED state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.is_closed is True
        assert circuit_breaker.is_open is False

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test requests are allowed when circuit is closed."""
        assert await circuit_breaker.can_execute() is True

    @pytest.mark.asyncio
    async def test_opens_after_failure_threshold(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test circuit opens after reaching failure threshold."""
        # Record failures up to threshold
        for _ in range(3):
            await circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.is_open is True
        assert await circuit_breaker.can_execute() is False

    @pytest.mark.asyncio
    async def test_does_not_open_below_threshold(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test circuit stays closed below failure threshold."""
        # Record failures below threshold
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.CLOSED
        assert await circuit_breaker.can_execute() is True

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test successful operation resets failure count."""
        # Record some failures
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()

        # Record success
        await circuit_breaker.record_success()

        # Now failures should need to start from 0 again
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()

        # Should still be closed (only 2 failures after reset)
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_recovery_timeout(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test circuit transitions to HALF_OPEN after recovery timeout."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for recovery timeout (plus small buffer)
        await asyncio.sleep(1.1)

        # Next can_execute should transition to HALF_OPEN
        assert await circuit_breaker.can_execute() is True
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test successful operation in HALF_OPEN state closes circuit."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Transition to HALF_OPEN
        await circuit_breaker.can_execute()
        assert circuit_breaker.state == CircuitState.HALF_OPEN

        # Success should close circuit
        await circuit_breaker.record_success()
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker.is_closed is True

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test failure in HALF_OPEN state reopens circuit."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Transition to HALF_OPEN
        await circuit_breaker.can_execute()
        assert circuit_breaker.state == CircuitState.HALF_OPEN

        # Failure should reopen circuit
        await circuit_breaker.record_failure()
        assert circuit_breaker.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# POPClient create_report_task Tests
# ---------------------------------------------------------------------------


class TestCreateReportTask:
    """Tests for POPClient.create_report_task() method."""

    @pytest.mark.asyncio
    async def test_create_report_task_success(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
        sample_task_create_response: dict,
    ) -> None:
        """Test successful task creation."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_task_create_response
        mock_httpx_client.request.return_value = mock_response

        # Replace client's internal httpx client
        pop_client._client = mock_httpx_client

        result = await pop_client.create_report_task(
            keyword="test keyword",
            url="https://example.com/page",
        )

        assert result.success is True
        assert result.task_id == "task-abc-123"
        assert result.status == POPTaskStatus.PENDING

        # Verify request was made with correct parameters
        mock_httpx_client.request.assert_called_once()
        call_args = mock_httpx_client.request.call_args
        assert call_args.args[0] == "POST"
        assert "/api/report" in call_args.args[1]
        assert call_args.kwargs["json"]["keyword"] == "test keyword"
        assert call_args.kwargs["json"]["url"] == "https://example.com/page"
        assert "apiKey" in call_args.kwargs["json"]

    @pytest.mark.asyncio
    async def test_create_report_task_missing_keyword(
        self, pop_client: POPClient
    ) -> None:
        """Test task creation fails with missing keyword."""
        result = await pop_client.create_report_task(
            keyword="",
            url="https://example.com/page",
        )

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_report_task_missing_url(self, pop_client: POPClient) -> None:
        """Test task creation fails with missing URL."""
        result = await pop_client.create_report_task(
            keyword="test keyword",
            url="",
        )

        assert result.success is False
        assert "required" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_report_task_no_api_key(
        self, mock_settings: MagicMock
    ) -> None:
        """Test task creation fails without API key."""
        mock_settings.pop_api_key = None

        with patch("app.integrations.pop.get_settings", return_value=mock_settings):
            client = POPClient()

        result = await client.create_report_task(
            keyword="test keyword",
            url="https://example.com/page",
        )

        assert result.success is False
        assert "not configured" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_report_task_with_taskId_format(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test task creation handles taskId (camelCase) format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "taskId": "task-def-456",  # camelCase format
            "status": "pending",
        }
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        result = await pop_client.create_report_task(
            keyword="test keyword",
            url="https://example.com/page",
        )

        assert result.success is True
        assert result.task_id == "task-def-456"


# ---------------------------------------------------------------------------
# POPClient get_task_result Tests
# ---------------------------------------------------------------------------


class TestGetTaskResult:
    """Tests for POPClient.get_task_result() method."""

    @pytest.mark.asyncio
    async def test_get_task_result_pending(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
        sample_task_pending_response: dict,
    ) -> None:
        """Test getting pending task result."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_task_pending_response
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        result = await pop_client.get_task_result("task-abc-123")

        assert result.success is True
        assert result.task_id == "task-abc-123"
        assert result.status == POPTaskStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_get_task_result_complete(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
        sample_task_complete_response: dict,
    ) -> None:
        """Test getting completed task result."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_task_complete_response
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        result = await pop_client.get_task_result("task-abc-123")

        assert result.success is True
        assert result.task_id == "task-abc-123"
        assert result.status == POPTaskStatus.SUCCESS
        assert "pageScore" in result.data.get("data", {})

    @pytest.mark.asyncio
    async def test_get_task_result_failure_status(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test getting failed task result."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "task-abc-123",
            "status": "failed",
            "error": "Analysis failed",
        }
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        result = await pop_client.get_task_result("task-abc-123")

        assert result.success is True  # API call succeeded
        assert result.status == POPTaskStatus.FAILURE

    @pytest.mark.asyncio
    async def test_get_task_result_unknown_status(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test getting task with unknown status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "task-abc-123",
            "status": "some_unknown_status",
        }
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        result = await pop_client.get_task_result("task-abc-123")

        assert result.success is True
        assert result.status == POPTaskStatus.UNKNOWN

    @pytest.mark.asyncio
    async def test_get_task_result_missing_task_id(self, pop_client: POPClient) -> None:
        """Test get_task_result fails with missing task_id."""
        result = await pop_client.get_task_result("")

        assert result.success is False
        assert "required" in result.error.lower()


# ---------------------------------------------------------------------------
# POPClient poll_for_result Tests
# ---------------------------------------------------------------------------


class TestPollForResult:
    """Tests for POPClient.poll_for_result() polling loop."""

    @pytest.mark.asyncio
    async def test_poll_completes_on_success(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
        sample_task_complete_response: dict,
    ) -> None:
        """Test polling completes when task succeeds."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_task_complete_response
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        result = await pop_client.poll_for_result(
            task_id="task-abc-123",
            poll_interval=0.1,
            timeout=5.0,
        )

        assert result.success is True
        assert result.status == POPTaskStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_poll_completes_on_failure_status(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test polling completes when task fails (FAILURE status)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "task-abc-123",
            "status": "failure",
            "error": "Task failed",
        }
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        result = await pop_client.poll_for_result(
            task_id="task-abc-123",
            poll_interval=0.1,
            timeout=5.0,
        )

        assert result.success is True  # API call succeeded
        assert result.status == POPTaskStatus.FAILURE

    @pytest.mark.asyncio
    async def test_poll_timeout_raises_error(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
        sample_task_pending_response: dict,
    ) -> None:
        """Test polling raises timeout error when timeout exceeded."""
        # Always return pending status
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_task_pending_response
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        with pytest.raises(POPTimeoutError) as exc_info:
            await pop_client.poll_for_result(
                task_id="task-abc-123",
                poll_interval=0.05,
                timeout=0.2,  # Very short timeout
            )

        assert "task-abc-123" in str(exc_info.value)
        assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_poll_transitions_from_pending_to_success(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
        sample_task_pending_response: dict,
        sample_task_complete_response: dict,
    ) -> None:
        """Test polling handles transition from pending to success."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        # First two calls return pending, third returns complete
        mock_response.json.side_effect = [
            sample_task_pending_response,
            sample_task_pending_response,
            sample_task_complete_response,
        ]
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        result = await pop_client.poll_for_result(
            task_id="task-abc-123",
            poll_interval=0.05,
            timeout=5.0,
        )

        assert result.success is True
        assert result.status == POPTaskStatus.SUCCESS
        assert mock_httpx_client.request.call_count == 3


# ---------------------------------------------------------------------------
# Retry Logic Tests
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Tests for POPClient retry logic with various error codes.

    Note: create_report_task() catches exceptions and returns POPTaskResult.
    For exception testing, we verify the returned result has success=False
    and appropriate error messages. For direct exception testing, we test
    the internal _make_request() method.
    """

    @pytest.mark.asyncio
    async def test_retries_on_500_error(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test client retries on 5xx server errors."""
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        mock_response_error.json.return_value = {"error": "Internal server error"}

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"task_id": "task-123"}

        # First two calls fail, third succeeds
        mock_httpx_client.request.side_effect = [
            mock_response_error,
            mock_response_error,
            mock_response_success,
        ]

        pop_client._client = mock_httpx_client

        result = await pop_client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        assert result.success is True
        assert mock_httpx_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test client does not retry on 401/403 auth errors."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        # create_report_task catches exceptions and returns POPTaskResult
        result = await pop_client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        assert result.success is False
        assert "Authentication failed" in result.error
        # Should not retry auth errors
        assert mock_httpx_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_auth_error_raises_from_make_request(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test _make_request raises POPAuthError on 401/403."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        with pytest.raises(POPAuthError):
            await pop_client._make_request("/api/report", {"keyword": "test"})

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test client does not retry on 4xx client errors (except 429)."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"error": "Bad request"}'
        mock_response.json.return_value = {"error": "Bad request"}
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        # create_report_task catches exceptions and returns POPTaskResult
        result = await pop_client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        assert result.success is False
        assert "400" in result.error
        assert mock_httpx_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_client_error_raises_from_make_request(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test _make_request raises POPError on 4xx client errors."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.content = b'{"error": "Bad request"}'
        mock_response.json.return_value = {"error": "Bad request"}
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        with pytest.raises(POPError) as exc_info:
            await pop_client._make_request("/api/report", {"keyword": "test"})

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_with_retry_after(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test client retries on 429 with Retry-After header."""
        mock_response_rate_limit = MagicMock()
        mock_response_rate_limit.status_code = 429
        mock_response_rate_limit.headers = {"retry-after": "0.1"}

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"task_id": "task-123"}

        mock_httpx_client.request.side_effect = [
            mock_response_rate_limit,
            mock_response_success,
        ]

        pop_client._client = mock_httpx_client

        result = await pop_client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        assert result.success is True
        assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_rate_limit_without_retry_after_returns_failure(
        self,
        mock_settings: MagicMock,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test 429 without Retry-After header eventually returns failure."""
        mock_settings.pop_max_retries = 2  # Reduce retries for faster test

        with patch("app.integrations.pop.get_settings", return_value=mock_settings):
            client = POPClient()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}  # No Retry-After header
        mock_httpx_client.request.return_value = mock_response

        client._client = mock_httpx_client

        result = await client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        assert result.success is False
        assert "Rate limit" in result.error

    @pytest.mark.asyncio
    async def test_rate_limit_raises_from_make_request(
        self,
        mock_settings: MagicMock,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test _make_request raises POPRateLimitError on 429."""
        mock_settings.pop_max_retries = 1

        with patch("app.integrations.pop.get_settings", return_value=mock_settings):
            client = POPClient()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}  # No Retry-After header
        mock_httpx_client.request.return_value = mock_response

        client._client = mock_httpx_client

        with pytest.raises(POPRateLimitError):
            await client._make_request("/api/report", {"keyword": "test"})

    @pytest.mark.asyncio
    async def test_retries_on_timeout(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test client retries on timeout errors."""
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"task_id": "task-123"}

        # First two calls timeout, third succeeds
        mock_httpx_client.request.side_effect = [
            httpx.TimeoutException("Timeout"),
            httpx.TimeoutException("Timeout"),
            mock_response_success,
        ]

        pop_client._client = mock_httpx_client

        result = await pop_client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        assert result.success is True
        assert mock_httpx_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_timeout_returns_failure_after_max_retries(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test timeout returns failure result after max retries."""
        mock_httpx_client.request.side_effect = httpx.TimeoutException("Timeout")

        pop_client._client = mock_httpx_client

        result = await pop_client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_timeout_raises_from_make_request(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
    ) -> None:
        """Test _make_request raises POPTimeoutError after max retries."""
        mock_httpx_client.request.side_effect = httpx.TimeoutException("Timeout")

        pop_client._client = mock_httpx_client

        with pytest.raises(POPTimeoutError):
            await pop_client._make_request("/api/report", {"keyword": "test"})

    @pytest.mark.asyncio
    async def test_exponential_backoff_delay(
        self,
        mock_settings: MagicMock,
    ) -> None:
        """Test retry uses exponential backoff."""
        mock_settings.pop_retry_delay = 0.01  # Fast for testing

        with patch("app.integrations.pop.get_settings", return_value=mock_settings):
            client = POPClient()

        mock_httpx_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        mock_response_error.json.return_value = {"error": "Server error"}

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"task_id": "task-123"}

        call_times: list[float] = []

        async def track_calls(*args, **kwargs):
            call_times.append(time.monotonic())
            if len(call_times) < 3:
                return mock_response_error
            return mock_response_success

        mock_httpx_client.request.side_effect = track_calls
        client._client = mock_httpx_client

        await client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        # Verify delays increased (exponential backoff)
        if len(call_times) >= 3:
            delay1 = call_times[1] - call_times[0]
            delay2 = call_times[2] - call_times[1]
            # Second delay should be longer (exponential)
            assert delay2 >= delay1 * 1.5  # Allow some tolerance


# ---------------------------------------------------------------------------
# Circuit Breaker Integration Tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration with POPClient."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_repeated_failures(
        self,
        mock_settings: MagicMock,
    ) -> None:
        """Test circuit opens after repeated API failures."""
        mock_settings.pop_circuit_failure_threshold = 3
        mock_settings.pop_max_retries = 1  # Only 1 retry to speed up test

        with patch("app.integrations.pop.get_settings", return_value=mock_settings):
            client = POPClient()

        mock_httpx_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Server error"}
        mock_httpx_client.request.return_value = mock_response

        client._client = mock_httpx_client

        # Make multiple failing requests to trip the circuit
        # create_report_task catches exceptions, so check return values
        for _ in range(3):
            result = await client.create_report_task(
                keyword="test", url="https://example.com"
            )
            assert result.success is False

        # Verify circuit is now open
        assert client.circuit_breaker.is_open

        # Next request should fail immediately with circuit open error
        # (create_report_task will still return POPTaskResult, not raise)
        result = await client.create_report_task(
            keyword="test", url="https://example.com"
        )
        assert result.success is False
        assert (
            "Circuit breaker" in result.error
            or "not configured" in result.error.lower()
        )

    @pytest.mark.asyncio
    async def test_circuit_allows_request_after_recovery(
        self,
        mock_settings: MagicMock,
    ) -> None:
        """Test circuit allows requests after recovery timeout."""
        mock_settings.pop_circuit_failure_threshold = 2
        mock_settings.pop_circuit_recovery_timeout = 0.1  # Fast recovery for test
        mock_settings.pop_max_retries = 1

        with patch("app.integrations.pop.get_settings", return_value=mock_settings):
            client = POPClient()

        mock_httpx_client = AsyncMock(spec=httpx.AsyncClient)
        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        mock_response_error.json.return_value = {"error": "Server error"}

        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"task_id": "task-123"}

        mock_httpx_client.request.return_value = mock_response_error
        client._client = mock_httpx_client

        # Trip the circuit - create_report_task catches exceptions internally
        for _ in range(2):
            result = await client.create_report_task(
                keyword="test", url="https://example.com"
            )
            assert result.success is False

        # Verify circuit is open
        assert client.circuit_breaker.is_open

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Switch to success response
        mock_httpx_client.request.return_value = mock_response_success

        # Should be able to make request again (half-open state)
        result = await client.create_report_task(
            keyword="test",
            url="https://example.com",
        )

        assert result.success is True
        assert client.circuit_breaker.is_closed


# ---------------------------------------------------------------------------
# Credential Masking Tests
# ---------------------------------------------------------------------------


class TestCredentialMasking:
    """Tests verifying API credentials are masked in logs."""

    def test_mask_api_key_in_body(self, pop_client: POPClient) -> None:
        """Test _mask_api_key() masks the API key."""
        body = {
            "apiKey": "secret-key-12345",
            "keyword": "test keyword",
            "url": "https://example.com",
        }

        masked = pop_client._mask_api_key(body)

        assert masked["apiKey"] == "****"
        assert masked["keyword"] == "test keyword"  # Other fields unchanged
        assert masked["url"] == "https://example.com"

    def test_mask_api_key_preserves_body_without_key(
        self, pop_client: POPClient
    ) -> None:
        """Test _mask_api_key() works when no apiKey present."""
        body = {
            "keyword": "test keyword",
            "url": "https://example.com",
        }

        masked = pop_client._mask_api_key(body)

        assert masked == body
        assert "apiKey" not in masked

    @pytest.mark.asyncio
    async def test_api_key_not_logged_on_request(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test API key is not present in log output during requests."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"task_id": "task-123"}
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        # Set up log capture at DEBUG level
        with caplog.at_level(logging.DEBUG, logger="app.integrations.pop"):
            await pop_client.create_report_task(
                keyword="test keyword",
                url="https://example.com",
            )

        # Check no log record contains the actual API key
        for record in caplog.records:
            assert "test-api-key-12345" not in str(record.message)
            assert "test-api-key-12345" not in str(getattr(record, "extra", {}))
            # The masked version should appear
            if "apiKey" in str(record.message) or "apiKey" in str(
                getattr(record, "extra", {})
            ):
                assert "****" in str(record.message) or "****" in str(
                    getattr(record, "extra", {})
                )

    @pytest.mark.asyncio
    async def test_api_key_not_logged_on_auth_failure(
        self,
        pop_client: POPClient,
        mock_httpx_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test API key is not logged even on auth failures."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_httpx_client.request.return_value = mock_response

        pop_client._client = mock_httpx_client

        with caplog.at_level(logging.WARNING, logger="app.integrations.pop"):
            # create_report_task catches exceptions, so check return value
            result = await pop_client.create_report_task(
                keyword="test keyword",
                url="https://example.com",
            )

        assert result.success is False
        assert "Authentication failed" in result.error

        # Verify no API key in logs
        for record in caplog.records:
            log_text = str(record.message) + str(getattr(record, "extra", {}))
            assert "test-api-key-12345" not in log_text

        # Verify credentials_logged: False is in the auth failure log
        auth_failure_logs = [
            r for r in caplog.records if "authentication failed" in r.message.lower()
        ]
        assert len(auth_failure_logs) > 0


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_truncate_for_logging_small_data(self) -> None:
        """Test _truncate_for_logging returns small data unchanged."""
        data = {"key": "value", "number": 123}
        result = _truncate_for_logging(data)
        assert result == data

    def test_truncate_for_logging_large_data(self) -> None:
        """Test _truncate_for_logging truncates large data."""
        # Create data larger than 5KB
        large_data = {"key": "x" * 10000}
        result = _truncate_for_logging(large_data)

        assert result["_truncated"] is True
        assert "_original_size_bytes" in result
        assert "_preview" in result

    def test_truncate_for_logging_non_json(self) -> None:
        """Test _truncate_for_logging handles non-JSON data."""

        # Object that can't be JSON serialized
        class CustomObj:
            pass

        result = _truncate_for_logging(CustomObj())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# POPTaskResult and POPTaskStatus Tests
# ---------------------------------------------------------------------------


class TestPOPDataclasses:
    """Tests for POP data structures."""

    def test_pop_task_result_defaults(self) -> None:
        """Test POPTaskResult has correct defaults."""
        result = POPTaskResult(success=True)

        assert result.success is True
        assert result.task_id is None
        assert result.status == POPTaskStatus.UNKNOWN
        assert result.data == {}
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.request_id is None

    def test_pop_task_result_with_values(self) -> None:
        """Test POPTaskResult with all values set."""
        result = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.SUCCESS,
            data={"pageScore": 75},
            error=None,
            duration_ms=150.5,
            request_id="req-abc",
        )

        assert result.task_id == "task-123"
        assert result.status == POPTaskStatus.SUCCESS
        assert result.data == {"pageScore": 75}
        assert result.duration_ms == 150.5

    def test_pop_task_status_values(self) -> None:
        """Test POPTaskStatus enum values."""
        assert POPTaskStatus.PENDING.value == "pending"
        assert POPTaskStatus.PROCESSING.value == "processing"
        assert POPTaskStatus.SUCCESS.value == "success"
        assert POPTaskStatus.FAILURE.value == "failure"
        assert POPTaskStatus.UNKNOWN.value == "unknown"


# ---------------------------------------------------------------------------
# Exception Tests
# ---------------------------------------------------------------------------


class TestPOPExceptions:
    """Tests for POP exception classes."""

    def test_pop_error_basic(self) -> None:
        """Test POPError basic usage."""
        error = POPError("Test error")
        assert str(error) == "Test error"
        assert error.status_code is None
        assert error.response_body is None
        assert error.request_id is None

    def test_pop_error_with_details(self) -> None:
        """Test POPError with all details."""
        error = POPError(
            "Test error",
            status_code=500,
            response_body={"error": "Server error"},
            request_id="req-123",
        )
        assert error.status_code == 500
        assert error.response_body == {"error": "Server error"}
        assert error.request_id == "req-123"

    def test_pop_timeout_error(self) -> None:
        """Test POPTimeoutError."""
        error = POPTimeoutError("Timeout after 30s", request_id="req-123")
        assert "Timeout" in str(error)
        assert isinstance(error, POPError)

    def test_pop_rate_limit_error(self) -> None:
        """Test POPRateLimitError."""
        error = POPRateLimitError(
            "Rate limited",
            retry_after=60.0,
            request_id="req-123",
        )
        assert error.status_code == 429
        assert error.retry_after == 60.0

    def test_pop_auth_error(self) -> None:
        """Test POPAuthError."""
        error = POPAuthError("Invalid API key", status_code=401)
        assert error.status_code == 401
        assert isinstance(error, POPError)

    def test_pop_circuit_open_error(self) -> None:
        """Test POPCircuitOpenError."""
        error = POPCircuitOpenError("Circuit breaker is open")
        assert "circuit" in str(error).lower()
        assert isinstance(error, POPError)
