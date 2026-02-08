"""KeywordCluster and ClusterPage models for keyword cluster management.

KeywordCluster represents a group of related keywords built around a seed keyword:
- seed_keyword: The root keyword that the cluster is built around
- name: Display name for the cluster
- status: Workflow status (generating, suggestions_ready, approved, content_generating, complete)
- generation_metadata: JSONB for storing AI generation context

ClusterPage represents a single page within a cluster:
- keyword: The target keyword for this page
- role: Whether this is the 'parent' or 'child' page in the cluster
- url_slug: Generated URL slug for the page
- SEO metrics: search_volume, cpc, competition, competition_level, composite_score
- expansion_strategy/reasoning: AI-generated strategy info
- is_approved: Approval status for content generation
- crawled_page_id: Optional link to an existing crawled page
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.crawled_page import CrawledPage
    from app.models.project import Project


class ClusterStatus(str, Enum):
    """Status of a keyword cluster."""

    GENERATING = "generating"
    SUGGESTIONS_READY = "suggestions_ready"
    APPROVED = "approved"
    CONTENT_GENERATING = "content_generating"
    COMPLETE = "complete"


class KeywordCluster(Base):
    """KeywordCluster model for grouping related keywords.

    Attributes:
        id: UUID primary key
        project_id: Reference to the parent project
        seed_keyword: The root keyword the cluster is built around
        name: Display name for the cluster
        status: Workflow status
        generation_metadata: JSONB for AI generation context
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "keyword_clusters"

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

    seed_keyword: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ClusterStatus.GENERATING.value,
        server_default=text("'generating'"),
        index=True,
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
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="clusters",
    )

    pages: Mapped[list["ClusterPage"]] = relationship(
        "ClusterPage",
        back_populates="cluster",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KeywordCluster(id={self.id!r}, name={self.name!r}, seed={self.seed_keyword!r})>"


class ClusterPage(Base):
    """ClusterPage model for individual pages within a keyword cluster.

    Attributes:
        id: UUID primary key
        cluster_id: Reference to the parent keyword cluster
        keyword: Target keyword for this page
        role: 'parent' or 'child' role within the cluster
        url_slug: Generated URL slug
        expansion_strategy: AI-generated strategy for content expansion
        reasoning: AI reasoning for this page's inclusion
        search_volume: Estimated monthly search volume
        cpc: Cost per click
        competition: Competition score (0-1)
        competition_level: Competition level label
        composite_score: Overall score combining metrics
        is_approved: Whether this page is approved for content generation
        crawled_page_id: Optional link to existing crawled page
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "cluster_pages"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    cluster_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("keyword_clusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    keyword: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    url_slug: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    expansion_strategy: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    search_volume: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    cpc: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    competition: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    competition_level: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    composite_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    crawled_page_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("crawled_pages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    cluster: Mapped["KeywordCluster"] = relationship(
        "KeywordCluster",
        back_populates="pages",
    )

    crawled_page: Mapped["CrawledPage | None"] = relationship(
        "CrawledPage",
    )

    def __repr__(self) -> str:
        return f"<ClusterPage(id={self.id!r}, keyword={self.keyword!r}, role={self.role!r})>"
