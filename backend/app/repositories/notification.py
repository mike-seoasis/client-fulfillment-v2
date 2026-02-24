"""NotificationRepository with CRUD operations.

Handles all database operations for notification entities:
- NotificationTemplate (email templates)
- WebhookConfig (webhook configurations)
- NotificationLog (delivery tracking)

Follows the layered architecture pattern: API -> Service -> Repository -> Database.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (notification_id, template_id, webhook_id) in all logs
- Log validation failures with field names and rejected values
- Log state transitions (status changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import db_logger, get_logger
from app.models.notification import (
    NotificationLog,
    NotificationStatus,
    NotificationTemplate,
    WebhookConfig,
)

logger = get_logger(__name__)

SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second


class NotificationTemplateRepository:
    """Repository for NotificationTemplate CRUD operations."""

    TABLE_NAME = "notification_templates"

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session
        logger.debug("NotificationTemplateRepository initialized")

    async def create(
        self,
        name: str,
        subject: str,
        body_html: str,
        body_text: str,
        variables: list[str] | None = None,
        is_active: bool = True,
    ) -> NotificationTemplate:
        """Create a new notification template."""
        start_time = time.monotonic()
        logger.debug(
            "Creating notification template",
            extra={"name": name, "is_active": is_active},
        )

        try:
            template = NotificationTemplate(
                name=name,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                variables=variables or [],
                is_active=is_active,
            )
            self.session.add(template)
            await self.session.flush()
            await self.session.refresh(template)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Notification template created",
                extra={
                    "template_id": template.id,
                    "name": name,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query="INSERT INTO notification_templates",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return template

        except IntegrityError as e:
            logger.error(
                "Failed to create notification template - integrity error",
                extra={
                    "name": name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Creating template name={name}",
            )
            raise

    async def get_by_id(self, template_id: str) -> NotificationTemplate | None:
        """Get a template by ID."""
        start_time = time.monotonic()
        logger.debug(
            "Fetching notification template by ID",
            extra={"template_id": template_id},
        )

        try:
            result = await self.session.execute(
                select(NotificationTemplate).where(NotificationTemplate.id == template_id)
            )
            template = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Template fetch completed",
                extra={
                    "template_id": template_id,
                    "found": template is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM notification_templates WHERE id={template_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return template

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch notification template",
                extra={
                    "template_id": template_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_name(self, name: str) -> NotificationTemplate | None:
        """Get a template by name."""
        start_time = time.monotonic()
        logger.debug(
            "Fetching notification template by name",
            extra={"name": name},
        )

        try:
            result = await self.session.execute(
                select(NotificationTemplate).where(NotificationTemplate.name == name)
            )
            template = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Template fetch by name completed",
                extra={
                    "name": name,
                    "found": template is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return template

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch notification template by name",
                extra={
                    "name": name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def list_all(
        self,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NotificationTemplate]:
        """List all templates with optional filters."""
        start_time = time.monotonic()
        logger.debug(
            "Listing notification templates",
            extra={"active_only": active_only, "limit": limit, "offset": offset},
        )

        try:
            query = select(NotificationTemplate)
            if active_only:
                query = query.where(NotificationTemplate.is_active == True)  # noqa: E712
            query = query.order_by(NotificationTemplate.name).limit(limit).offset(offset)

            result = await self.session.execute(query)
            templates = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Template list completed",
                extra={
                    "count": len(templates),
                    "active_only": active_only,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query="SELECT FROM notification_templates",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return templates

        except SQLAlchemyError as e:
            logger.error(
                "Failed to list notification templates",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update(
        self,
        template_id: str,
        name: str | None = None,
        subject: str | None = None,
        body_html: str | None = None,
        body_text: str | None = None,
        variables: list[str] | None = None,
        is_active: bool | None = None,
    ) -> NotificationTemplate | None:
        """Update a template."""
        start_time = time.monotonic()

        update_values: dict[str, Any] = {}
        if name is not None:
            update_values["name"] = name
        if subject is not None:
            update_values["subject"] = subject
        if body_html is not None:
            update_values["body_html"] = body_html
        if body_text is not None:
            update_values["body_text"] = body_text
        if variables is not None:
            update_values["variables"] = variables
        if is_active is not None:
            update_values["is_active"] = is_active

        if not update_values:
            return await self.get_by_id(template_id)

        logger.debug(
            "Updating notification template",
            extra={
                "template_id": template_id,
                "update_fields": list(update_values.keys()),
            },
        )

        try:
            await self.session.execute(
                update(NotificationTemplate)
                .where(NotificationTemplate.id == template_id)
                .values(**update_values)
            )
            await self.session.flush()

            template = await self.get_by_id(template_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Template updated",
                extra={
                    "template_id": template_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"UPDATE notification_templates WHERE id={template_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return template

        except IntegrityError as e:
            logger.error(
                "Failed to update notification template - integrity error",
                extra={
                    "template_id": template_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating template_id={template_id}",
            )
            raise

    async def delete(self, template_id: str) -> bool:
        """Delete a template."""
        start_time = time.monotonic()
        logger.debug(
            "Deleting notification template",
            extra={"template_id": template_id},
        )

        try:
            result = await self.session.execute(
                delete(NotificationTemplate).where(NotificationTemplate.id == template_id)
            )
            await self.session.flush()

            deleted = result.rowcount > 0

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Template delete completed",
                extra={
                    "template_id": template_id,
                    "deleted": deleted,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return deleted

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting template_id={template_id}",
            )
            raise

    async def count(self, active_only: bool = False) -> int:
        """Count templates."""
        try:
            query = select(func.count()).select_from(NotificationTemplate)
            if active_only:
                query = query.where(NotificationTemplate.is_active == True)  # noqa: E712

            result = await self.session.execute(query)
            return result.scalar_one()

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count notification templates",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
                exc_info=True,
            )
            raise


class WebhookConfigRepository:
    """Repository for WebhookConfig CRUD operations."""

    TABLE_NAME = "webhook_configs"

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session
        logger.debug("WebhookConfigRepository initialized")

    async def create(
        self,
        name: str,
        url: str,
        method: str = "POST",
        headers: dict[str, str] | None = None,
        payload_template: dict[str, Any] | None = None,
        events: list[str] | None = None,
        secret: str | None = None,
        is_active: bool = True,
        retry_count: int = 3,
        timeout_seconds: int = 30,
    ) -> WebhookConfig:
        """Create a new webhook configuration."""
        start_time = time.monotonic()
        logger.debug(
            "Creating webhook config",
            extra={"name": name, "url": url[:50], "is_active": is_active},
        )

        try:
            webhook = WebhookConfig(
                name=name,
                url=url,
                method=method,
                headers=headers or {},
                payload_template=payload_template or {},
                events=events or [],
                secret=secret,
                is_active=is_active,
                retry_count=retry_count,
                timeout_seconds=timeout_seconds,
            )
            self.session.add(webhook)
            await self.session.flush()
            await self.session.refresh(webhook)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Webhook config created",
                extra={
                    "webhook_id": webhook.id,
                    "name": name,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query="INSERT INTO webhook_configs",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return webhook

        except IntegrityError as e:
            logger.error(
                "Failed to create webhook config - integrity error",
                extra={
                    "name": name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Creating webhook name={name}",
            )
            raise

    async def get_by_id(self, webhook_id: str) -> WebhookConfig | None:
        """Get a webhook config by ID."""
        start_time = time.monotonic()
        logger.debug(
            "Fetching webhook config by ID",
            extra={"webhook_id": webhook_id},
        )

        try:
            result = await self.session.execute(
                select(WebhookConfig).where(WebhookConfig.id == webhook_id)
            )
            webhook = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Webhook fetch completed",
                extra={
                    "webhook_id": webhook_id,
                    "found": webhook is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return webhook

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch webhook config",
                extra={
                    "webhook_id": webhook_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_name(self, name: str) -> WebhookConfig | None:
        """Get a webhook config by name."""
        start_time = time.monotonic()
        logger.debug(
            "Fetching webhook config by name",
            extra={"name": name},
        )

        try:
            result = await self.session.execute(
                select(WebhookConfig).where(WebhookConfig.name == name)
            )
            webhook = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Webhook fetch by name completed",
                extra={
                    "name": name,
                    "found": webhook is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return webhook

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch webhook config by name",
                extra={
                    "name": name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_event(self, event: str, active_only: bool = True) -> list[WebhookConfig]:
        """Get all webhook configs subscribed to an event."""
        start_time = time.monotonic()
        logger.debug(
            "Fetching webhook configs by event",
            extra={"event": event, "active_only": active_only},
        )

        try:
            # Use JSONB containment operator to check if event is in events array
            query = select(WebhookConfig).where(
                WebhookConfig.events.contains([event])
            )
            if active_only:
                query = query.where(WebhookConfig.is_active == True)  # noqa: E712

            result = await self.session.execute(query)
            webhooks = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Webhook fetch by event completed",
                extra={
                    "event": event,
                    "count": len(webhooks),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return webhooks

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch webhook configs by event",
                extra={
                    "event": event,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def list_all(
        self,
        active_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WebhookConfig]:
        """List all webhook configs with optional filters."""
        start_time = time.monotonic()
        logger.debug(
            "Listing webhook configs",
            extra={"active_only": active_only, "limit": limit, "offset": offset},
        )

        try:
            query = select(WebhookConfig)
            if active_only:
                query = query.where(WebhookConfig.is_active == True)  # noqa: E712
            query = query.order_by(WebhookConfig.name).limit(limit).offset(offset)

            result = await self.session.execute(query)
            webhooks = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Webhook list completed",
                extra={
                    "count": len(webhooks),
                    "active_only": active_only,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return webhooks

        except SQLAlchemyError as e:
            logger.error(
                "Failed to list webhook configs",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update(
        self,
        webhook_id: str,
        name: str | None = None,
        url: str | None = None,
        method: str | None = None,
        headers: dict[str, str] | None = None,
        payload_template: dict[str, Any] | None = None,
        events: list[str] | None = None,
        secret: str | None = None,
        is_active: bool | None = None,
        retry_count: int | None = None,
        timeout_seconds: int | None = None,
    ) -> WebhookConfig | None:
        """Update a webhook config."""
        start_time = time.monotonic()

        update_values: dict[str, Any] = {}
        if name is not None:
            update_values["name"] = name
        if url is not None:
            update_values["url"] = url
        if method is not None:
            update_values["method"] = method
        if headers is not None:
            update_values["headers"] = headers
        if payload_template is not None:
            update_values["payload_template"] = payload_template
        if events is not None:
            update_values["events"] = events
        if secret is not None:
            update_values["secret"] = secret
        if is_active is not None:
            update_values["is_active"] = is_active
        if retry_count is not None:
            update_values["retry_count"] = retry_count
        if timeout_seconds is not None:
            update_values["timeout_seconds"] = timeout_seconds

        if not update_values:
            return await self.get_by_id(webhook_id)

        logger.debug(
            "Updating webhook config",
            extra={
                "webhook_id": webhook_id,
                "update_fields": list(update_values.keys()),
            },
        )

        try:
            await self.session.execute(
                update(WebhookConfig)
                .where(WebhookConfig.id == webhook_id)
                .values(**update_values)
            )
            await self.session.flush()

            webhook = await self.get_by_id(webhook_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Webhook config updated",
                extra={
                    "webhook_id": webhook_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return webhook

        except IntegrityError as e:
            logger.error(
                "Failed to update webhook config - integrity error",
                extra={
                    "webhook_id": webhook_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating webhook_id={webhook_id}",
            )
            raise

    async def delete(self, webhook_id: str) -> bool:
        """Delete a webhook config."""
        start_time = time.monotonic()
        logger.debug(
            "Deleting webhook config",
            extra={"webhook_id": webhook_id},
        )

        try:
            result = await self.session.execute(
                delete(WebhookConfig).where(WebhookConfig.id == webhook_id)
            )
            await self.session.flush()

            deleted = result.rowcount > 0

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Webhook delete completed",
                extra={
                    "webhook_id": webhook_id,
                    "deleted": deleted,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return deleted

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting webhook_id={webhook_id}",
            )
            raise

    async def count(self, active_only: bool = False) -> int:
        """Count webhook configs."""
        try:
            query = select(func.count()).select_from(WebhookConfig)
            if active_only:
                query = query.where(WebhookConfig.is_active == True)  # noqa: E712

            result = await self.session.execute(query)
            return result.scalar_one()

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count webhook configs",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
                exc_info=True,
            )
            raise


class NotificationLogRepository:
    """Repository for NotificationLog CRUD operations."""

    TABLE_NAME = "notification_logs"

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.session = session
        logger.debug("NotificationLogRepository initialized")

    async def create(
        self,
        channel: str,
        recipient: str,
        status: str = NotificationStatus.PENDING.value,
        project_id: str | None = None,
        template_id: str | None = None,
        webhook_config_id: str | None = None,
        subject: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> NotificationLog:
        """Create a new notification log entry."""
        start_time = time.monotonic()
        logger.debug(
            "Creating notification log",
            extra={
                "channel": channel,
                "recipient": recipient[:50] if recipient else None,
                "status": status,
                "project_id": project_id,
            },
        )

        try:
            log = NotificationLog(
                channel=channel,
                recipient=recipient,
                status=status,
                project_id=project_id,
                template_id=template_id,
                webhook_config_id=webhook_config_id,
                subject=subject,
                payload=payload or {},
            )
            self.session.add(log)
            await self.session.flush()
            await self.session.refresh(log)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Notification log created",
                extra={
                    "notification_id": log.id,
                    "channel": channel,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return log

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Creating notification log channel={channel}",
            )
            raise

    async def get_by_id(self, log_id: str) -> NotificationLog | None:
        """Get a notification log by ID."""
        start_time = time.monotonic()
        logger.debug(
            "Fetching notification log by ID",
            extra={"notification_id": log_id},
        )

        try:
            result = await self.session.execute(
                select(NotificationLog).where(NotificationLog.id == log_id)
            )
            log = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Notification log fetch completed",
                extra={
                    "notification_id": log_id,
                    "found": log is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return log

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch notification log",
                extra={
                    "notification_id": log_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update_status(
        self,
        log_id: str,
        status: str,
        response: dict[str, Any] | None = None,
        error_message: str | None = None,
        sent_at: datetime | None = None,
        delivered_at: datetime | None = None,
        retry_attempt: int | None = None,
    ) -> NotificationLog | None:
        """Update notification log status."""
        start_time = time.monotonic()

        # Get current log to track status transition
        current_log = await self.get_by_id(log_id)
        if current_log is None:
            return None

        old_status = current_log.status

        logger.debug(
            "Updating notification log status",
            extra={
                "notification_id": log_id,
                "old_status": old_status,
                "new_status": status,
            },
        )

        try:
            update_values: dict[str, Any] = {"status": status}
            if response is not None:
                update_values["response"] = response
            if error_message is not None:
                update_values["error_message"] = error_message
            if sent_at is not None:
                update_values["sent_at"] = sent_at
            if delivered_at is not None:
                update_values["delivered_at"] = delivered_at
            if retry_attempt is not None:
                update_values["retry_attempt"] = retry_attempt

            await self.session.execute(
                update(NotificationLog)
                .where(NotificationLog.id == log_id)
                .values(**update_values)
            )
            await self.session.flush()

            # Log status transition at INFO level
            if old_status != status:
                logger.info(
                    "Notification status transition",
                    extra={
                        "notification_id": log_id,
                        "channel": current_log.channel,
                        "from_status": old_status,
                        "to_status": status,
                        "project_id": current_log.project_id,
                    },
                )

            log = await self.get_by_id(log_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Notification log status updated",
                extra={
                    "notification_id": log_id,
                    "status": status,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return log

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating notification log_id={log_id}",
            )
            raise

    async def list_by_project(
        self,
        project_id: str,
        channel: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NotificationLog]:
        """List notification logs for a project."""
        start_time = time.monotonic()
        logger.debug(
            "Listing notification logs by project",
            extra={
                "project_id": project_id,
                "channel": channel,
                "status": status,
                "limit": limit,
                "offset": offset,
            },
        )

        try:
            query = select(NotificationLog).where(NotificationLog.project_id == project_id)
            if channel:
                query = query.where(NotificationLog.channel == channel)
            if status:
                query = query.where(NotificationLog.status == status)
            query = query.order_by(NotificationLog.created_at.desc()).limit(limit).offset(offset)

            result = await self.session.execute(query)
            logs = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Notification logs by project completed",
                extra={
                    "project_id": project_id,
                    "count": len(logs),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return logs

        except SQLAlchemyError as e:
            logger.error(
                "Failed to list notification logs by project",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def list_all(
        self,
        channel: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[NotificationLog]:
        """List all notification logs with optional filters."""
        start_time = time.monotonic()
        logger.debug(
            "Listing notification logs",
            extra={
                "channel": channel,
                "status": status,
                "limit": limit,
                "offset": offset,
            },
        )

        try:
            query = select(NotificationLog)
            if channel:
                query = query.where(NotificationLog.channel == channel)
            if status:
                query = query.where(NotificationLog.status == status)
            query = query.order_by(NotificationLog.created_at.desc()).limit(limit).offset(offset)

            result = await self.session.execute(query)
            logs = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Notification logs list completed",
                extra={
                    "count": len(logs),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return logs

        except SQLAlchemyError as e:
            logger.error(
                "Failed to list notification logs",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def count(
        self,
        project_id: str | None = None,
        channel: str | None = None,
        status: str | None = None,
    ) -> int:
        """Count notification logs with optional filters."""
        try:
            query = select(func.count()).select_from(NotificationLog)
            if project_id:
                query = query.where(NotificationLog.project_id == project_id)
            if channel:
                query = query.where(NotificationLog.channel == channel)
            if status:
                query = query.where(NotificationLog.status == status)

            result = await self.session.execute(query)
            return result.scalar_one()

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count notification logs",
                extra={"error_type": type(e).__name__, "error_message": str(e)},
                exc_info=True,
            )
            raise

    async def get_pending_retries(self, max_retries: int = 3) -> list[NotificationLog]:
        """Get failed notifications eligible for retry."""
        start_time = time.monotonic()
        logger.debug(
            "Fetching pending retries",
            extra={"max_retries": max_retries},
        )

        try:
            query = (
                select(NotificationLog)
                .where(NotificationLog.status == NotificationStatus.FAILED.value)
                .where(NotificationLog.retry_attempt < max_retries)
                .order_by(NotificationLog.created_at)
            )

            result = await self.session.execute(query)
            logs = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Pending retries fetch completed",
                extra={
                    "count": len(logs),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return logs

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch pending retries",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise
