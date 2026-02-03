"""S3 integration client with circuit breaker pattern.

Features:
- Boto3-based S3 client with S3-compatible API support
- Circuit breaker for fault tolerance
- Retry logic with exponential backoff
- Request/response logging
- LocalStack compatibility via endpoint_url

ERROR LOGGING REQUIREMENTS:
- Log all S3 operations with key, method, timing
- Log and handle: timeouts, auth failures, connection errors
- Include retry attempt number in logs
- Mask access keys in all logs
- Log circuit breaker state changes

RAILWAY/LOCALSTACK REQUIREMENTS:
- All credentials via environment variables
- Never log or expose credentials
- Use endpoint_url for LocalStack compatibility
"""

import asyncio
import time
from collections.abc import Callable
from io import BytesIO
from typing import Any, BinaryIO

import boto3
from botocore.config import Config as BotoConfig  # type: ignore[import-not-found]
from botocore.exceptions import (  # type: ignore[import-not-found]
    BotoCoreError,
    ClientError,
    ConnectionError,
    EndpointConnectionError,
)

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class S3Error(Exception):
    """Base exception for S3 errors."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        key: str | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.key = key


class S3TimeoutError(S3Error):
    """Raised when an S3 operation times out."""

    pass


class S3ConnectionError(S3Error):
    """Raised when connection to S3 fails."""

    pass


class S3AuthError(S3Error):
    """Raised when S3 authentication fails."""

    pass


class S3NotFoundError(S3Error):
    """Raised when S3 object is not found."""

    pass


class S3CircuitOpenError(S3Error):
    """Raised when circuit breaker is open."""

    pass


class S3Client:
    """Client for S3-compatible object storage.

    Provides file storage capabilities with:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Comprehensive logging
    - LocalStack/S3-compatible endpoint support
    """

    def __init__(
        self,
        bucket: str | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
    ) -> None:
        """Initialize S3 client.

        Args:
            bucket: S3 bucket name. Defaults to settings.
            endpoint_url: S3 endpoint URL for LocalStack. Defaults to settings.
            access_key: S3 access key. Defaults to settings.
            secret_key: S3 secret key. Defaults to settings.
            region: S3 region. Defaults to settings.
            timeout: Operation timeout in seconds. Defaults to settings.
            max_retries: Maximum retry attempts. Defaults to settings.
            retry_delay: Base delay between retries. Defaults to settings.
        """
        settings = get_settings()

        self._bucket = bucket or settings.s3_bucket
        self._endpoint_url = endpoint_url or settings.s3_endpoint_url
        self._access_key = access_key or settings.s3_access_key
        self._secret_key = secret_key or settings.s3_secret_key
        self._region = region or settings.s3_region
        self._timeout = timeout or settings.s3_timeout
        self._max_retries = max_retries or settings.s3_max_retries
        self._retry_delay = retry_delay or settings.s3_retry_delay

        # Initialize circuit breaker
        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=settings.s3_circuit_failure_threshold,
                recovery_timeout=settings.s3_circuit_recovery_timeout,
            ),
            name="s3",
        )

        # S3 client (created lazily)
        self._client: boto3.client | None = None
        self._available = bool(self._bucket and self._access_key and self._secret_key)

    @property
    def available(self) -> bool:
        """Check if S3 is configured and available."""
        return self._available

    @property
    def bucket(self) -> str | None:
        """Get the configured bucket name."""
        return self._bucket

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Get the circuit breaker instance."""
        return self._circuit_breaker

    def _get_client(self) -> boto3.client:
        """Get or create S3 client."""
        if self._client is None:
            boto_config = BotoConfig(
                connect_timeout=self._timeout,
                read_timeout=self._timeout,
                retries={"max_attempts": 0},  # We handle retries ourselves
            )

            client_kwargs = {
                "service_name": "s3",
                "aws_access_key_id": self._access_key,
                "aws_secret_access_key": self._secret_key,
                "region_name": self._region,
                "config": boto_config,
            }

            if self._endpoint_url:
                client_kwargs["endpoint_url"] = self._endpoint_url

            self._client = boto3.client(**client_kwargs)

        return self._client

    def _log_operation_start(
        self,
        operation: str,
        key: str | None = None,
        retry_attempt: int = 0,
    ) -> None:
        """Log operation start."""
        logger.debug(
            f"S3 {operation} started",
            extra={
                "s3_operation": operation,
                "s3_key": key,
                "s3_bucket": self._bucket,
                "retry_attempt": retry_attempt,
            },
        )

    def _log_operation_success(
        self,
        operation: str,
        duration_ms: float,
        key: str | None = None,
        **extra: object,
    ) -> None:
        """Log successful operation."""
        logger.info(
            f"S3 {operation} completed",
            extra={
                "s3_operation": operation,
                "s3_key": key,
                "s3_bucket": self._bucket,
                "duration_ms": round(duration_ms, 2),
                **extra,
            },
        )

    def _log_operation_error(
        self,
        operation: str,
        duration_ms: float,
        error: str,
        error_type: str,
        key: str | None = None,
        retry_attempt: int = 0,
    ) -> None:
        """Log operation error."""
        logger.error(
            f"S3 {operation} failed: {error}",
            extra={
                "s3_operation": operation,
                "s3_key": key,
                "s3_bucket": self._bucket,
                "duration_ms": round(duration_ms, 2),
                "error": error,
                "error_type": error_type,
                "retry_attempt": retry_attempt,
            },
        )

    async def _execute_with_retry(
        self,
        operation: str,
        func: Callable[[], Any],
        key: str | None = None,
    ) -> Any:
        """Execute an S3 operation with retry logic and circuit breaker.

        Args:
            operation: Operation name for logging
            func: Synchronous function to execute
            key: S3 key being operated on (for logging)

        Returns:
            Result of the operation

        Raises:
            S3CircuitOpenError: If circuit breaker is open
            S3TimeoutError: If operation times out
            S3AuthError: If authentication fails
            S3NotFoundError: If object not found
            S3Error: For other errors
        """
        if not self._available:
            raise S3Error(
                "S3 not configured (missing bucket, access_key, or secret_key)",
                operation=operation,
                key=key,
            )

        if not await self._circuit_breaker.can_execute():
            logger.warning(
                f"S3 {operation} blocked by circuit breaker",
                extra={"s3_operation": operation, "s3_key": key},
            )
            raise S3CircuitOpenError(
                "Circuit breaker is open", operation=operation, key=key
            )

        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            start_time = time.monotonic()

            try:
                self._log_operation_start(operation, key, attempt)

                # Run sync boto3 operation in thread pool
                loop = asyncio.get_event_loop()
                result: Any = await loop.run_in_executor(None, func)

                duration_ms = (time.monotonic() - start_time) * 1000
                self._log_operation_success(operation, duration_ms, key)
                await self._circuit_breaker.record_success()
                return result

            except ClientError as e:
                duration_ms = (time.monotonic() - start_time) * 1000
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_message = e.response.get("Error", {}).get("Message", str(e))

                self._log_operation_error(
                    operation,
                    duration_ms,
                    error_message,
                    f"ClientError:{error_code}",
                    key,
                    attempt,
                )

                # Handle specific error codes
                if error_code in ("AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"):
                    await self._circuit_breaker.record_failure()
                    raise S3AuthError(
                        f"Authentication failed: {error_message}",
                        operation=operation,
                        key=key,
                    )

                if error_code in ("NoSuchKey", "404"):
                    # Don't record as circuit failure - this is expected behavior
                    raise S3NotFoundError(
                        f"Object not found: {key}",
                        operation=operation,
                        key=key,
                    )

                if error_code == "NoSuchBucket":
                    await self._circuit_breaker.record_failure()
                    raise S3Error(
                        f"Bucket not found: {self._bucket}",
                        operation=operation,
                        key=key,
                    )

                # For other errors, retry
                await self._circuit_breaker.record_failure()
                last_error = S3Error(
                    f"S3 error ({error_code}): {error_message}",
                    operation=operation,
                    key=key,
                )

            except (EndpointConnectionError, ConnectionError) as e:
                duration_ms = (time.monotonic() - start_time) * 1000
                self._log_operation_error(
                    operation,
                    duration_ms,
                    str(e),
                    "ConnectionError",
                    key,
                    attempt,
                )
                await self._circuit_breaker.record_failure()
                last_error = S3ConnectionError(
                    f"Connection failed: {e}",
                    operation=operation,
                    key=key,
                )

            except BotoCoreError as e:
                duration_ms = (time.monotonic() - start_time) * 1000
                self._log_operation_error(
                    operation,
                    duration_ms,
                    str(e),
                    type(e).__name__,
                    key,
                    attempt,
                )
                await self._circuit_breaker.record_failure()
                last_error = S3Error(
                    f"S3 error: {e}",
                    operation=operation,
                    key=key,
                )

            # Retry with exponential backoff
            if attempt < self._max_retries - 1:
                delay = self._retry_delay * (2**attempt)
                logger.warning(
                    f"S3 {operation} attempt {attempt + 1} failed, retrying in {delay}s",
                    extra={
                        "s3_operation": operation,
                        "s3_key": key,
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "delay_seconds": delay,
                    },
                )
                await asyncio.sleep(delay)

        if last_error:
            raise last_error
        raise S3Error(
            "Operation failed after all retries",
            operation=operation,
            key=key,
        )

    async def upload_file(
        self,
        key: str,
        file_obj: BinaryIO | bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to S3.

        Args:
            key: S3 object key (path/filename)
            file_obj: File-like object or bytes to upload
            content_type: MIME type of the content

        Returns:
            The S3 key of the uploaded object

        Raises:
            S3Error: If upload fails
        """
        client = self._get_client()

        # Convert bytes to file-like object if needed
        if isinstance(file_obj, bytes):
            file_obj = BytesIO(file_obj)

        def upload() -> str:
            client.upload_fileobj(
                file_obj,
                self._bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            return key

        await self._execute_with_retry("upload_file", upload, key)
        return key

    async def get_file(self, key: str) -> bytes:
        """Get a file from S3.

        Args:
            key: S3 object key

        Returns:
            File contents as bytes

        Raises:
            S3NotFoundError: If object does not exist
            S3Error: If download fails
        """
        client = self._get_client()

        def download() -> bytes:
            response = client.get_object(Bucket=self._bucket, Key=key)
            body: bytes = response["Body"].read()
            return body

        result = await self._execute_with_retry("get_file", download, key)
        return result  # type: ignore[no-any-return]

    async def delete_file(self, key: str) -> bool:
        """Delete a file from S3.

        Args:
            key: S3 object key

        Returns:
            True if deletion was successful

        Raises:
            S3Error: If deletion fails
        """
        client = self._get_client()

        def delete() -> bool:
            client.delete_object(Bucket=self._bucket, Key=key)
            return True

        result = await self._execute_with_retry("delete_file", delete, key)
        return result  # type: ignore[no-any-return]

    async def file_exists(self, key: str) -> bool:
        """Check if a file exists in S3.

        Args:
            key: S3 object key

        Returns:
            True if object exists, False otherwise
        """
        client = self._get_client()

        def head() -> bool:
            try:
                client.head_object(Bucket=self._bucket, Key=key)
                return True
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    return False
                raise

        try:
            result = await self._execute_with_retry("file_exists", head, key)
            return result  # type: ignore[no-any-return]
        except S3NotFoundError:
            return False

    async def get_file_metadata(self, key: str) -> dict[str, Any]:
        """Get metadata for an S3 object.

        Args:
            key: S3 object key

        Returns:
            Dict with ContentLength, ContentType, LastModified, etc.

        Raises:
            S3NotFoundError: If object does not exist
        """
        client = self._get_client()

        def head() -> dict[str, Any]:
            response = client.head_object(Bucket=self._bucket, Key=key)
            return {
                "content_length": response.get("ContentLength"),
                "content_type": response.get("ContentType"),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag"),
            }

        result = await self._execute_with_retry("get_file_metadata", head, key)
        return result  # type: ignore[no-any-return]


# Global S3 client instance
s3_client: S3Client | None = None


async def init_s3() -> S3Client:
    """Initialize the global S3 client.

    Returns:
        Initialized S3Client instance
    """
    global s3_client
    if s3_client is None:
        s3_client = S3Client()
        if s3_client.available:
            logger.info(
                "S3 client initialized",
                extra={"s3_bucket": s3_client.bucket},
            )
        else:
            logger.info("S3 not configured (missing credentials or bucket)")
    return s3_client


async def close_s3() -> None:
    """Close the global S3 client."""
    global s3_client
    if s3_client:
        # boto3 clients don't need explicit closing
        s3_client = None
        logger.info("S3 client closed")


async def get_s3() -> S3Client:
    """Dependency for getting S3 client.

    Usage:
        @app.post("/upload")
        async def upload_file(
            file: UploadFile,
            s3: S3Client = Depends(get_s3)
        ):
            key = await s3.upload_file(file.filename, file.file)
            ...
    """
    global s3_client
    if s3_client is None:
        await init_s3()
    return s3_client  # type: ignore[return-value]
