"""Project service with CRUD operations.

Provides business logic for Project entities, separating concerns from API routes.
Uses async SQLAlchemy 2.0 patterns.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


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
    async def delete_project(db: AsyncSession, project_id: str) -> None:
        """Delete a project by ID.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.

        Raises:
            HTTPException: 404 if project not found.
        """
        project = await ProjectService.get_project(db, project_id)
        await db.delete(project)
        await db.flush()
