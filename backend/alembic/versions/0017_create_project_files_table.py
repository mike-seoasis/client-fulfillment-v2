"""Create project_files table for uploaded brand documents.

Revision ID: 0017
Revises: 0016
Create Date: 2026-02-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create project_files table."""
    op.create_table(
        "project_files",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("s3_key", sa.String(length=1024), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_files_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("s3_key", name="uq_project_files_s3_key"),
    )
    # Index on project_id for efficient queries
    op.create_index(
        op.f("ix_project_files_project_id"),
        "project_files",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop project_files table."""
    op.drop_index(op.f("ix_project_files_project_id"), table_name="project_files")
    op.drop_table("project_files")
