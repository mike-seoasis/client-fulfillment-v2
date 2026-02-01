"""Competitor model for storing competitor URLs and scraped content.

The Competitor model represents a competitor website to analyze:
- url: The competitor website URL
- name: Optional friendly name for the competitor
- status: Scraping status (pending, scraping, completed, failed)
- content: JSONB storing scraped content (title, description, pages, etc.)
- Timestamps for auditing
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Competitor(Base):
    """Competitor model for storing competitor URLs and scraped content.

    Attributes:
        id: UUID primary key
        project_id: Reference to the parent project
        url: The competitor website URL (normalized)
        name: Optional friendly name for the competitor
        status: Scraping status (pending, scraping, completed, failed)
        content: JSONB storing scraped content data
        error_message: Error message if scraping failed
        pages_scraped: Number of pages successfully scraped
        scrape_started_at: When scraping started
        scrape_completed_at: When scraping completed
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example content structure:
        {
            "title": "Competitor Inc.",
            "description": "About the competitor...",
            "pages": [
                {
                    "url": "https://competitor.com/about",
                    "title": "About Us",
                    "content": "Page content...",
                    "scraped_at": "2026-02-01T12:00:00Z"
                }
            ],
            "metadata": {
                "domain": "competitor.com",
                "crawl_depth": 2,
                "total_links_found": 50
            }
        }
    """

    __tablename__ = "competitors"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        index=True,
    )

    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    pages_scraped: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    scrape_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    scrape_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<Competitor(id={self.id!r}, url={self.url!r}, status={self.status!r})>"
