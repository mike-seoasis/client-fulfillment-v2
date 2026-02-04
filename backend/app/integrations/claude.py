"""Claude/Anthropic LLM integration client for page categorization.

Features:
- Async HTTP client using httpx (direct API calls)
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- Request/response logging per requirements
- Handles timeouts, rate limits (429), auth failures (401/403)
- Masks API keys in all logs
- Token usage logging for quota tracking

ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Log API quota/credit usage if available
- Mask API keys and tokens in all logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- All API keys via environment variables (ANTHROPIC_API_KEY)
- Never log or expose API keys
- Handle cold-start latency (first request may be slow)
- Implement request timeouts (Railway has 5min request limit)
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import claude_logger, get_logger

logger = get_logger(__name__)

# Anthropic API base URL
ANTHROPIC_API_URL = "https://api.anthropic.com"
ANTHROPIC_API_VERSION = "2023-06-01"


@dataclass
class CategorizationResult:
    """Result of a page categorization operation."""

    success: bool
    url: str
    category: str = "other"
    confidence: float = 0.0
    reasoning: str | None = None
    labels: list[str] = field(default_factory=list)
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


@dataclass
class CompletionResult:
    """Result of a Claude completion request."""

    success: bool
    text: str | None = None
    stop_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None
    status_code: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


class ClaudeError(Exception):
    """Base exception for Claude API errors."""

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


class ClaudeTimeoutError(ClaudeError):
    """Raised when a request times out."""

    pass


class ClaudeRateLimitError(ClaudeError):
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


class ClaudeAuthError(ClaudeError):
    """Raised when authentication fails (401/403)."""

    pass


class ClaudeCircuitOpenError(ClaudeError):
    """Raised when circuit breaker is open."""

    pass


# Default categories for page categorization
DEFAULT_CATEGORIES = [
    "homepage",
    "product",
    "collection",
    "blog",
    "policy",
    "about",
    "contact",
    "faq",
    "account",
    "cart",
    "search",
    "other",
]

# System prompt for categorization
CATEGORIZATION_SYSTEM_PROMPT = """You are a web page categorization expert. Your task is to analyze web page content and classify it into predefined categories.

Respond ONLY with valid JSON in this exact format:
{
  "category": "<category_name>",
  "confidence": <0.0-1.0>,
  "reasoning": "<brief explanation>",
  "labels": ["<optional>", "<additional>", "<labels>"]
}

Guidelines:
- Choose the single most appropriate category from the provided list
- Confidence should reflect how certain you are (0.0 = uncertain, 1.0 = certain)
- Keep reasoning brief (1-2 sentences)
- Labels are optional additional descriptors (max 5)
- If content is unclear or minimal, use "other" with lower confidence"""


class ClaudeClient:
    """Async client for Claude/Anthropic API.

    Provides LLM capabilities with:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Comprehensive logging
    - Railway deployment compatibility
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """Initialize Claude client.

        Args:
            api_key: Anthropic API key. Defaults to settings.
            model: Model to use. Defaults to settings (claude-3-haiku).
            timeout: Request timeout in seconds. Defaults to settings.
            max_retries: Maximum retry attempts. Defaults to settings.
            retry_delay: Base delay between retries. Defaults to settings.
            max_tokens: Maximum response tokens. Defaults to settings.
        """
        settings = get_settings()

        self._api_key = api_key or settings.anthropic_api_key
        self._model = model or settings.claude_model
        self._timeout = timeout or settings.claude_timeout
        self._max_retries = max_retries or settings.claude_max_retries
        self._retry_delay = retry_delay or settings.claude_retry_delay
        self._max_tokens = max_tokens or settings.claude_max_tokens

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.claude_circuit_failure_threshold,
                recovery_timeout=settings.claude_circuit_recovery_timeout,
            ),
            name="claude",
        )

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None
        self._available = bool(self._api_key)

        # Debug logging for initialization
        logger.info(
            "ClaudeClient instantiated",
            extra={
                "instance_id": id(self),
                "available": self._available,
                "has_api_key": bool(self._api_key),
                "model": self._model,
                "settings_api_key_present": bool(settings.anthropic_api_key),
            },
        )

    @property
    def available(self) -> bool:
        """Check if Claude is configured and available."""
        return self._available

    @property
    def model(self) -> str:
        """Get the model being used."""
        return self._model

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
                "anthropic-version": ANTHROPIC_API_VERSION,
            }
            if self._api_key:
                headers["x-api-key"] = self._api_key

            self._client = httpx.AsyncClient(
                base_url=ANTHROPIC_API_URL,
                headers=headers,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Claude client closed")

    async def complete(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> CompletionResult:
        """Send a completion request to Claude.

        Args:
            user_prompt: The user message/prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum response tokens (overrides default)
            temperature: Sampling temperature (0.0 = deterministic)

        Returns:
            CompletionResult with response text and metadata
        """
        if not self._available:
            return CompletionResult(
                success=False,
                error="Claude not configured (missing API key)",
            )

        if not await self._circuit_breaker.can_execute():
            claude_logger.graceful_fallback("complete", "Circuit breaker open")
            return CompletionResult(
                success=False,
                error="Circuit breaker is open",
            )

        start_time = time.monotonic()
        client = await self._get_client()
        last_error: Exception | None = None
        request_id: str | None = None

        # Build request body
        request_body: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if system_prompt:
            request_body["system"] = system_prompt

        for attempt in range(self._max_retries):
            attempt_start = time.monotonic()

            try:
                # Log request start
                claude_logger.api_call_start(
                    self._model,
                    len(user_prompt),
                    retry_attempt=attempt,
                    request_id=request_id,
                )
                if system_prompt:
                    claude_logger.request_body(self._model, system_prompt, user_prompt)

                # Make request
                response = await client.post("/v1/messages", json=request_body)
                duration_ms = (time.monotonic() - attempt_start) * 1000

                # Extract request ID from response headers
                request_id = response.headers.get("request-id")

                # Handle response based on status code
                if response.status_code == 429:
                    # Rate limited
                    retry_after_str = response.headers.get("retry-after")
                    retry_after = float(retry_after_str) if retry_after_str else None
                    claude_logger.rate_limit(
                        self._model, retry_after=retry_after, request_id=request_id
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

                    return CompletionResult(
                        success=False,
                        error="Rate limit exceeded",
                        status_code=429,
                        request_id=request_id,
                        duration_ms=duration_ms,
                    )

                if response.status_code in (401, 403):
                    # Auth failure
                    claude_logger.auth_failure(response.status_code)
                    claude_logger.api_call_error(
                        self._model,
                        duration_ms,
                        response.status_code,
                        "Authentication failed",
                        "AuthError",
                        retry_attempt=attempt,
                        request_id=request_id,
                    )
                    await self._circuit_breaker.record_failure()
                    return CompletionResult(
                        success=False,
                        error=f"Authentication failed ({response.status_code})",
                        status_code=response.status_code,
                        request_id=request_id,
                        duration_ms=duration_ms,
                    )

                if response.status_code >= 500:
                    # Server error - retry
                    error_msg = f"Server error ({response.status_code})"
                    claude_logger.api_call_error(
                        self._model,
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
                            f"Claude request attempt {attempt + 1} failed, "
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

                    return CompletionResult(
                        success=False,
                        error=error_msg,
                        status_code=response.status_code,
                        request_id=request_id,
                        duration_ms=duration_ms,
                    )

                if response.status_code >= 400:
                    # Client error - don't retry
                    error_body = response.json() if response.content else None
                    error_msg = (
                        error_body.get("error", {}).get("message", str(error_body))
                        if error_body
                        else "Client error"
                    )
                    claude_logger.api_call_error(
                        self._model,
                        duration_ms,
                        response.status_code,
                        error_msg,
                        "ClientError",
                        retry_attempt=attempt,
                        request_id=request_id,
                    )
                    return CompletionResult(
                        success=False,
                        error=f"Client error ({response.status_code}): {error_msg}",
                        status_code=response.status_code,
                        request_id=request_id,
                        duration_ms=duration_ms,
                    )

                # Success - parse response
                response_data = response.json()
                total_duration_ms = (time.monotonic() - start_time) * 1000

                # Extract content and usage
                content = response_data.get("content", [])
                text = content[0].get("text", "") if content else ""
                stop_reason = response_data.get("stop_reason")
                usage = response_data.get("usage", {})
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")

                # Log success
                claude_logger.api_call_success(
                    self._model,
                    duration_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    request_id=request_id,
                )
                claude_logger.response_body(
                    self._model, text, duration_ms, stop_reason=stop_reason
                )

                # Log token usage
                if input_tokens and output_tokens:
                    cache_creation = usage.get("cache_creation_input_tokens")
                    cache_read = usage.get("cache_read_input_tokens")
                    claude_logger.token_usage(
                        self._model,
                        input_tokens,
                        output_tokens,
                        cache_creation_input_tokens=cache_creation,
                        cache_read_input_tokens=cache_read,
                    )

                await self._circuit_breaker.record_success()

                return CompletionResult(
                    success=True,
                    text=text,
                    stop_reason=stop_reason,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    request_id=request_id,
                    duration_ms=total_duration_ms,
                )

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                claude_logger.timeout(self._model, self._timeout)
                claude_logger.api_call_error(
                    self._model,
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
                        f"Claude request attempt {attempt + 1} timed out, "
                        f"retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                last_error = ClaudeTimeoutError(
                    f"Request timed out after {self._timeout}s"
                )

            except httpx.RequestError as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                claude_logger.api_call_error(
                    self._model,
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
                        f"Claude request attempt {attempt + 1} failed, "
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

                last_error = ClaudeError(f"Request failed: {e}")

        total_duration_ms = (time.monotonic() - start_time) * 1000
        if last_error:
            return CompletionResult(
                success=False,
                error=str(last_error),
                duration_ms=total_duration_ms,
                request_id=request_id,
            )
        return CompletionResult(
            success=False,
            error="Request failed after all retries",
            duration_ms=total_duration_ms,
            request_id=request_id,
        )

    async def categorize_page(
        self,
        url: str,
        title: str | None = None,
        content: str | None = None,
        categories: list[str] | None = None,
    ) -> CategorizationResult:
        """Categorize a web page using Claude.

        Args:
            url: Page URL
            title: Page title
            content: Page content (text/markdown, will be truncated if too long)
            categories: List of valid categories (defaults to DEFAULT_CATEGORIES)

        Returns:
            CategorizationResult with category, confidence, and reasoning
        """
        start_time = time.monotonic()
        categories = categories or DEFAULT_CATEGORIES

        claude_logger.categorization_start(url, len(categories))

        # Build user prompt with available content
        content_parts = [f"URL: {url}"]
        if title:
            content_parts.append(f"Title: {title}")
        if content:
            # Truncate content to avoid token limits (roughly 10k chars ~ 2.5k tokens)
            truncated_content = content[:10000]
            if len(content) > 10000:
                truncated_content += f"\n... (truncated, {len(content)} total chars)"
            content_parts.append(f"Content:\n{truncated_content}")

        # Include valid categories in prompt
        categories_str = ", ".join(categories)
        user_prompt = f"""Analyze this web page and categorize it.

Valid categories: {categories_str}

{chr(10).join(content_parts)}

Respond with JSON only."""

        # Make completion request
        result = await self.complete(
            user_prompt=user_prompt,
            system_prompt=CATEGORIZATION_SYSTEM_PROMPT,
            temperature=0.0,  # Deterministic for consistency
        )

        total_duration_ms = (time.monotonic() - start_time) * 1000

        if not result.success:
            claude_logger.categorization_complete(
                url, "other", 0.0, total_duration_ms, success=False
            )
            return CategorizationResult(
                success=False,
                url=url,
                category="other",
                confidence=0.0,
                error=result.error,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=total_duration_ms,
                request_id=result.request_id,
            )

        # Parse JSON response
        try:
            # Try to extract JSON from response (handle markdown code blocks)
            response_text = result.text or ""
            json_text = response_text.strip()

            # Handle markdown code blocks
            if json_text.startswith("```"):
                # Remove opening fence
                lines = json_text.split("\n")
                lines = lines[1:]  # Remove first line (```json or ```)
                # Remove closing fence
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                json_text = "\n".join(lines)

            parsed = json.loads(json_text)
            category = parsed.get("category", "other")
            confidence = float(parsed.get("confidence", 0.5))
            reasoning = parsed.get("reasoning")
            labels = parsed.get("labels", [])

            # Validate category
            if category not in categories:
                logger.warning(
                    f"Invalid category '{category}' returned, using 'other'",
                    extra={"url": url[:200], "invalid_category": category},
                )
                category = "other"
                confidence = min(confidence, 0.5)  # Lower confidence for fallback

            # Ensure labels is a list
            if not isinstance(labels, list):
                labels = []
            labels = [str(label) for label in labels[:5]]  # Max 5 labels

            claude_logger.categorization_complete(
                url, category, confidence, total_duration_ms, success=True
            )

            return CategorizationResult(
                success=True,
                url=url,
                category=category,
                confidence=confidence,
                reasoning=reasoning,
                labels=labels,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=total_duration_ms,
                request_id=result.request_id,
            )

        except json.JSONDecodeError as e:
            logger.warning(
                f"Failed to parse categorization response: {e}",
                extra={
                    "url": url[:200],
                    "response": (result.text or "")[:500],
                    "error": str(e),
                },
            )
            claude_logger.categorization_complete(
                url, "other", 0.0, total_duration_ms, success=False
            )
            return CategorizationResult(
                success=False,
                url=url,
                category="other",
                confidence=0.0,
                error=f"Failed to parse response: {e}",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=total_duration_ms,
                request_id=result.request_id,
            )

    async def categorize_pages(
        self,
        pages: list[dict[str, str | None]],
        categories: list[str] | None = None,
        batch_size: int = 10,
        project_id: str | None = None,
    ) -> list[CategorizationResult]:
        """Categorize multiple pages with batch processing.

        Processes pages in batches of `batch_size` (default 10) for efficient
        LLM usage. Each batch is processed sequentially to avoid overwhelming
        the API, but allows for better rate limit handling and token tracking.

        Args:
            pages: List of dicts with 'url', 'title', and 'content' keys
            categories: List of valid categories (defaults to DEFAULT_CATEGORIES)
            batch_size: Number of pages to process per batch (default 10)
            project_id: Project ID for logging context

        Returns:
            List of CategorizationResult objects
        """
        if not pages:
            return []

        start_time = time.monotonic()
        total_pages = len(pages)
        total_batches = (total_pages + batch_size - 1) // batch_size  # Ceiling division

        # Log batch processing start
        claude_logger.batch_processing_start(
            total_pages=total_pages,
            batch_size=batch_size,
            total_batches=total_batches,
            project_id=project_id,
        )

        results: list[CategorizationResult] = []
        total_input_tokens = 0
        total_output_tokens = 0
        total_success = 0
        total_failure = 0

        # Process in batches
        for batch_index in range(total_batches):
            batch_start = batch_index * batch_size
            batch_end = min(batch_start + batch_size, total_pages)
            batch = pages[batch_start:batch_end]
            batch_start_time = time.monotonic()

            # Log batch start
            claude_logger.batch_start(
                batch_index=batch_index,
                batch_size=len(batch),
                total_batches=total_batches,
                total_pages=total_pages,
                project_id=project_id,
            )

            batch_results: list[CategorizationResult] = []
            batch_input_tokens = 0
            batch_output_tokens = 0
            batch_success = 0
            batch_failure = 0

            try:
                # Process each page in the batch
                for page in batch:
                    result = await self.categorize_page(
                        url=page.get("url") or "",
                        title=page.get("title"),
                        content=page.get("content"),
                        categories=categories,
                    )
                    batch_results.append(result)

                    # Track tokens and success/failure
                    if result.input_tokens:
                        batch_input_tokens += result.input_tokens
                    if result.output_tokens:
                        batch_output_tokens += result.output_tokens
                    if result.success:
                        batch_success += 1
                    else:
                        batch_failure += 1

                batch_duration_ms = (time.monotonic() - batch_start_time) * 1000

                # Log batch completion
                claude_logger.batch_complete(
                    batch_index=batch_index,
                    batch_size=len(batch),
                    total_batches=total_batches,
                    success_count=batch_success,
                    failure_count=batch_failure,
                    duration_ms=batch_duration_ms,
                    total_input_tokens=batch_input_tokens,
                    total_output_tokens=batch_output_tokens,
                    project_id=project_id,
                )

            except Exception as e:
                batch_duration_ms = (time.monotonic() - batch_start_time) * 1000

                # Log batch error
                claude_logger.batch_error(
                    batch_index=batch_index,
                    total_batches=total_batches,
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=batch_duration_ms,
                    project_id=project_id,
                )

                # Create failure results for remaining pages in batch
                for page in batch[len(batch_results) :]:
                    batch_results.append(
                        CategorizationResult(
                            success=False,
                            url=page.get("url") or "",
                            category="other",
                            confidence=0.0,
                            error=f"Batch processing failed: {e}",
                        )
                    )
                batch_failure += len(batch) - batch_success

            # Accumulate totals
            results.extend(batch_results)
            total_input_tokens += batch_input_tokens
            total_output_tokens += batch_output_tokens
            total_success += batch_success
            total_failure += batch_failure

        total_duration_ms = (time.monotonic() - start_time) * 1000

        # Log batch processing completion
        claude_logger.batch_processing_complete(
            total_pages=total_pages,
            total_batches=total_batches,
            success_count=total_success,
            failure_count=total_failure,
            duration_ms=total_duration_ms,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            project_id=project_id,
        )

        return results


# Global Claude client instance
claude_client: ClaudeClient | None = None


async def init_claude() -> ClaudeClient:
    """Initialize the global Claude client.

    Returns:
        Initialized ClaudeClient instance
    """
    global claude_client
    if claude_client is None:
        claude_client = ClaudeClient()
        if claude_client.available:
            logger.info(
                "Claude client initialized",
                extra={"model": claude_client.model},
            )
        else:
            logger.info("Claude not configured (missing API key)")
    return claude_client


async def close_claude() -> None:
    """Close the global Claude client."""
    global claude_client
    if claude_client:
        await claude_client.close()
        claude_client = None


async def get_claude() -> ClaudeClient:
    """Dependency for getting Claude client.

    Usage:
        @app.get("/categorize")
        async def categorize_page(
            url: str,
            claude: ClaudeClient = Depends(get_claude)
        ):
            result = await claude.categorize_page(url)
            ...
    """
    global claude_client
    if claude_client is None:
        await init_claude()
    return claude_client  # type: ignore[return-value]
