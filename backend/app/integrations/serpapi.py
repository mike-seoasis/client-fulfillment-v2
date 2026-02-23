"""SerpAPI integration client for Reddit post discovery.

Searches Google via SerpAPI with `site:reddit.com` queries to discover
Reddit posts matching project keywords.

Features:
- Async HTTP client using httpx (direct API calls)
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- 1-second rate limiting between requests
- Structured SerpResult dataclass for type-safe results
- Subreddit-scoped search support
- Time range filtering (24h, 7d, 30d)

Follows the same integration pattern as claude.py.
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# SerpAPI base URL
SERPAPI_URL = "https://serpapi.com/search"

# Time range mapping: user-friendly values to Google's tbs parameter
TIME_RANGE_MAP: dict[str, str] = {
    "24h": "qdr:d",
    "7d": "qdr:w",
    "30d": "qdr:m",
}

# Default number of results per search
DEFAULT_NUM_RESULTS = 20


@dataclass
class SerpResult:
    """A single Reddit post discovered via SerpAPI search."""

    url: str
    title: str
    snippet: str
    subreddit: str
    discovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    search_keyword: str = ""


class SerpAPIError(Exception):
    """Base exception for SerpAPI errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class SerpAPICircuitOpenError(SerpAPIError):
    """Raised when circuit breaker is open."""

    pass


class SerpAPIClient:
    """Async client for SerpAPI Google search.

    Provides Reddit post discovery with:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - 1-second rate limiting between requests
    - Structured result parsing
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit_delay: float = 1.0,
    ) -> None:
        """Initialize SerpAPI client.

        Args:
            api_key: SerpAPI key. Defaults to settings.
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts.
            retry_delay: Base delay between retries.
            rate_limit_delay: Minimum seconds between consecutive requests.
        """
        settings = get_settings()

        self._api_key = api_key or settings.serpapi_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._rate_limit_delay = rate_limit_delay

        # Circuit breaker (5 failures, 60s recovery — matches other integrations)
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0),
            name="serpapi",
        )

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None
        self._available = bool(self._api_key)

        # Rate limiting: track last request time
        self._last_request_time: float = 0.0

        logger.info(
            "SerpAPIClient instantiated",
            extra={
                "available": self._available,
                "has_api_key": bool(self._api_key),
                "timeout": self._timeout,
                "rate_limit_delay": self._rate_limit_delay,
            },
        )

    @property
    def available(self) -> bool:
        """Check if SerpAPI is configured and available."""
        return self._available

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("SerpAPI client closed")

    async def _rate_limit(self) -> None:
        """Enforce minimum delay between consecutive requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_delay:
            wait = self._rate_limit_delay - elapsed
            logger.debug(
                "Rate limiting SerpAPI request",
                extra={"wait_seconds": round(wait, 3)},
            )
            await asyncio.sleep(wait)
        self._last_request_time = time.monotonic()

    @staticmethod
    def _extract_subreddit(url: str) -> str:
        """Extract subreddit name from a Reddit URL.

        Args:
            url: Reddit URL like https://www.reddit.com/r/SkincareAddiction/comments/abc123/...

        Returns:
            Subreddit name (e.g. "SkincareAddiction") or "unknown" if parsing fails.
        """
        match = re.search(r"/r/([^/]+)", url)
        return match.group(1) if match else "unknown"

    @staticmethod
    def _is_reddit_post(url: str) -> bool:
        """Check if URL is an actual Reddit post (has /comments/ in path)."""
        return "reddit.com" in url and "/comments/" in url

    def _build_query(self, keyword: str, subreddit: str | None = None) -> str:
        """Build a Google search query for Reddit posts.

        Args:
            keyword: Search keyword.
            subreddit: Optional subreddit to scope the search.

        Returns:
            Formatted search query string.
        """
        if subreddit:
            return f'site:reddit.com/r/{subreddit} "{keyword}"'
        return f'site:reddit.com "{keyword}"'

    async def _execute_search(
        self,
        query: str,
        time_range: str | None = None,
        num_results: int = DEFAULT_NUM_RESULTS,
    ) -> list[SerpResult]:
        """Execute a single SerpAPI search with retries and circuit breaker.

        Args:
            query: The full search query string.
            time_range: Time filter (24h, 7d, 30d). None for no filter.
            num_results: Number of results to request.

        Returns:
            List of SerpResult objects for Reddit posts found.
        """
        if not self._available:
            logger.warning("SerpAPI not configured (missing API key)")
            return []

        if not await self._circuit_breaker.can_execute():
            logger.warning("SerpAPI circuit breaker is open, skipping request")
            return []

        # Build request parameters
        params: dict[str, Any] = {
            "q": query,
            "api_key": self._api_key,
            "engine": "google",
            "num": num_results,
        }

        if time_range and time_range in TIME_RANGE_MAP:
            params["tbs"] = TIME_RANGE_MAP[time_range]

        # Rate limit
        await self._rate_limit()

        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            attempt_start = time.monotonic()

            try:
                logger.info(
                    "SerpAPI search request",
                    extra={
                        "query": query,
                        "time_range": time_range,
                        "num_results": num_results,
                        "attempt": attempt + 1,
                    },
                )

                response = await client.get(SERPAPI_URL, params=params)
                duration_ms = (time.monotonic() - attempt_start) * 1000

                if response.status_code == 429:
                    logger.warning(
                        "SerpAPI rate limited",
                        extra={
                            "status_code": 429,
                            "duration_ms": round(duration_ms, 2),
                            "attempt": attempt + 1,
                        },
                    )
                    await self._circuit_breaker.record_failure()
                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    return []

                if response.status_code in (401, 403):
                    logger.error(
                        "SerpAPI authentication failed",
                        extra={
                            "status_code": response.status_code,
                            "duration_ms": round(duration_ms, 2),
                        },
                    )
                    await self._circuit_breaker.record_failure()
                    return []

                if response.status_code >= 500:
                    logger.warning(
                        "SerpAPI server error",
                        extra={
                            "status_code": response.status_code,
                            "duration_ms": round(duration_ms, 2),
                            "attempt": attempt + 1,
                        },
                    )
                    await self._circuit_breaker.record_failure()
                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2**attempt)
                        await asyncio.sleep(delay)
                        continue
                    return []

                if response.status_code >= 400:
                    error_body = response.json() if response.content else {}
                    logger.error(
                        "SerpAPI client error",
                        extra={
                            "status_code": response.status_code,
                            "error": error_body.get("error", "Unknown error"),
                            "duration_ms": round(duration_ms, 2),
                        },
                    )
                    return []

                # Success — parse results
                data = response.json()
                organic_results = data.get("organic_results", [])

                results: list[SerpResult] = []
                now = datetime.now(UTC)

                for item in organic_results:
                    link = item.get("link", "")
                    if self._is_reddit_post(link):
                        results.append(
                            SerpResult(
                                url=link,
                                title=item.get("title", ""),
                                snippet=item.get("snippet", ""),
                                subreddit=self._extract_subreddit(link),
                                discovered_at=now,
                            )
                        )

                await self._circuit_breaker.record_success()

                logger.info(
                    "SerpAPI search complete",
                    extra={
                        "query": query,
                        "total_organic": len(organic_results),
                        "reddit_posts_found": len(results),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

                return results

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.warning(
                    "SerpAPI request timed out",
                    extra={
                        "timeout": self._timeout,
                        "duration_ms": round(duration_ms, 2),
                        "attempt": attempt + 1,
                    },
                )
                await self._circuit_breaker.record_failure()
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                last_error = SerpAPIError(f"Request timed out after {self._timeout}s")

            except httpx.RequestError as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                logger.warning(
                    "SerpAPI request failed",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "duration_ms": round(duration_ms, 2),
                        "attempt": attempt + 1,
                    },
                )
                await self._circuit_breaker.record_failure()
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                last_error = SerpAPIError(f"Request failed: {e}")

        if last_error:
            logger.error(
                "SerpAPI request failed after all retries",
                extra={"error": str(last_error), "max_retries": self._max_retries},
            )
        return []

    async def search(
        self,
        keyword: str,
        subreddits: list[str] | None = None,
        time_range: str | None = "7d",
        num_results: int = DEFAULT_NUM_RESULTS,
    ) -> list[SerpResult]:
        """Search for Reddit posts matching a keyword.

        If subreddits are provided, runs a separate search for each subreddit
        and combines results. Otherwise, searches all of reddit.com.

        Args:
            keyword: The search keyword.
            subreddits: Optional list of subreddits to scope the search.
            time_range: Time filter — "24h", "7d", or "30d". Defaults to "7d".
            num_results: Number of results per search query.

        Returns:
            Combined list of SerpResult objects (may contain duplicates across
            subreddit searches — caller should deduplicate).
        """
        if not self._available:
            logger.warning("SerpAPI not configured, returning empty results")
            return []

        all_results: list[SerpResult] = []

        if subreddits:
            for subreddit in subreddits:
                query = self._build_query(keyword, subreddit)
                results = await self._execute_search(query, time_range, num_results)
                all_results.extend(results)
        else:
            query = self._build_query(keyword)
            results = await self._execute_search(query, time_range, num_results)
            all_results.extend(results)

        logger.info(
            "SerpAPI search batch complete",
            extra={
                "keyword": keyword,
                "subreddits": subreddits,
                "time_range": time_range,
                "total_results": len(all_results),
            },
        )

        return all_results


# ---------------------------------------------------------------------------
# Global client instance + lifecycle functions
# ---------------------------------------------------------------------------

serpapi_client: SerpAPIClient | None = None


async def init_serpapi() -> SerpAPIClient:
    """Initialize the global SerpAPI client.

    Returns:
        Initialized SerpAPIClient instance.
    """
    global serpapi_client
    if serpapi_client is None:
        serpapi_client = SerpAPIClient()
        if serpapi_client.available:
            logger.info("SerpAPI client initialized")
        else:
            logger.info("SerpAPI not configured (missing SERPAPI_KEY)")
    return serpapi_client


async def close_serpapi() -> None:
    """Close the global SerpAPI client."""
    global serpapi_client
    if serpapi_client:
        await serpapi_client.close()
        serpapi_client = None


async def get_serpapi() -> SerpAPIClient:
    """Dependency for getting the SerpAPI client.

    Usage:
        @app.get("/search")
        async def search_reddit(
            keyword: str,
            serpapi: SerpAPIClient = Depends(get_serpapi)
        ):
            results = await serpapi.search(keyword)
            ...
    """
    global serpapi_client
    if serpapi_client is None:
        await init_serpapi()
    return serpapi_client  # type: ignore[return-value]
