"""Pydantic schemas for NLP content analysis API endpoints.

Schemas for content signal analysis:
- AnalyzeContentRequest: Input for content analysis
- AnalyzeContentResponse: Analysis results with signals and confidence

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

from pydantic import BaseModel, Field

# =============================================================================
# CONTENT SIGNAL MODELS
# =============================================================================


class ContentSignalItem(BaseModel):
    """A detected content signal indicating a category."""

    signal_type: str = Field(
        ...,
        description="Type of signal (title, heading, schema, meta, breadcrumb, body)",
        examples=["title", "schema", "body"],
    )
    category: str = Field(
        ...,
        description="The category this signal indicates",
        examples=["product", "blog", "policy"],
    )
    confidence_boost: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence boost from this signal (0.0-1.0)",
    )
    matched_text: str = Field(
        ...,
        max_length=200,
        description="The text that matched the signal pattern (truncated to 200 chars)",
        examples=["Buy now", "$29.99", '"@type": "Product"'],
    )
    pattern: str | None = Field(
        None,
        description="The regex pattern that matched (for debugging)",
    )


# =============================================================================
# ANALYZE CONTENT REQUEST
# =============================================================================


class AnalyzeContentRequest(BaseModel):
    """Request schema for content analysis."""

    url_category: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Category from URL-based detection",
        examples=["product", "collection", "blog", "other"],
    )
    url_confidence: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Base confidence from URL pattern matching (0.0-1.0)",
    )
    title: str | None = Field(
        None,
        max_length=500,
        description="Page title",
        examples=["Buy Widget Pro - Free Shipping | Example Store"],
    )
    headings: list[str] | None = Field(
        None,
        max_length=20,
        description="List of heading texts (H1, H2, etc.)",
        examples=[["Product Details", "Add to Cart", "Reviews"]],
    )
    body_text: str | None = Field(
        None,
        max_length=50000,
        description="Body text content (truncated to 10k chars for analysis)",
    )
    jsonld_schema: str | None = Field(
        None,
        max_length=20000,
        description="JSON-LD schema content as string",
    )
    meta_description: str | None = Field(
        None,
        max_length=500,
        description="Meta description content",
    )
    breadcrumbs: list[str] | None = Field(
        None,
        max_length=10,
        description="Breadcrumb trail texts",
        examples=[["Home", "Products", "Widgets"]],
    )
    project_id: str | None = Field(
        None,
        description="Optional project ID for logging context",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for logging context",
    )


# =============================================================================
# ANALYZE CONTENT RESPONSE
# =============================================================================


class AnalyzeContentResponse(BaseModel):
    """Response schema for content analysis."""

    success: bool = Field(
        ...,
        description="Whether analysis completed successfully",
    )
    request_id: str = Field(
        ...,
        description="Request ID for debugging and tracing",
    )

    # Analysis results
    url_category: str = Field(
        ...,
        description="Original category from URL-based detection",
    )
    url_confidence: float = Field(
        ...,
        description="Original confidence from URL pattern matching",
    )
    final_category: str = Field(
        ...,
        description="Final category after applying signals (may differ from url_category)",
    )
    boosted_confidence: float = Field(
        ...,
        description="Final confidence after applying signal boosts",
    )
    signals: list[ContentSignalItem] = Field(
        default_factory=list,
        description="List of detected content signals",
    )
    signal_count: int = Field(
        0,
        ge=0,
        description="Total number of signals detected",
    )

    # Error handling
    error: str | None = Field(
        None,
        description="Error message if failed",
    )

    # Performance
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


# =============================================================================
# ANALYZE COMPETITORS REQUEST/RESPONSE
# =============================================================================


class CompetitorTermItem(BaseModel):
    """A term extracted from competitor content with TF-IDF scoring."""

    term: str = Field(
        ...,
        description="The extracted term (unigram or bigram)",
        examples=["vacuum sealed", "coffee storage", "airtight"],
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized TF-IDF score (0.0-1.0)",
    )
    doc_frequency: int = Field(
        0,
        ge=0,
        description="Number of documents containing this term",
    )
    term_frequency: int = Field(
        0,
        ge=0,
        description="Total occurrences across all documents",
    )


class AnalyzeCompetitorsRequest(BaseModel):
    """Request schema for competitor content analysis using TF-IDF."""

    documents: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of competitor content documents to analyze (1-50 documents)",
        examples=[
            [
                "Vacuum sealed coffee containers keep beans fresh for months",
                "Airtight coffee storage preserves aroma and flavor",
            ]
        ],
    )
    top_n: int = Field(
        25,
        ge=1,
        le=100,
        description="Number of top terms to return (1-100)",
    )
    include_bigrams: bool = Field(
        True,
        description="Whether to include two-word phrases (bigrams) in analysis",
    )
    user_content: str | None = Field(
        None,
        max_length=50000,
        description="Optional user content to find missing terms "
        "(only terms NOT in user content will be returned)",
    )
    min_doc_frequency: int = Field(
        1,
        ge=1,
        description="Minimum number of documents a term must appear in",
    )
    max_doc_frequency_ratio: float = Field(
        0.85,
        gt=0.0,
        le=1.0,
        description="Maximum ratio of documents a term can appear in (0.0-1.0)",
    )
    project_id: str | None = Field(
        None,
        description="Optional project ID for logging and caching context",
    )


class AnalyzeCompetitorsResponse(BaseModel):
    """Response schema for competitor content analysis."""

    success: bool = Field(
        ...,
        description="Whether analysis completed successfully",
    )
    request_id: str = Field(
        ...,
        description="Request ID for debugging and tracing",
    )

    # Analysis results
    terms: list[CompetitorTermItem] = Field(
        default_factory=list,
        description="List of extracted terms with TF-IDF scores, sorted by score descending",
    )
    term_count: int = Field(
        0,
        ge=0,
        description="Number of terms returned",
    )
    document_count: int = Field(
        0,
        ge=0,
        description="Number of documents analyzed",
    )
    vocabulary_size: int = Field(
        0,
        ge=0,
        description="Total unique terms before filtering",
    )

    # Missing terms mode
    missing_terms_mode: bool = Field(
        False,
        description="Whether results are filtered to terms missing from user content",
    )

    # Error handling
    error: str | None = Field(
        None,
        description="Error message if analysis failed",
    )

    # Performance
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )
    cache_hit: bool = Field(
        False,
        description="Whether results were served from cache",
    )


# =============================================================================
# RECOMMEND TERMS REQUEST/RESPONSE
# =============================================================================


class RecommendedTermItem(BaseModel):
    """A recommended term with priority and context."""

    term: str = Field(
        ...,
        description="The recommended term (unigram or bigram)",
        examples=["vacuum sealed", "airtight container", "freshness"],
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized importance score (0.0-1.0)",
    )
    priority: str = Field(
        ...,
        description="Recommendation priority: high, medium, or low",
        examples=["high", "medium", "low"],
    )
    doc_frequency: int = Field(
        0,
        ge=0,
        description="Number of competitor documents containing this term",
    )
    is_missing: bool = Field(
        True,
        description="Whether the term is missing from user content",
    )
    category: str | None = Field(
        None,
        description="Optional category/theme for this term",
        examples=["product_feature", "benefit", "material"],
    )


class RecommendTermsRequest(BaseModel):
    """Request schema for term recommendations."""

    user_content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="User's content to analyze for missing terms",
        examples=["Coffee containers keep beans fresh in your kitchen."],
    )
    competitor_documents: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of competitor content documents (1-50 documents)",
        examples=[
            [
                "Vacuum sealed coffee storage with CO2 valve",
                "Airtight containers preserve aroma for months",
            ]
        ],
    )
    top_n: int = Field(
        20,
        ge=1,
        le=100,
        description="Number of recommended terms to return (1-100)",
    )
    include_bigrams: bool = Field(
        True,
        description="Whether to include two-word phrases in recommendations",
    )
    only_missing: bool = Field(
        True,
        description="Only recommend terms missing from user content (default: True)",
    )
    min_doc_frequency: int = Field(
        1,
        ge=1,
        description="Minimum number of competitor docs a term must appear in",
    )
    max_doc_frequency_ratio: float = Field(
        0.85,
        gt=0.0,
        le=1.0,
        description="Maximum ratio of docs a term can appear in (filters common terms)",
    )
    project_id: str | None = Field(
        None,
        description="Optional project ID for logging and caching context",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for logging context",
    )


class RecommendTermsResponse(BaseModel):
    """Response schema for term recommendations."""

    success: bool = Field(
        ...,
        description="Whether analysis completed successfully",
    )
    request_id: str = Field(
        ...,
        description="Request ID for debugging and tracing",
    )

    # Recommendations
    recommendations: list[RecommendedTermItem] = Field(
        default_factory=list,
        description="List of recommended terms, sorted by priority and score",
    )
    recommendation_count: int = Field(
        0,
        ge=0,
        description="Total number of recommendations returned",
    )

    # Analysis metadata
    user_term_count: int = Field(
        0,
        ge=0,
        description="Number of unique terms found in user content",
    )
    competitor_term_count: int = Field(
        0,
        ge=0,
        description="Total unique terms across competitor documents",
    )
    document_count: int = Field(
        0,
        ge=0,
        description="Number of competitor documents analyzed",
    )

    # Summary stats
    high_priority_count: int = Field(
        0,
        ge=0,
        description="Number of high priority recommendations",
    )
    medium_priority_count: int = Field(
        0,
        ge=0,
        description="Number of medium priority recommendations",
    )
    low_priority_count: int = Field(
        0,
        ge=0,
        description="Number of low priority recommendations",
    )

    # Error handling
    error: str | None = Field(
        None,
        description="Error message if analysis failed",
    )

    # Performance
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )
    cache_hit: bool = Field(
        False,
        description="Whether results were served from cache",
    )
