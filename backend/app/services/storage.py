"""Storage service with S3/local backend support.

Provides a unified interface for storing and retrieving documents
using either S3 or local filesystem storage.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, document_id) in all service logs
- Log validation failures with field names and rejected values
- Add timing logs for operations >1 second
"""

import hashlib
import os
import time
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp"}


class StorageError(Exception):
    """Base exception for storage errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        document_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.document_id = document_id


class FileTooLargeError(StorageError):
    """Raised when file exceeds maximum size."""

    def __init__(
        self,
        size: int,
        max_size: int,
        project_id: str | None = None,
    ) -> None:
        super().__init__(
            f"File size ({size:,} bytes) exceeds maximum allowed ({max_size:,} bytes)",
            project_id=project_id,
        )
        self.size = size
        self.max_size = max_size


class UnsupportedFileTypeError(StorageError):
    """Raised when file type is not supported."""

    def __init__(
        self,
        content_type: str,
        project_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Unsupported file type: {content_type}. "
            f"Allowed types: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
            project_id=project_id,
        )
        self.content_type = content_type


class DocumentNotFoundError(StorageError):
    """Raised when document is not found."""

    pass


@dataclass
class StoredDocument:
    """Represents a stored document."""

    id: str
    filename: str
    content_type: str
    size_bytes: int
    storage_backend: str
    storage_path: str
    project_id: str
    uploaded_at: datetime
    checksum: str | None = None


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def store(
        self,
        file_stream: BinaryIO,
        filename: str,
        content_type: str,
        project_id: str,
        document_id: str,
    ) -> str:
        """Store a file and return the storage path/key.

        Args:
            file_stream: File content as binary stream
            filename: Original filename
            content_type: MIME type
            project_id: Associated project ID
            document_id: Unique document ID

        Returns:
            Storage path or key where file is stored
        """
        pass

    @abstractmethod
    async def retrieve(self, storage_path: str) -> bytes:
        """Retrieve file content by storage path.

        Args:
            storage_path: Path/key where file is stored

        Returns:
            File content as bytes
        """
        pass

    @abstractmethod
    async def delete(self, storage_path: str) -> bool:
        """Delete a file by storage path.

        Args:
            storage_path: Path/key where file is stored

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, storage_path: str) -> bool:
        """Check if a file exists.

        Args:
            storage_path: Path/key where file is stored

        Returns:
            True if file exists
        """
        pass

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Return the backend name (e.g., 'local', 's3')."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: str | None = None) -> None:
        """Initialize local storage backend.

        Args:
            base_path: Base directory for storing files.
                      Defaults to STORAGE_LOCAL_PATH env var or ./uploads
        """
        self._base_path = Path(
            base_path or os.environ.get("STORAGE_LOCAL_PATH", "./uploads")
        )
        self._base_path.mkdir(parents=True, exist_ok=True)

        logger.debug(
            "LocalStorageBackend initialized",
            extra={"base_path": str(self._base_path)},
        )

    @property
    def backend_name(self) -> str:
        return "local"

    def _get_file_path(self, project_id: str, document_id: str, filename: str) -> Path:
        """Get the full file path for a document."""
        # Organize by project_id for easier management
        project_dir = self._base_path / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        # Use document_id as prefix to ensure uniqueness
        safe_filename = f"{document_id}_{filename}"
        return project_dir / safe_filename

    async def store(
        self,
        file_stream: BinaryIO,
        filename: str,
        content_type: str,
        project_id: str,
        document_id: str,
    ) -> str:
        """Store file to local filesystem."""
        start_time = time.monotonic()

        logger.debug(
            "Storing file to local storage",
            extra={
                "filename": filename[:50],
                "content_type": content_type,
                "project_id": project_id,
                "document_id": document_id,
            },
        )

        try:
            file_path = self._get_file_path(project_id, document_id, filename)

            # Read and write file
            content = file_stream.read()
            file_path.write_bytes(content)

            storage_path = str(file_path.relative_to(self._base_path))

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "File stored to local storage",
                extra={
                    "storage_path": storage_path,
                    "size_bytes": len(content),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "document_id": document_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow local storage write",
                    extra={
                        "storage_path": storage_path,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return storage_path

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Failed to store file to local storage",
                extra={
                    "filename": filename[:50],
                    "project_id": project_id,
                    "document_id": document_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise StorageError(
                f"Failed to store file: {e}",
                project_id=project_id,
                document_id=document_id,
            ) from e

    async def retrieve(self, storage_path: str) -> bytes:
        """Retrieve file from local filesystem."""
        start_time = time.monotonic()

        logger.debug(
            "Retrieving file from local storage",
            extra={"storage_path": storage_path},
        )

        try:
            file_path = self._base_path / storage_path

            if not file_path.exists():
                raise DocumentNotFoundError(f"File not found: {storage_path}")

            content = file_path.read_bytes()

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "File retrieved from local storage",
                extra={
                    "storage_path": storage_path,
                    "size_bytes": len(content),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return content

        except DocumentNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "Failed to retrieve file from local storage",
                extra={
                    "storage_path": storage_path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise StorageError(f"Failed to retrieve file: {e}") from e

    async def delete(self, storage_path: str) -> bool:
        """Delete file from local filesystem."""
        start_time = time.monotonic()

        logger.debug(
            "Deleting file from local storage",
            extra={"storage_path": storage_path},
        )

        try:
            file_path = self._base_path / storage_path

            if not file_path.exists():
                logger.debug(
                    "File not found for deletion",
                    extra={"storage_path": storage_path},
                )
                return False

            file_path.unlink()

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "File deleted from local storage",
                extra={
                    "storage_path": storage_path,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to delete file from local storage",
                extra={
                    "storage_path": storage_path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise StorageError(f"Failed to delete file: {e}") from e

    async def exists(self, storage_path: str) -> bool:
        """Check if file exists in local filesystem."""
        file_path = self._base_path / storage_path
        return file_path.exists()


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""

    def __init__(
        self,
        bucket_name: str | None = None,
        region: str | None = None,
        prefix: str = "documents",
    ) -> None:
        """Initialize S3 storage backend.

        Args:
            bucket_name: S3 bucket name. Defaults to STORAGE_S3_BUCKET env var.
            region: AWS region. Defaults to AWS_REGION env var.
            prefix: Key prefix for all objects. Defaults to 'documents'.
        """
        self._bucket_name = bucket_name or os.environ.get("STORAGE_S3_BUCKET")
        self._region = region or os.environ.get("AWS_REGION", "us-east-1")
        self._prefix = prefix
        self._client: Any = None  # S3Client from boto3

        if not self._bucket_name:
            logger.warning(
                "S3 bucket name not configured",
                extra={"env_var": "STORAGE_S3_BUCKET"},
            )

        logger.debug(
            "S3StorageBackend initialized",
            extra={
                "bucket_name": self._bucket_name,
                "region": self._region,
                "prefix": self._prefix,
            },
        )

    @property
    def backend_name(self) -> str:
        return "s3"

    def _get_client(self) -> Any:
        """Get or create S3 client."""
        if self._client is None:
            try:
                import boto3
            except ImportError as e:
                logger.error(
                    "boto3 not installed",
                    extra={
                        "error": str(e),
                        "stack_trace": traceback.format_exc(),
                    },
                )
                raise StorageError("S3 storage requires boto3 library") from e

            self._client = boto3.client("s3", region_name=self._region)

        return self._client

    def _get_key(self, project_id: str, document_id: str, filename: str) -> str:
        """Get the S3 key for a document."""
        return f"{self._prefix}/{project_id}/{document_id}_{filename}"

    async def store(
        self,
        file_stream: BinaryIO,
        filename: str,
        content_type: str,
        project_id: str,
        document_id: str,
    ) -> str:
        """Store file to S3."""
        start_time = time.monotonic()

        if not self._bucket_name:
            raise StorageError(
                "S3 bucket not configured",
                project_id=project_id,
                document_id=document_id,
            )

        logger.debug(
            "Storing file to S3",
            extra={
                "filename": filename[:50],
                "content_type": content_type,
                "project_id": project_id,
                "document_id": document_id,
                "bucket": self._bucket_name,
            },
        )

        try:
            client = self._get_client()
            key = self._get_key(project_id, document_id, filename)

            # Read content
            content = file_stream.read()

            # Upload to S3
            client.put_object(
                Bucket=self._bucket_name,
                Key=key,
                Body=content,
                ContentType=content_type,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "File stored to S3",
                extra={
                    "bucket": self._bucket_name,
                    "key": key,
                    "size_bytes": len(content),
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "document_id": document_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow S3 upload",
                    extra={
                        "bucket": self._bucket_name,
                        "key": key,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return key

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Failed to store file to S3",
                extra={
                    "filename": filename[:50],
                    "bucket": self._bucket_name,
                    "project_id": project_id,
                    "document_id": document_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise StorageError(
                f"Failed to store file to S3: {e}",
                project_id=project_id,
                document_id=document_id,
            ) from e

    async def retrieve(self, storage_path: str) -> bytes:
        """Retrieve file from S3."""
        start_time = time.monotonic()

        if not self._bucket_name:
            raise StorageError("S3 bucket not configured")

        logger.debug(
            "Retrieving file from S3",
            extra={"bucket": self._bucket_name, "key": storage_path},
        )

        try:
            client = self._get_client()

            response = client.get_object(
                Bucket=self._bucket_name,
                Key=storage_path,
            )

            content: bytes = response["Body"].read()

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "File retrieved from S3",
                extra={
                    "bucket": self._bucket_name,
                    "key": storage_path,
                    "size_bytes": len(content),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return content

        except client.exceptions.NoSuchKey:
            raise DocumentNotFoundError(f"Document not found: {storage_path}")
        except Exception as e:
            logger.error(
                "Failed to retrieve file from S3",
                extra={
                    "bucket": self._bucket_name,
                    "key": storage_path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise StorageError(f"Failed to retrieve file from S3: {e}") from e

    async def delete(self, storage_path: str) -> bool:
        """Delete file from S3."""
        start_time = time.monotonic()

        if not self._bucket_name:
            raise StorageError("S3 bucket not configured")

        logger.debug(
            "Deleting file from S3",
            extra={"bucket": self._bucket_name, "key": storage_path},
        )

        try:
            client = self._get_client()

            # Check if exists first
            try:
                client.head_object(Bucket=self._bucket_name, Key=storage_path)
            except client.exceptions.ClientError as e:
                if e.response.get("Error", {}).get("Code") == "404":
                    logger.debug(
                        "File not found for deletion in S3",
                        extra={"bucket": self._bucket_name, "key": storage_path},
                    )
                    return False
                raise

            # Delete the object
            client.delete_object(Bucket=self._bucket_name, Key=storage_path)

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "File deleted from S3",
                extra={
                    "bucket": self._bucket_name,
                    "key": storage_path,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to delete file from S3",
                extra={
                    "bucket": self._bucket_name,
                    "key": storage_path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise StorageError(f"Failed to delete file from S3: {e}") from e

    async def exists(self, storage_path: str) -> bool:
        """Check if file exists in S3."""
        if not self._bucket_name:
            return False

        try:
            client = self._get_client()
            client.head_object(Bucket=self._bucket_name, Key=storage_path)
            return True
        except Exception:
            return False


class StorageService:
    """Main storage service that manages document uploads.

    Supports both S3 and local storage backends with automatic fallback.
    """

    def __init__(
        self,
        backend: StorageBackend | None = None,
        max_file_size: int = MAX_FILE_SIZE_BYTES,
    ) -> None:
        """Initialize storage service.

        Args:
            backend: Storage backend to use. Auto-detected if not provided.
            max_file_size: Maximum allowed file size in bytes.
        """
        self._backend = backend or self._auto_detect_backend()
        self._max_file_size = max_file_size

        logger.info(
            "StorageService initialized",
            extra={
                "backend": self._backend.backend_name,
                "max_file_size_bytes": self._max_file_size,
            },
        )

    def _auto_detect_backend(self) -> StorageBackend:
        """Auto-detect the best available storage backend."""
        # Check if S3 is configured
        s3_bucket = os.environ.get("STORAGE_S3_BUCKET")
        if s3_bucket:
            logger.info("Using S3 storage backend", extra={"bucket": s3_bucket})
            return S3StorageBackend(bucket_name=s3_bucket)

        # Fall back to local storage
        logger.info("Using local storage backend")
        return LocalStorageBackend()

    def _validate_file(
        self,
        filename: str,
        content_type: str,
        size: int,
        project_id: str,
    ) -> None:
        """Validate file before upload.

        Args:
            filename: Original filename
            content_type: MIME type
            size: File size in bytes
            project_id: Associated project ID

        Raises:
            FileTooLargeError: If file exceeds size limit
            UnsupportedFileTypeError: If file type not allowed
        """
        # Check file size
        if size > self._max_file_size:
            logger.warning(
                "File size validation failed",
                extra={
                    "filename": filename[:50],
                    "size_bytes": size,
                    "max_size_bytes": self._max_file_size,
                    "project_id": project_id,
                },
            )
            raise FileTooLargeError(size, self._max_file_size, project_id)

        # Check content type
        if content_type not in ALLOWED_CONTENT_TYPES:
            # Also check by extension as fallback
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED_EXTENSIONS:
                logger.warning(
                    "File type validation failed",
                    extra={
                        "filename": filename[:50],
                        "content_type": content_type,
                        "extension": ext,
                        "project_id": project_id,
                    },
                )
                raise UnsupportedFileTypeError(content_type, project_id)

    def _compute_checksum(self, content: bytes) -> str:
        """Compute MD5 checksum of file content."""
        return hashlib.md5(content).hexdigest()

    async def upload(
        self,
        file_stream: BinaryIO,
        filename: str,
        content_type: str,
        project_id: str,
    ) -> StoredDocument:
        """Upload a document.

        Args:
            file_stream: File content as binary stream
            filename: Original filename
            content_type: MIME type
            project_id: Associated project ID

        Returns:
            StoredDocument with upload details

        Raises:
            FileTooLargeError: If file exceeds size limit
            UnsupportedFileTypeError: If file type not allowed
            StorageError: On storage backend errors
        """
        start_time = time.monotonic()
        document_id = str(uuid4())

        logger.debug(
            "Starting document upload",
            extra={
                "filename": filename[:50],
                "content_type": content_type,
                "project_id": project_id,
                "document_id": document_id,
            },
        )

        try:
            # Read content to determine size and compute checksum
            content = file_stream.read()
            actual_size = len(content)

            # Validate file
            self._validate_file(filename, content_type, actual_size, project_id)

            # Compute checksum
            checksum = self._compute_checksum(content)

            # Create new stream from content
            import io

            new_stream = io.BytesIO(content)

            # Store the file
            storage_path = await self._backend.store(
                file_stream=new_stream,
                filename=filename,
                content_type=content_type,
                project_id=project_id,
                document_id=document_id,
            )

            uploaded_at = datetime.now(UTC)

            document = StoredDocument(
                id=document_id,
                filename=filename,
                content_type=content_type,
                size_bytes=actual_size,
                storage_backend=self._backend.backend_name,
                storage_path=storage_path,
                project_id=project_id,
                uploaded_at=uploaded_at,
                checksum=checksum,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.info(
                "Document uploaded successfully",
                extra={
                    "document_id": document_id,
                    "filename": filename[:50],
                    "size_bytes": actual_size,
                    "storage_backend": self._backend.backend_name,
                    "storage_path": storage_path,
                    "project_id": project_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return document

        except (FileTooLargeError, UnsupportedFileTypeError):
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Document upload failed",
                extra={
                    "filename": filename[:50],
                    "project_id": project_id,
                    "document_id": document_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise StorageError(
                f"Document upload failed: {e}",
                project_id=project_id,
                document_id=document_id,
            ) from e

    async def download(self, storage_path: str) -> bytes:
        """Download a document by storage path.

        Args:
            storage_path: Path/key where document is stored

        Returns:
            Document content as bytes

        Raises:
            DocumentNotFoundError: If document not found
            StorageError: On storage backend errors
        """
        return await self._backend.retrieve(storage_path)

    async def delete(self, storage_path: str) -> bool:
        """Delete a document by storage path.

        Args:
            storage_path: Path/key where document is stored

        Returns:
            True if deleted, False if not found

        Raises:
            StorageError: On storage backend errors
        """
        return await self._backend.delete(storage_path)

    async def exists(self, storage_path: str) -> bool:
        """Check if a document exists.

        Args:
            storage_path: Path/key where document is stored

        Returns:
            True if document exists
        """
        return await self._backend.exists(storage_path)


# Global singleton instance
_storage_service: StorageService | None = None


def get_storage_service() -> StorageService:
    """Get the global storage service instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
        logger.info("StorageService singleton created")
    return _storage_service
