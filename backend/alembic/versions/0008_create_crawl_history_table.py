"""Create crawl_history table for tracking crawl job execution history.

Revision ID: 0008
Revises: 0007
Create Date: 2026-02-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create crawl_history table."""
    op.create_table(
        "crawl_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("trigger_type", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pages_crawled", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pages_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "stats",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "error_log",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            ["schedule_id"],
            ["crawl_schedules.id"],
            name="fk_crawl_history_schedule_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_crawl_history_project_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_crawl_history_schedule_id"), "crawl_history", ["schedule_id"], unique=False
    )
    op.create_index(
        op.f("ix_crawl_history_project_id"), "crawl_history", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_crawl_history_status"), "crawl_history", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_crawl_history_started_at"), "crawl_history", ["started_at"], unique=False
    )


def downgrade() -> None:
    """Drop crawl_history table."""
    op.drop_index(op.f("ix_crawl_history_started_at"), table_name="crawl_history")
    op.drop_index(op.f("ix_crawl_history_status"), table_name="crawl_history")
    op.drop_index(op.f("ix_crawl_history_project_id"), table_name="crawl_history")
    op.drop_index(op.f("ix_crawl_history_schedule_id"), table_name="crawl_history")
    op.drop_table("crawl_history")
