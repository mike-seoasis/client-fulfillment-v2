"""Schedule configuration API endpoints for projects.

Provides CRUD operations for schedule configurations:
- POST /api/v1/projects/{project_id}/phases/schedule - Create a schedule
- GET /api/v1/projects/{project_id}/phases/schedule - List schedules
- GET /api/v1/projects/{project_id}/phases/schedule/{schedule_id} - Get schedule details
- PUT /api/v1/projects/{project_id}/phases/schedule/{schedule_id} - Update a schedule
- DELETE /api/v1/projects/{project_id}/phases/schedule/{schedule_id} - Delete a schedule

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level
"""

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.schemas.schedule import (
    ScheduleConfigCreate,
    ScheduleConfigListResponse,
    ScheduleConfigResponse,
    ScheduleConfigUpdate,
)
from app.services.project import ProjectNotFoundError, ProjectService
from app.services.schedule import (
    ScheduleNotFoundError,
    ScheduleService,
    ScheduleValidationError,
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
    """Verify that the project exists.

    Returns JSONResponse with 404 if not found, None if found.
    """
    service = ProjectService(session)
    try:
        await service.get_project(project_id)
        return None
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


@router.post(
    "",
    response_model=ScheduleConfigResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a schedule configuration",
    description="Create a new schedule configuration for the project.",
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
        },
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation failed for 'field': message",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def create_schedule(
    request: Request,
    project_id: str,
    data: ScheduleConfigCreate,
    session: AsyncSession = Depends(get_session),
) -> ScheduleConfigResponse | JSONResponse:
    """Create a new schedule configuration for the project."""
    request_id = _get_request_id(request)
    logger.info(
        "Create schedule request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "schedule_type": data.schedule_type,
        },
    )
    logger.debug(
        "Create schedule request body",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "start_url": data.start_url[:50] + "..." if len(data.start_url) > 50 else data.start_url,
            "max_pages": data.max_pages,
            "max_depth": data.max_depth,
            "is_active": data.is_active,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = ScheduleService(session)
    try:
        schedule = await service.create_schedule(project_id, data)
        logger.info(
            "Schedule created successfully",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "schedule_id": schedule.id,
            },
        )
        return ScheduleConfigResponse.model_validate(schedule)
    except ScheduleValidationError as e:
        logger.warning(
            "Schedule validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
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
    "",
    response_model=ScheduleConfigListResponse,
    summary="List schedule configurations",
    description="Retrieve a paginated list of schedule configurations for the project.",
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
        },
    },
)
async def list_schedules(
    request: Request,
    project_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    session: AsyncSession = Depends(get_session),
) -> ScheduleConfigListResponse | JSONResponse:
    """List schedule configurations for the project with pagination."""
    request_id = _get_request_id(request)
    logger.info(
        "List schedules request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = ScheduleService(session)
    try:
        schedules, total = await service.list_schedules(
            project_id=project_id,
            limit=limit,
            offset=offset,
        )
        logger.info(
            "Schedules listed successfully",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "count": len(schedules),
                "total": total,
            },
        )
        return ScheduleConfigListResponse(
            items=[ScheduleConfigResponse.model_validate(s) for s in schedules],
            total=total,
            limit=limit,
            offset=offset,
        )
    except ScheduleValidationError as e:
        logger.warning(
            "Schedule validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
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
    "/{schedule_id}",
    response_model=ScheduleConfigResponse,
    summary="Get a schedule configuration",
    description="Retrieve a schedule configuration by its ID.",
    responses={
        404: {
            "description": "Project or schedule not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Schedule not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def get_schedule(
    request: Request,
    project_id: str,
    schedule_id: str,
    session: AsyncSession = Depends(get_session),
) -> ScheduleConfigResponse | JSONResponse:
    """Get a schedule configuration by ID."""
    request_id = _get_request_id(request)
    logger.info(
        "Get schedule request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "schedule_id": schedule_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = ScheduleService(session)
    try:
        schedule = await service.get_schedule(schedule_id)

        # Verify schedule belongs to this project
        if schedule.project_id != project_id:
            logger.warning(
                "Schedule does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "schedule_id": schedule_id,
                    "schedule_project_id": schedule.project_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Schedule not found: {schedule_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        logger.info(
            "Schedule retrieved successfully",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "schedule_id": schedule_id,
            },
        )
        return ScheduleConfigResponse.model_validate(schedule)
    except ScheduleNotFoundError as e:
        logger.warning(
            "Schedule not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "schedule_id": schedule_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )
    except ScheduleValidationError as e:
        logger.warning(
            "Schedule validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
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
    "/{schedule_id}",
    response_model=ScheduleConfigResponse,
    summary="Update a schedule configuration",
    description="Update an existing schedule configuration.",
    responses={
        404: {
            "description": "Project or schedule not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Schedule not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation failed for 'field': message",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def update_schedule(
    request: Request,
    project_id: str,
    schedule_id: str,
    data: ScheduleConfigUpdate,
    session: AsyncSession = Depends(get_session),
) -> ScheduleConfigResponse | JSONResponse:
    """Update an existing schedule configuration."""
    request_id = _get_request_id(request)
    logger.info(
        "Update schedule request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "schedule_id": schedule_id,
            "update_fields": [k for k, v in data.model_dump().items() if v is not None],
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = ScheduleService(session)
    try:
        # Verify schedule exists and belongs to project before updating
        existing = await service.get_schedule_or_none(schedule_id)
        if existing is None:
            logger.warning(
                "Schedule not found",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "schedule_id": schedule_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Schedule not found: {schedule_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        if existing.project_id != project_id:
            logger.warning(
                "Schedule does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "schedule_id": schedule_id,
                    "schedule_project_id": existing.project_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Schedule not found: {schedule_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        schedule = await service.update_schedule(schedule_id, data)
        logger.info(
            "Schedule updated successfully",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "schedule_id": schedule_id,
            },
        )
        return ScheduleConfigResponse.model_validate(schedule)
    except ScheduleNotFoundError as e:
        logger.warning(
            "Schedule not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "schedule_id": schedule_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )
    except ScheduleValidationError as e:
        logger.warning(
            "Schedule validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
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


@router.delete(
    "/{schedule_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a schedule configuration",
    description="Delete an existing schedule configuration by its ID.",
    responses={
        204: {"description": "Schedule deleted successfully"},
        404: {
            "description": "Project or schedule not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Schedule not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def delete_schedule(
    request: Request,
    project_id: str,
    schedule_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response | JSONResponse:
    """Delete a schedule configuration."""
    request_id = _get_request_id(request)
    logger.info(
        "Delete schedule request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "schedule_id": schedule_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = ScheduleService(session)
    try:
        # Verify schedule exists and belongs to project before deleting
        existing = await service.get_schedule_or_none(schedule_id)
        if existing is None:
            logger.warning(
                "Schedule not found",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "schedule_id": schedule_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Schedule not found: {schedule_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        if existing.project_id != project_id:
            logger.warning(
                "Schedule does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "schedule_id": schedule_id,
                    "schedule_project_id": existing.project_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Schedule not found: {schedule_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        await service.delete_schedule(schedule_id)
        logger.info(
            "Schedule deleted successfully",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "schedule_id": schedule_id,
            },
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ScheduleNotFoundError as e:
        logger.warning(
            "Schedule not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "schedule_id": schedule_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )
    except ScheduleValidationError as e:
        logger.warning(
            "Schedule validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
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
