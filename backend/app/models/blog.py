"""BlogCampaign and BlogPost models for blog content management.

BlogCampaign represents a blog initiative tied 1:1 to a keyword cluster:
- cluster_id: UNIQUE FK to keyword_clusters (1:1 relationship)
- name: Display name for the campaign
- status: Workflow status (planning/writing/review/complete)
- generation_metadata: JSONB for AI generation context

BlogPost represents a single blog post within a campaign:
- primary_keyword: Target keyword for this post
- url_slug: Generated URL slug
- Content fields: title, meta_description, content (single HTML field)
- pop_brief: JSONB for POP report brief data
- Approval workflow: is_approved (keyword), content_approved (content)
- content_status: Generation status (pending/generating/complete/failed)
- status: Overall post status (keyword_pending/generating/editing/complete)
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.keyword_cluster import ClusterPage, KeywordCluster
    from app.models.project import Project


class CampaignStatus(str, Enum):
    """Status of a blog campaign."""

    PLANNING = "planning"
    WRITING = "writing"
    REVIEW = "review"
    COMPLETE = "complete"


class ContentStatus(str, Enum):
    """Content generation status for a blog post."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


class PostStatus(str, Enum):
    """Overall status of a blog post."""

    KEYWORD_PENDING = "keyword_pending"
    GENERATING = "generating"
    EDITING = "editing"
    COMPLETE = "complete"


class BlogCampaign(Base):
    """BlogCampaign model for blog initiatives tied to keyword clusters.

    Attributes:
        id: UUID primary key
        project_id: Reference to the parent project
        cluster_id: UNIQUE reference to keyword cluster (1:1)
        name: Display name for the campaign
        status: Workflow status
        generation_metadata: JSONB for AI generation context
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "blog_campaigns"

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

    cluster_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("keyword_clusters.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CampaignStatus.PLANNING.value,
        server_default=text("'planning'"),
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
        back_populates="blog_campaigns",
    )

    cluster: Mapped["KeywordCluster"] = relationship(
        "KeywordCluster",
        back_populates="blog_campaign",
    )

    posts: Mapped[list["BlogPost"]] = relationship(
        "BlogPost",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<BlogCampaign(id={self.id!r}, name={self.name!r}, status={self.status!r})>"


class BlogPost(Base):
    """BlogPost model for individual blog posts within a campaign.

    Attributes:
        id: UUID primary key
        campaign_id: Reference to the parent blog campaign
        primary_keyword: Target keyword for this post
        url_slug: Generated URL slug
        search_volume: Estimated monthly search volume
        source_page_id: Optional link to cluster page that seeded this topic
        title: Page title
        meta_description: Meta description for SEO
        content: Single HTML content field
        pop_brief: JSONB for POP report brief data
        is_approved: Whether the keyword is approved
        content_status: Content generation status
        content_approved: Whether the content is approved
        qa_results: JSONB for QA check results
        status: Overall post status
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated
    """

    __tablename__ = "blog_posts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    campaign_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("blog_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    primary_keyword: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    url_slug: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    search_volume: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    source_page_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("cluster_pages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    meta_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    pop_brief: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    content_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ContentStatus.PENDING.value,
        server_default=text("'pending'"),
    )

    content_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    qa_results: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=PostStatus.KEYWORD_PENDING.value,
        server_default=text("'keyword_pending'"),
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
    campaign: Mapped["BlogCampaign"] = relationship(
        "BlogCampaign",
        back_populates="posts",
    )

    source_page: Mapped["ClusterPage | None"] = relationship(
        "ClusterPage",
    )

    def __repr__(self) -> str:
        return f"<BlogPost(id={self.id!r}, keyword={self.primary_keyword!r}, status={self.status!r})>"
