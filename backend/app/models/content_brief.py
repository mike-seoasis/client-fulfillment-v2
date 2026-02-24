"""ContentBrief model for storing POP content brief data.

The ContentBrief model represents content optimization guidance from PageOptimizer Pro:
- Keyword targets, word count recommendations, heading structures
- LSI terms, entities, and related content suggestions
- Competitor analysis data
- Raw API response for debugging
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.crawled_page import CrawledPage


class ContentBrief(Base):
    """ContentBrief model for storing POP content brief data.

    Attributes:
        id: UUID primary key
        page_id: Reference to the parent crawled page
        keyword: Target keyword for content optimization
        pop_task_id: POP API task identifier for tracking
        word_count_target: Recommended word count target
        word_count_min: Minimum recommended word count
        word_count_max: Maximum recommended word count
        heading_targets: JSONB array of recommended headings
        keyword_targets: JSONB array of keyword usage targets
        lsi_terms: JSONB array of LSI (latent semantic indexing) terms
        entities: JSONB array of entities to include
        related_questions: JSONB array of related questions (People Also Ask)
        related_searches: JSONB array of related search queries
        competitors: JSONB array of competitor page data
        page_score_target: Target page optimization score
        raw_response: Full POP API response for debugging
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example heading_targets structure:
        [{"level": "h2", "text": "What is keyword?", "priority": 1}]

    Example keyword_targets structure:
        [{"keyword": "primary term", "count_min": 3, "count_max": 5}]
    """

    __tablename__ = "content_briefs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    page_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("crawled_pages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    keyword: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )

    pop_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    word_count_target: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    word_count_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    word_count_max: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    heading_targets: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    keyword_targets: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    lsi_terms: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    entities: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    related_questions: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    related_searches: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    competitors: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    page_score_target: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    raw_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
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

    # Relationship to CrawledPage
    page: Mapped["CrawledPage"] = relationship(
        "CrawledPage",
        back_populates="content_brief",
    )

    def __repr__(self) -> str:
        return f"<ContentBrief(id={self.id!r}, keyword={self.keyword!r}, page_id={self.page_id!r})>"
