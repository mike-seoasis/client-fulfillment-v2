"""Rename project phases for better UX clarity.

Renames phase keys in existing project records:
- discovery → brand_setup
- requirements → site_analysis
- implementation → content_generation
- review → review_edit
- launch → export

Revision ID: 0015
Revises: 0014
Create Date: 2026-02-02

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Phase name mappings
PHASE_RENAME_MAP = {
    "discovery": "brand_setup",
    "requirements": "site_analysis",
    "implementation": "content_generation",
    "review": "review_edit",
    "launch": "export",
}

PHASE_RENAME_MAP_REVERSE = {v: k for k, v in PHASE_RENAME_MAP.items()}


def upgrade() -> None:
    """Rename phase keys in existing project records."""
    # Use raw SQL to update JSONB keys
    # For each old key, rename to new key if it exists
    for old_key, new_key in PHASE_RENAME_MAP.items():
        op.execute(
            f"""
            UPDATE projects
            SET phase_status = (phase_status - '{old_key}') ||
                jsonb_build_object('{new_key}', phase_status->'{old_key}')
            WHERE phase_status ? '{old_key}'
            """
        )


def downgrade() -> None:
    """Revert phase key renames."""
    for new_key, old_key in PHASE_RENAME_MAP_REVERSE.items():
        op.execute(
            f"""
            UPDATE projects
            SET phase_status = (phase_status - '{new_key}') ||
                jsonb_build_object('{old_key}', phase_status->'{new_key}')
            WHERE phase_status ? '{new_key}'
            """
        )
