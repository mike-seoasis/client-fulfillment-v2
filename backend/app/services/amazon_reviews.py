"""AmazonReviewsService for brand Amazon store detection and review analysis.

Orchestrates the Amazon reviews integration to:
1. Detect if a brand has products on Amazon
2. Fetch and analyze customer reviews
3. Extract insights, personas, and proof statistics

Features:
- Amazon store auto-detection via Perplexity
- Review extraction and analysis
- Customer persona generation
- Proof statistics extraction

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second

RAILWAY DEPLOYMENT REQUIREMENTS:
- API base URL from environment variable (uses Perplexity settings)
- Handle API errors gracefully (show user-friendly messages)
- Implement retry logic for transient failures (via integration client)
- Support both HTTP and HTTPS (Railway provides SSL)
"""

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.amazon_reviews import (
    AmazonProduct,
    AmazonReview,
    AmazonReviewAnalysisResult,
    AmazonReviewsClient,
    AmazonStoreDetectionResult,
    get_amazon_reviews,
)

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000


class AmazonReviewsServiceError(Exception):
    """Base exception for AmazonReviewsService errors."""

    pass


class AmazonReviewsValidationError(AmazonReviewsServiceError):
    """Raised when input validation fails."""

    def __init__(self, field_name: str, value: str, message: str) -> None:
        super().__init__(f"Validation error for {field_name}: {message}")
        self.field_name = field_name
        self.value = value
        self.message = message


class AmazonReviewsLookupError(AmazonReviewsServiceError):
    """Raised when Amazon review lookup fails."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        brand_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.brand_name = brand_name


@dataclass
class AmazonStoreResult:
    """Result of Amazon store detection.

    Attributes:
        success: Whether the operation succeeded
        brand_name: The brand that was searched
        has_store: Whether the brand has products on Amazon
        products: List of products found
        error: Error message if operation failed
        duration_ms: Operation duration in milliseconds
    """

    success: bool
    brand_name: str
    has_store: bool = False
    products: list[AmazonProduct] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class ReviewAnalysisResult:
    """Result of Amazon review analysis.

    Attributes:
        success: Whether the operation succeeded
        brand_name: The brand that was analyzed
        products_analyzed: Number of products analyzed
        reviews: Extracted reviews
        common_praise: Common positive themes
        common_complaints: Common negative themes
        customer_personas: Inferred customer personas
        proof_stats: Social proof statistics
        error: Error message if operation failed
        duration_ms: Operation duration in milliseconds
        analyzed_at: Timestamp of analysis
        needs_review: Whether the result needs user validation (fallback used)
        fallback_used: Whether fallback persona generation was used
        fallback_source: Source of fallback data (e.g., "website_analysis")
    """

    success: bool
    brand_name: str
    products_analyzed: int = 0
    reviews: list[AmazonReview] = field(default_factory=list)
    common_praise: list[str] = field(default_factory=list)
    common_complaints: list[str] = field(default_factory=list)
    customer_personas: list[dict[str, Any]] = field(default_factory=list)
    proof_stats: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    analyzed_at: str = ""
    needs_review: bool = False
    fallback_used: bool = False
    fallback_source: str | None = None


class AmazonReviewsService:
    """Service for Amazon store detection and review analysis.

    Provides business logic layer for:
    - Detecting if brands sell on Amazon
    - Analyzing customer reviews
    - Extracting insights for brand configuration
    """

    def __init__(
        self,
        client: AmazonReviewsClient | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            client: Optional AmazonReviewsClient instance.
                   If not provided, uses the global client.
        """
        self._client = client

    async def _get_client(self) -> AmazonReviewsClient:
        """Get the Amazon reviews client."""
        if self._client is None:
            self._client = await get_amazon_reviews()
        return self._client

    def _validate_brand_name(self, brand_name: str) -> None:
        """Validate brand name input.

        Args:
            brand_name: The brand name to validate

        Raises:
            AmazonReviewsValidationError: If validation fails
        """
        if not brand_name:
            logger.warning(
                "Brand name validation failed: empty",
                extra={"field": "brand_name", "value": ""},
            )
            raise AmazonReviewsValidationError(
                field_name="brand_name",
                value="",
                message="Brand name cannot be empty",
            )

        if len(brand_name) > 200:
            logger.warning(
                "Brand name validation failed: too long",
                extra={"field": "brand_name", "length": len(brand_name)},
            )
            raise AmazonReviewsValidationError(
                field_name="brand_name",
                value=brand_name[:50] + "...",
                message="Brand name must be 200 characters or less",
            )

    async def detect_amazon_store(
        self,
        brand_name: str,
        product_category: str | None = None,
        project_id: str | None = None,
    ) -> AmazonStoreResult:
        """Detect if a brand has products on Amazon.

        Args:
            brand_name: The brand/company name to search
            product_category: Optional category to narrow search
            project_id: Optional project ID for logging

        Returns:
            AmazonStoreResult with detection results

        Raises:
            AmazonReviewsValidationError: If input validation fails
        """
        logger.debug(
            "detect_amazon_store entry",
            extra={
                "brand_name": brand_name,
                "product_category": product_category,
                "project_id": project_id,
            },
        )

        start_time = time.monotonic()

        # Validate input
        self._validate_brand_name(brand_name)

        try:
            client = await self._get_client()

            logger.info(
                "Starting Amazon store detection",
                extra={
                    "brand_name": brand_name,
                    "project_id": project_id,
                },
            )

            # Call the integration
            result: AmazonStoreDetectionResult = await client.detect_amazon_store(
                brand_name=brand_name,
                product_category=product_category,
                project_id=project_id,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.info(
                    "Slow Amazon store detection",
                    extra={
                        "brand_name": brand_name,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )

            logger.info(
                "Amazon store detection complete",
                extra={
                    "brand_name": brand_name,
                    "success": result.success,
                    "has_store": result.has_amazon_store,
                    "products_found": len(result.products),
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )

            logger.debug(
                "detect_amazon_store exit",
                extra={
                    "brand_name": brand_name,
                    "success": result.success,
                    "project_id": project_id,
                },
            )

            return AmazonStoreResult(
                success=result.success,
                brand_name=result.brand_name,
                has_store=result.has_amazon_store,
                products=result.products,
                error=result.error,
                duration_ms=duration_ms,
            )

        except AmazonReviewsValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.exception(
                "Exception in detect_amazon_store",
                extra={
                    "brand_name": brand_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )
            raise AmazonReviewsLookupError(
                message=f"Failed to detect Amazon store: {e}",
                project_id=project_id,
                brand_name=brand_name,
            ) from e

    async def analyze_reviews(
        self,
        brand_name: str,
        product_category: str | None = None,
        max_products: int = 3,
        project_id: str | None = None,
        website_url: str | None = None,
        use_fallback: bool = True,
    ) -> ReviewAnalysisResult:
        """Analyze Amazon reviews for a brand.

        Performs complete review analysis:
        1. Detects Amazon store and products
        2. Analyzes reviews for top products
        3. Extracts insights, personas, and proof stats
        4. If no reviews found and use_fallback=True, generates fallback personas

        Args:
            brand_name: The brand/company name
            product_category: Optional category hint
            max_products: Max products to analyze (1-5)
            project_id: Optional project ID for logging
            website_url: Optional website URL for fallback persona generation
            use_fallback: Whether to use fallback persona generation (default True)

        Returns:
            ReviewAnalysisResult with comprehensive review data

        Raises:
            AmazonReviewsValidationError: If input validation fails
        """
        logger.debug(
            "analyze_reviews entry",
            extra={
                "brand_name": brand_name,
                "product_category": product_category,
                "max_products": max_products,
                "project_id": project_id,
                "website_url": website_url,
                "use_fallback": use_fallback,
            },
        )

        start_time = time.monotonic()

        # Validate input
        self._validate_brand_name(brand_name)

        if max_products < 1 or max_products > 5:
            logger.warning(
                "max_products validation failed",
                extra={
                    "field": "max_products",
                    "value": max_products,
                },
            )
            raise AmazonReviewsValidationError(
                field_name="max_products",
                value=str(max_products),
                message="max_products must be between 1 and 5",
            )

        try:
            client = await self._get_client()

            logger.info(
                "Starting Amazon review analysis",
                extra={
                    "brand_name": brand_name,
                    "max_products": max_products,
                    "project_id": project_id,
                },
            )

            # Call the integration
            result: AmazonReviewAnalysisResult = await client.analyze_brand_reviews(
                brand_name=brand_name,
                product_category=product_category,
                max_products=max_products,
                project_id=project_id,
                website_url=website_url,
                use_fallback=use_fallback,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.info(
                    "Slow Amazon review analysis",
                    extra={
                        "brand_name": brand_name,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )

            logger.info(
                "Amazon review analysis complete",
                extra={
                    "brand_name": brand_name,
                    "success": result.success,
                    "products_analyzed": result.products_analyzed,
                    "reviews_found": len(result.reviews),
                    "personas_generated": len(result.customer_personas),
                    "fallback_used": result.fallback_used,
                    "needs_review": result.needs_review,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )

            logger.debug(
                "analyze_reviews exit",
                extra={
                    "brand_name": brand_name,
                    "success": result.success,
                    "fallback_used": result.fallback_used,
                    "project_id": project_id,
                },
            )

            return ReviewAnalysisResult(
                success=result.success,
                brand_name=result.brand_name,
                products_analyzed=result.products_analyzed,
                reviews=result.reviews,
                common_praise=result.common_praise,
                common_complaints=result.common_complaints,
                customer_personas=result.customer_personas,
                proof_stats=result.proof_stats,
                error=result.error,
                duration_ms=duration_ms,
                analyzed_at=result.analyzed_at,
                needs_review=result.needs_review,
                fallback_used=result.fallback_used,
                fallback_source=result.fallback_source,
            )

        except AmazonReviewsValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.exception(
                "Exception in analyze_reviews",
                extra={
                    "brand_name": brand_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )
            raise AmazonReviewsLookupError(
                message=f"Failed to analyze Amazon reviews: {e}",
                project_id=project_id,
                brand_name=brand_name,
            ) from e


# Global service instance
_amazon_reviews_service: AmazonReviewsService | None = None


def get_amazon_reviews_service() -> AmazonReviewsService:
    """Get or create the global AmazonReviewsService instance.

    Returns:
        AmazonReviewsService singleton instance
    """
    global _amazon_reviews_service
    if _amazon_reviews_service is None:
        _amazon_reviews_service = AmazonReviewsService()
    return _amazon_reviews_service
