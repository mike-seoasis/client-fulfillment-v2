"""PAA Enrichment phase API endpoints for projects.

Provides PAA (People Also Ask) enrichment operations for a project:
- POST /api/v1/projects/{project_id}/phases/paa_enrichment/enrich - Enrich single keyword
- POST /api/v1/projects/{project_id}/phases/paa_enrichment/batch - Enrich multiple keywords
- GET /api/v1/projects/{project_id}/phases/paa_enrichment/stats - Get statistics

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
from app.schemas.paa_enrichment import (
    PAAEnrichmentBatchItemResponse,
    PAAEnrichmentBatchRequest,
    PAAEnrichmentBatchResponse,
    PAAEnrichmentRequest,
    PAAEnrichmentResponse,
    PAAEnrichmentStatsResponse,
    PAAQuestionResponse,
)
from app.services.paa_enrichment import (
    PAAEnrichmentResult,
    PAAValidationError,
    enrich_keyword_paa,
    enrich_keyword_paa_cached,
    get_paa_enrichment_service,
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
    result: PAAEnrichmentResult,
    from_cache: bool = False,
) -> PAAEnrichmentResponse:
    """Convert service result to API response schema."""
    questions = [
        PAAQuestionResponse(
            question=q.question,
            answer_snippet=q.answer_snippet,
            source_url=q.source_url,
            source_domain=q.source_domain,
            position=q.position,
            is_nested=q.is_nested,
            parent_question=q.parent_question,
            intent=q.intent.value,
        )
        for q in result.questions
    ]

    return PAAEnrichmentResponse(
        success=result.success,
        keyword=result.keyword,
        questions=questions,
        initial_count=result.initial_count,
        nested_count=result.nested_count,
        related_search_count=result.related_search_count,
        total_count=result.total_count,
        used_fallback=result.used_fallback,
        from_cache=from_cache,
        error=result.error,
        cost=result.cost,
        duration_ms=round(result.duration_ms, 2),
    )


@router.post(
    "/enrich",
    response_model=PAAEnrichmentResponse,
    summary="Enrich keyword with PAA questions",
    description="Discover PAA (People Also Ask) questions for a keyword using fan-out strategy.",
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
async def enrich_keyword(
    request: Request,
    project_id: str,
    data: PAAEnrichmentRequest,
    session: AsyncSession = Depends(get_session),
) -> PAAEnrichmentResponse | JSONResponse:
    """Enrich a keyword with PAA questions.

    Uses DataForSEO SERP API with optional fan-out strategy:
    1. Fetch initial PAA questions for the keyword
    2. Optionally search each initial question for nested questions (fan-out)
    3. Fall back to Related Searches if insufficient PAA results
    4. Optionally categorize questions by intent

    Results are cached in Redis with 24h TTL when use_cache=True.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "PAA enrichment request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "keyword": data.keyword[:50],
            "location_code": data.location_code,
            "language_code": data.language_code,
            "fanout_enabled": data.fanout_enabled,
            "max_fanout_questions": data.max_fanout_questions,
            "fallback_enabled": data.fallback_enabled,
            "categorize_enabled": data.categorize_enabled,
            "use_cache": data.use_cache,
            "page_id": data.page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        # Use cached or direct function based on use_cache flag
        if data.use_cache:
            result = await enrich_keyword_paa_cached(
                keyword=data.keyword,
                location_code=data.location_code,
                language_code=data.language_code,
                fanout_enabled=data.fanout_enabled,
                max_fanout_questions=data.max_fanout_questions,
                fallback_enabled=data.fallback_enabled,
                min_paa_for_fallback=data.min_paa_for_fallback,
                categorize_enabled=data.categorize_enabled,
                project_id=project_id,
                page_id=data.page_id,
            )
            # Note: cached results are detected by checking duration
            # (cached results have much shorter duration)
            from_cache = result.duration_ms < 100 and result.success
        else:
            result = await enrich_keyword_paa(
                keyword=data.keyword,
                location_code=data.location_code,
                language_code=data.language_code,
                fanout_enabled=data.fanout_enabled,
                max_fanout_questions=data.max_fanout_questions,
                fallback_enabled=data.fallback_enabled,
                min_paa_for_fallback=data.min_paa_for_fallback,
                categorize_enabled=data.categorize_enabled,
                project_id=project_id,
                page_id=data.page_id,
            )
            from_cache = False

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "PAA enrichment complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "keyword": data.keyword[:50],
                "success": result.success,
                "total_questions": result.total_count,
                "initial_count": result.initial_count,
                "nested_count": result.nested_count,
                "related_search_count": result.related_search_count,
                "used_fallback": result.used_fallback,
                "from_cache": from_cache,
                "cost": result.cost,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return _convert_result_to_response(result, from_cache=from_cache)

    except PAAValidationError as e:
        logger.warning(
            "PAA enrichment validation error",
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
            "PAA enrichment failed",
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
    response_model=PAAEnrichmentBatchResponse,
    summary="Batch enrich keywords with PAA questions",
    description="Enrich multiple keywords with PAA questions concurrently.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def enrich_keywords_batch(
    request: Request,
    project_id: str,
    data: PAAEnrichmentBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> PAAEnrichmentBatchResponse | JSONResponse:
    """Enrich multiple keywords with PAA questions.

    Uses rate-limited concurrent processing (max_concurrent parameter).
    Each keyword is enriched independently with the same settings.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "PAA batch enrichment request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "keyword_count": len(data.keywords),
            "location_code": data.location_code,
            "language_code": data.language_code,
            "fanout_enabled": data.fanout_enabled,
            "max_concurrent": data.max_concurrent,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_paa_enrichment_service()
        results = await service.enrich_keywords_batch(
            keywords=data.keywords,
            location_code=data.location_code,
            language_code=data.language_code,
            fanout_enabled=data.fanout_enabled,
            max_fanout_questions=data.max_fanout_questions,
            fallback_enabled=data.fallback_enabled,
            min_paa_for_fallback=data.min_paa_for_fallback,
            max_concurrent=data.max_concurrent,
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        # Build response items
        items: list[PAAEnrichmentBatchItemResponse] = []
        successful = 0
        failed = 0
        total_questions = 0

        for result in results:
            items.append(
                PAAEnrichmentBatchItemResponse(
                    keyword=result.keyword,
                    success=result.success,
                    question_count=result.total_count,
                    initial_count=result.initial_count,
                    nested_count=result.nested_count,
                    related_search_count=result.related_search_count,
                    used_fallback=result.used_fallback,
                    error=result.error,
                )
            )
            if result.success:
                successful += 1
                total_questions += result.total_count
            else:
                failed += 1

        logger.info(
            "PAA batch enrichment complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_keywords": len(data.keywords),
                "successful_keywords": successful,
                "failed_keywords": failed,
                "total_questions": total_questions,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return PAAEnrichmentBatchResponse(
            success=True,
            results=items,
            total_keywords=len(data.keywords),
            successful_keywords=successful,
            failed_keywords=failed,
            total_questions=total_questions,
            error=None,
            duration_ms=round(duration_ms, 2),
        )

    except PAAValidationError as e:
        logger.warning(
            "PAA batch enrichment validation error",
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
            "PAA batch enrichment failed",
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


@router.get(
    "/stats",
    response_model=PAAEnrichmentStatsResponse,
    summary="Get PAA enrichment statistics",
    description="Get statistics about PAA enrichment for a project.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def get_paa_enrichment_stats(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> PAAEnrichmentStatsResponse | JSONResponse:
    """Get PAA enrichment statistics for a project.

    Returns counts of keywords enriched, questions discovered,
    and breakdown by intent category.
    """
    request_id = _get_request_id(request)
    logger.debug(
        "Get PAA enrichment stats request",
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
        # TODO: Implement actual stats from database when PAA results are persisted
        # Currently returns placeholder values since PAA results are not yet stored
        # in the database. When PAA enrichment results are persisted to a table,
        # update this to query actual statistics.

        logger.debug(
            "PAA enrichment stats retrieved",
            extra={
                "request_id": request_id,
                "project_id": project_id,
            },
        )

        return PAAEnrichmentStatsResponse(
            project_id=project_id,
            total_keywords_enriched=0,
            total_questions_discovered=0,
            questions_by_intent={
                "buying": 0,
                "usage": 0,
                "care": 0,
                "comparison": 0,
                "unknown": 0,
            },
            cache_hit_rate=0.0,
        )

    except Exception as e:
        logger.error(
            "Failed to get PAA enrichment stats",
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
