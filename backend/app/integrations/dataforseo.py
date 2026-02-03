"""DataForSEO API integration client for SERP and keyword data.

Features:
- Async HTTP client using httpx (direct API calls)
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- Request/response logging per requirements
- Handles timeouts, rate limits (429), auth failures (401/403)
- Masks API credentials in all logs
- Cost usage logging for quota tracking
- Batch processing for large keyword lists (max 1000 per request)

DataForSEO provides:
- Keyword search volume data
- SERP (Search Engine Results Page) data
- Keyword suggestions
- Domain rankings
- And more...

ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Log API quota/cost usage if available
- Mask API credentials in all logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- All API credentials via environment variables (DATAFORSEO_API_LOGIN, DATAFORSEO_API_PASSWORD)
- Never log or expose API credentials
- Handle cold-start latency (first request may be slow)
- Implement request timeouts (Railway has 5min request limit)
"""

import asyncio
import base64
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import dataforseo_logger, get_logger

logger = get_logger(__name__)

# DataForSEO API base URL
DATAFORSEO_API_URL = "https://api.dataforseo.com"

# Maximum keywords per request (DataForSEO limit is 1000 for most endpoints)
MAX_KEYWORDS_PER_REQUEST = 1000

# Maximum tasks per batch request
MAX_TASKS_PER_REQUEST = 100


@dataclass
class KeywordVolumeData:
    """Search volume data for a single keyword."""

    keyword: str
    search_volume: int | None = None
    cpc: float | None = None
    competition: float | None = None
    competition_level: str | None = None
    monthly_searches: list[dict[str, Any]] | None = None
    error: str | None = None


@dataclass
class KeywordVolumeResult:
    """Result of a keyword volume lookup operation."""

    success: bool
    keywords: list[KeywordVolumeData] = field(default_factory=list)
    error: str | None = None
    cost: float | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


@dataclass
class SerpResult:
    """A single SERP result item."""

    position: int
    url: str
    title: str
    description: str | None = None
    domain: str | None = None


@dataclass
class SerpSearchResult:
    """Result of a SERP search operation."""

    success: bool
    keyword: str
    results: list[SerpResult] = field(default_factory=list)
    total_results: int | None = None
    error: str | None = None
    cost: float | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


class DataForSEOError(Exception):
    """Base exception for DataForSEO API errors."""

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


class DataForSEOTimeoutError(DataForSEOError):
    """Raised when a request times out."""

    pass


class DataForSEORateLimitError(DataForSEOError):
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


class DataForSEOAuthError(DataForSEOError):
    """Raised when authentication fails (401/403)."""

    pass


class DataForSEOCircuitOpenError(DataForSEOError):
    """Raised when circuit breaker is open."""

    pass


class DataForSEOClient:
    """Async client for DataForSEO API.

    Provides keyword and SERP data capabilities:
    - Keyword search volume
    - Cost per click (CPC)
    - Competition data
    - SERP results
    - Keyword suggestions

    Features:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Comprehensive logging
    - Railway deployment compatibility
    - Batch processing for large keyword lists

    Authentication:
    DataForSEO uses HTTP Basic Auth with login (email) and password.
    """

    def __init__(
        self,
        api_login: str | None = None,
        api_password: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        default_location_code: int | None = None,
        default_language_code: str | None = None,
    ) -> None:
        """Initialize DataForSEO client.

        Args:
            api_login: DataForSEO API login (email). Defaults to settings.
            api_password: DataForSEO API password. Defaults to settings.
            timeout: Request timeout in seconds. Defaults to settings.
            max_retries: Maximum retry attempts. Defaults to settings.
            retry_delay: Base delay between retries. Defaults to settings.
            default_location_code: Default location code (2840=US). Defaults to settings.
            default_language_code: Default language code. Defaults to settings.
        """
        settings = get_settings()

        self._api_login = api_login or settings.dataforseo_api_login
        self._api_password = api_password or settings.dataforseo_api_password
        self._timeout = timeout or settings.dataforseo_timeout
        self._max_retries = max_retries or settings.dataforseo_max_retries
        self._retry_delay = retry_delay or settings.dataforseo_retry_delay
        self._default_location_code = (
            default_location_code or settings.dataforseo_default_location_code
        )
        self._default_language_code = (
            default_language_code or settings.dataforseo_default_language_code
        )

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.dataforseo_circuit_failure_threshold,
                recovery_timeout=settings.dataforseo_circuit_recovery_timeout,
            ),
            name="dataforseo",
        )

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None
        self._available = bool(self._api_login and self._api_password)

    @property
    def available(self) -> bool:
        """Check if DataForSEO is configured and available."""
        return self._available

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    def _get_auth_header(self) -> str:
        """Generate Basic Auth header value."""
        credentials = f"{self._api_login}:{self._api_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers: dict[str, str] = {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            if self._api_login and self._api_password:
                headers["Authorization"] = self._get_auth_header()

            self._client = httpx.AsyncClient(
                base_url=DATAFORSEO_API_URL,
                headers=headers,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("DataForSEO client closed")

    async def _make_request(
        self,
        endpoint: str,
        payload: list[dict[str, Any]],
        method: str = "POST",
    ) -> tuple[dict[str, Any], str]:
        """Make an HTTP request to DataForSEO API with retry logic.

        Args:
            endpoint: API endpoint path
            payload: Request payload (list of tasks)
            method: HTTP method

        Returns:
            Tuple of (response_data, request_id)

        Raises:
            DataForSEOError: On API errors
            DataForSEOTimeoutError: On timeout
            DataForSEORateLimitError: On rate limit (429)
            DataForSEOAuthError: On auth failure (401/403)
            DataForSEOCircuitOpenError: When circuit breaker is open
        """
        request_id = str(uuid.uuid4())[:8]

        if not self._available:
            raise DataForSEOError(
                "DataForSEO not configured (missing API credentials)",
                request_id=request_id,
            )

        if not await self._circuit_breaker.can_execute():
            dataforseo_logger.graceful_fallback(endpoint, "Circuit breaker open")
            raise DataForSEOCircuitOpenError(
                "Circuit breaker is open",
                request_id=request_id,
            )

        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            attempt_start = time.monotonic()

            try:
                # Log request start
                dataforseo_logger.api_call_start(
                    endpoint,
                    method=method,
                    retry_attempt=attempt,
                    request_id=request_id,
                )
                dataforseo_logger.request_body(endpoint, payload)

                # Make request
                response = await client.request(
                    method,
                    endpoint,
                    json=payload,
                )
                duration_ms = (time.monotonic() - attempt_start) * 1000

                # Handle response based on status code
                if response.status_code == 429:
                    # Rate limited
                    retry_after_str = response.headers.get("retry-after")
                    retry_after = float(retry_after_str) if retry_after_str else None
                    dataforseo_logger.rate_limit(
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

                    raise DataForSEORateLimitError(
                        "Rate limit exceeded",
                        retry_after=retry_after,
                        request_id=request_id,
                    )

                if response.status_code in (401, 403):
                    # Auth failure
                    dataforseo_logger.auth_failure(response.status_code)
                    dataforseo_logger.api_call_error(
                        endpoint,
                        duration_ms,
                        response.status_code,
                        "Authentication failed",
                        "AuthError",
                        method=method,
                        retry_attempt=attempt,
                        request_id=request_id,
                    )
                    await self._circuit_breaker.record_failure()
                    raise DataForSEOAuthError(
                        f"Authentication failed ({response.status_code})",
                        status_code=response.status_code,
                        request_id=request_id,
                    )

                if response.status_code >= 500:
                    # Server error - retry
                    error_msg = f"Server error ({response.status_code})"
                    dataforseo_logger.api_call_error(
                        endpoint,
                        duration_ms,
                        response.status_code,
                        error_msg,
                        "ServerError",
                        method=method,
                        retry_attempt=attempt,
                        request_id=request_id,
                    )
                    await self._circuit_breaker.record_failure()

                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2**attempt)
                        logger.warning(
                            f"DataForSEO request attempt {attempt + 1} failed, "
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

                    raise DataForSEOError(
                        error_msg,
                        status_code=response.status_code,
                        request_id=request_id,
                    )

                if response.status_code >= 400:
                    # Client error - don't retry
                    error_body = response.json() if response.content else None
                    error_msg = str(error_body) if error_body else "Client error"
                    dataforseo_logger.api_call_error(
                        endpoint,
                        duration_ms,
                        response.status_code,
                        error_msg,
                        "ClientError",
                        method=method,
                        retry_attempt=attempt,
                        request_id=request_id,
                    )
                    raise DataForSEOError(
                        f"Client error ({response.status_code}): {error_msg}",
                        status_code=response.status_code,
                        response_body=error_body,
                        request_id=request_id,
                    )

                # Success - parse response
                response_data = response.json()

                # Extract cost from response if available
                cost = response_data.get("cost")
                tasks_count = response_data.get("tasks_count")

                # Log success
                dataforseo_logger.api_call_success(
                    endpoint,
                    duration_ms,
                    method=method,
                    cost=cost,
                    tasks_count=tasks_count,
                    request_id=request_id,
                )
                dataforseo_logger.response_body(
                    endpoint, response_data, duration_ms, cost=cost
                )

                # Log cost usage if available
                if cost is not None:
                    dataforseo_logger.cost_usage(cost, endpoint=endpoint)

                await self._circuit_breaker.record_success()

                return response_data, request_id

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                dataforseo_logger.timeout(endpoint, self._timeout)
                dataforseo_logger.api_call_error(
                    endpoint,
                    duration_ms,
                    None,
                    "Request timed out",
                    "TimeoutError",
                    method=method,
                    retry_attempt=attempt,
                    request_id=request_id,
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"DataForSEO request attempt {attempt + 1} timed out, "
                        f"retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                last_error = DataForSEOTimeoutError(
                    f"Request timed out after {self._timeout}s",
                    request_id=request_id,
                )

            except httpx.RequestError as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                dataforseo_logger.api_call_error(
                    endpoint,
                    duration_ms,
                    None,
                    str(e),
                    type(e).__name__,
                    method=method,
                    retry_attempt=attempt,
                    request_id=request_id,
                )
                await self._circuit_breaker.record_failure()

                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"DataForSEO request attempt {attempt + 1} failed, "
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

                last_error = DataForSEOError(
                    f"Request failed: {e}",
                    request_id=request_id,
                )

        if last_error:
            raise last_error
        raise DataForSEOError(
            "Request failed after all retries",
            request_id=request_id,
        )

    async def get_keyword_volume(
        self,
        keywords: list[str],
        location_code: int | None = None,
        language_code: str | None = None,
    ) -> KeywordVolumeResult:
        """Get search volume data for a list of keywords.

        Uses the Keywords Data API - Google Ads Search Volume endpoint.

        Args:
            keywords: List of keywords to lookup (max 1000 per request)
            location_code: Location code (e.g., 2840 for US). Defaults to settings.
            language_code: Language code (e.g., 'en'). Defaults to settings.

        Returns:
            KeywordVolumeResult with keyword data, cost, and metadata
        """
        if not self._available:
            return KeywordVolumeResult(
                success=False,
                error="DataForSEO not configured (missing API credentials)",
            )

        if not keywords:
            return KeywordVolumeResult(
                success=False,
                error="No keywords provided",
            )

        if len(keywords) > MAX_KEYWORDS_PER_REQUEST:
            return KeywordVolumeResult(
                success=False,
                error=f"Too many keywords ({len(keywords)}), max {MAX_KEYWORDS_PER_REQUEST} per request",
            )

        start_time = time.monotonic()
        location_code = location_code or self._default_location_code
        language_code = language_code or self._default_language_code

        # Log operation start
        dataforseo_logger.keyword_search_start(keywords, location_code)

        # Build request payload
        # DataForSEO expects a list of tasks
        payload = [
            {
                "keywords": keywords,
                "location_code": location_code,
                "language_code": language_code,
            }
        ]

        endpoint = "/v3/keywords_data/google_ads/search_volume/live"

        try:
            response_data, request_id = await self._make_request(endpoint, payload)

            # Parse response
            keyword_results: list[KeywordVolumeData] = []
            cost = response_data.get("cost")

            # DataForSEO returns results in tasks[].result[]
            tasks = response_data.get("tasks", [])
            for task in tasks:
                task_result = task.get("result", [])
                for item in task_result:
                    kw = item.get("keyword", "")
                    search_volume = item.get("search_volume")
                    cpc_data = item.get("cpc")
                    competition = item.get("competition")
                    competition_level = item.get("competition_level")
                    monthly_searches = item.get("monthly_searches")

                    keyword_results.append(
                        KeywordVolumeData(
                            keyword=kw,
                            search_volume=search_volume,
                            cpc=float(cpc_data) if cpc_data is not None else None,
                            competition=float(competition)
                            if competition is not None
                            else None,
                            competition_level=competition_level,
                            monthly_searches=monthly_searches,
                        )
                    )

            total_duration_ms = (time.monotonic() - start_time) * 1000

            dataforseo_logger.keyword_search_complete(
                len(keywords),
                total_duration_ms,
                success=True,
                results_count=len(keyword_results),
                cost=cost,
            )

            return KeywordVolumeResult(
                success=True,
                keywords=keyword_results,
                cost=cost,
                request_id=request_id,
                duration_ms=total_duration_ms,
            )

        except DataForSEOError as e:
            total_duration_ms = (time.monotonic() - start_time) * 1000
            dataforseo_logger.keyword_search_complete(
                len(keywords), total_duration_ms, success=False
            )
            return KeywordVolumeResult(
                success=False,
                error=str(e),
                request_id=e.request_id,
                duration_ms=total_duration_ms,
            )

    async def get_keyword_volume_batch(
        self,
        keywords: list[str],
        location_code: int | None = None,
        language_code: str | None = None,
        max_concurrent: int = 5,
    ) -> KeywordVolumeResult:
        """Get search volume data for a large list of keywords in batches.

        Automatically splits keywords into batches of 1000 (API limit) and
        processes them with controlled concurrency.

        Args:
            keywords: List of keywords to lookup (any size)
            location_code: Location code (e.g., 2840 for US). Defaults to settings.
            language_code: Language code (e.g., 'en'). Defaults to settings.
            max_concurrent: Maximum concurrent batch requests. Defaults to 5.

        Returns:
            KeywordVolumeResult with combined keyword data from all batches
        """
        if not keywords:
            return KeywordVolumeResult(
                success=False,
                error="No keywords provided",
            )

        # If within single batch limit, use regular method
        if len(keywords) <= MAX_KEYWORDS_PER_REQUEST:
            return await self.get_keyword_volume(keywords, location_code, language_code)

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
        all_keywords: list[KeywordVolumeData] = []
        total_cost: float = 0.0
        errors: list[str] = []

        async def process_batch(
            batch_index: int, batch: list[str]
        ) -> tuple[int, KeywordVolumeResult]:
            """Process a single batch with semaphore control."""
            async with semaphore:
                dataforseo_logger.batch_start(
                    batch_index,
                    len(batch),
                    total_batches,
                    len(keywords),
                    operation="keyword_volume",
                )
                result = await self.get_keyword_volume(
                    batch, location_code, language_code
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
                if result.cost:
                    total_cost += result.cost
                dataforseo_logger.batch_complete(
                    batch_index,
                    batch_size,
                    total_batches,
                    len(result.keywords),
                    result.duration_ms,
                    cost=result.cost,
                    operation="keyword_volume",
                )
            else:
                errors.append(f"Batch {batch_index + 1}: {result.error}")
                dataforseo_logger.batch_complete(
                    batch_index,
                    batch_size,
                    total_batches,
                    0,
                    result.duration_ms,
                    cost=None,
                    operation="keyword_volume",
                )

        total_duration_ms = (time.monotonic() - start_time) * 1000

        if errors and not all_keywords:
            # All batches failed
            return KeywordVolumeResult(
                success=False,
                error="; ".join(errors),
                duration_ms=total_duration_ms,
            )

        # Partial or full success
        return KeywordVolumeResult(
            success=True,
            keywords=all_keywords,
            cost=total_cost if total_cost > 0 else None,
            error="; ".join(errors) if errors else None,
            duration_ms=total_duration_ms,
        )

    async def get_serp(
        self,
        keyword: str,
        location_code: int | None = None,
        language_code: str | None = None,
        depth: int = 10,
        search_engine: str = "google",
    ) -> SerpSearchResult:
        """Get SERP (Search Engine Results Page) data for a keyword.

        Uses the SERP API - Google Organic endpoint.

        Args:
            keyword: Keyword to search
            location_code: Location code (e.g., 2840 for US). Defaults to settings.
            language_code: Language code (e.g., 'en'). Defaults to settings.
            depth: Number of results to fetch (max 100). Defaults to 10.
            search_engine: Search engine ('google', 'bing'). Defaults to 'google'.

        Returns:
            SerpSearchResult with SERP data, cost, and metadata
        """
        if not self._available:
            return SerpSearchResult(
                success=False,
                keyword=keyword,
                error="DataForSEO not configured (missing API credentials)",
            )

        if not keyword:
            return SerpSearchResult(
                success=False,
                keyword=keyword,
                error="No keyword provided",
            )

        start_time = time.monotonic()
        location_code = location_code or self._default_location_code
        language_code = language_code or self._default_language_code

        # Log operation start
        dataforseo_logger.serp_search_start(keyword, location_code, search_engine)

        # Build request payload
        payload = [
            {
                "keyword": keyword,
                "location_code": location_code,
                "language_code": language_code,
                "depth": depth,
            }
        ]

        # Select endpoint based on search engine
        if search_engine == "bing":
            endpoint = "/v3/serp/bing/organic/live/regular"
        else:
            endpoint = "/v3/serp/google/organic/live/regular"

        try:
            response_data, request_id = await self._make_request(endpoint, payload)

            # Parse response
            serp_results: list[SerpResult] = []
            cost = response_data.get("cost")
            total_results: int | None = None

            # DataForSEO returns results in tasks[].result[].items[]
            tasks = response_data.get("tasks", [])
            for task in tasks:
                task_result_list = task.get("result", [])
                for task_result in task_result_list:
                    total_results = task_result.get("se_results_count")
                    items = task_result.get("items", [])
                    for item in items:
                        # Only include organic results
                        if item.get("type") == "organic":
                            serp_results.append(
                                SerpResult(
                                    position=item.get("rank_group", 0),
                                    url=item.get("url", ""),
                                    title=item.get("title", ""),
                                    description=item.get("description"),
                                    domain=item.get("domain"),
                                )
                            )

            total_duration_ms = (time.monotonic() - start_time) * 1000

            dataforseo_logger.serp_search_complete(
                keyword,
                total_duration_ms,
                success=True,
                results_count=len(serp_results),
                cost=cost,
            )

            return SerpSearchResult(
                success=True,
                keyword=keyword,
                results=serp_results,
                total_results=total_results,
                cost=cost,
                request_id=request_id,
                duration_ms=total_duration_ms,
            )

        except DataForSEOError as e:
            total_duration_ms = (time.monotonic() - start_time) * 1000
            dataforseo_logger.serp_search_complete(
                keyword, total_duration_ms, success=False
            )
            return SerpSearchResult(
                success=False,
                keyword=keyword,
                error=str(e),
                request_id=e.request_id,
                duration_ms=total_duration_ms,
            )

    async def get_keyword_suggestions(
        self,
        keyword: str,
        location_code: int | None = None,
        language_code: str | None = None,
        include_seed_keyword: bool = True,
        limit: int = 100,
    ) -> KeywordVolumeResult:
        """Get keyword suggestions related to a seed keyword.

        Uses the Keywords Data API - Google Ads Keywords For Keywords endpoint.

        Args:
            keyword: Seed keyword
            location_code: Location code (e.g., 2840 for US). Defaults to settings.
            language_code: Language code (e.g., 'en'). Defaults to settings.
            include_seed_keyword: Include seed keyword in results. Defaults to True.
            limit: Maximum number of suggestions. Defaults to 100.

        Returns:
            KeywordVolumeResult with suggested keywords, volume data, cost, and metadata
        """
        if not self._available:
            return KeywordVolumeResult(
                success=False,
                error="DataForSEO not configured (missing API credentials)",
            )

        if not keyword:
            return KeywordVolumeResult(
                success=False,
                error="No keyword provided",
            )

        start_time = time.monotonic()
        location_code = location_code or self._default_location_code
        language_code = language_code or self._default_language_code

        # Log operation start
        dataforseo_logger.keyword_search_start([keyword], location_code)

        # Build request payload
        payload = [
            {
                "keywords": [keyword],
                "location_code": location_code,
                "language_code": language_code,
                "include_seed_keyword": include_seed_keyword,
                "limit": limit,
            }
        ]

        endpoint = "/v3/keywords_data/google_ads/keywords_for_keywords/live"

        try:
            response_data, request_id = await self._make_request(endpoint, payload)

            # Parse response
            keyword_results: list[KeywordVolumeData] = []
            cost = response_data.get("cost")

            # DataForSEO returns results in tasks[].result[]
            tasks = response_data.get("tasks", [])
            for task in tasks:
                task_result = task.get("result", [])
                for item in task_result:
                    kw = item.get("keyword", "")
                    search_volume = item.get("search_volume")
                    cpc_data = item.get("cpc")
                    competition = item.get("competition")
                    competition_level = item.get("competition_level")
                    monthly_searches = item.get("monthly_searches")

                    keyword_results.append(
                        KeywordVolumeData(
                            keyword=kw,
                            search_volume=search_volume,
                            cpc=float(cpc_data) if cpc_data is not None else None,
                            competition=float(competition)
                            if competition is not None
                            else None,
                            competition_level=competition_level,
                            monthly_searches=monthly_searches,
                        )
                    )

            total_duration_ms = (time.monotonic() - start_time) * 1000

            dataforseo_logger.keyword_search_complete(
                1,  # Only one seed keyword
                total_duration_ms,
                success=True,
                results_count=len(keyword_results),
                cost=cost,
            )

            return KeywordVolumeResult(
                success=True,
                keywords=keyword_results,
                cost=cost,
                request_id=request_id,
                duration_ms=total_duration_ms,
            )

        except DataForSEOError as e:
            total_duration_ms = (time.monotonic() - start_time) * 1000
            dataforseo_logger.keyword_search_complete(
                1, total_duration_ms, success=False
            )
            return KeywordVolumeResult(
                success=False,
                error=str(e),
                request_id=e.request_id,
                duration_ms=total_duration_ms,
            )


# Global DataForSEO client instance
dataforseo_client: DataForSEOClient | None = None


async def init_dataforseo() -> DataForSEOClient:
    """Initialize the global DataForSEO client.

    Returns:
        Initialized DataForSEOClient instance
    """
    global dataforseo_client
    if dataforseo_client is None:
        dataforseo_client = DataForSEOClient()
        if dataforseo_client.available:
            logger.info("DataForSEO client initialized")
        else:
            logger.info("DataForSEO not configured (missing API credentials)")
    return dataforseo_client


async def close_dataforseo() -> None:
    """Close the global DataForSEO client."""
    global dataforseo_client
    if dataforseo_client:
        await dataforseo_client.close()
        dataforseo_client = None


async def get_dataforseo() -> DataForSEOClient:
    """Dependency for getting DataForSEO client.

    Usage:
        @app.get("/keywords")
        async def get_keywords(
            keywords: list[str],
            client: DataForSEOClient = Depends(get_dataforseo)
        ):
            result = await client.get_keyword_volume(keywords)
            ...
    """
    global dataforseo_client
    if dataforseo_client is None:
        await init_dataforseo()
    return dataforseo_client  # type: ignore[return-value]
