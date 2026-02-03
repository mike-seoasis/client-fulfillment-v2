"""Files API router.

REST endpoints for managing project file uploads.
Supports multipart/form-data uploads with file type and size validation.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.integrations.s3 import S3Client, get_s3
from app.schemas.project_file import ProjectFileList, ProjectFileResponse
from app.services.file import FileService
from app.services.project import ProjectService

router = APIRouter(prefix="/projects/{project_id}/files", tags=["Files"])

# File validation constants
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


@router.post("", response_model=ProjectFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    project_id: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_session),
    s3: S3Client = Depends(get_s3),
) -> ProjectFileResponse:
    """Upload a file to a project.

    Args:
        project_id: UUID of the project.
        file: File to upload (multipart/form-data).

    Returns:
        The created file record.

    Raises:
        HTTPException: 404 if project not found.
        HTTPException: 413 if file size exceeds 10MB.
        HTTPException: 415 if file type is not PDF, DOCX, or TXT.
    """
    # Verify project exists
    await ProjectService.get_project(db, project_id)

    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {content_type}. Allowed types: PDF, DOCX, TXT",
        )

    # Read file content and validate size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB",
        )

    # Upload file via service
    file_service = FileService(s3)
    project_file = await file_service.upload_file(
        db=db,
        project_id=project_id,
        file=file_content,
        filename=file.filename or "unnamed",
        content_type=content_type,
    )

    return ProjectFileResponse.model_validate(project_file)


@router.get("", response_model=ProjectFileList)
async def list_files(
    project_id: str,
    db: AsyncSession = Depends(get_session),
    s3: S3Client = Depends(get_s3),
) -> ProjectFileList:
    """List all files for a project.

    Args:
        project_id: UUID of the project.

    Returns:
        List of file records.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists
    await ProjectService.get_project(db, project_id)

    # List files via service
    file_service = FileService(s3)
    files = await file_service.list_files(db, project_id)

    return ProjectFileList(
        items=[ProjectFileResponse.model_validate(f) for f in files],
        total=len(files),
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    project_id: str,
    file_id: str,
    db: AsyncSession = Depends(get_session),
    s3: S3Client = Depends(get_s3),
) -> None:
    """Delete a file from a project.

    Args:
        project_id: UUID of the project.
        file_id: UUID of the file to delete.

    Raises:
        HTTPException: 404 if project or file not found.
    """
    # Verify project exists
    await ProjectService.get_project(db, project_id)

    # Delete file via service
    file_service = FileService(s3)
    await file_service.delete_file(db, project_id, file_id)
