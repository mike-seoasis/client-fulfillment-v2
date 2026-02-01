"""Review Platforms phase API endpoints for projects.

Provides on-site review platform detection:
- POST /api/v1/projects/{project_id}/phases/review_platforms/detect - Detect review platforms

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
from app.schemas.review_platforms import (
    PlatformInfoResponse,
    ReviewPlatformDetectionRequest,
    ReviewPlatformDetectionResponse,
)
from app.services.project import ProjectNotFoundError, ProjectService
from app.services.review_platforms import (
    ReviewPlatformLookupError,
    ReviewPlatformValidationError,
    get_review_platform_service,
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


@router.post(
    "/detect",
    response_model=ReviewPlatformDetectionResponse,
    summary="Detect review platforms on a website",
    description="Analyze a website to detect embedded review platforms like Yotpo, Judge.me, etc.",
    responses={
        404: {
            "description": "Project not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Project not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<uuid>",
                    }
                }
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation error for website_url: Website URL cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<uuid>",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Failed to detect review platforms: <details>",
                        "code": "INTERNAL_ERROR",
                        "request_id": "<uuid>",
                    }
                }
            },
        },
    },
)
async def detect_review_platforms(
    request: Request,
    project_id: str,
    data: ReviewPlatformDetectionRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewPlatformDetectionResponse | JSONResponse:
    """Detect review platforms embedded on a website.

    Analyzes the specified website to find third-party review platforms
    such as Yotpo, Judge.me, Stamped.io, Loox, Okendo, Reviews.io,
    Trustpilot, Bazaarvoice, and PowerReviews.

    Returns detected platforms with confidence scores, evidence,
    and widget location information.

    Note: This uses Perplexity AI to analyze websites, avoiding direct scraping.
    No platform detected is not an error - it simply means no embedded
    review platform was found.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.info(
        "Review platform detection request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "website_url": data.website_url,
        },
    )

    # Verify project exists
    error_response = await _verify_project_exists(project_id, session, request_id)
    if error_response:
        return error_response

    try:
        service = get_review_platform_service()
        result = await service.detect_platforms(
            website_url=data.website_url,
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Review platform detection response",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "success": result.success,
                "platforms_found": len(result.platforms),
                "primary_platform": result.primary_platform,
                "duration_ms": duration_ms,
            },
        )

        return ReviewPlatformDetectionResponse(
            success=result.success,
            website_url=result.website_url,
            platforms=[
                PlatformInfoResponse(
                    platform=p.platform,
                    platform_name=p.platform_name,
                    confidence=p.confidence,
                    evidence=p.evidence,
                    widget_locations=p.widget_locations,
                    api_hints=p.api_hints,
                )
                for p in result.platforms
            ],
            primary_platform=result.primary_platform,
            primary_platform_name=result.primary_platform_name,
            error=result.error,
            duration_ms=result.duration_ms,
        )

    except ReviewPlatformValidationError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Review platform detection validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "field": e.field_name,
                "value": e.value[:50] if e.value else None,
                "message": e.message,
                "duration_ms": duration_ms,
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

    except ReviewPlatformLookupError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Review platform detection lookup error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "error": str(e),
                "duration_ms": duration_ms,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": str(e),
                "code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
        )

    except Exception as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.exception(
            "Review platform detection unexpected error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "duration_ms": duration_ms,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": f"Internal error: {e}",
                "code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
        )
