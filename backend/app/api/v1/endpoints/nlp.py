"""NLP content analysis API endpoints.

Provides content signal analysis for page categorization:
- POST /api/v1/nlp/analyze-content - Analyze content signals

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

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.schemas.nlp import (
    AnalyzeContentRequest,
    AnalyzeContentResponse,
    ContentSignalItem,
)
from app.utils.content_signals import (
    ContentSignalDetector,
    get_content_signal_detector,
)

logger = get_logger(__name__)

router = APIRouter()


def _get_request_id(request: Request) -> str:
    """Get request_id from request state."""
    return getattr(request.state, "request_id", "unknown")


@router.post(
    "/analyze-content",
    response_model=AnalyzeContentResponse,
    summary="Analyze content signals",
    description="Analyze content (title, headings, body, schema, etc.) to detect signals "
    "that indicate page category. Returns boosted confidence and final category.",
    responses={
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "url_category: Field required",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal server error",
                        "code": "INTERNAL_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def analyze_content(
    request: Request,
    data: AnalyzeContentRequest,
) -> AnalyzeContentResponse | JSONResponse:
    """Analyze content signals for page categorization.

    This endpoint analyzes various content elements (title, headings, body text,
    JSON-LD schema, meta description, breadcrumbs) to detect signals that indicate
    the page category. Signals can boost confidence in the URL-based categorization
    or even override the category if the signals are strong enough.

    Signal detection:
    - Title patterns: "buy now", "privacy policy", "blog", etc.
    - Schema types: Product, Article, FAQPage, etc.
    - Body patterns: prices, "add to cart", "posted by", etc.
    - Heading patterns: FAQ questions, contact info, etc.

    Confidence boosting:
    - Matching signals increase confidence (capped at 0.95)
    - Strong signals for a different category can override the URL category
    - Multiple signals for the same category stack (with diminishing returns)
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Content analysis request",
        extra={
            "request_id": request_id,
            "url_category": data.url_category,
            "url_confidence": data.url_confidence,
            "has_title": data.title is not None,
            "heading_count": len(data.headings) if data.headings else 0,
            "has_body": data.body_text is not None,
            "has_schema": data.jsonld_schema is not None,
            "has_meta": data.meta_description is not None,
            "breadcrumb_count": len(data.breadcrumbs) if data.breadcrumbs else 0,
            "project_id": data.project_id,
            "page_id": data.page_id,
        },
    )

    try:
        detector: ContentSignalDetector = get_content_signal_detector()

        analysis = detector.analyze(
            url_category=data.url_category,
            url_confidence=data.url_confidence,
            title=data.title,
            headings=data.headings,
            body_text=data.body_text,
            schema_json=data.jsonld_schema,
            meta_description=data.meta_description,
            breadcrumbs=data.breadcrumbs,
            project_id=data.project_id,
            page_id=data.page_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        # Convert signals to response format
        signals = [
            ContentSignalItem(
                signal_type=s.signal_type.value,
                category=s.category,
                confidence_boost=s.confidence_boost,
                matched_text=s.matched_text[:200] if s.matched_text else "",
                pattern=s.pattern,
            )
            for s in analysis.signals
        ]

        logger.info(
            "Content analysis complete",
            extra={
                "request_id": request_id,
                "url_category": data.url_category,
                "final_category": analysis.final_category,
                "url_confidence": data.url_confidence,
                "boosted_confidence": analysis.boosted_confidence,
                "signal_count": len(signals),
                "category_changed": data.url_category != analysis.final_category,
                "project_id": data.project_id,
                "page_id": data.page_id,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return AnalyzeContentResponse(
            success=True,
            request_id=request_id,
            url_category=analysis.url_category,
            url_confidence=analysis.url_confidence,
            final_category=analysis.final_category,
            boosted_confidence=analysis.boosted_confidence,
            signals=signals,
            signal_count=len(signals),
            error=None,
            duration_ms=round(duration_ms, 2),
        )

    except ValueError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Content analysis validation error",
            extra={
                "request_id": request_id,
                "url_category": data.url_category,
                "error_message": str(e),
                "project_id": data.project_id,
                "page_id": data.page_id,
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
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.error(
            "Content analysis failed",
            extra={
                "request_id": request_id,
                "url_category": data.url_category,
                "project_id": data.project_id,
                "page_id": data.page_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "duration_ms": round(duration_ms, 2),
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
