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
