"""Add site_url column to projects and make client_id nullable.

Revision ID: 0016
Revises: 0015
Create Date: 2026-02-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add site_url column and make client_id nullable."""
    # Add site_url column (required, indexed)
    op.add_column(
        "projects",
        sa.Column(
            "site_url",
            sa.String(length=2048),
            nullable=False,
            server_default="",  # Temporary default for existing rows
        ),
    )
    op.create_index(op.f("ix_projects_site_url"), "projects", ["site_url"], unique=False)

    # Remove temporary default after backfilling existing rows
    op.alter_column("projects", "site_url", server_default=None)

    # Make client_id nullable
    op.alter_column(
        "projects",
        "client_id",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    """Remove site_url column and make client_id required again."""
    # Make client_id required again (may fail if nulls exist)
    op.alter_column(
        "projects",
        "client_id",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    # Remove site_url column and index
    op.drop_index(op.f("ix_projects_site_url"), table_name="projects")
    op.drop_column("projects", "site_url")
