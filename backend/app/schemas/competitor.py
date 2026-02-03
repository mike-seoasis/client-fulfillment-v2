"""Pydantic schemas for Competitor phase API endpoints.

Schemas for competitor-related requests and responses:
- CompetitorCreateRequest: Request to add a new competitor
- CompetitorResponse: Response for competitor records
- CompetitorScrapeRequest: Request to start scraping
- CompetitorContentResponse: Response for scraped content
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Valid competitor statuses
VALID_STATUSES = frozenset({"pending", "scraping", "completed", "failed"})


class CompetitorCreateRequest(BaseModel):
    """Request schema for adding a new competitor."""

    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="The competitor website URL",
        examples=["https://competitor.com", "competitor.com"],
    )
    name: str | None = Field(
        None,
        max_length=255,
        description="Optional friendly name for the competitor",
        examples=["Acme Corp", "Main Competitor"],
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate the URL is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("url cannot be empty")
        return v


class CompetitorScrapeRequest(BaseModel):
    """Request schema for starting a competitor scrape."""

    max_pages: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of pages to scrape",
    )
    bypass_cache: bool = Field(
        default=False,
        description="Whether to bypass cached content",
    )


class ScrapedPageResponse(BaseModel):
    """Response schema for a single scraped page."""

    url: str = Field(..., description="Page URL")
    title: str = Field("", description="Page title")
    description: str = Field("", description="Page meta description")
    content: str = Field("", description="Page content (markdown, truncated)")
    scraped_at: str | None = Field(None, description="When the page was scraped")


class CompetitorContentResponse(BaseModel):
    """Response schema for competitor scraped content."""

    title: str = Field("", description="Main page title")
    description: str = Field("", description="Main page description")
    pages: list[ScrapedPageResponse] = Field(
        default_factory=list,
        description="List of scraped pages",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Scrape metadata (domain, timestamps, etc.)",
    )


class CompetitorResponse(BaseModel):
    """Response schema for competitor records."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Competitor UUID")
    project_id: str = Field(..., description="Project UUID")
    url: str = Field(..., description="Competitor website URL")
    name: str | None = Field(None, description="Friendly name for the competitor")
    status: str = Field(..., description="Scraping status")
    pages_scraped: int = Field(0, description="Number of pages scraped")
    error_message: str | None = Field(None, description="Error message if failed")
    scrape_started_at: datetime | None = Field(
        None, description="When scraping started"
    )
    scrape_completed_at: datetime | None = Field(
        None, description="When scraping completed"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record update timestamp")


class CompetitorDetailResponse(CompetitorResponse):
    """Response schema for competitor with full content."""

    content: CompetitorContentResponse = Field(
        default_factory=CompetitorContentResponse,
        description="Scraped content data",
    )

    @classmethod
    def from_orm_with_content(cls, competitor: Any) -> "CompetitorDetailResponse":
        """Create response from ORM object with content parsing."""
        content_data = competitor.content or {}
        pages_data = content_data.get("pages", [])

        pages = [
            ScrapedPageResponse(
                url=p.get("url", ""),
                title=p.get("title", ""),
                description=p.get("description", ""),
                content=p.get("content", ""),
                scraped_at=p.get("scraped_at"),
            )
            for p in pages_data
        ]

        content = CompetitorContentResponse(
            title=content_data.get("title", ""),
            description=content_data.get("description", ""),
            pages=pages,
            metadata=content_data.get("metadata", {}),
        )

        return cls(
            id=competitor.id,
            project_id=competitor.project_id,
            url=competitor.url,
            name=competitor.name,
            status=competitor.status,
            pages_scraped=competitor.pages_scraped,
            error_message=competitor.error_message,
            scrape_started_at=competitor.scrape_started_at,
            scrape_completed_at=competitor.scrape_completed_at,
            created_at=competitor.created_at,
            updated_at=competitor.updated_at,
            content=content,
        )


class CompetitorListResponse(BaseModel):
    """Response schema for paginated competitor list."""

    items: list[CompetitorResponse] = Field(
        ..., description="List of competitor records"
    )
    total: int = Field(..., description="Total number of records")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Offset from start")


class CompetitorScrapeProgressResponse(BaseModel):
    """Response schema for scrape progress updates."""

    competitor_id: str = Field(..., description="Competitor UUID")
    project_id: str = Field(..., description="Project UUID")
    status: str = Field(..., description="Current scraping status")
    pages_scraped: int = Field(0, description="Pages successfully scraped")
    scrape_started_at: datetime | None = Field(
        None, description="When scraping started"
    )
    scrape_completed_at: datetime | None = Field(
        None, description="When scraping completed"
    )
    error_message: str | None = Field(None, description="Error message if failed")
