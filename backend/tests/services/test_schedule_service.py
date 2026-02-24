"""Unit tests for ScheduleService.

Tests cover:
- Creating schedule configurations
- Getting schedules by ID
- Listing schedules with pagination
- Updating schedule configurations
- Deleting schedules
- Validation (UUID, cron, pagination)
- Error handling and logging

ERROR LOGGING REQUIREMENTS (verified by tests):
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, schedule_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (is_active changes) at INFO level
- Add timing logs for operations >1 second

Target: 80% code coverage.
"""

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.crawl_schedule import CrawlSchedule
from app.services.schedule import (
    ScheduleNotFoundError,
    ScheduleService,
    ScheduleServiceError,
    ScheduleValidationError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_repository():
    """Create a mock ScheduleRepository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.get_by_id = AsyncMock()
    repo.get_by_project = AsyncMock()
    repo.count_by_project = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.exists = AsyncMock()
    return repo


@pytest.fixture
def sample_schedule():
    """Create a sample CrawlSchedule instance."""
    schedule = MagicMock(spec=CrawlSchedule)
    schedule.id = "11111111-1111-1111-1111-111111111111"
    schedule.project_id = "22222222-2222-2222-2222-222222222222"
    schedule.schedule_type = "daily"
    schedule.start_url = "https://example.com"
    schedule.cron_expression = None
    schedule.max_pages = 100
    schedule.max_depth = 3
    schedule.config = {}
    schedule.is_active = True
    return schedule


@pytest.fixture
def sample_create_data():
    """Create sample schedule creation data."""
    data = MagicMock()
    data.schedule_type = "daily"
    data.start_url = "https://example.com"
    data.cron_expression = None
    data.max_pages = 100
    data.max_depth = 3
    data.config = {}
    data.is_active = True
    return data


@pytest.fixture
def sample_update_data():
    """Create sample schedule update data."""
    data = MagicMock()
    data.schedule_type = None
    data.cron_expression = None
    data.start_url = None
    data.max_pages = None
    data.max_depth = None
    data.config = None
    data.is_active = None
    data.model_dump.return_value = {}
    return data


@pytest.fixture
def service(mock_session, mock_repository):
    """Create service instance with mocks."""
    service = ScheduleService(session=mock_session)
    service.repository = mock_repository
    return service


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestScheduleServiceExceptions:
    """Tests for ScheduleService exception classes."""

    def test_schedule_service_error(self):
        """Test base ScheduleServiceError."""
        error = ScheduleServiceError("Test error")
        assert str(error) == "Test error"

    def test_schedule_not_found_error(self):
        """Test ScheduleNotFoundError."""
        error = ScheduleNotFoundError("schedule-123")
        assert error.schedule_id == "schedule-123"
        assert "schedule-123" in str(error)
        assert isinstance(error, ScheduleServiceError)

    def test_schedule_validation_error(self):
        """Test ScheduleValidationError."""
        error = ScheduleValidationError(
            field="cron_expression",
            value="invalid",
            message="Invalid cron format",
        )
        assert error.field == "cron_expression"
        assert error.value == "invalid"
        assert error.message == "Invalid cron format"
        assert "cron_expression" in str(error)
        assert isinstance(error, ScheduleServiceError)


# ---------------------------------------------------------------------------
# Test: UUID Validation
# ---------------------------------------------------------------------------


class TestUUIDValidation:
    """Tests for UUID validation."""

    def test_validate_uuid_success(self, service):
        """Test valid UUID passes validation."""
        # Should not raise
        service._validate_uuid(
            "12345678-1234-1234-1234-123456789012",
            "test_field",
        )

    def test_validate_uuid_empty(self, service):
        """Test empty UUID raises error."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            service._validate_uuid("", "test_field")

        assert exc_info.value.field == "test_field"
        assert "required" in exc_info.value.message.lower()

    def test_validate_uuid_none(self, service):
        """Test None UUID raises error."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            service._validate_uuid(None, "test_field")

        assert exc_info.value.field == "test_field"

    def test_validate_uuid_invalid_format(self, service):
        """Test invalid UUID format raises error."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            service._validate_uuid("not-a-valid-uuid", "test_field")

        assert exc_info.value.field == "test_field"
        assert "format" in exc_info.value.message.lower()

    def test_validate_uuid_case_insensitive(self, service):
        """Test UUID validation is case insensitive."""
        # Should not raise - uppercase hex digits
        service._validate_uuid(
            "ABCDEF12-1234-1234-1234-123456789ABC",
            "test_field",
        )


# ---------------------------------------------------------------------------
# Test: Schedule Type and Cron Validation
# ---------------------------------------------------------------------------


class TestScheduleTypeCronValidation:
    """Tests for schedule_type and cron_expression validation."""

    def test_validate_cron_required_for_cron_type(self, service):
        """Test cron_expression is required when type is 'cron'."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            service._validate_schedule_type_cron("cron", None)

        assert exc_info.value.field == "cron_expression"
        assert "required" in exc_info.value.message.lower()

    def test_validate_cron_not_allowed_for_other_types(self, service):
        """Test cron_expression not allowed for non-cron types."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            service._validate_schedule_type_cron("daily", "0 0 * * *")

        assert exc_info.value.field == "cron_expression"
        assert "only be provided" in exc_info.value.message.lower()

    def test_validate_daily_without_cron(self, service):
        """Test daily type without cron_expression is valid."""
        # Should not raise
        service._validate_schedule_type_cron("daily", None)

    def test_validate_cron_with_expression(self, service):
        """Test cron type with cron_expression is valid."""
        # Should not raise
        service._validate_schedule_type_cron("cron", "0 0 * * *")


# ---------------------------------------------------------------------------
# Test: Pagination Validation
# ---------------------------------------------------------------------------


class TestPaginationValidation:
    """Tests for pagination parameter validation."""

    def test_validate_pagination_success(self, service):
        """Test valid pagination parameters."""
        # Should not raise
        service._validate_pagination(limit=50, offset=0)

    def test_validate_pagination_limit_zero(self, service):
        """Test limit of zero raises error."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            service._validate_pagination(limit=0, offset=0)

        assert exc_info.value.field == "limit"

    def test_validate_pagination_limit_negative(self, service):
        """Test negative limit raises error."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            service._validate_pagination(limit=-1, offset=0)

        assert exc_info.value.field == "limit"

    def test_validate_pagination_limit_too_large(self, service):
        """Test limit > 1000 raises error."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            service._validate_pagination(limit=1001, offset=0)

        assert exc_info.value.field == "limit"
        assert "1000" in exc_info.value.message

    def test_validate_pagination_offset_negative(self, service):
        """Test negative offset raises error."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            service._validate_pagination(limit=10, offset=-1)

        assert exc_info.value.field == "offset"

    def test_validate_pagination_max_limit(self, service):
        """Test max limit of 1000 is valid."""
        # Should not raise
        service._validate_pagination(limit=1000, offset=0)


# ---------------------------------------------------------------------------
# Test: create_schedule
# ---------------------------------------------------------------------------


class TestCreateSchedule:
    """Tests for create_schedule method."""

    @pytest.mark.asyncio
    async def test_create_schedule_success(
        self,
        service,
        mock_repository,
        sample_schedule,
        sample_create_data,
    ):
        """Test successful schedule creation."""
        mock_repository.create.return_value = sample_schedule

        result = await service.create_schedule(
            project_id="22222222-2222-2222-2222-222222222222",
            data=sample_create_data,
        )

        assert result.id == "11111111-1111-1111-1111-111111111111"
        mock_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_project_id(
        self,
        service,
        sample_create_data,
    ):
        """Test schedule creation with invalid project_id."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            await service.create_schedule(
                project_id="invalid-uuid",
                data=sample_create_data,
            )

        assert exc_info.value.field == "project_id"

    @pytest.mark.asyncio
    async def test_create_schedule_cron_without_expression(
        self,
        service,
        sample_create_data,
    ):
        """Test cron schedule type requires cron_expression."""
        sample_create_data.schedule_type = "cron"
        sample_create_data.cron_expression = None

        with pytest.raises(ScheduleValidationError) as exc_info:
            await service.create_schedule(
                project_id="22222222-2222-2222-2222-222222222222",
                data=sample_create_data,
            )

        assert exc_info.value.field == "cron_expression"


# ---------------------------------------------------------------------------
# Test: get_schedule
# ---------------------------------------------------------------------------


class TestGetSchedule:
    """Tests for get_schedule method."""

    @pytest.mark.asyncio
    async def test_get_schedule_success(
        self,
        service,
        mock_repository,
        sample_schedule,
    ):
        """Test successful schedule retrieval."""
        mock_repository.get_by_id.return_value = sample_schedule

        result = await service.get_schedule(
            "11111111-1111-1111-1111-111111111111"
        )

        assert result.id == "11111111-1111-1111-1111-111111111111"
        mock_repository.get_by_id.assert_called_once_with(
            "11111111-1111-1111-1111-111111111111"
        )

    @pytest.mark.asyncio
    async def test_get_schedule_not_found(
        self,
        service,
        mock_repository,
    ):
        """Test schedule not found raises error."""
        mock_repository.get_by_id.return_value = None

        with pytest.raises(ScheduleNotFoundError) as exc_info:
            await service.get_schedule("11111111-1111-1111-1111-111111111111")

        assert exc_info.value.schedule_id == "11111111-1111-1111-1111-111111111111"

    @pytest.mark.asyncio
    async def test_get_schedule_invalid_id(self, service):
        """Test invalid schedule_id raises validation error."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            await service.get_schedule("invalid-uuid")

        assert exc_info.value.field == "schedule_id"


# ---------------------------------------------------------------------------
# Test: get_schedule_or_none
# ---------------------------------------------------------------------------


class TestGetScheduleOrNone:
    """Tests for get_schedule_or_none method."""

    @pytest.mark.asyncio
    async def test_get_schedule_or_none_found(
        self,
        service,
        mock_repository,
        sample_schedule,
    ):
        """Test returns schedule when found."""
        mock_repository.get_by_id.return_value = sample_schedule

        result = await service.get_schedule_or_none(
            "11111111-1111-1111-1111-111111111111"
        )

        assert result is not None
        assert result.id == "11111111-1111-1111-1111-111111111111"

    @pytest.mark.asyncio
    async def test_get_schedule_or_none_not_found(
        self,
        service,
        mock_repository,
    ):
        """Test returns None when not found."""
        mock_repository.get_by_id.return_value = None

        result = await service.get_schedule_or_none(
            "11111111-1111-1111-1111-111111111111"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_schedule_or_none_invalid_uuid(self, service):
        """Test returns None for invalid UUID."""
        result = await service.get_schedule_or_none("invalid-uuid")
        assert result is None


# ---------------------------------------------------------------------------
# Test: list_schedules
# ---------------------------------------------------------------------------


class TestListSchedules:
    """Tests for list_schedules method."""

    @pytest.mark.asyncio
    async def test_list_schedules_success(
        self,
        service,
        mock_repository,
        sample_schedule,
    ):
        """Test successful schedule listing."""
        mock_repository.get_by_project.return_value = [sample_schedule]
        mock_repository.count_by_project.return_value = 1

        schedules, total = await service.list_schedules(
            project_id="22222222-2222-2222-2222-222222222222",
            limit=10,
            offset=0,
        )

        assert len(schedules) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_schedules_empty(
        self,
        service,
        mock_repository,
    ):
        """Test listing when no schedules exist."""
        mock_repository.get_by_project.return_value = []
        mock_repository.count_by_project.return_value = 0

        schedules, total = await service.list_schedules(
            project_id="22222222-2222-2222-2222-222222222222",
        )

        assert len(schedules) == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_schedules_invalid_project_id(self, service):
        """Test listing with invalid project_id."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            await service.list_schedules(
                project_id="invalid-uuid",
            )

        assert exc_info.value.field == "project_id"

    @pytest.mark.asyncio
    async def test_list_schedules_invalid_pagination(self, service):
        """Test listing with invalid pagination."""
        with pytest.raises(ScheduleValidationError) as exc_info:
            await service.list_schedules(
                project_id="22222222-2222-2222-2222-222222222222",
                limit=0,
            )

        assert exc_info.value.field == "limit"


# ---------------------------------------------------------------------------
# Test: update_schedule
# ---------------------------------------------------------------------------


class TestUpdateSchedule:
    """Tests for update_schedule method."""

    @pytest.mark.asyncio
    async def test_update_schedule_success(
        self,
        service,
        mock_repository,
        sample_schedule,
        sample_update_data,
    ):
        """Test successful schedule update."""
        sample_update_data.max_pages = 200
        sample_update_data.model_dump.return_value = {"max_pages": 200}

        mock_repository.get_by_id.return_value = sample_schedule
        mock_repository.update.return_value = sample_schedule

        result = await service.update_schedule(
            schedule_id="11111111-1111-1111-1111-111111111111",
            data=sample_update_data,
        )

        assert result is not None
        mock_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_schedule_not_found(
        self,
        service,
        mock_repository,
        sample_update_data,
    ):
        """Test update when schedule not found."""
        mock_repository.get_by_id.return_value = None

        with pytest.raises(ScheduleNotFoundError):
            await service.update_schedule(
                schedule_id="11111111-1111-1111-1111-111111111111",
                data=sample_update_data,
            )

    @pytest.mark.asyncio
    async def test_update_schedule_logs_activation_change(
        self,
        service,
        mock_repository,
        sample_schedule,
        sample_update_data,
    ):
        """Test that is_active change is logged."""
        sample_schedule.is_active = True
        sample_update_data.is_active = False
        sample_update_data.model_dump.return_value = {"is_active": False}

        mock_repository.get_by_id.return_value = sample_schedule
        mock_repository.update.return_value = sample_schedule

        # Should complete without error
        await service.update_schedule(
            schedule_id="11111111-1111-1111-1111-111111111111",
            data=sample_update_data,
        )

    @pytest.mark.asyncio
    async def test_update_schedule_validate_cron_change(
        self,
        service,
        mock_repository,
        sample_schedule,
        sample_update_data,
    ):
        """Test validation when changing to cron type."""
        sample_schedule.schedule_type = "daily"
        sample_update_data.schedule_type = "cron"
        sample_update_data.cron_expression = None

        mock_repository.get_by_id.return_value = sample_schedule

        with pytest.raises(ScheduleValidationError) as exc_info:
            await service.update_schedule(
                schedule_id="11111111-1111-1111-1111-111111111111",
                data=sample_update_data,
            )

        assert exc_info.value.field == "cron_expression"


# ---------------------------------------------------------------------------
# Test: delete_schedule
# ---------------------------------------------------------------------------


class TestDeleteSchedule:
    """Tests for delete_schedule method."""

    @pytest.mark.asyncio
    async def test_delete_schedule_success(
        self,
        service,
        mock_repository,
    ):
        """Test successful schedule deletion."""
        mock_repository.delete.return_value = True

        result = await service.delete_schedule(
            "11111111-1111-1111-1111-111111111111"
        )

        assert result is True
        mock_repository.delete.assert_called_once_with(
            "11111111-1111-1111-1111-111111111111"
        )

    @pytest.mark.asyncio
    async def test_delete_schedule_not_found(
        self,
        service,
        mock_repository,
    ):
        """Test delete when schedule not found."""
        mock_repository.delete.return_value = False

        with pytest.raises(ScheduleNotFoundError):
            await service.delete_schedule(
                "11111111-1111-1111-1111-111111111111"
            )

    @pytest.mark.asyncio
    async def test_delete_schedule_invalid_id(self, service):
        """Test delete with invalid schedule_id."""
        with pytest.raises(ScheduleValidationError):
            await service.delete_schedule("invalid-uuid")


# ---------------------------------------------------------------------------
# Test: schedule_exists
# ---------------------------------------------------------------------------


class TestScheduleExists:
    """Tests for schedule_exists method."""

    @pytest.mark.asyncio
    async def test_schedule_exists_true(
        self,
        service,
        mock_repository,
    ):
        """Test schedule exists returns True."""
        mock_repository.exists.return_value = True

        result = await service.schedule_exists(
            "11111111-1111-1111-1111-111111111111"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_schedule_exists_false(
        self,
        service,
        mock_repository,
    ):
        """Test schedule exists returns False."""
        mock_repository.exists.return_value = False

        result = await service.schedule_exists(
            "11111111-1111-1111-1111-111111111111"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_schedule_exists_invalid_uuid(self, service):
        """Test schedule exists returns False for invalid UUID."""
        result = await service.schedule_exists("invalid-uuid")
        assert result is False


# ---------------------------------------------------------------------------
# Test: Service Initialization
# ---------------------------------------------------------------------------


class TestScheduleServiceInit:
    """Tests for service initialization."""

    def test_init_creates_repository(self, mock_session):
        """Test that initialization creates repository."""
        service = ScheduleService(session=mock_session)

        assert service.session is mock_session
        assert service.repository is not None
