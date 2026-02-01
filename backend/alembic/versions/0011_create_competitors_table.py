"""Create competitors table for storing competitor URLs and scraped content.

Revision ID: 0011
Revises: 0010
Create Date: 2026-02-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create competitors table."""
    op.create_table(
        "competitors",
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
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "content",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "pages_scraped",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("scrape_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scrape_completed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["project_id"],
            ["projects.id"],
            name="fk_competitors_project_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_competitors_project_id"),
        "competitors",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_competitors_url"),
        "competitors",
        ["url"],
        unique=False,
    )
    op.create_index(
        op.f("ix_competitors_status"),
        "competitors",
        ["status"],
        unique=False,
    )
    # Composite unique index for project_id + url to prevent duplicate competitors
    op.create_index(
        "ix_competitors_project_url_unique",
        "competitors",
        ["project_id", "url"],
        unique=True,
    )


def downgrade() -> None:
    """Drop competitors table."""
    op.drop_index("ix_competitors_project_url_unique", table_name="competitors")
    op.drop_index(op.f("ix_competitors_status"), table_name="competitors")
    op.drop_index(op.f("ix_competitors_url"), table_name="competitors")
    op.drop_index(op.f("ix_competitors_project_id"), table_name="competitors")
    op.drop_table("competitors")
