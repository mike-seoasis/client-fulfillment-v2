"""add reddit_only column to projects

Revision ID: 0028
Revises: 0027
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0028'
down_revision: Union[str, None] = '0027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add reddit_only boolean column to projects table."""
    op.add_column(
        'projects',
        sa.Column(
            'reddit_only',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )


def downgrade() -> None:
    """Remove reddit_only column from projects table."""
    op.drop_column('projects', 'reddit_only')
