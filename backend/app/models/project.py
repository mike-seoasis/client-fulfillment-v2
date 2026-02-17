"""Project model with phase_status JSONB field.

The Project model represents a client onboarding project with:
- Basic project information (name, client reference)
- Status tracking
- Phase status stored as JSONB for flexible workflow tracking
- Timestamps for auditing
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.blog import BlogCampaign
    from app.models.keyword_cluster import KeywordCluster
    from app.models.reddit_config import RedditProjectConfig


class Project(Base):
    """Project model for client onboarding.

    Attributes:
        id: UUID primary key
        name: Project name
        client_id: Reference to the client (external ID for now, optional)
        site_url: Client website URL (required)
        status: Overall project status (e.g., 'active', 'completed', 'on_hold')
        phase_status: JSONB field storing status of each onboarding phase
        created_at: Timestamp when project was created
        updated_at: Timestamp when project was last updated

    Example phase_status structure:
        {
            "discovery": {"status": "completed", "completed_at": "2024-01-15T10:00:00Z"},
            "requirements": {"status": "in_progress", "started_at": "2024-01-16T09:00:00Z"},
            "implementation": {"status": "pending"},
            "review": {"status": "pending"},
            "launch": {"status": "pending"}
        }
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    client_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    site_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        index=True,
    )

    phase_status: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    brand_wizard_state: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        doc="State of the brand configuration wizard (current step, form data, research results)",
    )

    additional_info: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Additional notes or information about the project provided during creation",
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
    clusters: Mapped[list["KeywordCluster"]] = relationship(
        "KeywordCluster",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    blog_campaigns: Mapped[list["BlogCampaign"]] = relationship(
        "BlogCampaign",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    reddit_config: Mapped["RedditProjectConfig | None"] = relationship(
        "RedditProjectConfig",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id!r}, name={self.name!r}, status={self.status!r})>"
