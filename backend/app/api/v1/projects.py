"""Projects API router.

REST endpoints for managing projects with CRUD operations.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.integrations.s3 import S3Client, get_s3
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: AsyncSession = Depends(get_session),
) -> ProjectListResponse:
    """List all projects.

    Returns projects ordered by most recently updated.
    """
    projects = await ProjectService.list_projects(db)
    items = await ProjectService.to_response_list(db, projects)
    return ProjectListResponse(
        items=items,
        total=len(projects),
        limit=max(len(projects), 1),  # Minimum of 1 to satisfy schema constraint
        offset=0,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Create a new project.

    Args:
        data: Project creation data with name and site_url (required).

    Returns:
        The newly created project.
    """
    project = await ProjectService.create_project(db, data)
    return await ProjectService.to_response(db, project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Get a project by ID.

    Args:
        project_id: UUID of the project.

    Returns:
        The project if found.

    Raises:
        HTTPException: 404 if project not found.
    """
    project = await ProjectService.get_project(db, project_id)
    return await ProjectService.to_response(db, project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Update a project.

    Args:
        project_id: UUID of the project.
        data: Fields to update (all optional).

    Returns:
        The updated project.

    Raises:
        HTTPException: 404 if project not found.
    """
    project = await ProjectService.update_project(db, project_id, data)
    return await ProjectService.to_response(db, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_session),
    s3: S3Client = Depends(get_s3),
) -> None:
    """Delete a project and all associated files from storage.

    This endpoint:
    1. Deletes all project files from S3 storage
    2. Deletes the project record (cascades to delete ProjectFile records)

    Args:
        project_id: UUID of the project.

    Raises:
        HTTPException: 404 if project not found.
    """
    await ProjectService.delete_project(db, project_id, s3_client=s3)
