"""Pydantic schemas for Phase 5C Word Count API endpoints.

Schemas for word count validation (300-450 words required):
- ContentWordCountRequest: Validate word count for content
- ContentWordCountResponse: Validation result with word count details
- ContentWordCountBatchRequest/Response: Batch word count validation

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
# WORD COUNT REQUEST
# =============================================================================


class ContentWordCountRequest(BaseModel):
    """Request schema for Phase 5C word count validation."""

    content: str = Field(
        ...,
        min_length=1,
        description="Content to validate (may contain HTML)",
        examples=["<p>Your collection page content here...</p>"],
    )
    field_name: str = Field(
        "bottom_description",
        description="Name of the field being validated",
        examples=["bottom_description"],
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )
    content_id: str | None = Field(
        None,
        description="Optional content ID for tracking",
    )


# =============================================================================
# WORD COUNT RESPONSE
# =============================================================================


class ContentWordCountResponse(BaseModel):
    """Response schema for Phase 5C word count validation."""

    success: bool = Field(
        ...,
        description="Whether validation completed successfully",
    )
    content_id: str | None = Field(
        None,
        description="Content ID that was checked",
    )
    field_name: str | None = Field(
        None,
        description="Name of the field that was validated",
    )

    # Word count results
    word_count: int = Field(
        0,
        ge=0,
        description="Number of words in the content",
    )
    min_required: int = Field(
        300,
        ge=0,
        description="Minimum words required (300)",
    )
    max_allowed: int = Field(
        450,
        ge=0,
        description="Maximum words allowed (450)",
    )
    is_valid: bool = Field(
        ...,
        description="Whether word count is within required range",
    )

    # Feedback
    error: str | None = Field(
        None,
        description="Error message if validation failed",
    )
    suggestion: str | None = Field(
        None,
        description="Suggestion for fixing word count",
    )

    # Performance
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


# =============================================================================
# BATCH WORD COUNT
# =============================================================================


class ContentWordCountBatchItemRequest(BaseModel):
    """Single item in batch word count validation request."""

    content: str = Field(
        ...,
        min_length=1,
        description="Content to validate",
    )
    field_name: str = Field(
        "bottom_description",
        description="Field name",
    )
    page_id: str | None = Field(None, description="Optional page ID")
    content_id: str | None = Field(None, description="Optional content ID")


class ContentWordCountBatchRequest(BaseModel):
    """Request schema for batch word count validation."""

    items: list[ContentWordCountBatchItemRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Content items to validate",
    )


class ContentWordCountBatchItemResponse(BaseModel):
    """Response for a single item in batch word count validation."""

    content_id: str | None = Field(None, description="Content ID")
    page_id: str | None = Field(None, description="Page ID")
    success: bool = Field(..., description="Whether check completed")
    word_count: int = Field(0, ge=0, description="Number of words")
    is_valid: bool = Field(..., description="Whether word count is valid")
    error: str | None = Field(None, description="Error message if failed")


class ContentWordCountBatchResponse(BaseModel):
    """Response schema for batch word count validation."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some may have failed)",
    )
    results: list[ContentWordCountBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each item",
    )
    total_items: int = Field(0, description="Total items in request")
    valid_count: int = Field(0, description="Items with valid word count")
    invalid_count: int = Field(0, description="Items with invalid word count")
    error_count: int = Field(0, description="Items with errors")
    average_word_count: float = Field(0.0, description="Average word count across items")
    error: str | None = Field(None, description="Error if batch failed")
    duration_ms: float = Field(..., description="Total processing time")
