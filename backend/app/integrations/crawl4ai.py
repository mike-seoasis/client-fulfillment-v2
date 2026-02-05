"""Crawl4AI integration client with async support and circuit breaker pattern.

Features:
- Async HTTP client using httpx
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- Request/response logging per requirements
- Handles timeouts, rate limits (429), auth failures (401/403)
- Masks API tokens in all logs

ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Log API quota/credit usage if available
- Mask API keys and tokens in all logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- All API keys via environment variables (CRAWL4AI_API_TOKEN)
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
from app.core.logging import crawl4ai_logger, get_logger

logger = get_logger(__name__)


@dataclass
class CrawlResult:
    """Result of a crawl operation."""

    success: bool
    url: str
    html: str | None = None
    markdown: str | None = None
    cleaned_html: str | None = None
    links: list[dict[str, str]] = field(default_factory=list)
    images: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    status_code: int | None = None
    duration_ms: float = 0.0


@dataclass
class CrawlOptions:
    """Options for crawl operations."""

    # Content extraction
    word_count_threshold: int = 10
    excluded_tags: list[str] | None = None
    include_raw_html: bool = False

    # Browser behavior
    wait_for: str | None = None  # CSS selector to wait for
    delay_before_return_html: float = 0.0  # Seconds to wait after page load
    js_code: str | None = None  # JavaScript to execute

    # Caching
    bypass_cache: bool = False
    cache_mode: str | None = None  # "enabled", "disabled", "read_only", "write_only"

    # Screenshot
    screenshot: bool = False
    screenshot_wait_for: str | None = None

    # Anti-bot
    magic: bool = False  # Use anti-bot detection bypass
    simulate_user: bool = False

    # Session management
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert options to API request format."""
        result: dict[str, Any] = {
            "word_count_threshold": self.word_count_threshold,
            "include_raw_html": self.include_raw_html,
            "bypass_cache": self.bypass_cache,
        }

        if self.excluded_tags:
            result["excluded_tags"] = self.excluded_tags
        if self.wait_for:
            result["wait_for"] = self.wait_for
        if self.delay_before_return_html > 0:
            result["delay_before_return_html"] = self.delay_before_return_html
        if self.js_code:
            result["js_code"] = self.js_code
        if self.cache_mode:
            result["cache_mode"] = self.cache_mode
        if self.screenshot:
            result["screenshot"] = self.screenshot
            if self.screenshot_wait_for:
                result["screenshot_wait_for"] = self.screenshot_wait_for
        if self.magic:
            result["magic"] = self.magic
        if self.simulate_user:
            result["simulate_user"] = self.simulate_user
        if self.session_id:
            result["session_id"] = self.session_id

        return result


class Crawl4AIError(Exception):
    """Base exception for Crawl4AI errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class Crawl4AITimeoutError(Crawl4AIError):
    """Raised when a request times out."""

    pass


class Crawl4AIRateLimitError(Crawl4AIError):
    """Raised when rate limited (429)."""

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, status_code=429, response_body=response_body)
        self.retry_after = retry_after


class Crawl4AIAuthError(Crawl4AIError):
    """Raised when authentication fails (401/403)."""

    pass


class Crawl4AICircuitOpenError(Crawl4AIError):
    """Raised when circuit breaker is open."""

    pass


class Crawl4AIClient:
    """Async client for Crawl4AI API.

    Provides web crawling capabilities with:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Comprehensive logging
    - Railway deployment compatibility
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_token: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
    ) -> None:
        """Initialize Crawl4AI client.

        Args:
            api_url: Crawl4AI API base URL. Defaults to settings.
            api_token: API token for authentication. Defaults to settings.
            timeout: Request timeout in seconds. Defaults to settings.
            max_retries: Maximum retry attempts. Defaults to settings.
            retry_delay: Base delay between retries. Defaults to settings.
        """
        settings = get_settings()

        self._api_url = (api_url or settings.crawl4ai_api_url or "").rstrip("/")
        self._api_token = api_token or settings.crawl4ai_api_token
        self._timeout = timeout or settings.crawl4ai_timeout
        self._max_retries = max_retries or settings.crawl4ai_max_retries
        self._retry_delay = retry_delay or settings.crawl4ai_retry_delay

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.crawl4ai_circuit_failure_threshold,
                recovery_timeout=settings.crawl4ai_circuit_recovery_timeout,
            ),
            name="crawl4ai",
        )

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None
        self._available = bool(self._api_url)

    @property
    def available(self) -> bool:
        """Check if Crawl4AI is configured and available."""
        return self._available

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers: dict[str, str] = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if self._api_token:
                headers["Authorization"] = f"Bearer {self._api_token}"

            self._client = httpx.AsyncClient(
                base_url=self._api_url,
                headers=headers,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Crawl4AI client closed")

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: dict[str, Any] | None = None,
        target_url: str | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request with retry logic and circuit breaker.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            json: Request body as JSON
            target_url: Target URL being crawled (for logging)

        Returns:
            Response JSON as dict

        Raises:
            Crawl4AICircuitOpenError: If circuit breaker is open
            Crawl4AITimeoutError: If request times out
            Crawl4AIRateLimitError: If rate limited (429)
            Crawl4AIAuthError: If authentication fails (401/403)
            Crawl4AIError: For other errors
        """
        if not self._available:
            raise Crawl4AIError("Crawl4AI not configured (missing API URL)")

        if not await self._circuit_breaker.can_execute():
            crawl4ai_logger.graceful_fallback(endpoint, "Circuit breaker open")
            raise Crawl4AICircuitOpenError("Circuit breaker is open")

        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            start_time = time.monotonic()

            try:
                # Log request start
                crawl4ai_logger.api_call_start(
                    method, endpoint, url=target_url, retry_attempt=attempt
                )
                if json:
                    crawl4ai_logger.request_body(endpoint, json)

                # Make request
                response = await client.request(method, endpoint, json=json)
                duration_ms = (time.monotonic() - start_time) * 1000

                # Handle response based on status code
                if response.status_code == 429:
                    # Rate limited
                    retry_after = response.headers.get("Retry-After")
                    retry_after_int = int(retry_after) if retry_after else None
                    crawl4ai_logger.rate_limit(
                        endpoint, retry_after=retry_after_int, url=target_url
                    )
                    await self._circuit_breaker.record_failure()

                    # If we have retry attempts left and Retry-After is reasonable
                    if (
                        attempt < self._max_retries - 1
                        and retry_after_int
                        and retry_after_int <= 60
                    ):
                        await asyncio.sleep(retry_after_int)
                        continue

                    raise Crawl4AIRateLimitError(
                        "Rate limit exceeded",
                        retry_after=retry_after_int,
                        response_body=response.json() if response.content else None,
                    )

                if response.status_code in (401, 403):
                    # Auth failure
                    crawl4ai_logger.auth_failure(
                        endpoint, response.status_code, url=target_url
                    )
                    crawl4ai_logger.api_call_error(
                        method,
                        endpoint,
                        duration_ms,
                        response.status_code,
                        "Authentication failed",
                        "AuthError",
                        url=target_url,
                        retry_attempt=attempt,
                    )
                    await self._circuit_breaker.record_failure()
                    raise Crawl4AIAuthError(
                        f"Authentication failed ({response.status_code})",
                        status_code=response.status_code,
                    )

                if response.status_code >= 500:
                    # Server error - retry
                    error_msg = f"Server error ({response.status_code})"
                    crawl4ai_logger.api_call_error(
                        method,
                        endpoint,
                        duration_ms,
                        response.status_code,
                        error_msg,
                        "ServerError",
                        url=target_url,
                        retry_attempt=attempt,
                    )
                    await self._circuit_breaker.record_failure()

                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2**attempt)
                        logger.warning(
                            f"Crawl4AI request attempt {attempt + 1} failed, "
                            f"retrying in {delay}s",
                            extra={
                                "attempt": attempt + 1,
                                "max_retries": self._max_retries,
                                "delay_seconds": delay,
                                "status_code": response.status_code,
                            },
                        )
                        await asyncio.sleep(delay)
                        continue

                    raise Crawl4AIError(
                        error_msg,
                        status_code=response.status_code,
                        response_body=response.json() if response.content else None,
                    )

                if response.status_code >= 400:
                    # Client error - don't retry
                    error_body = response.json() if response.content else None
                    error_msg = (
                        error_body.get("error", str(error_body))
                        if error_body
                        else "Client error"
                    )
                    crawl4ai_logger.api_call_error(
                        method,
                        endpoint,
                        duration_ms,
                        response.status_code,
                        error_msg,
                        "ClientError",
                        url=target_url,
                        retry_attempt=attempt,
                    )
                    raise Crawl4AIError(
                        f"Client error ({response.status_code}): {error_msg}",
                        status_code=response.status_code,
                        response_body=error_body,
                    )

                # Success
                response_data = response.json() if response.content else {}
                crawl4ai_logger.api_call_success(
                    method, endpoint, duration_ms, response.status_code, url=target_url
                )
                crawl4ai_logger.response_body(endpoint, response_data, duration_ms)
                await self._circuit_breaker.record_success()
                return response_data

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - start_time) * 1000
                crawl4ai_logger.timeout(endpoint, self._timeout, url=target_url)
                crawl4ai_logger.api_call_error(
                    method,
                    endpoint,
                    duration_ms,
                    None,
                    "Request timed out",
                    "TimeoutError",
                    url=target_url,
                    retry_attempt=attempt,
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"Crawl4AI request attempt {attempt + 1} timed out, "
                        f"retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                last_error = Crawl4AITimeoutError(
                    f"Request timed out after {self._timeout}s"
                )

            except httpx.RequestError as e:
                duration_ms = (time.monotonic() - start_time) * 1000
                crawl4ai_logger.api_call_error(
                    method,
                    endpoint,
                    duration_ms,
                    None,
                    str(e),
                    type(e).__name__,
                    url=target_url,
                    retry_attempt=attempt,
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"Crawl4AI request attempt {attempt + 1} failed, "
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

                last_error = Crawl4AIError(f"Request failed: {e}")

        if last_error:
            raise last_error
        raise Crawl4AIError("Request failed after all retries")

    async def health_check(self) -> bool:
        """Check if Crawl4AI API is healthy.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self._available:
            return False

        try:
            await self._request("GET", "/health")
            return True
        except Crawl4AIError:
            return False

    async def _simple_crawl(self, url: str) -> CrawlResult:
        """Simple httpx-based crawl fallback when Crawl4AI API is not configured.

        Args:
            url: URL to crawl

        Returns:
            CrawlResult with HTML content (no markdown conversion)
        """
        start_time = time.monotonic()
        logger.info(f"Using simple httpx crawl for {url} (Crawl4AI not configured)")

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True,
            ) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    },
                )
                duration_ms = (time.monotonic() - start_time) * 1000

                if response.status_code >= 400:
                    return CrawlResult(
                        success=False,
                        url=url,
                        error=f"HTTP {response.status_code}",
                        status_code=response.status_code,
                        duration_ms=duration_ms,
                    )

                html = response.text
                return CrawlResult(
                    success=True,
                    url=url,
                    html=html,
                    markdown=None,  # Simple crawl doesn't convert to markdown
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )

        except httpx.TimeoutException:
            duration_ms = (time.monotonic() - start_time) * 1000
            return CrawlResult(
                success=False,
                url=url,
                error=f"Request timed out after {self._timeout}s",
                duration_ms=duration_ms,
            )
        except httpx.RequestError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            return CrawlResult(
                success=False,
                url=url,
                error=str(e),
                duration_ms=duration_ms,
            )

    async def crawl(
        self,
        url: str,
        options: CrawlOptions | None = None,
    ) -> CrawlResult:
        """Crawl a single URL.

        Args:
            url: URL to crawl
            options: Crawl options

        Returns:
            CrawlResult with extracted content
        """
        # Use simple httpx fallback if Crawl4AI API is not configured
        if not self._available:
            return await self._simple_crawl(url)

        start_time = time.monotonic()
        options = options or CrawlOptions()

        crawl4ai_logger.crawl_start(url, options.to_dict())

        try:
            request_body = {
                "urls": [url],  # Crawl4AI expects a list even for single URL
                **options.to_dict(),
            }

            response = await self._request(
                "POST", "/crawl", json=request_body, target_url=url
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Extract result from response (API returns "results" plural)
            result_data = response.get("results") or response.get("result") or response

            # Handle both single result and list of results
            if isinstance(result_data, list) and len(result_data) > 0:
                result_data = result_data[0]

            crawl_result = CrawlResult(
                success=result_data.get("success", True),
                url=url,
                html=result_data.get("html"),
                markdown=result_data.get("markdown"),
                cleaned_html=result_data.get("cleaned_html"),
                links=result_data.get("links", []),
                images=result_data.get("images", []),
                metadata=result_data.get("metadata", {}),
                error=result_data.get("error"),
                status_code=result_data.get("status_code"),
                duration_ms=duration_ms,
            )

            crawl4ai_logger.crawl_complete(
                url, duration_ms, crawl_result.success, pages_crawled=1
            )

            return crawl_result

        except Crawl4AIError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            crawl4ai_logger.crawl_complete(url, duration_ms, success=False)
            return CrawlResult(
                success=False,
                url=url,
                error=str(e),
                status_code=e.status_code,
                duration_ms=duration_ms,
            )

    async def crawl_many(
        self,
        urls: list[str],
        options: CrawlOptions | None = None,
    ) -> list[CrawlResult]:
        """Crawl multiple URLs.

        Args:
            urls: List of URLs to crawl
            options: Crawl options (applied to all URLs)

        Returns:
            List of CrawlResult objects
        """
        start_time = time.monotonic()
        options = options or CrawlOptions()

        crawl4ai_logger.crawl_start(
            f"batch ({len(urls)} URLs)", {"urls": urls[:5], **options.to_dict()}
        )

        try:
            request_body = {
                "urls": urls,
                **options.to_dict(),
            }

            response = await self._request(
                "POST",
                "/crawl",
                json=request_body,
                target_url=f"batch ({len(urls)} URLs)",
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Extract results from response
            results_data = response.get("results", response.get("result", []))
            if not isinstance(results_data, list):
                results_data = [results_data]

            results: list[CrawlResult] = []
            for i, result_data in enumerate(results_data):
                result_url = result_data.get(
                    "url", urls[i] if i < len(urls) else "unknown"
                )
                results.append(
                    CrawlResult(
                        success=result_data.get("success", True),
                        url=result_url,
                        html=result_data.get("html"),
                        markdown=result_data.get("markdown"),
                        cleaned_html=result_data.get("cleaned_html"),
                        links=result_data.get("links", []),
                        images=result_data.get("images", []),
                        metadata=result_data.get("metadata", {}),
                        error=result_data.get("error"),
                        status_code=result_data.get("status_code"),
                        duration_ms=result_data.get("duration_ms", 0),
                    )
                )

            success_count = sum(1 for r in results if r.success)
            crawl4ai_logger.crawl_complete(
                f"batch ({len(urls)} URLs)",
                duration_ms,
                success=success_count == len(urls),
                pages_crawled=success_count,
            )

            return results

        except Crawl4AIError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            crawl4ai_logger.crawl_complete(
                f"batch ({len(urls)} URLs)", duration_ms, success=False
            )
            # Return error result for each URL
            return [
                CrawlResult(
                    success=False,
                    url=url,
                    error=str(e),
                    status_code=e.status_code,
                    duration_ms=duration_ms / len(urls) if urls else 0,
                )
                for url in urls
            ]

    async def extract_markdown(
        self,
        url: str,
        options: CrawlOptions | None = None,
    ) -> str | None:
        """Convenience method to crawl and return markdown content.

        Args:
            url: URL to crawl
            options: Crawl options

        Returns:
            Markdown content or None if crawl failed
        """
        result = await self.crawl(url, options)
        return result.markdown if result.success else None

    async def get_links(
        self,
        url: str,
        options: CrawlOptions | None = None,
    ) -> list[dict[str, str]]:
        """Convenience method to crawl and return links.

        Args:
            url: URL to crawl
            options: Crawl options

        Returns:
            List of links (each with 'href' and 'text' keys)
        """
        result = await self.crawl(url, options)
        return result.links if result.success else []


# Global Crawl4AI client instance
crawl4ai_client: Crawl4AIClient | None = None


async def init_crawl4ai() -> Crawl4AIClient:
    """Initialize the global Crawl4AI client.

    Returns:
        Initialized Crawl4AIClient instance
    """
    global crawl4ai_client
    if crawl4ai_client is None:
        crawl4ai_client = Crawl4AIClient()
        if crawl4ai_client.available:
            logger.info("Crawl4AI client initialized")
        else:
            logger.info("Crawl4AI not configured (missing API URL)")
    return crawl4ai_client


async def close_crawl4ai() -> None:
    """Close the global Crawl4AI client."""
    global crawl4ai_client
    if crawl4ai_client:
        await crawl4ai_client.close()
        crawl4ai_client = None


async def get_crawl4ai() -> Crawl4AIClient:
    """Dependency for getting Crawl4AI client.

    Usage:
        @app.get("/crawl")
        async def crawl_url(
            url: str,
            crawl4ai: Crawl4AIClient = Depends(get_crawl4ai)
        ):
            result = await crawl4ai.crawl(url)
            ...
    """
    global crawl4ai_client
    if crawl4ai_client is None:
        await init_crawl4ai()
    return crawl4ai_client  # type: ignore[return-value]
