"""Add keyword_clusters and cluster_pages tables, source column to crawled_pages.

Phase 8 - Keyword Cluster Creation:
- keyword_clusters: Groups of related keywords built around a seed keyword
- cluster_pages: Individual pages within a keyword cluster
- crawled_pages.source: Distinguishes 'onboarding' vs 'cluster' page origins

Revision ID: 0023
Revises: 0022
Create Date: 2026-02-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create keyword_clusters and cluster_pages tables, add source column to crawled_pages."""
    # --- keyword_clusters table ---
    op.create_table(
        "keyword_clusters",
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
        sa.Column("seed_keyword", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'generating'"),
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
            name="fk_keyword_clusters_project_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_keyword_clusters_project_id"),
        "keyword_clusters",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_keyword_clusters_status"),
        "keyword_clusters",
        ["status"],
        unique=False,
    )

    # --- cluster_pages table ---
    op.create_table(
        "cluster_pages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "cluster_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("keyword", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("url_slug", sa.Text(), nullable=False),
        sa.Column("expansion_strategy", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("search_volume", sa.Integer(), nullable=True),
        sa.Column("cpc", sa.Float(), nullable=True),
        sa.Column("competition", sa.Float(), nullable=True),
        sa.Column("competition_level", sa.String(length=50), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column(
            "is_approved",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "crawled_page_id",
            postgresql.UUID(as_uuid=False),
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
            ["cluster_id"],
            ["keyword_clusters.id"],
            name="fk_cluster_pages_cluster_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["crawled_page_id"],
            ["crawled_pages.id"],
            name="fk_cluster_pages_crawled_page_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        op.f("ix_cluster_pages_cluster_id"),
        "cluster_pages",
        ["cluster_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cluster_pages_crawled_page_id"),
        "cluster_pages",
        ["crawled_page_id"],
        unique=False,
    )

    # --- Add source column to crawled_pages ---
    op.add_column(
        "crawled_pages",
        sa.Column(
            "source",
            sa.String(length=20),
            server_default=sa.text("'onboarding'"),
            nullable=False,
        ),
    )
    # Backfill existing rows (server_default handles this for new rows,
    # but explicit UPDATE ensures existing rows get the value)
    op.execute("UPDATE crawled_pages SET source = 'onboarding' WHERE source IS NULL")
    op.create_index(
        op.f("ix_crawled_pages_source"),
        "crawled_pages",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    """Drop keyword_clusters and cluster_pages tables, remove source column from crawled_pages."""
    # --- Remove source column from crawled_pages ---
    op.drop_index(op.f("ix_crawled_pages_source"), table_name="crawled_pages")
    op.drop_column("crawled_pages", "source")

    # --- Drop cluster_pages table ---
    op.drop_index(op.f("ix_cluster_pages_crawled_page_id"), table_name="cluster_pages")
    op.drop_index(op.f("ix_cluster_pages_cluster_id"), table_name="cluster_pages")
    op.drop_table("cluster_pages")

    # --- Drop keyword_clusters table ---
    op.drop_index(op.f("ix_keyword_clusters_status"), table_name="keyword_clusters")
    op.drop_index(op.f("ix_keyword_clusters_project_id"), table_name="keyword_clusters")
    op.drop_table("keyword_clusters")
