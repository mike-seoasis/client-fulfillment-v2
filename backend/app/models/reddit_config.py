"""RedditProjectConfig model for per-project Reddit settings.

RedditProjectConfig stores project-specific Reddit configuration:
- search_keywords: JSONB array of keywords to monitor
- target_subreddits: JSONB array of subreddits to engage in
- banned_subreddits: JSONB array of subreddits to avoid
- competitors: JSONB array of competitor identifiers
- comment_instructions: Free-text voice/tone instructions for comments
- niche_tags: JSONB array of niche/topic tags
- discovery_settings: JSONB for advanced discovery configuration
- is_active: Whether Reddit engagement is active for this project

1:1 relationship with Project via unique project_id FK.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


class RedditProjectConfig(Base):
    """RedditProjectConfig model for per-project Reddit settings.

    Attributes:
        id: UUID primary key
        project_id: Unique FK to projects.id (1:1 relationship)
        search_keywords: JSONB array of keywords to monitor
        target_subreddits: JSONB array of subreddits to engage in
        banned_subreddits: JSONB array of subreddits to avoid
        competitors: JSONB array of competitor identifiers
        comment_instructions: Free-text voice/tone instructions
        niche_tags: JSONB array of niche/topic tags
        discovery_settings: JSONB for advanced discovery configuration
        is_active: Whether Reddit engagement is active
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "reddit_project_configs"

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
        unique=True,
        index=True,
    )

    search_keywords: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    target_subreddits: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    banned_subreddits: Mapped[list[Any]] = mapped_column(
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

    comment_instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    niche_tags: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    discovery_settings: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
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
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="reddit_config",
    )

    def __repr__(self) -> str:
        return f"<RedditProjectConfig(id={self.id!r}, project_id={self.project_id!r}, is_active={self.is_active!r})>"
