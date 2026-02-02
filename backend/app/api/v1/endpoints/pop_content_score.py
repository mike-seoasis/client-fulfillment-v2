"""Content Score phase API endpoints for projects.

Provides content scoring operations for a project:
- POST /api/v1/projects/{project_id}/phases/content_score/score - Score content for a page
- POST /api/v1/projects/{project_id}/phases/content_score/batch - Batch score multiple pages

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

import asyncio
import time

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.content_score import ContentScore
from app.models.crawled_page import CrawledPage
from app.schemas.content_score import (
    ContentScoreBatchItemResponse,
    ContentScoreBatchRequest,
    ContentScoreBatchResponse,
    ContentScoreCreateResponse,
    ContentScoreRequest,
    ContentScoreResponse,
)
from app.services.pop_content_score import (
    POPContentScoreService,
    POPContentScoreServiceError,
    POPContentScoreValidationError,
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


def _convert_score_to_response(score: ContentScore) -> ContentScoreResponse:
    """Convert ContentScore model to API response schema.

    The ContentScore model stores JSONB fields as dict[str, Any], but the
    ContentScoreResponse schema uses typed nested Pydantic models. Pydantic's
    from_attributes mode handles the coercion automatically, but we need to
    pass the raw dict values and let Pydantic do the conversion.
    """
    return ContentScoreResponse(
        id=score.id,
        page_id=score.page_id,
        pop_task_id=score.pop_task_id,
        page_score=score.page_score,
        passed=score.passed,
        keyword_analysis=score.keyword_analysis,  # type: ignore[arg-type]
        lsi_coverage=score.lsi_coverage,  # type: ignore[arg-type]
        word_count_current=score.word_count_current,
        heading_analysis=score.heading_analysis,  # type: ignore[arg-type]
        recommendations=score.recommendations,
        fallback_used=score.fallback_used,
        scored_at=score.scored_at,
        created_at=score.created_at,
    )


@router.post(
    "/score",
    response_model=ContentScoreCreateResponse,
    summary="Score content for a page",
    description="Score content from POP API for a keyword/URL and save to database.",
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
async def score_content(
    request: Request,
    project_id: str,
    data: ContentScoreRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentScoreCreateResponse | JSONResponse:
    """Score content from POP API for a keyword/URL.

    Creates a POP report task, polls for completion, parses the results,
    and saves the content score to the database. Each scoring creates a
    new record to maintain scoring history.

    The request requires a page_id query parameter to associate the score
    with an existing crawled page.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    # Get page_id from query params
    page_id = request.query_params.get("page_id")

    logger.debug(
        "Content score request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "page_id": page_id,
            "keyword": data.keyword[:50] if data.keyword else "",
            "content_url": data.content_url[:100] if data.content_url else "",
        },
    )

    # Validate page_id is provided
    if not page_id:
        logger.warning(
            "Content score missing page_id",
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
        service = POPContentScoreService(session=session)

        # Score and save the content
        result = await service.score_and_save_content(
            project_id=project_id,
            page_id=page_id,
            keyword=data.keyword,
            content_url=data.content_url,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        if result.success and result.score_id:
            # Fetch the saved score to return full response
            stmt = select(ContentScore).where(ContentScore.id == result.score_id)
            db_result = await session.execute(stmt)
            score = db_result.scalar_one_or_none()

            logger.info(
                "Content score complete",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                    "score_id": result.score_id,
                    "keyword": data.keyword[:50],
                    "page_score": result.page_score,
                    "passed": result.passed,
                    "fallback_used": result.fallback_used,
                    "success": True,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return ContentScoreCreateResponse(
                success=True,
                score=_convert_score_to_response(score) if score else None,
                error=None,
                fallback_used=result.fallback_used,
                duration_ms=round(duration_ms, 2),
            )
        else:
            logger.warning(
                "Content score failed",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": data.keyword[:50],
                    "error": result.error,
                    "fallback_used": result.fallback_used,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return ContentScoreCreateResponse(
                success=False,
                score=None,
                error=result.error,
                fallback_used=result.fallback_used,
                duration_ms=round(duration_ms, 2),
            )

    except POPContentScoreValidationError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Content score validation error",
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
    except POPContentScoreServiceError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Content score service error",
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
                "error": "Content score service error",
                "code": "SERVICE_ERROR",
                "request_id": request_id,
            },
        )
    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Content score failed unexpectedly",
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


@router.post(
    "/batch",
    response_model=ContentScoreBatchResponse,
    summary="Batch score content for multiple pages",
    description="Score content from POP API for multiple keyword/URL pairs concurrently.",
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
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation failed: items cannot be empty",
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
async def batch_score_content(
    request: Request,
    project_id: str,
    data: ContentScoreBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentScoreBatchResponse | JSONResponse:
    """Batch score content from POP API for multiple keyword/URL pairs.

    Processes multiple scoring requests concurrently up to max_concurrent limit.
    Each item requires a page_id query parameter in the request items or as a
    comma-separated list in the query string (page_ids=uuid1,uuid2,...).

    Returns individual results for each item, with overall statistics.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    # Get page_ids from query params (comma-separated)
    page_ids_param = request.query_params.get("page_ids", "")
    page_ids = [pid.strip() for pid in page_ids_param.split(",") if pid.strip()]

    logger.debug(
        "Batch content score request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "item_count": len(data.items),
            "page_ids_count": len(page_ids),
            "max_concurrent": data.max_concurrent,
        },
    )

    # Validate page_ids count matches items count
    if len(page_ids) != len(data.items):
        logger.warning(
            "Batch content score page_ids count mismatch",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "item_count": len(data.items),
                "page_ids_count": len(page_ids),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": f"page_ids count ({len(page_ids)}) must match items count ({len(data.items)})",
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    # Verify all pages exist and belong to project
    for page_id in page_ids:
        _, page_not_found = await _verify_page_exists(
            page_id, project_id, session, request_id
        )
        if page_not_found:
            return page_not_found

    try:
        results: list[ContentScoreBatchItemResponse] = []
        semaphore = asyncio.Semaphore(data.max_concurrent)

        async def score_single_item(
            item: ContentScoreRequest,
            page_id: str,
        ) -> ContentScoreBatchItemResponse:
            """Score a single item with semaphore control."""
            async with semaphore:
                try:
                    # Create service with session for persistence
                    service = POPContentScoreService(session=session)

                    result = await service.score_and_save_content(
                        project_id=project_id,
                        page_id=page_id,
                        keyword=item.keyword,
                        content_url=item.content_url,
                    )

                    logger.debug(
                        "Batch item scored",
                        extra={
                            "request_id": request_id,
                            "project_id": project_id,
                            "page_id": page_id,
                            "keyword": item.keyword[:50],
                            "success": result.success,
                            "page_score": result.page_score,
                            "passed": result.passed,
                            "fallback_used": result.fallback_used,
                        },
                    )

                    return ContentScoreBatchItemResponse(
                        page_id=page_id,
                        keyword=item.keyword,
                        success=result.success,
                        score_id=result.score_id,
                        page_score=result.page_score,
                        passed=result.passed,
                        fallback_used=result.fallback_used,
                        error=result.error,
                    )

                except Exception as e:
                    logger.error(
                        "Batch item scoring failed",
                        extra={
                            "request_id": request_id,
                            "project_id": project_id,
                            "page_id": page_id,
                            "keyword": item.keyword[:50],
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                        exc_info=True,
                    )
                    return ContentScoreBatchItemResponse(
                        page_id=page_id,
                        keyword=item.keyword,
                        success=False,
                        error=str(e),
                    )

        # Process all items concurrently with semaphore limit
        tasks = [
            score_single_item(item, page_id)
            for item, page_id in zip(data.items, page_ids, strict=True)
        ]
        results = await asyncio.gather(*tasks)

        duration_ms = (time.monotonic() - start_time) * 1000

        # Calculate statistics
        successful_items = sum(1 for r in results if r.success)
        failed_items = sum(1 for r in results if not r.success)
        items_passed = sum(1 for r in results if r.success and r.passed is True)
        items_failed_threshold = sum(
            1 for r in results if r.success and r.passed is False
        )
        fallback_count = sum(1 for r in results if r.fallback_used)

        logger.info(
            "Batch content score complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_items": len(data.items),
                "successful_items": successful_items,
                "failed_items": failed_items,
                "items_passed": items_passed,
                "items_failed_threshold": items_failed_threshold,
                "fallback_count": fallback_count,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return ContentScoreBatchResponse(
            success=True,
            results=results,
            total_items=len(data.items),
            successful_items=successful_items,
            failed_items=failed_items,
            items_passed=items_passed,
            items_failed_threshold=items_failed_threshold,
            fallback_count=fallback_count,
            error=None,
            duration_ms=round(duration_ms, 2),
        )

    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Batch content score failed unexpectedly",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "item_count": len(data.items),
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
