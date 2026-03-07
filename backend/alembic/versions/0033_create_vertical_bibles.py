"""Create vertical_bibles table.

Revision ID: 0033
Revises: 0032
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vertical_bibles",
        sa.Column(
            "id",
            UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column(
            "content_md", sa.Text(), server_default=sa.text("''"), nullable=False
        ),
        sa.Column(
            "trigger_keywords",
            JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "qa_rules",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
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
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "project_id", "slug", name="uq_vertical_bibles_project_slug"
        ),
    )
    op.create_index(
        "ix_vertical_bibles_project_id", "vertical_bibles", ["project_id"]
    )
    op.create_index("ix_vertical_bibles_slug", "vertical_bibles", ["slug"])
    op.create_index(
        "ix_vertical_bibles_trigger_keywords",
        "vertical_bibles",
        ["trigger_keywords"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_vertical_bibles_qa_rules",
        "vertical_bibles",
        ["qa_rules"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_vertical_bibles_qa_rules", table_name="vertical_bibles")
    op.drop_index(
        "ix_vertical_bibles_trigger_keywords", table_name="vertical_bibles"
    )
    op.drop_index("ix_vertical_bibles_slug", table_name="vertical_bibles")
    op.drop_index("ix_vertical_bibles_project_id", table_name="vertical_bibles")
    op.drop_table("vertical_bibles")
