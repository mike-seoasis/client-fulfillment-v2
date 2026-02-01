"""Create notification system tables.

Creates tables for:
- notification_templates: Email templates with variable substitution
- webhook_configs: Webhook endpoint configurations
- notification_logs: Delivery tracking and audit logs

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create notification system tables."""
    # Create notification_templates table
    op.create_table(
        "notification_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "variables",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
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
        sa.UniqueConstraint("name", name="uq_notification_templates_name"),
    )
    op.create_index(
        op.f("ix_notification_templates_name"),
        "notification_templates",
        ["name"],
        unique=True,
    )

    # Create webhook_configs table
    op.create_table(
        "webhook_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "method",
            sa.String(length=10),
            server_default=sa.text("'POST'"),
            nullable=False,
        ),
        sa.Column(
            "headers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "payload_template",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "events",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("secret", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "retry_count",
            sa.Integer(),
            server_default=sa.text("3"),
            nullable=False,
        ),
        sa.Column(
            "timeout_seconds",
            sa.Integer(),
            server_default=sa.text("30"),
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
        sa.UniqueConstraint("name", name="uq_webhook_configs_name"),
    )
    op.create_index(
        op.f("ix_webhook_configs_name"),
        "webhook_configs",
        ["name"],
        unique=True,
    )

    # Create notification_logs table
    op.create_table(
        "notification_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(length=500), nullable=False),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "webhook_config_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "retry_attempt",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
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
            name="fk_notification_logs_project_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["notification_templates.id"],
            name="fk_notification_logs_template_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["webhook_config_id"],
            ["webhook_configs.id"],
            name="fk_notification_logs_webhook_config_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        op.f("ix_notification_logs_project_id"),
        "notification_logs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_logs_channel"),
        "notification_logs",
        ["channel"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_logs_status"),
        "notification_logs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_logs_created_at"),
        "notification_logs",
        ["created_at"],
        unique=False,
    )
    # Composite index for efficient filtering by channel and status
    op.create_index(
        "ix_notification_logs_channel_status",
        "notification_logs",
        ["channel", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop notification system tables."""
    # Drop notification_logs table first (has foreign keys)
    op.drop_index("ix_notification_logs_channel_status", table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_created_at"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_status"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_channel"), table_name="notification_logs")
    op.drop_index(op.f("ix_notification_logs_project_id"), table_name="notification_logs")
    op.drop_table("notification_logs")

    # Drop webhook_configs table
    op.drop_index(op.f("ix_webhook_configs_name"), table_name="webhook_configs")
    op.drop_table("webhook_configs")

    # Drop notification_templates table
    op.drop_index(op.f("ix_notification_templates_name"), table_name="notification_templates")
    op.drop_table("notification_templates")
