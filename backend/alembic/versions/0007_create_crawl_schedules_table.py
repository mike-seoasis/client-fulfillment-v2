"""Create crawl_schedules table for managing scheduled crawl jobs.

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create crawl_schedules table."""
    op.create_table(
        "crawl_schedules",
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
        sa.Column("schedule_type", sa.String(length=50), nullable=False),
        sa.Column("cron_expression", sa.String(length=100), nullable=True),
        sa.Column("start_url", sa.Text(), nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=True),
        sa.Column("max_depth", sa.Integer(), nullable=True),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
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
            name="fk_crawl_schedules_project_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_crawl_schedules_project_id"), "crawl_schedules", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_crawl_schedules_schedule_type"), "crawl_schedules", ["schedule_type"], unique=False
    )
    op.create_index(
        op.f("ix_crawl_schedules_is_active"), "crawl_schedules", ["is_active"], unique=False
    )
    op.create_index(
        op.f("ix_crawl_schedules_next_run_at"), "crawl_schedules", ["next_run_at"], unique=False
    )


def downgrade() -> None:
    """Drop crawl_schedules table."""
    op.drop_index(op.f("ix_crawl_schedules_next_run_at"), table_name="crawl_schedules")
    op.drop_index(op.f("ix_crawl_schedules_is_active"), table_name="crawl_schedules")
    op.drop_index(op.f("ix_crawl_schedules_schedule_type"), table_name="crawl_schedules")
    op.drop_index(op.f("ix_crawl_schedules_project_id"), table_name="crawl_schedules")
    op.drop_table("crawl_schedules")
