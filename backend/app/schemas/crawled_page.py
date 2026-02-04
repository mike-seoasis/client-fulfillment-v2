"""Pydantic schemas for CrawledPage API endpoints.

Schemas for URL upload, crawling, and page management:
- CrawledPageCreate: Request to create a new crawled page
- CrawledPageResponse: Response for crawled page records with all fields
- CrawlStatusResponse: Response for crawl progress with pages array
- UrlsUploadRequest: Request to upload multiple URLs for crawling
- PageLabelsUpdate: Request to update labels for a page
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.crawled_page import CrawlStatus


class CrawledPageCreate(BaseModel):
    """Request schema for creating a new crawled page."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="The URL of the page to create",
        examples=["https://example.com/products/widget"],
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate the URL has a valid format."""
        v = v.strip()
        if not v:
            raise ValueError("url cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return v


class CrawledPageResponse(BaseModel):
    """Response schema for crawled page records with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Page UUID")
    project_id: str = Field(..., description="Project UUID")
    normalized_url: str = Field(..., description="Normalized/canonical URL")
    raw_url: str | None = Field(None, description="Original URL before normalization")
    category: str | None = Field(None, description="Page category")
    labels: list[str] = Field(default_factory=list, description="Page labels/tags")
    title: str | None = Field(None, description="Page title")
    status: str = Field(
        default=CrawlStatus.PENDING.value,
        description="Crawl status (pending, crawling, completed, failed)",
    )
    meta_description: str | None = Field(
        None, description="Page meta description extracted from HTML"
    )
    body_content: str | None = Field(
        None, description="Main content extracted as markdown"
    )
    headings: dict[str, Any] | None = Field(
        None,
        description="Headings structure with h1, h2, h3 arrays",
        examples=[{"h1": ["Main Title"], "h2": ["Section 1"], "h3": ["Subsection"]}],
    )
    product_count: int | None = Field(
        None, description="Number of products detected on page"
    )
    crawl_error: str | None = Field(None, description="Error message if crawl failed")
    word_count: int | None = Field(None, description="Number of words in body content")
    content_hash: str | None = Field(
        None, description="Content hash for change detection"
    )
    last_crawled_at: datetime | None = Field(None, description="When last crawled")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")


class PageSummary(BaseModel):
    """Summary of a crawled page for status response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Page UUID")
    url: str = Field(..., description="Normalized URL")
    status: str = Field(..., description="Crawl status")
    title: str | None = Field(None, description="Page title")
    word_count: int | None = Field(None, description="Word count of extracted content")
    product_count: int | None = Field(None, description="Products found on page")
    labels: list[str] = Field(default_factory=list, description="Assigned labels")


class ProgressCounts(BaseModel):
    """Progress counts for crawl status."""

    total: int = Field(..., ge=0, description="Total number of pages")
    completed: int = Field(..., ge=0, description="Pages successfully crawled")
    failed: int = Field(..., ge=0, description="Pages that failed to crawl")
    pending: int = Field(..., ge=0, description="Pages pending crawl")


class CrawlStatusResponse(BaseModel):
    """Response schema for crawl status with progress and pages array."""

    project_id: str = Field(..., description="Project UUID")
    status: str = Field(
        ...,
        description="Overall status: crawling, labeling, or complete",
    )
    progress: ProgressCounts = Field(..., description="Progress counts by status")
    pages: list[PageSummary] = Field(
        default_factory=list,
        description="Array of page summaries",
    )


class UrlsUploadRequest(BaseModel):
    """Request schema for uploading multiple URLs for crawling."""

    urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="List of URLs to upload for crawling",
        examples=[
            [
                "https://example.com/products/widget",
                "https://example.com/products/gadget",
                "https://example.com/about",
            ]
        ],
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
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"URL must start with http:// or https://: {url[:50]}")
            validated.append(url)
        if not validated:
            raise ValueError("At least one valid URL is required")
        return validated


class PageLabelsUpdate(BaseModel):
    """Request schema for updating labels on a page."""

    labels: list[str] = Field(
        ...,
        max_length=100,
        description="List of labels/tags to set on the page",
        examples=[["primary-nav", "high-traffic", "needs-review"]],
    )

    @field_validator("labels")
    @classmethod
    def validate_labels(cls, v: list[str]) -> list[str]:
        """Validate and normalize labels."""
        validated = []
        for label in v:
            label = label.strip().lower()
            if not label:
                continue
            if len(label) > 100:
                raise ValueError(f"Label too long (max 100 chars): {label[:50]}...")
            validated.append(label)
        return validated


class UrlUploadResponse(BaseModel):
    """Response schema for URL upload endpoint."""

    task_id: str = Field(
        ..., description="Background task ID for tracking crawl progress"
    )
    pages_created: int = Field(
        ..., ge=0, description="Number of new CrawledPage records created"
    )
    pages_skipped: int = Field(
        ..., ge=0, description="Number of duplicate URLs skipped"
    )
    total_urls: int = Field(..., ge=0, description="Total URLs in request")
