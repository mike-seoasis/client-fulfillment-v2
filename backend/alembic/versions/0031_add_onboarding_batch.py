"""Add onboarding_batch column to crawled_pages.

Revision ID: 0031
Revises: 0030
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crawled_pages",
        sa.Column("onboarding_batch", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_crawled_pages_onboarding_batch",
        "crawled_pages",
        ["onboarding_batch"],
    )
    # Backfill: existing onboarding pages get batch=1
    op.execute(
        "UPDATE crawled_pages SET onboarding_batch = 1 WHERE source = 'onboarding'"
    )


def downgrade() -> None:
    op.drop_index("ix_crawled_pages_onboarding_batch", table_name="crawled_pages")
    op.drop_column("crawled_pages", "onboarding_batch")
