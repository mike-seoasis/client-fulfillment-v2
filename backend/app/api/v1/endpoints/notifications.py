"""Notification API endpoints for templates, webhooks, and delivery.

Provides REST endpoints for:
- Email template CRUD
- Webhook configuration CRUD
- Notification sending (email, webhook)
- Event triggering
- Notification log retrieval

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, notification_id) in all logs
- Log validation failures with field names and rejected values
- Log state transitions at INFO level
- Add timing logs for operations >1 second
"""

import time
import traceback
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.repositories.notification import (
    NotificationLogRepository,
    NotificationTemplateRepository,
    WebhookConfigRepository,
)
from app.schemas.notification import (
    NotificationLogListResponse,
    NotificationLogResponse,
    NotificationTemplateCreate,
    NotificationTemplateResponse,
    NotificationTemplateUpdate,
    SendEmailRequest,
    SendNotificationResponse,
    SendWebhookRequest,
    TriggerEventRequest,
    TriggerEventResponse,
    WebhookConfigCreate,
    WebhookConfigResponse,
    WebhookConfigUpdate,
)
from app.services.notification import (
    NotificationService,
    TemplateNotFoundError,
    WebhookConfigNotFoundError,
    get_notification_service,
)

logger = get_logger(__name__)

router = APIRouter()

SLOW_OPERATION_THRESHOLD_MS = 1000


# Dependency for getting notification service
async def get_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationService:
    """Get notification service instance."""
    return get_notification_service(session)


# -----------------------------------------------------------------------------
# Email Template Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/templates",
    response_model=NotificationTemplateResponse,
    status_code=201,
    summary="Create email template",
    description="Create a new email template for notifications.",
)
async def create_template(
    data: NotificationTemplateCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationTemplateResponse:
    """Create a new email template."""
    start_time = time.monotonic()
    logger.debug(
        "Creating notification template",
        extra={"name": data.name},
    )

    try:
        repo = NotificationTemplateRepository(session)
        template = await repo.create(
            name=data.name,
            subject=data.subject,
            body_html=data.body_html,
            body_text=data.body_text,
            variables=data.variables,
            is_active=data.is_active,
        )
        await session.commit()

        duration_ms = (time.monotonic() - start_time) * 1000
        logger.debug(
            "Template created",
            extra={
                "template_id": template.id,
                "name": template.name,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return NotificationTemplateResponse.model_validate(template)

    except IntegrityError:
        await session.rollback()
        logger.warning(
            "Template name already exists",
            extra={"name": data.name},
        )
        raise HTTPException(
            status_code=409,
            detail=f"Template with name '{data.name}' already exists",
        )
    except Exception as e:
        await session.rollback()
        logger.error(
            "Failed to create template",
            extra={
                "name": data.name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": traceback.format_exc(),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to create template")


@router.get(
    "/templates",
    response_model=list[NotificationTemplateResponse],
    summary="List email templates",
    description="List all email templates with optional filtering.",
)
async def list_templates(
    session: Annotated[AsyncSession, Depends(get_session)],
    active_only: bool = Query(False, description="Only return active templates"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum templates to return"),
    offset: int = Query(0, ge=0, description="Number of templates to skip"),
) -> list[NotificationTemplateResponse]:
    """List all email templates."""
    logger.debug(
        "Listing templates",
        extra={"active_only": active_only, "limit": limit, "offset": offset},
    )

    repo = NotificationTemplateRepository(session)
    templates = await repo.list_all(
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    return [NotificationTemplateResponse.model_validate(t) for t in templates]


@router.get(
    "/templates/{template_id}",
    response_model=NotificationTemplateResponse,
    summary="Get email template",
    description="Get an email template by ID.",
)
async def get_template(
    template_id: Annotated[str, Path(description="Template UUID")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationTemplateResponse:
    """Get an email template by ID."""
    logger.debug("Getting template", extra={"template_id": template_id})

    repo = NotificationTemplateRepository(session)
    template = await repo.get_by_id(template_id)

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    return NotificationTemplateResponse.model_validate(template)


@router.patch(
    "/templates/{template_id}",
    response_model=NotificationTemplateResponse,
    summary="Update email template",
    description="Update an email template.",
)
async def update_template(
    template_id: Annotated[str, Path(description="Template UUID")],
    data: NotificationTemplateUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationTemplateResponse:
    """Update an email template."""
    logger.debug(
        "Updating template",
        extra={
            "template_id": template_id,
            "update_fields": [k for k, v in data.model_dump().items() if v is not None],
        },
    )

    try:
        repo = NotificationTemplateRepository(session)
        template = await repo.update(
            template_id=template_id,
            name=data.name,
            subject=data.subject,
            body_html=data.body_html,
            body_text=data.body_text,
            variables=data.variables,
            is_active=data.is_active,
        )
        await session.commit()

        if template is None:
            raise HTTPException(status_code=404, detail="Template not found")

        return NotificationTemplateResponse.model_validate(template)

    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Template with name '{data.name}' already exists",
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            "Failed to update template",
            extra={
                "template_id": template_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to update template")


@router.delete(
    "/templates/{template_id}",
    status_code=204,
    summary="Delete email template",
    description="Delete an email template.",
)
async def delete_template(
    template_id: Annotated[str, Path(description="Template UUID")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete an email template."""
    logger.debug("Deleting template", extra={"template_id": template_id})

    repo = NotificationTemplateRepository(session)
    deleted = await repo.delete(template_id)
    await session.commit()

    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")


# -----------------------------------------------------------------------------
# Webhook Configuration Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/webhooks",
    response_model=WebhookConfigResponse,
    status_code=201,
    summary="Create webhook configuration",
    description="Create a new webhook configuration.",
)
async def create_webhook(
    data: WebhookConfigCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WebhookConfigResponse:
    """Create a new webhook configuration."""
    start_time = time.monotonic()
    logger.debug(
        "Creating webhook config",
        extra={"name": data.name, "url": data.url[:50]},
    )

    try:
        repo = WebhookConfigRepository(session)
        webhook = await repo.create(
            name=data.name,
            url=data.url,
            method=data.method,
            headers=data.headers,
            payload_template=data.payload_template,
            events=data.events,
            secret=data.secret,
            is_active=data.is_active,
            retry_count=data.retry_count,
            timeout_seconds=data.timeout_seconds,
        )
        await session.commit()

        duration_ms = (time.monotonic() - start_time) * 1000
        logger.debug(
            "Webhook config created",
            extra={
                "webhook_id": webhook.id,
                "name": webhook.name,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return WebhookConfigResponse.model_validate(webhook)

    except IntegrityError:
        await session.rollback()
        logger.warning(
            "Webhook name already exists",
            extra={"name": data.name},
        )
        raise HTTPException(
            status_code=409,
            detail=f"Webhook with name '{data.name}' already exists",
        )
    except Exception as e:
        await session.rollback()
        logger.error(
            "Failed to create webhook",
            extra={
                "name": data.name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": traceback.format_exc(),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to create webhook")


@router.get(
    "/webhooks",
    response_model=list[WebhookConfigResponse],
    summary="List webhook configurations",
    description="List all webhook configurations with optional filtering.",
)
async def list_webhooks(
    session: Annotated[AsyncSession, Depends(get_session)],
    active_only: bool = Query(False, description="Only return active webhooks"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum webhooks to return"),
    offset: int = Query(0, ge=0, description="Number of webhooks to skip"),
) -> list[WebhookConfigResponse]:
    """List all webhook configurations."""
    logger.debug(
        "Listing webhooks",
        extra={"active_only": active_only, "limit": limit, "offset": offset},
    )

    repo = WebhookConfigRepository(session)
    webhooks = await repo.list_all(
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    return [WebhookConfigResponse.model_validate(w) for w in webhooks]


@router.get(
    "/webhooks/{webhook_id}",
    response_model=WebhookConfigResponse,
    summary="Get webhook configuration",
    description="Get a webhook configuration by ID.",
)
async def get_webhook(
    webhook_id: Annotated[str, Path(description="Webhook UUID")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WebhookConfigResponse:
    """Get a webhook configuration by ID."""
    logger.debug("Getting webhook", extra={"webhook_id": webhook_id})

    repo = WebhookConfigRepository(session)
    webhook = await repo.get_by_id(webhook_id)

    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookConfigResponse.model_validate(webhook)


@router.patch(
    "/webhooks/{webhook_id}",
    response_model=WebhookConfigResponse,
    summary="Update webhook configuration",
    description="Update a webhook configuration.",
)
async def update_webhook(
    webhook_id: Annotated[str, Path(description="Webhook UUID")],
    data: WebhookConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WebhookConfigResponse:
    """Update a webhook configuration."""
    logger.debug(
        "Updating webhook",
        extra={
            "webhook_id": webhook_id,
            "update_fields": [k for k, v in data.model_dump().items() if v is not None],
        },
    )

    try:
        repo = WebhookConfigRepository(session)
        webhook = await repo.update(
            webhook_id=webhook_id,
            name=data.name,
            url=data.url,
            method=data.method,
            headers=data.headers,
            payload_template=data.payload_template,
            events=data.events,
            secret=data.secret,
            is_active=data.is_active,
            retry_count=data.retry_count,
            timeout_seconds=data.timeout_seconds,
        )
        await session.commit()

        if webhook is None:
            raise HTTPException(status_code=404, detail="Webhook not found")

        return WebhookConfigResponse.model_validate(webhook)

    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Webhook with name '{data.name}' already exists",
        )
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            "Failed to update webhook",
            extra={
                "webhook_id": webhook_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to update webhook")


@router.delete(
    "/webhooks/{webhook_id}",
    status_code=204,
    summary="Delete webhook configuration",
    description="Delete a webhook configuration.",
)
async def delete_webhook(
    webhook_id: Annotated[str, Path(description="Webhook UUID")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    """Delete a webhook configuration."""
    logger.debug("Deleting webhook", extra={"webhook_id": webhook_id})

    repo = WebhookConfigRepository(session)
    deleted = await repo.delete(webhook_id)
    await session.commit()

    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")


# -----------------------------------------------------------------------------
# Notification Sending Endpoints
# -----------------------------------------------------------------------------


@router.post(
    "/send/email",
    response_model=SendNotificationResponse,
    summary="Send email notification",
    description="Send an email using a template.",
)
async def send_email(
    data: SendEmailRequest,
    service: Annotated[NotificationService, Depends(get_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SendNotificationResponse:
    """Send an email notification using a template."""
    start_time = time.monotonic()
    logger.debug(
        "API: Sending email",
        extra={
            "template_name": data.template_name,
            "recipient": data.recipient[:50],
            "project_id": data.project_id,
        },
    )

    try:
        result = await service.send_email(
            template_name=data.template_name,
            recipient=data.recipient,
            variables=data.variables,
            project_id=data.project_id,
        )
        await session.commit()

        duration_ms = (time.monotonic() - start_time) * 1000
        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow email send API call",
                extra={"duration_ms": round(duration_ms, 2)},
            )

        return result

    except TemplateNotFoundError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await session.rollback()
        logger.error(
            "API: Email send failed",
            extra={
                "template_name": data.template_name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": traceback.format_exc(),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to send email")


@router.post(
    "/send/webhook",
    response_model=SendNotificationResponse,
    summary="Send webhook notification",
    description="Send a webhook notification to a configured endpoint.",
)
async def send_webhook(
    data: SendWebhookRequest,
    service: Annotated[NotificationService, Depends(get_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SendNotificationResponse:
    """Send a webhook notification."""
    start_time = time.monotonic()
    logger.debug(
        "API: Sending webhook",
        extra={
            "webhook_name": data.webhook_name,
            "event": data.event,
            "project_id": data.project_id,
        },
    )

    try:
        result = await service.send_webhook(
            webhook_name=data.webhook_name,
            event=data.event,
            variables=data.variables,
            project_id=data.project_id,
        )
        await session.commit()

        duration_ms = (time.monotonic() - start_time) * 1000
        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow webhook send API call",
                extra={"duration_ms": round(duration_ms, 2)},
            )

        return result

    except WebhookConfigNotFoundError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        await session.rollback()
        logger.error(
            "API: Webhook send failed",
            extra={
                "webhook_name": data.webhook_name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": traceback.format_exc(),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to send webhook")


@router.post(
    "/trigger",
    response_model=TriggerEventResponse,
    summary="Trigger notification event",
    description="Trigger all notifications configured for an event.",
)
async def trigger_event(
    data: TriggerEventRequest,
    service: Annotated[NotificationService, Depends(get_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TriggerEventResponse:
    """Trigger all configured notifications for an event."""
    start_time = time.monotonic()
    logger.debug(
        "API: Triggering event",
        extra={
            "event": data.event,
            "project_id": data.project_id,
        },
    )

    try:
        result = await service.trigger_event(
            event=data.event,
            variables=data.variables,
            project_id=data.project_id,
        )
        await session.commit()

        duration_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "API: Event triggered",
            extra={
                "event": data.event,
                "notifications_sent": result.notifications_sent,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return result

    except Exception as e:
        await session.rollback()
        logger.error(
            "API: Event trigger failed",
            extra={
                "event": data.event,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "stack_trace": traceback.format_exc(),
            },
        )
        raise HTTPException(status_code=500, detail="Failed to trigger event")


# -----------------------------------------------------------------------------
# Notification Log Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/logs",
    response_model=NotificationLogListResponse,
    summary="List notification logs",
    description="List notification delivery logs with optional filtering.",
)
async def list_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    project_id: str | None = Query(None, description="Filter by project ID"),
    channel: str | None = Query(None, description="Filter by channel (email/webhook)"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
) -> NotificationLogListResponse:
    """List notification logs."""
    logger.debug(
        "Listing notification logs",
        extra={
            "project_id": project_id,
            "channel": channel,
            "status": status,
            "limit": limit,
            "offset": offset,
        },
    )

    repo = NotificationLogRepository(session)

    if project_id:
        logs = await repo.list_by_project(
            project_id=project_id,
            channel=channel,
            status=status,
            limit=limit,
            offset=offset,
        )
        total = await repo.count(project_id=project_id, channel=channel, status=status)
    else:
        logs = await repo.list_all(
            channel=channel,
            status=status,
            limit=limit,
            offset=offset,
        )
        total = await repo.count(channel=channel, status=status)

    return NotificationLogListResponse(
        items=[NotificationLogResponse.model_validate(log) for log in logs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/logs/{log_id}",
    response_model=NotificationLogResponse,
    summary="Get notification log",
    description="Get a notification log entry by ID.",
)
async def get_log(
    log_id: Annotated[str, Path(description="Log entry UUID")],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationLogResponse:
    """Get a notification log entry."""
    logger.debug("Getting notification log", extra={"log_id": log_id})

    repo = NotificationLogRepository(session)
    log = await repo.get_by_id(log_id)

    if log is None:
        raise HTTPException(status_code=404, detail="Log entry not found")

    return NotificationLogResponse.model_validate(log)
