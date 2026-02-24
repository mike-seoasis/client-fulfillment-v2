"""Add crawl status and extraction fields to CrawledPage.

Revision ID: 0019
Revises: 0018
Create Date: 2026-02-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add crawl status and content extraction fields to crawled_pages table."""
    # Add status column with default 'pending'
    op.add_column(
        "crawled_pages",
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_crawled_pages_status"), "crawled_pages", ["status"], unique=False
    )

    # Add content extraction fields
    op.add_column(
        "crawled_pages",
        sa.Column("meta_description", sa.Text(), nullable=True),
    )
    op.add_column(
        "crawled_pages",
        sa.Column("body_content", sa.Text(), nullable=True),
    )
    op.add_column(
        "crawled_pages",
        sa.Column(
            "headings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "crawled_pages",
        sa.Column("product_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "crawled_pages",
        sa.Column("crawl_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "crawled_pages",
        sa.Column("word_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove crawl status and content extraction fields from crawled_pages table."""
    op.drop_column("crawled_pages", "word_count")
    op.drop_column("crawled_pages", "crawl_error")
    op.drop_column("crawled_pages", "product_count")
    op.drop_column("crawled_pages", "headings")
    op.drop_column("crawled_pages", "body_content")
    op.drop_column("crawled_pages", "meta_description")
    op.drop_index(op.f("ix_crawled_pages_status"), table_name="crawled_pages")
    op.drop_column("crawled_pages", "status")
