"""Pydantic schemas for Amazon reviews API.

Defines request and response schemas for Amazon store detection
and review analysis endpoints.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AmazonProductResponse(BaseModel):
    """An Amazon product found for a brand."""

    title: str
    asin: str | None = None
    url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    price: str | None = None


class AmazonReviewResponse(BaseModel):
    """A customer review from Amazon."""

    text: str
    rating: int = Field(ge=1, le=5, description="Rating from 1 to 5")
    title: str | None = None
    verified_purchase: bool = True
    helpful_votes: int = 0


class CustomerPersonaResponse(BaseModel):
    """A customer persona inferred from reviews."""

    name: str
    source: str = "amazon_reviews"
    inferred: bool = True


class ProofStatResponse(BaseModel):
    """A proof statistic from Amazon data."""

    stat: str
    context: str


class AmazonStoreDetectionRequest(BaseModel):
    """Request to detect Amazon store for a brand."""

    brand_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Brand/company name to search for",
    )
    product_category: str | None = Field(
        default=None,
        max_length=100,
        description="Optional product category to narrow search",
    )


class AmazonStoreDetectionResponse(BaseModel):
    """Response from Amazon store detection."""

    success: bool
    brand_name: str
    has_amazon_store: bool = False
    store_url: str | None = None
    products: list[AmazonProductResponse] = []
    error: str | None = None
    duration_ms: float = 0.0


class AmazonReviewAnalysisRequest(BaseModel):
    """Request to analyze Amazon reviews for a brand."""

    brand_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Brand/company name to analyze",
    )
    product_category: str | None = Field(
        default=None,
        max_length=100,
        description="Optional product category hint",
    )
    max_products: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of products to analyze (1-5)",
    )


class AmazonReviewAnalysisResponse(BaseModel):
    """Response from Amazon review analysis."""

    success: bool
    brand_name: str
    products_analyzed: int = 0
    reviews: list[AmazonReviewResponse] = []
    common_praise: list[str] = []
    common_complaints: list[str] = []
    customer_personas: list[CustomerPersonaResponse] = []
    proof_stats: list[ProofStatResponse] = []
    error: str | None = None
    duration_ms: float = 0.0
    analyzed_at: datetime | None = None
