"""Word Count phase API endpoints for projects.

Provides Phase 5C word count validation for a project:
- POST /api/v1/projects/{project_id}/phases/word_count/check - Check single content
- POST /api/v1/projects/{project_id}/phases/word_count/batch - Check multiple contents

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
from app.schemas.content_word_count import (
    ContentWordCountBatchItemResponse,
    ContentWordCountBatchRequest,
    ContentWordCountBatchResponse,
    ContentWordCountRequest,
    ContentWordCountResponse,
)
from app.services.content_word_count import (
    ContentWordCountInput,
    ContentWordCountValidationError,
    get_content_word_count_service,
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
    "/check",
    response_model=ContentWordCountResponse,
    summary="Check word count",
    description="Run Phase 5C word count validation on content (300-450 words required).",
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
                        "error": "Validation failed: content cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def check_word_count(
    request: Request,
    project_id: str,
    data: ContentWordCountRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentWordCountResponse | JSONResponse:
    """Check word count of content.

    Phase 5C word count validation:
    1. Strips HTML tags from content
    2. Counts words
    3. Validates against 300-450 word requirement
    4. Provides suggestion if word count is invalid

    Content with 300-450 words passes validation.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Word count check request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "field_name": data.field_name,
            "content_length": len(data.content),
            "page_id": data.page_id,
            "content_id": data.content_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_content_word_count_service()
        input_data = ContentWordCountInput(
            content=data.content,
            field_name=data.field_name,
            project_id=project_id,
            page_id=data.page_id,
            content_id=data.content_id,
        )
        result = await service.check_word_count(input_data)

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Word count check complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "content_id": data.content_id,
                "success": result.success,
                "word_count": result.word_count,
                "is_valid": result.is_valid,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return ContentWordCountResponse(
            success=result.success,
            content_id=result.content_id,
            field_name=result.field_name,
            word_count=result.word_count,
            min_required=result.min_required,
            max_allowed=result.max_allowed,
            is_valid=result.is_valid,
            error=result.error,
            suggestion=result.suggestion,
            duration_ms=round(duration_ms, 2),
        )

    except ContentWordCountValidationError as e:
        logger.warning(
            "Word count validation error",
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
            "Word count check failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "content_id": data.content_id,
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
    response_model=ContentWordCountBatchResponse,
    summary="Batch check word count",
    description="Check word count for multiple content items.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def check_word_count_batch(
    request: Request,
    project_id: str,
    data: ContentWordCountBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentWordCountBatchResponse | JSONResponse:
    """Check word count for multiple content items.

    Runs Phase 5C word count checks on each item.
    Returns aggregate statistics and individual results.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Word count batch request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "item_count": len(data.items),
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_content_word_count_service()

        # Convert batch items to input data
        inputs: list[ContentWordCountInput] = []
        for item in data.items:
            inputs.append(
                ContentWordCountInput(
                    content=item.content,
                    field_name=item.field_name,
                    project_id=project_id,
                    page_id=item.page_id,
                    content_id=item.content_id,
                )
            )

        results = await service.check_word_count_batch(
            inputs=inputs,
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        # Build response items and calculate stats
        items: list[ContentWordCountBatchItemResponse] = []
        valid_count = 0
        invalid_count = 0
        error_count = 0
        total_word_count = 0
        word_count_items = 0

        for result in results:
            items.append(
                ContentWordCountBatchItemResponse(
                    content_id=result.content_id,
                    page_id=result.page_id,
                    success=result.success,
                    word_count=result.word_count,
                    is_valid=result.is_valid,
                    error=result.error,
                )
            )

            if not result.success:
                error_count += 1
            elif result.is_valid:
                valid_count += 1
                total_word_count += result.word_count
                word_count_items += 1
            else:
                invalid_count += 1
                total_word_count += result.word_count
                word_count_items += 1

        average_word_count = (
            round(total_word_count / word_count_items, 1) if word_count_items > 0 else 0.0
        )

        logger.info(
            "Word count batch complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_items": len(data.items),
                "valid_count": valid_count,
                "invalid_count": invalid_count,
                "error_count": error_count,
                "average_word_count": average_word_count,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return ContentWordCountBatchResponse(
            success=True,
            results=items,
            total_items=len(data.items),
            valid_count=valid_count,
            invalid_count=invalid_count,
            error_count=error_count,
            average_word_count=average_word_count,
            error=None,
            duration_ms=round(duration_ms, 2),
        )

    except ContentWordCountValidationError as e:
        logger.warning(
            "Word count batch validation error",
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
            "Word count batch failed",
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
