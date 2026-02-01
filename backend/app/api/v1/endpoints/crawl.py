"""Crawl phase API endpoints for projects.

Provides crawl-related operations for a project:
- POST /api/v1/projects/{project_id}/phases/crawl - Start a new crawl
- GET /api/v1/projects/{project_id}/phases/crawl - List crawl history
- GET /api/v1/projects/{project_id}/phases/crawl/{crawl_id} - Get crawl details
- GET /api/v1/projects/{project_id}/phases/crawl/{crawl_id}/progress - Get crawl progress
- POST /api/v1/projects/{project_id}/phases/crawl/{crawl_id}/stop - Stop a running crawl
- GET /api/v1/projects/{project_id}/phases/crawl/pages - List crawled pages

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

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.crawl_history import CrawlHistory
from app.models.crawled_page import CrawledPage
from app.schemas.crawl import (
    CrawledPageListResponse,
    CrawledPageResponse,
    CrawlHistoryListResponse,
    CrawlHistoryResponse,
    CrawlProgressResponse,
    CrawlStartRequest,
    CrawlStopResponse,
)
from app.services.crawl import (
    CrawlConfig,
    CrawlNotFoundError,
    CrawlService,
    CrawlValidationError,
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


async def _run_crawl_background(
    crawl_id: str,
    config: CrawlConfig,
    session: AsyncSession,
) -> None:
    """Background task to run the crawl.

    This is executed asynchronously after the start endpoint returns.
    """
    try:
        service = CrawlService(session)
        await service.run_crawl(crawl_id, config)
    except Exception as e:
        logger.error(
            "Background crawl failed",
            extra={
                "crawl_id": crawl_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )


@router.post(
    "",
    response_model=CrawlHistoryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a crawl",
    description="Start a new crawl for the project. Returns immediately with crawl job details.",
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
                        "error": "Validation failed for 'start_url': Invalid URL format",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def start_crawl(
    request: Request,
    project_id: str,
    data: CrawlStartRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> CrawlHistoryResponse | JSONResponse:
    """Start a new crawl for a project.

    The crawl runs in the background. Use the progress endpoint to track status.
    """
    request_id = _get_request_id(request)
    logger.debug(
        "Start crawl request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "start_url": data.start_url[:200],
            "max_pages": data.max_pages,
            "max_depth": data.max_depth,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CrawlService(session)
    try:
        # Create crawl config
        config = CrawlConfig(
            start_url=data.start_url,
            include_patterns=data.include_patterns,
            exclude_patterns=data.exclude_patterns,
            max_pages=data.max_pages,
            max_depth=data.max_depth,
        )

        # Start the crawl (creates history record)
        history = await service.start_crawl(
            project_id=project_id,
            config=config,
            trigger_type="manual",
        )

        # Commit the session to persist the history record
        await session.commit()

        # Queue background task to run the crawl
        # Note: Background tasks run after the response is sent
        # For production, consider using a proper task queue (Celery, etc.)
        background_tasks.add_task(
            _run_crawl_background,
            crawl_id=history.id,
            config=config,
            session=session,
        )

        logger.info(
            "Crawl started",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "crawl_id": history.id,
                "start_url": data.start_url[:200],
            },
        )

        return CrawlHistoryResponse.model_validate(history)

    except CrawlValidationError as e:
        logger.warning(
            "Crawl validation error",
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
    "",
    response_model=CrawlHistoryListResponse,
    summary="List crawl history",
    description="Get paginated list of crawl history for a project.",
    responses={
        404: {
            "description": "Project not found",
        },
    },
)
async def list_crawl_history(
    request: Request,
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100, description="Number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (pending, running, completed, failed, cancelled)",
    ),
    session: AsyncSession = Depends(get_session),
) -> CrawlHistoryListResponse | JSONResponse:
    """List crawl history for a project with pagination."""
    request_id = _get_request_id(request)
    logger.debug(
        "List crawl history request",
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
        # Build query
        query = select(CrawlHistory).where(CrawlHistory.project_id == project_id)
        count_query = select(func.count()).select_from(CrawlHistory).where(
            CrawlHistory.project_id == project_id
        )

        if status_filter:
            query = query.where(CrawlHistory.status == status_filter)
            count_query = count_query.where(CrawlHistory.status == status_filter)

        query = query.order_by(CrawlHistory.created_at.desc()).limit(limit).offset(offset)

        # Execute queries
        result = await session.execute(query)
        histories = list(result.scalars().all())

        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        logger.debug(
            "Crawl history list retrieved",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "count": len(histories),
                "total": total,
            },
        )

        return CrawlHistoryListResponse(
            items=[CrawlHistoryResponse.model_validate(h) for h in histories],
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(
            "Failed to list crawl history",
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
    "/{crawl_id}",
    response_model=CrawlHistoryResponse,
    summary="Get crawl details",
    description="Get details of a specific crawl job.",
    responses={
        404: {
            "description": "Project or crawl not found",
        },
    },
)
async def get_crawl_history(
    request: Request,
    project_id: str,
    crawl_id: str,
    session: AsyncSession = Depends(get_session),
) -> CrawlHistoryResponse | JSONResponse:
    """Get a specific crawl history record."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get crawl history request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "crawl_id": crawl_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CrawlService(session)
    try:
        history = await service.get_crawl_history(crawl_id)

        # Verify crawl belongs to this project
        if history.project_id != project_id:
            logger.warning(
                "Crawl does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "crawl_id": crawl_id,
                    "actual_project_id": history.project_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"CrawlHistory not found: {crawl_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        return CrawlHistoryResponse.model_validate(history)

    except CrawlNotFoundError as e:
        logger.warning(
            "Crawl history not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "crawl_id": crawl_id,
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
    except CrawlValidationError as e:
        logger.warning(
            "Crawl validation error",
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
    "/{crawl_id}/progress",
    response_model=CrawlProgressResponse,
    summary="Get crawl progress",
    description="Get real-time progress of a running crawl.",
    responses={
        404: {
            "description": "Project or crawl not found",
        },
    },
)
async def get_crawl_progress(
    request: Request,
    project_id: str,
    crawl_id: str,
    session: AsyncSession = Depends(get_session),
) -> CrawlProgressResponse | JSONResponse:
    """Get the current progress of a crawl job."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get crawl progress request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "crawl_id": crawl_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CrawlService(session)
    try:
        history = await service.get_crawl_history(crawl_id)

        # Verify crawl belongs to this project
        if history.project_id != project_id:
            logger.warning(
                "Crawl does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "crawl_id": crawl_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"CrawlHistory not found: {crawl_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        # Extract progress from stats
        stats = history.stats or {}

        return CrawlProgressResponse(
            crawl_id=history.id,
            project_id=history.project_id,
            status=history.status,
            pages_crawled=history.pages_crawled,
            pages_failed=history.pages_failed,
            pages_skipped=stats.get("pages_skipped", 0),
            urls_discovered=stats.get("urls_discovered", 0),
            current_depth=stats.get("current_depth", 0),
            started_at=history.started_at,
            completed_at=history.completed_at,
            error_count=len(history.error_log) if history.error_log else 0,
        )

    except CrawlNotFoundError as e:
        logger.warning(
            "Crawl history not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "crawl_id": crawl_id,
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
    except CrawlValidationError as e:
        logger.warning(
            "Crawl validation error",
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


@router.post(
    "/{crawl_id}/stop",
    response_model=CrawlStopResponse,
    summary="Stop a crawl",
    description="Stop a running crawl job.",
    responses={
        404: {
            "description": "Project or crawl not found",
        },
        400: {
            "description": "Crawl cannot be stopped (already completed/failed)",
        },
    },
)
async def stop_crawl(
    request: Request,
    project_id: str,
    crawl_id: str,
    session: AsyncSession = Depends(get_session),
) -> CrawlStopResponse | JSONResponse:
    """Stop a running crawl job."""
    request_id = _get_request_id(request)
    logger.debug(
        "Stop crawl request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "crawl_id": crawl_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CrawlService(session)
    try:
        history = await service.get_crawl_history(crawl_id)

        # Verify crawl belongs to this project
        if history.project_id != project_id:
            logger.warning(
                "Crawl does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "crawl_id": crawl_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"CrawlHistory not found: {crawl_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        # Check if crawl can be stopped
        if history.status not in ("pending", "running"):
            logger.warning(
                "Cannot stop crawl in current state",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "crawl_id": crawl_id,
                    "current_status": history.status,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": f"Cannot stop crawl in '{history.status}' state",
                    "code": "INVALID_STATE",
                    "request_id": request_id,
                },
            )

        # Update status to cancelled
        await service.update_crawl_status(crawl_id, "cancelled")
        await session.commit()

        logger.info(
            "Crawl stopped",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "crawl_id": crawl_id,
            },
        )

        return CrawlStopResponse(
            crawl_id=crawl_id,
            status="cancelled",
            message="Crawl has been cancelled",
        )

    except CrawlNotFoundError as e:
        logger.warning(
            "Crawl history not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "crawl_id": crawl_id,
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
    except CrawlValidationError as e:
        logger.warning(
            "Crawl validation error",
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
    "/pages",
    response_model=CrawledPageListResponse,
    summary="List crawled pages",
    description="Get paginated list of crawled pages for a project.",
    responses={
        404: {
            "description": "Project not found",
        },
    },
)
async def list_crawled_pages(
    request: Request,
    project_id: str,
    limit: int = Query(default=50, ge=1, le=500, description="Number of results"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    category: str | None = Query(default=None, description="Filter by category"),
    session: AsyncSession = Depends(get_session),
) -> CrawledPageListResponse | JSONResponse:
    """List crawled pages for a project with pagination."""
    request_id = _get_request_id(request)
    logger.debug(
        "List crawled pages request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "limit": limit,
            "offset": offset,
            "category": category,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        # Build query
        query = select(CrawledPage).where(CrawledPage.project_id == project_id)
        count_query = select(func.count()).select_from(CrawledPage).where(
            CrawledPage.project_id == project_id
        )

        if category:
            query = query.where(CrawledPage.category == category)
            count_query = count_query.where(CrawledPage.category == category)

        query = query.order_by(CrawledPage.created_at.desc()).limit(limit).offset(offset)

        # Execute queries
        result = await session.execute(query)
        pages = list(result.scalars().all())

        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        logger.debug(
            "Crawled pages list retrieved",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "count": len(pages),
                "total": total,
            },
        )

        return CrawledPageListResponse(
            items=[CrawledPageResponse.model_validate(p) for p in pages],
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(
            "Failed to list crawled pages",
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
    "/pages/{page_id}",
    response_model=CrawledPageResponse,
    summary="Get crawled page",
    description="Get details of a specific crawled page.",
    responses={
        404: {
            "description": "Project or page not found",
        },
    },
)
async def get_crawled_page(
    request: Request,
    project_id: str,
    page_id: str,
    session: AsyncSession = Depends(get_session),
) -> CrawledPageResponse | JSONResponse:
    """Get a specific crawled page."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get crawled page request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "page_id": page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        # Fetch the page
        query = select(CrawledPage).where(CrawledPage.id == page_id)
        result = await session.execute(query)
        page = result.scalar_one_or_none()

        if page is None:
            logger.warning(
                "Crawled page not found",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"CrawledPage not found: {page_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        # Verify page belongs to this project
        if page.project_id != project_id:
            logger.warning(
                "Page does not belong to project",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                    "actual_project_id": page.project_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"CrawledPage not found: {page_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        return CrawledPageResponse.model_validate(page)

    except Exception as e:
        logger.error(
            "Failed to get crawled page",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": page_id,
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
