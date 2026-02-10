"""Create link_plan_snapshots table.

Phase 9 - Internal Linking:
- link_plan_snapshots: Stores full link plan snapshots for audit and rollback
- JSONB plan_data includes pre-injection content per page

Revision ID: 0025
Revises: 0024
Create Date: 2026-02-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "link_plan_snapshots",
        sa.Column(
            "id",
            sa.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("cluster_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("plan_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("total_links", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cluster_id"],
            ["keyword_clusters.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_link_plan_snapshots_project_id_scope",
        "link_plan_snapshots",
        ["project_id", "scope"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_link_plan_snapshots_project_id_scope",
        table_name="link_plan_snapshots",
    )
    op.drop_table("link_plan_snapshots")
