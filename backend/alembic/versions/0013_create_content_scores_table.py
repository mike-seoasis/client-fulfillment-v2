"""Create content_scores table for storing POP scoring results.

Revision ID: 0013
Revises: 0012
Create Date: 2026-02-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create content_scores table."""
    op.create_table(
        "content_scores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("pop_task_id", sa.String(length=255), nullable=True),
        sa.Column("page_score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column(
            "keyword_analysis",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "lsi_coverage",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("word_count_current", sa.Integer(), nullable=True),
        sa.Column(
            "heading_analysis",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "recommendations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("fallback_used", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "raw_response",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["crawled_pages.id"],
            name="fk_content_scores_page_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_content_scores_page_id"),
        "content_scores",
        ["page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_scores_pop_task_id"),
        "content_scores",
        ["pop_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_scores_scored_at"),
        "content_scores",
        ["scored_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_scores_passed"),
        "content_scores",
        ["passed"],
        unique=False,
    )


def downgrade() -> None:
    """Drop content_scores table."""
    op.drop_index(op.f("ix_content_scores_passed"), table_name="content_scores")
    op.drop_index(op.f("ix_content_scores_scored_at"), table_name="content_scores")
    op.drop_index(op.f("ix_content_scores_pop_task_id"), table_name="content_scores")
    op.drop_index(op.f("ix_content_scores_page_id"), table_name="content_scores")
    op.drop_table("content_scores")
