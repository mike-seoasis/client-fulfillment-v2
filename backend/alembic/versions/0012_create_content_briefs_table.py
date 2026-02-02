"""Create content_briefs table for storing POP content brief data.

Revision ID: 0012
Revises: 0011
Create Date: 2026-02-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create content_briefs table."""
    op.create_table(
        "content_briefs",
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
        sa.Column("keyword", sa.Text(), nullable=False),
        sa.Column("pop_task_id", sa.String(length=255), nullable=True),
        sa.Column("word_count_target", sa.Integer(), nullable=True),
        sa.Column("word_count_min", sa.Integer(), nullable=True),
        sa.Column("word_count_max", sa.Integer(), nullable=True),
        sa.Column(
            "heading_targets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "keyword_targets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "lsi_terms",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "entities",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "related_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "related_searches",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "competitors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("page_score_target", sa.Float(), nullable=True),
        sa.Column(
            "raw_response",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
            ["page_id"],
            ["crawled_pages.id"],
            name="fk_content_briefs_page_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_content_briefs_page_id"),
        "content_briefs",
        ["page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_briefs_keyword"),
        "content_briefs",
        ["keyword"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_briefs_pop_task_id"),
        "content_briefs",
        ["pop_task_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop content_briefs table."""
    op.drop_index(op.f("ix_content_briefs_pop_task_id"), table_name="content_briefs")
    op.drop_index(op.f("ix_content_briefs_keyword"), table_name="content_briefs")
    op.drop_index(op.f("ix_content_briefs_page_id"), table_name="content_briefs")
    op.drop_table("content_briefs")
