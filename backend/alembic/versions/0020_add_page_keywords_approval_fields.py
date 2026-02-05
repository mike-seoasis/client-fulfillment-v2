"""Add approval and scoring fields to page_keywords table.

Adds fields needed for Phase 4 - Primary Keyword + Approval:
- is_approved: Boolean for approval status
- is_priority: Boolean for priority flagging
- alternative_keywords: JSONB array of alternative keyword suggestions
- composite_score: Float for overall keyword score
- relevance_score: Float for relevance to page content
- ai_reasoning: Text explaining AI's keyword recommendation

Revision ID: 0020
Revises: 0019
Create Date: 2026-02-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add approval and scoring fields to page_keywords table."""
    # Add is_approved Boolean field with default=False
    op.add_column(
        "page_keywords",
        sa.Column(
            "is_approved",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # Add is_priority Boolean field with default=False
    op.add_column(
        "page_keywords",
        sa.Column(
            "is_priority",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # Add alternative_keywords JSONB field with default=[]
    op.add_column(
        "page_keywords",
        sa.Column(
            "alternative_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    # Add composite_score Float field (nullable)
    op.add_column(
        "page_keywords",
        sa.Column("composite_score", sa.Float(), nullable=True),
    )

    # Add relevance_score Float field (nullable)
    op.add_column(
        "page_keywords",
        sa.Column("relevance_score", sa.Float(), nullable=True),
    )

    # Add ai_reasoning Text field (nullable)
    op.add_column(
        "page_keywords",
        sa.Column("ai_reasoning", sa.Text(), nullable=True),
    )

    # Add index on is_approved for filtering approved keywords
    op.create_index(
        op.f("ix_page_keywords_is_approved"),
        "page_keywords",
        ["is_approved"],
        unique=False,
    )

    # Add index on is_priority for filtering priority keywords
    op.create_index(
        op.f("ix_page_keywords_is_priority"),
        "page_keywords",
        ["is_priority"],
        unique=False,
    )


def downgrade() -> None:
    """Remove approval and scoring fields from page_keywords table."""
    op.drop_index(op.f("ix_page_keywords_is_priority"), table_name="page_keywords")
    op.drop_index(op.f("ix_page_keywords_is_approved"), table_name="page_keywords")
    op.drop_column("page_keywords", "ai_reasoning")
    op.drop_column("page_keywords", "relevance_score")
    op.drop_column("page_keywords", "composite_score")
    op.drop_column("page_keywords", "alternative_keywords")
    op.drop_column("page_keywords", "is_priority")
    op.drop_column("page_keywords", "is_approved")
