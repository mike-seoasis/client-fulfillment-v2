"""Add additional_info column to projects table.

Revision ID: 0018
Revises: 0017
Create Date: 2026-02-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add additional_info column to projects table."""
    op.add_column(
        "projects",
        sa.Column(
            "additional_info",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove additional_info column from projects table."""
    op.drop_column("projects", "additional_info")
