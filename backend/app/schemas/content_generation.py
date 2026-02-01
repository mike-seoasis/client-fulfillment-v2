"""Pydantic schemas for Content Generation phase API endpoints.

Schemas for content generation operations:
- ContentGenerationRequest: Generate content for a single page
- ContentGenerationResponse: Generated content with metadata
- ContentGenerationBatchRequest: Generate content for multiple pages
- ContentGenerationBatchResponse: Batch results with statistics

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
# GENERATED CONTENT MODEL
# =============================================================================


class GeneratedContentOutput(BaseModel):
    """Generated content fields from content generation."""

    h1: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="H1 heading for the page",
        examples=["Premium Leather Wallets"],
    )
    title_tag: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Title tag for SEO (under 60 chars recommended)",
        examples=["Premium Leather Wallets | Acme Co"],
    )
    meta_description: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Meta description for SEO (150-160 chars recommended)",
        examples=[
            "Discover our collection of premium leather wallets. "
            "Handcrafted with full-grain leather for lasting quality. Shop now."
        ],
    )
    body_content: str = Field(
        ...,
        description="Main body content (HTML)",
    )
    word_count: int = Field(
        ...,
        ge=0,
        description="Word count of body content",
    )


# =============================================================================
# CONTENT GENERATION REQUEST
# =============================================================================


class ContentGenerationRequest(BaseModel):
    """Request schema for content generation."""

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
        description="Brand name for title tag and content",
        examples=["Acme Co", "Premium Goods"],
    )
    content_type: str = Field(
        "collection",
        description="Type of content to generate: collection, product, blog, landing",
        pattern="^(collection|product|blog|landing)$",
    )
    tone: str = Field(
        "professional",
        max_length=100,
        description="Desired tone for the content",
        examples=["professional", "friendly", "casual", "luxury"],
    )
    target_word_count: int = Field(
        400,
        ge=100,
        le=2000,
        description="Target word count for body content",
    )
    context: dict[str, Any] | None = Field(
        None,
        description="Additional context for content generation (research briefs, brand voice, etc.)",
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
# CONTENT GENERATION RESPONSE
# =============================================================================


class ContentGenerationResponse(BaseModel):
    """Response schema for content generation."""

    success: bool = Field(
        ...,
        description="Whether content was generated successfully",
    )
    keyword: str = Field(
        ...,
        description="The keyword this content is for",
    )
    content_type: str = Field(
        ...,
        description="Type of content generated",
    )

    # Generated content
    content: GeneratedContentOutput | None = Field(
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
        description="Request ID for debugging",
    )


# =============================================================================
# BATCH CONTENT GENERATION
# =============================================================================


class ContentGenerationBatchItemRequest(BaseModel):
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
    content_type: str = Field(
        "collection",
        description="Type of content to generate",
        pattern="^(collection|product|blog|landing)$",
    )
    target_word_count: int = Field(
        400,
        ge=100,
        le=2000,
        description="Target word count",
    )
    context: dict[str, Any] | None = Field(
        None,
        description="Additional context for this item",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID",
    )


class ContentGenerationBatchRequest(BaseModel):
    """Request schema for batch content generation."""

    brand_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Brand name (shared for all items)",
    )
    tone: str = Field(
        "professional",
        max_length=100,
        description="Desired tone (shared for all items)",
    )
    items: list[ContentGenerationBatchItemRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Items to generate content for",
    )
    max_concurrent: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum concurrent content generations",
    )

    @field_validator("items")
    @classmethod
    def validate_items(
        cls, v: list[ContentGenerationBatchItemRequest]
    ) -> list[ContentGenerationBatchItemRequest]:
        """Validate items list."""
        if not v:
            raise ValueError("At least one item is required")
        return v


class ContentGenerationBatchItemResponse(BaseModel):
    """Response for a single item in batch content generation."""

    keyword: str = Field(..., description="The keyword")
    url: str = Field(..., description="The URL path")
    content_type: str = Field(..., description="Content type generated")
    success: bool = Field(..., description="Whether content was generated")
    h1: str | None = Field(None, description="Generated H1 if successful")
    word_count: int | None = Field(None, description="Body content word count")
    error: str | None = Field(None, description="Error message if failed")


class ContentGenerationBatchResponse(BaseModel):
    """Response schema for batch content generation."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some may have failed)",
    )
    results: list[ContentGenerationBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each item",
    )
    total_items: int = Field(0, description="Total items in request")
    successful_items: int = Field(0, description="Items with generated content")
    failed_items: int = Field(0, description="Items that failed")
    error: str | None = Field(None, description="Error if batch failed")
    duration_ms: float = Field(..., description="Total processing time")
    request_id: str | None = Field(None, description="Request ID for debugging")


# =============================================================================
# REGENERATION ENDPOINTS
# =============================================================================


class RegenerateRequest(BaseModel):
    """Request schema for regenerating content for a failed page."""

    page_id: str = Field(
        ...,
        min_length=1,
        description="ID of the page to regenerate content for",
    )
    brand_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Brand name for title tag and content",
        examples=["Acme Co", "Premium Goods"],
    )
    tone: str = Field(
        "professional",
        max_length=100,
        description="Desired tone for the content",
        examples=["professional", "friendly", "casual", "luxury"],
    )
    target_word_count: int = Field(
        400,
        ge=100,
        le=2000,
        description="Target word count for body content",
    )
    context: dict[str, Any] | None = Field(
        None,
        description="Additional context for content generation",
    )

    @field_validator("page_id")
    @classmethod
    def validate_page_id(cls, v: str) -> str:
        """Validate and normalize page ID."""
        v = v.strip()
        if not v:
            raise ValueError("Page ID cannot be empty")
        return v

    @field_validator("brand_name")
    @classmethod
    def validate_brand_name(cls, v: str) -> str:
        """Validate and normalize brand name."""
        v = v.strip()
        if not v:
            raise ValueError("Brand name cannot be empty")
        return v


class RegenerateResponse(BaseModel):
    """Response schema for single page regeneration."""

    success: bool = Field(
        ...,
        description="Whether regeneration was successful",
    )
    page_id: str = Field(
        ...,
        description="ID of the page that was regenerated",
    )
    keyword: str | None = Field(
        None,
        description="The keyword this content is for",
    )
    content_type: str | None = Field(
        None,
        description="Type of content generated",
    )

    # Generated content
    content: GeneratedContentOutput | None = Field(
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
        description="Request ID for debugging",
    )


class RegenerateBatchItemRequest(BaseModel):
    """Single item in batch regeneration request."""

    page_id: str = Field(
        ...,
        min_length=1,
        description="ID of the page to regenerate",
    )
    target_word_count: int = Field(
        400,
        ge=100,
        le=2000,
        description="Target word count",
    )
    context: dict[str, Any] | None = Field(
        None,
        description="Additional context for this item",
    )


class RegenerateBatchRequest(BaseModel):
    """Request schema for batch regeneration of failed pages."""

    brand_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Brand name (shared for all items)",
    )
    tone: str = Field(
        "professional",
        max_length=100,
        description="Desired tone (shared for all items)",
    )
    items: list[RegenerateBatchItemRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Pages to regenerate content for",
    )
    max_concurrent: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum concurrent regenerations",
    )

    @field_validator("items")
    @classmethod
    def validate_items(
        cls, v: list[RegenerateBatchItemRequest]
    ) -> list[RegenerateBatchItemRequest]:
        """Validate items list."""
        if not v:
            raise ValueError("At least one item is required")
        return v


class RegenerateBatchItemResponse(BaseModel):
    """Response for a single item in batch regeneration."""

    page_id: str = Field(..., description="The page ID")
    keyword: str | None = Field(None, description="The keyword")
    url: str | None = Field(None, description="The URL path")
    content_type: str | None = Field(None, description="Content type generated")
    success: bool = Field(..., description="Whether regeneration succeeded")
    h1: str | None = Field(None, description="Generated H1 if successful")
    word_count: int | None = Field(None, description="Body content word count")
    error: str | None = Field(None, description="Error message if failed")


class RegenerateBatchResponse(BaseModel):
    """Response schema for batch regeneration."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some may have failed)",
    )
    results: list[RegenerateBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each item",
    )
    total_items: int = Field(0, description="Total items in request")
    successful_items: int = Field(0, description="Items with regenerated content")
    failed_items: int = Field(0, description="Items that failed")
    error: str | None = Field(None, description="Error if batch failed")
    duration_ms: float = Field(..., description="Total processing time")
    request_id: str | None = Field(None, description="Request ID for debugging")
