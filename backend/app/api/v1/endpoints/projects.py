"""Projects API endpoints.

Provides CRUD operations for projects:
- GET /api/v1/projects - List all projects with pagination
- POST /api/v1/projects - Create a new project
- GET /api/v1/projects/{project_id} - Get a project by ID
- PUT /api/v1/projects/{project_id} - Update a project
- DELETE /api/v1/projects/{project_id} - Delete a project

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level
"""

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.schemas.project import (
    PhaseStatusUpdate,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project import (
    InvalidPhaseTransitionError,
    ProjectNotFoundError,
    ProjectService,
    ProjectValidationError,
)

logger = get_logger(__name__)

router = APIRouter()


def _get_request_id(request: Request) -> str:
    """Get request_id from request state."""
    return getattr(request.state, "request_id", "unknown")


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List all projects",
    description="Retrieve a paginated list of all projects.",
)
async def list_projects(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000, description="Number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    session: AsyncSession = Depends(get_session),
) -> ProjectListResponse:
    """List all projects with pagination."""
    request_id = _get_request_id(request)
    logger.debug(
        "List projects request",
        extra={"request_id": request_id, "limit": limit, "offset": offset},
    )

    service = ProjectService(session)
    projects, total = await service.list_projects(limit=limit, offset=offset)

    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
    description="Create a new project with the provided data.",
)
async def create_project(
    request: Request,
    data: ProjectCreate,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse | JSONResponse:
    """Create a new project."""
    request_id = _get_request_id(request)
    logger.debug(
        "Create project request",
        extra={
            "request_id": request_id,
            "name": data.name,
            "client_id": data.client_id,
        },
    )

    service = ProjectService(session)
    try:
        project = await service.create_project(data)
        return ProjectResponse.model_validate(project)
    except ProjectValidationError as e:
        logger.warning(
            "Project validation error",
            extra={
                "request_id": request_id,
                "field": e.field,
                "value": e.value,
                "message": e.message,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a project",
    description="Retrieve a project by its ID.",
    responses={
        404: {
            "description": "Project not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Project not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        }
    },
)
async def get_project(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse | JSONResponse:
    """Get a project by ID."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get project request",
        extra={"request_id": request_id, "project_id": project_id},
    )

    service = ProjectService(session)
    try:
        project = await service.get_project(project_id)
        return ProjectResponse.model_validate(project)
    except ProjectNotFoundError as e:
        logger.warning(
            "Project not found",
            extra={"request_id": request_id, "project_id": project_id},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )
    except ProjectValidationError as e:
        logger.warning(
            "Project validation error",
            extra={
                "request_id": request_id,
                "field": e.field,
                "value": e.value,
                "message": e.message,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
    description="Update an existing project with the provided data.",
    responses={
        404: {
            "description": "Project not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Project not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        }
    },
)
async def update_project(
    request: Request,
    project_id: str,
    data: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse | JSONResponse:
    """Update an existing project."""
    request_id = _get_request_id(request)
    logger.debug(
        "Update project request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "update_fields": [k for k, v in data.model_dump().items() if v is not None],
        },
    )

    service = ProjectService(session)
    try:
        project = await service.update_project(project_id, data)
        return ProjectResponse.model_validate(project)
    except ProjectNotFoundError as e:
        logger.warning(
            "Project not found",
            extra={"request_id": request_id, "project_id": project_id},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )
    except ProjectValidationError as e:
        logger.warning(
            "Project validation error",
            extra={
                "request_id": request_id,
                "field": e.field,
                "value": e.value,
                "message": e.message,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )
    except InvalidPhaseTransitionError as e:
        logger.warning(
            "Invalid phase transition",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "phase": e.phase,
                "from_status": e.from_status,
                "to_status": e.to_status,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "INVALID_TRANSITION",
                "request_id": request_id,
            },
        )


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete a project",
    description="Delete an existing project by its ID.",
    responses={
        404: {
            "description": "Project not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Project not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        }
    },
)
async def delete_project(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> None | JSONResponse:
    """Delete a project."""
    request_id = _get_request_id(request)
    logger.debug(
        "Delete project request",
        extra={"request_id": request_id, "project_id": project_id},
    )

    service = ProjectService(session)
    try:
        await service.delete_project(project_id)
        return None  # 204 No Content
    except ProjectNotFoundError as e:
        logger.warning(
            "Project not found",
            extra={"request_id": request_id, "project_id": project_id},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )
    except ProjectValidationError as e:
        logger.warning(
            "Project validation error",
            extra={
                "request_id": request_id,
                "field": e.field,
                "value": e.value,
                "message": e.message,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )


@router.patch(
    "/{project_id}/phases",
    response_model=ProjectResponse,
    summary="Update a project phase",
    description="Update the status of a specific phase within a project.",
    responses={
        404: {
            "description": "Project not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Project not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        }
    },
)
async def update_project_phase(
    request: Request,
    project_id: str,
    data: PhaseStatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse | JSONResponse:
    """Update a specific phase's status within a project."""
    request_id = _get_request_id(request)
    logger.debug(
        "Update project phase request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "phase": data.phase,
            "status": data.status,
        },
    )

    service = ProjectService(session)
    try:
        project = await service.update_phase_status(project_id, data)
        return ProjectResponse.model_validate(project)
    except ProjectNotFoundError as e:
        logger.warning(
            "Project not found",
            extra={"request_id": request_id, "project_id": project_id},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )
    except InvalidPhaseTransitionError as e:
        logger.warning(
            "Invalid phase transition",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "phase": e.phase,
                "from_status": e.from_status,
                "to_status": e.to_status,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "INVALID_TRANSITION",
                "request_id": request_id,
            },
        )
    except ProjectValidationError as e:
        logger.warning(
            "Project validation error",
            extra={
                "request_id": request_id,
                "field": e.field,
                "value": e.value,
                "message": e.message,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )
