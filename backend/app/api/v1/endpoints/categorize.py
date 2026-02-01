"""Categorize phase API endpoints for projects.

Provides page categorization operations for a project:
- POST /api/v1/projects/{project_id}/phases/categorize - Categorize a single page
- POST /api/v1/projects/{project_id}/phases/categorize/batch - Categorize multiple pages
- POST /api/v1/projects/{project_id}/phases/categorize/pages - Categorize by page IDs
- POST /api/v1/projects/{project_id}/phases/categorize/all - Categorize all uncategorized pages
- GET /api/v1/projects/{project_id}/phases/categorize/stats - Get categorization statistics
- PUT /api/v1/projects/{project_id}/phases/categorize/pages/{page_id} - Update page category

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
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.crawled_page import CrawledPage
from app.schemas.categorize import (
    CategorizeAllRequest,
    CategorizeAllResponse,
    CategorizeBatchRequest,
    CategorizedPageResponse,
    CategorizePageIdsRequest,
    CategorizePageIdsResponse,
    CategorizeRequest,
    CategorizeResponse,
    CategorizeStatsResponse,
    ContentAnalysisResponse,
    ContentSignalResponse,
    UpdateCategoryRequest,
    UpdateCategoryResponse,
)
from app.services.category import (
    CategorizationRequest,
    CategoryService,
    CategoryValidationError,
)
from app.services.project import ProjectNotFoundError, ProjectService
from app.utils.content_signals import ContentAnalysis
from app.utils.url_categorizer import VALID_PAGE_CATEGORIES

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


def _content_analysis_to_response(
    analysis: ContentAnalysis | None,
) -> ContentAnalysisResponse | None:
    """Convert ContentAnalysis to response schema."""
    if analysis is None:
        return None
    return ContentAnalysisResponse(
        url_category=analysis.url_category,
        url_confidence=analysis.url_confidence,
        signals=[
            ContentSignalResponse(
                signal_type=s.signal_type.value if hasattr(s.signal_type, "value") else str(s.signal_type),
                category=s.category,
                confidence_boost=s.confidence_boost,
                matched_text=s.matched_text,
            )
            for s in analysis.signals
        ],
        boosted_confidence=analysis.boosted_confidence,
        final_category=analysis.final_category,
    )


@router.post(
    "",
    response_model=CategorizeResponse,
    summary="Categorize a page",
    description="Categorize a single page using URL patterns and optional content signals.",
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
                        "error": "Validation failed for 'url': Invalid URL format",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def categorize_page(
    request: Request,
    project_id: str,
    data: CategorizeRequest,
    session: AsyncSession = Depends(get_session),
) -> CategorizeResponse | JSONResponse:
    """Categorize a single page.

    Uses a two-tier approach:
    1. URL patterns + content signals (fast, free)
    2. LLM fallback via Claude if confidence is low (slower, costs tokens)
    """
    request_id = _get_request_id(request)
    logger.debug(
        "Categorize page request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "url": data.url[:200],
            "has_title": data.title is not None,
            "has_content": data.content is not None,
            "force_llm": data.force_llm,
            "skip_llm": data.skip_llm,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CategoryService()
    try:
        result = await service.categorize(
            url=data.url,
            title=data.title,
            content=data.content,
            headings=data.headings,
            schema_json=data.json_ld_schema,
            meta_description=data.meta_description,
            breadcrumbs=data.breadcrumbs,
            project_id=project_id,
            force_llm=data.force_llm,
            skip_llm=data.skip_llm,
        )

        logger.info(
            "Page categorized",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "url": data.url[:200],
                "category": result.category,
                "confidence": result.confidence,
                "tier": result.tier,
            },
        )

        return CategorizeResponse(
            success=result.success,
            url=result.url,
            category=result.category,
            confidence=result.confidence,
            tier=result.tier,
            url_category=result.url_category,
            url_confidence=result.url_confidence,
            content_analysis=_content_analysis_to_response(result.content_analysis),
            llm_result=result.llm_result,
            labels=result.labels,
            reasoning=result.reasoning,
            error=result.error,
            duration_ms=result.duration_ms,
        )

    except CategoryValidationError as e:
        logger.warning(
            "Categorization validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
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
    except Exception as e:
        logger.error(
            "Failed to categorize page",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "url": data.url[:200],
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


@router.post(
    "/batch",
    response_model=list[CategorizeResponse],
    summary="Batch categorize pages",
    description="Categorize multiple pages in a single request.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def categorize_batch(
    request: Request,
    project_id: str,
    data: CategorizeBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> list[CategorizeResponse] | JSONResponse:
    """Categorize multiple pages in a batch.

    Uses two-phase processing:
    1. Pattern-based categorization for all pages (fast)
    2. LLM batch processing for low-confidence pages
    """
    request_id = _get_request_id(request)
    logger.debug(
        "Batch categorize request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "page_count": len(data.pages),
            "force_llm": data.force_llm,
            "skip_llm": data.skip_llm,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = CategoryService()
    try:
        # Convert to CategorizationRequest objects
        requests = [
            CategorizationRequest(
                url=page.url,
                title=page.title,
                content=page.content,
                headings=page.headings,
                schema_json=page.json_ld_schema,
                meta_description=page.meta_description,
                breadcrumbs=page.breadcrumbs,
                project_id=project_id,
                page_id=page.page_id,
            )
            for page in data.pages
        ]

        results = await service.categorize_many(
            pages=requests,
            force_llm=data.force_llm,
            skip_llm=data.skip_llm,
            project_id=project_id,
        )

        logger.info(
            "Batch categorization complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_count": len(data.pages),
                "success_count": sum(1 for r in results if r.success),
            },
        )

        return [
            CategorizeResponse(
                success=r.success,
                url=r.url,
                category=r.category,
                confidence=r.confidence,
                tier=r.tier,
                url_category=r.url_category,
                url_confidence=r.url_confidence,
                content_analysis=_content_analysis_to_response(r.content_analysis),
                llm_result=r.llm_result,
                labels=r.labels,
                reasoning=r.reasoning,
                error=r.error,
                duration_ms=r.duration_ms,
            )
            for r in results
        ]

    except Exception as e:
        logger.error(
            "Failed to batch categorize",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_count": len(data.pages),
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


@router.post(
    "/pages",
    response_model=CategorizePageIdsResponse,
    summary="Categorize pages by ID",
    description="Categorize existing crawled pages by their IDs.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def categorize_page_ids(
    request: Request,
    project_id: str,
    data: CategorizePageIdsRequest,
    session: AsyncSession = Depends(get_session),
) -> CategorizePageIdsResponse | JSONResponse:
    """Categorize existing crawled pages by their IDs."""
    request_id = _get_request_id(request)
    start_time = time.monotonic()
    logger.debug(
        "Categorize page IDs request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "page_count": len(data.page_ids),
            "force_llm": data.force_llm,
            "skip_llm": data.skip_llm,
            "update_pages": data.update_pages,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        # Fetch the pages
        query = select(CrawledPage).where(
            CrawledPage.id.in_(data.page_ids),
            CrawledPage.project_id == project_id,
        )
        result = await session.execute(query)
        pages = list(result.scalars().all())

        # Build a map for quick lookup
        page_map = {p.id: p for p in pages}

        # Track results
        results: list[CategorizedPageResponse] = []
        categorized = 0
        failed = 0

        service = CategoryService()

        for page_id in data.page_ids:
            page = page_map.get(page_id)
            if page is None:
                logger.warning(
                    "Page not found for categorization",
                    extra={
                        "request_id": request_id,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                failed += 1
                continue

            try:
                cat_result = await service.categorize(
                    url=page.normalized_url,
                    title=page.title,
                    project_id=project_id,
                    page_id=page.id,
                    force_llm=data.force_llm,
                    skip_llm=data.skip_llm,
                )

                updated = False
                if data.update_pages and cat_result.success:
                    page.category = cat_result.category
                    if cat_result.labels:
                        page.labels = cat_result.labels
                    page.updated_at = datetime.now(UTC)
                    updated = True

                results.append(
                    CategorizedPageResponse(
                        page_id=page.id,
                        url=page.normalized_url,
                        title=page.title,
                        category=cat_result.category,
                        confidence=cat_result.confidence,
                        tier=cat_result.tier,
                        labels=cat_result.labels,
                        updated=updated,
                    )
                )
                categorized += 1

            except Exception as e:
                logger.warning(
                    "Failed to categorize page",
                    extra={
                        "request_id": request_id,
                        "project_id": project_id,
                        "page_id": page_id,
                        "error": str(e),
                    },
                )
                failed += 1

        # Commit updates if any were made
        if data.update_pages:
            await session.commit()

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Page IDs categorization complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total": len(data.page_ids),
                "categorized": categorized,
                "failed": failed,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return CategorizePageIdsResponse(
            total=len(data.page_ids),
            categorized=categorized,
            failed=failed,
            results=results,
            duration_ms=round(duration_ms, 2),
        )

    except Exception as e:
        logger.error(
            "Failed to categorize page IDs",
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


async def _run_categorize_all_background(
    project_id: str,
    data: CategorizeAllRequest,
    session: AsyncSession,
    request_id: str,
) -> None:
    """Background task to categorize all pages."""
    try:
        logger.info(
            "Starting background categorization for all pages",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "include_categorized": data.include_categorized,
            },
        )

        # Build query for pages to categorize
        query = select(CrawledPage).where(CrawledPage.project_id == project_id)
        if not data.include_categorized:
            query = query.where(CrawledPage.category.is_(None))

        result = await session.execute(query)
        pages = list(result.scalars().all())

        if not pages:
            logger.info(
                "No pages to categorize",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                },
            )
            return

        service = CategoryService()

        # Build categorization requests
        requests = [
            CategorizationRequest(
                url=page.normalized_url,
                title=page.title,
                project_id=project_id,
                page_id=page.id,
            )
            for page in pages
        ]

        # Run batch categorization
        results = await service.categorize_many(
            pages=requests,
            force_llm=data.force_llm,
            skip_llm=data.skip_llm,
            project_id=project_id,
            batch_size=data.batch_size,
        )

        # Update pages with results
        if data.update_pages:
            page_map = {p.id: p for p in pages}
            for cat_result in results:
                if cat_result.success and cat_result.page_id:
                    page = page_map.get(cat_result.page_id)
                    if page:
                        page.category = cat_result.category
                        if cat_result.labels:
                            page.labels = cat_result.labels
                        page.updated_at = datetime.now(UTC)

            await session.commit()

        logger.info(
            "Background categorization complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total": len(pages),
                "success_count": sum(1 for r in results if r.success),
            },
        )

    except Exception as e:
        logger.error(
            "Background categorization failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )


@router.post(
    "/all",
    response_model=CategorizeAllResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Categorize all pages",
    description="Categorize all uncategorized pages in a project. Returns immediately.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def categorize_all_pages(
    request: Request,
    project_id: str,
    data: CategorizeAllRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> CategorizeAllResponse | JSONResponse:
    """Categorize all uncategorized pages in a project.

    Runs in the background for large page sets.
    Returns 202 Accepted immediately with initial statistics.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()
    logger.debug(
        "Categorize all pages request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "force_llm": data.force_llm,
            "skip_llm": data.skip_llm,
            "include_categorized": data.include_categorized,
            "batch_size": data.batch_size,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        # Count pages to categorize
        query = select(func.count()).select_from(CrawledPage).where(
            CrawledPage.project_id == project_id
        )
        if not data.include_categorized:
            query = query.where(CrawledPage.category.is_(None))

        result = await session.execute(query)
        total_to_categorize = result.scalar() or 0

        # Count already categorized if not including them
        skipped = 0
        if not data.include_categorized:
            count_query = select(func.count()).select_from(CrawledPage).where(
                CrawledPage.project_id == project_id,
                CrawledPage.category.isnot(None),
            )
            count_result = await session.execute(count_query)
            skipped = count_result.scalar() or 0

        # Queue background task
        background_tasks.add_task(
            _run_categorize_all_background,
            project_id=project_id,
            data=data,
            session=session,
            request_id=request_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Categorize all pages queued",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total": total_to_categorize,
                "skipped": skipped,
            },
        )

        return CategorizeAllResponse(
            total=total_to_categorize,
            categorized=0,  # Will be populated when complete
            failed=0,
            skipped=skipped,
            category_counts={},
            tier_counts={},
            duration_ms=round(duration_ms, 2),
        )

    except Exception as e:
        logger.error(
            "Failed to start categorize all",
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
    "/stats",
    response_model=CategorizeStatsResponse,
    summary="Get categorization statistics",
    description="Get statistics about page categorization for a project.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def get_categorize_stats(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> CategorizeStatsResponse | JSONResponse:
    """Get categorization statistics for a project."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get categorize stats request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        # Total pages
        total_query = select(func.count()).select_from(CrawledPage).where(
            CrawledPage.project_id == project_id
        )
        total_result = await session.execute(total_query)
        total_pages = total_result.scalar() or 0

        # Categorized pages (category is not null)
        categorized_query = select(func.count()).select_from(CrawledPage).where(
            CrawledPage.project_id == project_id,
            CrawledPage.category.isnot(None),
        )
        categorized_result = await session.execute(categorized_query)
        categorized_pages = categorized_result.scalar() or 0

        # Count per category
        category_query = (
            select(CrawledPage.category, func.count())
            .where(
                CrawledPage.project_id == project_id,
                CrawledPage.category.isnot(None),
            )
            .group_by(CrawledPage.category)
        )
        category_result = await session.execute(category_query)
        category_counts = {row[0]: row[1] for row in category_result.fetchall()}

        logger.debug(
            "Categorize stats retrieved",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_pages": total_pages,
                "categorized_pages": categorized_pages,
            },
        )

        return CategorizeStatsResponse(
            project_id=project_id,
            total_pages=total_pages,
            categorized_pages=categorized_pages,
            uncategorized_pages=total_pages - categorized_pages,
            category_counts=category_counts,
            valid_categories=sorted(VALID_PAGE_CATEGORIES),
        )

    except Exception as e:
        logger.error(
            "Failed to get categorize stats",
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


@router.put(
    "/pages/{page_id}",
    response_model=UpdateCategoryResponse,
    summary="Update page category",
    description="Manually update a page's category.",
    responses={
        404: {"description": "Project or page not found"},
        400: {"description": "Invalid category"},
    },
)
async def update_page_category(
    request: Request,
    project_id: str,
    page_id: str,
    data: UpdateCategoryRequest,
    session: AsyncSession = Depends(get_session),
) -> UpdateCategoryResponse | JSONResponse:
    """Manually update a page's category."""
    request_id = _get_request_id(request)
    logger.debug(
        "Update page category request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "page_id": page_id,
            "new_category": data.category,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        # Fetch the page
        query = select(CrawledPage).where(
            CrawledPage.id == page_id,
            CrawledPage.project_id == project_id,
        )
        result = await session.execute(query)
        page = result.scalar_one_or_none()

        if page is None:
            logger.warning(
                "Page not found for category update",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Page not found: {page_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            )

        old_category = page.category
        page.category = data.category
        if data.labels is not None:
            page.labels = data.labels
        page.updated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(page)

        logger.info(
            "Page category updated",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": page_id,
                "old_category": old_category,
                "new_category": data.category,
            },
        )

        return UpdateCategoryResponse(
            page_id=page.id,
            url=page.normalized_url,
            old_category=old_category,
            new_category=page.category,
            labels=page.labels,
            updated_at=page.updated_at,
        )

    except Exception as e:
        logger.error(
            "Failed to update page category",
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
