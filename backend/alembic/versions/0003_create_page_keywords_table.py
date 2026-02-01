"""Create page_keywords table with primary/secondary keyword structure.

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-31

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create page_keywords table."""
    op.create_table(
        "page_keywords",
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
        sa.Column("primary_keyword", sa.Text(), nullable=False),
        sa.Column(
            "secondary_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("search_volume", sa.Integer(), nullable=True),
        sa.Column("difficulty_score", sa.Integer(), nullable=True),
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
            name="fk_page_keywords_crawled_page_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_page_keywords_crawled_page_id"),
        "page_keywords",
        ["crawled_page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_page_keywords_primary_keyword"),
        "page_keywords",
        ["primary_keyword"],
        unique=False,
    )


def downgrade() -> None:
    """Drop page_keywords table."""
    op.drop_index(op.f("ix_page_keywords_primary_keyword"), table_name="page_keywords")
    op.drop_index(op.f("ix_page_keywords_crawled_page_id"), table_name="page_keywords")
    op.drop_table("page_keywords")
