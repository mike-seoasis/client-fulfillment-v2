"""Content Score phase API endpoints for projects.

Provides content scoring operations for a project:
- POST /api/v1/projects/{project_id}/phases/content_score/score - Score content for a page
- POST /api/v1/projects/{project_id}/phases/content_score/batch - Batch score multiple pages

The scoring behavior is controlled by the use_pop_scoring feature flag:
- When enabled (True): Uses POPContentScoreService for SERP-based POP API scoring
- When disabled (False): Uses legacy ContentScoreService for local content analysis

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
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
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
from app.services.content_score import (
    ContentScoreInput,
    get_content_score_service,
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


async def _score_with_legacy_service(
    project_id: str,
    page_id: str,
    keyword: str,
    content_url: str,
    session: AsyncSession,
    request_id: str,
) -> tuple[ContentScore | None, str | None]:
    """Score content using legacy ContentScoreService when POP is disabled.

    When use_pop_scoring flag is False, this function handles scoring using
    the legacy ContentScoreService. Since the legacy service requires actual
    content text (not a URL), we attempt to fetch the page's cached content
    from the database.

    Args:
        project_id: Project ID
        page_id: Page ID
        keyword: Target keyword for scoring
        content_url: URL of the content (for reference, not fetched)
        session: Database session
        request_id: Request ID for logging

    Returns:
        Tuple of (ContentScore, None) on success, or (None, error_message) on failure
    """
    start_time = time.monotonic()

    logger.info(
        "Using legacy ContentScoreService (POP scoring disabled)",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "page_id": page_id,
            "keyword": keyword[:50] if keyword else "",
            "use_pop_scoring": False,
        },
    )

    try:
        # Get the page to access any cached content
        stmt = select(CrawledPage).where(CrawledPage.id == page_id)
        result = await session.execute(stmt)
        page = result.scalar_one_or_none()

        if not page:
            return None, f"Page not found: {page_id}"

        # Get content from page if available (body_text or similar field)
        content = ""
        if hasattr(page, "body_text") and page.body_text:
            content = page.body_text
        elif hasattr(page, "content") and page.content:
            content = page.content
        elif hasattr(page, "raw_html") and page.raw_html:
            # Strip HTML tags for basic content extraction
            import re

            content = re.sub(r"<[^>]+>", " ", page.raw_html)
            content = re.sub(r"\s+", " ", content).strip()

        # If no content available, use a minimal placeholder
        # The legacy service will return a low score for empty content
        if not content:
            logger.warning(
                "No content available for legacy scoring",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            content = keyword  # Use keyword as minimal content

        # Get legacy service and score
        legacy_service = get_content_score_service()
        legacy_input = ContentScoreInput(
            content=content,
            primary_keyword=keyword,
            secondary_keywords=[],
            project_id=project_id,
            page_id=page_id,
        )

        legacy_result = await legacy_service.score_content(legacy_input)

        duration_ms = (time.monotonic() - start_time) * 1000

        if not legacy_result.success:
            logger.warning(
                "Legacy scoring failed",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                    "error": legacy_result.error,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return None, legacy_result.error

        # Convert legacy score (0.0-1.0) to POP scale (0-100)
        page_score = legacy_result.overall_score * 100

        # Determine pass/fail using POP threshold
        settings = get_settings()
        passed = page_score >= settings.pop_pass_threshold

        # Create ContentScore record
        score = ContentScore(
            page_id=page_id,
            pop_task_id=None,  # No POP task for legacy scoring
            page_score=page_score,
            passed=passed,
            keyword_analysis=None,
            lsi_coverage=None,
            word_count_current=(
                legacy_result.word_count_score.word_count
                if legacy_result.word_count_score
                else None
            ),
            heading_analysis=None,
            recommendations=[],
            fallback_used=False,  # Not a fallback - intentionally using legacy
            raw_response={
                "legacy_scoring": True,
                "overall_score": legacy_result.overall_score,
                "word_count_score": (
                    legacy_result.word_count_score.to_dict()
                    if legacy_result.word_count_score
                    else None
                ),
                "semantic_score": (
                    legacy_result.semantic_score.to_dict()
                    if legacy_result.semantic_score
                    else None
                ),
                "readability_score": (
                    legacy_result.readability_score.to_dict()
                    if legacy_result.readability_score
                    else None
                ),
                "keyword_density_score": (
                    legacy_result.keyword_density_score.to_dict()
                    if legacy_result.keyword_density_score
                    else None
                ),
                "entity_coverage_score": (
                    legacy_result.entity_coverage_score.to_dict()
                    if legacy_result.entity_coverage_score
                    else None
                ),
            },
            scored_at=datetime.now(UTC),
        )

        # Save to database
        session.add(score)
        await session.flush()
        await session.refresh(score)

        logger.info(
            "Legacy scoring complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": page_id,
                "score_id": score.id,
                "page_score": page_score,
                "passed": passed,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return score, None

    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Legacy scoring error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": page_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": round(duration_ms, 2),
            },
            exc_info=True,
        )
        return None, f"Legacy scoring error: {e}"


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
    """Score content for a keyword/URL.

    The scoring behavior is controlled by the use_pop_scoring feature flag:
    - When enabled (True): Uses POPContentScoreService for SERP-based POP API scoring
    - When disabled (False): Uses legacy ContentScoreService for local content analysis

    Creates a scoring record and saves to the database. Each scoring creates a
    new record to maintain scoring history.

    The request requires a page_id query parameter to associate the score
    with an existing crawled page.

    Response includes fallback_used indicator:
    - False when using POP scoring successfully or when using legacy service by flag
    - True when POP scoring failed and fell back to legacy service
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    # Get page_id from query params
    page_id = request.query_params.get("page_id")

    # Check feature flag
    settings = get_settings()
    use_pop = settings.use_pop_scoring

    logger.debug(
        "Content score request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "page_id": page_id,
            "keyword": data.keyword[:50] if data.keyword else "",
            "content_url": data.content_url[:100] if data.content_url else "",
            "use_pop_scoring": use_pop,
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

    # Route to appropriate scoring service based on feature flag
    if not use_pop:
        # Use legacy ContentScoreService when POP is disabled
        score, error = await _score_with_legacy_service(
            project_id=project_id,
            page_id=page_id,
            keyword=data.keyword,
            content_url=data.content_url,
            session=session,
            request_id=request_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        if score:
            return ContentScoreCreateResponse(
                success=True,
                score=_convert_score_to_response(score),
                error=None,
                fallback_used=False,  # Not a fallback - intentionally using legacy
                duration_ms=round(duration_ms, 2),
            )
        else:
            return ContentScoreCreateResponse(
                success=False,
                score=None,
                error=error,
                fallback_used=False,
                duration_ms=round(duration_ms, 2),
            )

    # Use POPContentScoreService when POP is enabled (default behavior)
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
    """Batch score content for multiple keyword/URL pairs.

    The scoring behavior is controlled by the use_pop_scoring feature flag:
    - When enabled (True): Uses POPContentScoreService for SERP-based POP API scoring
    - When disabled (False): Uses legacy ContentScoreService for local content analysis

    Processes multiple scoring requests concurrently up to max_concurrent limit.
    Each item requires a page_id query parameter in the request items or as a
    comma-separated list in the query string (page_ids=uuid1,uuid2,...).

    Returns individual results for each item, with overall statistics.
    Response includes fallback_used indicator per item and fallback_count total.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    # Check feature flag
    settings = get_settings()
    use_pop = settings.use_pop_scoring

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
            "use_pop_scoring": use_pop,
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
                    # Route based on feature flag
                    if not use_pop:
                        # Use legacy ContentScoreService when POP is disabled
                        score, error = await _score_with_legacy_service(
                            project_id=project_id,
                            page_id=page_id,
                            keyword=item.keyword,
                            content_url=item.content_url,
                            session=session,
                            request_id=request_id,
                        )

                        logger.debug(
                            "Batch item scored (legacy)",
                            extra={
                                "request_id": request_id,
                                "project_id": project_id,
                                "page_id": page_id,
                                "keyword": item.keyword[:50],
                                "success": score is not None,
                                "page_score": score.page_score if score else None,
                                "passed": score.passed if score else None,
                                "fallback_used": False,
                                "use_pop_scoring": False,
                            },
                        )

                        if score:
                            return ContentScoreBatchItemResponse(
                                page_id=page_id,
                                keyword=item.keyword,
                                success=True,
                                score_id=score.id,
                                page_score=score.page_score,
                                passed=score.passed,
                                fallback_used=False,  # Not a fallback
                                error=None,
                            )
                        else:
                            return ContentScoreBatchItemResponse(
                                page_id=page_id,
                                keyword=item.keyword,
                                success=False,
                                fallback_used=False,
                                error=error,
                            )

                    # Use POPContentScoreService when POP is enabled
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
