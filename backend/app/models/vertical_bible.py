"""VerticalBible model for domain-specific knowledge bibles.

A VerticalBible stores domain expertise for a project vertical:
- content_md: Markdown knowledge doc injected into generation prompts
- trigger_keywords: JSONB array of keywords that activate this bible
- qa_rules: JSONB dict of structured quality check rules
- sort_order: Priority when multiple bibles match (lower = higher priority)
- is_active: Enable/disable without deleting
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VerticalBible(Base):
    """Vertical knowledge bible for domain-specific content generation.

    Attributes:
        id: UUID primary key
        project_id: FK to projects table
        name: Display name (e.g., "Tattoo Cartridge Needles")
        slug: URL-safe identifier, unique per project
        content_md: Full markdown knowledge doc (injected into prompts)
        trigger_keywords: JSONB array of keywords that activate this bible
        qa_rules: JSONB dict of structured rules for quality checks
        sort_order: Priority when multiple bibles match (lower = higher priority)
        is_active: Whether this bible is active for matching
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "vertical_bibles"

    __table_args__ = (
        sa.UniqueConstraint(
            "project_id", "slug", name="uq_vertical_bibles_project_slug"
        ),
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

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    content_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default=text("''"),
    )

    trigger_keywords: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    qa_rules: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
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

    def __repr__(self) -> str:
        return (
            f"<VerticalBible(id={self.id!r}, name={self.name!r}, slug={self.slug!r})>"
        )
