"""Notification models for email templates, webhook configs, and notification logs.

The notification system supports:
- Email templates with variable substitution
- Webhook configurations for external integrations
- Notification logs for delivery tracking and audit

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, notification_id) in all logs
- Log validation failures with field names and rejected values
- Log state transitions (delivery status changes) at INFO level
- Add timing logs for operations >1 second
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NotificationChannel(str, Enum):
    """Notification delivery channels."""

    EMAIL = "email"
    WEBHOOK = "webhook"


class NotificationStatus(str, Enum):
    """Notification delivery status."""

    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class NotificationTemplate(Base):
    """Email template model for notification system.

    Attributes:
        id: UUID primary key
        name: Template name (unique identifier)
        subject: Email subject line (supports variable substitution)
        body_html: HTML body content (supports variable substitution)
        body_text: Plain text body content (supports variable substitution)
        variables: JSONB field listing expected template variables
        is_active: Whether template is currently active
        created_at: Timestamp when template was created
        updated_at: Timestamp when template was last updated

    Example variables structure:
        ["project_name", "client_name", "phase_status", "completion_date"]
    """

    __tablename__ = "notification_templates"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    subject: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    body_html: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    body_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    variables: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<NotificationTemplate(id={self.id!r}, name={self.name!r})>"


class WebhookConfig(Base):
    """Webhook configuration model for external integrations.

    Attributes:
        id: UUID primary key
        name: Configuration name (unique identifier)
        url: Webhook endpoint URL
        method: HTTP method (POST, PUT, PATCH)
        headers: JSONB field with custom headers
        payload_template: JSONB template for payload (supports variable substitution)
        events: JSONB list of events that trigger this webhook
        secret: Optional webhook secret for signature verification
        is_active: Whether webhook is currently active
        retry_count: Number of retry attempts on failure
        timeout_seconds: Request timeout in seconds
        created_at: Timestamp when config was created
        updated_at: Timestamp when config was last updated

    Example events structure:
        ["phase_completed", "project_created", "crawl_finished"]

    Example payload_template:
        {
            "event": "{{event_type}}",
            "project_id": "{{project_id}}",
            "project_name": "{{project_name}}",
            "timestamp": "{{timestamp}}"
        }
    """

    __tablename__ = "webhook_configs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="POST",
        server_default=text("'POST'"),
    )

    headers: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    payload_template: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    events: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    secret: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    retry_count: Mapped[int] = mapped_column(
        nullable=False,
        default=3,
        server_default=text("3"),
    )

    timeout_seconds: Mapped[int] = mapped_column(
        nullable=False,
        default=30,
        server_default=text("30"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<WebhookConfig(id={self.id!r}, name={self.name!r}, url={self.url[:50]!r})>"


class NotificationLog(Base):
    """Notification delivery log for tracking and audit.

    Attributes:
        id: UUID primary key
        project_id: Optional reference to the project (for project-related notifications)
        channel: Delivery channel (email, webhook)
        status: Delivery status
        recipient: Email address or webhook URL
        template_id: Reference to the template used (if email)
        webhook_config_id: Reference to the webhook config used (if webhook)
        subject: Email subject or webhook event name
        payload: JSONB with the actual payload sent
        response: JSONB with the delivery response/result
        error_message: Error details if delivery failed
        retry_attempt: Current retry attempt number
        sent_at: Timestamp when notification was sent
        delivered_at: Timestamp when notification was confirmed delivered
        created_at: Timestamp when log was created
    """

    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    project_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=NotificationStatus.PENDING.value,
        server_default=text(f"'{NotificationStatus.PENDING.value}'"),
        index=True,
    )

    recipient: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    template_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("notification_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    webhook_config_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("webhook_configs.id", ondelete="SET NULL"),
        nullable=True,
    )

    subject: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    response: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    retry_attempt: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    # Relationships
    template: Mapped["NotificationTemplate | None"] = relationship(
        "NotificationTemplate",
        foreign_keys=[template_id],
        lazy="selectin",
    )

    webhook_config: Mapped["WebhookConfig | None"] = relationship(
        "WebhookConfig",
        foreign_keys=[webhook_config_id],
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_notification_logs_created_at", "created_at"),
        Index("ix_notification_logs_channel_status", "channel", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog(id={self.id!r}, channel={self.channel!r}, "
            f"status={self.status!r})>"
        )
