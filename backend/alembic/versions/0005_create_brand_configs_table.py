"""Create brand_configs table with v2_schema JSONB field.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create brand_configs table."""
    op.create_table(
        "brand_configs",
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
        sa.Column("brand_name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column(
            "v2_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
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
            name="fk_brand_configs_project_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_brand_configs_project_id"),
        "brand_configs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_brand_configs_brand_name"),
        "brand_configs",
        ["brand_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_brand_configs_domain"),
        "brand_configs",
        ["domain"],
        unique=False,
    )


def downgrade() -> None:
    """Drop brand_configs table."""
    op.drop_index(op.f("ix_brand_configs_domain"), table_name="brand_configs")
    op.drop_index(op.f("ix_brand_configs_brand_name"), table_name="brand_configs")
    op.drop_index(op.f("ix_brand_configs_project_id"), table_name="brand_configs")
    op.drop_table("brand_configs")
