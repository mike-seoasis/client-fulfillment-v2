"""NLP content analysis API endpoints.

Provides content signal analysis for page categorization:
- POST /api/v1/nlp/analyze-content - Analyze content signals
- POST /api/v1/nlp/analyze-competitors - Analyze competitor content using TF-IDF

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
    AnalyzeCompetitorsRequest,
    AnalyzeCompetitorsResponse,
    AnalyzeContentRequest,
    AnalyzeContentResponse,
    CompetitorTermItem,
    ContentSignalItem,
)
from app.services.tfidf_analysis import get_tfidf_analysis_service
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


@router.post(
    "/analyze-competitors",
    response_model=AnalyzeCompetitorsResponse,
    summary="Analyze competitor content",
    description="Analyze competitor content using TF-IDF to extract important terms. "
    "Optionally find terms missing from user content.",
    responses={
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "documents: Field required",
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
async def analyze_competitors(
    request: Request,
    data: AnalyzeCompetitorsRequest,
) -> AnalyzeCompetitorsResponse | JSONResponse:
    """Analyze competitor content using TF-IDF term extraction.

    This endpoint performs Term Frequency-Inverse Document Frequency (TF-IDF)
    analysis on competitor content to identify the most important and distinctive
    terms. Use this for:

    - Identifying key terms competitors use
    - Finding content gaps (terms missing from your content)
    - Understanding semantic themes across competitor pages
    - Improving content optimization strategy

    TF-IDF scoring:
    - Terms appearing frequently in few documents score highest
    - Common terms appearing across all documents are filtered out
    - Includes both unigrams (single words) and bigrams (two-word phrases)

    Missing terms mode:
    - When user_content is provided, only returns terms NOT in user content
    - Useful for content gap analysis and optimization recommendations
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Competitor analysis request",
        extra={
            "request_id": request_id,
            "document_count": len(data.documents),
            "top_n": data.top_n,
            "include_bigrams": data.include_bigrams,
            "has_user_content": data.user_content is not None,
            "min_doc_frequency": data.min_doc_frequency,
            "max_doc_frequency_ratio": data.max_doc_frequency_ratio,
            "project_id": data.project_id,
        },
    )

    try:
        tfidf_service = get_tfidf_analysis_service()
        missing_terms_mode = data.user_content is not None

        if missing_terms_mode:
            # Find terms missing from user content
            result = await tfidf_service.find_missing_terms(
                competitor_documents=data.documents,
                user_content=data.user_content or "",
                top_n=data.top_n,
                project_id=data.project_id,
            )
        else:
            # Standard TF-IDF analysis
            result = await tfidf_service.analyze(
                documents=data.documents,
                top_n=data.top_n,
                include_bigrams=data.include_bigrams,
                min_df=data.min_doc_frequency,
                max_df_ratio=data.max_doc_frequency_ratio,
                project_id=data.project_id,
            )

        duration_ms = (time.monotonic() - start_time) * 1000

        if not result.success:
            logger.warning(
                "Competitor analysis failed",
                extra={
                    "request_id": request_id,
                    "document_count": len(data.documents),
                    "error_message": result.error,
                    "project_id": data.project_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": result.error or "Analysis failed",
                    "code": "ANALYSIS_FAILED",
                    "request_id": request_id,
                },
            )

        # Convert terms to response format
        terms = [
            CompetitorTermItem(
                term=t.term,
                score=round(t.score, 4),
                doc_frequency=t.doc_frequency,
                term_frequency=t.term_frequency,
            )
            for t in result.terms
        ]

        logger.info(
            "Competitor analysis complete",
            extra={
                "request_id": request_id,
                "document_count": result.document_count,
                "term_count": len(terms),
                "vocabulary_size": result.vocabulary_size,
                "missing_terms_mode": missing_terms_mode,
                "project_id": data.project_id,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return AnalyzeCompetitorsResponse(
            success=True,
            request_id=request_id,
            terms=terms,
            term_count=len(terms),
            document_count=result.document_count,
            vocabulary_size=result.vocabulary_size,
            missing_terms_mode=missing_terms_mode,
            error=None,
            duration_ms=round(duration_ms, 2),
            cache_hit=False,
        )

    except ValueError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        logger.warning(
            "Competitor analysis validation error",
            extra={
                "request_id": request_id,
                "document_count": len(data.documents),
                "error_message": str(e),
                "project_id": data.project_id,
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
            "Competitor analysis failed",
            extra={
                "request_id": request_id,
                "document_count": len(data.documents),
                "project_id": data.project_id,
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
