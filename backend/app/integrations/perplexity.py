"""Perplexity API integration client for website analysis.

Features:
- Async HTTP client using httpx (direct API calls)
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- Request/response logging per requirements
- Handles timeouts, rate limits (429), auth failures (401/403)
- Masks API keys in all logs
- Token usage logging for quota tracking
- Web-connected responses with citations

ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Log API quota/credit usage if available
- Mask API keys and tokens in all logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- All API keys via environment variables (PERPLEXITY_API_KEY)
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
from app.core.logging import get_logger, perplexity_logger

logger = get_logger(__name__)

# Perplexity API base URL
PERPLEXITY_API_URL = "https://api.perplexity.ai"


@dataclass
class WebsiteAnalysisResult:
    """Result of a website analysis operation."""

    success: bool
    url: str
    analysis: str | None = None
    citations: list[str] = field(default_factory=list)
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


@dataclass
class BrandResearchResult:
    """Result of a brand research operation for V3 brand config."""

    success: bool
    domain: str
    research_data: dict[str, Any] | None = None
    raw_text: str | None = None
    citations: list[str] = field(default_factory=list)
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


@dataclass
class CompletionResult:
    """Result of a Perplexity completion request."""

    success: bool
    text: str | None = None
    citations: list[str] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None
    status_code: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


class PerplexityError(Exception):
    """Base exception for Perplexity API errors."""

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


class PerplexityTimeoutError(PerplexityError):
    """Raised when a request times out."""

    pass


class PerplexityRateLimitError(PerplexityError):
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


class PerplexityAuthError(PerplexityError):
    """Raised when authentication fails (401/403)."""

    pass


class PerplexityCircuitOpenError(PerplexityError):
    """Raised when circuit breaker is open."""

    pass


# System prompt for website analysis
WEBSITE_ANALYSIS_SYSTEM_PROMPT = """You are a website analysis expert. Your task is to analyze websites and provide comprehensive information about the business, its products/services, and key details that would be useful for client onboarding.

Focus on extracting:
1. Business overview and what they do
2. Key products or services offered
3. Target audience or customer segments
4. Unique value propositions or differentiators
5. Company information (size, location if available)
6. Brand voice and tone

Provide a well-structured, factual analysis based on what you find on the website and any available information."""

# System prompt for brand research (V3 brand config)
BRAND_RESEARCH_SYSTEM_PROMPT = """You are a brand research expert. Your task is to thoroughly research a brand from their website and online presence to extract comprehensive brand information.

Research and extract the following information, organized into these sections:

## 1. FOUNDATION
- Company name, founding year, location, industry
- Business model (B2B, B2C, DTC, etc.)
- Primary products/services and price positioning
- Tagline or slogan (if any)
- Mission statement and core values
- Key differentiators (what makes them unique)
- What they explicitly are NOT (positioning they reject)

## 2. TARGET AUDIENCE
For each identifiable customer segment, extract:
- Demographics (age, location, income level, profession)
- Psychographics (values, aspirations, fears, identity)
- Pain points and frustrations with current solutions
- Motivations and buying triggers
- How they discover and research products
- Decision factors (price, quality, brand, convenience)

## 3. VOICE INDICATORS
Analyze their existing content to identify:
- Formality level (casual to formal, scale 1-10)
- Use of humor (playful to serious, scale 1-10)
- Tone toward competitors/industry (irreverent to respectful, scale 1-10)
- Energy/enthusiasm level (enthusiastic to matter-of-fact, scale 1-10)
- Voice characteristics (e.g., "knowledgeable but approachable")
- What their voice is definitely NOT

## 4. WRITING PATTERNS
Note any observable patterns:
- Sentence length tendencies (short and punchy vs. longer)
- Use of contractions
- Punctuation habits (exclamation points, em dashes)
- Recurring phrases or terminology
- Industry-specific vocabulary

## 5. PROOF & TRUST ELEMENTS
Extract any verifiable claims:
- Customer counts or statistics
- Years in business
- Review ratings and counts
- Certifications or awards
- Media mentions
- Notable partnerships or endorsements
- Guarantees and warranties
- Customer testimonials (exact quotes if available)

## 6. COMPETITIVE CONTEXT
If discoverable:
- Main competitors mentioned or implied
- How they differentiate from competitors
- Market position (leader, challenger, specialist)

Provide thorough, factual findings with citations. If information is not available for a section, explicitly state what could not be determined."""


class PerplexityClient:
    """Async client for Perplexity API.

    Provides LLM capabilities with web-connected responses:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Comprehensive logging
    - Railway deployment compatibility
    - Citations from web sources
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
        """Initialize Perplexity client.

        Args:
            api_key: Perplexity API key. Defaults to settings.
            model: Model to use. Defaults to settings (sonar).
            timeout: Request timeout in seconds. Defaults to settings.
            max_retries: Maximum retry attempts. Defaults to settings.
            retry_delay: Base delay between retries. Defaults to settings.
            max_tokens: Maximum response tokens. Defaults to settings.
        """
        settings = get_settings()

        self._api_key = api_key or settings.perplexity_api_key
        self._model = model or settings.perplexity_model
        self._timeout = timeout or settings.perplexity_timeout
        self._max_retries = max_retries or settings.perplexity_max_retries
        self._retry_delay = retry_delay or settings.perplexity_retry_delay
        self._max_tokens = max_tokens or settings.perplexity_max_tokens

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.perplexity_circuit_failure_threshold,
                recovery_timeout=settings.perplexity_circuit_recovery_timeout,
            ),
            name="perplexity",
        )

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None
        self._available = bool(self._api_key)

    @property
    def available(self) -> bool:
        """Check if Perplexity is configured and available."""
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
            }
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            self._client = httpx.AsyncClient(
                base_url=PERPLEXITY_API_URL,
                headers=headers,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Perplexity client closed")

    async def complete(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.2,
        return_citations: bool = True,
    ) -> CompletionResult:
        """Send a completion request to Perplexity.

        Args:
            user_prompt: The user message/prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum response tokens (overrides default)
            temperature: Sampling temperature (0.2 for factual, higher for creative)
            return_citations: Whether to include web citations

        Returns:
            CompletionResult with response text, citations, and metadata
        """
        if not self._available:
            return CompletionResult(
                success=False,
                error="Perplexity not configured (missing API key)",
            )

        if not await self._circuit_breaker.can_execute():
            perplexity_logger.graceful_fallback("complete", "Circuit breaker open")
            return CompletionResult(
                success=False,
                error="Circuit breaker is open",
            )

        start_time = time.monotonic()
        client = await self._get_client()
        last_error: Exception | None = None
        request_id: str | None = None

        # Build request body (Perplexity uses OpenAI-compatible format)
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        request_body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens or self._max_tokens,
            "temperature": temperature,
            "return_citations": return_citations,
        }

        for attempt in range(self._max_retries):
            attempt_start = time.monotonic()

            try:
                # Log request start
                perplexity_logger.api_call_start(
                    self._model,
                    len(user_prompt),
                    retry_attempt=attempt,
                    request_id=request_id,
                )
                if system_prompt:
                    perplexity_logger.request_body(
                        self._model, system_prompt, user_prompt
                    )

                # Make request
                response = await client.post("/chat/completions", json=request_body)
                duration_ms = (time.monotonic() - attempt_start) * 1000

                # Extract request ID from response headers
                request_id = response.headers.get("x-request-id")

                # Handle response based on status code
                if response.status_code == 429:
                    # Rate limited
                    retry_after_str = response.headers.get("retry-after")
                    retry_after = float(retry_after_str) if retry_after_str else None
                    perplexity_logger.rate_limit(
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
                    perplexity_logger.auth_failure(response.status_code)
                    perplexity_logger.api_call_error(
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
                    perplexity_logger.api_call_error(
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
                            f"Perplexity request attempt {attempt + 1} failed, "
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
                        if error_body and isinstance(error_body, dict)
                        else "Client error"
                    )
                    perplexity_logger.api_call_error(
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

                # Extract content and usage (OpenAI-compatible format)
                choices = response_data.get("choices", [])
                text = ""
                if choices:
                    message = choices[0].get("message", {})
                    text = message.get("content", "")

                # Extract citations if available
                citations = response_data.get("citations", [])

                # Extract usage
                usage = response_data.get("usage", {})
                input_tokens = usage.get("prompt_tokens")
                output_tokens = usage.get("completion_tokens")

                # Log success
                perplexity_logger.api_call_success(
                    self._model,
                    duration_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    request_id=request_id,
                )
                perplexity_logger.response_body(
                    self._model, text, duration_ms, citations=citations
                )

                # Log token usage
                if input_tokens and output_tokens:
                    perplexity_logger.token_usage(
                        self._model,
                        input_tokens,
                        output_tokens,
                    )

                await self._circuit_breaker.record_success()

                return CompletionResult(
                    success=True,
                    text=text,
                    citations=citations,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    request_id=request_id,
                    duration_ms=total_duration_ms,
                )

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                perplexity_logger.timeout(self._model, self._timeout)
                perplexity_logger.api_call_error(
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
                        f"Perplexity request attempt {attempt + 1} timed out, "
                        f"retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                last_error = PerplexityTimeoutError(
                    f"Request timed out after {self._timeout}s"
                )

            except httpx.RequestError as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                perplexity_logger.api_call_error(
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
                        f"Perplexity request attempt {attempt + 1} failed, "
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

                last_error = PerplexityError(f"Request failed: {e}")

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

    async def analyze_website(
        self,
        url: str,
        focus_areas: list[str] | None = None,
    ) -> WebsiteAnalysisResult:
        """Analyze a website using Perplexity's web-connected capabilities.

        Args:
            url: Website URL to analyze
            focus_areas: Optional list of specific areas to focus on
                        (e.g., ["products", "pricing", "company info"])

        Returns:
            WebsiteAnalysisResult with analysis, citations, and metadata
        """
        start_time = time.monotonic()

        perplexity_logger.analysis_start(url)

        # Build user prompt
        focus_str = ""
        if focus_areas:
            focus_str = f"\n\nPlease focus particularly on: {', '.join(focus_areas)}"

        user_prompt = f"""Analyze the website at {url} and provide a comprehensive overview.{focus_str}

Please research the website thoroughly and provide factual information with citations."""

        # Make completion request
        result = await self.complete(
            user_prompt=user_prompt,
            system_prompt=WEBSITE_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.2,  # Lower temperature for factual analysis
            return_citations=True,
        )

        total_duration_ms = (time.monotonic() - start_time) * 1000

        if not result.success:
            perplexity_logger.analysis_complete(
                url, total_duration_ms, success=False, citation_count=0
            )
            return WebsiteAnalysisResult(
                success=False,
                url=url,
                error=result.error,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=total_duration_ms,
                request_id=result.request_id,
            )

        perplexity_logger.analysis_complete(
            url,
            total_duration_ms,
            success=True,
            citation_count=len(result.citations),
        )

        return WebsiteAnalysisResult(
            success=True,
            url=url,
            analysis=result.text,
            citations=result.citations,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            duration_ms=total_duration_ms,
            request_id=result.request_id,
        )

    async def research_query(
        self,
        query: str,
        context: str | None = None,
    ) -> CompletionResult:
        """Execute a research query with web-connected context.

        Args:
            query: The research question or query
            context: Optional additional context for the query

        Returns:
            CompletionResult with research findings and citations
        """
        user_prompt = query
        if context:
            user_prompt = f"Context: {context}\n\nQuery: {query}"

        return await self.complete(
            user_prompt=user_prompt,
            system_prompt="You are a research assistant. Provide accurate, well-cited information based on your web research.",
            temperature=0.2,
            return_citations=True,
        )

    async def research_brand(
        self,
        domain: str,
        brand_name: str | None = None,
    ) -> BrandResearchResult:
        """Research a brand from their website for V3 brand config creation.

        This method performs comprehensive brand research using Perplexity's
        web-connected capabilities, extracting information aligned with the
        11-part V3 brand configuration schema.

        Args:
            domain: Website domain to research (e.g., "acme.com" or "https://acme.com")
            brand_name: Optional brand name if different from domain

        Returns:
            BrandResearchResult with structured brand research data and citations
        """
        start_time = time.monotonic()

        # Normalize domain
        if not domain.startswith(("http://", "https://")):
            url = f"https://{domain}"
        else:
            url = domain
            # Extract domain from URL for logging
            domain = url.replace("https://", "").replace("http://", "").split("/")[0]

        perplexity_logger.analysis_start(url)
        logger.info(
            "Starting brand research",
            extra={"domain": domain, "brand_name": brand_name},
        )

        # Build user prompt
        brand_context = f"for the brand '{brand_name}'" if brand_name else ""
        user_prompt = f"""Research the brand at {url} {brand_context} and provide comprehensive brand information.

Analyze their website, social media presence, reviews, press mentions, and any other available information to build a complete picture of:
1. Who they are (company foundation, mission, values)
2. Who they serve (target audience personas)
3. How they communicate (brand voice and writing style)
4. What makes them credible (proof elements, trust signals)
5. How they position against competitors

Be thorough and cite your sources. If certain information cannot be determined, explicitly note what is missing."""

        # Make completion request with higher token limit for comprehensive research
        result = await self.complete(
            user_prompt=user_prompt,
            system_prompt=BRAND_RESEARCH_SYSTEM_PROMPT,
            max_tokens=4096,  # Allow longer response for comprehensive research
            temperature=0.2,  # Lower temperature for factual research
            return_citations=True,
        )

        total_duration_ms = (time.monotonic() - start_time) * 1000

        if not result.success:
            perplexity_logger.analysis_complete(
                url, total_duration_ms, success=False, citation_count=0
            )
            logger.warning(
                "Brand research failed",
                extra={"domain": domain, "error": result.error},
            )
            return BrandResearchResult(
                success=False,
                domain=domain,
                error=result.error,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=total_duration_ms,
                request_id=result.request_id,
            )

        perplexity_logger.analysis_complete(
            url,
            total_duration_ms,
            success=True,
            citation_count=len(result.citations),
        )
        logger.info(
            "Brand research completed",
            extra={
                "domain": domain,
                "duration_ms": total_duration_ms,
                "citations": len(result.citations),
            },
        )

        return BrandResearchResult(
            success=True,
            domain=domain,
            research_data=None,  # Raw text only; synthesis happens in BrandResearchService
            raw_text=result.text,
            citations=result.citations,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            duration_ms=total_duration_ms,
            request_id=result.request_id,
        )


# Global Perplexity client instance
perplexity_client: PerplexityClient | None = None


async def init_perplexity() -> PerplexityClient:
    """Initialize the global Perplexity client.

    Returns:
        Initialized PerplexityClient instance
    """
    global perplexity_client
    if perplexity_client is None:
        perplexity_client = PerplexityClient()
        if perplexity_client.available:
            logger.info(
                "Perplexity client initialized",
                extra={"model": perplexity_client.model},
            )
        else:
            logger.info("Perplexity not configured (missing API key)")
    return perplexity_client


async def close_perplexity() -> None:
    """Close the global Perplexity client."""
    global perplexity_client
    if perplexity_client:
        await perplexity_client.close()
        perplexity_client = None


async def get_perplexity() -> PerplexityClient:
    """Dependency for getting Perplexity client.

    Usage:
        @app.get("/analyze")
        async def analyze_website(
            url: str,
            perplexity: PerplexityClient = Depends(get_perplexity)
        ):
            result = await perplexity.analyze_website(url)
            ...
    """
    global perplexity_client
    if perplexity_client is None:
        await init_perplexity()
    return perplexity_client  # type: ignore[return-value]
