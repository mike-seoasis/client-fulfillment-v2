"""Create page_contents and prompt_logs tables, add unique constraint to content_briefs.page_id.

Phase 5 - Content Generation:
- Creates page_contents table for storing generated content per page (one-to-one with crawled_pages)
- Creates prompt_logs table for persisting Claude prompt/response exchanges
- Adds unique constraint to content_briefs.page_id for one-to-one relationship
- Does NOT create content_scores table (deferred to Phase 6)
- Does NOT drop generated_content table

Revision ID: 0021
Revises: 0020
Create Date: 2026-02-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create page_contents and prompt_logs tables."""
    # 1. Create page_contents table
    op.create_table(
        "page_contents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "crawled_page_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("page_title", sa.Text(), nullable=True),
        sa.Column("meta_description", sa.Text(), nullable=True),
        sa.Column("top_description", sa.Text(), nullable=True),
        sa.Column("bottom_description", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "qa_results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "generation_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "generation_completed_at",
            sa.DateTime(timezone=True),
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
            ["crawled_page_id"],
            ["crawled_pages.id"],
            name="fk_page_contents_crawled_page_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("crawled_page_id", name="uq_page_contents_crawled_page_id"),
    )
    op.create_index(
        op.f("ix_page_contents_crawled_page_id"),
        "page_contents",
        ["crawled_page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_page_contents_status"),
        "page_contents",
        ["status"],
        unique=False,
    )

    # 2. Create prompt_logs table
    op.create_table(
        "prompt_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "page_content_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("step", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["page_content_id"],
            ["page_contents.id"],
            name="fk_prompt_logs_page_content_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_prompt_logs_page_content_id"),
        "prompt_logs",
        ["page_content_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prompt_logs_step"),
        "prompt_logs",
        ["step"],
        unique=False,
    )

    # 3. Make content_briefs.page_id unique (one-to-one with crawled_pages)
    # Drop the existing non-unique index first, then recreate as unique
    op.drop_index(
        op.f("ix_content_briefs_page_id"),
        table_name="content_briefs",
    )
    op.create_index(
        op.f("ix_content_briefs_page_id"),
        "content_briefs",
        ["page_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop page_contents and prompt_logs tables, revert content_briefs unique constraint."""
    # Revert content_briefs.page_id to non-unique index
    op.drop_index(
        op.f("ix_content_briefs_page_id"),
        table_name="content_briefs",
    )
    op.create_index(
        op.f("ix_content_briefs_page_id"),
        "content_briefs",
        ["page_id"],
        unique=False,
    )

    # Drop prompt_logs table
    op.drop_index(op.f("ix_prompt_logs_step"), table_name="prompt_logs")
    op.drop_index(op.f("ix_prompt_logs_page_content_id"), table_name="prompt_logs")
    op.drop_table("prompt_logs")

    # Drop page_contents table
    op.drop_index(op.f("ix_page_contents_status"), table_name="page_contents")
    op.drop_index(op.f("ix_page_contents_crawled_page_id"), table_name="page_contents")
    op.drop_table("page_contents")
