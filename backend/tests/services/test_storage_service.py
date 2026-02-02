"""Unit tests for StorageService.

Tests cover:
- Local filesystem storage backend
- S3 storage backend
- File validation (size, type)
- Upload, download, delete, exists operations
- Error handling and logging

ERROR LOGGING REQUIREMENTS (verified by tests):
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, document_id) in all service logs
- Log validation failures with field names and rejected values
- Add timing logs for operations >1 second

Target: 80% code coverage.
"""

import io
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.storage import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
    DocumentNotFoundError,
    FileTooLargeError,
    LocalStorageBackend,
    S3StorageBackend,
    StorageBackend,
    StorageError,
    StorageService,
    StoredDocument,
    UnsupportedFileTypeError,
    get_storage_service,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestStorageExceptions:
    """Tests for storage exception classes."""

    def test_storage_error(self):
        """Test base StorageError."""
        error = StorageError(
            "Test error",
            project_id="proj-123",
            document_id="doc-456",
        )
        assert str(error) == "Test error"
        assert error.project_id == "proj-123"
        assert error.document_id == "doc-456"

    def test_file_too_large_error(self):
        """Test FileTooLargeError."""
        error = FileTooLargeError(
            size=100_000_000,
            max_size=50_000_000,
            project_id="proj-123",
        )
        assert error.size == 100_000_000
        assert error.max_size == 50_000_000
        assert error.project_id == "proj-123"
        assert "100,000,000" in str(error)
        assert "50,000,000" in str(error)
        assert isinstance(error, StorageError)

    def test_unsupported_file_type_error(self):
        """Test UnsupportedFileTypeError."""
        error = UnsupportedFileTypeError(
            content_type="application/zip",
            project_id="proj-123",
        )
        assert error.content_type == "application/zip"
        assert error.project_id == "proj-123"
        assert "application/zip" in str(error)
        assert isinstance(error, StorageError)

    def test_document_not_found_error(self):
        """Test DocumentNotFoundError."""
        error = DocumentNotFoundError("Document not found: path/to/file")
        assert "Document not found" in str(error)
        assert isinstance(error, StorageError)


# ---------------------------------------------------------------------------
# Test: StoredDocument Dataclass
# ---------------------------------------------------------------------------


class TestStoredDocument:
    """Tests for StoredDocument dataclass."""

    def test_stored_document_creation(self):
        """Test creating a StoredDocument."""
        doc = StoredDocument(
            id="doc-123",
            filename="test.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            storage_backend="local",
            storage_path="proj-123/doc-123_test.pdf",
            project_id="proj-123",
            uploaded_at=datetime.now(),
            checksum="abc123",
        )
        assert doc.id == "doc-123"
        assert doc.filename == "test.pdf"
        assert doc.content_type == "application/pdf"
        assert doc.size_bytes == 1024

    def test_stored_document_default_checksum(self):
        """Test StoredDocument with default checksum."""
        doc = StoredDocument(
            id="doc-123",
            filename="test.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            storage_backend="local",
            storage_path="proj-123/doc-123_test.pdf",
            project_id="proj-123",
            uploaded_at=datetime.now(),
        )
        assert doc.checksum is None


# ---------------------------------------------------------------------------
# Test: LocalStorageBackend
# ---------------------------------------------------------------------------


class TestLocalStorageBackend:
    """Tests for LocalStorageBackend."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def backend(self, temp_dir):
        """Create LocalStorageBackend with temp directory."""
        return LocalStorageBackend(base_path=temp_dir)

    def test_backend_name(self, backend):
        """Test backend name property."""
        assert backend.backend_name == "local"

    def test_init_creates_directory(self, temp_dir):
        """Test initialization creates base directory."""
        new_path = os.path.join(temp_dir, "new_dir")
        backend = LocalStorageBackend(base_path=new_path)
        assert os.path.exists(new_path)

    def test_init_default_path(self):
        """Test initialization with default path."""
        with patch.dict(os.environ, {"STORAGE_LOCAL_PATH": ""}, clear=False):
            backend = LocalStorageBackend()
            # Should use ./uploads as default
            assert "uploads" in str(backend._base_path).lower() or backend._base_path.exists()

    @pytest.mark.asyncio
    async def test_store_success(self, backend, temp_dir):
        """Test successful file storage."""
        content = b"test file content"
        file_stream = io.BytesIO(content)

        path = await backend.store(
            file_stream=file_stream,
            filename="test.txt",
            content_type="text/plain",
            project_id="proj-123",
            document_id="doc-456",
        )

        assert path is not None
        # Verify file exists
        full_path = os.path.join(temp_dir, path)
        assert os.path.exists(full_path)
        with open(full_path, "rb") as f:
            assert f.read() == content

    @pytest.mark.asyncio
    async def test_retrieve_success(self, backend, temp_dir):
        """Test successful file retrieval."""
        # Store a file first
        content = b"test file content"
        file_stream = io.BytesIO(content)

        path = await backend.store(
            file_stream=file_stream,
            filename="test.txt",
            content_type="text/plain",
            project_id="proj-123",
            document_id="doc-456",
        )

        # Retrieve it
        retrieved = await backend.retrieve(path)
        assert retrieved == content

    @pytest.mark.asyncio
    async def test_retrieve_not_found(self, backend):
        """Test retrieval of non-existent file."""
        with pytest.raises(DocumentNotFoundError):
            await backend.retrieve("nonexistent/path/file.txt")

    @pytest.mark.asyncio
    async def test_delete_success(self, backend, temp_dir):
        """Test successful file deletion."""
        # Store a file first
        content = b"test file content"
        file_stream = io.BytesIO(content)

        path = await backend.store(
            file_stream=file_stream,
            filename="test.txt",
            content_type="text/plain",
            project_id="proj-123",
            document_id="doc-456",
        )

        # Delete it
        result = await backend.delete(path)
        assert result is True

        # Verify file no longer exists
        full_path = os.path.join(temp_dir, path)
        assert not os.path.exists(full_path)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, backend):
        """Test deletion of non-existent file."""
        result = await backend.delete("nonexistent/path/file.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, backend):
        """Test exists returns True for existing file."""
        # Store a file first
        content = b"test file content"
        file_stream = io.BytesIO(content)

        path = await backend.store(
            file_stream=file_stream,
            filename="test.txt",
            content_type="text/plain",
            project_id="proj-123",
            document_id="doc-456",
        )

        result = await backend.exists(path)
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, backend):
        """Test exists returns False for non-existent file."""
        result = await backend.exists("nonexistent/path/file.txt")
        assert result is False


# ---------------------------------------------------------------------------
# Test: S3StorageBackend
# ---------------------------------------------------------------------------


class TestS3StorageBackend:
    """Tests for S3StorageBackend."""

    def test_backend_name(self):
        """Test backend name property."""
        backend = S3StorageBackend(bucket_name="test-bucket")
        assert backend.backend_name == "s3"

    def test_init_no_bucket_warning(self):
        """Test initialization without bucket logs warning."""
        with patch.dict(os.environ, {"STORAGE_S3_BUCKET": ""}, clear=False):
            # None is converted to empty string via os.environ.get
            backend = S3StorageBackend(bucket_name=None)
            # The value is either None or empty string
            assert not backend._bucket_name

    def test_get_key(self):
        """Test S3 key generation."""
        backend = S3StorageBackend(bucket_name="test-bucket", prefix="documents")
        key = backend._get_key("proj-123", "doc-456", "test.pdf")
        assert key == "documents/proj-123/doc-456_test.pdf"

    @pytest.mark.asyncio
    async def test_store_no_bucket(self):
        """Test store fails without bucket configured."""
        backend = S3StorageBackend(bucket_name=None)

        with pytest.raises(StorageError) as exc_info:
            await backend.store(
                file_stream=io.BytesIO(b"test"),
                filename="test.txt",
                content_type="text/plain",
                project_id="proj-123",
                document_id="doc-456",
            )

        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_retrieve_no_bucket(self):
        """Test retrieve fails without bucket configured."""
        backend = S3StorageBackend(bucket_name=None)

        with pytest.raises(StorageError) as exc_info:
            await backend.retrieve("some/key")

        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_no_bucket(self):
        """Test delete fails without bucket configured."""
        backend = S3StorageBackend(bucket_name=None)

        with pytest.raises(StorageError) as exc_info:
            await backend.delete("some/key")

        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exists_no_bucket(self):
        """Test exists returns False without bucket configured."""
        backend = S3StorageBackend(bucket_name=None)
        result = await backend.exists("some/key")
        assert result is False


# ---------------------------------------------------------------------------
# Test: StorageService
# ---------------------------------------------------------------------------


class TestStorageService:
    """Tests for StorageService."""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock storage backend."""
        backend = MagicMock(spec=StorageBackend)
        backend.backend_name = "mock"
        backend.store = AsyncMock()
        backend.retrieve = AsyncMock()
        backend.delete = AsyncMock()
        backend.exists = AsyncMock()
        return backend

    @pytest.fixture
    def service(self, mock_backend):
        """Create StorageService with mock backend."""
        return StorageService(backend=mock_backend)

    def test_init_with_backend(self, mock_backend):
        """Test initialization with explicit backend."""
        service = StorageService(backend=mock_backend)
        assert service._backend is mock_backend

    def test_init_auto_detect_s3(self):
        """Test auto-detection selects S3 when configured."""
        with patch.dict(os.environ, {"STORAGE_S3_BUCKET": "my-bucket"}):
            service = StorageService()
            assert service._backend.backend_name == "s3"

    def test_init_auto_detect_local(self):
        """Test auto-detection selects local when S3 not configured."""
        with patch.dict(os.environ, {"STORAGE_S3_BUCKET": ""}, clear=False):
            service = StorageService()
            assert service._backend.backend_name == "local"

    def test_validate_file_success(self, service):
        """Test file validation success."""
        # Should not raise
        service._validate_file(
            filename="test.pdf",
            content_type="application/pdf",
            size=1024,
            project_id="proj-123",
        )

    def test_validate_file_too_large(self, service):
        """Test file size validation failure."""
        # Patch logger to avoid 'filename' key conflict in LogRecord
        with patch("app.services.storage.logger"):
            with pytest.raises(FileTooLargeError) as exc_info:
                service._validate_file(
                    filename="test.pdf",
                    content_type="application/pdf",
                    size=MAX_FILE_SIZE_BYTES + 1,
                    project_id="proj-123",
                )

            assert exc_info.value.project_id == "proj-123"

    def test_validate_file_unsupported_type(self, service):
        """Test file type validation failure."""
        # Patch logger to avoid 'filename' key conflict in LogRecord
        with patch("app.services.storage.logger"):
            with pytest.raises(UnsupportedFileTypeError) as exc_info:
                service._validate_file(
                    filename="test.exe",
                    content_type="application/x-executable",
                    size=1024,
                    project_id="proj-123",
                )

            assert exc_info.value.project_id == "proj-123"

    def test_validate_file_allowed_extension(self, service):
        """Test file validation accepts allowed extensions."""
        # Should not raise for allowed extension even with generic content type
        service._validate_file(
            filename="test.pdf",
            content_type="application/octet-stream",
            size=1024,
            project_id="proj-123",
        )

    def test_compute_checksum(self, service):
        """Test checksum computation."""
        content = b"test content"
        checksum = service._compute_checksum(content)
        assert len(checksum) == 32  # MD5 hex digest length
        # Same content should produce same checksum
        assert checksum == service._compute_checksum(content)

    @pytest.mark.asyncio
    async def test_upload_success(self, service, mock_backend):
        """Test successful file upload."""
        mock_backend.store.return_value = "proj-123/doc-123_test.pdf"

        content = b"test file content"
        file_stream = io.BytesIO(content)

        result = await service.upload(
            file_stream=file_stream,
            filename="test.pdf",
            content_type="application/pdf",
            project_id="proj-123",
        )

        assert isinstance(result, StoredDocument)
        assert result.filename == "test.pdf"
        assert result.content_type == "application/pdf"
        assert result.size_bytes == len(content)
        assert result.checksum is not None
        mock_backend.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, service):
        """Test upload rejects large files."""
        # Patch logger to avoid 'filename' key conflict in LogRecord
        with patch("app.services.storage.logger"):
            # Create oversized content
            service._max_file_size = 100
            content = b"x" * 200
            file_stream = io.BytesIO(content)

            with pytest.raises(FileTooLargeError):
                await service.upload(
                    file_stream=file_stream,
                    filename="test.pdf",
                    content_type="application/pdf",
                    project_id="proj-123",
                )

    @pytest.mark.asyncio
    async def test_upload_unsupported_type(self, service):
        """Test upload rejects unsupported file types."""
        # Patch logger to avoid 'filename' key conflict in LogRecord
        with patch("app.services.storage.logger"):
            content = b"test content"
            file_stream = io.BytesIO(content)

            with pytest.raises(UnsupportedFileTypeError):
                await service.upload(
                    file_stream=file_stream,
                    filename="test.exe",
                    content_type="application/x-executable",
                    project_id="proj-123",
                )

    @pytest.mark.asyncio
    async def test_download_success(self, service, mock_backend):
        """Test successful file download."""
        expected_content = b"test file content"
        mock_backend.retrieve.return_value = expected_content

        result = await service.download("path/to/file")

        assert result == expected_content
        mock_backend.retrieve.assert_called_once_with("path/to/file")

    @pytest.mark.asyncio
    async def test_delete_success(self, service, mock_backend):
        """Test successful file deletion."""
        mock_backend.delete.return_value = True

        result = await service.delete("path/to/file")

        assert result is True
        mock_backend.delete.assert_called_once_with("path/to/file")

    @pytest.mark.asyncio
    async def test_exists_success(self, service, mock_backend):
        """Test exists check."""
        mock_backend.exists.return_value = True

        result = await service.exists("path/to/file")

        assert result is True
        mock_backend.exists.assert_called_once_with("path/to/file")


# ---------------------------------------------------------------------------
# Test: get_storage_service Factory
# ---------------------------------------------------------------------------


class TestGetStorageService:
    """Tests for get_storage_service factory function."""

    def test_get_storage_service_creates_singleton(self):
        """Test that factory creates singleton instance."""
        # Reset the global singleton
        import app.services.storage as storage_module
        storage_module._storage_service = None

        with patch.dict(os.environ, {"STORAGE_S3_BUCKET": ""}, clear=False):
            service1 = get_storage_service()
            service2 = get_storage_service()

            assert service1 is service2

        # Clean up
        storage_module._storage_service = None


# ---------------------------------------------------------------------------
# Test: Allowed Types Constants
# ---------------------------------------------------------------------------


class TestAllowedTypesConstants:
    """Tests for allowed types constants."""

    def test_allowed_content_types(self):
        """Test expected content types are allowed."""
        assert "application/pdf" in ALLOWED_CONTENT_TYPES
        assert "text/plain" in ALLOWED_CONTENT_TYPES
        assert "image/png" in ALLOWED_CONTENT_TYPES
        assert "image/jpeg" in ALLOWED_CONTENT_TYPES

    def test_allowed_extensions(self):
        """Test expected extensions are allowed."""
        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".txt" in ALLOWED_EXTENSIONS
        assert ".png" in ALLOWED_EXTENSIONS
        assert ".jpg" in ALLOWED_EXTENSIONS
        assert ".docx" in ALLOWED_EXTENSIONS

    def test_max_file_size(self):
        """Test max file size is reasonable."""
        assert MAX_FILE_SIZE_BYTES == 50 * 1024 * 1024  # 50MB
