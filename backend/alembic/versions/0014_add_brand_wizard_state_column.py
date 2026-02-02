"""Add brand_wizard_state JSONB column to projects table.

Stores the state of the 7-step brand configuration wizard including:
- Current step number
- Data entered in each step
- Research results from Perplexity

Revision ID: 0014
Revises: 0013
Create Date: 2026-02-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add brand_wizard_state column to projects table."""
    op.add_column(
        "projects",
        sa.Column(
            "brand_wizard_state",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove brand_wizard_state column from projects table."""
    op.drop_column("projects", "brand_wizard_state")
