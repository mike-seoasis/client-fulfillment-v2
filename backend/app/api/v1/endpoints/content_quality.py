"""Content Quality phase API endpoints for projects.

Provides Phase 5C AI trope detection and quality scoring for a project:
- POST /api/v1/projects/{project_id}/phases/content_quality/check - Check single content
- POST /api/v1/projects/{project_id}/phases/content_quality/batch - Check multiple contents

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
from app.schemas.content_quality import (
    ContentQualityBatchItemResponse,
    ContentQualityBatchRequest,
    ContentQualityBatchResponse,
    ContentQualityRequest,
    ContentQualityResponse,
    PatternMatchItem,
    PhraseMatchItem,
    TropeDetectionItem,
    WordMatchItem,
)
from app.services.content_quality import (
    ContentQualityInput,
    ContentQualityResult,
    ContentQualityValidationError,
    get_content_quality_service,
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
    result: ContentQualityResult,
) -> ContentQualityResponse:
    """Convert service result to API response schema."""
    trope_detection = None
    if result.trope_detection:
        td = result.trope_detection
        trope_detection = TropeDetectionItem(
            found_banned_words=[
                WordMatchItem(
                    word=w.word,
                    count=w.count,
                    positions=w.positions,
                )
                for w in td.found_banned_words
            ],
            found_banned_phrases=[
                PhraseMatchItem(
                    phrase=p.phrase,
                    count=p.count,
                    positions=p.positions,
                )
                for p in td.found_banned_phrases
            ],
            found_em_dashes=td.found_em_dashes,
            found_triplet_patterns=[
                PatternMatchItem(
                    pattern_type=p.pattern_type,
                    matched_text=p.matched_text,
                    position=p.position,
                )
                for p in td.found_triplet_patterns
            ],
            found_negation_patterns=[
                PatternMatchItem(
                    pattern_type=p.pattern_type,
                    matched_text=p.matched_text,
                    position=p.position,
                )
                for p in td.found_negation_patterns
            ],
            found_rhetorical_questions=td.found_rhetorical_questions,
            limited_use_words=td.limited_use_words,
            overall_score=round(td.overall_score, 2),
            is_approved=td.is_approved,
            suggestions=td.suggestions,
        )

    return ContentQualityResponse(
        success=result.success,
        content_id=result.content_id,
        trope_detection=trope_detection,
        passed_qa=result.passed_qa,
        error=result.error,
        duration_ms=round(result.duration_ms, 2),
    )


def _convert_request_to_input(
    data: ContentQualityRequest,
    project_id: str,
) -> ContentQualityInput:
    """Convert API request to service input."""
    return ContentQualityInput(
        h1=data.h1,
        title_tag=data.title_tag,
        meta_description=data.meta_description,
        top_description=data.top_description,
        bottom_description=data.bottom_description,
        project_id=project_id,
        page_id=data.page_id,
        content_id=data.content_id,
    )


@router.post(
    "/check",
    response_model=ContentQualityResponse,
    summary="Check content quality",
    description="Run Phase 5C AI trope detection and quality scoring on generated content.",
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
                        "error": "Validation failed: bottom_description cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def check_content_quality(
    request: Request,
    project_id: str,
    data: ContentQualityRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentQualityResponse | JSONResponse:
    """Check quality of generated content.

    Phase 5C AI trope detection:
    1. Detects banned words (delve, unlock, journey, etc.)
    2. Detects banned phrases ("In today's fast-paced world", etc.)
    3. Counts em dashes (should be zero)
    4. Detects triplet patterns ("Fast. Simple. Powerful.")
    5. Detects negation patterns ("aren't just X, they're Y")
    6. Counts rhetorical question openers
    7. Tracks limited-use word frequency (max 1 per page)
    8. Calculates overall quality score (0-100)
    9. Generates actionable improvement suggestions

    Content with score >= 80 passes QA.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Content quality check request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "h1_length": len(data.h1),
            "title_tag_length": len(data.title_tag),
            "meta_description_length": len(data.meta_description),
            "bottom_description_length": len(data.bottom_description),
            "page_id": data.page_id,
            "content_id": data.content_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_content_quality_service()
        input_data = _convert_request_to_input(data, project_id)
        result = await service.check_content_quality(input_data)

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Content quality check complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "content_id": data.content_id,
                "success": result.success,
                "quality_score": result.trope_detection.overall_score if result.trope_detection else None,
                "passed_qa": result.passed_qa,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return _convert_result_to_response(result)

    except ContentQualityValidationError as e:
        logger.warning(
            "Content quality validation error",
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
            "Content quality check failed",
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
    response_model=ContentQualityBatchResponse,
    summary="Batch check content quality",
    description="Check quality for multiple content items.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def check_content_quality_batch(
    request: Request,
    project_id: str,
    data: ContentQualityBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentQualityBatchResponse | JSONResponse:
    """Check quality for multiple content items.

    Runs Phase 5C quality checks on each item.
    Returns aggregate statistics and individual results.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Content quality batch request",
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
        service = get_content_quality_service()

        # Convert batch items to input data
        inputs: list[ContentQualityInput] = []
        for item in data.items:
            inputs.append(
                ContentQualityInput(
                    h1=item.h1,
                    title_tag=item.title_tag,
                    meta_description=item.meta_description,
                    top_description=item.top_description,
                    bottom_description=item.bottom_description,
                    project_id=project_id,
                    page_id=item.page_id,
                    content_id=item.content_id,
                )
            )

        results = await service.check_content_quality_batch(
            inputs=inputs,
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        # Build response items and calculate stats
        items: list[ContentQualityBatchItemResponse] = []
        passed_qa_count = 0
        failed_qa_count = 0
        error_count = 0
        total_score = 0.0
        score_count = 0

        for result in results:
            issue_count = 0
            quality_score = None

            if result.trope_detection:
                td = result.trope_detection
                issue_count = (
                    sum(w.count for w in td.found_banned_words)
                    + sum(p.count for p in td.found_banned_phrases)
                    + td.found_em_dashes
                    + len(td.found_triplet_patterns)
                    + len(td.found_negation_patterns)
                    + td.found_rhetorical_questions
                )
                quality_score = td.overall_score
                total_score += quality_score
                score_count += 1

            items.append(
                ContentQualityBatchItemResponse(
                    content_id=result.content_id,
                    page_id=result.page_id,
                    success=result.success,
                    quality_score=round(quality_score, 2) if quality_score is not None else None,
                    passed_qa=result.passed_qa,
                    issue_count=issue_count,
                    error=result.error,
                )
            )

            if not result.success:
                error_count += 1
            elif result.passed_qa:
                passed_qa_count += 1
            else:
                failed_qa_count += 1

        average_score = round(total_score / score_count, 2) if score_count > 0 else 0.0

        logger.info(
            "Content quality batch complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_items": len(data.items),
                "passed_qa_count": passed_qa_count,
                "failed_qa_count": failed_qa_count,
                "error_count": error_count,
                "average_score": average_score,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return ContentQualityBatchResponse(
            success=True,
            results=items,
            total_items=len(data.items),
            passed_qa_count=passed_qa_count,
            failed_qa_count=failed_qa_count,
            error_count=error_count,
            average_score=average_score,
            error=None,
            duration_ms=round(duration_ms, 2),
        )

    except ContentQualityValidationError as e:
        logger.warning(
            "Content quality batch validation error",
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
            "Content quality batch failed",
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
