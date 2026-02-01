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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.schemas.content_generation import (
    ContentGenerationBatchItemResponse,
    ContentGenerationBatchRequest,
    ContentGenerationBatchResponse,
    ContentGenerationRequest,
    ContentGenerationResponse,
    GeneratedContentOutput,
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
