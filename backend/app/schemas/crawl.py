"""Pydantic schemas for Crawl phase API endpoints.

Schemas for crawl-related requests and responses:
- CrawlStartRequest: Request to start a new crawl
- CrawlHistoryResponse: Response for crawl history records
- CrawledPageResponse: Response for crawled page records
- CrawlProgressResponse: Response for crawl progress updates
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Valid crawl statuses
VALID_CRAWL_STATUSES = frozenset({
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
})

# Valid trigger types
VALID_TRIGGER_TYPES = frozenset({
    "manual",
    "scheduled",
    "webhook",
})


class CrawlStartRequest(BaseModel):
    """Request schema for starting a new crawl."""

    start_url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="The URL to start crawling from",
        examples=["https://example.com"],
    )
    include_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for URLs to include (e.g., '/products/*')",
        examples=[["/products/*", "/services/*"]],
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
        description="Glob patterns for URLs to exclude (e.g., '/admin/*')",
        examples=[["/admin/*", "/api/*", "*.pdf"]],
    )
    max_pages: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of pages to crawl",
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum crawl depth from the start URL",
    )

    @field_validator("start_url")
    @classmethod
    def validate_start_url(cls, v: str) -> str:
        """Validate the start URL has a valid format."""
        v = v.strip()
        if not v:
            raise ValueError("start_url cannot be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError("start_url must start with http:// or https://")
        return v

    @field_validator("include_patterns", "exclude_patterns")
    @classmethod
    def validate_patterns(cls, v: list[str]) -> list[str]:
        """Validate patterns are not empty strings."""
        return [p.strip() for p in v if p.strip()]


class CrawlHistoryResponse(BaseModel):
    """Response schema for crawl history records."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Crawl history UUID")
    project_id: str = Field(..., description="Project UUID")
    schedule_id: str | None = Field(None, description="Optional schedule UUID")
    status: str = Field(..., description="Crawl status")
    trigger_type: str = Field(..., description="How the crawl was triggered")
    started_at: datetime | None = Field(None, description="When the crawl started")
    completed_at: datetime | None = Field(None, description="When the crawl completed")
    pages_crawled: int = Field(..., description="Number of pages successfully crawled")
    pages_failed: int = Field(..., description="Number of pages that failed")
    stats: dict[str, Any] = Field(default_factory=dict, description="Crawl statistics")
    error_log: list[dict[str, Any]] = Field(default_factory=list, description="Error entries")
    error_message: str | None = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")


class CrawlHistoryListResponse(BaseModel):
    """Response schema for paginated crawl history list."""

    items: list[CrawlHistoryResponse] = Field(
        ..., description="List of crawl history records"
    )
    total: int = Field(..., description="Total number of records")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Offset from start")


class CrawledPageResponse(BaseModel):
    """Response schema for crawled page records."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Page UUID")
    project_id: str = Field(..., description="Project UUID")
    normalized_url: str = Field(..., description="Normalized/canonical URL")
    raw_url: str | None = Field(None, description="Original URL before normalization")
    category: str | None = Field(None, description="Page category")
    labels: list[str] = Field(default_factory=list, description="Page labels/tags")
    title: str | None = Field(None, description="Page title")
    content_hash: str | None = Field(None, description="Content hash for change detection")
    last_crawled_at: datetime | None = Field(None, description="When last crawled")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")


class CrawledPageListResponse(BaseModel):
    """Response schema for paginated crawled pages list."""

    items: list[CrawledPageResponse] = Field(
        ..., description="List of crawled page records"
    )
    total: int = Field(..., description="Total number of records")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Offset from start")


class CrawlProgressResponse(BaseModel):
    """Response schema for crawl progress updates."""

    crawl_id: str = Field(..., description="Crawl history UUID")
    project_id: str = Field(..., description="Project UUID")
    status: str = Field(..., description="Current crawl status")
    pages_crawled: int = Field(..., description="Pages successfully crawled")
    pages_failed: int = Field(..., description="Pages that failed")
    pages_skipped: int = Field(0, description="Pages skipped (e.g., max depth)")
    urls_discovered: int = Field(0, description="New URLs discovered")
    current_depth: int = Field(0, description="Current crawl depth")
    started_at: datetime | None = Field(None, description="When crawl started")
    completed_at: datetime | None = Field(None, description="When crawl completed")
    error_count: int = Field(0, description="Number of errors encountered")


class CrawlStopResponse(BaseModel):
    """Response schema for stopping a crawl."""

    crawl_id: str = Field(..., description="Crawl history UUID")
    status: str = Field(..., description="New status after stop")
    message: str = Field(..., description="Status message")
