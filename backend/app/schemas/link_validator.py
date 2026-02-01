"""Pydantic schemas for Phase 5C Link Validator API endpoints.

Schemas for link validation against collection registry:
- LinkValidationRequest: Validate links from generated content
- LinkValidationResponse: Validation results with detailed status
- CollectionRegistryItem: Registry entry for valid collection pages
- LinkValidationBatchRequest/Response: Batch link validation

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
# COLLECTION REGISTRY MODELS
# =============================================================================


class CollectionRegistryItem(BaseModel):
    """An entry representing a valid collection page in the registry."""

    url: str = Field(
        ...,
        min_length=1,
        description="The canonical URL of the collection page",
        examples=["https://example.com/collections/wallets"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable name of the collection",
        examples=["Leather Wallets"],
    )
    labels: list[str] = Field(
        default_factory=list,
        description="Labels/tags for this collection",
        examples=[["accessories", "leather", "wallets"]],
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )


# =============================================================================
# LINK MODELS
# =============================================================================


class LinkItem(BaseModel):
    """A link to be validated against the collection registry."""

    url: str = Field(
        ...,
        min_length=1,
        description="The URL of the link to validate",
        examples=["/collections/wallets", "https://example.com/collections/bags"],
    )
    anchor_text: str = Field(
        "",
        max_length=500,
        description="The anchor text of the link",
        examples=["Shop Wallets", "View Collection"],
    )
    link_type: str = Field(
        "internal",
        max_length=50,
        description="Type of link (e.g., 'related', 'priority', 'internal')",
        examples=["related", "priority", "internal"],
    )


class LinkValidationResultItem(BaseModel):
    """Result of validating a single link."""

    url: str = Field(
        ...,
        description="The original URL that was validated",
    )
    anchor_text: str = Field(
        "",
        description="The anchor text of the link",
    )
    is_valid: bool = Field(
        ...,
        description="Whether the link is valid (exists in registry)",
    )
    is_internal: bool = Field(
        True,
        description="Whether the link is internal to the site",
    )
    normalized_url: str | None = Field(
        None,
        description="The normalized form of the URL (for internal links)",
    )
    error: str | None = Field(
        None,
        description="Error message if validation failed",
    )
    suggestion: str | None = Field(
        None,
        description="Suggestion for fixing invalid links",
    )


# =============================================================================
# LINK VALIDATION REQUEST
# =============================================================================


class LinkValidationRequest(BaseModel):
    """Request schema for Phase 5C link validation."""

    links: list[LinkItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Links to validate",
    )
    registry: list[CollectionRegistryItem] = Field(
        ...,
        min_length=1,
        description="Collection registry entries (valid pages)",
    )
    site_domain: str | None = Field(
        None,
        description="Domain of the site (for determining internal links)",
        examples=["example.com"],
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
# LINK VALIDATION RESPONSE
# =============================================================================


class LinkValidationResponse(BaseModel):
    """Response schema for Phase 5C link validation."""

    success: bool = Field(
        ...,
        description="Whether validation completed successfully",
    )

    # Validation results
    results: list[LinkValidationResultItem] = Field(
        default_factory=list,
        description="Individual validation results for each link",
    )

    # Summary statistics
    total_links: int = Field(
        0,
        ge=0,
        description="Total number of links validated",
    )
    valid_count: int = Field(
        0,
        ge=0,
        description="Number of valid links",
    )
    invalid_count: int = Field(
        0,
        ge=0,
        description="Number of invalid links",
    )
    external_count: int = Field(
        0,
        ge=0,
        description="Number of external links (not validated against registry)",
    )
    validation_score: float = Field(
        100.0,
        ge=0,
        le=100,
        description="Percentage of valid internal links (0-100)",
    )
    passed_validation: bool = Field(
        True,
        description="Whether all internal links are valid",
    )

    # Error handling
    error: str | None = Field(
        None,
        description="Error message if validation failed",
    )

    # Performance
    duration_ms: float = Field(
        0.0,
        description="Processing time in milliseconds",
    )


# =============================================================================
# BATCH LINK VALIDATION
# =============================================================================


class BatchLinkValidationItemRequest(BaseModel):
    """Single item in batch link validation request."""

    links: list[LinkItem] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Links to validate for this content",
    )
    page_id: str | None = Field(None, description="Optional page ID")
    content_id: str | None = Field(None, description="Optional content ID")


class BatchLinkValidationRequest(BaseModel):
    """Request schema for batch link validation."""

    items: list[BatchLinkValidationItemRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Content items with links to validate",
    )
    registry: list[CollectionRegistryItem] = Field(
        ...,
        min_length=1,
        description="Shared collection registry entries",
    )
    site_domain: str | None = Field(
        None,
        description="Domain of the site",
        examples=["example.com"],
    )


class BatchLinkValidationItemResponse(BaseModel):
    """Response for a single item in batch link validation."""

    content_id: str | None = Field(None, description="Content ID")
    page_id: str | None = Field(None, description="Page ID")
    success: bool = Field(..., description="Whether validation completed")
    valid_count: int = Field(0, description="Number of valid links")
    invalid_count: int = Field(0, description="Number of invalid links")
    external_count: int = Field(0, description="Number of external links")
    validation_score: float = Field(100.0, description="Validation score 0-100")
    passed_validation: bool = Field(True, description="Whether all internal links are valid")
    invalid_urls: list[str] = Field(default_factory=list, description="List of invalid URLs")
    error: str | None = Field(None, description="Error message if failed")


class BatchLinkValidationResponse(BaseModel):
    """Response schema for batch link validation."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some may have failed)",
    )
    results: list[BatchLinkValidationItemResponse] = Field(
        default_factory=list,
        description="Results for each item",
    )
    total_items: int = Field(0, description="Total items in request")
    passed_count: int = Field(0, description="Items passing validation")
    failed_count: int = Field(0, description="Items failing validation")
    error_count: int = Field(0, description="Items with errors")
    average_score: float = Field(0.0, description="Average validation score")
    error: str | None = Field(None, description="Error if batch failed")
    duration_ms: float = Field(..., description="Total processing time")
