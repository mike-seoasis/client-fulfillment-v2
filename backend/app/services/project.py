"""Project service with CRUD operations.

Provides business logic for Project entities, separating concerns from API routes.
Uses async SQLAlchemy 2.0 patterns.
"""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.s3 import S3Client, S3Error, S3NotFoundError
from app.models.brand_config import BrandConfig
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate


class ProjectService:
    """Service class for Project CRUD operations."""

    @staticmethod
    async def list_projects(db: AsyncSession) -> list[Project]:
        """List all projects ordered by updated_at descending.

        Args:
            db: AsyncSession for database operations.

        Returns:
            List of Project instances ordered by most recently updated.
        """
        stmt = select(Project).order_by(Project.updated_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_project(db: AsyncSession, project_id: str) -> Project:
        """Get a project by ID.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.

        Returns:
            Project instance.

        Raises:
            HTTPException: 404 if project not found.
        """
        stmt = select(Project).where(Project.id == project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()

        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with id '{project_id}' not found",
            )

        return project

    @staticmethod
    async def create_project(db: AsyncSession, data: ProjectCreate) -> Project:
        """Create a new project.

        Args:
            db: AsyncSession for database operations.
            data: ProjectCreate schema with project data.

        Returns:
            Newly created Project instance.
        """
        # Convert HttpUrl to string for database storage
        project = Project(
            name=data.name,
            site_url=str(data.site_url),
            client_id=data.client_id,
            additional_info=data.additional_info,
            status=data.status,
            phase_status=data.phase_status,
        )

        db.add(project)
        await db.flush()
        await db.refresh(project)

        return project

    @staticmethod
    async def update_project(
        db: AsyncSession, project_id: str, data: ProjectUpdate
    ) -> Project:
        """Update an existing project.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.
            data: ProjectUpdate schema with fields to update.

        Returns:
            Updated Project instance.

        Raises:
            HTTPException: 404 if project not found.
        """
        project = await ProjectService.get_project(db, project_id)

        # Update only provided fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            # Convert HttpUrl to string for site_url
            if field == "site_url" and value is not None:
                value = str(value)
            setattr(project, field, value)

        await db.flush()
        await db.refresh(project)

        return project

    @staticmethod
    async def delete_project(
        db: AsyncSession, project_id: str, s3_client: S3Client | None = None
    ) -> None:
        """Delete a project by ID, including S3 files.

        This method:
        1. Verifies the project exists
        2. Finds all ProjectFile records for the project
        3. Deletes each file from S3 (if s3_client provided)
        4. Deletes the project (DB cascade handles ProjectFile records)

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.
            s3_client: Optional S3Client for deleting files from storage.
                       If not provided, S3 files will NOT be deleted.

        Raises:
            HTTPException: 404 if project not found.
        """
        project = await ProjectService.get_project(db, project_id)

        # Delete files from S3 before deleting the project
        if s3_client is not None:
            # Get all project files
            files_stmt = select(ProjectFile).where(ProjectFile.project_id == project_id)
            files_result = await db.execute(files_stmt)
            project_files = list(files_result.scalars().all())

            # Delete each file from S3
            for project_file in project_files:
                try:
                    await s3_client.delete_file(project_file.s3_key)
                except S3NotFoundError:
                    # File already gone from S3 - continue
                    pass
                except S3Error:
                    # Log but don't fail the project deletion
                    # The DB records will be cascade deleted anyway
                    pass

        # Delete the project (DB cascade handles ProjectFile records)
        await db.delete(project)
        await db.flush()

    @staticmethod
    async def to_response(db: AsyncSession, project: Project) -> ProjectResponse:
        """Convert a Project model to ProjectResponse with computed fields.

        Populates:
        - brand_config_status: from project.brand_wizard_state.generation.status
        - has_brand_config: true if BrandConfig exists for this project
        - uploaded_files_count: count of ProjectFile records

        Args:
            db: AsyncSession for database operations.
            project: Project model instance.

        Returns:
            ProjectResponse with all computed fields populated.
        """
        # Get brand_config_status from brand_wizard_state
        brand_config_status = "pending"
        brand_wizard_state: dict[str, Any] = project.brand_wizard_state or {}
        generation_state = brand_wizard_state.get("generation", {})
        if generation_state and "status" in generation_state:
            brand_config_status = generation_state["status"]

        # Check if BrandConfig exists for this project
        brand_config_stmt = select(func.count()).where(
            BrandConfig.project_id == project.id
        )
        brand_config_result = await db.execute(brand_config_stmt)
        has_brand_config = brand_config_result.scalar_one() > 0

        # Count ProjectFile records for this project
        files_stmt = select(func.count()).where(ProjectFile.project_id == project.id)
        files_result = await db.execute(files_stmt)
        uploaded_files_count = files_result.scalar_one()

        return ProjectResponse(
            id=project.id,
            name=project.name,
            site_url=project.site_url,
            client_id=project.client_id,
            additional_info=project.additional_info,
            status=project.status,
            phase_status=project.phase_status,
            brand_config_status=brand_config_status,
            has_brand_config=has_brand_config,
            uploaded_files_count=uploaded_files_count,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    @staticmethod
    async def to_response_list(
        db: AsyncSession, projects: list[Project]
    ) -> list[ProjectResponse]:
        """Convert a list of Project models to ProjectResponses with computed fields.

        Args:
            db: AsyncSession for database operations.
            projects: List of Project model instances.

        Returns:
            List of ProjectResponse with all computed fields populated.
        """
        return [await ProjectService.to_response(db, project) for project in projects]
