"""Pydantic schemas for Phase 5C LLM QA Fix API endpoints.

Schemas for LLM-powered content correction:
- LLMQAFixRequest: Content and issues to fix
- LLMQAFixResponse: Fixed content with change details
- LLMQAFixBatchRequest/Response: Batch fixing support

The LLM QA Fix service handles patterns that regex might miss,
making minimal corrections while preserving structure and links.

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
# ISSUE TYPES
# =============================================================================


class IssueToFix(BaseModel):
    """Describes a specific issue that needs to be fixed."""

    issue_type: str = Field(
        ...,
        description="Type of issue (negation_pattern, banned_word, em_dash, etc.)",
        examples=["negation_pattern", "banned_word", "em_dash", "triplet_pattern"],
    )
    matched_text: str = Field(
        ...,
        description="The specific text that was flagged",
        examples=["aren't just wallets, they're investments", "delve"],
    )
    position: int | None = Field(
        None,
        ge=0,
        description="Character position where the issue occurs (optional)",
    )
    suggestion: str | None = Field(
        None,
        description="Suggested fix from the content quality service",
    )


# =============================================================================
# FIX RESULTS
# =============================================================================


class FixApplied(BaseModel):
    """Describes a fix that was applied to the content."""

    issue_type: str = Field(
        ...,
        description="Type of issue that was fixed",
    )
    original_text: str = Field(
        ...,
        description="The original text that was problematic",
    )
    fixed_text: str = Field(
        ...,
        description="The corrected text",
    )
    explanation: str = Field(
        "",
        description="Brief explanation of the change",
    )


# =============================================================================
# LLM QA FIX REQUEST
# =============================================================================


class LLMQAFixRequest(BaseModel):
    """Request schema for Phase 5C LLM QA fix."""

    # Content fields (same as content quality)
    h1: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="H1 heading",
        examples=["Premium Leather Wallets"],
    )
    title_tag: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Title tag",
        examples=["Premium Leather Wallets | Acme Co"],
    )
    meta_description: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Meta description",
    )
    top_description: str = Field(
        "",
        description="Above-the-fold description (HTML)",
    )
    bottom_description: str = Field(
        ...,
        min_length=1,
        description="Full bottom description to fix (HTML)",
    )

    # Issues to fix
    issues: list[IssueToFix] = Field(
        ...,
        min_length=1,
        description="Issues detected by content quality check that need fixing",
    )

    # Primary keyword for context
    primary_keyword: str = Field(
        ...,
        min_length=1,
        description="Primary keyword for the page (helps LLM preserve keyword usage)",
    )

    # Tracking
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )
    content_id: str | None = Field(
        None,
        description="Optional content ID for tracking",
    )


# =============================================================================
# LLM QA FIX RESPONSE
# =============================================================================


class LLMQAFixResponse(BaseModel):
    """Response schema for Phase 5C LLM QA fix."""

    success: bool = Field(
        ...,
        description="Whether the fix operation completed successfully",
    )

    # Fixed content (only bottom_description is modified)
    fixed_bottom_description: str | None = Field(
        None,
        description="The corrected bottom description (null if failed)",
    )

    # Fix details
    issues_found: list[str] = Field(
        default_factory=list,
        description="Issues that were identified in the content",
    )
    fixes_applied: list[FixApplied] = Field(
        default_factory=list,
        description="Details of each fix that was made",
    )
    fix_count: int = Field(
        0,
        ge=0,
        description="Number of fixes applied",
    )

    # Metadata
    content_id: str | None = Field(
        None,
        description="Content ID that was fixed",
    )
    page_id: str | None = Field(
        None,
        description="Page ID that was fixed",
    )

    # LLM usage
    input_tokens: int | None = Field(
        None,
        description="LLM input tokens used",
    )
    output_tokens: int | None = Field(
        None,
        description="LLM output tokens used",
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
# BATCH LLM QA FIX
# =============================================================================


class LLMQAFixBatchItemRequest(BaseModel):
    """Single item in batch LLM QA fix request."""

    h1: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="H1 heading",
    )
    title_tag: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Title tag",
    )
    meta_description: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Meta description",
    )
    top_description: str = Field(
        "",
        description="Above-the-fold description",
    )
    bottom_description: str = Field(
        ...,
        min_length=1,
        description="Bottom description to fix",
    )
    issues: list[IssueToFix] = Field(
        ...,
        min_length=1,
        description="Issues to fix",
    )
    primary_keyword: str = Field(
        ...,
        min_length=1,
        description="Primary keyword for the page",
    )
    page_id: str | None = Field(None, description="Optional page ID")
    content_id: str | None = Field(None, description="Optional content ID")


class LLMQAFixBatchRequest(BaseModel):
    """Request schema for batch LLM QA fix."""

    items: list[LLMQAFixBatchItemRequest] = Field(
        ...,
        min_length=1,
        max_length=10,  # Limit batch size for LLM calls
        description="Content items to fix (max 10 per batch due to LLM costs)",
    )


class LLMQAFixBatchItemResponse(BaseModel):
    """Response for a single item in batch LLM QA fix."""

    content_id: str | None = Field(None, description="Content ID")
    page_id: str | None = Field(None, description="Page ID")
    success: bool = Field(..., description="Whether fix completed")
    fix_count: int = Field(0, description="Number of fixes applied")
    fixed_bottom_description: str | None = Field(
        None,
        description="Fixed content (null if failed)",
    )
    error: str | None = Field(None, description="Error message if failed")


class LLMQAFixBatchResponse(BaseModel):
    """Response schema for batch LLM QA fix."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some may have failed)",
    )
    results: list[LLMQAFixBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each item",
    )
    total_items: int = Field(0, description="Total items in request")
    success_count: int = Field(0, description="Items fixed successfully")
    error_count: int = Field(0, description="Items with errors")
    total_fixes: int = Field(0, description="Total fixes applied across all items")

    # Token usage
    total_input_tokens: int = Field(0, description="Total LLM input tokens")
    total_output_tokens: int = Field(0, description="Total LLM output tokens")

    error: str | None = Field(None, description="Error if batch failed")
    duration_ms: float = Field(..., description="Total processing time")
