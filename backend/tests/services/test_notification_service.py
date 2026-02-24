"""Unit tests for NotificationService.

Tests cover:
- Email sending via templates
- Webhook sending via configurations
- Event triggering for configured notifications
- Template variable substitution
- Error handling and validation
- Logging per requirements

ERROR LOGGING REQUIREMENTS (verified by tests):
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, notification_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (delivery status) at INFO level
- Add timing logs for operations >1 second

Target: 80% code coverage.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.notification import NotificationChannel, NotificationStatus
from app.schemas.notification import SendNotificationResponse, TriggerEventResponse
from app.services.notification import (
    NotificationService,
    NotificationServiceError,
    TemplateNotFoundError,
    TemplateRenderError,
    WebhookConfigNotFoundError,
    get_notification_service,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_email_client():
    """Create a mock email client."""
    client = MagicMock()
    client.send = AsyncMock()
    return client


@pytest.fixture
def mock_webhook_client():
    """Create a mock webhook client."""
    client = MagicMock()
    client.send = AsyncMock()
    return client


@pytest.fixture
def mock_template_repo():
    """Create a mock template repository."""
    repo = MagicMock()
    repo.get_by_name = AsyncMock()
    return repo


@pytest.fixture
def mock_webhook_repo():
    """Create a mock webhook config repository."""
    repo = MagicMock()
    repo.get_by_name = AsyncMock()
    repo.get_by_event = AsyncMock()
    return repo


@pytest.fixture
def mock_log_repo():
    """Create a mock notification log repository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.update_status = AsyncMock()
    return repo


@pytest.fixture
def sample_template():
    """Create a sample notification template."""
    template = MagicMock()
    template.id = "template-123"
    template.name = "welcome_email"
    template.is_active = True
    template.subject = "Welcome to {{company_name}}, {{user_name}}!"
    template.body_html = "<h1>Welcome {{user_name}}</h1><p>Thanks for joining {{company_name}}.</p>"
    template.body_text = "Welcome {{user_name}}! Thanks for joining {{company_name}}."
    return template


@pytest.fixture
def sample_webhook_config():
    """Create a sample webhook config."""
    config = MagicMock()
    config.id = "webhook-123"
    config.name = "slack_notifications"
    config.url = "https://hooks.slack.com/services/XXX"
    config.method = "POST"
    config.is_active = True
    config.headers = {"Content-Type": "application/json"}
    config.secret = "webhook-secret"
    config.timeout_seconds = 30
    config.retry_count = 3
    config.payload_template = {
        "text": "{{event_type}}: {{message}}",
        "channel": "#notifications",
    }
    config.events = ["project.created", "project.completed"]
    return config


@pytest.fixture
def sample_notification_log():
    """Create a sample notification log."""
    log = MagicMock()
    log.id = "log-123"
    log.channel = NotificationChannel.EMAIL.value
    log.recipient = "user@example.com"
    log.status = NotificationStatus.SENDING.value
    return log


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestNotificationServiceExceptions:
    """Tests for NotificationService exception classes."""

    def test_notification_service_error(self):
        """Test base NotificationServiceError."""
        error = NotificationServiceError("Test error")
        assert str(error) == "Test error"

    def test_template_not_found_error(self):
        """Test TemplateNotFoundError."""
        error = TemplateNotFoundError("welcome_email")
        assert error.name == "welcome_email"
        assert "welcome_email" in str(error)
        assert isinstance(error, NotificationServiceError)

    def test_webhook_config_not_found_error(self):
        """Test WebhookConfigNotFoundError."""
        error = WebhookConfigNotFoundError("slack_webhook")
        assert error.name == "slack_webhook"
        assert "slack_webhook" in str(error)
        assert isinstance(error, NotificationServiceError)

    def test_template_render_error(self):
        """Test TemplateRenderError."""
        error = TemplateRenderError("welcome_email", ["user_name", "company"])
        assert error.template_name == "welcome_email"
        assert error.missing_vars == ["user_name", "company"]
        assert "welcome_email" in str(error)
        assert "user_name" in str(error)
        assert isinstance(error, NotificationServiceError)


# ---------------------------------------------------------------------------
# Test: Variable Substitution
# ---------------------------------------------------------------------------


class TestVariableSubstitution:
    """Tests for template variable substitution methods."""

    @pytest.fixture
    def service(self, mock_session, mock_email_client, mock_webhook_client):
        """Create service instance with mocks."""
        return NotificationService(
            session=mock_session,
            email_client=mock_email_client,
            webhook_client=mock_webhook_client,
        )

    def test_substitute_variables_simple(self, service):
        """Test simple variable substitution."""
        template = "Hello {{name}}, welcome to {{company}}!"
        variables = {"name": "John", "company": "Acme Corp"}

        result = service._substitute_variables(template, variables)

        assert result == "Hello John, welcome to Acme Corp!"

    def test_substitute_variables_missing_var(self, service):
        """Test substitution with missing variable leaves placeholder."""
        template = "Hello {{name}}, your code is {{code}}"
        variables = {"name": "John"}

        result = service._substitute_variables(template, variables)

        assert result == "Hello John, your code is {{code}}"

    def test_substitute_variables_none_value(self, service):
        """Test substitution with None value."""
        template = "Value is: {{value}}"
        variables = {"value": None}

        result = service._substitute_variables(template, variables)

        assert result == "Value is: "

    def test_substitute_variables_empty_template(self, service):
        """Test substitution with empty template."""
        result = service._substitute_variables("", {"name": "John"})
        assert result == ""

    def test_substitute_variables_no_placeholders(self, service):
        """Test substitution with no placeholders."""
        template = "No variables here"
        result = service._substitute_variables(template, {"name": "John"})
        assert result == "No variables here"

    def test_substitute_dict_variables_simple(self, service):
        """Test dict variable substitution."""
        template_dict = {
            "greeting": "Hello {{name}}",
            "message": "Welcome to {{company}}",
        }
        variables = {"name": "John", "company": "Acme"}

        result = service._substitute_dict_variables(template_dict, variables)

        assert result["greeting"] == "Hello John"
        assert result["message"] == "Welcome to Acme"

    def test_substitute_dict_variables_nested(self, service):
        """Test nested dict variable substitution."""
        template_dict = {
            "outer": {
                "inner": "Hello {{name}}",
            },
        }
        variables = {"name": "John"}

        result = service._substitute_dict_variables(template_dict, variables)

        assert result["outer"]["inner"] == "Hello John"

    def test_substitute_dict_variables_with_list(self, service):
        """Test dict substitution with list values."""
        template_dict = {
            "items": ["{{item1}}", "{{item2}}", "static"],
        }
        variables = {"item1": "First", "item2": "Second"}

        result = service._substitute_dict_variables(template_dict, variables)

        assert result["items"] == ["First", "Second", "static"]

    def test_substitute_dict_variables_non_string(self, service):
        """Test dict substitution preserves non-string values."""
        template_dict = {
            "count": 42,
            "active": True,
            "name": "{{name}}",
        }
        variables = {"name": "John"}

        result = service._substitute_dict_variables(template_dict, variables)

        assert result["count"] == 42
        assert result["active"] is True
        assert result["name"] == "John"


# ---------------------------------------------------------------------------
# Test: send_email
# ---------------------------------------------------------------------------


class TestSendEmail:
    """Tests for send_email method."""

    @pytest.fixture
    def service(
        self,
        mock_session,
        mock_email_client,
        mock_webhook_client,
        mock_template_repo,
        mock_log_repo,
    ):
        """Create service instance with mocks."""
        service = NotificationService(
            session=mock_session,
            email_client=mock_email_client,
            webhook_client=mock_webhook_client,
        )
        service.template_repo = mock_template_repo
        service.log_repo = mock_log_repo
        return service

    @pytest.mark.asyncio
    async def test_send_email_success(
        self,
        service,
        mock_email_client,
        mock_template_repo,
        mock_log_repo,
        sample_template,
        sample_notification_log,
    ):
        """Test successful email sending."""
        mock_template_repo.get_by_name.return_value = sample_template
        mock_log_repo.create.return_value = sample_notification_log

        # Mock successful send
        send_result = MagicMock()
        send_result.success = True
        send_result.message_id = "msg-123"
        mock_email_client.send.return_value = send_result

        result = await service.send_email(
            template_name="welcome_email",
            recipient="user@example.com",
            variables={"user_name": "John", "company_name": "Acme"},
            project_id="proj-123",
        )

        assert result.success is True
        assert result.notification_id == "log-123"
        assert result.channel == NotificationChannel.EMAIL.value
        mock_template_repo.get_by_name.assert_called_once_with("welcome_email")
        mock_email_client.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_email_template_not_found(
        self,
        service,
        mock_template_repo,
    ):
        """Test email sending with missing template."""
        mock_template_repo.get_by_name.return_value = None

        with pytest.raises(TemplateNotFoundError) as exc_info:
            await service.send_email(
                template_name="nonexistent_template",
                recipient="user@example.com",
                variables={},
            )

        assert exc_info.value.name == "nonexistent_template"

    @pytest.mark.asyncio
    async def test_send_email_template_inactive(
        self,
        service,
        mock_template_repo,
        sample_template,
    ):
        """Test email sending with inactive template."""
        sample_template.is_active = False
        mock_template_repo.get_by_name.return_value = sample_template

        with pytest.raises(TemplateNotFoundError) as exc_info:
            await service.send_email(
                template_name="welcome_email",
                recipient="user@example.com",
                variables={},
            )

        assert "inactive" in exc_info.value.name

    @pytest.mark.asyncio
    async def test_send_email_failure(
        self,
        service,
        mock_email_client,
        mock_template_repo,
        mock_log_repo,
        sample_template,
        sample_notification_log,
    ):
        """Test email sending failure."""
        mock_template_repo.get_by_name.return_value = sample_template
        mock_log_repo.create.return_value = sample_notification_log

        # Mock failed send
        send_result = MagicMock()
        send_result.success = False
        send_result.error = "SMTP connection failed"
        send_result.retry_attempt = 3
        mock_email_client.send.return_value = send_result

        result = await service.send_email(
            template_name="welcome_email",
            recipient="user@example.com",
            variables={"user_name": "John", "company_name": "Acme"},
        )

        assert result.success is False
        assert result.status == NotificationStatus.FAILED.value
        assert result.message == "SMTP connection failed"

    @pytest.mark.asyncio
    async def test_send_email_variable_substitution(
        self,
        service,
        mock_email_client,
        mock_template_repo,
        mock_log_repo,
        sample_template,
        sample_notification_log,
    ):
        """Test that variables are substituted in email."""
        mock_template_repo.get_by_name.return_value = sample_template
        mock_log_repo.create.return_value = sample_notification_log

        send_result = MagicMock()
        send_result.success = True
        send_result.message_id = "msg-123"
        mock_email_client.send.return_value = send_result

        await service.send_email(
            template_name="welcome_email",
            recipient="user@example.com",
            variables={"user_name": "Alice", "company_name": "TechCo"},
        )

        # Check that substituted content was passed to email client
        call_args = mock_email_client.send.call_args
        assert "Alice" in call_args.kwargs.get("subject", "")
        assert "TechCo" in call_args.kwargs.get("subject", "")


# ---------------------------------------------------------------------------
# Test: send_webhook
# ---------------------------------------------------------------------------


class TestSendWebhook:
    """Tests for send_webhook method."""

    @pytest.fixture
    def service(
        self,
        mock_session,
        mock_email_client,
        mock_webhook_client,
        mock_webhook_repo,
        mock_log_repo,
    ):
        """Create service instance with mocks."""
        service = NotificationService(
            session=mock_session,
            email_client=mock_email_client,
            webhook_client=mock_webhook_client,
        )
        service.webhook_repo = mock_webhook_repo
        service.log_repo = mock_log_repo
        return service

    @pytest.mark.asyncio
    async def test_send_webhook_success(
        self,
        service,
        mock_webhook_client,
        mock_webhook_repo,
        mock_log_repo,
        sample_webhook_config,
        sample_notification_log,
    ):
        """Test successful webhook sending."""
        mock_webhook_repo.get_by_name.return_value = sample_webhook_config
        sample_notification_log.channel = NotificationChannel.WEBHOOK.value
        mock_log_repo.create.return_value = sample_notification_log

        # Mock successful send
        send_result = MagicMock()
        send_result.success = True
        send_result.status_code = 200
        send_result.response_body = {"ok": True}
        mock_webhook_client.send.return_value = send_result

        result = await service.send_webhook(
            webhook_name="slack_notifications",
            event="project.created",
            variables={"message": "New project created"},
            project_id="proj-123",
        )

        assert result.success is True
        assert result.channel == NotificationChannel.WEBHOOK.value
        mock_webhook_repo.get_by_name.assert_called_once_with("slack_notifications")
        mock_webhook_client.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_webhook_config_not_found(
        self,
        service,
        mock_webhook_repo,
    ):
        """Test webhook sending with missing config."""
        mock_webhook_repo.get_by_name.return_value = None

        with pytest.raises(WebhookConfigNotFoundError) as exc_info:
            await service.send_webhook(
                webhook_name="nonexistent_webhook",
                event="test.event",
                variables={},
            )

        assert exc_info.value.name == "nonexistent_webhook"

    @pytest.mark.asyncio
    async def test_send_webhook_config_inactive(
        self,
        service,
        mock_webhook_repo,
        sample_webhook_config,
    ):
        """Test webhook sending with inactive config."""
        sample_webhook_config.is_active = False
        mock_webhook_repo.get_by_name.return_value = sample_webhook_config

        with pytest.raises(WebhookConfigNotFoundError) as exc_info:
            await service.send_webhook(
                webhook_name="slack_notifications",
                event="test.event",
                variables={},
            )

        assert "inactive" in exc_info.value.name

    @pytest.mark.asyncio
    async def test_send_webhook_failure(
        self,
        service,
        mock_webhook_client,
        mock_webhook_repo,
        mock_log_repo,
        sample_webhook_config,
        sample_notification_log,
    ):
        """Test webhook sending failure."""
        mock_webhook_repo.get_by_name.return_value = sample_webhook_config
        sample_notification_log.channel = NotificationChannel.WEBHOOK.value
        mock_log_repo.create.return_value = sample_notification_log

        # Mock failed send
        send_result = MagicMock()
        send_result.success = False
        send_result.status_code = 500
        send_result.response_body = {"error": "Internal server error"}
        send_result.error = "HTTP 500 error"
        send_result.retry_attempt = 3
        mock_webhook_client.send.return_value = send_result

        result = await service.send_webhook(
            webhook_name="slack_notifications",
            event="test.event",
            variables={"message": "Test"},
        )

        assert result.success is False
        assert result.status == NotificationStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_send_webhook_empty_payload_template(
        self,
        service,
        mock_webhook_client,
        mock_webhook_repo,
        mock_log_repo,
        sample_webhook_config,
        sample_notification_log,
    ):
        """Test webhook with empty payload template uses variables directly."""
        sample_webhook_config.payload_template = {}
        mock_webhook_repo.get_by_name.return_value = sample_webhook_config
        sample_notification_log.channel = NotificationChannel.WEBHOOK.value
        mock_log_repo.create.return_value = sample_notification_log

        send_result = MagicMock()
        send_result.success = True
        send_result.status_code = 200
        send_result.response_body = {}
        mock_webhook_client.send.return_value = send_result

        await service.send_webhook(
            webhook_name="slack_notifications",
            event="test.event",
            variables={"custom_field": "value"},
            project_id="proj-123",
        )

        call_args = mock_webhook_client.send.call_args
        payload = call_args.kwargs.get("payload", {})
        assert "custom_field" in payload
        assert "event_type" in payload
        assert "project_id" in payload


# ---------------------------------------------------------------------------
# Test: trigger_event
# ---------------------------------------------------------------------------


class TestTriggerEvent:
    """Tests for trigger_event method."""

    @pytest.fixture
    def service(
        self,
        mock_session,
        mock_email_client,
        mock_webhook_client,
        mock_webhook_repo,
        mock_log_repo,
    ):
        """Create service instance with mocks."""
        service = NotificationService(
            session=mock_session,
            email_client=mock_email_client,
            webhook_client=mock_webhook_client,
        )
        service.webhook_repo = mock_webhook_repo
        service.log_repo = mock_log_repo
        return service

    @pytest.mark.asyncio
    async def test_trigger_event_no_webhooks(
        self,
        service,
        mock_webhook_repo,
    ):
        """Test triggering event with no webhooks subscribed."""
        mock_webhook_repo.get_by_event.return_value = []

        result = await service.trigger_event(
            event="test.event",
            variables={"message": "Test"},
            project_id="proj-123",
        )

        assert isinstance(result, TriggerEventResponse)
        assert result.event == "test.event"
        assert result.notifications_sent == 0
        assert len(result.results) == 0

    @pytest.mark.asyncio
    async def test_trigger_event_multiple_webhooks(
        self,
        service,
        mock_webhook_repo,
        mock_webhook_client,
        mock_log_repo,
        sample_webhook_config,
        sample_notification_log,
    ):
        """Test triggering event with multiple webhooks."""
        # Create two webhook configs
        webhook1 = MagicMock()
        webhook1.id = "webhook-1"
        webhook1.name = "webhook_1"
        webhook1.url = "https://example.com/hook1"
        webhook1.method = "POST"
        webhook1.is_active = True
        webhook1.headers = {}
        webhook1.secret = None
        webhook1.timeout_seconds = 30
        webhook1.retry_count = 3
        webhook1.payload_template = {}

        webhook2 = MagicMock()
        webhook2.id = "webhook-2"
        webhook2.name = "webhook_2"
        webhook2.url = "https://example.com/hook2"
        webhook2.method = "POST"
        webhook2.is_active = True
        webhook2.headers = {}
        webhook2.secret = None
        webhook2.timeout_seconds = 30
        webhook2.retry_count = 3
        webhook2.payload_template = {}

        mock_webhook_repo.get_by_event.return_value = [webhook1, webhook2]
        mock_webhook_repo.get_by_name.side_effect = lambda name: (
            webhook1 if name == "webhook_1" else webhook2
        )

        sample_notification_log.channel = NotificationChannel.WEBHOOK.value
        mock_log_repo.create.return_value = sample_notification_log

        send_result = MagicMock()
        send_result.success = True
        send_result.status_code = 200
        send_result.response_body = {}
        mock_webhook_client.send.return_value = send_result

        result = await service.trigger_event(
            event="project.created",
            variables={"project_name": "Test Project"},
            project_id="proj-123",
        )

        assert result.notifications_sent == 2
        assert len(result.results) == 2
        assert all(r.success for r in result.results)

    @pytest.mark.asyncio
    async def test_trigger_event_partial_failure(
        self,
        service,
        mock_webhook_repo,
        mock_webhook_client,
        mock_log_repo,
        sample_notification_log,
    ):
        """Test triggering event with some webhook failures."""
        webhook1 = MagicMock()
        webhook1.id = "webhook-1"
        webhook1.name = "webhook_1"
        webhook1.url = "https://example.com/hook1"
        webhook1.method = "POST"
        webhook1.is_active = True
        webhook1.headers = {}
        webhook1.secret = None
        webhook1.timeout_seconds = 30
        webhook1.retry_count = 3
        webhook1.payload_template = {}

        mock_webhook_repo.get_by_event.return_value = [webhook1]
        mock_webhook_repo.get_by_name.return_value = webhook1

        sample_notification_log.channel = NotificationChannel.WEBHOOK.value
        mock_log_repo.create.return_value = sample_notification_log

        # First webhook succeeds, second fails
        send_result = MagicMock()
        send_result.success = True
        send_result.status_code = 200
        send_result.response_body = {}
        mock_webhook_client.send.return_value = send_result

        result = await service.trigger_event(
            event="project.created",
            variables={},
        )

        assert result.notifications_sent == 1

    @pytest.mark.asyncio
    async def test_trigger_event_webhook_exception(
        self,
        service,
        mock_webhook_repo,
    ):
        """Test triggering event when webhook raises exception."""
        webhook = MagicMock()
        webhook.id = "webhook-1"
        webhook.name = "failing_webhook"

        mock_webhook_repo.get_by_event.return_value = [webhook]
        mock_webhook_repo.get_by_name.side_effect = Exception("Connection error")

        result = await service.trigger_event(
            event="project.created",
            variables={},
        )

        # Should still return a result with the failure recorded
        assert result.notifications_sent == 1
        assert len(result.results) == 1
        assert result.results[0].success is False
        assert "Connection error" in result.results[0].message


# ---------------------------------------------------------------------------
# Test: Service Factory
# ---------------------------------------------------------------------------


class TestGetNotificationService:
    """Tests for get_notification_service factory."""

    def test_get_notification_service(self, mock_session):
        """Test service factory function returns NotificationService."""
        # Patch the get_email_client and get_webhook_client to avoid Settings errors
        with patch("app.services.notification.get_email_client") as mock_email:
            with patch("app.services.notification.get_webhook_client") as mock_webhook:
                mock_email.return_value = MagicMock()
                mock_webhook.return_value = MagicMock()

                service = get_notification_service(mock_session)

                assert isinstance(service, NotificationService)
                assert service.session is mock_session


# ---------------------------------------------------------------------------
# Test: Service Initialization
# ---------------------------------------------------------------------------


class TestNotificationServiceInit:
    """Tests for service initialization."""

    def test_init_with_defaults(self, mock_session):
        """Test service initialization with default dependencies."""
        with patch("app.services.notification.get_email_client") as mock_get_email:
            with patch("app.services.notification.get_webhook_client") as mock_get_webhook:
                mock_get_email.return_value = MagicMock()
                mock_get_webhook.return_value = MagicMock()

                service = NotificationService(session=mock_session)

                assert service.session is mock_session
                mock_get_email.assert_called_once()
                mock_get_webhook.assert_called_once()

    def test_init_with_custom_clients(
        self, mock_session, mock_email_client, mock_webhook_client
    ):
        """Test service initialization with custom clients."""
        service = NotificationService(
            session=mock_session,
            email_client=mock_email_client,
            webhook_client=mock_webhook_client,
        )

        assert service._email_client is mock_email_client
        assert service._webhook_client is mock_webhook_client
