"""Create blog_campaigns and blog_posts tables.

Phase 11 - Blog Planning & Writing:
- blog_campaigns: Blog initiatives tied 1:1 to keyword clusters
- blog_posts: Individual blog posts within a campaign

Revision ID: 0026
Revises: 0025
Create Date: 2026-02-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: str | tuple[str, ...] | None = ("0025", "da1ea5f253b0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create blog_campaigns and blog_posts tables."""
    # --- blog_campaigns table ---
    op.create_table(
        "blog_campaigns",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'planning'"),
            nullable=False,
        ),
        sa.Column(
            "generation_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_blog_campaigns_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["keyword_clusters.id"],
            name="fk_blog_campaigns_cluster_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("cluster_id", name="uq_blog_campaigns_cluster_id"),
    )
    op.create_index(
        op.f("ix_blog_campaigns_project_id"),
        "blog_campaigns",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_blog_campaigns_cluster_id"),
        "blog_campaigns",
        ["cluster_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_blog_campaigns_status"),
        "blog_campaigns",
        ["status"],
        unique=False,
    )

    # --- blog_posts table ---
    op.create_table(
        "blog_posts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("primary_keyword", sa.Text(), nullable=False),
        sa.Column("url_slug", sa.String(length=255), nullable=False),
        sa.Column("search_volume", sa.Integer(), nullable=True),
        sa.Column(
            "source_page_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "pop_brief",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "is_approved",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "content_status",
            sa.String(length=50),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "content_approved",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "qa_results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'keyword_pending'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["blog_campaigns.id"],
            name="fk_blog_posts_campaign_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_page_id"],
            ["cluster_pages.id"],
            name="fk_blog_posts_source_page_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        op.f("ix_blog_posts_campaign_id"),
        "blog_posts",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_blog_posts_source_page_id"),
        "blog_posts",
        ["source_page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_blog_posts_status"),
        "blog_posts",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop blog_posts and blog_campaigns tables."""
    # --- Drop blog_posts table (child first) ---
    op.drop_index(op.f("ix_blog_posts_status"), table_name="blog_posts")
    op.drop_index(op.f("ix_blog_posts_source_page_id"), table_name="blog_posts")
    op.drop_index(op.f("ix_blog_posts_campaign_id"), table_name="blog_posts")
    op.drop_table("blog_posts")

    # --- Drop blog_campaigns table ---
    op.drop_index(op.f("ix_blog_campaigns_status"), table_name="blog_campaigns")
    op.drop_index(op.f("ix_blog_campaigns_cluster_id"), table_name="blog_campaigns")
    op.drop_index(op.f("ix_blog_campaigns_project_id"), table_name="blog_campaigns")
    op.drop_table("blog_campaigns")
