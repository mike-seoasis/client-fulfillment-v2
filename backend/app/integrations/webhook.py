"""Webhook integration client for sending HTTP notifications.

Features:
- Async HTTP client using httpx
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- HMAC signature generation for webhook security
- Request/response logging per requirements
- Handles timeouts, rate limits, and connection errors

ERROR LOGGING REQUIREMENTS:
- Log all outbound webhook calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), connection errors
- Include retry attempt number in logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- Handle cold-start latency
- Implement request timeouts (Railway has 5min request limit)
"""

import asyncio
import contextlib
import hashlib
import hmac
import json
import time
import traceback
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class WebhookResult:
    """Result of a webhook send operation."""

    success: bool
    url: str
    method: str
    status_code: int | None = None
    response_body: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: float = 0.0
    retry_attempt: int = 0


class WebhookError(Exception):
    """Base exception for webhook errors."""

    pass


class WebhookConnectionError(WebhookError):
    """Raised when connection to webhook endpoint fails."""

    pass


class WebhookTimeoutError(WebhookError):
    """Raised when webhook request times out."""

    pass


class WebhookRateLimitError(WebhookError):
    """Raised when rate limited (429)."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class WebhookCircuitOpenError(WebhookError):
    """Raised when circuit breaker is open."""

    pass


def generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload.

    Args:
        payload: JSON payload string
        secret: Webhook secret key

    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class WebhookClient:
    """Async client for sending webhook notifications.

    Provides webhook capabilities with:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - HMAC signature generation
    - Comprehensive logging
    """

    def __init__(
        self,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
    ) -> None:
        """Initialize webhook client."""
        settings = get_settings()

        self._timeout = timeout or settings.webhook_timeout
        self._max_retries = max_retries or settings.webhook_max_retries
        self._retry_delay = retry_delay or settings.webhook_retry_delay

        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.webhook_circuit_failure_threshold,
                recovery_timeout=settings.webhook_circuit_recovery_timeout,
            ),
            name="webhook",
        )

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get circuit breaker instance."""
        return self._circuit_breaker

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Webhook client closed")

    async def send(
        self,
        url: str,
        payload: dict[str, Any],
        method: str = "POST",
        headers: dict[str, str] | None = None,
        secret: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
    ) -> WebhookResult:
        """Send a webhook notification.

        Args:
            url: Webhook endpoint URL
            payload: JSON payload to send
            method: HTTP method (POST, PUT, PATCH)
            headers: Custom HTTP headers
            secret: Optional secret for HMAC signature
            timeout: Request timeout (overrides default)
            max_retries: Max retry attempts (overrides default)
            retry_delay: Base retry delay (overrides default)

        Returns:
            WebhookResult with send status and response data
        """
        if not await self._circuit_breaker.can_execute():
            logger.warning(
                "Webhook circuit breaker open, rejecting send",
                extra={"url": url[:100], "method": method},
            )
            return WebhookResult(
                success=False,
                url=url,
                method=method,
                error="Circuit breaker is open",
            )

        timeout = timeout or self._timeout
        max_retries = max_retries or self._max_retries
        retry_delay = retry_delay or self._retry_delay

        start_time = time.monotonic()
        last_error: Exception | None = None
        client = await self._get_client()

        # Prepare headers
        request_headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            request_headers.update(headers)

        # Serialize payload
        payload_str = json.dumps(payload, default=str)

        # Add signature if secret provided
        if secret:
            signature = generate_webhook_signature(payload_str, secret)
            request_headers["X-Webhook-Signature"] = f"sha256={signature}"

        for attempt in range(max_retries):
            attempt_start = time.monotonic()

            try:
                logger.debug(
                    "Sending webhook",
                    extra={
                        "url": url[:100],
                        "method": method,
                        "payload_size": len(payload_str),
                        "retry_attempt": attempt,
                    },
                )

                # Make request
                response = await client.request(
                    method=method,
                    url=url,
                    content=payload_str,
                    headers=request_headers,
                    timeout=timeout,
                )

                duration_ms = (time.monotonic() - attempt_start) * 1000
                total_duration_ms = (time.monotonic() - start_time) * 1000

                # Parse response body
                response_body = None
                with contextlib.suppress(Exception):
                    response_body = response.json()

                # Handle response based on status code
                if response.status_code == 429:
                    # Rate limited
                    retry_after_str = response.headers.get("Retry-After")
                    retry_after = float(retry_after_str) if retry_after_str else None

                    logger.warning(
                        "Webhook rate limited",
                        extra={
                            "url": url[:100],
                            "status_code": 429,
                            "retry_after": retry_after,
                            "retry_attempt": attempt,
                        },
                    )
                    await self._circuit_breaker.record_failure()

                    # Retry if we have attempts left and retry-after is reasonable
                    if attempt < max_retries - 1 and retry_after and retry_after <= 60:
                        await asyncio.sleep(retry_after)
                        continue

                    return WebhookResult(
                        success=False,
                        url=url,
                        method=method,
                        status_code=429,
                        response_body=response_body,
                        error="Rate limit exceeded",
                        duration_ms=total_duration_ms,
                        retry_attempt=attempt,
                    )

                if response.status_code >= 500:
                    # Server error - retry
                    logger.warning(
                        "Webhook server error",
                        extra={
                            "url": url[:100],
                            "status_code": response.status_code,
                            "duration_ms": round(duration_ms, 2),
                            "retry_attempt": attempt,
                        },
                    )
                    await self._circuit_breaker.record_failure()

                    if attempt < max_retries - 1:
                        delay = retry_delay * (2**attempt)
                        logger.info(
                            f"Retrying webhook in {delay}s",
                            extra={
                                "url": url[:100],
                                "retry_attempt": attempt + 1,
                                "max_retries": max_retries,
                            },
                        )
                        await asyncio.sleep(delay)
                        continue

                    return WebhookResult(
                        success=False,
                        url=url,
                        method=method,
                        status_code=response.status_code,
                        response_body=response_body,
                        error=f"Server error ({response.status_code})",
                        duration_ms=total_duration_ms,
                        retry_attempt=attempt,
                    )

                if response.status_code >= 400:
                    # Client error - don't retry
                    logger.warning(
                        "Webhook client error",
                        extra={
                            "url": url[:100],
                            "status_code": response.status_code,
                            "response_body": str(response_body)[:200]
                            if response_body
                            else None,
                            "duration_ms": round(duration_ms, 2),
                            "retry_attempt": attempt,
                        },
                    )
                    return WebhookResult(
                        success=False,
                        url=url,
                        method=method,
                        status_code=response.status_code,
                        response_body=response_body,
                        error=f"Client error ({response.status_code})",
                        duration_ms=total_duration_ms,
                        retry_attempt=attempt,
                    )

                # Success (2xx)
                logger.debug(
                    "Webhook sent successfully",
                    extra={
                        "url": url[:100],
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                        "total_duration_ms": round(total_duration_ms, 2),
                        "retry_attempt": attempt,
                    },
                )

                await self._circuit_breaker.record_success()

                return WebhookResult(
                    success=True,
                    url=url,
                    method=method,
                    status_code=response.status_code,
                    response_body=response_body,
                    duration_ms=total_duration_ms,
                    retry_attempt=attempt,
                )

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.warning(
                    "Webhook request timed out",
                    extra={
                        "url": url[:100],
                        "timeout": timeout,
                        "duration_ms": round(duration_ms, 2),
                        "retry_attempt": attempt,
                    },
                )
                await self._circuit_breaker.record_failure()
                last_error = WebhookTimeoutError(f"Timeout after {timeout}s")

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    logger.info(
                        f"Retrying webhook in {delay}s",
                        extra={
                            "url": url[:100],
                            "retry_attempt": attempt + 1,
                            "max_retries": max_retries,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

            except httpx.ConnectError as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.warning(
                    "Webhook connection error",
                    extra={
                        "url": url[:100],
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "duration_ms": round(duration_ms, 2),
                        "retry_attempt": attempt,
                    },
                )
                await self._circuit_breaker.record_failure()
                last_error = WebhookConnectionError(f"Connection error: {e}")

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    logger.info(
                        f"Retrying webhook in {delay}s",
                        extra={
                            "url": url[:100],
                            "retry_attempt": attempt + 1,
                            "max_retries": max_retries,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

            except Exception as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.error(
                    "Webhook send failed",
                    extra={
                        "url": url[:100],
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "stack_trace": traceback.format_exc(),
                        "duration_ms": round(duration_ms, 2),
                        "retry_attempt": attempt,
                    },
                )
                await self._circuit_breaker.record_failure()
                last_error = e

                if attempt < max_retries - 1:
                    delay = retry_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    continue

        total_duration_ms = (time.monotonic() - start_time) * 1000
        return WebhookResult(
            success=False,
            url=url,
            method=method,
            error=str(last_error) if last_error else "Send failed after all retries",
            duration_ms=total_duration_ms,
            retry_attempt=max_retries - 1,
        )


# Global webhook client instance
_webhook_client: WebhookClient | None = None


def get_webhook_client() -> WebhookClient:
    """Get or create the global webhook client."""
    global _webhook_client
    if _webhook_client is None:
        _webhook_client = WebhookClient()
        logger.info("Webhook client initialized")
    return _webhook_client


async def close_webhook_client() -> None:
    """Close the global webhook client."""
    global _webhook_client
    if _webhook_client is not None:
        await _webhook_client.close()
        _webhook_client = None
