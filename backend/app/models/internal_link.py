"""InternalLink model for storing page-to-page internal links.

The InternalLink model represents an edge between two CrawledPages:
- source_page_id: The page containing the link
- target_page_id: The page being linked to
- scope: 'onboarding' (cluster_id=null) or 'cluster' (cluster_id set)
- anchor_text: The visible text of the link
- anchor_type: How the anchor text relates to the target keyword
- placement_method: Whether the link was placed by rules or LLM fallback
- status: Lifecycle status (planned → injected → verified | removed)
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.crawled_page import CrawledPage
    from app.models.keyword_cluster import KeywordCluster
    from app.models.project import Project


class LinkScope(str, Enum):
    """Scope of an internal link."""

    ONBOARDING = "onboarding"
    CLUSTER = "cluster"
    BLOG = "blog"


class AnchorType(str, Enum):
    """How the anchor text relates to the target keyword."""

    EXACT_MATCH = "exact_match"
    PARTIAL_MATCH = "partial_match"
    NATURAL = "natural"


class PlacementMethod(str, Enum):
    """How the link was placed in the content."""

    RULE_BASED = "rule_based"
    LLM_FALLBACK = "llm_fallback"


class LinkStatus(str, Enum):
    """Lifecycle status of an internal link."""

    PLANNED = "planned"
    INJECTED = "injected"
    VERIFIED = "verified"
    REMOVED = "removed"


class InternalLink(Base):
    """InternalLink model for storing page-to-page internal links.

    Attributes:
        id: UUID primary key
        source_page_id: Reference to the page containing the link
        target_page_id: Reference to the page being linked to
        project_id: Reference to the parent project
        cluster_id: Optional reference to a keyword cluster (null for onboarding scope)
        scope: 'onboarding' or 'cluster'
        anchor_text: The visible text of the link
        anchor_type: 'exact_match', 'partial_match', or 'natural'
        position_in_content: Optional character offset in content
        is_mandatory: Whether this link is required
        placement_method: 'rule_based' or 'llm_fallback'
        status: 'planned', 'injected', 'verified', or 'removed'
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "internal_links"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    source_page_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("crawled_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_page_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("crawled_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    cluster_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("keyword_clusters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    anchor_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    anchor_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    position_in_content: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    placement_method: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default=LinkStatus.PLANNED.value,
        server_default=text("'planned'"),
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

    # Composite index for project_id + scope queries
    __table_args__ = (
        Index("ix_internal_links_project_id_scope", "project_id", "scope"),
    )

    # Relationships
    source_page: Mapped["CrawledPage"] = relationship(
        "CrawledPage",
        foreign_keys=[source_page_id],
        back_populates="outbound_links",
    )

    target_page: Mapped["CrawledPage"] = relationship(
        "CrawledPage",
        foreign_keys=[target_page_id],
        back_populates="inbound_links",
    )

    project: Mapped["Project"] = relationship(
        "Project",
    )

    cluster: Mapped["KeywordCluster | None"] = relationship(
        "KeywordCluster",
    )

    def __repr__(self) -> str:
        return (
            f"<InternalLink(id={self.id!r}, source={self.source_page_id!r}, "
            f"target={self.target_page_id!r}, scope={self.scope!r})>"
        )


class LinkPlanSnapshot(Base):
    """Snapshot of a link plan for audit and rollback.

    Stores the full plan including pre-injection content per page,
    enabling rollback by restoring pre-injection content.

    plan_data JSONB structure:
    {
        pages: [{page_id, pre_injection_content, links: [{target_id, anchor_text, anchor_type}]}],
        metadata: {scope, cluster_id, total_pages}
    }
    """

    __tablename__ = "link_plan_snapshots"

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
    )

    cluster_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("keyword_clusters.id", ondelete="SET NULL"),
        nullable=True,
    )

    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    plan_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    total_links: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    # Composite index for project_id + scope queries
    __table_args__ = (
        Index("ix_link_plan_snapshots_project_id_scope", "project_id", "scope"),
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
    )

    cluster: Mapped["KeywordCluster | None"] = relationship(
        "KeywordCluster",
    )

    def __repr__(self) -> str:
        return (
            f"<LinkPlanSnapshot(id={self.id!r}, project_id={self.project_id!r}, "
            f"scope={self.scope!r}, total_links={self.total_links!r})>"
        )
