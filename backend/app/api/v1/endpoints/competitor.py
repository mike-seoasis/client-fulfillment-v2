"""Competitor phase API endpoints for projects.

Provides competitor-related operations for a project:
- POST /api/v1/projects/{project_id}/phases/competitor - Add a competitor
- GET /api/v1/projects/{project_id}/phases/competitor - List competitors
- GET /api/v1/projects/{project_id}/phases/competitor/{competitor_id} - Get competitor details
- POST /api/v1/projects/{project_id}/phases/competitor/{competitor_id}/scrape - Start scraping
- GET /api/v1/projects/{project_id}/phases/competitor/{competitor_id}/progress - Get scrape progress
- DELETE /api/v1/projects/{project_id}/phases/competitor/{competitor_id} - Delete competitor

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level

Railway Deployment Requirements:
- CORS must allow frontend domain (configure via FRONTEND_URL env var)
- Return proper error responses (Railway shows these in logs)
- Include request_id in all responses for debugging
- Health check endpoint at /health or /api/v1/health
"""

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.schemas.competitor import (
    CompetitorCreateRequest,
    CompetitorDetailResponse,
    CompetitorListResponse,
    CompetitorResponse,
    CompetitorScrapeProgressResponse,
    CompetitorScrapeRequest,
)
from app.services.competitor import (
    CompetitorDuplicateError,
    CompetitorNotFoundError,
    CompetitorService,
    CompetitorValidationError,
    ScrapeConfig,
)
from app.services.project import ProjectNotFoundError, ProjectService

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


async def _run_scrape_background(
    competitor_id: str,
    config: ScrapeConfig,
    session: AsyncSession,
) -> None:
    """Background task to run the scrape.

    This is executed asynchronously after the start endpoint returns.
    """
    try:
        service = CompetitorService(session)
        await service.start_scrape(competitor_id, config)
    except Exception as e:
        logger.error(
            "Background scrape failed",
            extra={
                "competitor_id": competitor_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )


@router.post(
    "",
    response_model=CompetitorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a competitor",
    description="Add a new competitor URL to track for a project.",
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
            "description": "Validation error or duplicate URL",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation failed for 'url': Invalid URL format",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
        409: {
            "description": "Competitor URL already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Competitor URL already exists for project",
                        "code": "DUPLICATE",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def add_competitor(
    request: Request,
    project_id: str,
    data: CompetitorCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> CompetitorResponse | JSONResponse:
    """Add a new competitor URL to a project."""
    request_id = _get_request_id(request)
    logger.debug(
        "Add competitor request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "url": data.url[:200] if data.url else "",
            "name": data.name,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CompetitorService(session)
    try:
        competitor = await service.add_competitor(
            project_id=project_id,
            url=data.url,
            name=data.name,
        )

        logger.info(
            "Competitor added",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "competitor_id": competitor.id,
                "url": competitor.url[:200],
            },
        )

        return CompetitorResponse.model_validate(competitor)

    except CompetitorValidationError as e:
        logger.warning(
            "Competitor validation error",
            extra={
                "request_id": request_id,
                "field": e.field,
                "value": str(e.value)[:100],
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

    except CompetitorDuplicateError as e:
        logger.warning(
            "Duplicate competitor URL",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "url": e.url[:200],
            },
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": str(e),
                "code": "DUPLICATE",
                "request_id": request_id,
            },
        )


@router.get(
    "",
    response_model=CompetitorListResponse,
    summary="List competitors",
    description="Get paginated list of competitors for a project.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def list_competitors(
    request: Request,
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100, description="Number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (pending, scraping, completed, failed)",
    ),
    session: AsyncSession = Depends(get_session),
) -> CompetitorListResponse | JSONResponse:
    """List competitors for a project with pagination."""
    request_id = _get_request_id(request)
    logger.debug(
        "List competitors request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
            "status_filter": status_filter,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = CompetitorService(session)
        competitors, total = await service.list_competitors(
            project_id=project_id,
            limit=limit,
            offset=offset,
            status=status_filter,
        )

        logger.debug(
            "Competitors list retrieved",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "count": len(competitors),
                "total": total,
            },
        )

        return CompetitorListResponse(
            items=[CompetitorResponse.model_validate(c) for c in competitors],
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(
            "Failed to list competitors",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
        )


@router.get(
    "/{competitor_id}",
    response_model=CompetitorDetailResponse,
    summary="Get competitor details",
    description="Get details of a specific competitor including scraped content.",
    responses={
        404: {"description": "Project or competitor not found"},
    },
)
async def get_competitor(
    request: Request,
    project_id: str,
    competitor_id: str,
    session: AsyncSession = Depends(get_session),
) -> CompetitorDetailResponse | JSONResponse:
    """Get a specific competitor with full content."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get competitor request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "competitor_id": competitor_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CompetitorService(session)
    try:
        competitor = await service.get_competitor(competitor_id)

        # Verify competitor belongs to this project
        if competitor.project_id != project_id:
            logger.warning(
                "Competitor does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "competitor_id": competitor_id,
                    "actual_project_id": competitor.project_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Competitor not found: {competitor_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        return CompetitorDetailResponse.from_orm_with_content(competitor)

    except CompetitorNotFoundError as e:
        logger.warning(
            "Competitor not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "competitor_id": competitor_id,
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


@router.post(
    "/{competitor_id}/scrape",
    response_model=CompetitorResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start scraping",
    description="Start scraping a competitor website. Returns immediately with updated status.",
    responses={
        404: {"description": "Project or competitor not found"},
        400: {"description": "Competitor is already being scraped"},
    },
)
async def start_scrape(
    request: Request,
    project_id: str,
    competitor_id: str,
    data: CompetitorScrapeRequest | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: AsyncSession = Depends(get_session),
) -> CompetitorResponse | JSONResponse:
    """Start scraping a competitor website.

    The scrape runs in the background. Use the progress endpoint to track status.
    """
    request_id = _get_request_id(request)
    data = data or CompetitorScrapeRequest()

    logger.debug(
        "Start scrape request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "competitor_id": competitor_id,
            "max_pages": data.max_pages,
            "bypass_cache": data.bypass_cache,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CompetitorService(session)
    try:
        competitor = await service.get_competitor(competitor_id)

        # Verify competitor belongs to this project
        if competitor.project_id != project_id:
            logger.warning(
                "Competitor does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "competitor_id": competitor_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Competitor not found: {competitor_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        # Check if already scraping
        if competitor.status == "scraping":
            logger.warning(
                "Competitor already being scraped",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "competitor_id": competitor_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Competitor is already being scraped",
                    "code": "ALREADY_SCRAPING",
                    "request_id": request_id,
                },
            )

        # Create scrape config
        config = ScrapeConfig(
            max_pages=data.max_pages,
            bypass_cache=data.bypass_cache,
        )

        # Queue background task to run the scrape
        background_tasks.add_task(
            _run_scrape_background,
            competitor_id=competitor_id,
            config=config,
            session=session,
        )

        # Update status to scraping synchronously
        from app.repositories.competitor import CompetitorRepository

        repo = CompetitorRepository(session)
        updated = await repo.update_status(competitor_id, "scraping")
        await session.commit()

        logger.info(
            "Scrape started",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "competitor_id": competitor_id,
                "url": competitor.url[:200],
            },
        )

        return CompetitorResponse.model_validate(updated)

    except CompetitorNotFoundError as e:
        logger.warning(
            "Competitor not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "competitor_id": competitor_id,
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

    except CompetitorValidationError as e:
        logger.warning(
            "Competitor validation error",
            extra={
                "request_id": request_id,
                "field": e.field,
                "value": str(e.value)[:100],
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
    "/{competitor_id}/progress",
    response_model=CompetitorScrapeProgressResponse,
    summary="Get scrape progress",
    description="Get the current progress of a competitor scrape.",
    responses={
        404: {"description": "Project or competitor not found"},
    },
)
async def get_scrape_progress(
    request: Request,
    project_id: str,
    competitor_id: str,
    session: AsyncSession = Depends(get_session),
) -> CompetitorScrapeProgressResponse | JSONResponse:
    """Get the current progress of a competitor scrape."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get scrape progress request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "competitor_id": competitor_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CompetitorService(session)
    try:
        competitor = await service.get_competitor(competitor_id)

        # Verify competitor belongs to this project
        if competitor.project_id != project_id:
            logger.warning(
                "Competitor does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "competitor_id": competitor_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Competitor not found: {competitor_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        return CompetitorScrapeProgressResponse(
            competitor_id=competitor.id,
            project_id=competitor.project_id,
            status=competitor.status,
            pages_scraped=competitor.pages_scraped,
            scrape_started_at=competitor.scrape_started_at,
            scrape_completed_at=competitor.scrape_completed_at,
            error_message=competitor.error_message,
        )

    except CompetitorNotFoundError as e:
        logger.warning(
            "Competitor not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "competitor_id": competitor_id,
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


@router.delete(
    "/{competitor_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete competitor",
    description="Delete a competitor and its scraped content.",
    responses={
        204: {"description": "Competitor deleted successfully"},
        404: {"description": "Project or competitor not found"},
    },
)
async def delete_competitor(
    request: Request,
    project_id: str,
    competitor_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response | JSONResponse:
    """Delete a competitor and its scraped content."""
    request_id = _get_request_id(request)
    logger.debug(
        "Delete competitor request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "competitor_id": competitor_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CompetitorService(session)
    try:
        # First check the competitor exists and belongs to project
        competitor = await service.get_competitor(competitor_id)
        if competitor.project_id != project_id:
            logger.warning(
                "Competitor does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "competitor_id": competitor_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Competitor not found: {competitor_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        # Delete the competitor
        deleted = await service.delete_competitor(competitor_id)

        if not deleted:
            logger.warning(
                "Competitor not found for deletion",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "competitor_id": competitor_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Competitor not found: {competitor_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        logger.info(
            "Competitor deleted",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "competitor_id": competitor_id,
            },
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except CompetitorNotFoundError as e:
        logger.warning(
            "Competitor not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "competitor_id": competitor_id,
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
