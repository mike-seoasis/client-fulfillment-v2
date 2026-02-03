"""Google Cloud NLP integration client for entity extraction.

Features:
- Async HTTP client using httpx (direct API calls)
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- Request/response logging per requirements
- Handles timeouts, rate limits (429), auth failures (401/403)
- Masks API keys in all logs
- Entity extraction with type classification

ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Log API quota/credit usage if available
- Mask API keys and tokens in all logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- All API keys via environment variables (GOOGLE_NLP_API_KEY)
- Never log or expose API keys
- Handle cold-start latency (first request may be slow)
- Implement request timeouts (Railway has 5min request limit)
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import get_logger, google_nlp_logger

logger = get_logger(__name__)

# Google Cloud NLP API base URL
GOOGLE_NLP_API_URL = "https://language.googleapis.com"
GOOGLE_NLP_API_VERSION = "v1"


class EntityType(Enum):
    """Google Cloud NLP entity types."""

    UNKNOWN = "UNKNOWN"
    PERSON = "PERSON"
    LOCATION = "LOCATION"
    ORGANIZATION = "ORGANIZATION"
    EVENT = "EVENT"
    WORK_OF_ART = "WORK_OF_ART"
    CONSUMER_GOOD = "CONSUMER_GOOD"
    OTHER = "OTHER"
    PHONE_NUMBER = "PHONE_NUMBER"
    ADDRESS = "ADDRESS"
    DATE = "DATE"
    NUMBER = "NUMBER"
    PRICE = "PRICE"


@dataclass
class Entity:
    """Represents an extracted entity from text."""

    name: str
    type: str
    salience: float
    mentions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "salience": self.salience,
            "mentions": self.mentions,
            "metadata": self.metadata,
        }


@dataclass
class EntityExtractionResult:
    """Result of an entity extraction operation."""

    success: bool
    text: str
    entities: list[Entity] = field(default_factory=list)
    language: str | None = None
    error: str | None = None
    status_code: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "text": self.text[:200] + "..." if len(self.text) > 200 else self.text,
            "entities": [e.to_dict() for e in self.entities],
            "entity_count": len(self.entities),
            "language": self.language,
            "error": self.error,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "request_id": self.request_id,
        }


class GoogleNLPError(Exception):
    """Base exception for Google Cloud NLP API errors."""

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


class GoogleNLPTimeoutError(GoogleNLPError):
    """Raised when a request times out."""

    pass


class GoogleNLPRateLimitError(GoogleNLPError):
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


class GoogleNLPAuthError(GoogleNLPError):
    """Raised when authentication fails (401/403)."""

    pass


class GoogleNLPCircuitOpenError(GoogleNLPError):
    """Raised when circuit breaker is open."""

    pass


class GoogleNLPClient:
    """Async client for Google Cloud NLP API.

    Provides entity extraction capabilities with:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Comprehensive logging
    - Railway deployment compatibility
    """

    def __init__(
        self,
        api_key: str | None = None,
        project_id: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
    ) -> None:
        """Initialize Google Cloud NLP client.

        Args:
            api_key: Google Cloud API key. Defaults to settings.
            project_id: Google Cloud project ID. Defaults to settings.
            timeout: Request timeout in seconds. Defaults to settings.
            max_retries: Maximum retry attempts. Defaults to settings.
            retry_delay: Base delay between retries. Defaults to settings.
        """
        settings = get_settings()

        self._api_key = api_key or settings.google_nlp_api_key
        self._project_id = project_id or settings.google_nlp_project_id
        self._timeout = timeout or settings.google_nlp_timeout
        self._max_retries = max_retries or settings.google_nlp_max_retries
        self._retry_delay = retry_delay or settings.google_nlp_retry_delay

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.google_nlp_circuit_failure_threshold,
                recovery_timeout=settings.google_nlp_circuit_recovery_timeout,
            ),
            name="google_nlp",
        )

        # HTTP client (created lazily)
        self._client: httpx.AsyncClient | None = None
        self._available = bool(self._api_key)

    @property
    def available(self) -> bool:
        """Check if Google Cloud NLP is configured and available."""
        return self._available

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=GOOGLE_NLP_API_URL,
                timeout=httpx.Timeout(self._timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("Google Cloud NLP client closed")

    async def analyze_entities(
        self,
        text: str,
        encoding_type: str = "UTF8",
    ) -> EntityExtractionResult:
        """Extract entities from text using Google Cloud NLP.

        Args:
            text: The text content to analyze
            encoding_type: Text encoding type (UTF8, UTF16, UTF32, NONE)

        Returns:
            EntityExtractionResult with extracted entities
        """
        if not self._available:
            return EntityExtractionResult(
                success=False,
                text=text,
                error="Google Cloud NLP not configured (missing API key)",
            )

        if not await self._circuit_breaker.can_execute():
            google_nlp_logger.graceful_fallback(
                "analyze_entities", "Circuit breaker open"
            )
            return EntityExtractionResult(
                success=False,
                text=text,
                error="Circuit breaker is open",
            )

        start_time = time.monotonic()
        client = await self._get_client()
        last_error: Exception | None = None
        request_id: str | None = None

        endpoint = f"/{GOOGLE_NLP_API_VERSION}/documents:analyzeEntities"

        # Build request body
        request_body: dict[str, Any] = {
            "document": {
                "type": "PLAIN_TEXT",
                "content": text,
            },
            "encodingType": encoding_type,
        }

        google_nlp_logger.entity_extraction_start(len(text))

        for attempt in range(self._max_retries):
            attempt_start = time.monotonic()

            try:
                # Log request start
                google_nlp_logger.api_call_start(
                    endpoint,
                    len(text),
                    retry_attempt=attempt,
                    request_id=request_id,
                )
                google_nlp_logger.request_body(endpoint, text, encoding_type)

                # Make request with API key as query parameter
                response = await client.post(
                    endpoint,
                    json=request_body,
                    params={"key": self._api_key},
                )
                duration_ms = (time.monotonic() - attempt_start) * 1000

                # Extract request ID from response headers if available
                request_id = response.headers.get("x-goog-request-id")

                # Handle response based on status code
                if response.status_code == 429:
                    # Rate limited
                    retry_after_str = response.headers.get("retry-after")
                    retry_after = float(retry_after_str) if retry_after_str else None
                    google_nlp_logger.rate_limit(
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
                    google_nlp_logger.entity_extraction_complete(
                        len(text), total_duration_ms, success=False
                    )
                    return EntityExtractionResult(
                        success=False,
                        text=text,
                        error="Rate limit exceeded",
                        status_code=429,
                        request_id=request_id,
                        duration_ms=duration_ms,
                    )

                if response.status_code in (401, 403):
                    # Auth failure
                    google_nlp_logger.auth_failure(response.status_code)
                    google_nlp_logger.api_call_error(
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
                    google_nlp_logger.entity_extraction_complete(
                        len(text), total_duration_ms, success=False
                    )
                    return EntityExtractionResult(
                        success=False,
                        text=text,
                        error=f"Authentication failed ({response.status_code})",
                        status_code=response.status_code,
                        request_id=request_id,
                        duration_ms=duration_ms,
                    )

                if response.status_code >= 500:
                    # Server error - retry
                    error_msg = f"Server error ({response.status_code})"
                    google_nlp_logger.api_call_error(
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
                            f"Google Cloud NLP request attempt {attempt + 1} failed, "
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
                    google_nlp_logger.entity_extraction_complete(
                        len(text), total_duration_ms, success=False
                    )
                    return EntityExtractionResult(
                        success=False,
                        text=text,
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
                    google_nlp_logger.api_call_error(
                        endpoint,
                        duration_ms,
                        response.status_code,
                        error_msg,
                        "ClientError",
                        retry_attempt=attempt,
                        request_id=request_id,
                    )
                    total_duration_ms = (time.monotonic() - start_time) * 1000
                    google_nlp_logger.entity_extraction_complete(
                        len(text), total_duration_ms, success=False
                    )
                    return EntityExtractionResult(
                        success=False,
                        text=text,
                        error=f"Client error ({response.status_code}): {error_msg}",
                        status_code=response.status_code,
                        request_id=request_id,
                        duration_ms=duration_ms,
                    )

                # Success - parse response
                response_data = response.json()
                total_duration_ms = (time.monotonic() - start_time) * 1000

                # Extract entities
                entities: list[Entity] = []
                raw_entities = response_data.get("entities", [])
                for raw_entity in raw_entities:
                    entity = Entity(
                        name=raw_entity.get("name", ""),
                        type=raw_entity.get("type", "UNKNOWN"),
                        salience=raw_entity.get("salience", 0.0),
                        mentions=raw_entity.get("mentions", []),
                        metadata=raw_entity.get("metadata", {}),
                    )
                    entities.append(entity)

                # Extract language if available
                language = response_data.get("language")

                # Log success
                google_nlp_logger.api_call_success(
                    endpoint,
                    duration_ms,
                    entity_count=len(entities),
                    request_id=request_id,
                )
                google_nlp_logger.response_body(endpoint, len(entities), duration_ms)
                google_nlp_logger.entity_extraction_complete(
                    len(text),
                    total_duration_ms,
                    success=True,
                    entity_count=len(entities),
                )

                await self._circuit_breaker.record_success()

                return EntityExtractionResult(
                    success=True,
                    text=text,
                    entities=entities,
                    language=language,
                    request_id=request_id,
                    duration_ms=total_duration_ms,
                )

            except httpx.TimeoutException:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                google_nlp_logger.timeout(endpoint, self._timeout)
                google_nlp_logger.api_call_error(
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
                        f"Google Cloud NLP request attempt {attempt + 1} timed out, "
                        f"retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self._max_retries,
                            "delay_seconds": delay,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                last_error = GoogleNLPTimeoutError(
                    f"Request timed out after {self._timeout}s"
                )

            except httpx.RequestError as e:
                duration_ms = (time.monotonic() - attempt_start) * 1000
                google_nlp_logger.api_call_error(
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
                        f"Google Cloud NLP request attempt {attempt + 1} failed, "
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

                last_error = GoogleNLPError(f"Request failed: {e}")

        total_duration_ms = (time.monotonic() - start_time) * 1000
        google_nlp_logger.entity_extraction_complete(
            len(text), total_duration_ms, success=False
        )
        if last_error:
            return EntityExtractionResult(
                success=False,
                text=text,
                error=str(last_error),
                duration_ms=total_duration_ms,
                request_id=request_id,
            )
        return EntityExtractionResult(
            success=False,
            text=text,
            error="Request failed after all retries",
            duration_ms=total_duration_ms,
            request_id=request_id,
        )

    async def extract_entities_batch(
        self,
        texts: list[str],
        encoding_type: str = "UTF8",
    ) -> list[EntityExtractionResult]:
        """Extract entities from multiple texts.

        Processes texts sequentially to respect API rate limits.

        Args:
            texts: List of text contents to analyze
            encoding_type: Text encoding type

        Returns:
            List of EntityExtractionResult objects
        """
        if not texts:
            return []

        results: list[EntityExtractionResult] = []
        total_texts = len(texts)
        total_entities = 0

        # Process texts sequentially
        for i, text in enumerate(texts):
            google_nlp_logger.batch_start(
                batch_index=i,
                batch_size=1,
                total_batches=total_texts,
                total_texts=total_texts,
            )

            result = await self.analyze_entities(text, encoding_type)
            results.append(result)

            if result.success:
                total_entities += len(result.entities)
                google_nlp_logger.batch_complete(
                    batch_index=i,
                    batch_size=1,
                    total_batches=total_texts,
                    success_count=1,
                    failure_count=0,
                    duration_ms=result.duration_ms,
                    total_entities=len(result.entities),
                )
            else:
                google_nlp_logger.batch_complete(
                    batch_index=i,
                    batch_size=1,
                    total_batches=total_texts,
                    success_count=0,
                    failure_count=1,
                    duration_ms=result.duration_ms,
                    total_entities=0,
                )

        return results

    def get_entities_by_type(
        self,
        result: EntityExtractionResult,
        entity_type: str | EntityType,
    ) -> list[Entity]:
        """Filter entities by type from a result.

        Args:
            result: EntityExtractionResult to filter
            entity_type: Entity type to filter by (string or EntityType enum)

        Returns:
            List of entities matching the specified type
        """
        if isinstance(entity_type, EntityType):
            entity_type = entity_type.value

        return [e for e in result.entities if e.type == entity_type]

    def get_top_entities(
        self,
        result: EntityExtractionResult,
        n: int = 10,
        min_salience: float = 0.0,
    ) -> list[Entity]:
        """Get top entities by salience score.

        Args:
            result: EntityExtractionResult to analyze
            n: Maximum number of entities to return
            min_salience: Minimum salience score threshold

        Returns:
            List of top entities sorted by salience
        """
        filtered = [e for e in result.entities if e.salience >= min_salience]
        sorted_entities = sorted(filtered, key=lambda e: e.salience, reverse=True)
        return sorted_entities[:n]


# Global Google Cloud NLP client instance
google_nlp_client: GoogleNLPClient | None = None


async def init_google_nlp() -> GoogleNLPClient:
    """Initialize the global Google Cloud NLP client.

    Returns:
        Initialized GoogleNLPClient instance
    """
    global google_nlp_client
    if google_nlp_client is None:
        google_nlp_client = GoogleNLPClient()
        if google_nlp_client.available:
            logger.info("Google Cloud NLP client initialized")
        else:
            logger.info("Google Cloud NLP not configured (missing API key)")
    return google_nlp_client


async def close_google_nlp() -> None:
    """Close the global Google Cloud NLP client."""
    global google_nlp_client
    if google_nlp_client:
        await google_nlp_client.close()
        google_nlp_client = None


async def get_google_nlp() -> GoogleNLPClient:
    """Dependency for getting Google Cloud NLP client.

    Usage:
        @app.get("/entities")
        async def extract_entities(
            text: str,
            nlp: GoogleNLPClient = Depends(get_google_nlp)
        ):
            result = await nlp.analyze_entities(text)
            ...
    """
    global google_nlp_client
    if google_nlp_client is None:
        await init_google_nlp()
    return google_nlp_client  # type: ignore[return-value]
