"""Keyword Research phase API endpoints for projects.

Provides keyword research operations for a project:
- POST /api/v1/projects/{project_id}/phases/keyword_research/ideas - Generate keyword ideas
- POST /api/v1/projects/{project_id}/phases/keyword_research/volumes - Look up keyword volumes
- POST /api/v1/projects/{project_id}/phases/keyword_research/specificity - Filter by specificity
- POST /api/v1/projects/{project_id}/phases/keyword_research/primary - Select primary keyword
- POST /api/v1/projects/{project_id}/phases/keyword_research/secondary - Select secondary keywords
- POST /api/v1/projects/{project_id}/phases/keyword_research/full - Run full pipeline
- GET /api/v1/projects/{project_id}/phases/keyword_research/stats - Get statistics

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
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.crawled_page import CrawledPage
from app.schemas.keyword_research import (
    KeywordIdeaRequest,
    KeywordIdeaResponse,
    KeywordResearchFullRequest,
    KeywordResearchFullResponse,
    KeywordResearchStatsResponse,
    KeywordSpecificityRequest,
    KeywordSpecificityResponse,
    KeywordVolumeDataResponse,
    KeywordVolumeRequest,
    KeywordVolumeResponse,
    KeywordWithVolume,
    PrimaryKeywordRequest,
    PrimaryKeywordResponse,
    SecondaryKeywordRequest,
    SecondaryKeywordResponse,
    VolumeStatsResponse,
)
from app.services.keyword_ideas import (
    KeywordIdeaValidationError,
    get_keyword_idea_service,
)
from app.services.keyword_specificity import (
    KeywordSpecificityValidationError,
    get_keyword_specificity_service,
)
from app.services.keyword_volume import (
    KeywordVolumeData,
    KeywordVolumeValidationError,
    get_keyword_volume_service,
)
from app.services.primary_keyword import (
    PrimaryKeywordValidationError,
    get_primary_keyword_service,
)
from app.services.project import ProjectNotFoundError, ProjectService
from app.services.secondary_keywords import (
    SecondaryKeywordValidationError,
    get_secondary_keyword_service,
)

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


def _convert_to_keyword_volume_data(kw: KeywordWithVolume) -> KeywordVolumeData:
    """Convert KeywordWithVolume schema to KeywordVolumeData service object."""
    return KeywordVolumeData(
        keyword=kw.keyword,
        volume=kw.volume,
        cpc=kw.cpc,
        competition=kw.competition,
        from_cache=False,
    )


def _convert_to_keyword_with_volume(kw: KeywordVolumeData) -> KeywordWithVolume:
    """Convert KeywordVolumeData service object to KeywordWithVolume schema."""
    return KeywordWithVolume(
        keyword=kw.keyword,
        volume=kw.volume,
        cpc=kw.cpc,
        competition=kw.competition,
    )


@router.post(
    "/ideas",
    response_model=KeywordIdeaResponse,
    summary="Generate keyword ideas",
    description="Generate 20-30 keyword ideas for a collection using LLM.",
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
                        "error": "Validation failed: collection_title cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def generate_keyword_ideas(
    request: Request,
    project_id: str,
    data: KeywordIdeaRequest,
    session: AsyncSession = Depends(get_session),
) -> KeywordIdeaResponse | JSONResponse:
    """Generate keyword ideas for a collection page.

    Uses Claude LLM to generate 20-30 keyword ideas including
    long-tail variations, question keywords, and comparison keywords.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Generate keyword ideas request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "collection_title": data.collection_title[:100],
            "url": data.url[:200],
            "content_excerpt_length": len(data.content_excerpt),
            "page_id": data.page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = get_keyword_idea_service()
    try:
        result = await service.generate_ideas(
            collection_title=data.collection_title,
            url=data.url,
            content_excerpt=data.content_excerpt,
            project_id=project_id,
            page_id=data.page_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Keyword ideas generated",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "keyword_count": result.keyword_count,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return KeywordIdeaResponse(
            success=result.success,
            keywords=result.keywords,
            keyword_count=result.keyword_count,
            error=result.error,
            duration_ms=round(result.duration_ms, 2),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

    except KeywordIdeaValidationError as e:
        logger.warning(
            "Keyword idea validation error",
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
            "Failed to generate keyword ideas",
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


@router.post(
    "/volumes",
    response_model=KeywordVolumeResponse,
    summary="Look up keyword volumes",
    description="Look up search volumes for a list of keywords with caching.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def lookup_keyword_volumes(
    request: Request,
    project_id: str,
    data: KeywordVolumeRequest,
    session: AsyncSession = Depends(get_session),
) -> KeywordVolumeResponse | JSONResponse:
    """Look up search volumes for keywords.

    Uses cache-first approach with Redis caching (30-day TTL).
    Falls back to Keywords Everywhere API for cache misses.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Keyword volume lookup request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "keyword_count": len(data.keywords),
            "country": data.country,
            "data_source": data.data_source,
            "page_id": data.page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = get_keyword_volume_service()
    try:
        result = await service.lookup_volumes(
            keywords=data.keywords,
            country=data.country,
            data_source=data.data_source,
            project_id=project_id,
            page_id=data.page_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Keyword volumes looked up",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_keywords": result.stats.total_keywords,
                "cache_hits": result.stats.cache_hits,
                "cache_hit_rate": round(result.stats.cache_hit_rate, 3),
                "credits_used": result.credits_used,
                "duration_ms": round(duration_ms, 2),
            },
        )

        # Convert service objects to response schemas
        keywords_response = [
            KeywordVolumeDataResponse(
                keyword=kw.keyword,
                volume=kw.volume,
                cpc=kw.cpc,
                competition=kw.competition,
                trend=kw.trend,
                from_cache=kw.from_cache,
            )
            for kw in result.keywords
        ]

        stats_response = VolumeStatsResponse(
            total_keywords=result.stats.total_keywords,
            cache_hits=result.stats.cache_hits,
            cache_misses=result.stats.cache_misses,
            api_lookups=result.stats.api_lookups,
            api_errors=result.stats.api_errors,
            cache_hit_rate=round(result.stats.cache_hit_rate, 3),
        )

        return KeywordVolumeResponse(
            success=result.success,
            keywords=keywords_response,
            stats=stats_response,
            error=result.error,
            duration_ms=round(result.duration_ms, 2),
            credits_used=result.credits_used,
        )

    except KeywordVolumeValidationError as e:
        logger.warning(
            "Keyword volume validation error",
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
            "Failed to lookup keyword volumes",
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


@router.post(
    "/specificity",
    response_model=KeywordSpecificityResponse,
    summary="Filter keywords by specificity",
    description="Filter keywords to only those that SPECIFICALLY describe a collection.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def filter_keywords_by_specificity(
    request: Request,
    project_id: str,
    data: KeywordSpecificityRequest,
    session: AsyncSession = Depends(get_session),
) -> KeywordSpecificityResponse | JSONResponse:
    """Filter keywords to only SPECIFIC ones (vs generic/broad).

    Uses Claude LLM to determine which keywords specifically describe
    the collection's products vs. generic keywords that are too broad.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Keyword specificity filter request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "collection_title": data.collection_title[:100],
            "keyword_count": len(data.keywords),
            "page_id": data.page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = get_keyword_specificity_service()
    try:
        # Convert schema objects to service objects
        keywords = [_convert_to_keyword_volume_data(kw) for kw in data.keywords]

        result = await service.filter_keywords(
            collection_title=data.collection_title,
            url=data.url,
            content_excerpt=data.content_excerpt,
            keywords=keywords,
            project_id=project_id,
            page_id=data.page_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Keyword specificity filtering complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "original_count": result.original_count,
                "filtered_count": result.filtered_count,
                "filter_rate": result.filter_rate,
                "duration_ms": round(duration_ms, 2),
            },
        )

        # Convert service objects to response schemas
        specific_keywords = [
            _convert_to_keyword_with_volume(kw) for kw in result.specific_keywords
        ]

        return KeywordSpecificityResponse(
            success=result.success,
            specific_keywords=specific_keywords,
            filtered_count=result.filtered_count,
            original_count=result.original_count,
            filter_rate=result.filter_rate,
            error=result.error,
            duration_ms=round(result.duration_ms, 2),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )

    except KeywordSpecificityValidationError as e:
        logger.warning(
            "Keyword specificity validation error",
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
            "Failed to filter keywords by specificity",
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


@router.post(
    "/primary",
    response_model=PrimaryKeywordResponse,
    summary="Select primary keyword",
    description="Select the primary keyword (highest-volume specific keyword).",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def select_primary_keyword(
    request: Request,
    project_id: str,
    data: PrimaryKeywordRequest,
    session: AsyncSession = Depends(get_session),
) -> PrimaryKeywordResponse | JSONResponse:
    """Select the primary keyword from specific keywords.

    Chooses the highest-volume keyword from the SPECIFIC keywords list.
    Tie-breaker: prefers shorter keywords (more concise).
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Primary keyword selection request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "collection_title": data.collection_title[:100],
            "specific_keyword_count": len(data.specific_keywords),
            "used_primaries_count": len(data.used_primaries),
            "page_id": data.page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = get_primary_keyword_service()
    try:
        # Convert schema objects to service objects
        specific_keywords = [
            _convert_to_keyword_volume_data(kw) for kw in data.specific_keywords
        ]
        used_primaries = set(data.used_primaries) if data.used_primaries else set()

        result = await service.select_primary(
            collection_title=data.collection_title,
            specific_keywords=specific_keywords,
            used_primaries=used_primaries,
            project_id=project_id,
            page_id=data.page_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Primary keyword selected",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "primary_keyword": result.primary_keyword,
                "primary_volume": result.primary_volume,
                "candidate_count": result.candidate_count,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return PrimaryKeywordResponse(
            success=result.success,
            primary_keyword=result.primary_keyword,
            primary_volume=result.primary_volume,
            candidate_count=result.candidate_count,
            error=result.error,
            duration_ms=round(result.duration_ms, 2),
        )

    except PrimaryKeywordValidationError as e:
        logger.warning(
            "Primary keyword validation error",
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
            "Failed to select primary keyword",
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


@router.post(
    "/secondary",
    response_model=SecondaryKeywordResponse,
    summary="Select secondary keywords",
    description="Select 3-5 secondary keywords (mix of specific and broader terms).",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def select_secondary_keywords(
    request: Request,
    project_id: str,
    data: SecondaryKeywordRequest,
    session: AsyncSession = Depends(get_session),
) -> SecondaryKeywordResponse | JSONResponse:
    """Select secondary keywords from specific and broader terms.

    Selects 3-5 keywords as a mix of:
    - 2-3 specific keywords (lower volume than primary)
    - 1-2 broader terms with volume > 1000
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Secondary keyword selection request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "collection_title": data.collection_title[:100],
            "primary_keyword": data.primary_keyword,
            "specific_keyword_count": len(data.specific_keywords),
            "all_keyword_count": len(data.all_keywords),
            "used_primaries_count": len(data.used_primaries),
            "page_id": data.page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    service = get_secondary_keyword_service()
    try:
        # Convert schema objects to service objects
        specific_keywords = [
            _convert_to_keyword_volume_data(kw) for kw in data.specific_keywords
        ]
        all_keywords = [
            _convert_to_keyword_volume_data(kw) for kw in data.all_keywords
        ]
        used_primaries = set(data.used_primaries) if data.used_primaries else set()

        result = await service.select_secondary(
            collection_title=data.collection_title,
            primary_keyword=data.primary_keyword,
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            used_primaries=used_primaries,
            project_id=project_id,
            page_id=data.page_id,
            min_specific=data.min_specific,
            max_specific=data.max_specific,
            min_broader=data.min_broader,
            max_broader=data.max_broader,
            broader_volume_threshold=data.broader_volume_threshold,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Secondary keywords selected",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_count": result.total_count,
                "specific_count": result.specific_count,
                "broader_count": result.broader_count,
                "duration_ms": round(duration_ms, 2),
            },
        )

        # Convert service objects to response schemas
        secondary_keywords = [
            _convert_to_keyword_with_volume(kw) for kw in result.secondary_keywords
        ]

        return SecondaryKeywordResponse(
            success=result.success,
            secondary_keywords=secondary_keywords,
            specific_count=result.specific_count,
            broader_count=result.broader_count,
            total_count=result.total_count,
            error=result.error,
            duration_ms=round(result.duration_ms, 2),
        )

    except SecondaryKeywordValidationError as e:
        logger.warning(
            "Secondary keyword validation error",
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
            "Failed to select secondary keywords",
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


@router.post(
    "/full",
    response_model=KeywordResearchFullResponse,
    summary="Run full keyword research pipeline",
    description="Run the full keyword research pipeline (Steps 1-6).",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def run_full_keyword_research(
    request: Request,
    project_id: str,
    data: KeywordResearchFullRequest,
    session: AsyncSession = Depends(get_session),
) -> KeywordResearchFullResponse | JSONResponse:
    """Run the full keyword research pipeline.

    Steps:
    1. Generate keyword ideas (LLM)
    2. Look up volumes (API + cache)
    4. Filter by specificity (LLM)
    5. Select primary keyword
    6. Select secondary keywords
    """
    request_id = _get_request_id(request)
    pipeline_start = time.monotonic()

    logger.debug(
        "Full keyword research pipeline request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "collection_title": data.collection_title[:100],
            "url": data.url[:200],
            "used_primaries_count": len(data.used_primaries),
            "page_id": data.page_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    step_timings: dict[str, float] = {}
    total_credits_used: int | None = None

    try:
        # ================================================================
        # STEP 1: Generate keyword ideas
        # ================================================================
        step_start = time.monotonic()
        idea_service = get_keyword_idea_service()
        idea_result = await idea_service.generate_ideas(
            collection_title=data.collection_title,
            url=data.url,
            content_excerpt=data.content_excerpt,
            project_id=project_id,
            page_id=data.page_id,
        )
        step_timings["step1_ideas"] = round((time.monotonic() - step_start) * 1000, 2)

        if not idea_result.success:
            logger.warning(
                "Step 1 failed: keyword idea generation",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "error": idea_result.error,
                },
            )
            return KeywordResearchFullResponse(
                success=False,
                primary_keyword=None,
                primary_volume=None,
                error=f"Step 1 (idea generation) failed: {idea_result.error}",
                duration_ms=round((time.monotonic() - pipeline_start) * 1000, 2),
                step_timings=step_timings,
                credits_used=None,
            )

        all_ideas = idea_result.keywords

        logger.debug(
            "Step 1 complete: keyword ideas generated",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "idea_count": len(all_ideas),
                "duration_ms": step_timings["step1_ideas"],
            },
        )

        # ================================================================
        # STEP 2: Look up volumes
        # ================================================================
        step_start = time.monotonic()
        volume_service = get_keyword_volume_service()
        volume_result = await volume_service.lookup_volumes(
            keywords=all_ideas,
            country=data.country,
            data_source=data.data_source,
            project_id=project_id,
            page_id=data.page_id,
        )
        step_timings["step2_volumes"] = round((time.monotonic() - step_start) * 1000, 2)

        if not volume_result.success:
            logger.warning(
                "Step 2 failed: volume lookup",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "error": volume_result.error,
                },
            )
            return KeywordResearchFullResponse(
                success=False,
                primary_keyword=None,
                primary_volume=None,
                all_ideas=all_ideas,
                error=f"Step 2 (volume lookup) failed: {volume_result.error}",
                duration_ms=round((time.monotonic() - pipeline_start) * 1000, 2),
                step_timings=step_timings,
                credits_used=None,
            )

        all_keywords_with_volume = volume_result.keywords
        total_credits_used = volume_result.credits_used

        logger.debug(
            "Step 2 complete: volumes looked up",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "keyword_count": len(all_keywords_with_volume),
                "cache_hit_rate": volume_result.stats.cache_hit_rate,
                "credits_used": total_credits_used,
                "duration_ms": step_timings["step2_volumes"],
            },
        )

        # ================================================================
        # STEP 4: Filter by specificity
        # ================================================================
        step_start = time.monotonic()
        specificity_service = get_keyword_specificity_service()
        specificity_result = await specificity_service.filter_keywords(
            collection_title=data.collection_title,
            url=data.url,
            content_excerpt=data.content_excerpt,
            keywords=all_keywords_with_volume,
            project_id=project_id,
            page_id=data.page_id,
        )
        step_timings["step4_specificity"] = round(
            (time.monotonic() - step_start) * 1000, 2
        )

        if not specificity_result.success:
            logger.warning(
                "Step 4 failed: specificity filtering",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "error": specificity_result.error,
                },
            )
            return KeywordResearchFullResponse(
                success=False,
                primary_keyword=None,
                primary_volume=None,
                all_ideas=all_ideas,
                all_keywords_with_volume=[
                    _convert_to_keyword_with_volume(kw) for kw in all_keywords_with_volume
                ],
                error=f"Step 4 (specificity filter) failed: {specificity_result.error}",
                duration_ms=round((time.monotonic() - pipeline_start) * 1000, 2),
                step_timings=step_timings,
                credits_used=total_credits_used,
            )

        specific_keywords = specificity_result.specific_keywords

        logger.debug(
            "Step 4 complete: keywords filtered by specificity",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "specific_count": len(specific_keywords),
                "filter_rate": specificity_result.filter_rate,
                "duration_ms": step_timings["step4_specificity"],
            },
        )

        # ================================================================
        # STEP 5: Select primary keyword
        # ================================================================
        step_start = time.monotonic()
        primary_service = get_primary_keyword_service()
        used_primaries = set(data.used_primaries) if data.used_primaries else set()
        primary_result = await primary_service.select_primary(
            collection_title=data.collection_title,
            specific_keywords=specific_keywords,
            used_primaries=used_primaries,
            project_id=project_id,
            page_id=data.page_id,
        )
        step_timings["step5_primary"] = round((time.monotonic() - step_start) * 1000, 2)

        if not primary_result.success:
            logger.warning(
                "Step 5 failed: primary keyword selection",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "error": primary_result.error,
                },
            )
            return KeywordResearchFullResponse(
                success=False,
                primary_keyword=None,
                primary_volume=None,
                all_ideas=all_ideas,
                all_keywords_with_volume=[
                    _convert_to_keyword_with_volume(kw) for kw in all_keywords_with_volume
                ],
                specific_keywords=[
                    _convert_to_keyword_with_volume(kw) for kw in specific_keywords
                ],
                error=f"Step 5 (primary selection) failed: {primary_result.error}",
                duration_ms=round((time.monotonic() - pipeline_start) * 1000, 2),
                step_timings=step_timings,
                credits_used=total_credits_used,
            )

        primary_keyword = primary_result.primary_keyword
        primary_volume = primary_result.primary_volume

        logger.debug(
            "Step 5 complete: primary keyword selected",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "primary_keyword": primary_keyword,
                "primary_volume": primary_volume,
                "duration_ms": step_timings["step5_primary"],
            },
        )

        # ================================================================
        # STEP 6: Select secondary keywords
        # ================================================================
        step_start = time.monotonic()
        secondary_service = get_secondary_keyword_service()

        # Ensure primary_keyword is not None before calling
        if primary_keyword is None:
            logger.warning(
                "Step 6 skipped: no primary keyword",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                },
            )
            secondary_keywords: list[KeywordVolumeData] = []
        else:
            secondary_result = await secondary_service.select_secondary(
                collection_title=data.collection_title,
                primary_keyword=primary_keyword,
                specific_keywords=specific_keywords,
                all_keywords=all_keywords_with_volume,
                used_primaries=used_primaries,
                project_id=project_id,
                page_id=data.page_id,
            )
            step_timings["step6_secondary"] = round(
                (time.monotonic() - step_start) * 1000, 2
            )

            if not secondary_result.success:
                logger.warning(
                    "Step 6 failed: secondary keyword selection",
                    extra={
                        "request_id": request_id,
                        "project_id": project_id,
                        "error": secondary_result.error,
                    },
                )
                # Continue with empty secondary keywords rather than failing
                secondary_keywords = []
            else:
                secondary_keywords = secondary_result.secondary_keywords

        logger.debug(
            "Step 6 complete: secondary keywords selected",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "secondary_count": len(secondary_keywords),
                "duration_ms": step_timings.get("step6_secondary", 0),
            },
        )

        # ================================================================
        # PIPELINE COMPLETE
        # ================================================================
        total_duration_ms = round((time.monotonic() - pipeline_start) * 1000, 2)

        logger.info(
            "Full keyword research pipeline complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "primary_keyword": primary_keyword,
                "primary_volume": primary_volume,
                "secondary_count": len(secondary_keywords),
                "total_ideas": len(all_ideas),
                "specific_count": len(specific_keywords),
                "credits_used": total_credits_used,
                "total_duration_ms": total_duration_ms,
                "step_timings": step_timings,
            },
        )

        return KeywordResearchFullResponse(
            success=True,
            primary_keyword=primary_keyword,
            primary_volume=primary_volume,
            secondary_keywords=[
                _convert_to_keyword_with_volume(kw) for kw in secondary_keywords
            ],
            all_ideas=all_ideas,
            all_keywords_with_volume=[
                _convert_to_keyword_with_volume(kw) for kw in all_keywords_with_volume
            ],
            specific_keywords=[
                _convert_to_keyword_with_volume(kw) for kw in specific_keywords
            ],
            error=None,
            duration_ms=total_duration_ms,
            step_timings=step_timings,
            credits_used=total_credits_used,
        )

    except Exception as e:
        logger.error(
            "Full keyword research pipeline failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "step_timings": step_timings,
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
    response_model=KeywordResearchStatsResponse,
    summary="Get keyword research statistics",
    description="Get statistics about keyword research for a project.",
    responses={
        404: {"description": "Project not found"},
    },
)
async def get_keyword_research_stats(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> KeywordResearchStatsResponse | JSONResponse:
    """Get keyword research statistics for a project."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get keyword research stats request",
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

        # TODO: Update when keyword research fields are added to CrawledPage model
        # Currently, keyword research results are returned from the API but not
        # persisted to the database. When primary_keyword and secondary_keywords
        # columns are added, update these queries to count actual values.
        pages_with_keywords = 0
        total_primary_keywords = 0
        total_secondary_keywords = 0

        # Get cache stats
        volume_service = get_keyword_volume_service()
        cache_stats = volume_service.get_cache_stats()

        cache_stats_response = VolumeStatsResponse(
            total_keywords=cache_stats.hits + cache_stats.misses,
            cache_hits=cache_stats.hits,
            cache_misses=cache_stats.misses,
            api_lookups=0,  # Not tracked in CacheStats
            api_errors=cache_stats.errors,
            cache_hit_rate=round(cache_stats.hit_rate, 3),
        )

        logger.debug(
            "Keyword research stats retrieved",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_pages": total_pages,
                "pages_with_keywords": pages_with_keywords,
                "total_primary_keywords": total_primary_keywords,
            },
        )

        return KeywordResearchStatsResponse(
            project_id=project_id,
            total_pages=total_pages,
            pages_with_keywords=pages_with_keywords,
            pages_without_keywords=total_pages - pages_with_keywords,
            total_primary_keywords=total_primary_keywords,
            total_secondary_keywords=total_secondary_keywords,
            cache_stats=cache_stats_response,
        )

    except Exception as e:
        logger.error(
            "Failed to get keyword research stats",
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
