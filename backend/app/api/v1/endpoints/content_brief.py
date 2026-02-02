"""Content Brief phase API endpoints for projects.

Provides content brief operations for a project:
- POST /api/v1/projects/{project_id}/phases/content_brief/fetch - Fetch content brief for a page
- GET /api/v1/projects/{project_id}/pages/{page_id}/brief - Get existing content brief

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

import time

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.schemas.content_brief import (
    ContentBriefCreateResponse,
    ContentBriefRequest,
    ContentBriefResponse,
)
from app.services.pop_content_brief import (
    POPContentBriefService,
    POPContentBriefServiceError,
    POPContentBriefValidationError,
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


async def _verify_page_exists(
    page_id: str,
    project_id: str,
    session: AsyncSession,
    request_id: str,
) -> tuple[CrawledPage | None, JSONResponse | None]:
    """Verify that the page exists and belongs to the project.

    Returns (page, None) if found, (None, JSONResponse) if not found.
    """
    stmt = select(CrawledPage).where(
        CrawledPage.id == page_id,
        CrawledPage.project_id == project_id,
    )
    result = await session.execute(stmt)
    page = result.scalar_one_or_none()

    if page is None:
        logger.warning(
            "Page not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": page_id,
            },
        )
        return None, JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": f"Page not found: {page_id}",
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )

    return page, None


def _convert_brief_to_response(brief: ContentBrief) -> ContentBriefResponse:
    """Convert ContentBrief model to API response schema."""
    return ContentBriefResponse(
        id=brief.id,
        page_id=brief.page_id,
        keyword=brief.keyword,
        pop_task_id=brief.pop_task_id,
        word_count_target=brief.word_count_target,
        word_count_min=brief.word_count_min,
        word_count_max=brief.word_count_max,
        heading_targets=brief.heading_targets,
        keyword_targets=brief.keyword_targets,
        lsi_terms=brief.lsi_terms,
        entities=brief.entities,
        related_questions=brief.related_questions,
        related_searches=brief.related_searches,
        competitors=brief.competitors,
        page_score_target=brief.page_score_target,
        created_at=brief.created_at,
        updated_at=brief.updated_at,
    )


@router.post(
    "/fetch",
    response_model=ContentBriefCreateResponse,
    summary="Fetch content brief for a page",
    description="Fetch content brief from POP API for a keyword/URL and save to database.",
    responses={
        404: {
            "description": "Project or page not found",
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
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation failed: keyword cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal server error",
                        "code": "INTERNAL_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def fetch_content_brief(
    request: Request,
    project_id: str,
    data: ContentBriefRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentBriefCreateResponse | JSONResponse:
    """Fetch content brief from POP API for a keyword/URL.

    Creates a POP report task, polls for completion, parses the results,
    and saves the content brief to the database. If a brief already exists
    for the same page, it will be replaced.

    The request requires a page_id query parameter to associate the brief
    with an existing crawled page.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    # Get page_id from query params
    page_id = request.query_params.get("page_id")

    logger.debug(
        "Content brief fetch request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "page_id": page_id,
            "keyword": data.keyword[:50] if data.keyword else "",
            "target_url": data.target_url[:100] if data.target_url else "",
        },
    )

    # Validate page_id is provided
    if not page_id:
        logger.warning(
            "Content brief fetch missing page_id",
            extra={
                "request_id": request_id,
                "project_id": project_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "page_id query parameter is required",
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    # Verify page exists and belongs to project
    page, page_not_found = await _verify_page_exists(
        page_id, project_id, session, request_id
    )
    if page_not_found:
        return page_not_found

    try:
        # Create service with session for persistence
        service = POPContentBriefService(session=session)

        # Fetch and save the content brief
        result = await service.fetch_and_save_brief(
            project_id=project_id,
            page_id=page_id,
            keyword=data.keyword,
            target_url=data.target_url,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        if result.success and result.brief_id:
            # Fetch the saved brief to return full response
            stmt = select(ContentBrief).where(ContentBrief.id == result.brief_id)
            db_result = await session.execute(stmt)
            brief = db_result.scalar_one_or_none()

            logger.info(
                "Content brief fetch complete",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                    "brief_id": result.brief_id,
                    "keyword": data.keyword[:50],
                    "success": True,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return ContentBriefCreateResponse(
                success=True,
                brief=_convert_brief_to_response(brief) if brief else None,
                error=None,
                duration_ms=round(duration_ms, 2),
            )
        else:
            logger.warning(
                "Content brief fetch failed",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": data.keyword[:50],
                    "error": result.error,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return ContentBriefCreateResponse(
                success=False,
                brief=None,
                error=result.error,
                duration_ms=round(duration_ms, 2),
            )

    except POPContentBriefValidationError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Content brief validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": page_id,
                "field": e.field_name,
                "value": str(e.value)[:100],
                "message": str(e),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )
    except POPContentBriefServiceError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Content brief service error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": page_id,
                "keyword": data.keyword[:50],
                "error": str(e),
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Content brief service error",
                "code": "SERVICE_ERROR",
                "request_id": request_id,
            },
        )
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Content brief fetch failed unexpectedly",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": page_id,
                "keyword": data.keyword[:50] if data.keyword else "",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "duration_ms": round(duration_ms, 2),
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
    "/pages/{page_id}/brief",
    response_model=ContentBriefResponse,
    summary="Get content brief for a page",
    description="Get the existing content brief for a specific page.",
    responses={
        404: {
            "description": "Project, page, or brief not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Content brief not found for page: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def get_content_brief(
    request: Request,
    project_id: str,
    page_id: str,
    session: AsyncSession = Depends(get_session),
) -> ContentBriefResponse | JSONResponse:
    """Get the existing content brief for a page.

    Returns the most recent content brief associated with the specified page.
    If no brief exists for the page, returns 404.
    """
    request_id = _get_request_id(request)

    logger.debug(
        "Get content brief request",
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

    # Verify page exists and belongs to project
    page, page_not_found = await _verify_page_exists(
        page_id, project_id, session, request_id
    )
    if page_not_found:
        return page_not_found

    try:
        # Get the content brief for this page
        stmt = select(ContentBrief).where(ContentBrief.page_id == page_id)
        result = await session.execute(stmt)
        brief = result.scalar_one_or_none()

        if brief is None:
            logger.warning(
                "Content brief not found",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Content brief not found for page: {page_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        logger.debug(
            "Content brief retrieved",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": page_id,
                "brief_id": brief.id,
            },
        )

        return _convert_brief_to_response(brief)

    except Exception as e:
        logger.error(
            "Failed to get content brief",
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
