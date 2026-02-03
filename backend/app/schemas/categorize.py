"""Pydantic schemas for Categorize phase API endpoints.

Schemas for page categorization requests and responses:
- CategorizeRequest: Request to categorize a single page
- CategorizeBatchRequest: Request to categorize multiple pages
- CategorizeResponse: Response for categorization result
- CategorizedPageResponse: Response with categorization details
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Valid page categories for categorization
VALID_PAGE_CATEGORIES = frozenset(
    [
        "homepage",
        "product",
        "collection",
        "blog",
        "policy",
        "about",
        "contact",
        "faq",
        "account",
        "cart",
        "search",
        "other",
    ]
)


class CategorizeRequest(BaseModel):
    """Request schema for categorizing a single page."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="The page URL to categorize",
        examples=["https://example.com/products/widget"],
    )
    title: str | None = Field(
        None,
        max_length=500,
        description="Page title (improves accuracy)",
        examples=["Buy Widget Pro - Free Shipping"],
    )
    content: str | None = Field(
        None,
        max_length=100000,
        description="Page content/body text (improves accuracy)",
    )
    headings: list[str] | None = Field(
        None,
        description="List of heading texts from the page",
        examples=[["Product Details", "Add to Cart", "Customer Reviews"]],
    )
    json_ld_schema: str | None = Field(
        None,
        max_length=50000,
        description="JSON-LD schema content (highly improves accuracy)",
    )
    meta_description: str | None = Field(
        None,
        max_length=1000,
        description="Meta description from the page",
    )
    breadcrumbs: list[str] | None = Field(
        None,
        description="Breadcrumb trail texts",
        examples=[["Home", "Products", "Widget Pro"]],
    )
    force_llm: bool = Field(
        False,
        description="Force LLM categorization regardless of pattern confidence",
    )
    skip_llm: bool = Field(
        False,
        description="Skip LLM even if confidence is low (faster, potentially less accurate)",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate the URL has a valid format."""
        v = v.strip()
        if not v:
            raise ValueError("url cannot be empty")
        if not v.startswith(("http://", "https://", "/")):
            raise ValueError("url must start with http://, https://, or /")
        return v


class BatchPageRequest(BaseModel):
    """Single page in a batch categorization request."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="The page URL to categorize",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking (e.g., from crawled_pages)",
    )
    title: str | None = Field(
        None,
        max_length=500,
        description="Page title",
    )
    content: str | None = Field(
        None,
        max_length=100000,
        description="Page content/body text",
    )
    headings: list[str] | None = Field(
        None,
        description="List of heading texts",
    )
    json_ld_schema: str | None = Field(
        None,
        max_length=50000,
        description="JSON-LD schema content",
    )
    meta_description: str | None = Field(
        None,
        max_length=1000,
        description="Meta description",
    )
    breadcrumbs: list[str] | None = Field(
        None,
        description="Breadcrumb trail texts",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate the URL has a valid format."""
        v = v.strip()
        if not v:
            raise ValueError("url cannot be empty")
        if not v.startswith(("http://", "https://", "/")):
            raise ValueError("url must start with http://, https://, or /")
        return v


class CategorizePageIdsRequest(BaseModel):
    """Request schema for categorizing existing crawled pages by IDs."""

    page_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of crawled page IDs to categorize",
    )
    force_llm: bool = Field(
        False,
        description="Force LLM categorization regardless of pattern confidence",
    )
    skip_llm: bool = Field(
        False,
        description="Skip LLM even if confidence is low",
    )
    update_pages: bool = Field(
        True,
        description="Whether to update the crawled pages with new categories",
    )


class CategorizeAllRequest(BaseModel):
    """Request schema for categorizing all uncategorized pages in a project."""

    force_llm: bool = Field(
        False,
        description="Force LLM categorization regardless of pattern confidence",
    )
    skip_llm: bool = Field(
        False,
        description="Skip LLM even if confidence is low",
    )
    update_pages: bool = Field(
        True,
        description="Whether to update the crawled pages with new categories",
    )
    include_categorized: bool = Field(
        False,
        description="Re-categorize pages that already have a category",
    )
    batch_size: int = Field(
        10,
        ge=1,
        le=50,
        description="Number of pages per LLM batch",
    )


class CategorizeBatchRequest(BaseModel):
    """Request schema for batch categorization of multiple pages."""

    pages: list[BatchPageRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of pages to categorize",
    )
    force_llm: bool = Field(
        False,
        description="Force LLM categorization regardless of pattern confidence",
    )
    skip_llm: bool = Field(
        False,
        description="Skip LLM even if confidence is low",
    )


class ContentSignalResponse(BaseModel):
    """Response schema for a content signal detection."""

    signal_type: str = Field(
        ..., description="Type of signal (title, heading, schema, etc.)"
    )
    category: str = Field(..., description="Category indicated by signal")
    confidence_boost: float = Field(
        ..., description="Confidence boost from this signal"
    )
    matched_text: str | None = Field(None, description="Text that matched the pattern")


class ContentAnalysisResponse(BaseModel):
    """Response schema for content analysis results."""

    url_category: str = Field(..., description="Category from URL patterns")
    url_confidence: float = Field(..., description="Confidence from URL patterns")
    signals: list[ContentSignalResponse] = Field(
        default_factory=list, description="Detected content signals"
    )
    boosted_confidence: float = Field(
        ..., description="Final confidence after boosting"
    )
    final_category: str = Field(
        ..., description="Final category (may differ if signals override)"
    )


class CategorizeResponse(BaseModel):
    """Response schema for categorization result."""

    success: bool = Field(..., description="Whether categorization succeeded")
    url: str = Field(..., description="The categorized URL")
    category: str = Field(..., description="Final assigned category")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)"
    )
    tier: str = Field(
        ..., description="Which tier was used ('pattern', 'llm', 'fallback')"
    )
    url_category: str = Field(..., description="Category from URL patterns only")
    url_confidence: float = Field(..., description="Confidence from URL patterns only")
    content_analysis: ContentAnalysisResponse | None = Field(
        None, description="Full content analysis results"
    )
    llm_result: dict[str, Any] | None = Field(
        None, description="LLM categorization result (if used)"
    )
    labels: list[str] = Field(
        default_factory=list, description="Additional labels from LLM"
    )
    reasoning: str | None = Field(None, description="LLM reasoning for category choice")
    error: str | None = Field(None, description="Error message if failed")
    duration_ms: float = Field(..., description="Total processing time in milliseconds")


class CategorizedPageResponse(BaseModel):
    """Response schema for a categorized page with page details."""

    model_config = ConfigDict(from_attributes=True)

    page_id: str = Field(..., description="Page UUID")
    url: str = Field(..., description="Page URL")
    title: str | None = Field(None, description="Page title")
    category: str = Field(..., description="Assigned category")
    confidence: float = Field(..., description="Categorization confidence")
    tier: str = Field(..., description="Which tier was used")
    labels: list[str] = Field(default_factory=list, description="Additional labels")
    updated: bool = Field(..., description="Whether the page record was updated")


class CategorizePageIdsResponse(BaseModel):
    """Response schema for categorizing pages by IDs."""

    total: int = Field(..., description="Total pages requested")
    categorized: int = Field(..., description="Pages successfully categorized")
    failed: int = Field(..., description="Pages that failed")
    results: list[CategorizedPageResponse] = Field(..., description="Per-page results")
    duration_ms: float = Field(..., description="Total processing time")


class CategorizeAllResponse(BaseModel):
    """Response schema for categorizing all pages in a project."""

    total: int = Field(..., description="Total pages processed")
    categorized: int = Field(..., description="Pages successfully categorized")
    failed: int = Field(..., description="Pages that failed")
    skipped: int = Field(..., description="Pages skipped (already categorized)")
    category_counts: dict[str, int] = Field(
        default_factory=dict, description="Count per category"
    )
    tier_counts: dict[str, int] = Field(
        default_factory=dict, description="Count per tier (pattern/llm/fallback)"
    )
    duration_ms: float = Field(..., description="Total processing time")


class CategorizeStatsResponse(BaseModel):
    """Response schema for categorization statistics."""

    project_id: str = Field(..., description="Project UUID")
    total_pages: int = Field(..., description="Total crawled pages")
    categorized_pages: int = Field(..., description="Pages with a category")
    uncategorized_pages: int = Field(..., description="Pages without a category")
    category_counts: dict[str, int] = Field(
        default_factory=dict, description="Count per category"
    )
    valid_categories: list[str] = Field(
        default_factory=list, description="List of valid category names"
    )


class UpdateCategoryRequest(BaseModel):
    """Request schema for manually updating a page's category."""

    category: str = Field(
        ...,
        description="New category to assign",
    )
    labels: list[str] | None = Field(
        None,
        description="Optional labels to add/update",
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Validate the category is a valid value."""
        v = v.strip().lower()
        if v not in VALID_PAGE_CATEGORIES:
            valid = ", ".join(sorted(VALID_PAGE_CATEGORIES))
            raise ValueError(f"category must be one of: {valid}")
        return v


class UpdateCategoryResponse(BaseModel):
    """Response schema for updating a page's category."""

    page_id: str = Field(..., description="Page UUID")
    url: str = Field(..., description="Page URL")
    old_category: str | None = Field(None, description="Previous category")
    new_category: str = Field(..., description="New category")
    labels: list[str] = Field(default_factory=list, description="Page labels")
    updated_at: datetime = Field(..., description="Update timestamp")
