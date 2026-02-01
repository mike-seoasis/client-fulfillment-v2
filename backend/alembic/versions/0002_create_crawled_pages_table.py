"""Create crawled_pages table with normalized_url, category, labels fields.

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create crawled_pages table."""
    op.create_table(
        "crawled_pages",
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
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("raw_url", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column(
            "labels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
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
            name="fk_crawled_pages_project_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_crawled_pages_project_id"), "crawled_pages", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_crawled_pages_normalized_url"),
        "crawled_pages",
        ["normalized_url"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crawled_pages_category"), "crawled_pages", ["category"], unique=False
    )
    # Unique constraint: one normalized_url per project
    op.create_index(
        "ix_crawled_pages_project_url_unique",
        "crawled_pages",
        ["project_id", "normalized_url"],
        unique=True,
    )


def downgrade() -> None:
    """Drop crawled_pages table."""
    op.drop_index("ix_crawled_pages_project_url_unique", table_name="crawled_pages")
    op.drop_index(op.f("ix_crawled_pages_category"), table_name="crawled_pages")
    op.drop_index(op.f("ix_crawled_pages_normalized_url"), table_name="crawled_pages")
    op.drop_index(op.f("ix_crawled_pages_project_id"), table_name="crawled_pages")
    op.drop_table("crawled_pages")
