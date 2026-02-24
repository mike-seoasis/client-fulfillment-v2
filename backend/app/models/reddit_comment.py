"""RedditComment model for AI-generated Reddit comments.

RedditComment stores AI-generated comments with approval workflow:
- post_id: FK to the Reddit post being replied to
- project_id: FK to the project
- account_id: FK to the Reddit account (SET NULL on delete to preserve history)
- body: Current (possibly edited) comment text
- original_body: AI-generated text that never changes
- is_promotional: Whether the comment contains promotional content
- approach_type: Strategy used for the comment (e.g. 'helpful', 'subtle_mention')
- status: Workflow status (draft → approved/rejected → submitting → posted/failed)
- generation_metadata: JSONB with AI generation details
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.reddit_post import RedditPost


class CommentStatus(str, Enum):
    """Workflow status for AI-generated comments."""

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUBMITTING = "submitting"
    POSTED = "posted"
    FAILED = "failed"
    MOD_REMOVED = "mod_removed"


class RedditComment(Base):
    """RedditComment model for AI-generated Reddit comments.

    Attributes:
        id: UUID primary key
        post_id: FK to reddit_posts (CASCADE delete)
        project_id: FK to projects (CASCADE delete)
        account_id: FK to reddit_accounts (SET NULL on delete, nullable)
        body: Current (possibly edited) comment text
        original_body: AI-generated text that never changes
        is_promotional: Whether comment contains promotional content
        approach_type: Strategy used for the comment
        status: Workflow status
        reject_reason: Reason for rejection
        crowdreply_task_id: External CrowdReply task ID
        posted_url: URL of the posted comment
        posted_at: When the comment was posted to Reddit
        generation_metadata: JSONB with AI generation details
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "reddit_comments"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    post_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("reddit_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("reddit_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    original_body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_promotional: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    approach_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CommentStatus.DRAFT.value,
        server_default=text("'draft'"),
        index=True,
    )

    reject_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    crowdreply_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    posted_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    generation_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
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

    # Relationships
    post: Mapped["RedditPost"] = relationship(
        "RedditPost",
        back_populates="comments",
    )

    def __repr__(self) -> str:
        return f"<RedditComment(id={self.id!r}, post_id={self.post_id!r}, status={self.status!r})>"
