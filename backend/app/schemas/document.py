"""Document upload schemas.

Pydantic models for document upload requests and responses.
Supports uploading documents to S3 or local storage.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class StorageBackend(str, Enum):
    """Storage backend types."""

    LOCAL = "local"
    S3 = "s3"


class DocumentUploadResponse(BaseModel):
    """Response after successfully uploading a document."""

    id: str = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type of the document")
    size_bytes: int = Field(..., description="File size in bytes")
    storage_backend: StorageBackend = Field(
        ..., description="Storage backend used (local or s3)"
    )
    storage_path: str = Field(..., description="Path/key where document is stored")
    project_id: str = Field(..., description="Associated project ID")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    request_id: str = Field(..., description="Request ID for tracing")


class DocumentMetadataResponse(BaseModel):
    """Document metadata without content."""

    id: str = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type of the document")
    size_bytes: int = Field(..., description="File size in bytes")
    storage_backend: StorageBackend = Field(
        ..., description="Storage backend used (local or s3)"
    )
    project_id: str = Field(..., description="Associated project ID")
    uploaded_at: datetime = Field(..., description="Upload timestamp")


class DocumentListResponse(BaseModel):
    """Response for listing documents."""

    items: list[DocumentMetadataResponse] = Field(
        default_factory=list, description="List of documents"
    )
    total: int = Field(..., description="Total number of documents")


class DocumentDeleteResponse(BaseModel):
    """Response after deleting a document."""

    id: str = Field(..., description="Deleted document ID")
    deleted: bool = Field(..., description="Whether deletion was successful")
    request_id: str = Field(..., description="Request ID for tracing")
