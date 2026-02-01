"""Document upload API endpoints.

Provides endpoints for document upload, retrieval, and management:
- POST /api/v1/projects/{project_id}/documents/upload - Upload a document
- GET /api/v1/projects/{project_id}/documents/{document_id} - Download a document
- DELETE /api/v1/projects/{project_id}/documents/{document_id} - Delete a document

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
"""

import time

from fastapi import APIRouter, Depends, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.repositories.project import ProjectRepository
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentUploadResponse,
)
from app.schemas.document import (
    StorageBackend as SchemaStorageBackend,
)
from app.services.storage import (
    DocumentNotFoundError,
    FileTooLargeError,
    StorageError,
    UnsupportedFileTypeError,
    get_storage_service,
)

logger = get_logger(__name__)

router = APIRouter()


def _get_request_id(request: Request) -> str:
    """Get request_id from request state."""
    return getattr(request.state, "request_id", "unknown")


async def _verify_project_exists(
    project_id: str,
    session: AsyncSession,
    request_id: str,
) -> JSONResponse | None:
    """Verify project exists and return error response if not.

    Returns:
        None if project exists, JSONResponse with 404 if not found
    """
    repo = ProjectRepository(session)
    exists = await repo.exists(project_id)

    if not exists:
        logger.warning(
            "Project not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": f"Project not found: {project_id}",
                "code": "PROJECT_NOT_FOUND",
                "request_id": request_id,
            },
        )

    return None


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description="""
Upload a document to the project's storage.

**Supported formats:**
- PDF (.pdf)
- DOCX (.docx)
- TXT (.txt)
- Images: PNG, JPEG, GIF, WebP

**Limits:**
- Maximum file size: 50MB

**Storage:**
- Uses S3 if configured (STORAGE_S3_BUCKET env var)
- Falls back to local storage otherwise
""",
    responses={
        201: {"description": "Document uploaded successfully"},
        400: {
            "description": "Validation error (file too large or unsupported type)",
            "content": {
                "application/json": {
                    "example": {
                        "error": "File size exceeds maximum allowed",
                        "code": "FILE_TOO_LARGE",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
        404: {
            "description": "Project not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Project not found: <uuid>",
                        "code": "PROJECT_NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
        500: {
            "description": "Storage error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Failed to store document",
                        "code": "STORAGE_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def upload_document(
    request: Request,
    project_id: str,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
) -> DocumentUploadResponse | JSONResponse:
    """Upload a document to project storage."""
    start_time = time.monotonic()
    request_id = _get_request_id(request)

    logger.debug(
        "Document upload request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "filename": file.filename[:50] if file.filename else "unknown",
            "content_type": file.content_type,
        },
    )

    # Verify project exists
    error_response = await _verify_project_exists(project_id, session, request_id)
    if error_response:
        return error_response

    try:
        storage_service = get_storage_service()

        # Upload the file
        document = await storage_service.upload(
            file_stream=file.file,
            filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Document uploaded successfully",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "document_id": document.id,
                "filename": document.filename[:50],
                "size_bytes": document.size_bytes,
                "storage_backend": document.storage_backend,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return DocumentUploadResponse(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            storage_backend=SchemaStorageBackend(document.storage_backend),
            storage_path=document.storage_path,
            project_id=document.project_id,
            uploaded_at=document.uploaded_at,
            request_id=request_id,
        )

    except FileTooLargeError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Document upload failed - file too large",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "filename": file.filename[:50] if file.filename else "unknown",
                "size_bytes": e.size,
                "max_size_bytes": e.max_size,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "FILE_TOO_LARGE",
                "request_id": request_id,
            },
        )

    except UnsupportedFileTypeError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Document upload failed - unsupported file type",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "filename": file.filename[:50] if file.filename else "unknown",
                "content_type": e.content_type,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "UNSUPPORTED_FILE_TYPE",
                "request_id": request_id,
            },
        )

    except StorageError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Document upload failed - storage error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "filename": file.filename[:50] if file.filename else "unknown",
                "error": str(e),
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Failed to store document",
                "code": "STORAGE_ERROR",
                "request_id": request_id,
            },
        )


@router.get(
    "/{document_id}/download",
    summary="Download a document",
    description="Download a document by its ID. Returns the raw file content.",
    responses={
        200: {"description": "Document content"},
        404: {
            "description": "Document or project not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Document not found",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def download_document(
    request: Request,
    project_id: str,
    document_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response | JSONResponse:
    """Download a document by ID.

    Note: This endpoint requires the storage_path to be provided or looked up
    from a document metadata store. For simplicity, we construct it from
    the document_id pattern used during upload.
    """
    start_time = time.monotonic()
    request_id = _get_request_id(request)

    logger.debug(
        "Document download request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "document_id": document_id,
        },
    )

    # Verify project exists
    error_response = await _verify_project_exists(project_id, session, request_id)
    if error_response:
        return error_response

    try:
        storage_service = get_storage_service()

        # Construct the storage path pattern
        # This matches the pattern used in LocalStorageBackend and S3StorageBackend
        # Format: {project_id}/{document_id}_{filename}
        # Since we don't have a document metadata store, we need to search for files
        # matching the document_id prefix

        # For local storage, search in the project directory
        import os
        from pathlib import Path

        local_path = os.environ.get("STORAGE_LOCAL_PATH", "./uploads")
        project_dir = Path(local_path) / project_id

        if project_dir.exists():
            # Find file matching document_id
            matching_files = list(project_dir.glob(f"{document_id}_*"))
            if matching_files:
                file_path = matching_files[0]
                storage_path = str(file_path.relative_to(Path(local_path)))

                content = await storage_service.download(storage_path)

                # Guess content type from filename
                filename = file_path.name[len(document_id) + 1 :]  # Remove {id}_ prefix
                content_type = _guess_content_type(filename)

                duration_ms = (time.monotonic() - start_time) * 1000

                logger.info(
                    "Document downloaded successfully",
                    extra={
                        "request_id": request_id,
                        "project_id": project_id,
                        "document_id": document_id,
                        "size_bytes": len(content),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

                return Response(
                    content=content,
                    media_type=content_type,
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "X-Request-ID": request_id,
                    },
                )

        # Document not found
        logger.warning(
            "Document not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "document_id": document_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": f"Document not found: {document_id}",
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )

    except DocumentNotFoundError:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Document not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "document_id": document_id,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": f"Document not found: {document_id}",
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )

    except StorageError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Document download failed - storage error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "document_id": document_id,
                "error": str(e),
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Failed to retrieve document",
                "code": "STORAGE_ERROR",
                "request_id": request_id,
            },
        )


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete a document",
    description="Delete a document by its ID.",
    responses={
        200: {"description": "Document deleted successfully"},
        404: {
            "description": "Document or project not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Document not found",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def delete_document(
    request: Request,
    project_id: str,
    document_id: str,
    session: AsyncSession = Depends(get_session),
) -> DocumentDeleteResponse | JSONResponse:
    """Delete a document by ID."""
    start_time = time.monotonic()
    request_id = _get_request_id(request)

    logger.debug(
        "Document delete request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "document_id": document_id,
        },
    )

    # Verify project exists
    error_response = await _verify_project_exists(project_id, session, request_id)
    if error_response:
        return error_response

    try:
        storage_service = get_storage_service()

        # Find and delete the document (similar to download)
        import os
        from pathlib import Path

        local_path = os.environ.get("STORAGE_LOCAL_PATH", "./uploads")
        project_dir = Path(local_path) / project_id

        deleted = False
        if project_dir.exists():
            matching_files = list(project_dir.glob(f"{document_id}_*"))
            if matching_files:
                file_path = matching_files[0]
                storage_path = str(file_path.relative_to(Path(local_path)))
                deleted = await storage_service.delete(storage_path)

        duration_ms = (time.monotonic() - start_time) * 1000

        if deleted:
            logger.info(
                "Document deleted successfully",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "document_id": document_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return DocumentDeleteResponse(
                id=document_id,
                deleted=True,
                request_id=request_id,
            )
        else:
            logger.warning(
                "Document not found for deletion",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "document_id": document_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Document not found: {document_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

    except StorageError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Document delete failed - storage error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "document_id": document_id,
                "error": str(e),
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Failed to delete document",
                "code": "STORAGE_ERROR",
                "request_id": request_id,
            },
        )


def _guess_content_type(filename: str) -> str:
    """Guess content type from filename extension."""
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    content_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    return content_types.get(ext, "application/octet-stream")
