"""Content Plan Builder phase API endpoints for projects.

Provides Phase 5A content plan building operations for a project:
- POST /api/v1/projects/{project_id}/phases/content_plan/build - Build content plan for keyword
- POST /api/v1/projects/{project_id}/phases/content_plan/batch - Build plans for multiple keywords

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
from app.schemas.content_plan import (
    BenefitItem,
    ContentPlanBatchItemResponse,
    ContentPlanBatchRequest,
    ContentPlanBatchResponse,
    ContentPlanRequest,
    ContentPlanResponse,
    PriorityQuestion,
)
from app.schemas.paa_analysis import ContentAngleResponse
from app.services.content_plan import (
    ContentPlanResult,
    ContentPlanValidationError,
    get_content_plan_service,
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
    result: ContentPlanResult,
) -> ContentPlanResponse:
    """Convert service result to API response schema."""
    # Convert main angle
    main_angle = None
    if result.main_angle:
        main_angle = ContentAngleResponse(
            primary_angle=result.main_angle.primary_angle,
            reasoning=result.main_angle.reasoning,
            focus_areas=result.main_angle.focus_areas,
        )

    # Convert benefits
    benefits = [
        BenefitItem(
            benefit=b.benefit,
            source=b.source,
            confidence=b.confidence,
        )
        for b in result.benefits
    ]

    # Convert priority questions
    priority_questions = [
        PriorityQuestion(
            question=q.question,
            intent=q.intent,
            priority_rank=q.priority_rank,
            answer_snippet=q.answer_snippet,
            source_url=q.source_url,
        )
        for q in result.priority_questions
    ]

    return ContentPlanResponse(
        success=result.success,
        keyword=result.keyword,
        main_angle=main_angle,
        benefits=benefits,
        priority_questions=priority_questions,
        intent_distribution=result.intent_distribution,
        total_questions_analyzed=result.total_questions_analyzed,
        perplexity_used=result.perplexity_used,
        perplexity_citations=result.perplexity_citations,
        error=result.error,
        partial_success=result.partial_success,
        duration_ms=round(result.duration_ms, 2),
    )


@router.post(
    "/build",
    response_model=ContentPlanResponse,
    summary="Build content plan for keyword",
    description="Build a Phase 5A content plan with main angle, benefits, and priority questions.",
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
async def build_content_plan(
    request: Request,
    project_id: str,
    data: ContentPlanRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentPlanResponse | JSONResponse:
    """Build a content plan for a keyword.

    Phase 5A content plan building:
    1. Enriches keyword with PAA questions (via DataForSEO)
    2. Categorizes questions by intent (via Claude)
    3. Analyzes to determine main angle and priority questions
    4. Optionally researches benefits via Perplexity
    5. Synthesizes into actionable content plan

    The content plan includes:
    - Main angle recommendation (purchase_decision, longevity_maintenance, practical_benefits, balanced)
    - Key benefits from web research
    - Priority questions to address in content
    - Intent distribution for reference
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Content plan build request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "keyword": data.keyword[:50],
            "location_code": data.location_code,
            "language_code": data.language_code,
            "include_perplexity_research": data.include_perplexity_research,
            "max_benefits": data.max_benefits,
            "max_priority_questions": data.max_priority_questions,
            "fanout_enabled": data.fanout_enabled,
            "use_cache": data.use_cache,
            "page_id": data.page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_content_plan_service()
        result = await service.build_content_plan(
            keyword=data.keyword,
            location_code=data.location_code,
            language_code=data.language_code,
            include_perplexity_research=data.include_perplexity_research,
            max_benefits=data.max_benefits,
            max_priority_questions=data.max_priority_questions,
            fanout_enabled=data.fanout_enabled,
            use_cache=data.use_cache,
            project_id=project_id,
            page_id=data.page_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Content plan build complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "keyword": data.keyword[:50],
                "success": result.success,
                "partial_success": result.partial_success,
                "main_angle": (
                    result.main_angle.primary_angle if result.main_angle else None
                ),
                "benefits_count": len(result.benefits),
                "questions_count": len(result.priority_questions),
                "perplexity_used": result.perplexity_used,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return _convert_result_to_response(result)

    except ContentPlanValidationError as e:
        logger.warning(
            "Content plan validation error",
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
            "Content plan build failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "keyword": data.keyword[:50],
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
    response_model=ContentPlanBatchResponse,
    summary="Batch build content plans",
    description="Build content plans for multiple keywords concurrently.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def build_content_plans_batch(
    request: Request,
    project_id: str,
    data: ContentPlanBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> ContentPlanBatchResponse | JSONResponse:
    """Build content plans for multiple keywords.

    Uses rate-limited concurrent processing (max_concurrent parameter).
    Each keyword gets its own content plan built independently.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Content plan batch request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "keyword_count": len(data.keywords),
            "location_code": data.location_code,
            "language_code": data.language_code,
            "include_perplexity_research": data.include_perplexity_research,
            "max_concurrent": data.max_concurrent,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_content_plan_service()
        results = await service.build_content_plans_batch(
            keywords=data.keywords,
            location_code=data.location_code,
            language_code=data.language_code,
            include_perplexity_research=data.include_perplexity_research,
            max_benefits=data.max_benefits,
            max_priority_questions=data.max_priority_questions,
            max_concurrent=data.max_concurrent,
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        # Build response items
        items: list[ContentPlanBatchItemResponse] = []
        successful = 0
        failed = 0

        for result in results:
            items.append(
                ContentPlanBatchItemResponse(
                    keyword=result.keyword,
                    success=result.success,
                    main_angle=(
                        result.main_angle.primary_angle if result.main_angle else None
                    ),
                    benefits_count=len(result.benefits),
                    questions_count=len(result.priority_questions),
                    error=result.error,
                )
            )
            if result.success:
                successful += 1
            else:
                failed += 1

        logger.info(
            "Content plan batch complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_keywords": len(data.keywords),
                "successful_keywords": successful,
                "failed_keywords": failed,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return ContentPlanBatchResponse(
            success=True,
            results=items,
            total_keywords=len(data.keywords),
            successful_keywords=successful,
            failed_keywords=failed,
            error=None,
            duration_ms=round(duration_ms, 2),
        )

    except ContentPlanValidationError as e:
        logger.warning(
            "Content plan batch validation error",
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
            "Content plan batch failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "keyword_count": len(data.keywords),
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
