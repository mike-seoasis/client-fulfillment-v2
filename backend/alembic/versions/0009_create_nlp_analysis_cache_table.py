"""Create nlp_analysis_cache table for caching NLP analysis results on competitor data.

Revision ID: 0009
Revises: 0008
Create Date: 2026-02-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create nlp_analysis_cache table."""
    op.create_table(
        "nlp_analysis_cache",
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
        sa.Column("competitor_url", sa.Text(), nullable=False),
        sa.Column("analysis_type", sa.String(length=50), nullable=False),
        sa.Column(
            "analysis_results",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("model_version", sa.String(length=100), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "hit_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
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
            name="fk_nlp_analysis_cache_project_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_nlp_analysis_cache_project_id"),
        "nlp_analysis_cache",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nlp_analysis_cache_competitor_url"),
        "nlp_analysis_cache",
        ["competitor_url"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nlp_analysis_cache_analysis_type"),
        "nlp_analysis_cache",
        ["analysis_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nlp_analysis_cache_content_hash"),
        "nlp_analysis_cache",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_nlp_analysis_cache_expires_at"),
        "nlp_analysis_cache",
        ["expires_at"],
        unique=False,
    )
    # Composite index for efficient cache lookups by project, URL, and analysis type
    op.create_index(
        "ix_nlp_analysis_cache_lookup",
        "nlp_analysis_cache",
        ["project_id", "competitor_url", "analysis_type"],
        unique=False,
    )


def downgrade() -> None:
    """Drop nlp_analysis_cache table."""
    op.drop_index("ix_nlp_analysis_cache_lookup", table_name="nlp_analysis_cache")
    op.drop_index(op.f("ix_nlp_analysis_cache_expires_at"), table_name="nlp_analysis_cache")
    op.drop_index(op.f("ix_nlp_analysis_cache_content_hash"), table_name="nlp_analysis_cache")
    op.drop_index(op.f("ix_nlp_analysis_cache_analysis_type"), table_name="nlp_analysis_cache")
    op.drop_index(op.f("ix_nlp_analysis_cache_competitor_url"), table_name="nlp_analysis_cache")
    op.drop_index(op.f("ix_nlp_analysis_cache_project_id"), table_name="nlp_analysis_cache")
    op.drop_table("nlp_analysis_cache")
