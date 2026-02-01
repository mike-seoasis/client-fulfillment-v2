"""Label phase API endpoints for projects.

Provides label generation operations for a project:
- POST /api/v1/projects/{project_id}/phases/label - Generate labels for a collection
- POST /api/v1/projects/{project_id}/phases/label/batch - Generate labels for multiple collections
- POST /api/v1/projects/{project_id}/phases/label/pages - Generate labels by page IDs
- POST /api/v1/projects/{project_id}/phases/label/all - Generate labels for all pages
- GET /api/v1/projects/{project_id}/phases/label/stats - Get label statistics

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
from collections import Counter
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.crawled_page import CrawledPage
from app.schemas.label import (
    LabelAllRequest,
    LabelAllResponse,
    LabelBatchItemResponse,
    LabelBatchRequest,
    LabelBatchResponse,
    LabeledPageResponse,
    LabelGenerateRequest,
    LabelGenerateResponse,
    LabelPageIdsRequest,
    LabelPageIdsResponse,
    LabelStatsResponse,
)
from app.services.label import (
    LabelRequest,
    LabelValidationError,
    get_label_service,
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


@router.post(
    "",
    response_model=LabelGenerateResponse,
    summary="Generate labels for a collection",
    description="Generate 2-5 thematic labels for a collection of pages.",
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
                        "error": "Validation failed for 'urls': At least one valid URL is required",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def generate_labels(
    request: Request,
    project_id: str,
    data: LabelGenerateRequest,
    session: AsyncSession = Depends(get_session),
) -> LabelGenerateResponse | JSONResponse:
    """Generate thematic labels for a collection of pages.

    Uses a two-tier approach:
    1. Pattern-based labeling from categories, URLs, and titles (fast, free)
    2. LLM fallback via Claude if confidence is low (slower, costs tokens)
    """
    request_id = _get_request_id(request)
    logger.debug(
        "Generate labels request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "url_count": len(data.urls),
            "has_titles": data.titles is not None,
            "has_categories": data.categories is not None,
            "force_llm": data.force_llm,
            "skip_llm": data.skip_llm,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = get_label_service()
    try:
        result = await service.generate_labels(
            urls=data.urls,
            titles=data.titles,
            categories=data.categories,
            content_snippets=data.content_snippets,
            project_id=project_id,
            force_llm=data.force_llm,
            skip_llm=data.skip_llm,
        )

        logger.info(
            "Labels generated",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "labels": result.labels,
                "confidence": result.confidence,
                "tier": result.tier,
                "duration_ms": result.duration_ms,
            },
        )

        return LabelGenerateResponse(
            success=result.success,
            labels=result.labels,
            confidence=result.confidence,
            tier=result.tier,
            pattern_labels=result.pattern_labels,
            llm_labels=result.llm_labels,
            reasoning=result.reasoning,
            error=result.error,
            duration_ms=result.duration_ms,
        )

    except LabelValidationError as e:
        logger.warning(
            "Label validation error",
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
            "Failed to generate labels",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "url_count": len(data.urls),
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
    response_model=LabelBatchResponse,
    summary="Batch generate labels",
    description="Generate labels for multiple collections in parallel.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def generate_labels_batch(
    request: Request,
    project_id: str,
    data: LabelBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> LabelBatchResponse | JSONResponse:
    """Generate labels for multiple collections in a batch.

    Uses parallel processing with configurable concurrency limit.
    """
    request_id = _get_request_id(request)
    logger.debug(
        "Batch generate labels request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "collection_count": len(data.collections),
            "max_concurrent": data.max_concurrent,
            "force_llm": data.force_llm,
            "skip_llm": data.skip_llm,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = get_label_service()
    try:
        # Convert to LabelRequest objects
        requests = [
            LabelRequest(
                urls=collection.urls,
                titles=collection.titles or [],
                categories=collection.categories or [],
                content_snippets=collection.content_snippets or [],
                project_id=project_id,
            )
            for collection in data.collections
        ]

        batch_result = await service.generate_labels_batch(
            requests=requests,
            max_concurrent=data.max_concurrent,
            force_llm=data.force_llm,
            skip_llm=data.skip_llm,
        )

        logger.info(
            "Batch label generation complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "collection_count": len(data.collections),
                "successful_count": batch_result.successful_count,
                "failed_count": batch_result.failed_count,
                "total_duration_ms": batch_result.total_duration_ms,
            },
        )

        # Build response items with collection_id from original request
        result_items = []
        for i, result in enumerate(batch_result.results):
            collection_id = (
                data.collections[i].collection_id if i < len(data.collections) else None
            )
            result_items.append(
                LabelBatchItemResponse(
                    collection_id=collection_id,
                    success=result.success,
                    labels=result.labels,
                    confidence=result.confidence,
                    tier=result.tier,
                    error=result.error,
                    duration_ms=result.duration_ms,
                )
            )

        return LabelBatchResponse(
            success=batch_result.success,
            results=result_items,
            total_duration_ms=batch_result.total_duration_ms,
            successful_count=batch_result.successful_count,
            failed_count=batch_result.failed_count,
            max_concurrent=batch_result.max_concurrent,
        )

    except Exception as e:
        logger.error(
            "Failed to batch generate labels",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "collection_count": len(data.collections),
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
    response_model=LabelPageIdsResponse,
    summary="Generate labels by page IDs",
    description="Generate labels for existing crawled pages by their IDs.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def generate_labels_for_page_ids(
    request: Request,
    project_id: str,
    data: LabelPageIdsRequest,
    session: AsyncSession = Depends(get_session),
) -> LabelPageIdsResponse | JSONResponse:
    """Generate labels for existing crawled pages by their IDs."""
    request_id = _get_request_id(request)
    start_time = time.monotonic()
    logger.debug(
        "Generate labels for page IDs request",
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
        results: list[LabeledPageResponse] = []
        labeled = 0
        failed = 0

        service = get_label_service()

        for page_id in data.page_ids:
            page = page_map.get(page_id)
            if page is None:
                logger.warning(
                    "Page not found for label generation",
                    extra={
                        "request_id": request_id,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                failed += 1
                continue

            try:
                label_result = await service.generate_labels(
                    urls=[page.normalized_url],
                    titles=[page.title] if page.title else [],
                    categories=[page.category] if page.category else [],
                    project_id=project_id,
                    force_llm=data.force_llm,
                    skip_llm=data.skip_llm,
                )

                updated = False
                if data.update_pages and label_result.success:
                    page.labels = label_result.labels
                    page.updated_at = datetime.now(UTC)
                    updated = True

                results.append(
                    LabeledPageResponse(
                        page_id=page.id,
                        url=page.normalized_url,
                        title=page.title,
                        labels=label_result.labels,
                        confidence=label_result.confidence,
                        tier=label_result.tier,
                        updated=updated,
                    )
                )
                labeled += 1

            except Exception as e:
                logger.warning(
                    "Failed to generate labels for page",
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
            "Page IDs label generation complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total": len(data.page_ids),
                "labeled": labeled,
                "failed": failed,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return LabelPageIdsResponse(
            total=len(data.page_ids),
            labeled=labeled,
            failed=failed,
            results=results,
            duration_ms=round(duration_ms, 2),
        )

    except Exception as e:
        logger.error(
            "Failed to generate labels for page IDs",
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


async def _run_label_all_background(
    project_id: str,
    data: LabelAllRequest,
    session: AsyncSession,
    request_id: str,
) -> None:
    """Background task to generate labels for all pages."""
    try:
        logger.info(
            "Starting background label generation for all pages",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "include_labeled": data.include_labeled,
            },
        )

        # Build query for pages to label
        query = select(CrawledPage).where(CrawledPage.project_id == project_id)
        if not data.include_labeled:
            # Filter to pages without labels (empty array or null)
            query = query.where(
                (CrawledPage.labels.is_(None)) | (CrawledPage.labels == [])
            )

        result = await session.execute(query)
        pages = list(result.scalars().all())

        if not pages:
            logger.info(
                "No pages to label",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                },
            )
            return

        service = get_label_service()

        # Process in batches
        labeled_count = 0
        failed_count = 0

        for i in range(0, len(pages), data.batch_size):
            batch_pages = pages[i : i + data.batch_size]

            # Build requests for the batch
            requests = [
                LabelRequest(
                    urls=[page.normalized_url],
                    titles=[page.title] if page.title else [],
                    categories=[page.category] if page.category else [],
                    project_id=project_id,
                )
                for page in batch_pages
            ]

            # Process batch
            batch_result = await service.generate_labels_batch(
                requests=requests,
                max_concurrent=5,
                force_llm=data.force_llm,
                skip_llm=data.skip_llm,
            )

            # Update pages with results
            if data.update_pages:
                for page, label_result in zip(batch_pages, batch_result.results, strict=True):
                    if label_result.success:
                        page.labels = label_result.labels
                        page.updated_at = datetime.now(UTC)
                        labeled_count += 1
                    else:
                        failed_count += 1

                await session.commit()
            else:
                labeled_count += batch_result.successful_count
                failed_count += batch_result.failed_count

        logger.info(
            "Background label generation complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total": len(pages),
                "labeled_count": labeled_count,
                "failed_count": failed_count,
            },
        )

    except Exception as e:
        logger.error(
            "Background label generation failed",
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
    response_model=LabelAllResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate labels for all pages",
    description="Generate labels for all pages in a project. Returns immediately.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def generate_labels_for_all_pages(
    request: Request,
    project_id: str,
    data: LabelAllRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> LabelAllResponse | JSONResponse:
    """Generate labels for all pages in a project.

    Runs in the background for large page sets.
    Returns 202 Accepted immediately with initial statistics.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()
    logger.debug(
        "Generate labels for all pages request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "force_llm": data.force_llm,
            "skip_llm": data.skip_llm,
            "include_labeled": data.include_labeled,
            "batch_size": data.batch_size,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        # Count pages to label
        query = select(func.count()).select_from(CrawledPage).where(
            CrawledPage.project_id == project_id
        )
        if not data.include_labeled:
            query = query.where(
                (CrawledPage.labels.is_(None)) | (CrawledPage.labels == [])
            )

        result = await session.execute(query)
        total_to_label = result.scalar() or 0

        # Count already labeled if not including them
        skipped = 0
        if not data.include_labeled:
            count_query = select(func.count()).select_from(CrawledPage).where(
                CrawledPage.project_id == project_id,
                CrawledPage.labels.isnot(None),
                CrawledPage.labels != [],
            )
            count_result = await session.execute(count_query)
            skipped = count_result.scalar() or 0

        # Queue background task
        background_tasks.add_task(
            _run_label_all_background,
            project_id=project_id,
            data=data,
            session=session,
            request_id=request_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Generate labels for all pages queued",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total": total_to_label,
                "skipped": skipped,
            },
        )

        return LabelAllResponse(
            total=total_to_label,
            labeled=0,  # Will be populated when complete
            failed=0,
            skipped=skipped,
            tier_counts={},
            duration_ms=round(duration_ms, 2),
        )

    except Exception as e:
        logger.error(
            "Failed to start generate labels for all",
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
    response_model=LabelStatsResponse,
    summary="Get label statistics",
    description="Get statistics about label generation for a project.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def get_label_stats(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> LabelStatsResponse | JSONResponse:
    """Get label statistics for a project."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get label stats request",
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

        # Labeled pages (labels is not null and not empty)
        labeled_query = select(func.count()).select_from(CrawledPage).where(
            CrawledPage.project_id == project_id,
            CrawledPage.labels.isnot(None),
            CrawledPage.labels != [],
        )
        labeled_result = await session.execute(labeled_query)
        labeled_pages = labeled_result.scalar() or 0

        # Get all labels and count them
        # First, fetch all pages with labels
        labels_query = select(CrawledPage.labels).where(
            CrawledPage.project_id == project_id,
            CrawledPage.labels.isnot(None),
            CrawledPage.labels != [],
        )
        labels_result = await session.execute(labels_query)
        all_labels_lists = [row[0] for row in labels_result.fetchall()]

        # Flatten and count labels
        label_counter: Counter[str] = Counter()
        for labels_list in all_labels_lists:
            if labels_list:
                label_counter.update(labels_list)

        label_counts = dict(label_counter)
        top_labels = [label for label, _ in label_counter.most_common(10)]

        logger.debug(
            "Label stats retrieved",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_pages": total_pages,
                "labeled_pages": labeled_pages,
                "unique_labels": len(label_counts),
            },
        )

        return LabelStatsResponse(
            project_id=project_id,
            total_pages=total_pages,
            labeled_pages=labeled_pages,
            unlabeled_pages=total_pages - labeled_pages,
            label_counts=label_counts,
            top_labels=top_labels,
        )

    except Exception as e:
        logger.error(
            "Failed to get label stats",
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
