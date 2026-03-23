"""Add source column to keyword_clusters to distinguish cluster-tool vs wordpress silo clusters.

Revision ID: 0034
Revises: 0033
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "keyword_clusters",
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="cluster_tool",
        ),
    )
    op.create_index(
        "ix_keyword_clusters_source",
        "keyword_clusters",
        ["source"],
    )

    # Data migration: tag existing WordPress silo clusters.
    # WordPress silo clusters are linked to crawled_pages with source='wordpress'
    # via the cluster_pages join table.
    op.execute(
        """
        UPDATE keyword_clusters
        SET source = 'wordpress'
        WHERE id IN (
            SELECT DISTINCT kc.id
            FROM keyword_clusters kc
            JOIN cluster_pages cp ON cp.cluster_id = kc.id
            JOIN crawled_pages crp ON crp.id = cp.crawled_page_id
            WHERE crp.source = 'wordpress'
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_keyword_clusters_source", table_name="keyword_clusters")
    op.drop_column("keyword_clusters", "source")
