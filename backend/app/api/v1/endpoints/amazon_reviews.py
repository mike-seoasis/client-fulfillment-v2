"""Amazon Reviews phase API endpoints for projects.

Provides Amazon store detection and review analysis:
- POST /api/v1/projects/{project_id}/phases/amazon_reviews/detect - Detect Amazon store
- POST /api/v1/projects/{project_id}/phases/amazon_reviews/analyze - Analyze reviews

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

import contextlib
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.schemas.amazon_reviews import (
    AmazonProductResponse,
    AmazonReviewAnalysisRequest,
    AmazonReviewAnalysisResponse,
    AmazonReviewResponse,
    AmazonStoreDetectionRequest,
    AmazonStoreDetectionResponse,
    CustomerPersonaResponse,
    ProofStatResponse,
)
from app.services.amazon_reviews import (
    AmazonReviewsLookupError,
    AmazonReviewsValidationError,
    get_amazon_reviews_service,
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
    "/detect",
    response_model=AmazonStoreDetectionResponse,
    summary="Detect Amazon store for a brand",
    description="Search Amazon for products sold by or branded as the given brand name.",
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
                        "error": "Validation error for brand_name: Brand name cannot be empty",
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
                        "error": "Failed to detect Amazon store: <details>",
                        "code": "INTERNAL_ERROR",
                        "request_id": "<uuid>",
                    }
                }
            },
        },
    },
)
async def detect_amazon_store(
    request: Request,
    project_id: str,
    data: AmazonStoreDetectionRequest,
    session: AsyncSession = Depends(get_session),
) -> AmazonStoreDetectionResponse | JSONResponse:
    """Detect if a brand has products on Amazon.

    Searches Amazon for products sold by or branded as the given brand name.
    Returns a list of found products with their details.

    Note: This uses Perplexity AI to search Amazon, avoiding direct scraping.
    No Amazon store found is not an error - it simply means the brand doesn't
    sell on Amazon.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.info(
        "Amazon store detection request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "brand_name": data.brand_name,
            "product_category": data.product_category,
        },
    )

    # Verify project exists
    error_response = await _verify_project_exists(project_id, session, request_id)
    if error_response:
        return error_response

    try:
        service = get_amazon_reviews_service()
        result = await service.detect_amazon_store(
            brand_name=data.brand_name,
            product_category=data.product_category,
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Amazon store detection response",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "success": result.success,
                "has_store": result.has_store,
                "products_found": len(result.products),
                "duration_ms": duration_ms,
            },
        )

        return AmazonStoreDetectionResponse(
            success=result.success,
            brand_name=result.brand_name,
            has_amazon_store=result.has_store,
            products=[
                AmazonProductResponse(
                    title=p.title,
                    asin=p.asin,
                    url=p.url,
                    rating=p.rating,
                    review_count=p.review_count,
                    price=p.price,
                )
                for p in result.products
            ],
            error=result.error,
            duration_ms=result.duration_ms,
        )

    except AmazonReviewsValidationError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Amazon store detection validation error",
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

    except AmazonReviewsLookupError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Amazon store detection lookup error",
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
            "Amazon store detection unexpected error",
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


@router.post(
    "/analyze",
    response_model=AmazonReviewAnalysisResponse,
    summary="Analyze Amazon reviews for a brand",
    description="Detect Amazon store and analyze customer reviews for insights.",
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
                        "error": "Validation error for brand_name: Brand name cannot be empty",
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
                        "error": "Failed to analyze Amazon reviews: <details>",
                        "code": "INTERNAL_ERROR",
                        "request_id": "<uuid>",
                    }
                }
            },
        },
    },
)
async def analyze_amazon_reviews(
    request: Request,
    project_id: str,
    data: AmazonReviewAnalysisRequest,
    session: AsyncSession = Depends(get_session),
) -> AmazonReviewAnalysisResponse | JSONResponse:
    """Analyze Amazon reviews for a brand.

    Performs complete review analysis:
    1. Detects Amazon store and products
    2. Analyzes reviews for top products (up to max_products)
    3. Extracts insights, personas, and proof statistics

    Note: This uses Perplexity AI to analyze Amazon reviews, avoiding direct scraping.
    If no Amazon store is found, the response will indicate success with 0 products analyzed.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.info(
        "Amazon review analysis request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "brand_name": data.brand_name,
            "product_category": data.product_category,
            "max_products": data.max_products,
        },
    )

    # Verify project exists
    error_response = await _verify_project_exists(project_id, session, request_id)
    if error_response:
        return error_response

    try:
        service = get_amazon_reviews_service()
        result = await service.analyze_reviews(
            brand_name=data.brand_name,
            product_category=data.product_category,
            max_products=data.max_products,
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Amazon review analysis response",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "success": result.success,
                "products_analyzed": result.products_analyzed,
                "reviews_found": len(result.reviews),
                "personas_generated": len(result.customer_personas),
                "duration_ms": duration_ms,
            },
        )

        # Parse analyzed_at timestamp
        analyzed_at = None
        if result.analyzed_at:
            with contextlib.suppress(ValueError):
                analyzed_at = datetime.fromisoformat(result.analyzed_at.replace("Z", "+00:00"))

        return AmazonReviewAnalysisResponse(
            success=result.success,
            brand_name=result.brand_name,
            products_analyzed=result.products_analyzed,
            reviews=[
                AmazonReviewResponse(
                    text=r.text,
                    rating=r.rating,
                    title=r.title,
                    verified_purchase=r.verified_purchase,
                    helpful_votes=r.helpful_votes,
                )
                for r in result.reviews
            ],
            common_praise=result.common_praise,
            common_complaints=result.common_complaints,
            customer_personas=[
                CustomerPersonaResponse(
                    name=p.get("name", ""),
                    source=p.get("source", "amazon_reviews"),
                    inferred=p.get("inferred", True),
                )
                for p in result.customer_personas
            ],
            proof_stats=[
                ProofStatResponse(
                    stat=s.get("stat", ""),
                    context=s.get("context", ""),
                )
                for s in result.proof_stats
            ],
            error=result.error,
            duration_ms=result.duration_ms,
            analyzed_at=analyzed_at,
        )

    except AmazonReviewsValidationError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Amazon review analysis validation error",
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

    except AmazonReviewsLookupError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Amazon review analysis lookup error",
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
            "Amazon review analysis unexpected error",
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
