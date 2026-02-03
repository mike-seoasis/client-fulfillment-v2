"""Unit tests for S3 integration client.

Tests cover:
- upload_file() stores file and returns key
- get_file() retrieves file content
- delete_file() removes file
- file_exists() checks object existence
- get_file_metadata() retrieves object metadata
- Circuit breaker state transitions on S3 failures
- Retry logic with various error codes
- Not-found errors don't trip circuit breaker

Uses unittest.mock for mocking boto3 client.
"""

import asyncio
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.core.circuit_breaker import CircuitState
from app.integrations.s3 import (
    S3AuthError,
    S3CircuitOpenError,
    S3Client,
    S3ConnectionError,
    S3Error,
    S3NotFoundError,
)

# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for S3 client."""
    settings = MagicMock()
    settings.s3_bucket = "test-bucket"
    settings.s3_endpoint_url = "http://localhost:4566"
    settings.s3_access_key = "test-access-key"
    settings.s3_secret_key = "test-secret-key"
    settings.s3_region = "us-east-1"
    settings.s3_timeout = 5.0
    settings.s3_max_retries = 3
    settings.s3_retry_delay = 0.01  # Fast for tests
    settings.s3_circuit_failure_threshold = 3
    settings.s3_circuit_recovery_timeout = 1.0
    return settings


@pytest.fixture
def mock_boto_client() -> MagicMock:
    """Create a mock boto3 S3 client."""
    return MagicMock()


@pytest.fixture
def s3_client(mock_settings: MagicMock) -> S3Client:
    """Create an S3Client instance with mocked settings."""
    with patch("app.integrations.s3.get_settings", return_value=mock_settings):
        return S3Client()


def make_client_error(code: str, message: str = "Test error") -> Exception:
    """Create a botocore ClientError with specified error code."""
    from botocore.exceptions import ClientError

    error: Exception = ClientError(
        {"Error": {"Code": code, "Message": message}},
        "test_operation",
    )
    return error


# ---------------------------------------------------------------------------
# S3Client Initialization Tests
# ---------------------------------------------------------------------------


class TestS3ClientInit:
    """Tests for S3Client initialization."""

    def test_client_is_available_with_valid_config(
        self, mock_settings: MagicMock
    ) -> None:
        """Test client reports available with valid configuration."""
        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        assert client.available is True
        assert client.bucket == "test-bucket"

    def test_client_not_available_without_bucket(
        self, mock_settings: MagicMock
    ) -> None:
        """Test client reports not available without bucket."""
        mock_settings.s3_bucket = None

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        assert client.available is False

    def test_client_not_available_without_access_key(
        self, mock_settings: MagicMock
    ) -> None:
        """Test client reports not available without access key."""
        mock_settings.s3_access_key = None

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        assert client.available is False

    def test_client_not_available_without_secret_key(
        self, mock_settings: MagicMock
    ) -> None:
        """Test client reports not available without secret key."""
        mock_settings.s3_secret_key = None

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        assert client.available is False

    def test_client_accepts_override_params(self, mock_settings: MagicMock) -> None:
        """Test client accepts constructor override parameters."""
        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client(
                bucket="override-bucket",
                endpoint_url="http://custom:9000",
                access_key="custom-key",
                secret_key="custom-secret",
                region="eu-west-1",
            )

        assert client.bucket == "override-bucket"
        assert client._endpoint_url == "http://custom:9000"
        assert client._access_key == "custom-key"
        assert client._secret_key == "custom-secret"
        assert client._region == "eu-west-1"


# ---------------------------------------------------------------------------
# upload_file Tests
# ---------------------------------------------------------------------------


class TestUploadFile:
    """Tests for S3Client.upload_file() method."""

    @pytest.mark.asyncio
    async def test_upload_file_success_with_bytes(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test successful file upload with bytes."""
        s3_client._client = mock_boto_client

        result = await s3_client.upload_file(
            key="test/file.txt",
            file_obj=b"Hello, World!",
            content_type="text/plain",
        )

        assert result == "test/file.txt"
        mock_boto_client.upload_fileobj.assert_called_once()
        call_args = mock_boto_client.upload_fileobj.call_args
        assert call_args.args[1] == "test-bucket"
        assert call_args.args[2] == "test/file.txt"
        assert call_args.kwargs["ExtraArgs"]["ContentType"] == "text/plain"

    @pytest.mark.asyncio
    async def test_upload_file_success_with_file_object(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test successful file upload with file-like object."""
        s3_client._client = mock_boto_client
        file_obj = BytesIO(b"File content")

        result = await s3_client.upload_file(
            key="test/document.pdf",
            file_obj=file_obj,
            content_type="application/pdf",
        )

        assert result == "test/document.pdf"
        mock_boto_client.upload_fileobj.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_default_content_type(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test upload uses default content type."""
        s3_client._client = mock_boto_client

        await s3_client.upload_file(key="test/file.bin", file_obj=b"binary data")

        call_args = mock_boto_client.upload_fileobj.call_args
        assert call_args.kwargs["ExtraArgs"]["ContentType"] == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_upload_file_not_configured_raises_error(
        self, mock_settings: MagicMock
    ) -> None:
        """Test upload fails when S3 not configured."""
        mock_settings.s3_bucket = None

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        with pytest.raises(S3Error) as exc_info:
            await client.upload_file(key="test/file.txt", file_obj=b"data")

        assert "not configured" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# get_file Tests
# ---------------------------------------------------------------------------


class TestGetFile:
    """Tests for S3Client.get_file() method."""

    @pytest.mark.asyncio
    async def test_get_file_success(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test successful file retrieval."""
        mock_body = MagicMock()
        mock_body.read.return_value = b"File content"
        mock_boto_client.get_object.return_value = {"Body": mock_body}
        s3_client._client = mock_boto_client

        result = await s3_client.get_file("test/file.txt")

        assert result == b"File content"
        mock_boto_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_get_file_not_found_raises_error(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test get_file raises S3NotFoundError for missing object."""
        mock_boto_client.get_object.side_effect = make_client_error(
            "NoSuchKey", "Object not found"
        )
        s3_client._client = mock_boto_client

        with pytest.raises(S3NotFoundError) as exc_info:
            await s3_client.get_file("nonexistent/file.txt")

        assert "nonexistent/file.txt" in str(exc_info.value)


# ---------------------------------------------------------------------------
# delete_file Tests
# ---------------------------------------------------------------------------


class TestDeleteFile:
    """Tests for S3Client.delete_file() method."""

    @pytest.mark.asyncio
    async def test_delete_file_success(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test successful file deletion."""
        s3_client._client = mock_boto_client

        result = await s3_client.delete_file("test/file.txt")

        assert result is True
        mock_boto_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_delete_file_idempotent(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test delete_file succeeds even if object doesn't exist (S3 behavior)."""
        # S3 delete_object doesn't raise an error for non-existent keys
        s3_client._client = mock_boto_client

        result = await s3_client.delete_file("nonexistent/file.txt")

        assert result is True


# ---------------------------------------------------------------------------
# file_exists Tests
# ---------------------------------------------------------------------------


class TestFileExists:
    """Tests for S3Client.file_exists() method."""

    @pytest.mark.asyncio
    async def test_file_exists_returns_true_when_exists(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test file_exists returns True for existing object."""
        mock_boto_client.head_object.return_value = {
            "ContentLength": 100,
            "ContentType": "text/plain",
        }
        s3_client._client = mock_boto_client

        result = await s3_client.file_exists("test/file.txt")

        assert result is True
        mock_boto_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/file.txt"
        )

    @pytest.mark.asyncio
    async def test_file_exists_returns_false_when_not_exists(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test file_exists returns False for non-existing object."""
        mock_boto_client.head_object.side_effect = make_client_error(
            "404", "Not Found"
        )
        s3_client._client = mock_boto_client

        result = await s3_client.file_exists("nonexistent/file.txt")

        assert result is False


# ---------------------------------------------------------------------------
# get_file_metadata Tests
# ---------------------------------------------------------------------------


class TestGetFileMetadata:
    """Tests for S3Client.get_file_metadata() method."""

    @pytest.mark.asyncio
    async def test_get_file_metadata_success(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test successful metadata retrieval."""
        from datetime import datetime

        last_modified = datetime(2024, 1, 15, 10, 30, 0)
        mock_boto_client.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "application/pdf",
            "LastModified": last_modified,
            "ETag": '"abc123"',
        }
        s3_client._client = mock_boto_client

        result = await s3_client.get_file_metadata("test/document.pdf")

        assert result["content_length"] == 1024
        assert result["content_type"] == "application/pdf"
        assert result["last_modified"] == last_modified
        assert result["etag"] == '"abc123"'

    @pytest.mark.asyncio
    async def test_get_file_metadata_not_found_raises_error(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test get_file_metadata raises S3NotFoundError for missing object."""
        mock_boto_client.head_object.side_effect = make_client_error(
            "404", "Not Found"
        )
        s3_client._client = mock_boto_client

        with pytest.raises(S3NotFoundError):
            await s3_client.get_file_metadata("nonexistent/file.txt")


# ---------------------------------------------------------------------------
# Circuit Breaker Tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for circuit breaker behavior on S3 failures."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_repeated_failures(
        self, mock_settings: MagicMock
    ) -> None:
        """Test circuit opens after reaching failure threshold."""
        mock_settings.s3_circuit_failure_threshold = 3
        mock_settings.s3_max_retries = 1  # Reduce retries for faster test

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        mock_boto_client = MagicMock()
        # Simulate server error that triggers circuit breaker
        mock_boto_client.get_object.side_effect = make_client_error(
            "InternalError", "Server error"
        )
        client._client = mock_boto_client

        # Make multiple failing requests to trip the circuit
        for _ in range(3):
            with pytest.raises(S3Error):
                await client.get_file("test/file.txt")

        # Verify circuit is now open
        assert client.circuit_breaker.is_open

    @pytest.mark.asyncio
    async def test_circuit_rejects_requests_when_open(
        self, mock_settings: MagicMock
    ) -> None:
        """Test requests are rejected when circuit is open."""
        mock_settings.s3_circuit_failure_threshold = 2
        mock_settings.s3_max_retries = 1

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        mock_boto_client = MagicMock()
        mock_boto_client.get_object.side_effect = make_client_error(
            "InternalError", "Server error"
        )
        client._client = mock_boto_client

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(S3Error):
                await client.get_file("test/file.txt")

        assert client.circuit_breaker.is_open

        # Next request should fail immediately with circuit open error
        with pytest.raises(S3CircuitOpenError):
            await client.get_file("test/file.txt")

    @pytest.mark.asyncio
    async def test_circuit_allows_request_after_recovery_timeout(
        self, mock_settings: MagicMock
    ) -> None:
        """Test circuit transitions to half-open after recovery timeout."""
        mock_settings.s3_circuit_failure_threshold = 2
        mock_settings.s3_circuit_recovery_timeout = 0.1  # Fast recovery for test
        mock_settings.s3_max_retries = 1

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        mock_boto_client = MagicMock()
        mock_boto_client.get_object.side_effect = make_client_error(
            "InternalError", "Server error"
        )
        client._client = mock_boto_client

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(S3Error):
                await client.get_file("test/file.txt")

        assert client.circuit_breaker.is_open

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Setup success response
        mock_body = MagicMock()
        mock_body.read.return_value = b"content"
        mock_boto_client.get_object.side_effect = None
        mock_boto_client.get_object.return_value = {"Body": mock_body}

        # Request should succeed and close circuit
        result = await client.get_file("test/file.txt")
        assert result == b"content"
        assert client.circuit_breaker.is_closed

    @pytest.mark.asyncio
    async def test_not_found_error_does_not_trip_circuit(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test S3NotFoundError does not increment circuit breaker failures."""
        mock_boto_client.get_object.side_effect = make_client_error(
            "NoSuchKey", "Object not found"
        )
        s3_client._client = mock_boto_client

        initial_failure_count = s3_client.circuit_breaker.failure_count

        # Make multiple not-found requests
        for _ in range(5):
            with pytest.raises(S3NotFoundError):
                await s3_client.get_file("nonexistent/file.txt")

        # Circuit should still be closed - not-found is expected behavior
        assert s3_client.circuit_breaker.is_closed
        assert s3_client.circuit_breaker.failure_count == initial_failure_count


# ---------------------------------------------------------------------------
# Retry Logic Tests
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Tests for S3Client retry logic."""

    @pytest.mark.asyncio
    async def test_retries_on_server_error(
        self, mock_settings: MagicMock
    ) -> None:
        """Test client retries on server errors."""
        mock_settings.s3_retry_delay = 0.01

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        mock_boto_client = MagicMock()

        # First two calls fail, third succeeds
        mock_body = MagicMock()
        mock_body.read.return_value = b"success"
        mock_boto_client.get_object.side_effect = [
            make_client_error("InternalError", "Server error"),
            make_client_error("ServiceUnavailable", "Service unavailable"),
            {"Body": mock_body},
        ]
        client._client = mock_boto_client

        result = await client.get_file("test/file.txt")

        assert result == b"success"
        assert mock_boto_client.get_object.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_auth_error(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test client does not retry on authentication errors."""
        mock_boto_client.get_object.side_effect = make_client_error(
            "AccessDenied", "Access denied"
        )
        s3_client._client = mock_boto_client

        with pytest.raises(S3AuthError):
            await s3_client.get_file("test/file.txt")

        # Should not retry auth errors
        assert mock_boto_client.get_object.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_invalid_access_key(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test client does not retry on InvalidAccessKeyId."""
        mock_boto_client.get_object.side_effect = make_client_error(
            "InvalidAccessKeyId", "Invalid access key"
        )
        s3_client._client = mock_boto_client

        with pytest.raises(S3AuthError):
            await s3_client.get_file("test/file.txt")

        assert mock_boto_client.get_object.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_signature_error(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test client does not retry on SignatureDoesNotMatch."""
        mock_boto_client.get_object.side_effect = make_client_error(
            "SignatureDoesNotMatch", "Signature mismatch"
        )
        s3_client._client = mock_boto_client

        with pytest.raises(S3AuthError):
            await s3_client.get_file("test/file.txt")

        assert mock_boto_client.get_object.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_not_found(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test client does not retry on NoSuchKey."""
        mock_boto_client.get_object.side_effect = make_client_error(
            "NoSuchKey", "Object not found"
        )
        s3_client._client = mock_boto_client

        with pytest.raises(S3NotFoundError):
            await s3_client.get_file("test/file.txt")

        # Should not retry not-found errors
        assert mock_boto_client.get_object.call_count == 1

    @pytest.mark.asyncio
    async def test_bucket_not_found_raises_error(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test NoSuchBucket raises S3Error."""
        mock_boto_client.get_object.side_effect = make_client_error(
            "NoSuchBucket", "Bucket not found"
        )
        s3_client._client = mock_boto_client

        with pytest.raises(S3Error) as exc_info:
            await s3_client.get_file("test/file.txt")

        assert "Bucket not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(
        self, mock_settings: MagicMock
    ) -> None:
        """Test client retries on connection errors."""
        from botocore.exceptions import EndpointConnectionError

        mock_settings.s3_retry_delay = 0.01

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        mock_boto_client = MagicMock()

        # First two calls fail with connection error, third succeeds
        mock_body = MagicMock()
        mock_body.read.return_value = b"success"
        mock_boto_client.get_object.side_effect = [
            EndpointConnectionError(endpoint_url="http://localhost:4566"),
            EndpointConnectionError(endpoint_url="http://localhost:4566"),
            {"Body": mock_body},
        ]
        client._client = mock_boto_client

        result = await client.get_file("test/file.txt")

        assert result == b"success"
        assert mock_boto_client.get_object.call_count == 3

    @pytest.mark.asyncio
    async def test_connection_error_after_max_retries(
        self, mock_settings: MagicMock
    ) -> None:
        """Test connection error raises after max retries."""
        from botocore.exceptions import EndpointConnectionError

        mock_settings.s3_retry_delay = 0.01
        mock_settings.s3_max_retries = 2

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        mock_boto_client = MagicMock()
        mock_boto_client.get_object.side_effect = EndpointConnectionError(
            endpoint_url="http://localhost:4566"
        )
        client._client = mock_boto_client

        with pytest.raises(S3ConnectionError):
            await client.get_file("test/file.txt")


# ---------------------------------------------------------------------------
# Exception Tests
# ---------------------------------------------------------------------------


class TestS3Exceptions:
    """Tests for S3 exception classes."""

    def test_s3_error_basic(self) -> None:
        """Test S3Error basic usage."""
        error = S3Error("Test error")
        assert str(error) == "Test error"
        assert error.operation is None
        assert error.key is None

    def test_s3_error_with_details(self) -> None:
        """Test S3Error with all details."""
        error = S3Error(
            "Test error",
            operation="upload_file",
            key="test/file.txt",
        )
        assert error.operation == "upload_file"
        assert error.key == "test/file.txt"

    def test_s3_timeout_error(self) -> None:
        """Test S3TimeoutError."""
        from app.integrations.s3 import S3TimeoutError

        error = S3TimeoutError("Timeout after 30s", operation="get_file")
        assert "Timeout" in str(error)
        assert isinstance(error, S3Error)

    def test_s3_connection_error(self) -> None:
        """Test S3ConnectionError."""
        error = S3ConnectionError(
            "Connection failed",
            operation="upload_file",
            key="test/file.txt",
        )
        assert "Connection failed" in str(error)
        assert isinstance(error, S3Error)

    def test_s3_auth_error(self) -> None:
        """Test S3AuthError."""
        error = S3AuthError("Invalid credentials", operation="get_file")
        assert isinstance(error, S3Error)

    def test_s3_not_found_error(self) -> None:
        """Test S3NotFoundError."""
        error = S3NotFoundError(
            "Object not found",
            operation="get_file",
            key="test/file.txt",
        )
        assert isinstance(error, S3Error)
        assert error.key == "test/file.txt"

    def test_s3_circuit_open_error(self) -> None:
        """Test S3CircuitOpenError."""
        error = S3CircuitOpenError("Circuit breaker is open")
        assert "circuit" in str(error).lower()
        assert isinstance(error, S3Error)


# ---------------------------------------------------------------------------
# Edge Cases and Integration Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and integration scenarios."""

    @pytest.mark.asyncio
    async def test_upload_large_file(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test uploading a larger file works correctly."""
        s3_client._client = mock_boto_client
        # Simulate 1MB file
        large_content = b"x" * (1024 * 1024)

        result = await s3_client.upload_file(
            key="test/large-file.bin",
            file_obj=large_content,
        )

        assert result == "test/large-file.bin"
        mock_boto_client.upload_fileobj.assert_called_once()

    @pytest.mark.asyncio
    async def test_key_with_special_characters(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test operations with special characters in key."""
        s3_client._client = mock_boto_client
        special_key = "projects/uuid-123/files/Report (Final) - 2024.pdf"

        await s3_client.upload_file(
            key=special_key,
            file_obj=b"content",
        )

        call_args = mock_boto_client.upload_fileobj.call_args
        assert call_args.args[2] == special_key

    @pytest.mark.asyncio
    async def test_empty_file_upload(
        self, s3_client: S3Client, mock_boto_client: MagicMock
    ) -> None:
        """Test uploading an empty file."""
        s3_client._client = mock_boto_client

        result = await s3_client.upload_file(
            key="test/empty.txt",
            file_obj=b"",
        )

        assert result == "test/empty.txt"
        mock_boto_client.upload_fileobj.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_initial_state(
        self, s3_client: S3Client
    ) -> None:
        """Test circuit breaker starts in closed state."""
        assert s3_client.circuit_breaker.state == CircuitState.CLOSED
        assert s3_client.circuit_breaker.is_closed is True
        assert s3_client.circuit_breaker.is_open is False

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(
        self, mock_settings: MagicMock
    ) -> None:
        """Test successful operation resets circuit breaker failure count."""
        # Use higher failure threshold so we don't trip the circuit
        mock_settings.s3_circuit_failure_threshold = 10
        mock_settings.s3_max_retries = 1  # Fewer retries = fewer failures per call

        with patch("app.integrations.s3.get_settings", return_value=mock_settings):
            client = S3Client()

        mock_boto_client = MagicMock()
        # First, cause some failures (but not enough to trip circuit)
        mock_boto_client.get_object.side_effect = make_client_error(
            "InternalError", "Server error"
        )
        client._client = mock_boto_client

        with pytest.raises(S3Error):
            await client.get_file("test/file.txt")

        assert client.circuit_breaker.failure_count > 0
        initial_failures = client.circuit_breaker.failure_count

        # Now succeed
        mock_body = MagicMock()
        mock_body.read.return_value = b"content"
        mock_boto_client.get_object.side_effect = None
        mock_boto_client.get_object.return_value = {"Body": mock_body}

        await client.get_file("test/file.txt")

        # Failure count should be reset after success
        assert client.circuit_breaker.failure_count == 0
        assert client.circuit_breaker.failure_count < initial_failures
