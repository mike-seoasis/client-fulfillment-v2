"""ContentScore model for storing POP content scoring results.

The ContentScore model represents content optimization scoring from PageOptimizer Pro:
- Page score and pass/fail status
- Detailed keyword and LSI analysis
- Word count and heading structure analysis
- Recommendations for improvement
- Raw API response for debugging
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.crawled_page import CrawledPage


class ContentScore(Base):
    """ContentScore model for storing POP content scoring results.

    Attributes:
        id: UUID primary key
        page_id: Reference to the parent crawled page
        pop_task_id: POP API task identifier for tracking
        page_score: Overall page optimization score (0-100)
        passed: Whether the page passes optimization threshold
        keyword_analysis: JSONB object with keyword usage analysis
        lsi_coverage: JSONB object with LSI term coverage data
        word_count_current: Current word count of the page
        heading_analysis: JSONB object with heading structure analysis
        recommendations: JSONB array of improvement recommendations
        fallback_used: Whether fallback scoring was used (e.g., API timeout)
        raw_response: Full POP API response for debugging
        scored_at: Timestamp when the scoring was performed
        created_at: Timestamp when record was created

    Example keyword_analysis structure:
        {"primary_count": 5, "density": 1.2, "in_title": true, "in_h1": true}

    Example recommendations structure:
        [{"type": "word_count", "message": "Add 200 more words", "priority": "high"}]
    """

    __tablename__ = "content_scores"

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
        index=True,
    )

    pop_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    page_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    passed: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
    )

    keyword_analysis: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    lsi_coverage: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    word_count_current: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    heading_analysis: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    recommendations: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    fallback_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    raw_response: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    # Relationship to CrawledPage
    page: Mapped["CrawledPage"] = relationship(
        "CrawledPage",
        back_populates="content_scores",
    )

    def __repr__(self) -> str:
        return f"<ContentScore(id={self.id!r}, page_score={self.page_score!r}, passed={self.passed!r})>"
