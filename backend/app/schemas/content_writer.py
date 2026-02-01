"""Pydantic schemas for Phase 5B Content Writer API endpoints.

Schemas for generating SEO content with Skill Bible rules:
- ContentWriterRequest: Generate content for a single page
- ContentWriterResponse: Generated content with H1, title, meta, descriptions
- InternalLinkItem: Internal link with URL and anchor text
- GeneratedContentItem: The actual content fields

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

from typing import Any

from pydantic import BaseModel, Field, field_validator

# =============================================================================
# INTERNAL LINK MODEL
# =============================================================================


class InternalLinkItem(BaseModel):
    """An internal link for content insertion."""

    url: str = Field(
        ...,
        description="The URL path for the link",
        examples=["/collections/leather-wallets", "/collections/mens-accessories"],
    )
    anchor_text: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Descriptive anchor text for the link",
        examples=["Premium Leather Wallets", "Men's Accessories"],
    )
    link_type: str = Field(
        "related",
        description="Link type: 'related' for related collections, 'priority' for priority pages",
        pattern="^(related|priority)$",
    )


# =============================================================================
# GENERATED CONTENT MODEL
# =============================================================================


class GeneratedContentItem(BaseModel):
    """Generated content fields from Phase 5B."""

    h1: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="H1 heading (3-7 words, Title Case, includes keyword)",
        examples=["Premium Leather Wallets"],
    )
    title_tag: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Title tag (under 60 chars, format: Keyword | Brand)",
        examples=["Premium Leather Wallets | Acme Co"],
    )
    meta_description: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Meta description (150-160 chars with soft CTA)",
        examples=[
            "Discover our collection of premium leather wallets. "
            "Handcrafted with full-grain leather for lasting quality. Shop now."
        ],
    )
    top_description: str = Field(
        ...,
        description="Short intro paragraph for above the fold (HTML)",
    )
    bottom_description: str = Field(
        ...,
        description="Full bottom description (300-450 words, HTML with h2, h3, p, a tags)",
    )
    word_count: int = Field(
        ...,
        ge=0,
        description="Word count of bottom description",
    )


# =============================================================================
# CONTENT WRITER REQUEST
# =============================================================================


class ContentWriterRequest(BaseModel):
    """Request schema for Phase 5B content generation."""

    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Primary keyword for content generation",
        examples=["leather wallets", "coffee storage containers"],
    )
    url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Target page URL path",
        examples=["/collections/leather-wallets"],
    )
    brand_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Brand name for title tag",
        examples=["Acme Co", "Premium Goods"],
    )
    research_brief: dict[str, Any] | None = Field(
        None,
        description="Research brief from Phase 5A (main_angle, benefits, priority_questions)",
    )
    brand_voice: dict[str, Any] | None = Field(
        None,
        description="Brand voice config from V2 schema (tone, personality, writing_style)",
    )
    related_links: list[InternalLinkItem] = Field(
        default_factory=list,
        max_length=10,
        description="Related collection links (max 3 will be used)",
    )
    priority_links: list[InternalLinkItem] = Field(
        default_factory=list,
        max_length=10,
        description="Priority page links (max 3 will be used)",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        """Validate and normalize keyword."""
        v = v.strip()
        if not v:
            raise ValueError("Keyword cannot be empty")
        return v

    @field_validator("brand_name")
    @classmethod
    def validate_brand_name(cls, v: str) -> str:
        """Validate and normalize brand name."""
        v = v.strip()
        if not v:
            raise ValueError("Brand name cannot be empty")
        return v


# =============================================================================
# CONTENT WRITER RESPONSE
# =============================================================================


class ContentWriterResponse(BaseModel):
    """Response schema for Phase 5B content generation."""

    success: bool = Field(
        ...,
        description="Whether content was generated successfully",
    )
    keyword: str = Field(
        ...,
        description="The keyword this content is for",
    )

    # Generated content
    content: GeneratedContentItem | None = Field(
        None,
        description="Generated content (null if failed)",
    )

    # Error handling
    error: str | None = Field(
        None,
        description="Error message if failed",
    )

    # Performance and metadata
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )
    input_tokens: int | None = Field(
        None,
        description="LLM input tokens used",
    )
    output_tokens: int | None = Field(
        None,
        description="LLM output tokens used",
    )
    request_id: str | None = Field(
        None,
        description="Claude API request ID for debugging",
    )


# =============================================================================
# BATCH CONTENT WRITER
# =============================================================================


class ContentWriterBatchItemRequest(BaseModel):
    """Single item in batch content generation request."""

    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Primary keyword",
    )
    url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Target page URL path",
    )
    research_brief: dict[str, Any] | None = Field(
        None,
        description="Research brief from Phase 5A",
    )
    related_links: list[InternalLinkItem] = Field(
        default_factory=list,
        description="Related collection links",
    )
    priority_links: list[InternalLinkItem] = Field(
        default_factory=list,
        description="Priority page links",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID",
    )


class ContentWriterBatchRequest(BaseModel):
    """Request schema for batch content generation."""

    brand_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Brand name (shared for all pages)",
    )
    brand_voice: dict[str, Any] | None = Field(
        None,
        description="Brand voice config (shared for all pages)",
    )
    items: list[ContentWriterBatchItemRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Pages to generate content for",
    )
    max_concurrent: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum concurrent content generations",
    )

    @field_validator("items")
    @classmethod
    def validate_items(cls, v: list[ContentWriterBatchItemRequest]) -> list[ContentWriterBatchItemRequest]:
        """Validate items list."""
        if not v:
            raise ValueError("At least one item is required")
        return v


class ContentWriterBatchItemResponse(BaseModel):
    """Response for a single item in batch content generation."""

    keyword: str = Field(..., description="The keyword")
    url: str = Field(..., description="The URL path")
    success: bool = Field(..., description="Whether content was generated")
    h1: str | None = Field(None, description="Generated H1 if successful")
    word_count: int | None = Field(None, description="Bottom description word count")
    error: str | None = Field(None, description="Error message if failed")


class ContentWriterBatchResponse(BaseModel):
    """Response schema for batch content generation."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some may have failed)",
    )
    results: list[ContentWriterBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each item",
    )
    total_items: int = Field(0, description="Total items in request")
    successful_items: int = Field(0, description="Items with generated content")
    failed_items: int = Field(0, description="Items that failed")
    error: str | None = Field(None, description="Error if batch failed")
    duration_ms: float = Field(..., description="Total processing time")
