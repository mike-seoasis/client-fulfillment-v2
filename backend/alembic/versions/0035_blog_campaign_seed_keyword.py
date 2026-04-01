"""Make blog_campaigns.cluster_id nullable and add seed_keyword column.

Allows blog campaigns to be created from a user-provided seed keyword
instead of requiring an existing keyword cluster.

Revision ID: 0035
Revises: 0034
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make cluster_id nullable (was NOT NULL + UNIQUE)
    op.alter_column(
        "blog_campaigns",
        "cluster_id",
        existing_type=sa.UUID(as_uuid=False),
        nullable=True,
    )

    # Add seed_keyword column for standalone campaigns
    op.add_column(
        "blog_campaigns",
        sa.Column("seed_keyword", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("blog_campaigns", "seed_keyword")

    op.alter_column(
        "blog_campaigns",
        "cluster_id",
        existing_type=sa.UUID(as_uuid=False),
        nullable=False,
    )
