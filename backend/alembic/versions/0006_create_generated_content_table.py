"""Create generated_content table with qa_results JSONB field.

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create generated_content table."""
    op.create_table(
        "generated_content",
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
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("prompt_used", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column(
            "qa_results",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'draft'"),
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
            ["crawled_page_id"],
            ["crawled_pages.id"],
            name="fk_generated_content_crawled_page_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_generated_content_crawled_page_id"),
        "generated_content",
        ["crawled_page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_content_content_type"),
        "generated_content",
        ["content_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_content_status"),
        "generated_content",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop generated_content table."""
    op.drop_index(op.f("ix_generated_content_status"), table_name="generated_content")
    op.drop_index(op.f("ix_generated_content_content_type"), table_name="generated_content")
    op.drop_index(op.f("ix_generated_content_crawled_page_id"), table_name="generated_content")
    op.drop_table("generated_content")
