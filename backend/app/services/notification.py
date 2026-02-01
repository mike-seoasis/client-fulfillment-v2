"""NotificationService for sending emails and webhook notifications.

Orchestrates notification delivery with:
- Template variable substitution
- Email and webhook sending via integration clients
- Delivery logging and tracking
- Event triggering for configured notifications

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, notification_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (delivery status) at INFO level
- Add timing logs for operations >1 second
"""

import re
import time
import traceback
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.email import EmailClient, get_email_client
from app.integrations.webhook import WebhookClient, get_webhook_client
from app.models.notification import NotificationChannel, NotificationStatus
from app.repositories.notification import (
    NotificationLogRepository,
    NotificationTemplateRepository,
    WebhookConfigRepository,
)
from app.schemas.notification import (
    SendNotificationResponse,
    TriggerEventResponse,
)

logger = get_logger(__name__)

SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second


class NotificationServiceError(Exception):
    """Base exception for NotificationService errors."""

    pass


class TemplateNotFoundError(NotificationServiceError):
    """Raised when a template is not found."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Template not found: {name}")


class WebhookConfigNotFoundError(NotificationServiceError):
    """Raised when a webhook config is not found."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Webhook config not found: {name}")


class TemplateRenderError(NotificationServiceError):
    """Raised when template rendering fails."""

    def __init__(self, template_name: str, missing_vars: list[str]):
        self.template_name = template_name
        self.missing_vars = missing_vars
        super().__init__(
            f"Template '{template_name}' missing variables: {', '.join(missing_vars)}"
        )


class NotificationService:
    """Service for notification delivery and management.

    Handles:
    - Email sending via templates
    - Webhook sending via configurations
    - Event triggering for configured notifications
    - Delivery logging and tracking
    """

    def __init__(
        self,
        session: AsyncSession,
        email_client: EmailClient | None = None,
        webhook_client: WebhookClient | None = None,
    ) -> None:
        """Initialize service with database session and clients.

        Args:
            session: Async SQLAlchemy session
            email_client: Optional email client (defaults to global)
            webhook_client: Optional webhook client (defaults to global)
        """
        self.session = session
        self.template_repo = NotificationTemplateRepository(session)
        self.webhook_repo = WebhookConfigRepository(session)
        self.log_repo = NotificationLogRepository(session)
        self._email_client = email_client or get_email_client()
        self._webhook_client = webhook_client or get_webhook_client()
        logger.debug("NotificationService initialized")

    def _substitute_variables(
        self,
        template_str: str,
        variables: dict[str, Any],
    ) -> str:
        """Substitute {{variable}} placeholders in template string.

        Args:
            template_str: String with {{variable}} placeholders
            variables: Dict of variable name -> value

        Returns:
            String with substituted values
        """
        result = template_str
        # Match {{variable_name}} pattern
        pattern = re.compile(r"\{\{(\w+)\}\}")

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            if var_name in variables:
                value = variables[var_name]
                return str(value) if value is not None else ""
            # Leave unmatched variables as-is for debugging
            return match.group(0)

        result = pattern.sub(replace_var, result)
        return result

    def _substitute_dict_variables(
        self,
        template_dict: dict[str, Any],
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Recursively substitute variables in a dict template.

        Args:
            template_dict: Dict with {{variable}} placeholders in values
            variables: Dict of variable name -> value

        Returns:
            Dict with substituted values
        """
        result: dict[str, Any] = {}
        for key, value in template_dict.items():
            if isinstance(value, str):
                result[key] = self._substitute_variables(value, variables)
            elif isinstance(value, dict):
                result[key] = self._substitute_dict_variables(value, variables)
            elif isinstance(value, list):
                result[key] = [
                    self._substitute_variables(item, variables)
                    if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    async def send_email(
        self,
        template_name: str,
        recipient: str,
        variables: dict[str, Any],
        project_id: str | None = None,
    ) -> SendNotificationResponse:
        """Send an email using a template.

        Args:
            template_name: Name of the template to use
            recipient: Recipient email address
            variables: Template variable values
            project_id: Optional project ID for logging

        Returns:
            SendNotificationResponse with delivery status

        Raises:
            TemplateNotFoundError: If template doesn't exist
        """
        start_time = time.monotonic()
        logger.debug(
            "Sending email",
            extra={
                "template_name": template_name,
                "recipient": recipient[:50],
                "project_id": project_id,
                "variable_count": len(variables),
            },
        )

        try:
            # Get template
            template = await self.template_repo.get_by_name(template_name)
            if template is None:
                logger.warning(
                    "Email template not found",
                    extra={"template_name": template_name},
                )
                raise TemplateNotFoundError(template_name)

            if not template.is_active:
                logger.warning(
                    "Email template is inactive",
                    extra={"template_name": template_name, "template_id": template.id},
                )
                raise TemplateNotFoundError(f"{template_name} (inactive)")

            # Render template
            subject = self._substitute_variables(template.subject, variables)
            body_html = self._substitute_variables(template.body_html, variables)
            body_text = self._substitute_variables(template.body_text, variables)

            # Create notification log
            log = await self.log_repo.create(
                channel=NotificationChannel.EMAIL.value,
                recipient=recipient,
                status=NotificationStatus.SENDING.value,
                project_id=project_id,
                template_id=template.id,
                subject=subject,
                payload={"variables": variables},
            )

            # Send email
            result = await self._email_client.send(
                recipient=recipient,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )

            # Update log with result
            if result.success:
                await self.log_repo.update_status(
                    log_id=log.id,
                    status=NotificationStatus.SENT.value,
                    response={"message_id": result.message_id},
                    sent_at=datetime.now(UTC),
                )
                logger.info(
                    "Email sent successfully",
                    extra={
                        "notification_id": log.id,
                        "template_name": template_name,
                        "recipient": recipient[:50],
                        "project_id": project_id,
                    },
                )
            else:
                await self.log_repo.update_status(
                    log_id=log.id,
                    status=NotificationStatus.FAILED.value,
                    error_message=result.error,
                    retry_attempt=result.retry_attempt,
                )
                logger.warning(
                    "Email send failed",
                    extra={
                        "notification_id": log.id,
                        "template_name": template_name,
                        "recipient": recipient[:50],
                        "error": result.error,
                        "project_id": project_id,
                    },
                )

            duration_ms = (time.monotonic() - start_time) * 1000
            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow email send operation",
                    extra={
                        "notification_id": log.id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return SendNotificationResponse(
                success=result.success,
                notification_id=log.id,
                channel=NotificationChannel.EMAIL.value,
                status=NotificationStatus.SENT.value if result.success else NotificationStatus.FAILED.value,
                message=result.error if not result.success else None,
            )

        except NotificationServiceError:
            raise
        except Exception as e:
            logger.error(
                "Email send error",
                extra={
                    "template_name": template_name,
                    "recipient": recipient[:50],
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": traceback.format_exc(),
                    "project_id": project_id,
                },
            )
            raise

    async def send_webhook(
        self,
        webhook_name: str,
        event: str,
        variables: dict[str, Any],
        project_id: str | None = None,
    ) -> SendNotificationResponse:
        """Send a webhook notification.

        Args:
            webhook_name: Name of the webhook config to use
            event: Event type being triggered
            variables: Payload variable values
            project_id: Optional project ID for logging

        Returns:
            SendNotificationResponse with delivery status

        Raises:
            WebhookConfigNotFoundError: If webhook config doesn't exist
        """
        start_time = time.monotonic()
        logger.debug(
            "Sending webhook",
            extra={
                "webhook_name": webhook_name,
                "event": event,
                "project_id": project_id,
                "variable_count": len(variables),
            },
        )

        try:
            # Get webhook config
            webhook = await self.webhook_repo.get_by_name(webhook_name)
            if webhook is None:
                logger.warning(
                    "Webhook config not found",
                    extra={"webhook_name": webhook_name},
                )
                raise WebhookConfigNotFoundError(webhook_name)

            if not webhook.is_active:
                logger.warning(
                    "Webhook config is inactive",
                    extra={"webhook_name": webhook_name, "webhook_id": webhook.id},
                )
                raise WebhookConfigNotFoundError(f"{webhook_name} (inactive)")

            # Build payload with variables
            # Add standard event metadata
            payload_vars = {
                **variables,
                "event_type": event,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            if project_id:
                payload_vars["project_id"] = project_id

            # Render payload template
            payload = self._substitute_dict_variables(
                webhook.payload_template,
                payload_vars,
            )

            # If payload template is empty, use variables directly
            if not payload:
                payload = payload_vars

            # Create notification log
            log = await self.log_repo.create(
                channel=NotificationChannel.WEBHOOK.value,
                recipient=webhook.url,
                status=NotificationStatus.SENDING.value,
                project_id=project_id,
                webhook_config_id=webhook.id,
                subject=event,
                payload=payload,
            )

            # Send webhook
            result = await self._webhook_client.send(
                url=webhook.url,
                payload=payload,
                method=webhook.method,
                headers=webhook.headers or None,
                secret=webhook.secret,
                timeout=float(webhook.timeout_seconds),
                max_retries=webhook.retry_count,
            )

            # Update log with result
            if result.success:
                await self.log_repo.update_status(
                    log_id=log.id,
                    status=NotificationStatus.DELIVERED.value,
                    response={
                        "status_code": result.status_code,
                        "body": result.response_body,
                    },
                    sent_at=datetime.now(UTC),
                    delivered_at=datetime.now(UTC),
                )
                logger.info(
                    "Webhook sent successfully",
                    extra={
                        "notification_id": log.id,
                        "webhook_name": webhook_name,
                        "event": event,
                        "url": webhook.url[:50],
                        "status_code": result.status_code,
                        "project_id": project_id,
                    },
                )
            else:
                await self.log_repo.update_status(
                    log_id=log.id,
                    status=NotificationStatus.FAILED.value,
                    response={
                        "status_code": result.status_code,
                        "body": result.response_body,
                    },
                    error_message=result.error,
                    retry_attempt=result.retry_attempt,
                )
                logger.warning(
                    "Webhook send failed",
                    extra={
                        "notification_id": log.id,
                        "webhook_name": webhook_name,
                        "event": event,
                        "url": webhook.url[:50],
                        "error": result.error,
                        "status_code": result.status_code,
                        "project_id": project_id,
                    },
                )

            duration_ms = (time.monotonic() - start_time) * 1000
            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow webhook send operation",
                    extra={
                        "notification_id": log.id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return SendNotificationResponse(
                success=result.success,
                notification_id=log.id,
                channel=NotificationChannel.WEBHOOK.value,
                status=NotificationStatus.DELIVERED.value if result.success else NotificationStatus.FAILED.value,
                message=result.error if not result.success else None,
            )

        except NotificationServiceError:
            raise
        except Exception as e:
            logger.error(
                "Webhook send error",
                extra={
                    "webhook_name": webhook_name,
                    "event": event,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": traceback.format_exc(),
                    "project_id": project_id,
                },
            )
            raise

    async def trigger_event(
        self,
        event: str,
        variables: dict[str, Any],
        project_id: str | None = None,
    ) -> TriggerEventResponse:
        """Trigger all configured notifications for an event.

        Sends webhooks to all active webhook configs subscribed to the event.

        Args:
            event: Event type to trigger
            variables: Event data for variable substitution
            project_id: Optional project ID for logging

        Returns:
            TriggerEventResponse with results for all notifications
        """
        start_time = time.monotonic()
        logger.debug(
            "Triggering event",
            extra={
                "event": event,
                "project_id": project_id,
                "variable_count": len(variables),
            },
        )

        results: list[SendNotificationResponse] = []

        try:
            # Get all webhook configs subscribed to this event
            webhooks = await self.webhook_repo.get_by_event(event, active_only=True)

            logger.debug(
                "Found webhooks for event",
                extra={
                    "event": event,
                    "webhook_count": len(webhooks),
                    "project_id": project_id,
                },
            )

            # Send to each webhook
            for webhook in webhooks:
                try:
                    result = await self.send_webhook(
                        webhook_name=webhook.name,
                        event=event,
                        variables=variables,
                        project_id=project_id,
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(
                        "Failed to send event webhook",
                        extra={
                            "event": event,
                            "webhook_name": webhook.name,
                            "error": str(e),
                            "project_id": project_id,
                        },
                    )
                    # Create a failure result for tracking
                    results.append(
                        SendNotificationResponse(
                            success=False,
                            notification_id="",
                            channel=NotificationChannel.WEBHOOK.value,
                            status=NotificationStatus.FAILED.value,
                            message=str(e),
                        )
                    )

            duration_ms = (time.monotonic() - start_time) * 1000
            success_count = sum(1 for r in results if r.success)

            logger.info(
                "Event triggered",
                extra={
                    "event": event,
                    "total_notifications": len(results),
                    "success_count": success_count,
                    "failure_count": len(results) - success_count,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow event trigger operation",
                    extra={
                        "event": event,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return TriggerEventResponse(
                event=event,
                notifications_sent=len(results),
                results=results,
            )

        except Exception as e:
            logger.error(
                "Event trigger error",
                extra={
                    "event": event,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": traceback.format_exc(),
                    "project_id": project_id,
                },
            )
            raise


# Service factory for dependency injection
_service: NotificationService | None = None


def get_notification_service(session: AsyncSession) -> NotificationService:
    """Get a NotificationService instance.

    Creates a new service with the provided session.
    Use this as a FastAPI dependency.

    Args:
        session: AsyncSession for database operations

    Returns:
        NotificationService instance
    """
    return NotificationService(session)
