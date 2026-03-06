"""Add Shopify connection fields to projects table.

Revision ID: 0029
Revises: 0028
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("shopify_store_domain", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("shopify_access_token_encrypted", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("shopify_scopes", sa.Text(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("shopify_last_sync_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("projects", sa.Column("shopify_sync_status", sa.Text(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("shopify_connected_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "shopify_connected_at")
    op.drop_column("projects", "shopify_sync_status")
    op.drop_column("projects", "shopify_last_sync_at")
    op.drop_column("projects", "shopify_scopes")
    op.drop_column("projects", "shopify_access_token_encrypted")
    op.drop_column("projects", "shopify_store_domain")
