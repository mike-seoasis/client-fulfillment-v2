"""CrawledPage model for storing crawled website pages.

The CrawledPage model represents a single page crawled during client onboarding:
- normalized_url: The canonical URL after normalization (removes fragments, query params, etc.)
- category: Page category for classification (e.g., 'homepage', 'product', 'contact')
- labels: JSONB array of labels/tags for flexible categorization
- status: Crawl status (pending, crawling, completed, failed)
- Extracted content: meta_description, body_content, headings, word_count
- Timestamps for auditing
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.content_brief import ContentBrief
    from app.models.content_score import ContentScore
    from app.models.page_content import PageContent
    from app.models.page_keywords import PageKeywords


class CrawlStatus(str, Enum):
    """Status of a page crawl."""

    PENDING = "pending"
    CRAWLING = "crawling"
    COMPLETED = "completed"
    FAILED = "failed"


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
        status: Crawl status (pending, crawling, completed, failed)
        meta_description: Page meta description extracted from HTML
        body_content: Main content extracted as markdown
        headings: JSONB with h1, h2, h3 arrays
        product_count: Number of products detected on page
        crawl_error: Error message if crawl failed
        word_count: Number of words in body content
        content_hash: Hash of page content for change detection
        last_crawled_at: When the page was last successfully crawled
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example labels structure:
        ["primary-nav", "high-traffic", "needs-review"]

    Example headings structure:
        {"h1": ["Main Title"], "h2": ["Section 1", "Section 2"], "h3": ["Subsection"]}
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

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CrawlStatus.PENDING.value,
        server_default=text("'pending'"),
        index=True,
    )

    meta_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    body_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    headings: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    product_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    crawl_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    word_count: Mapped[int | None] = mapped_column(
        Integer,
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

    # Relationships to content brief and score models
    content_briefs: Mapped[list["ContentBrief"]] = relationship(
        "ContentBrief",
        back_populates="page",
        cascade="all, delete-orphan",
    )

    content_scores: Mapped[list["ContentScore"]] = relationship(
        "ContentScore",
        back_populates="page",
        cascade="all, delete-orphan",
    )

    # Relationship to PageContent (one-to-one)
    page_content: Mapped["PageContent | None"] = relationship(
        "PageContent",
        back_populates="page",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # Relationship to PageKeywords (one-to-one)
    keywords: Mapped["PageKeywords | None"] = relationship(
        "PageKeywords",
        back_populates="page",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<CrawledPage(id={self.id!r}, url={self.normalized_url!r}, category={self.category!r})>"
