"""PageOptimizer Pro (POP) API integration client for content scoring.

Features:
- Async HTTP client using httpx (direct API calls)
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- Request/response logging per requirements
- Handles timeouts, rate limits (429), auth failures (401/403)
- Masks API credentials in all logs
- Task polling for async operations

PageOptimizer Pro provides:
- Content briefs with keyword targets
- Content scoring and optimization recommendations
- Competitor analysis
- NLP-based content optimization

ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Mask API credentials in all logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- All API credentials via environment variables (POP_API_KEY)
- Never log or expose API credentials
- Handle cold-start latency (first request may be slow)
- Implement request timeouts (Railway has 5min request limit)

AUTHENTICATION:
- POP uses apiKey in request body (not HTTP headers)
- All requests must include {"apiKey": "<key>"} in the JSON body

API ENDPOINTS:
- Task creation: POST to base URL with keyword/URL in body
- Task results: GET https://app.pageoptimizer.pro/api/task/:task_id/results/
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject all requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int
    recovery_timeout: float


class CircuitBreaker:
    """Circuit breaker implementation for POP operations.

    Prevents cascading failures by stopping requests to a failing service.
    After recovery_timeout, allows a test request through (half-open state).
    If test succeeds, circuit closes. If fails, circuit opens again.
    """

    def __init__(self, config: CircuitBreakerConfig) -> None:
        self._config = config
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state == CircuitState.OPEN

    async def _check_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return False
        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self._config.recovery_timeout

    async def can_execute(self) -> bool:
        """Check if operation can be executed based on circuit state."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if await self._check_recovery():
                    # Transition to half-open for testing
                    previous_state = self._state.value
                    self._state = CircuitState.HALF_OPEN
                    logger.warning(
                        "POP circuit breaker state changed",
                        extra={
                            "previous_state": previous_state,
                            "new_state": self._state.value,
                            "failure_count": self._failure_count,
                        },
                    )
                    logger.info("POP circuit breaker attempting recovery")
                    return True
                return False

            # HALF_OPEN state - allow single test request
            return True

    async def record_success(self) -> None:
        """Record successful operation."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Recovery successful, close circuit
                previous_state = self._state.value
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._last_failure_time = None
                logger.warning(
                    "POP circuit breaker state changed",
                    extra={
                        "previous_state": previous_state,
                        "new_state": self._state.value,
                        "failure_count": self._failure_count,
                    },
                )
                logger.info("POP circuit breaker closed - API calls restored")
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record failed operation."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Recovery failed, open circuit again
                previous_state = self._state.value
                self._state = CircuitState.OPEN
                logger.warning(
                    "POP circuit breaker state changed",
                    extra={
                        "previous_state": previous_state,
                        "new_state": self._state.value,
                        "failure_count": self._failure_count,
                    },
                )
                logger.error(
                    "POP circuit breaker opened - API calls disabled",
                    extra={
                        "failure_count": self._failure_count,
                        "recovery_timeout_seconds": self._config.recovery_timeout,
                    },
                )
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self._config.failure_threshold
            ):
                # Too many failures, open circuit
                previous_state = self._state.value
                self._state = CircuitState.OPEN
                logger.warning(
                    "POP circuit breaker state changed",
                    extra={
                        "previous_state": previous_state,
                        "new_state": self._state.value,
                        "failure_count": self._failure_count,
                    },
                )
                logger.error(
                    "POP circuit breaker opened - API calls disabled",
                    extra={
                        "failure_count": self._failure_count,
                        "recovery_timeout_seconds": self._config.recovery_timeout,
                    },
                )


class POPError(Exception):
    """Base exception for POP API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.request_id = request_id


class POPTimeoutError(POPError):
    """Raised when a request times out."""

    pass


class POPRateLimitError(POPError):
    """Raised when rate limited (429)."""

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
        response_body: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(
            message, status_code=429, response_body=response_body, request_id=request_id
        )
        self.retry_after = retry_after


class POPAuthError(POPError):
    """Raised when authentication fails (401/403)."""

    pass


class POPCircuitOpenError(POPError):
    """Raised when circuit breaker is open."""

    pass


class POPTaskStatus(Enum):
    """POP task status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


@dataclass
class POPTaskResult:
    """Result of a POP task operation."""

    success: bool
    task_id: str | None = None
    status: POPTaskStatus = POPTaskStatus.UNKNOWN
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


class POPClient:
    """Async client for PageOptimizer Pro API.

    Provides content optimization capabilities:
    - Content briefs with keyword targets
    - Content scoring and recommendations
    - Competitor analysis

    Features:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Comprehensive logging
    - Railway deployment compatibility
    - Task polling for async operations

    Authentication:
    POP uses apiKey in request body, not HTTP headers.
    All requests must include {"apiKey": "<key>"} in the JSON body.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        task_poll_interval: float | None = None,
        task_timeout: float | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize POP client.

        Args:
            api_key: POP API key. Defaults to settings.
            api_url: POP API base URL. Defaults to settings.
            task_poll_interval: Interval between task status polls. Defaults to settings.
            task_timeout: Maximum time to wait for task completion. Defaults to settings.
            max_retries: Maximum retry attempts. Defaults to 3.
            retry_delay: Base delay between retries. Defaults to 1.0.
        """
        settings = get_settings()

        self._api_key = api_key or settings.pop_api_key
        self._api_url = api_url or settings.pop_api_url
        self._task_poll_interval = task_poll_interval or settings.pop_task_poll_interval
        self._task_timeout = task_timeout or settings.pop_task_timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.pop_circuit_failure_threshold,
                recovery_timeout=settings.pop_circuit_recovery_timeout,
            )
        )

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None
        self._available = bool(self._api_key)

    @property
    def available(self) -> bool:
        """Check if POP is configured and available."""
        return self._available

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    def _mask_api_key(self, body: dict[str, Any]) -> dict[str, Any]:
        """Mask API key in body for logging."""
        if "apiKey" in body:
            masked = body.copy()
            masked["apiKey"] = "****"
            return masked
        return body

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._api_url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(self._task_timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("POP client closed")

    async def _make_request(
        self,
        endpoint: str,
        payload: dict[str, Any],
        method: str = "POST",
    ) -> tuple[dict[str, Any], str]:
        """Make an HTTP request to POP API with retry logic.

        Args:
            endpoint: API endpoint path
            payload: Request payload (apiKey will be added automatically)
            method: HTTP method

        Returns:
            Tuple of (response_data, request_id)

        Raises:
            POPError: On API errors
            POPTimeoutError: On timeout
            POPRateLimitError: On rate limit (429)
            POPAuthError: On auth failure (401/403)
            POPCircuitOpenError: When circuit breaker is open
        """
        request_id = str(uuid.uuid4())[:8]

        if not self._available:
            raise POPError(
                "POP not configured (missing API key)",
                request_id=request_id,
            )

        if not await self._circuit_breaker.can_execute():
            logger.info(
                "POP unavailable, circuit breaker open",
                extra={
                    "endpoint": endpoint,
                    "reason": "Circuit breaker open",
                },
            )
            raise POPCircuitOpenError(
                "Circuit breaker is open",
                request_id=request_id,
            )

        client = await self._get_client()
        last_error: Exception | None = None

        # Add apiKey to payload
        request_payload = {"apiKey": self._api_key, **payload}

        for attempt in range(self._max_retries):
            attempt_start = time.monotonic()

            try:
                # Log request start (mask API key)
                logger.debug(
                    f"POP API call: {method} {endpoint}",
                    extra={
                        "endpoint": endpoint,
                        "method": method,
                        "retry_attempt": attempt,
                        "request_id": request_id,
                    },
                )
                logger.debug(
                    "POP API request body",
                    extra={
                        "endpoint": endpoint,
                        "request_body": self._mask_api_key(request_payload),
                    },
                )

                # Make request
                response = await client.request(
                    method,
                    endpoint,
                    json=request_payload,
                )
                duration_ms = (time.monotonic() - attempt_start) * 1000

                # Handle response based on status code
                if response.status_code == 429:
                    # Rate limited
                    retry_after_str = response.headers.get("retry-after")
                    retry_after = float(retry_after_str) if retry_after_str else None
                    logger.warning(
                        "POP API rate limit hit (429)",
                        extra={
                            "endpoint": endpoint,
                            "retry_after_seconds": retry_after,
                            "request_id": request_id,
                        },
                    )
                    await self._circuit_breaker.record_failure()

                    # If we have retry attempts left and Retry-After is reasonable
                    if (
                        attempt < self._max_retries - 1
                        and retry_after
                        and retry_after <= 60
                    ):
                        await asyncio.sleep(retry_after)
                        continue

                    raise POPRateLimitError(
                        "Rate limit exceeded",
                        retry_after=retry_after,
                        request_id=request_id,
                    )

                if response.status_code in (401, 403):
                    # Auth failure
                    logger.warning(
                        f"POP API authentication failed ({response.status_code})",
                        extra={
                            "status_code": response.status_code,
                        },
                    )
                    logger.warning(
                        f"POP API call failed: {method} {endpoint}",
                        extra={
                            "endpoint": endpoint,
                            "method": method,
                            "duration_ms": round(duration_ms, 2),
                            "status_code": response.status_code,
                            "error": "Authentication failed",
                            "error_type": "AuthError",
                            "retry_attempt": attempt,
                            "request_id": request_id,
                            "success": False,
                        },
                    )
                    await self._circuit_breaker.record_failure()
                    raise POPAuthError(
                        f"Authentication failed ({response.status_code})",
                        status_code=response.status_code,
                        request_id=request_id,
                    )

                if response.status_code >= 500:
                    # Server error - retry
                    error_msg = f"Server error ({response.status_code})"
                    logger.error(
                        f"POP API call failed: {method} {endpoint}",
                        extra={
                            "endpoint": endpoint,
                            "method": method,
                            "duration_ms": round(duration_ms, 2),
                            "status_code": response.status_code,
                            "error": error_msg,
                            "error_type": "ServerError",
                            "retry_attempt": attempt,
                            "request_id": request_id,
                            "success": False,
                        },
                    )
                    await self._circuit_breaker.record_failure()

                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2**attempt)
                        logger.warning(
                            f"POP request attempt {attempt + 1} failed, "
                            f"retrying in {delay}s",
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "delay_seconds": delay,
                                "status_code": response.status_code,
                                "request_id": request_id,
                            },
                        )
                        await asyncio.sleep(delay)
                        continue

                    raise POPError(
                        error_msg,
                        status_code=response.status_code,
                        request_id=request_id,
                    )

                if response.status_code >= 400:
                    # Client error - don't retry
                    error_body = response.json() if response.content else None
                    error_msg = str(error_body) if error_body else "Client error"
                    logger.warning(
                        f"POP API call failed: {method} {endpoint}",
                        extra={
                            "endpoint": endpoint,
                            "method": method,
                            "duration_ms": round(duration_ms, 2),
                            "status_code": response.status_code,
                            "error": error_msg,
                            "error_type": "ClientError",
                            "retry_attempt": attempt,
                            "request_id": request_id,
                            "success": False,
                        },
                    )
                    raise POPError(
                        f"Client error ({response.status_code}): {error_msg}",
                        status_code=response.status_code,
                        response_body=error_body,
                        request_id=request_id,
                    )

                # Success - parse response
                response_data = response.json()

                # Log success
                logger.debug(
                    f"POP API call completed: {method} {endpoint}",
                    extra={
                        "endpoint": endpoint,
                        "method": method,
                        "duration_ms": round(duration_ms, 2),
                        "request_id": request_id,
                        "success": True,
                    },
                )

                await self._circuit_breaker.record_success()

                return response_data, request_id

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.warning(
                    "POP API request timeout",
                    extra={
                        "endpoint": endpoint,
                        "timeout_seconds": self._task_timeout,
                    },
                )
                logger.error(
                    f"POP API call failed: {method} {endpoint}",
                    extra={
                        "endpoint": endpoint,
                        "method": method,
                        "duration_ms": round(duration_ms, 2),
                        "status_code": None,
                        "error": "Request timed out",
                        "error_type": "TimeoutError",
                        "retry_attempt": attempt,
                        "request_id": request_id,
                        "success": False,
                    },
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"POP request attempt {attempt + 1} timed out, "
                        f"retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                last_error = POPTimeoutError(
                    f"Request timed out after {self._task_timeout}s",
                    request_id=request_id,
                )

            except httpx.RequestError as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.error(
                    f"POP API call failed: {method} {endpoint}",
                    extra={
                        "endpoint": endpoint,
                        "method": method,
                        "duration_ms": round(duration_ms, 2),
                        "status_code": None,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "retry_attempt": attempt,
                        "request_id": request_id,
                        "success": False,
                    },
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"POP request attempt {attempt + 1} failed, "
                        f"retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                last_error = POPError(
                    f"Request failed: {e}",
                    request_id=request_id,
                )

        if last_error:
            raise last_error
        raise POPError(
            "Request failed after all retries",
            request_id=request_id,
        )

    async def create_report_task(
        self,
        keyword: str,
        url: str,
    ) -> POPTaskResult:
        """Create a POP report task for content scoring.

        POSTs to the POP API to create a new content analysis task.
        The task runs asynchronously and must be polled for results.

        Args:
            keyword: Target keyword for content optimization
            url: URL of the page to analyze

        Returns:
            POPTaskResult with task_id if successful
        """
        start_time = time.monotonic()

        if not self._available:
            return POPTaskResult(
                success=False,
                error="POP not configured (missing API key)",
            )

        if not keyword or not url:
            return POPTaskResult(
                success=False,
                error="Both keyword and url are required",
            )

        logger.info(
            "Creating POP report task",
            extra={
                "keyword": keyword[:50],
                "url": url[:100],
            },
        )

        payload = {
            "keyword": keyword,
            "url": url,
        }

        try:
            response_data, request_id = await self._make_request(
                "/api/report",
                payload,
                method="POST",
            )

            # Extract task_id from response
            task_id = response_data.get("task_id") or response_data.get("taskId")

            if not task_id:
                # Some APIs return the task_id directly or in a nested structure
                task_id = response_data.get("id") or response_data.get("data", {}).get(
                    "task_id"
                )

            duration_ms = (time.monotonic() - start_time) * 1000

            if task_id:
                logger.info(
                    "POP report task created",
                    extra={
                        "task_id": task_id,
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPTaskResult(
                    success=True,
                    task_id=str(task_id),
                    status=POPTaskStatus.PENDING,
                    data=response_data,
                    duration_ms=duration_ms,
                    request_id=request_id,
                )
            else:
                logger.warning(
                    "POP task created but no task_id returned",
                    extra={
                        "response_keys": list(response_data.keys()),
                    },
                )
                return POPTaskResult(
                    success=False,
                    error="No task_id in response",
                    data=response_data,
                    duration_ms=duration_ms,
                    request_id=request_id,
                )

        except POPError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Failed to create POP report task",
                extra={
                    "keyword": keyword[:50],
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return POPTaskResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
                request_id=e.request_id,
            )

    async def get_task_result(
        self,
        task_id: str,
    ) -> POPTaskResult:
        """Get the result of a POP task.

        GETs the task status and results from the POP API.

        Args:
            task_id: The task ID returned from create_report_task()

        Returns:
            POPTaskResult with status and data if available
        """
        start_time = time.monotonic()

        if not self._available:
            return POPTaskResult(
                success=False,
                task_id=task_id,
                error="POP not configured (missing API key)",
            )

        if not task_id:
            return POPTaskResult(
                success=False,
                error="task_id is required",
            )

        logger.debug(
            "Getting POP task result",
            extra={"task_id": task_id},
        )

        # POP API endpoint for task results
        # Note: This uses the app.pageoptimizer.pro domain per the notes
        endpoint = f"/api/task/{task_id}/results/"

        try:
            # Note: GET request still needs apiKey in body for POP
            response_data, request_id = await self._make_request(
                endpoint,
                {},  # Empty payload, apiKey added by _make_request
                method="GET",
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Parse status from response
            status_str = (
                response_data.get("status")
                or response_data.get("task_status")
                or "unknown"
            )
            status_str = status_str.lower()

            if status_str in ("success", "complete", "completed", "done"):
                status = POPTaskStatus.SUCCESS
            elif status_str in ("failure", "failed", "error"):
                status = POPTaskStatus.FAILURE
            elif status_str in ("pending", "queued", "waiting"):
                status = POPTaskStatus.PENDING
            elif status_str in ("processing", "running", "in_progress"):
                status = POPTaskStatus.PROCESSING
            else:
                status = POPTaskStatus.UNKNOWN

            logger.debug(
                "POP task status retrieved",
                extra={
                    "task_id": task_id,
                    "status": status.value,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return POPTaskResult(
                success=True,
                task_id=task_id,
                status=status,
                data=response_data,
                duration_ms=duration_ms,
                request_id=request_id,
            )

        except POPError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Failed to get POP task result",
                extra={
                    "task_id": task_id,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return POPTaskResult(
                success=False,
                task_id=task_id,
                error=str(e),
                duration_ms=duration_ms,
                request_id=e.request_id,
            )

    async def poll_for_result(
        self,
        task_id: str,
        poll_interval: float | None = None,
        timeout: float | None = None,
    ) -> POPTaskResult:
        """Poll for task completion with configurable interval and timeout.

        Continuously polls get_task_result() until the task completes
        (SUCCESS or FAILURE) or the timeout is reached.

        Args:
            task_id: The task ID to poll
            poll_interval: Seconds between polls. Defaults to settings (3s).
            timeout: Maximum seconds to wait. Defaults to settings (300s).

        Returns:
            POPTaskResult with final status and data

        Raises:
            POPTimeoutError: If timeout is reached before task completes
        """
        poll_interval = poll_interval or self._task_poll_interval
        timeout = timeout or self._task_timeout

        start_time = time.monotonic()
        poll_count = 0

        logger.info(
            "Starting POP task polling",
            extra={
                "task_id": task_id,
                "poll_interval_seconds": poll_interval,
                "timeout_seconds": timeout,
            },
        )

        while True:
            elapsed = time.monotonic() - start_time

            # Check timeout
            if elapsed >= timeout:
                logger.error(
                    "POP task polling timed out",
                    extra={
                        "task_id": task_id,
                        "elapsed_seconds": round(elapsed, 2),
                        "timeout_seconds": timeout,
                        "poll_count": poll_count,
                    },
                )
                raise POPTimeoutError(
                    f"Task {task_id} timed out after {elapsed:.1f}s",
                    request_id=task_id,
                )

            # Get current status
            result = await self.get_task_result(task_id)
            poll_count += 1

            if not result.success:
                # API error - return the error result
                logger.warning(
                    "POP task poll failed",
                    extra={
                        "task_id": task_id,
                        "error": result.error,
                        "poll_count": poll_count,
                    },
                )
                return result

            # Check for terminal states
            if result.status == POPTaskStatus.SUCCESS:
                logger.info(
                    "POP task completed successfully",
                    extra={
                        "task_id": task_id,
                        "elapsed_seconds": round(elapsed, 2),
                        "poll_count": poll_count,
                    },
                )
                return result

            if result.status == POPTaskStatus.FAILURE:
                logger.warning(
                    "POP task failed",
                    extra={
                        "task_id": task_id,
                        "elapsed_seconds": round(elapsed, 2),
                        "poll_count": poll_count,
                        "data": result.data,
                    },
                )
                return result

            # Still processing - wait and poll again
            logger.debug(
                "POP task still processing",
                extra={
                    "task_id": task_id,
                    "status": result.status.value,
                    "elapsed_seconds": round(elapsed, 2),
                    "poll_count": poll_count,
                    "next_poll_in": poll_interval,
                },
            )

            await asyncio.sleep(poll_interval)


# Global POP client instance
_pop_client: POPClient | None = None


async def init_pop() -> POPClient:
    """Initialize the global POP client.

    Returns:
        Initialized POPClient instance
    """
    global _pop_client
    if _pop_client is None:
        _pop_client = POPClient()
        if _pop_client.available:
            logger.info("POP client initialized")
        else:
            logger.info("POP not configured (missing API key)")
    return _pop_client


async def close_pop() -> None:
    """Close the global POP client."""
    global _pop_client
    if _pop_client:
        await _pop_client.close()
        _pop_client = None


async def get_pop_client() -> POPClient:
    """Dependency for getting POP client.

    Usage:
        @app.get("/content-score")
        async def score_content(
            url: str,
            client: POPClient = Depends(get_pop_client)
        ):
            result = await client.score_content(url)
            ...
    """
    global _pop_client
    if _pop_client is None:
        await init_pop()
    return _pop_client  # type: ignore[return-value]
