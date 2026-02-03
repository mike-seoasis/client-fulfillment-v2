"""Keywords Everywhere API integration client for keyword data.

Features:
- Async HTTP client using httpx (direct API calls)
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- Request/response logging per requirements
- Handles timeouts, rate limits (429), auth failures (401/403)
- Masks API keys in all logs
- Credit usage logging for quota tracking
- Batch processing for large keyword lists (max 100 per request)

ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Log API quota/credit usage if available
- Mask API keys and tokens in all logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- All API keys via environment variables (KEYWORDS_EVERYWHERE_API_KEY)
- Never log or expose API keys
- Handle cold-start latency (first request may be slow)
- Implement request timeouts (Railway has 5min request limit)
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import get_logger, keywords_everywhere_logger

logger = get_logger(__name__)

# Keywords Everywhere API base URL
KEYWORDS_EVERYWHERE_API_URL = "https://api.keywordseverywhere.com"

# Maximum keywords per request (API limit)
MAX_KEYWORDS_PER_REQUEST = 100


@dataclass
class KeywordData:
    """Data for a single keyword."""

    keyword: str
    volume: int | None = None
    cpc: float | None = None
    competition: float | None = None
    trend: list[int] | None = None
    error: str | None = None


@dataclass
class KeywordDataResult:
    """Result of a keyword data lookup operation."""

    success: bool
    keywords: list[KeywordData] = field(default_factory=list)
    error: str | None = None
    credits_used: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


class KeywordsEverywhereError(Exception):
    """Base exception for Keywords Everywhere API errors."""

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


class KeywordsEverywhereTimeoutError(KeywordsEverywhereError):
    """Raised when a request times out."""

    pass


class KeywordsEverywhereRateLimitError(KeywordsEverywhereError):
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


class KeywordsEverywhereAuthError(KeywordsEverywhereError):
    """Raised when authentication fails (401/403)."""

    pass


class KeywordsEverywhereCircuitOpenError(KeywordsEverywhereError):
    """Raised when circuit breaker is open."""

    pass


class KeywordsEverywhereClient:
    """Async client for Keywords Everywhere API.

    Provides keyword data capabilities:
    - Search volume
    - Cost per click (CPC)
    - Competition data
    - Trend data (12 months)

    Features:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Comprehensive logging
    - Railway deployment compatibility
    - Batch processing for large keyword lists
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        default_country: str | None = None,
        default_currency: str | None = None,
        default_data_source: str | None = None,
    ) -> None:
        """Initialize Keywords Everywhere client.

        Args:
            api_key: Keywords Everywhere API key. Defaults to settings.
            timeout: Request timeout in seconds. Defaults to settings.
            max_retries: Maximum retry attempts. Defaults to settings.
            retry_delay: Base delay between retries. Defaults to settings.
            default_country: Default country code. Defaults to settings.
            default_currency: Default currency code. Defaults to settings.
            default_data_source: Default data source (gkp/cli). Defaults to settings.
        """
        settings = get_settings()

        self._api_key = api_key or settings.keywords_everywhere_api_key
        self._timeout = timeout or settings.keywords_everywhere_timeout
        self._max_retries = max_retries or settings.keywords_everywhere_max_retries
        self._retry_delay = retry_delay or settings.keywords_everywhere_retry_delay
        self._default_country = (
            default_country or settings.keywords_everywhere_default_country
        )
        self._default_currency = (
            default_currency or settings.keywords_everywhere_default_currency
        )
        self._default_data_source = (
            default_data_source or settings.keywords_everywhere_default_data_source
        )

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.keywords_everywhere_circuit_failure_threshold,
                recovery_timeout=settings.keywords_everywhere_circuit_recovery_timeout,
            ),
            name="keywords_everywhere",
        )

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None
        self._available = bool(self._api_key)

    @property
    def available(self) -> bool:
        """Check if Keywords Everywhere is configured and available."""
        return self._available

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers: dict[str, str] = {
                "Accept": "application/json",
            }
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            self._client = httpx.AsyncClient(
                base_url=KEYWORDS_EVERYWHERE_API_URL,
                headers=headers,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Keywords Everywhere client closed")

    async def get_keyword_data(
        self,
        keywords: list[str],
        country: str | None = None,
        currency: str | None = None,
        data_source: str | None = None,
    ) -> KeywordDataResult:
        """Get keyword data for a list of keywords.

        Args:
            keywords: List of keywords to lookup (max 100 per request)
            country: Country code (e.g., 'us', 'uk'). Defaults to settings.
            currency: Currency code (e.g., 'USD', 'GBP'). Defaults to settings.
            data_source: Data source ('gkp' or 'cli'). Defaults to settings.

        Returns:
            KeywordDataResult with keyword data, credits used, and metadata
        """
        if not self._available:
            return KeywordDataResult(
                success=False,
                error="Keywords Everywhere not configured (missing API key)",
            )

        if not keywords:
            return KeywordDataResult(
                success=False,
                error="No keywords provided",
            )

        if len(keywords) > MAX_KEYWORDS_PER_REQUEST:
            return KeywordDataResult(
                success=False,
                error=f"Too many keywords ({len(keywords)}), max {MAX_KEYWORDS_PER_REQUEST} per request",
            )

        if not await self._circuit_breaker.can_execute():
            keywords_everywhere_logger.graceful_fallback(
                "get_keyword_data", "Circuit breaker open"
            )
            return KeywordDataResult(
                success=False,
                error="Circuit breaker is open",
            )

        start_time = time.monotonic()
        client = await self._get_client()
        last_error: Exception | None = None
        request_id: str | None = None

        # Use defaults if not specified
        country = country or self._default_country
        currency = currency or self._default_currency
        data_source = data_source or self._default_data_source

        # Log operation start
        keywords_everywhere_logger.keyword_lookup_start(len(keywords), country)

        # Build request body (form data format for Keywords Everywhere API)
        request_data: dict[str, Any] = {
            "country": country,
            "currency": currency,
            "dataSource": data_source,
        }
        # Keywords are sent as kw[] array
        for kw in keywords:
            if "kw[]" not in request_data:
                request_data["kw[]"] = []
            request_data["kw[]"].append(kw)

        endpoint = "/v1/get_keyword_data"

        for attempt in range(self._max_retries):
            attempt_start = time.monotonic()

            try:
                # Log request start
                keywords_everywhere_logger.api_call_start(
                    endpoint,
                    len(keywords),
                    retry_attempt=attempt,
                    request_id=request_id,
                )
                keywords_everywhere_logger.request_body(
                    endpoint, keywords, country, data_source
                )

                # Make request (form data format)
                response = await client.post(
                    endpoint,
                    data=request_data,
                )
                duration_ms = (time.monotonic() - attempt_start) * 1000

                # Extract request ID from response headers
                request_id = response.headers.get("x-request-id")

                # Handle response based on status code
                if response.status_code == 429:
                    # Rate limited
                    retry_after_str = response.headers.get("retry-after")
                    retry_after = float(retry_after_str) if retry_after_str else None
                    keywords_everywhere_logger.rate_limit(
                        endpoint, retry_after=retry_after, request_id=request_id
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

                    total_duration_ms = (time.monotonic() - start_time) * 1000
                    keywords_everywhere_logger.keyword_lookup_complete(
                        len(keywords), total_duration_ms, success=False
                    )
                    return KeywordDataResult(
                        success=False,
                        error="Rate limit exceeded",
                        request_id=request_id,
                        duration_ms=total_duration_ms,
                    )

                if response.status_code in (401, 403):
                    # Auth failure
                    keywords_everywhere_logger.auth_failure(response.status_code)
                    keywords_everywhere_logger.api_call_error(
                        endpoint,
                        duration_ms,
                        response.status_code,
                        "Authentication failed",
                        "AuthError",
                        retry_attempt=attempt,
                        request_id=request_id,
                    )
                    await self._circuit_breaker.record_failure()
                    total_duration_ms = (time.monotonic() - start_time) * 1000
                    keywords_everywhere_logger.keyword_lookup_complete(
                        len(keywords), total_duration_ms, success=False
                    )
                    return KeywordDataResult(
                        success=False,
                        error=f"Authentication failed ({response.status_code})",
                        request_id=request_id,
                        duration_ms=total_duration_ms,
                    )

                if response.status_code >= 500:
                    # Server error - retry
                    error_msg = f"Server error ({response.status_code})"
                    keywords_everywhere_logger.api_call_error(
                        endpoint,
                        duration_ms,
                        response.status_code,
                        error_msg,
                        "ServerError",
                        retry_attempt=attempt,
                        request_id=request_id,
                    )
                    await self._circuit_breaker.record_failure()

                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2**attempt)
                        logger.warning(
                            f"Keywords Everywhere request attempt {attempt + 1} failed, "
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

                    total_duration_ms = (time.monotonic() - start_time) * 1000
                    keywords_everywhere_logger.keyword_lookup_complete(
                        len(keywords), total_duration_ms, success=False
                    )
                    return KeywordDataResult(
                        success=False,
                        error=error_msg,
                        request_id=request_id,
                        duration_ms=total_duration_ms,
                    )

                if response.status_code >= 400:
                    # Client error - don't retry
                    error_body = response.json() if response.content else None
                    error_msg = (
                        error_body.get("error", str(error_body))
                        if error_body and isinstance(error_body, dict)
                        else "Client error"
                    )
                    keywords_everywhere_logger.api_call_error(
                        endpoint,
                        duration_ms,
                        response.status_code,
                        error_msg,
                        "ClientError",
                        retry_attempt=attempt,
                        request_id=request_id,
                    )
                    total_duration_ms = (time.monotonic() - start_time) * 1000
                    keywords_everywhere_logger.keyword_lookup_complete(
                        len(keywords), total_duration_ms, success=False
                    )
                    return KeywordDataResult(
                        success=False,
                        error=f"Client error ({response.status_code}): {error_msg}",
                        request_id=request_id,
                        duration_ms=total_duration_ms,
                    )

                # Success - parse response
                response_data = response.json()
                total_duration_ms = (time.monotonic() - start_time) * 1000

                # Extract keyword data from response
                keyword_results: list[KeywordData] = []
                data = response_data.get("data", [])

                for item in data:
                    kw = item.get("keyword", "")
                    vol = item.get("vol")
                    cpc_data = item.get("cpc", {})
                    cpc = (
                        cpc_data.get("value")
                        if isinstance(cpc_data, dict)
                        else cpc_data
                    )
                    competition = item.get("competition")
                    trend = item.get("trend")

                    keyword_results.append(
                        KeywordData(
                            keyword=kw,
                            volume=vol,
                            cpc=float(cpc) if cpc is not None else None,
                            competition=float(competition)
                            if competition is not None
                            else None,
                            trend=trend if isinstance(trend, list) else None,
                        )
                    )

                # Extract credits used from response if available
                credits_used = response_data.get("credits")

                # Log success
                keywords_everywhere_logger.api_call_success(
                    endpoint,
                    duration_ms,
                    len(keywords),
                    credits_used=credits_used,
                    request_id=request_id,
                )
                keywords_everywhere_logger.response_body(
                    endpoint,
                    len(keyword_results),
                    duration_ms,
                    credits_used=credits_used,
                )

                # Log credit usage if available
                if credits_used is not None:
                    credits_remaining = response_data.get("credits_remaining")
                    keywords_everywhere_logger.credit_usage(
                        credits_used, credits_remaining
                    )

                await self._circuit_breaker.record_success()

                keywords_everywhere_logger.keyword_lookup_complete(
                    len(keywords),
                    total_duration_ms,
                    success=True,
                    results_count=len(keyword_results),
                )

                return KeywordDataResult(
                    success=True,
                    keywords=keyword_results,
                    credits_used=credits_used,
                    request_id=request_id,
                    duration_ms=total_duration_ms,
                )

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                keywords_everywhere_logger.timeout(endpoint, self._timeout)
                keywords_everywhere_logger.api_call_error(
                    endpoint,
                    duration_ms,
                    None,
                    "Request timed out",
                    "TimeoutError",
                    retry_attempt=attempt,
                    request_id=request_id,
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"Keywords Everywhere request attempt {attempt + 1} timed out, "
                        f"retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                last_error = KeywordsEverywhereTimeoutError(
                    f"Request timed out after {self._timeout}s"
                )

            except httpx.RequestError as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                keywords_everywhere_logger.api_call_error(
                    endpoint,
                    duration_ms,
                    None,
                    str(e),
                    type(e).__name__,
                    retry_attempt=attempt,
                    request_id=request_id,
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"Keywords Everywhere request attempt {attempt + 1} failed, "
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

                last_error = KeywordsEverywhereError(f"Request failed: {e}")

        total_duration_ms = (time.monotonic() - start_time) * 1000
        keywords_everywhere_logger.keyword_lookup_complete(
            len(keywords), total_duration_ms, success=False
        )
        if last_error:
            return KeywordDataResult(
                success=False,
                error=str(last_error),
                duration_ms=total_duration_ms,
                request_id=request_id,
            )
        return KeywordDataResult(
            success=False,
            error="Request failed after all retries",
            duration_ms=total_duration_ms,
            request_id=request_id,
        )

    async def get_keyword_data_batch(
        self,
        keywords: list[str],
        country: str | None = None,
        currency: str | None = None,
        data_source: str | None = None,
        max_concurrent: int = 5,
    ) -> KeywordDataResult:
        """Get keyword data for a large list of keywords in batches.

        Automatically splits keywords into batches of 100 (API limit) and
        processes them with controlled concurrency.

        Args:
            keywords: List of keywords to lookup (any size)
            country: Country code (e.g., 'us', 'uk'). Defaults to settings.
            currency: Currency code (e.g., 'USD', 'GBP'). Defaults to settings.
            data_source: Data source ('gkp' or 'cli'). Defaults to settings.
            max_concurrent: Maximum concurrent batch requests. Defaults to 5.

        Returns:
            KeywordDataResult with combined keyword data from all batches
        """
        if not keywords:
            return KeywordDataResult(
                success=False,
                error="No keywords provided",
            )

        # If within single batch limit, use regular method
        if len(keywords) <= MAX_KEYWORDS_PER_REQUEST:
            return await self.get_keyword_data(keywords, country, currency, data_source)

        start_time = time.monotonic()

        # Split into batches
        batches: list[list[str]] = []
        for i in range(0, len(keywords), MAX_KEYWORDS_PER_REQUEST):
            batches.append(keywords[i : i + MAX_KEYWORDS_PER_REQUEST])

        total_batches = len(batches)
        logger.info(
            f"Processing {len(keywords)} keywords in {total_batches} batches",
            extra={
                "total_keywords": len(keywords),
                "total_batches": total_batches,
                "batch_size": MAX_KEYWORDS_PER_REQUEST,
                "max_concurrent": max_concurrent,
            },
        )

        # Process batches with controlled concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        all_keywords: list[KeywordData] = []
        total_credits = 0
        errors: list[str] = []

        async def process_batch(
            batch_index: int, batch: list[str]
        ) -> tuple[int, KeywordDataResult]:
            """Process a single batch with semaphore control."""
            async with semaphore:
                keywords_everywhere_logger.batch_start(
                    batch_index, len(batch), total_batches, len(keywords)
                )
                result = await self.get_keyword_data(
                    batch, country, currency, data_source
                )
                return batch_index, result

        # Create tasks for all batches
        tasks = [process_batch(i, batch) for i, batch in enumerate(batches)]

        # Execute all tasks
        results = await asyncio.gather(*tasks)

        # Sort by batch index and combine results
        results_sorted = sorted(results, key=lambda x: x[0])
        for batch_index, result in results_sorted:
            batch_size = len(batches[batch_index])

            if result.success:
                all_keywords.extend(result.keywords)
                if result.credits_used:
                    total_credits += result.credits_used
                keywords_everywhere_logger.batch_complete(
                    batch_index,
                    batch_size,
                    total_batches,
                    len(result.keywords),
                    result.duration_ms,
                    credits_used=result.credits_used,
                )
            else:
                errors.append(f"Batch {batch_index + 1}: {result.error}")
                keywords_everywhere_logger.batch_complete(
                    batch_index,
                    batch_size,
                    total_batches,
                    0,
                    result.duration_ms,
                    credits_used=None,
                )

        total_duration_ms = (time.monotonic() - start_time) * 1000

        if errors and not all_keywords:
            # All batches failed
            return KeywordDataResult(
                success=False,
                error="; ".join(errors),
                duration_ms=total_duration_ms,
            )

        # Partial or full success
        return KeywordDataResult(
            success=True,
            keywords=all_keywords,
            credits_used=total_credits if total_credits > 0 else None,
            error="; ".join(errors) if errors else None,
            duration_ms=total_duration_ms,
        )


# Global Keywords Everywhere client instance
keywords_everywhere_client: KeywordsEverywhereClient | None = None


async def init_keywords_everywhere() -> KeywordsEverywhereClient:
    """Initialize the global Keywords Everywhere client.

    Returns:
        Initialized KeywordsEverywhereClient instance
    """
    global keywords_everywhere_client
    if keywords_everywhere_client is None:
        keywords_everywhere_client = KeywordsEverywhereClient()
        if keywords_everywhere_client.available:
            logger.info("Keywords Everywhere client initialized")
        else:
            logger.info("Keywords Everywhere not configured (missing API key)")
    return keywords_everywhere_client


async def close_keywords_everywhere() -> None:
    """Close the global Keywords Everywhere client."""
    global keywords_everywhere_client
    if keywords_everywhere_client:
        await keywords_everywhere_client.close()
        keywords_everywhere_client = None


async def get_keywords_everywhere() -> KeywordsEverywhereClient:
    """Dependency for getting Keywords Everywhere client.

    Usage:
        @app.get("/keywords")
        async def get_keywords(
            keywords: list[str],
            client: KeywordsEverywhereClient = Depends(get_keywords_everywhere)
        ):
            result = await client.get_keyword_data(keywords)
            ...
    """
    global keywords_everywhere_client
    if keywords_everywhere_client is None:
        await init_keywords_everywhere()
    return keywords_everywhere_client  # type: ignore[return-value]
