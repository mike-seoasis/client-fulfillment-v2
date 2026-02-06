"""PageContent model for storing generated content for each page.

The PageContent model stores all 4 generated content fields for a single page:
- page_title: Generated SEO-optimized page title
- meta_description: Generated meta description
- top_description: Above-the-fold content
- bottom_description: Below-the-fold content

One-to-one relationship with CrawledPage via crawled_page_id.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.crawled_page import CrawledPage
    from app.models.prompt_log import PromptLog


class ContentStatus(str, Enum):
    """Status of content generation for a page."""

    PENDING = "pending"
    GENERATING_BRIEF = "generating_brief"
    WRITING = "writing"
    CHECKING = "checking"
    COMPLETE = "complete"
    FAILED = "failed"


class PageContent(Base):
    """PageContent model for storing generated content for each page.

    Attributes:
        id: UUID primary key
        crawled_page_id: FK to crawled_pages (unique, one-to-one)
        page_title: Generated page title
        meta_description: Generated meta description
        top_description: Above-the-fold content
        bottom_description: Below-the-fold content
        word_count: Total word count across content fields
        status: Generation status (pending, generating_brief, writing, checking, complete, failed)
        qa_results: JSONB storing QA check results
        generation_started_at: When generation started
        generation_completed_at: When generation completed
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "page_contents"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    crawled_page_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("crawled_pages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    page_title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    meta_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    top_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    bottom_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    word_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ContentStatus.PENDING.value,
        server_default=text("'pending'"),
        index=True,
    )

    qa_results: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    generation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    generation_completed_at: Mapped[datetime | None] = mapped_column(
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

    # Relationship to CrawledPage (one-to-one)
    page: Mapped["CrawledPage"] = relationship(
        "CrawledPage",
        back_populates="page_content",
    )

    # Relationship to PromptLog (one-to-many)
    prompt_logs: Mapped[list["PromptLog"]] = relationship(
        "PromptLog",
        back_populates="page_content",
    )

    def __repr__(self) -> str:
        return f"<PageContent(id={self.id!r}, page_id={self.crawled_page_id!r}, status={self.status!r})>"
