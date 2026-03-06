"""Create shopify_pages table.

Revision ID: 0030
Revises: 0029
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shopify_pages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("shopify_id", sa.Text(), nullable=False),
        sa.Column("page_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("handle", sa.Text(), nullable=True),
        sa.Column("full_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("product_type", sa.Text(), nullable=True),
        sa.Column("product_count", sa.Integer(), nullable=True),
        sa.Column("blog_name", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("shopify_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
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
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("project_id", "shopify_id", name="uq_shopify_pages_project_shopify"),
    )

    # Composite index for category sidebar queries
    op.create_index(
        "ix_shopify_pages_project_type_deleted",
        "shopify_pages",
        ["project_id", "page_type", "is_deleted"],
    )


def downgrade() -> None:
    op.drop_index("ix_shopify_pages_project_type_deleted", table_name="shopify_pages")
    op.drop_table("shopify_pages")
