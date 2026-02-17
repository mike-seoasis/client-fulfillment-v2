"""RedditPost model for discovered Reddit threads.

RedditPost stores Reddit threads discovered via SERP searches:
- project_id: FK to the project this post belongs to
- reddit_post_id: Native Reddit post ID (t3_xxx)
- subreddit/title/url: Post metadata
- intent/relevance_score: AI classification results
- filter_status: Workflow status (pending → relevant/irrelevant/skipped)
- discovered_at: When SERP returned the result (distinct from created_at)

UniqueConstraint on (project_id, url) prevents duplicate posts per project.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.reddit_comment import RedditComment


class PostFilterStatus(str, Enum):
    """Workflow filter status for discovered posts."""

    PENDING = "pending"
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    SKIPPED = "skipped"


class PostIntent(str, Enum):
    """Intent classification for Reddit posts."""

    RESEARCH = "research"
    PAIN_POINT = "pain_point"
    COMPETITOR = "competitor"
    QUESTION = "question"
    GENERAL = "general"


class RedditPost(Base):
    """RedditPost model for discovered Reddit threads.

    Attributes:
        id: UUID primary key
        project_id: FK to project (CASCADE delete)
        reddit_post_id: Native Reddit post ID (e.g. t3_xxx)
        subreddit: Subreddit name (e.g. 'webdev')
        title: Post title
        url: Full URL to the Reddit post
        snippet: SERP snippet or post excerpt
        keyword: Search keyword that found this post
        intent: AI-classified intent category
        intent_categories: JSONB array of intent labels
        relevance_score: AI relevance score (0.0–1.0)
        matched_keywords: JSONB array of keywords that matched
        ai_evaluation: JSONB with full AI evaluation details
        filter_status: Workflow filter status
        serp_position: Position in SERP results
        discovered_at: When SERP returned this result
        created_at: Timestamp when DB record was created
        updated_at: Timestamp when DB record was last updated
    """

    __tablename__ = "reddit_posts"

    __table_args__ = (
        UniqueConstraint("project_id", "url", name="uq_reddit_posts_project_url"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reddit_post_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    subreddit: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    snippet: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    keyword: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    intent: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    intent_categories: Mapped[list[Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    relevance_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    matched_keywords: Mapped[list[Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    ai_evaluation: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    filter_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=PostFilterStatus.PENDING.value,
        server_default=text("'pending'"),
        index=True,
    )

    serp_position: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
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

    # Relationships
    comments: Mapped[list["RedditComment"]] = relationship(
        "RedditComment",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<RedditPost(id={self.id!r}, subreddit={self.subreddit!r}, title={self.title[:50]!r})>"
