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
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


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


# Maximum response body size to log (5KB)
MAX_RESPONSE_LOG_SIZE = 5 * 1024


def _truncate_for_logging(data: Any, max_size: int = MAX_RESPONSE_LOG_SIZE) -> Any:
    """Truncate data for logging if it exceeds max_size.

    Args:
        data: Data to potentially truncate (dict, list, or string)
        max_size: Maximum size in bytes before truncation

    Returns:
        Original data or truncated version with indicator
    """
    import json

    try:
        serialized = json.dumps(data)
        if len(serialized) <= max_size:
            return data

        # Return truncated version with indicator
        truncated_str = serialized[:max_size]
        return {
            "_truncated": True,
            "_original_size_bytes": len(serialized),
            "_preview": truncated_str[:500] + "...",
        }
    except (TypeError, ValueError):
        # If we can't serialize, just return a string representation
        str_repr = str(data)
        if len(str_repr) <= max_size:
            return str_repr
        return f"{str_repr[:max_size]}... [truncated]"


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
        max_retries: int | None = None,
        retry_delay: float | None = None,
    ) -> None:
        """Initialize POP client.

        Args:
            api_key: POP API key. Defaults to settings.
            api_url: POP API base URL. Defaults to settings.
            task_poll_interval: Interval between task status polls. Defaults to settings.
            task_timeout: Maximum time to wait for task completion. Defaults to settings.
            max_retries: Maximum retry attempts. Defaults to settings (3).
            retry_delay: Base delay between retries. Defaults to settings (1.0).
        """
        settings = get_settings()

        self._api_key = api_key or settings.pop_api_key
        self._api_url = api_url or settings.pop_api_url
        self._task_poll_interval = task_poll_interval or settings.pop_task_poll_interval
        self._task_timeout = task_timeout or settings.pop_task_timeout
        self._max_retries = (
            max_retries if max_retries is not None else settings.pop_max_retries
        )
        self._retry_delay = (
            retry_delay if retry_delay is not None else settings.pop_retry_delay
        )

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.pop_circuit_failure_threshold,
                recovery_timeout=settings.pop_circuit_recovery_timeout,
            ),
            name="pop",
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
                # Log request start at INFO level with endpoint, method, timing context
                logger.info(
                    f"POP API call starting: {method} {endpoint}",
                    extra={
                        "endpoint": endpoint,
                        "method": method,
                        "retry_attempt": attempt,
                        "max_retries": self._max_retries,
                        "request_id": request_id,
                    },
                )
                # Log request body at DEBUG level (with masked API key)
                logger.debug(
                    "POP API request body",
                    extra={
                        "endpoint": endpoint,
                        "method": method,
                        "request_body": self._mask_api_key(request_payload),
                        "request_id": request_id,
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
                    # Rate limited - extract retry-after header
                    retry_after_str = response.headers.get("retry-after")
                    retry_after = float(retry_after_str) if retry_after_str else None
                    # Log rate limit with retry-after header if present
                    logger.warning(
                        "POP API rate limit hit (429)",
                        extra={
                            "endpoint": endpoint,
                            "method": method,
                            "status_code": 429,
                            "retry_after_seconds": retry_after,
                            "retry_after_header_present": retry_after is not None,
                            "retry_attempt": attempt,
                            "max_retries": self._max_retries,
                            "request_id": request_id,
                            "duration_ms": round(duration_ms, 2),
                        },
                    )
                    await self._circuit_breaker.record_failure()

                    # If we have retry attempts left and Retry-After is reasonable
                    if (
                        attempt < self._max_retries - 1
                        and retry_after
                        and retry_after <= 60
                    ):
                        logger.info(
                            f"POP rate limit: waiting {retry_after}s before retry "
                            f"(attempt {attempt + 2}/{self._max_retries})",
                            extra={
                                "retry_attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "retry_after_seconds": retry_after,
                                "request_id": request_id,
                            },
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    raise POPRateLimitError(
                        "Rate limit exceeded",
                        retry_after=retry_after,
                        request_id=request_id,
                    )

                if response.status_code in (401, 403):
                    # Auth failure - log without exposing credentials
                    # Note: We intentionally do NOT log the request body or any
                    # credential-related information for auth failures
                    logger.warning(
                        f"POP API authentication failed ({response.status_code})",
                        extra={
                            "endpoint": endpoint,
                            "method": method,
                            "status_code": response.status_code,
                            "duration_ms": round(duration_ms, 2),
                            "error": "Authentication failed - check API key configuration",
                            "error_type": "AuthError",
                            "retry_attempt": attempt,
                            "request_id": request_id,
                            "success": False,
                            # Explicitly note credentials are masked
                            "credentials_logged": False,
                        },
                    )
                    await self._circuit_breaker.record_failure()
                    raise POPAuthError(
                        f"Authentication failed ({response.status_code})",
                        status_code=response.status_code,
                        request_id=request_id,
                    )

                if response.status_code >= 500:
                    # Server error - retry with exponential backoff
                    error_msg = f"Server error ({response.status_code})"
                    logger.error(
                        f"POP API server error: {method} {endpoint}",
                        extra={
                            "endpoint": endpoint,
                            "method": method,
                            "duration_ms": round(duration_ms, 2),
                            "status_code": response.status_code,
                            "error": error_msg,
                            "error_type": "ServerError",
                            "retry_attempt": attempt,
                            "max_retries": self._max_retries,
                            "request_id": request_id,
                            "success": False,
                        },
                    )
                    await self._circuit_breaker.record_failure()

                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2**attempt)
                        logger.warning(
                            f"POP request attempt {attempt + 1}/{self._max_retries} failed "
                            f"with {response.status_code}, retrying in {delay}s",
                            extra={
                                "retry_attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "delay_seconds": delay,
                                "status_code": response.status_code,
                                "request_id": request_id,
                                "endpoint": endpoint,
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
                    error_body = None
                    if response.content:
                        try:
                            error_body = response.json()
                        except (ValueError, TypeError):
                            # Non-JSON response (e.g., HTML error page)
                            error_body = {"raw": response.text[:500]}
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

                # Extract API credits/cost if POP provides this info
                credits_used = response_data.get("credits_used") or response_data.get(
                    "cost"
                )
                credits_remaining = response_data.get(
                    "credits_remaining"
                ) or response_data.get("remaining_credits")

                # Log success at INFO level with timing
                log_extra: dict[str, Any] = {
                    "endpoint": endpoint,
                    "method": method,
                    "duration_ms": round(duration_ms, 2),
                    "status_code": response.status_code,
                    "request_id": request_id,
                    "retry_attempt": attempt,
                    "success": True,
                }
                # Include credits info if available
                if credits_used is not None:
                    log_extra["credits_used"] = credits_used
                if credits_remaining is not None:
                    log_extra["credits_remaining"] = credits_remaining

                logger.info(
                    f"POP API call completed: {method} {endpoint}",
                    extra=log_extra,
                )

                # Log response body at DEBUG level, truncating if >5KB
                logger.debug(
                    "POP API response body",
                    extra={
                        "endpoint": endpoint,
                        "method": method,
                        "request_id": request_id,
                        "response_body": _truncate_for_logging(response_data),
                    },
                )

                await self._circuit_breaker.record_success()

                return response_data, request_id

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                # Log timeout with all required fields: endpoint, elapsed time, configured timeout
                logger.error(
                    f"POP API timeout: {method} {endpoint}",
                    extra={
                        "endpoint": endpoint,
                        "method": method,
                        "elapsed_ms": round(duration_ms, 2),
                        "configured_timeout_seconds": self._task_timeout,
                        "error": "Request timed out",
                        "error_type": "TimeoutError",
                        "retry_attempt": attempt,
                        "max_retries": self._max_retries,
                        "request_id": request_id,
                        "success": False,
                    },
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"POP request attempt {attempt + 1}/{self._max_retries} timed out, "
                        f"retrying in {delay}s",
                        extra={
                            "retry_attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                            "request_id": request_id,
                            "endpoint": endpoint,
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
                    f"POP API request error: {method} {endpoint}",
                    extra={
                        "endpoint": endpoint,
                        "method": method,
                        "elapsed_ms": round(duration_ms, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "retry_attempt": attempt,
                        "max_retries": self._max_retries,
                        "request_id": request_id,
                        "success": False,
                    },
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"POP request attempt {attempt + 1}/{self._max_retries} failed "
                        f"({type(e).__name__}), retrying in {delay}s",
                        extra={
                            "retry_attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                            "error": str(e),
                            "request_id": request_id,
                            "endpoint": endpoint,
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

    async def create_report(
        self,
        prepare_id: str,
        variations: list[str],
        lsa_phrases: list[dict[str, Any]],
        page_not_built_yet: bool = True,
    ) -> POPTaskResult:
        """Create a POP report using data from get-terms.

        POSTs to /api/expose/create-report/ with the prepareId, variations,
        and lsaPhrases from a prior get-terms call. Returns a task_id that
        must be polled via poll_for_result().

        Args:
            prepare_id: The prepareId from get-terms response.
            variations: Keyword variations from get-terms.
            lsa_phrases: LSA phrases from get-terms.
            page_not_built_yet: True if the page doesn't exist yet.

        Returns:
            POPTaskResult with task_id if successful.
        """
        start_time = time.monotonic()

        if not self._available:
            return POPTaskResult(
                success=False,
                error="POP not configured (missing API key)",
            )

        logger.info(
            "Creating POP report",
            extra={
                "prepare_id": prepare_id,
                "variations_count": len(variations),
                "lsa_phrases_count": len(lsa_phrases),
            },
        )

        payload = {
            "prepareId": prepare_id,
            "variations": variations,
            "lsaPhrases": lsa_phrases,
            "pageNotBuiltYet": page_not_built_yet,
            "googleNlpCalculation": 0,
            "eeatCalculation": 0,
        }

        try:
            response_data, request_id = await self._make_request(
                "/api/expose/create-report/",
                payload,
                method="POST",
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Check for API-level failure
            api_status = response_data.get("status", "").upper()
            if api_status == "FAILURE":
                error_msg = (
                    response_data.get("msg")
                    or response_data.get("message")
                    or "API returned FAILURE status"
                )
                logger.warning(
                    "POP create-report returned failure",
                    extra={"error": error_msg, "request_id": request_id},
                )
                return POPTaskResult(
                    success=False,
                    error=error_msg,
                    data=response_data,
                    duration_ms=duration_ms,
                    request_id=request_id,
                )

            # Extract task_id
            task_id = response_data.get("task_id") or response_data.get("taskId")
            if not task_id:
                task_id = response_data.get("id") or response_data.get("data", {}).get("task_id")

            if task_id:
                logger.info(
                    "POP report task created",
                    extra={
                        "task_id": task_id,
                        "prepare_id": prepare_id,
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
                return POPTaskResult(
                    success=False,
                    error="No task_id in create-report response",
                    data=response_data,
                    duration_ms=duration_ms,
                    request_id=request_id,
                )

        except POPError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Failed to create POP report",
                extra={
                    "prepare_id": prepare_id,
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

    async def get_custom_recommendations(
        self,
        report_id: str,
        strategy: str = "target",
        approach: str = "regular",
    ) -> POPTaskResult:
        """Get custom keyword/heading recommendations for a report.

        POSTs to /api/expose/get-custom-recommendations/ which returns
        data synchronously (no polling needed).

        Args:
            report_id: The reportId from create-report response.
            strategy: Recommendation strategy (default: "target").
            approach: Recommendation approach (default: "regular").

        Returns:
            POPTaskResult with recommendation data.
        """
        start_time = time.monotonic()

        if not self._available:
            return POPTaskResult(
                success=False,
                error="POP not configured (missing API key)",
            )

        logger.info(
            "Getting POP custom recommendations",
            extra={"report_id": report_id, "strategy": strategy, "approach": approach},
        )

        payload = {
            "reportId": report_id,
            "strategy": strategy,
            "approach": approach,
        }

        try:
            response_data, request_id = await self._make_request(
                "/api/expose/get-custom-recommendations/",
                payload,
                method="POST",
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.info(
                "POP custom recommendations received",
                extra={
                    "report_id": report_id,
                    "duration_ms": round(duration_ms, 2),
                    "request_id": request_id,
                },
            )

            return POPTaskResult(
                success=True,
                data=response_data,
                duration_ms=duration_ms,
                request_id=request_id,
            )

        except POPError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Failed to get POP custom recommendations",
                extra={
                    "report_id": report_id,
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

    async def create_report_task(
        self,
        keyword: str,
        url: str,
        location_name: str = "United States",
        target_language: str = "english",
    ) -> POPTaskResult:
        """Create a POP report task for content scoring.

        POSTs to the POP API to create a new content analysis task.
        The task runs asynchronously and must be polled for results.

        Args:
            keyword: Target keyword for content optimization
            url: URL of the page to analyze
            location_name: Google search location (default: "United States")
            target_language: Target language for analysis (default: "english")

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
                "location": location_name,
                "language": target_language,
            },
        )

        # POP API uses /api/expose/get-terms/ endpoint with specific parameter names
        payload = {
            "keyword": keyword,
            "targetUrl": url,
            "locationName": location_name,
            "targetLanguage": target_language,
        }

        try:
            response_data, request_id = await self._make_request(
                "/api/expose/get-terms/",
                payload,
                method="POST",
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Check for API-level failure (POP returns status: "FAILURE" for errors)
            api_status = response_data.get("status", "").upper()
            if api_status == "FAILURE":
                error_msg = (
                    response_data.get("msg")
                    or response_data.get("message")
                    or "API returned FAILURE status"
                )
                logger.warning(
                    "POP API returned failure status",
                    extra={
                        "error": error_msg,
                        "response": response_data,
                        "request_id": request_id,
                    },
                )
                return POPTaskResult(
                    success=False,
                    error=error_msg,
                    data=response_data,
                    duration_ms=duration_ms,
                    request_id=request_id,
                )

            # Extract task_id from response
            task_id = response_data.get("task_id") or response_data.get("taskId")

            if not task_id:
                # Some APIs return the task_id directly or in a nested structure
                task_id = response_data.get("id") or response_data.get("data", {}).get(
                    "task_id"
                )

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

            # Check timeout - log with task_id, elapsed time, and configured timeout
            if elapsed >= timeout:
                logger.error(
                    "POP task polling timed out",
                    extra={
                        "task_id": task_id,
                        "elapsed_seconds": round(elapsed, 2),
                        "configured_timeout_seconds": timeout,
                        "poll_count": poll_count,
                        "poll_interval_seconds": poll_interval,
                    },
                )
                raise POPTimeoutError(
                    f"Task {task_id} timed out after {elapsed:.1f}s",
                    request_id=task_id,
                )

            # Get current status - log poll attempt
            logger.debug(
                f"POP task poll attempt {poll_count + 1}",
                extra={
                    "task_id": task_id,
                    "poll_attempt": poll_count + 1,
                    "elapsed_seconds": round(elapsed, 2),
                    "timeout_seconds": timeout,
                },
            )

            result = await self.get_task_result(task_id)
            poll_count += 1

            if not result.success:
                # API error - return the error result
                logger.warning(
                    "POP task poll failed",
                    extra={
                        "task_id": task_id,
                        "error": result.error,
                        "poll_attempt": poll_count,
                        "elapsed_seconds": round(elapsed, 2),
                    },
                )
                return result

            # Check for terminal states
            if result.status == POPTaskStatus.SUCCESS:
                logger.info(
                    "POP task completed successfully",
                    extra={
                        "task_id": task_id,
                        "status": result.status.value,
                        "elapsed_seconds": round(elapsed, 2),
                        "poll_attempt": poll_count,
                        "total_polls": poll_count,
                    },
                )
                return result

            if result.status == POPTaskStatus.FAILURE:
                logger.warning(
                    "POP task failed",
                    extra={
                        "task_id": task_id,
                        "status": result.status.value,
                        "elapsed_seconds": round(elapsed, 2),
                        "poll_attempt": poll_count,
                        "total_polls": poll_count,
                        "error": result.data.get("error") if result.data else None,
                    },
                )
                return result

            # Still processing - log poll attempt with task_id, attempt number, status
            logger.info(
                f"POP task polling: attempt {poll_count}, status={result.status.value}",
                extra={
                    "task_id": task_id,
                    "status": result.status.value,
                    "poll_attempt": poll_count,
                    "elapsed_seconds": round(elapsed, 2),
                    "next_poll_in_seconds": poll_interval,
                    "timeout_seconds": timeout,
                },
            )

            await asyncio.sleep(poll_interval)


# ---------------------------------------------------------------------------
# LSI term corpus for mock data generation
# ---------------------------------------------------------------------------

# Generic SEO-related terms that get mixed with keyword-derived terms.
# Grouped by broad topic to allow keyword-aware selection.
_GENERIC_LSI_TERMS: list[str] = [
    "best practices",
    "buying guide",
    "comparison",
    "cost",
    "customer reviews",
    "deals",
    "expert tips",
    "features",
    "frequently asked questions",
    "how to choose",
    "maintenance",
    "materials",
    "online shopping",
    "price range",
    "product reviews",
    "quality",
    "ratings",
    "recommendations",
    "shipping options",
    "size guide",
    "top rated",
    "types",
    "value for money",
    "warranty",
    "what to look for",
]


class POPMockClient:
    """Mock POP client that returns deterministic fixture data.

    Uses keyword hash as seed so the same keyword always produces the
    same fixture data. No actual API calls are made.

    The mock implements the same interface as POPClient (create_report_task
    and poll_for_result) so the brief service can use either transparently.
    """

    def __init__(self) -> None:
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    async def close(self) -> None:
        """No-op for mock client."""

    def _seed_from_keyword(self, keyword: str) -> int:
        """Derive a deterministic integer seed from a keyword."""
        return int(hashlib.sha256(keyword.lower().strip().encode()).hexdigest(), 16)

    def _generate_lsa_phrases(
        self, keyword: str, seed: int
    ) -> list[dict[str, Any]]:
        """Generate 15-25 realistic LSI terms seeded by keyword hash."""
        import random

        rng = random.Random(seed)

        # Split keyword into tokens for building related phrases
        tokens = keyword.lower().split()

        # Build keyword-derived terms by combining tokens with modifiers
        modifiers = [
            "best",
            "top",
            "affordable",
            "premium",
            "lightweight",
            "durable",
            "comfortable",
            "waterproof",
            "popular",
            "new",
        ]
        keyword_derived: list[str] = []
        for mod in modifiers:
            phrase = f"{mod} {keyword.lower()}"
            keyword_derived.append(phrase)
        # Also add partial-keyword combos
        if len(tokens) >= 2:
            keyword_derived.append(f"{tokens[0]} {tokens[-1]}")
            keyword_derived.append(f"{tokens[-1]} {tokens[0]}")
            for t in tokens:
                keyword_derived.append(f"best {t}")

        # Merge keyword-derived + generic, deduplicate
        all_terms = keyword_derived + _GENERIC_LSI_TERMS
        rng.shuffle(all_terms)

        # Pick 15-25 unique terms
        count = rng.randint(15, 25)
        selected = list(dict.fromkeys(all_terms))[:count]

        phrases: list[dict[str, Any]] = []
        for phrase_text in selected:
            weight = rng.randint(10, 100)
            avg_count = round(rng.uniform(0.5, 8.0), 1)
            target_count = max(1, round(avg_count * rng.uniform(0.8, 1.3)))
            phrases.append(
                {
                    "phrase": phrase_text,
                    "weight": weight,
                    "averageCount": avg_count,
                    "targetCount": target_count,
                }
            )

        # Sort by weight descending (mimics real API)
        phrases.sort(key=lambda p: p["weight"], reverse=True)
        return phrases

    def _generate_variations(self, keyword: str, seed: int) -> list[str]:
        """Generate keyword variations seeded by keyword hash."""
        import random

        rng = random.Random(seed + 1)  # offset seed for independent stream

        tokens = keyword.lower().split()
        variations: list[str] = [keyword.lower()]

        # Rearrangements
        if len(tokens) >= 2:
            variations.append(" ".join(reversed(tokens)))
            variations.append(f"{tokens[-1]} for {tokens[0]}")

        # Plurals / singulars
        for t in tokens:
            if t.endswith("s"):
                variations.append(keyword.lower().replace(t, t[:-1]))
            else:
                variations.append(keyword.lower().replace(t, t + "s"))

        # Question forms
        variations.append(f"what are the best {keyword.lower()}")
        variations.append(f"how to choose {keyword.lower()}")

        # Deduplicate, shuffle deterministically, take 5-10
        unique = list(dict.fromkeys(variations))
        rng.shuffle(unique)
        count = rng.randint(5, min(10, len(unique)))
        return unique[:count]

    def _generate_prepare_id(self, keyword: str) -> str:
        """Generate a fake prepareId string."""
        # Use first 12 hex chars of keyword hash as a realistic-looking ID
        hex_str = hashlib.sha256(keyword.lower().strip().encode()).hexdigest()
        return f"mock-{hex_str[:12]}"

    def _generate_competitors(self, keyword: str, seed: int) -> list[dict[str, Any]]:
        """Generate mock competitor data seeded by keyword hash."""
        import random

        rng = random.Random(seed + 10)
        tokens = keyword.lower().split()
        slug = "-".join(tokens)

        domains = [
            "competitor1.com", "bigretailer.com", "expertsite.org",
            "topreviews.com", "bestpicks.net",
        ]
        rng.shuffle(domains)

        competitors: list[dict[str, Any]] = []
        for i, domain in enumerate(domains[:3]):
            page_score = round(rng.uniform(55.0, 95.0), 1)
            word_count = rng.randint(600, 2000)
            h2_count = rng.randint(3, 8)
            h3_count = rng.randint(2, 6)
            competitors.append(
                {
                    "url": f"https://{domain}/{slug}",
                    "h2Texts": [f"H2 heading {j + 1} about {keyword}" for j in range(h2_count)],
                    "h3Texts": [f"H3 subtopic {j + 1}" for j in range(h3_count)],
                    "pageScore": page_score,
                    "wordCount": word_count,
                }
            )
        return competitors

    def _generate_related_questions(self, keyword: str, seed: int) -> list[str]:
        """Generate mock People Also Ask questions."""
        import random

        rng = random.Random(seed + 20)
        templates = [
            f"What are the best {keyword}?",
            f"How to choose {keyword}?",
            f"Are {keyword} worth it?",
            f"What is the difference between types of {keyword}?",
            f"Where to buy {keyword} online?",
            f"How much do {keyword} cost?",
            f"What are the top-rated {keyword}?",
            f"How to care for {keyword}?",
        ]
        rng.shuffle(templates)
        count = rng.randint(5, min(8, len(templates)))
        return templates[:count]

    def _generate_tag_counts(self, seed: int) -> dict[str, int]:
        """Generate mock heading tag count targets."""
        import random

        rng = random.Random(seed + 30)
        return {
            "h1": 1,
            "h2": rng.randint(3, 6),
            "h3": rng.randint(4, 10),
            "h4": rng.randint(0, 3),
        }

    def _generate_report_data(self, keyword: str, seed: int) -> dict[str, Any]:
        """Generate full create-report mock response data."""
        import random

        rng = random.Random(seed + 40)
        hex_str = hashlib.sha256(keyword.lower().strip().encode()).hexdigest()
        report_id = f"mock-report-{hex_str[:12]}"

        competitors = self._generate_competitors(keyword, seed)
        related_questions = self._generate_related_questions(keyword, seed)
        tag_counts = self._generate_tag_counts(seed)

        # Word count range from competitors
        comp_wcs = [c["wordCount"] for c in competitors]
        avg_wc = round(sum(comp_wcs) / len(comp_wcs)) if comp_wcs else 800

        # Page score target (slightly above average of competitors)
        comp_scores = [c["pageScore"] for c in competitors]
        avg_score = sum(comp_scores) / len(comp_scores) if comp_scores else 70.0
        page_score = round(min(avg_score + rng.uniform(5.0, 15.0), 100.0), 1)

        # cleanedContentBrief — per-term targets
        lsa_phrases = self._generate_lsa_phrases(keyword, seed)
        cleaned_brief: list[dict[str, Any]] = []
        for phrase_item in lsa_phrases[:15]:
            tc = phrase_item.get("targetCount", 1)
            cleaned_brief.append(
                {
                    "phrase": phrase_item["phrase"],
                    "targetMin": max(1, tc - 1),
                    "targetMax": tc + 1,
                }
            )

        return {
            "reportId": report_id,
            "competitors": competitors,
            "relatedQuestions": related_questions,
            "relatedSearches": self._generate_variations(keyword, seed),
            "wordCount": {
                "avg": avg_wc,
                "competitorsMin": min(comp_wcs) if comp_wcs else 500,
                "competitorsMax": max(comp_wcs) if comp_wcs else 1500,
            },
            "pageScore": page_score,
            "tagCounts": tag_counts,
            "cleanedContentBrief": cleaned_brief,
        }

    def _generate_recommendations_data(self, keyword: str, seed: int) -> dict[str, Any]:
        """Generate mock get-custom-recommendations response data."""
        import random

        rng = random.Random(seed + 50)

        exact_keyword_recs: list[dict[str, Any]] = [
            {"signal": "Meta Title", "target": 1, "comment": f'Include "{keyword}" in meta title'},
            {"signal": "H1", "target": 1, "comment": f'Include "{keyword}" in H1 heading'},
            {"signal": "URL", "target": 1, "comment": f'Include "{keyword}" slug in URL'},
        ]

        tokens = keyword.lower().split()
        lsi_signals: list[dict[str, Any]] = [
            {"signal": "Meta Title", "phrase": f"best {keyword}", "target": 1},
            {"signal": "H3", "phrase": tokens[0] if tokens else keyword, "target": rng.randint(1, 3)},
            {"signal": "Paragraph Text", "phrase": keyword, "target": rng.randint(3, 8)},
            {"signal": "Bold", "phrase": keyword, "target": rng.randint(1, 2)},
            {"signal": "Italic", "phrase": tokens[-1] if tokens else keyword, "target": 1},
        ]

        tag_counts = self._generate_tag_counts(seed)
        page_structure: list[dict[str, Any]] = [
            {"signal": "H1", "target": 1},
            {"signal": "H2", "target": tag_counts["h2"]},
            {"signal": "H3", "target": tag_counts["h3"]},
            {"signal": "H4", "target": tag_counts.get("h4", 0)},
            {"signal": "Paragraph Text", "target": rng.randint(8, 20)},
        ]

        return {
            "exactKeyword": exact_keyword_recs,
            "lsi": lsi_signals,
            "pageStructure": page_structure,
        }

    async def create_report(
        self,
        prepare_id: str,  # noqa: ARG002
        variations: list[str],  # noqa: ARG002
        lsa_phrases: list[dict[str, Any]],  # noqa: ARG002
        page_not_built_yet: bool = True,  # noqa: ARG002
    ) -> POPTaskResult:
        """Mock create_report — returns fixture data immediately."""
        # Derive keyword from prepare_id for deterministic data
        logger.info(
            "POPMockClient: mock create_report called",
            extra={"prepare_id": prepare_id},
        )
        return POPTaskResult(
            success=True,
            data={},
            duration_ms=0.0,
        )

    async def get_custom_recommendations(
        self,
        report_id: str,  # noqa: ARG002
        strategy: str = "target",  # noqa: ARG002
        approach: str = "regular",  # noqa: ARG002
    ) -> POPTaskResult:
        """Mock get_custom_recommendations — returns fixture data immediately."""
        logger.info(
            "POPMockClient: mock get_custom_recommendations called",
            extra={"report_id": report_id},
        )
        return POPTaskResult(
            success=True,
            data={},
            duration_ms=0.0,
        )

    async def create_report_task(
        self,
        keyword: str,
        url: str,
        location_name: str = "United States",  # noqa: ARG002
        target_language: str = "english",  # noqa: ARG002
    ) -> POPTaskResult:
        """Mock create_report_task — returns a fake task ID immediately."""
        seed = self._seed_from_keyword(keyword)
        task_id = f"mock-task-{hashlib.sha256(keyword.lower().strip().encode()).hexdigest()[:8]}"

        logger.info(
            "POPMockClient: created mock report task",
            extra={
                "keyword": keyword[:50],
                "url": url[:100],
                "task_id": task_id,
            },
        )

        return POPTaskResult(
            success=True,
            task_id=task_id,
            status=POPTaskStatus.PENDING,
            data={"task_id": task_id},
            duration_ms=0.0,
            request_id=f"mock-{seed % 100000:05d}",
        )

    async def poll_for_result(
        self,
        task_id: str,
        poll_interval: float | None = None,  # noqa: ARG002
        timeout: float | None = None,  # noqa: ARG002
    ) -> POPTaskResult:
        """Mock poll_for_result — returns fixture data immediately."""
        logger.info(
            "POPMockClient: returning mock result for task",
            extra={"task_id": task_id},
        )

        return POPTaskResult(
            success=True,
            task_id=task_id,
            status=POPTaskStatus.SUCCESS,
            data={},
            duration_ms=0.0,
        )

    async def get_terms(
        self,
        keyword: str,
        url: str,  # noqa: ARG002
        location_name: str = "United States",  # noqa: ARG002
        target_language: str = "english",  # noqa: ARG002
    ) -> POPTaskResult:
        """Combined convenience method: creates task + returns all 3-step mock results.

        This is the primary method the brief service should use. Returns
        complete fixture data from all 3 POP API steps in one call.

        Args:
            keyword: Target keyword for content optimization
            url: URL of the page to analyze
            location_name: Google search location
            target_language: Target language

        Returns:
            POPTaskResult with mock data from get-terms + create-report + recommendations
        """
        seed = self._seed_from_keyword(keyword)
        task_id = f"mock-task-{hashlib.sha256(keyword.lower().strip().encode()).hexdigest()[:8]}"

        lsa_phrases = self._generate_lsa_phrases(keyword, seed)
        variations = self._generate_variations(keyword, seed)
        prepare_id = self._generate_prepare_id(keyword)

        # Mock a realistic word count target (600-1200 range based on keyword)
        rng = __import__("random").Random(seed)
        word_count_target = rng.choice([600, 700, 800, 900, 1000, 1100, 1200])

        # Generate step 2 (create-report) data
        report_data = self._generate_report_data(keyword, seed)

        # Generate step 3 (recommendations) data
        recs_data = self._generate_recommendations_data(keyword, seed)

        # Merge all data into single response
        response_data: dict[str, Any] = {
            # Step 1: get-terms
            "lsaPhrases": lsa_phrases,
            "variations": variations,
            "prepareId": prepare_id,
            "wordCountTarget": word_count_target,
            "status": "success",
            "task_id": task_id,
            # Step 2: create-report
            "reportId": report_data["reportId"],
            "competitors": report_data["competitors"],
            "relatedQuestions": report_data["relatedQuestions"],
            "relatedSearches": report_data["relatedSearches"],
            "wordCount": report_data["wordCount"],
            "pageScore": report_data["pageScore"],
            "tagCounts": report_data["tagCounts"],
            "cleanedContentBrief": report_data["cleanedContentBrief"],
            # Step 3: recommendations
            "exactKeyword": recs_data["exactKeyword"],
            "lsi": recs_data["lsi"],
            "pageStructure": recs_data["pageStructure"],
        }

        logger.info(
            "POPMockClient: returning mock 3-step data",
            extra={
                "keyword": keyword[:50],
                "lsi_term_count": len(lsa_phrases),
                "variation_count": len(variations),
                "competitor_count": len(report_data["competitors"]),
                "related_questions_count": len(report_data["relatedQuestions"]),
                "prepare_id": prepare_id,
                "task_id": task_id,
            },
        )

        return POPTaskResult(
            success=True,
            task_id=task_id,
            status=POPTaskStatus.SUCCESS,
            data=response_data,
            duration_ms=0.0,
            request_id=f"mock-{seed % 100000:05d}",
        )


# ---------------------------------------------------------------------------
# Global POP client instance (real or mock)
# ---------------------------------------------------------------------------

_pop_client: POPClient | POPMockClient | None = None


async def init_pop() -> POPClient | POPMockClient:
    """Initialize the global POP client.

    Uses POPMockClient when POP_USE_MOCK=true, otherwise real POPClient.

    Returns:
        Initialized POPClient or POPMockClient instance
    """
    global _pop_client
    if _pop_client is None:
        settings = get_settings()
        if settings.pop_use_mock:
            _pop_client = POPMockClient()
            logger.info("POP mock client initialized (POP_USE_MOCK=true)")
        else:
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


async def get_pop_client() -> POPClient | POPMockClient:
    """Dependency for getting POP client.

    Returns POPMockClient when POP_USE_MOCK=true, otherwise real POPClient.

    Usage:
        @app.get("/content-score")
        async def score_content(
            url: str,
            client: POPClient | POPMockClient = Depends(get_pop_client)
        ):
            result = await client.score_content(url)
            ...
    """
    global _pop_client
    if _pop_client is None:
        await init_pop()
    return _pop_client  # type: ignore[return-value]
