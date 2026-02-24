"""Add approval fields to page_contents table.

Phase 6 - Content Review + Editing:
- is_approved: Boolean for content approval status
- approved_at: DateTime for when content was approved

Revision ID: 0022
Revises: 0021
Create Date: 2026-02-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add approval fields to page_contents table."""
    op.add_column(
        "page_contents",
        sa.Column(
            "is_approved",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.add_column(
        "page_contents",
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        op.f("ix_page_contents_is_approved"),
        "page_contents",
        ["is_approved"],
        unique=False,
    )


def downgrade() -> None:
    """Remove approval fields from page_contents table."""
    op.drop_index(op.f("ix_page_contents_is_approved"), table_name="page_contents")
    op.drop_column("page_contents", "approved_at")
    op.drop_column("page_contents", "is_approved")
