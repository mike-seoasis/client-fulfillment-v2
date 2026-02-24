"""Create internal_links table.

Phase 9 - Internal Linking:
- internal_links: Edge table for page-to-page internal links
- Supports both onboarding-scope and cluster-scope links
- Tracks anchor text, placement method, and lifecycle status

Revision ID: 0024
Revises: 0023
Create Date: 2026-02-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create internal_links table."""
    op.create_table(
        "internal_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "source_page_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "target_page_id",
            postgresql.UUID(as_uuid=False),
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
            nullable=True,
        ),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("anchor_text", sa.Text(), nullable=False),
        sa.Column("anchor_type", sa.String(length=20), nullable=False),
        sa.Column("position_in_content", sa.Integer(), nullable=True),
        sa.Column(
            "is_mandatory",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("placement_method", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'planned'"),
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
            ["source_page_id"],
            ["crawled_pages.id"],
            name="fk_internal_links_source_page_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_page_id"],
            ["crawled_pages.id"],
            name="fk_internal_links_target_page_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_internal_links_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["keyword_clusters.id"],
            name="fk_internal_links_cluster_id",
            ondelete="SET NULL",
        ),
    )
    # Individual indexes
    op.create_index(
        op.f("ix_internal_links_source_page_id"),
        "internal_links",
        ["source_page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_internal_links_target_page_id"),
        "internal_links",
        ["target_page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_internal_links_cluster_id"),
        "internal_links",
        ["cluster_id"],
        unique=False,
    )
    # Composite index for project + scope queries
    op.create_index(
        "ix_internal_links_project_id_scope",
        "internal_links",
        ["project_id", "scope"],
        unique=False,
    )


def downgrade() -> None:
    """Drop internal_links table."""
    op.drop_index("ix_internal_links_project_id_scope", table_name="internal_links")
    op.drop_index(op.f("ix_internal_links_cluster_id"), table_name="internal_links")
    op.drop_index(op.f("ix_internal_links_target_page_id"), table_name="internal_links")
    op.drop_index(op.f("ix_internal_links_source_page_id"), table_name="internal_links")
    op.drop_table("internal_links")
