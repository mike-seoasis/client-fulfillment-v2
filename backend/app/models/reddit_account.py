"""RedditAccount model for shared Reddit account management.

RedditAccount tracks shared Reddit accounts used across all projects:
- username: Unique Reddit username
- status: Account health (active, warming_up, cooldown, suspended, banned)
- warmup_stage: Progressive engagement stage (observation → operational)
- niche_tags: JSONB array of niche/topic tags
- karma_post/karma_comment: Karma tracking
- cooldown_until: When cooldown period ends
- last_used_at: Last activity timestamp

No FK to projects — accounts are shared across all projects.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WarmupStage(str, Enum):
    """Progressive warmup stages for Reddit accounts."""

    OBSERVATION = "observation"
    LIGHT_ENGAGEMENT = "light_engagement"
    REGULAR_ACTIVITY = "regular_activity"
    OPERATIONAL = "operational"


class AccountStatus(str, Enum):
    """Health status of a Reddit account."""

    ACTIVE = "active"
    WARMING_UP = "warming_up"
    COOLDOWN = "cooldown"
    SUSPENDED = "suspended"
    BANNED = "banned"


class RedditAccount(Base):
    """RedditAccount model for shared Reddit accounts.

    Attributes:
        id: UUID primary key
        username: Unique Reddit username
        status: Account health status
        warmup_stage: Current warmup stage
        niche_tags: JSONB array of niche/topic tags
        karma_post: Post karma count
        karma_comment: Comment karma count
        account_age_days: Age of the Reddit account in days
        cooldown_until: When cooldown period ends
        last_used_at: Last activity timestamp
        notes: Free-text notes
        extra_metadata: JSONB for arbitrary metadata (mapped to 'metadata' column)
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "reddit_accounts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AccountStatus.ACTIVE.value,
        server_default=text("'active'"),
        index=True,
    )

    warmup_stage: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=WarmupStage.OBSERVATION.value,
        server_default=text("'observation'"),
    )

    niche_tags: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    karma_post: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    karma_comment: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    account_age_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
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

    def __repr__(self) -> str:
        return f"<RedditAccount(id={self.id!r}, username={self.username!r}, status={self.status!r})>"
