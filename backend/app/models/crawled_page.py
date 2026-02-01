"""CrawledPage model for storing crawled website pages.

The CrawledPage model represents a single page crawled during client onboarding:
- normalized_url: The canonical URL after normalization (removes fragments, query params, etc.)
- category: Page category for classification (e.g., 'homepage', 'product', 'contact')
- labels: JSONB array of labels/tags for flexible categorization
- Timestamps for auditing
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CrawledPage(Base):
    """CrawledPage model for storing crawled website pages.

    Attributes:
        id: UUID primary key
        project_id: Reference to the parent project
        normalized_url: Canonical URL after normalization (unique per project)
        raw_url: Original URL before normalization
        category: Page category (e.g., 'homepage', 'product', 'about', 'contact')
        labels: JSONB array of labels for flexible tagging
        title: Page title extracted from HTML
        content_hash: Hash of page content for change detection
        last_crawled_at: When the page was last successfully crawled
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example labels structure:
        ["primary-nav", "high-traffic", "needs-review"]
    """

    __tablename__ = "crawled_pages"

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

    normalized_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )

    raw_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    labels: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    last_crawled_at: Mapped[datetime | None] = mapped_column(
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
        return f"<CrawledPage(id={self.id!r}, url={self.normalized_url!r}, category={self.category!r})>"
