"""Pydantic schemas for Label phase API endpoints.

Schemas for label generation requests and responses:
- LabelGenerateRequest: Request to generate labels for a collection
- LabelBatchRequest: Request to generate labels for multiple collections
- LabelGenerateResponse: Response with generated labels
- LabelBatchResponse: Response with batch results
- LabelStatsResponse: Statistics about labeling for a project
"""

from pydantic import BaseModel, Field, field_validator


class LabelGenerateRequest(BaseModel):
    """Request schema for generating labels for a collection of pages."""

    urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of page URLs in the collection",
        examples=[
            [
                "https://example.com/products/widget",
                "https://example.com/products/gadget",
            ]
        ],
    )
    titles: list[str] | None = Field(
        None,
        max_length=1000,
        description="List of page titles (optional, improves accuracy)",
        examples=[["Widget Pro", "Gadget Plus"]],
    )
    categories: list[str] | None = Field(
        None,
        max_length=1000,
        description="List of page categories (optional, improves accuracy)",
        examples=[["product", "product"]],
    )
    content_snippets: list[str] | None = Field(
        None,
        max_length=100,
        description="List of content snippets for LLM (optional, max 500 chars each)",
    )
    force_llm: bool = Field(
        False,
        description="Force LLM labeling regardless of pattern confidence",
    )
    skip_llm: bool = Field(
        False,
        description="Skip LLM even if confidence is low (faster, uses patterns only)",
    )

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        """Validate URLs have valid format."""
        validated = []
        for url in v:
            url = url.strip()
            if not url:
                continue
            if not url.startswith(("http://", "https://", "/")):
                raise ValueError(
                    f"URL must start with http://, https://, or /: {url[:50]}"
                )
            validated.append(url)
        if not validated:
            raise ValueError("At least one valid URL is required")
        return validated


class BatchCollectionRequest(BaseModel):
    """Single collection in a batch label generation request."""

    collection_id: str | None = Field(
        None,
        description="Optional collection identifier for tracking",
    )
    urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of page URLs in the collection",
    )
    titles: list[str] | None = Field(
        None,
        max_length=1000,
        description="List of page titles",
    )
    categories: list[str] | None = Field(
        None,
        max_length=1000,
        description="List of page categories",
    )
    content_snippets: list[str] | None = Field(
        None,
        max_length=100,
        description="List of content snippets",
    )

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        """Validate URLs have valid format."""
        validated = []
        for url in v:
            url = url.strip()
            if not url:
                continue
            if not url.startswith(("http://", "https://", "/")):
                raise ValueError(
                    f"URL must start with http://, https://, or /: {url[:50]}"
                )
            validated.append(url)
        if not validated:
            raise ValueError("At least one valid URL is required")
        return validated


class LabelBatchRequest(BaseModel):
    """Request schema for batch label generation."""

    collections: list[BatchCollectionRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of collections to generate labels for",
    )
    max_concurrent: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum concurrent label generation operations",
    )
    force_llm: bool = Field(
        False,
        description="Force LLM labeling regardless of pattern confidence",
    )
    skip_llm: bool = Field(
        False,
        description="Skip LLM even if confidence is low",
    )


class LabelPageIdsRequest(BaseModel):
    """Request schema for generating labels for existing crawled pages by IDs."""

    page_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of crawled page IDs to generate labels for",
    )
    force_llm: bool = Field(
        False,
        description="Force LLM labeling regardless of pattern confidence",
    )
    skip_llm: bool = Field(
        False,
        description="Skip LLM even if confidence is low",
    )
    update_pages: bool = Field(
        True,
        description="Whether to update the crawled pages with new labels",
    )


class LabelAllRequest(BaseModel):
    """Request schema for generating labels for all pages in a project."""

    force_llm: bool = Field(
        False,
        description="Force LLM labeling regardless of pattern confidence",
    )
    skip_llm: bool = Field(
        False,
        description="Skip LLM even if confidence is low",
    )
    update_pages: bool = Field(
        True,
        description="Whether to update the crawled pages with new labels",
    )
    include_labeled: bool = Field(
        False,
        description="Re-label pages that already have labels",
    )
    batch_size: int = Field(
        10,
        ge=1,
        le=50,
        description="Number of pages per batch for processing",
    )


class LabelGenerateResponse(BaseModel):
    """Response schema for label generation result."""

    success: bool = Field(..., description="Whether label generation succeeded")
    labels: list[str] = Field(
        default_factory=list,
        description="Generated labels (2-5 thematic labels)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0)",
    )
    tier: str = Field(
        ...,
        description="Which tier was used ('pattern', 'llm', 'fallback')",
    )
    pattern_labels: list[str] = Field(
        default_factory=list,
        description="Labels from pattern matching",
    )
    llm_labels: list[str] = Field(
        default_factory=list,
        description="Labels from LLM (if used)",
    )
    reasoning: str | None = Field(
        None,
        description="LLM reasoning for label choices",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


class LabelBatchItemResponse(BaseModel):
    """Response for a single collection in a batch."""

    collection_id: str | None = Field(
        None,
        description="Collection identifier (if provided in request)",
    )
    success: bool = Field(..., description="Whether label generation succeeded")
    labels: list[str] = Field(
        default_factory=list,
        description="Generated labels",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score",
    )
    tier: str = Field(..., description="Which tier was used")
    error: str | None = Field(None, description="Error message if failed")
    duration_ms: float = Field(..., description="Processing time in milliseconds")


class LabelBatchResponse(BaseModel):
    """Response schema for batch label generation."""

    success: bool = Field(
        ...,
        description="Whether all collections succeeded",
    )
    results: list[LabelBatchItemResponse] = Field(
        ...,
        description="Per-collection results",
    )
    total_duration_ms: float = Field(
        ...,
        description="Total processing time in milliseconds",
    )
    successful_count: int = Field(
        ...,
        description="Number of successful label generations",
    )
    failed_count: int = Field(
        ...,
        description="Number of failed label generations",
    )
    max_concurrent: int = Field(
        ...,
        description="Concurrency level used",
    )


class LabeledPageResponse(BaseModel):
    """Response schema for a labeled page with page details."""

    page_id: str = Field(..., description="Page UUID")
    url: str = Field(..., description="Page URL")
    title: str | None = Field(None, description="Page title")
    labels: list[str] = Field(default_factory=list, description="Generated labels")
    confidence: float = Field(..., description="Label confidence")
    tier: str = Field(..., description="Which tier was used")
    updated: bool = Field(..., description="Whether the page record was updated")


class LabelPageIdsResponse(BaseModel):
    """Response schema for generating labels by page IDs."""

    total: int = Field(..., description="Total pages requested")
    labeled: int = Field(..., description="Pages successfully labeled")
    failed: int = Field(..., description="Pages that failed")
    results: list[LabeledPageResponse] = Field(..., description="Per-page results")
    duration_ms: float = Field(..., description="Total processing time")


class LabelAllResponse(BaseModel):
    """Response schema for generating labels for all pages in a project."""

    total: int = Field(..., description="Total pages to process")
    labeled: int = Field(..., description="Pages successfully labeled")
    failed: int = Field(..., description="Pages that failed")
    skipped: int = Field(..., description="Pages skipped (already labeled)")
    tier_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count per tier (pattern/llm/fallback)",
    )
    duration_ms: float = Field(..., description="Total processing time")


class LabelStatsResponse(BaseModel):
    """Response schema for label statistics."""

    project_id: str = Field(..., description="Project UUID")
    total_pages: int = Field(..., description="Total crawled pages")
    labeled_pages: int = Field(..., description="Pages with labels")
    unlabeled_pages: int = Field(..., description="Pages without labels")
    label_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count per unique label",
    )
    top_labels: list[str] = Field(
        default_factory=list,
        description="Top 10 most common labels",
    )
