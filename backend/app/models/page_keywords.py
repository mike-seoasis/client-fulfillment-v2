"""PageKeywords model for storing SEO keywords associated with crawled pages.

The PageKeywords model represents keyword data for a page:
- primary_keyword: The main target keyword for the page
- secondary_keywords: JSONB array of supporting keywords
- Foreign key relationship to CrawledPage
- Timestamps for auditing
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PageKeywords(Base):
    """PageKeywords model for storing SEO keywords associated with crawled pages.

    Attributes:
        id: UUID primary key
        crawled_page_id: Reference to the parent crawled page
        primary_keyword: The main target keyword for the page
        secondary_keywords: JSONB array of supporting/related keywords
        search_volume: Estimated monthly search volume for primary keyword
        difficulty_score: SEO difficulty score (0-100) for primary keyword
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example secondary_keywords structure:
        ["related keyword 1", "related keyword 2", "long tail variation"]
    """

    __tablename__ = "page_keywords"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    crawled_page_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
    )

    primary_keyword: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )

    secondary_keywords: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    search_volume: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    difficulty_score: Mapped[int | None] = mapped_column(
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
        return f"<PageKeywords(id={self.id!r}, primary={self.primary_keyword!r})>"
