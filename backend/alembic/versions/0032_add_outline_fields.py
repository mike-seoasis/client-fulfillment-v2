"""Add outline fields to page_contents.

Revision ID: 0032
Revises: 0031
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "page_contents",
        sa.Column("outline_json", JSONB, nullable=True),
    )
    op.add_column(
        "page_contents",
        sa.Column("outline_status", sa.String(30), nullable=True),
    )
    op.add_column(
        "page_contents",
        sa.Column("google_doc_url", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_page_contents_outline_status",
        "page_contents",
        ["outline_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_page_contents_outline_status", table_name="page_contents")
    op.drop_column("page_contents", "google_doc_url")
    op.drop_column("page_contents", "outline_status")
    op.drop_column("page_contents", "outline_json")
