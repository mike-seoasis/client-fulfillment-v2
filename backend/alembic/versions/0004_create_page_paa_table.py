"""Create page_paa table for People Also Ask enrichment data.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create page_paa table."""
    op.create_table(
        "page_paa",
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
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer_snippet", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "related_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=True),
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
            name="fk_page_paa_crawled_page_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_page_paa_crawled_page_id"),
        "page_paa",
        ["crawled_page_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_page_paa_question"),
        "page_paa",
        ["question"],
        unique=False,
    )


def downgrade() -> None:
    """Drop page_paa table."""
    op.drop_index(op.f("ix_page_paa_question"), table_name="page_paa")
    op.drop_index(op.f("ix_page_paa_crawled_page_id"), table_name="page_paa")
    op.drop_table("page_paa")
