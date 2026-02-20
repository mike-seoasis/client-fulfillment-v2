"""File service for managing project file uploads.

Provides business logic for ProjectFile entities, coordinating:
- S3 storage operations
- Text extraction from documents
- Database record management
"""

import logging
from typing import BinaryIO
from uuid import uuid4

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.s3 import S3Client, S3Error, S3NotFoundError
from app.models.project_file import ProjectFile
from app.utils.text_extraction import (
    TextExtractionError,
    UnsupportedFileTypeError,
    extract_text,
)


class FileService:
    """Service class for ProjectFile operations.

    Coordinates S3Client for storage and text extraction utilities
    to manage the complete lifecycle of project files.
    """

    def __init__(self, s3_client: S3Client) -> None:
        """Initialize FileService with S3 client.

        Args:
            s3_client: Configured S3Client instance for storage operations.
        """
        self._s3 = s3_client

    @staticmethod
    def _generate_s3_key(project_id: str, file_id: str, filename: str) -> str:
        """Generate S3 key for a project file.

        Key format: projects/{project_id}/files/{file_id}/{filename}

        Args:
            project_id: UUID of the project.
            file_id: UUID of the file.
            filename: Original filename.

        Returns:
            S3 key string.
        """
        return f"projects/{project_id}/files/{file_id}/{filename}"

    async def upload_file(
        self,
        db: AsyncSession,
        project_id: str,
        file: BinaryIO | bytes,
        filename: str,
        content_type: str,
    ) -> ProjectFile:
        """Upload a file for a project.

        This method:
        1. Generates a unique file ID and S3 key
        2. Uploads the file to S3
        3. Attempts text extraction (non-blocking on failure)
        4. Creates the database record

        Args:
            db: AsyncSession for database operations.
            project_id: UUID of the project this file belongs to.
            file: File content as BinaryIO or bytes.
            filename: Original filename.
            content_type: MIME type of the file.

        Returns:
            Created ProjectFile instance.

        Raises:
            HTTPException: 500 if S3 upload fails.
        """
        # Generate IDs
        file_id = str(uuid4())
        s3_key = self._generate_s3_key(project_id, file_id, filename)

        # Read file content if BinaryIO
        if isinstance(file, bytes):
            file_bytes = file
        else:
            file_bytes = file.read()
            # Reset file position in case caller needs it
            file.seek(0)

        file_size = len(file_bytes)

        # Upload to S3
        try:
            await self._s3.upload_file(s3_key, file_bytes, content_type)
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to storage: {e}",
            )

        # Extract text (best effort - don't fail upload if extraction fails)
        extracted_text: str | None = None
        try:
            extracted_text = extract_text(file_bytes, content_type)
            if extracted_text:
                logger.info(
                    "Text extracted from uploaded file",
                    extra={
                        "filename": filename,
                        "content_type": content_type,
                        "extracted_length": len(extracted_text),
                        "preview": extracted_text[:200],
                    },
                )
            else:
                logger.warning(
                    "Text extraction returned empty result",
                    extra={"filename": filename, "content_type": content_type},
                )
        except UnsupportedFileTypeError:
            logger.info(
                "File type does not support text extraction",
                extra={"filename": filename, "content_type": content_type},
            )
        except TextExtractionError as e:
            logger.warning(
                "Text extraction failed for uploaded file",
                extra={
                    "filename": filename,
                    "content_type": content_type,
                    "error": str(e),
                },
            )

        # Create database record
        project_file = ProjectFile(
            id=file_id,
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            s3_key=s3_key,
            extracted_text=extracted_text,
            file_size=file_size,
        )

        db.add(project_file)
        await db.flush()
        await db.refresh(project_file)

        return project_file

    async def list_files(
        self,
        db: AsyncSession,
        project_id: str,
    ) -> list[ProjectFile]:
        """List all files for a project.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID of the project.

        Returns:
            List of ProjectFile instances ordered by created_at descending.
        """
        stmt = (
            select(ProjectFile)
            .where(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_file(
        self,
        db: AsyncSession,
        project_id: str,
        file_id: str,
    ) -> bool:
        """Delete a file from a project.

        This method:
        1. Finds the file record
        2. Deletes from S3
        3. Deletes the database record

        Args:
            db: AsyncSession for database operations.
            project_id: UUID of the project.
            file_id: UUID of the file to delete.

        Returns:
            True if deletion was successful.

        Raises:
            HTTPException: 404 if file not found.
            HTTPException: 500 if S3 deletion fails.
        """
        # Find the file
        stmt = select(ProjectFile).where(
            ProjectFile.id == file_id,
            ProjectFile.project_id == project_id,
        )
        result = await db.execute(stmt)
        project_file = result.scalar_one_or_none()

        if project_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File with id '{file_id}' not found in project '{project_id}'",
            )

        # Delete from S3
        try:
            await self._s3.delete_file(project_file.s3_key)
        except S3NotFoundError:
            # File already gone from S3 - continue with DB deletion
            pass
        except S3Error as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete file from storage: {e}",
            )

        # Delete database record
        await db.delete(project_file)
        await db.flush()

        return True
