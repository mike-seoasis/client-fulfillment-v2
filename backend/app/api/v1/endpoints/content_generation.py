"""Content Generation phase API endpoints for projects.

Provides content generation operations for a project:
- POST /api/v1/projects/{project_id}/phases/content_generation/generate - Generate content for page
- POST /api/v1/projects/{project_id}/phases/content_generation/batch - Generate content for multiple pages

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
from app.models.crawled_page import CrawledPage
from app.models.page_keywords import PageKeywords
from app.schemas.content_generation import (
    ContentGenerationBatchItemResponse,
    ContentGenerationBatchRequest,
    ContentGenerationBatchResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    GeneratedContentOutput,
    RegenerateBatchItemResponse,
    RegenerateBatchRequest,
    RegenerateBatchResponse,
    RegenerateRequest,
    RegenerateResponse,
)
from app.services.content_generation import (
    ContentGenerationInput,
    ContentGenerationResult,
    ContentGenerationValidationError,
    get_content_generation_service,
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


def _convert_result_to_response(
    result: ContentGenerationResult,
    request_id: str,
) -> ContentGenerationResponse:
    """Convert service result to API response schema."""
    content = None
    if result.content:
        content = GeneratedContentOutput(
            h1=result.content.h1,
            title_tag=result.content.title_tag,
            meta_description=result.content.meta_description,
            body_content=result.content.body_content,
            word_count=result.content.word_count,
        )

    return ContentGenerationResponse(
        success=result.success,
        keyword=result.keyword,
        content_type=result.content_type,
        content=content,
        error=result.error,
        duration_ms=round(result.duration_ms, 2),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        request_id=request_id,
    )


def _convert_request_to_input(
    data: ContentGenerationRequest,
    project_id: str,
) -> ContentGenerationInput:
    """Convert API request to service input."""
    return ContentGenerationInput(
        keyword=data.keyword,
        url=data.url,
        brand_name=data.brand_name,
        content_type=data.content_type,
        tone=data.tone,
        target_word_count=data.target_word_count,
        context=data.context,
        project_id=project_id,
        page_id=data.page_id,
    )


@router.post(
    "/generate",
    response_model=ContentGenerationResponse,
    summary="Generate content for page",
    description="Generate SEO-optimized content for a page.",
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
                        "error": "Validation failed: keyword cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def generate_content(
    request: Request,
    project_id: str,
    data: ContentGenerationRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentGenerationResponse | JSONResponse:
    """Generate content for a single page.

    Content generation process:
    1. Validates inputs and project exists
    2. Builds prompt with content type-specific instructions
    3. Includes optional context (research brief, brand voice)
    4. Generates SEO-optimized content via LLM
    5. Returns structured content: H1, title tag, meta description, body

    Supported content types:
    - collection: Product collection pages
    - product: Individual product pages
    - blog: Blog post content
    - landing: Landing page content
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Content generation request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "keyword": data.keyword[:50],
            "url": data.url[:100],
            "brand_name": data.brand_name[:50],
            "content_type": data.content_type,
            "tone": data.tone,
            "target_word_count": data.target_word_count,
            "has_context": data.context is not None,
            "page_id": data.page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_content_generation_service()
        input_data = _convert_request_to_input(data, project_id)
        result = await service.generate_content(input_data)

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Content generation complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "keyword": data.keyword[:50],
                "content_type": data.content_type,
                "success": result.success,
                "h1": result.content.h1[:50] if result.content else None,
                "word_count": result.content.word_count if result.content else None,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return _convert_result_to_response(result, request_id)

    except ContentGenerationValidationError as e:
        logger.warning(
            "Content generation validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "field": e.field_name,
                "value": str(e.value)[:100],
                "message": str(e),
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
            "Content generation failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "keyword": data.keyword[:50],
                "content_type": data.content_type,
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
    response_model=ContentGenerationBatchResponse,
    summary="Batch generate content",
    description="Generate content for multiple pages concurrently.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def generate_content_batch(
    request: Request,
    project_id: str,
    data: ContentGenerationBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentGenerationBatchResponse | JSONResponse:
    """Generate content for multiple pages.

    Uses rate-limited concurrent processing (max_concurrent parameter).
    Each page gets its content generated independently with shared
    brand name and tone settings.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Content generation batch request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "item_count": len(data.items),
            "brand_name": data.brand_name[:50],
            "tone": data.tone,
            "max_concurrent": data.max_concurrent,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_content_generation_service()

        # Convert batch items to input data
        inputs: list[ContentGenerationInput] = []
        for item in data.items:
            inputs.append(
                ContentGenerationInput(
                    keyword=item.keyword,
                    url=item.url,
                    brand_name=data.brand_name,
                    content_type=item.content_type,
                    tone=data.tone,
                    target_word_count=item.target_word_count,
                    context=item.context,
                    project_id=project_id,
                    page_id=item.page_id,
                )
            )

        results = await service.generate_content_batch(
            inputs=inputs,
            max_concurrent=data.max_concurrent,
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        # Build response items
        items: list[ContentGenerationBatchItemResponse] = []
        successful = 0
        failed = 0

        for result in results:
            items.append(
                ContentGenerationBatchItemResponse(
                    keyword=result.keyword,
                    url=next(
                        (inp.url for inp in inputs if inp.keyword == result.keyword),
                        "",
                    ),
                    content_type=result.content_type,
                    success=result.success,
                    h1=result.content.h1 if result.content else None,
                    word_count=result.content.word_count if result.content else None,
                    error=result.error,
                )
            )
            if result.success:
                successful += 1
            else:
                failed += 1

        logger.info(
            "Content generation batch complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_items": len(data.items),
                "successful_items": successful,
                "failed_items": failed,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return ContentGenerationBatchResponse(
            success=True,
            results=items,
            total_items=len(data.items),
            successful_items=successful,
            failed_items=failed,
            error=None,
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
        )

    except ContentGenerationValidationError as e:
        logger.warning(
            "Content generation batch validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "field": e.field_name,
                "value": str(e.value)[:100],
                "message": str(e),
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
            "Content generation batch failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "item_count": len(data.items),
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


async def _get_page_data(
    page_id: str,
    project_id: str,
    session: AsyncSession,
    request_id: str,
) -> tuple[CrawledPage | None, PageKeywords | None, JSONResponse | None]:
    """Get page and keyword data for regeneration.

    Returns (page, keywords, error_response). If error_response is not None,
    return it instead of proceeding.
    """
    # Get the crawled page
    result = await session.execute(
        select(CrawledPage).where(
            CrawledPage.id == page_id,
            CrawledPage.project_id == project_id,
        )
    )
    page = result.scalar_one_or_none()

    if not page:
        logger.warning(
            "Page not found for regeneration",
            extra={
                "request_id": request_id,
                "page_id": page_id,
                "project_id": project_id,
            },
        )
        return (
            None,
            None,
            JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Page not found: {page_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            ),
        )

    # Get the keywords for this page
    keywords_result = await session.execute(
        select(PageKeywords).where(PageKeywords.crawled_page_id == page_id)
    )
    keywords = keywords_result.scalar_one_or_none()

    if not keywords:
        logger.warning(
            "Keywords not found for page regeneration",
            extra={
                "request_id": request_id,
                "page_id": page_id,
                "project_id": project_id,
            },
        )
        return (
            page,
            None,
            JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": f"Keywords not found for page: {page_id}",
                    "code": "NOT_FOUND",
                    "request_id": request_id,
                },
            ),
        )

    return page, keywords, None


@router.post(
    "/regenerate",
    response_model=RegenerateResponse,
    summary="Regenerate content for failed page",
    description="Regenerate SEO-optimized content for a page that previously failed.",
    responses={
        404: {
            "description": "Project or page not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Page not found: <uuid>",
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
                        "error": "Validation failed: page_id cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def regenerate_content(
    request: Request,
    project_id: str,
    data: RegenerateRequest,
    session: AsyncSession = Depends(get_session),
) -> RegenerateResponse | JSONResponse:
    """Regenerate content for a single failed page.

    Regeneration process:
    1. Validates project and page exist
    2. Retrieves page URL and keyword data
    3. Rebuilds content generation input
    4. Generates new SEO-optimized content via LLM
    5. Returns structured content: H1, title tag, meta description, body
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Content regeneration request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "page_id": data.page_id,
            "brand_name": data.brand_name[:50],
            "tone": data.tone,
            "target_word_count": data.target_word_count,
            "has_context": data.context is not None,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    # Get page and keyword data
    page, keywords, error = await _get_page_data(
        data.page_id, project_id, session, request_id
    )
    if error:
        return error

    # Type assertions - error check above guarantees these are not None
    assert page is not None
    assert keywords is not None

    try:
        service = get_content_generation_service()

        # Build input from page data
        input_data = ContentGenerationInput(
            keyword=keywords.primary_keyword,
            url=page.normalized_url,
            brand_name=data.brand_name,
            content_type=page.category or "collection",
            tone=data.tone,
            target_word_count=data.target_word_count,
            context=data.context,
            project_id=project_id,
            page_id=data.page_id,
        )

        result = await service.generate_content(input_data)

        duration_ms = (time.monotonic() - start_time) * 1000

        content = None
        if result.content:
            content = GeneratedContentOutput(
                h1=result.content.h1,
                title_tag=result.content.title_tag,
                meta_description=result.content.meta_description,
                body_content=result.content.body_content,
                word_count=result.content.word_count,
            )

        logger.info(
            "Content regeneration complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": data.page_id,
                "keyword": keywords.primary_keyword[:50],
                "content_type": page.category,
                "success": result.success,
                "h1": result.content.h1[:50] if result.content else None,
                "word_count": result.content.word_count if result.content else None,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return RegenerateResponse(
            success=result.success,
            page_id=data.page_id,
            keyword=keywords.primary_keyword,
            content_type=page.category,
            content=content,
            error=result.error,
            duration_ms=round(duration_ms, 2),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            request_id=request_id,
        )

    except ContentGenerationValidationError as e:
        logger.warning(
            "Content regeneration validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": data.page_id,
                "field": e.field_name,
                "value": str(e.value)[:100],
                "message": str(e),
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
            "Content regeneration failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "page_id": data.page_id,
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
    "/regenerate_batch",
    response_model=RegenerateBatchResponse,
    summary="Batch regenerate content for failed pages",
    description="Regenerate content for multiple failed pages concurrently.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def regenerate_content_batch(
    request: Request,
    project_id: str,
    data: RegenerateBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> RegenerateBatchResponse | JSONResponse:
    """Regenerate content for multiple failed pages.

    Uses rate-limited concurrent processing (max_concurrent parameter).
    Each page gets its content regenerated independently with shared
    brand name and tone settings.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Content regeneration batch request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "item_count": len(data.items),
            "brand_name": data.brand_name[:50],
            "tone": data.tone,
            "max_concurrent": data.max_concurrent,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        # Collect page IDs and fetch all data in bulk
        page_ids = [item.page_id for item in data.items]

        # Get all pages
        pages_result = await session.execute(
            select(CrawledPage).where(
                CrawledPage.id.in_(page_ids),
                CrawledPage.project_id == project_id,
            )
        )
        pages = {page.id: page for page in pages_result.scalars().all()}

        # Get all keywords
        keywords_result = await session.execute(
            select(PageKeywords).where(PageKeywords.crawled_page_id.in_(page_ids))
        )
        keywords_map = {
            kw.crawled_page_id: kw for kw in keywords_result.scalars().all()
        }

        # Build inputs and track missing items
        service = get_content_generation_service()
        inputs: list[ContentGenerationInput] = []
        item_contexts: dict[str, dict[str, str | None]] = {}  # page_id -> context
        results: list[RegenerateBatchItemResponse] = []

        for item in data.items:
            page = pages.get(item.page_id)
            keywords = keywords_map.get(item.page_id)

            if not page:
                logger.warning(
                    "Page not found in batch regeneration",
                    extra={
                        "request_id": request_id,
                        "page_id": item.page_id,
                        "project_id": project_id,
                    },
                )
                results.append(
                    RegenerateBatchItemResponse(
                        page_id=item.page_id,
                        keyword=None,
                        url=None,
                        content_type=None,
                        success=False,
                        h1=None,
                        word_count=None,
                        error=f"Page not found: {item.page_id}",
                    )
                )
                continue

            if not keywords:
                logger.warning(
                    "Keywords not found in batch regeneration",
                    extra={
                        "request_id": request_id,
                        "page_id": item.page_id,
                        "project_id": project_id,
                    },
                )
                results.append(
                    RegenerateBatchItemResponse(
                        page_id=item.page_id,
                        keyword=None,
                        url=page.normalized_url,
                        content_type=page.category,
                        success=False,
                        h1=None,
                        word_count=None,
                        error=f"Keywords not found for page: {item.page_id}",
                    )
                )
                continue

            # Store context for matching results later
            item_contexts[item.page_id] = {
                "keyword": keywords.primary_keyword,
                "url": page.normalized_url,
                "content_type": page.category,
            }

            inputs.append(
                ContentGenerationInput(
                    keyword=keywords.primary_keyword,
                    url=page.normalized_url,
                    brand_name=data.brand_name,
                    content_type=page.category or "collection",
                    tone=data.tone,
                    target_word_count=item.target_word_count,
                    context=item.context,
                    project_id=project_id,
                    page_id=item.page_id,
                )
            )

        # Generate content for valid items
        if inputs:
            generation_results = await service.generate_content_batch(
                inputs=inputs,
                max_concurrent=data.max_concurrent,
                project_id=project_id,
            )

            # Match results back to page IDs
            for gen_result in generation_results:
                page_id = gen_result.page_id or ""
                ctx = item_contexts.get(page_id, {})

                results.append(
                    RegenerateBatchItemResponse(
                        page_id=page_id,
                        keyword=ctx.get("keyword"),
                        url=ctx.get("url"),
                        content_type=ctx.get("content_type"),
                        success=gen_result.success,
                        h1=gen_result.content.h1 if gen_result.content else None,
                        word_count=(
                            gen_result.content.word_count
                            if gen_result.content
                            else None
                        ),
                        error=gen_result.error,
                    )
                )

        duration_ms = (time.monotonic() - start_time) * 1000
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        logger.info(
            "Content regeneration batch complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_items": len(data.items),
                "successful_items": successful,
                "failed_items": failed,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return RegenerateBatchResponse(
            success=True,
            results=results,
            total_items=len(data.items),
            successful_items=successful,
            failed_items=failed,
            error=None,
            duration_ms=round(duration_ms, 2),
            request_id=request_id,
        )

    except ContentGenerationValidationError as e:
        logger.warning(
            "Content regeneration batch validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "field": e.field_name,
                "value": str(e.value)[:100],
                "message": str(e),
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
            "Content regeneration batch failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "item_count": len(data.items),
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
