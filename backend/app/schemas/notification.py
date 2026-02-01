"""Pydantic schemas for notification system.

Defines request/response models for:
- Email templates (CRUD operations)
- Webhook configurations (CRUD operations)
- Notification logs (tracking and audit)
- Send notification requests
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Valid notification channels
VALID_CHANNELS = {"email", "webhook"}

# Valid notification statuses
VALID_STATUSES = {"pending", "sending", "sent", "delivered", "failed", "bounced"}

# Valid HTTP methods for webhooks
VALID_HTTP_METHODS = {"POST", "PUT", "PATCH"}

# Valid webhook events
VALID_WEBHOOK_EVENTS = {
    "project_created",
    "project_updated",
    "project_completed",
    "phase_started",
    "phase_completed",
    "phase_failed",
    "crawl_started",
    "crawl_completed",
    "crawl_failed",
    "content_generated",
    "brand_config_updated",
}


# -----------------------------------------------------------------------------
# Email Template Schemas
# -----------------------------------------------------------------------------


class NotificationTemplateBase(BaseModel):
    """Base schema for notification templates."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique template name identifier",
    )
    subject: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Email subject line (supports {{variable}} substitution)",
    )
    body_html: str = Field(
        ...,
        min_length=1,
        description="HTML body content (supports {{variable}} substitution)",
    )
    body_text: str = Field(
        ...,
        min_length=1,
        description="Plain text body content (supports {{variable}} substitution)",
    )
    variables: list[str] = Field(
        default_factory=list,
        description="List of expected template variables",
    )
    is_active: bool = Field(
        default=True,
        description="Whether template is active",
    )


class NotificationTemplateCreate(NotificationTemplateBase):
    """Schema for creating a notification template."""

    pass


class NotificationTemplateUpdate(BaseModel):
    """Schema for updating a notification template."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Unique template name identifier",
    )
    subject: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description="Email subject line",
    )
    body_html: str | None = Field(
        default=None,
        min_length=1,
        description="HTML body content",
    )
    body_text: str | None = Field(
        default=None,
        min_length=1,
        description="Plain text body content",
    )
    variables: list[str] | None = Field(
        default=None,
        description="List of expected template variables",
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether template is active",
    )


class NotificationTemplateResponse(NotificationTemplateBase):
    """Schema for notification template response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Template UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# -----------------------------------------------------------------------------
# Webhook Configuration Schemas
# -----------------------------------------------------------------------------


class WebhookConfigBase(BaseModel):
    """Base schema for webhook configurations."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique webhook config name",
    )
    url: str = Field(
        ...,
        max_length=2048,
        description="Webhook endpoint URL",
    )
    method: str = Field(
        default="POST",
        description="HTTP method (POST, PUT, PATCH)",
    )
    headers: dict[str, str] = Field(
        default_factory=dict,
        description="Custom HTTP headers",
    )
    payload_template: dict[str, Any] = Field(
        default_factory=dict,
        description="Payload template with {{variable}} substitution",
    )
    events: list[str] = Field(
        default_factory=list,
        description="Events that trigger this webhook",
    )
    secret: str | None = Field(
        default=None,
        max_length=255,
        description="Webhook secret for signature verification",
    )
    is_active: bool = Field(
        default=True,
        description="Whether webhook is active",
    )
    retry_count: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retry attempts",
    )
    timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Request timeout in seconds",
    )

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate HTTP method."""
        v = v.upper()
        if v not in VALID_HTTP_METHODS:
            raise ValueError(f"Method must be one of: {', '.join(VALID_HTTP_METHODS)}")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        """Validate webhook events."""
        invalid = set(v) - VALID_WEBHOOK_EVENTS
        if invalid:
            raise ValueError(
                f"Invalid events: {invalid}. Valid events: {VALID_WEBHOOK_EVENTS}"
            )
        return v


class WebhookConfigCreate(WebhookConfigBase):
    """Schema for creating a webhook configuration."""

    pass


class WebhookConfigUpdate(BaseModel):
    """Schema for updating a webhook configuration."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Unique webhook config name",
    )
    url: str | None = Field(
        default=None,
        max_length=2048,
        description="Webhook endpoint URL",
    )
    method: str | None = Field(
        default=None,
        description="HTTP method (POST, PUT, PATCH)",
    )
    headers: dict[str, str] | None = Field(
        default=None,
        description="Custom HTTP headers",
    )
    payload_template: dict[str, Any] | None = Field(
        default=None,
        description="Payload template with {{variable}} substitution",
    )
    events: list[str] | None = Field(
        default=None,
        description="Events that trigger this webhook",
    )
    secret: str | None = Field(
        default=None,
        max_length=255,
        description="Webhook secret for signature verification",
    )
    is_active: bool | None = Field(
        default=None,
        description="Whether webhook is active",
    )
    retry_count: int | None = Field(
        default=None,
        ge=0,
        le=10,
        description="Number of retry attempts",
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=5,
        le=300,
        description="Request timeout in seconds",
    )

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str | None) -> str | None:
        """Validate HTTP method."""
        if v is None:
            return v
        v = v.upper()
        if v not in VALID_HTTP_METHODS:
            raise ValueError(f"Method must be one of: {', '.join(VALID_HTTP_METHODS)}")
        return v

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        """Validate webhook events."""
        if v is None:
            return v
        invalid = set(v) - VALID_WEBHOOK_EVENTS
        if invalid:
            raise ValueError(
                f"Invalid events: {invalid}. Valid events: {VALID_WEBHOOK_EVENTS}"
            )
        return v


class WebhookConfigResponse(BaseModel):
    """Schema for webhook configuration response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Webhook config UUID")
    name: str = Field(..., description="Unique webhook config name")
    url: str = Field(..., description="Webhook endpoint URL")
    method: str = Field(..., description="HTTP method")
    headers: dict[str, str] = Field(..., description="Custom HTTP headers")
    payload_template: dict[str, Any] = Field(..., description="Payload template")
    events: list[str] = Field(..., description="Triggering events")
    is_active: bool = Field(..., description="Whether webhook is active")
    retry_count: int = Field(..., description="Number of retry attempts")
    timeout_seconds: int = Field(..., description="Request timeout")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    # Note: secret is intentionally excluded from response


# -----------------------------------------------------------------------------
# Notification Log Schemas
# -----------------------------------------------------------------------------


class NotificationLogResponse(BaseModel):
    """Schema for notification log response."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Log entry UUID")
    project_id: str | None = Field(None, description="Related project UUID")
    channel: str = Field(..., description="Delivery channel (email/webhook)")
    status: str = Field(..., description="Delivery status")
    recipient: str = Field(..., description="Email address or webhook URL")
    template_id: str | None = Field(None, description="Template UUID if email")
    webhook_config_id: str | None = Field(None, description="Webhook config UUID")
    subject: str | None = Field(None, description="Email subject or event name")
    payload: dict[str, Any] = Field(..., description="Sent payload")
    response: dict[str, Any] | None = Field(None, description="Delivery response")
    error_message: str | None = Field(None, description="Error details if failed")
    retry_attempt: int = Field(..., description="Current retry attempt")
    sent_at: datetime | None = Field(None, description="Send timestamp")
    delivered_at: datetime | None = Field(None, description="Delivery timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")


class NotificationLogListResponse(BaseModel):
    """Schema for paginated notification log list."""

    items: list[NotificationLogResponse] = Field(..., description="Log entries")
    total: int = Field(..., description="Total count")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


# -----------------------------------------------------------------------------
# Send Notification Requests
# -----------------------------------------------------------------------------


class SendEmailRequest(BaseModel):
    """Schema for sending an email notification."""

    template_name: str = Field(
        ...,
        min_length=1,
        description="Template name to use",
    )
    recipient: str = Field(
        ...,
        min_length=1,
        description="Recipient email address",
    )
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Template variable values",
    )
    project_id: str | None = Field(
        default=None,
        description="Related project UUID",
    )


class SendWebhookRequest(BaseModel):
    """Schema for sending a webhook notification."""

    webhook_name: str = Field(
        ...,
        min_length=1,
        description="Webhook config name to use",
    )
    event: str = Field(
        ...,
        min_length=1,
        description="Event type being triggered",
    )
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Payload variable values",
    )
    project_id: str | None = Field(
        default=None,
        description="Related project UUID",
    )

    @field_validator("event")
    @classmethod
    def validate_event(cls, v: str) -> str:
        """Validate webhook event."""
        if v not in VALID_WEBHOOK_EVENTS:
            raise ValueError(
                f"Invalid event: {v}. Valid events: {VALID_WEBHOOK_EVENTS}"
            )
        return v


class SendNotificationResponse(BaseModel):
    """Schema for send notification response."""

    success: bool = Field(..., description="Whether send was initiated successfully")
    notification_id: str = Field(..., description="Notification log UUID")
    channel: str = Field(..., description="Delivery channel")
    status: str = Field(..., description="Current delivery status")
    message: str | None = Field(None, description="Additional message")


class TriggerEventRequest(BaseModel):
    """Schema for triggering a notification event.

    This triggers all configured notifications (emails and webhooks)
    for a specific event type.
    """

    event: str = Field(
        ...,
        min_length=1,
        description="Event type to trigger",
    )
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Event data for variable substitution",
    )
    project_id: str | None = Field(
        default=None,
        description="Related project UUID",
    )

    @field_validator("event")
    @classmethod
    def validate_event(cls, v: str) -> str:
        """Validate event type."""
        if v not in VALID_WEBHOOK_EVENTS:
            raise ValueError(
                f"Invalid event: {v}. Valid events: {VALID_WEBHOOK_EVENTS}"
            )
        return v


class TriggerEventResponse(BaseModel):
    """Schema for trigger event response."""

    event: str = Field(..., description="Triggered event type")
    notifications_sent: int = Field(..., description="Number of notifications sent")
    results: list[SendNotificationResponse] = Field(
        ..., description="Individual notification results"
    )
