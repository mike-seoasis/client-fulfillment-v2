"""CrowdReplyTask model for tracking CrowdReply API submissions.

CrowdReplyTask tracks submissions to the CrowdReply API with status,
pricing, and webhook responses:
- comment_id: FK to the reddit comment (SET NULL to preserve audit trail)
- external_task_id: CrowdReply's _id field from their API
- task_type: Type of CrowdReply task (comment, post, reply, upvote)
- status: Workflow status through CrowdReply's lifecycle
- target_url: Reddit URL being targeted
- content: Text content submitted to CrowdReply
- request_payload / response_payload: Raw API payloads for debugging
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.reddit_comment import RedditComment


class CrowdReplyTaskType(str, Enum):
    """Type of CrowdReply task."""

    COMMENT = "comment"
    POST = "post"
    REPLY = "reply"
    UPVOTE = "upvote"


class CrowdReplyTaskStatus(str, Enum):
    """Status lifecycle for CrowdReply tasks."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    ASSIGNED = "assigned"
    PUBLISHED = "published"
    MOD_REMOVED = "mod_removed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CrowdReplyTask(Base):
    """CrowdReplyTask model for tracking CrowdReply API submissions.

    Attributes:
        id: UUID primary key
        comment_id: FK to reddit_comments (SET NULL on delete, nullable)
        external_task_id: CrowdReply's _id from their API
        task_type: Type of task (comment, post, reply, upvote)
        status: Current task status
        target_url: Reddit URL being targeted
        content: Text content submitted
        crowdreply_project_id: CrowdReply's project identifier
        request_payload: Raw request sent to CrowdReply API
        response_payload: Raw response from CrowdReply API
        upvotes_requested: Number of upvotes requested
        price: Cost of the task
        submitted_at: When task was submitted to CrowdReply
        published_at: When task was published on Reddit
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "crowdreply_tasks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    comment_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("reddit_comments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    external_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    task_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CrowdReplyTaskStatus.PENDING.value,
        server_default=text("'pending'"),
        index=True,
    )

    target_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    crowdreply_project_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    request_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    response_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    upvotes_requested: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    published_at: Mapped[datetime | None] = mapped_column(
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

    # Relationships
    comment: Mapped["RedditComment | None"] = relationship(
        "RedditComment",
    )

    def __repr__(self) -> str:
        return f"<CrowdReplyTask(id={self.id!r}, type={self.task_type!r}, status={self.status!r})>"
