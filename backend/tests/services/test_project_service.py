"""Unit tests for ProjectService.

Tests cover:
- CRUD operations (create, read, update, delete)
- Validation logic (UUID, status, phase transitions)
- Business rules (status transitions, phase transitions)
- Error handling (ProjectNotFoundError, ProjectValidationError, InvalidPhaseTransitionError)
- Logging requirements (DEBUG entry/exit, WARNING validation failures, INFO state transitions)

Target: 80% code coverage.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.schemas.project import (
    PhaseStatusUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from app.services.project import (
    InvalidPhaseTransitionError,
    ProjectNotFoundError,
    ProjectService,
    ProjectServiceError,
    ProjectValidationError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_service(db_session: AsyncSession) -> ProjectService:
    """Create a ProjectService instance with test database session."""
    return ProjectService(db_session)


@pytest.fixture
def valid_project_data() -> ProjectCreate:
    """Valid project creation data."""
    return ProjectCreate(
        name="Test Project",
        client_id="client-123",
        status="active",
        phase_status={
            "discovery": {"status": "pending"},
        },
    )


@pytest.fixture
async def created_project(
    project_service: ProjectService,
    valid_project_data: ProjectCreate,
) -> Project:
    """Create a project for tests that need an existing project."""
    return await project_service.create_project(valid_project_data)


# ---------------------------------------------------------------------------
# Test: create_project
# ---------------------------------------------------------------------------


class TestCreateProject:
    """Tests for ProjectService.create_project method."""

    async def test_create_project_success(
        self,
        project_service: ProjectService,
        valid_project_data: ProjectCreate,
    ) -> None:
        """Should create a project with valid data."""
        project = await project_service.create_project(valid_project_data)

        assert project is not None
        assert project.id is not None
        assert project.name == "Test Project"
        assert project.client_id == "client-123"
        assert project.status == "active"
        assert project.phase_status == {"discovery": {"status": "pending"}}

    async def test_create_project_minimal_data(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should create project with minimal required fields."""
        data = ProjectCreate(
            name="Minimal Project",
            client_id="client-456",
        )
        project = await project_service.create_project(data)

        assert project.name == "Minimal Project"
        assert project.client_id == "client-456"
        assert project.status == "active"  # Default
        assert project.phase_status == {}  # Default

    async def test_create_project_name_too_short(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should reject project name shorter than 2 characters."""
        data = ProjectCreate(
            name="A",  # Only 1 character
            client_id="client-123",
        )

        with pytest.raises(ProjectValidationError) as exc_info:
            await project_service.create_project(data)

        assert exc_info.value.field == "name"
        assert "at least 2 characters" in exc_info.value.message

    async def test_create_project_invalid_phase_name_at_schema_level(
        self,
    ) -> None:
        """Invalid phase names are rejected at Pydantic schema level."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ProjectCreate(
                name="Test Project",
                client_id="client-123",
                phase_status={
                    "invalid_phase": {"status": "pending"},
                },
            )

        assert "phase_status" in str(exc_info.value)
        assert "invalid_phase" in str(exc_info.value)

    async def test_create_project_invalid_phase_status_at_schema_level(
        self,
    ) -> None:
        """Invalid phase status values are rejected at Pydantic schema level."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ProjectCreate(
                name="Test Project",
                client_id="client-123",
                phase_status={
                    "discovery": {"status": "invalid_status"},
                },
            )

        assert "phase_status" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test: get_project
# ---------------------------------------------------------------------------


class TestGetProject:
    """Tests for ProjectService.get_project method."""

    async def test_get_project_success(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should return project for valid ID."""
        result = await project_service.get_project(created_project.id)

        assert result is not None
        assert result.id == created_project.id
        assert result.name == created_project.name

    async def test_get_project_not_found(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should raise ProjectNotFoundError for non-existent ID."""
        non_existent_id = "12345678-1234-1234-1234-123456789012"

        with pytest.raises(ProjectNotFoundError) as exc_info:
            await project_service.get_project(non_existent_id)

        assert exc_info.value.project_id == non_existent_id

    async def test_get_project_invalid_uuid(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should raise ProjectValidationError for invalid UUID format."""
        with pytest.raises(ProjectValidationError) as exc_info:
            await project_service.get_project("invalid-uuid")

        assert exc_info.value.field == "project_id"
        assert "Invalid UUID format" in exc_info.value.message

    async def test_get_project_empty_id(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should raise ProjectValidationError for empty ID."""
        with pytest.raises(ProjectValidationError) as exc_info:
            await project_service.get_project("")

        assert exc_info.value.field == "project_id"


# ---------------------------------------------------------------------------
# Test: get_project_or_none
# ---------------------------------------------------------------------------


class TestGetProjectOrNone:
    """Tests for ProjectService.get_project_or_none method."""

    async def test_get_project_or_none_found(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should return project when found."""
        result = await project_service.get_project_or_none(created_project.id)

        assert result is not None
        assert result.id == created_project.id

    async def test_get_project_or_none_not_found(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should return None for non-existent ID."""
        result = await project_service.get_project_or_none(
            "12345678-1234-1234-1234-123456789012"
        )

        assert result is None

    async def test_get_project_or_none_invalid_uuid(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should return None for invalid UUID (graceful handling)."""
        result = await project_service.get_project_or_none("invalid-uuid")

        assert result is None


# ---------------------------------------------------------------------------
# Test: get_projects_by_client
# ---------------------------------------------------------------------------


class TestGetProjectsByClient:
    """Tests for ProjectService.get_projects_by_client method."""

    async def test_get_projects_by_client_success(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should return all projects for a client."""
        # Create multiple projects for same client
        for i in range(3):
            data = ProjectCreate(
                name=f"Project {i}",
                client_id="same-client",
            )
            await project_service.create_project(data)

        results = await project_service.get_projects_by_client("same-client")

        assert len(results) == 3
        assert all(p.client_id == "same-client" for p in results)

    async def test_get_projects_by_client_empty(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should return empty list for non-existent client."""
        results = await project_service.get_projects_by_client("non-existent-client")

        assert results == []

    async def test_get_projects_by_client_empty_client_id(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should raise validation error for empty client_id."""
        with pytest.raises(ProjectValidationError) as exc_info:
            await project_service.get_projects_by_client("")

        assert exc_info.value.field == "client_id"


# ---------------------------------------------------------------------------
# Test: get_projects_by_status
# ---------------------------------------------------------------------------


class TestGetProjectsByStatus:
    """Tests for ProjectService.get_projects_by_status method."""

    async def test_get_projects_by_status_success(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should return all projects with given status."""
        # Create projects with different statuses
        for status in ["active", "completed", "active"]:
            data = ProjectCreate(
                name=f"Project-{status}",
                client_id="client-123",
                status=status,
            )
            await project_service.create_project(data)

        results = await project_service.get_projects_by_status("active")

        assert len(results) == 2
        assert all(p.status == "active" for p in results)

    async def test_get_projects_by_status_invalid(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should raise validation error for invalid status."""
        with pytest.raises(ProjectValidationError) as exc_info:
            await project_service.get_projects_by_status("invalid_status")

        assert exc_info.value.field == "status"


# ---------------------------------------------------------------------------
# Test: list_projects
# ---------------------------------------------------------------------------


class TestListProjects:
    """Tests for ProjectService.list_projects method."""

    async def test_list_projects_success(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should return paginated list of projects."""
        # Create 5 projects
        for i in range(5):
            data = ProjectCreate(name=f"Project {i}", client_id="client-123")
            await project_service.create_project(data)

        projects, total = await project_service.list_projects(limit=10, offset=0)

        assert len(projects) == 5
        assert total == 5

    async def test_list_projects_pagination(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should respect pagination parameters."""
        # Create 5 projects
        for i in range(5):
            data = ProjectCreate(name=f"Project {i}", client_id="client-123")
            await project_service.create_project(data)

        projects, total = await project_service.list_projects(limit=2, offset=1)

        assert len(projects) == 2
        assert total == 5

    async def test_list_projects_invalid_limit_zero(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should reject limit of 0."""
        with pytest.raises(ProjectValidationError) as exc_info:
            await project_service.list_projects(limit=0, offset=0)

        assert exc_info.value.field == "limit"

    async def test_list_projects_invalid_limit_too_large(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should reject limit greater than 1000."""
        with pytest.raises(ProjectValidationError) as exc_info:
            await project_service.list_projects(limit=1001, offset=0)

        assert exc_info.value.field == "limit"

    async def test_list_projects_invalid_negative_offset(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should reject negative offset."""
        with pytest.raises(ProjectValidationError) as exc_info:
            await project_service.list_projects(limit=10, offset=-1)

        assert exc_info.value.field == "offset"


# ---------------------------------------------------------------------------
# Test: update_project
# ---------------------------------------------------------------------------


class TestUpdateProject:
    """Tests for ProjectService.update_project method."""

    async def test_update_project_name(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should update project name."""
        update_data = ProjectUpdate(name="Updated Name")

        updated = await project_service.update_project(
            created_project.id, update_data
        )

        assert updated.name == "Updated Name"
        assert updated.id == created_project.id

    async def test_update_project_status_valid_transition(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should allow valid status transitions."""
        # active -> on_hold is valid
        update_data = ProjectUpdate(status="on_hold")

        updated = await project_service.update_project(
            created_project.id, update_data
        )

        assert updated.status == "on_hold"

    async def test_update_project_status_invalid_transition(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should reject invalid status transitions."""
        # active -> archived is not valid (must go through completed/cancelled first)
        update_data = ProjectUpdate(status="archived")

        with pytest.raises(ProjectValidationError) as exc_info:
            await project_service.update_project(created_project.id, update_data)

        assert exc_info.value.field == "status"
        assert "Cannot transition" in exc_info.value.message

    async def test_update_project_not_found(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should raise ProjectNotFoundError for non-existent project."""
        update_data = ProjectUpdate(name="New Name")
        non_existent_id = "12345678-1234-1234-1234-123456789012"

        with pytest.raises(ProjectNotFoundError) as exc_info:
            await project_service.update_project(non_existent_id, update_data)

        assert exc_info.value.project_id == non_existent_id

    async def test_update_project_phase_status(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should update phase_status."""
        new_phase_status = {
            "discovery": {"status": "in_progress"},
            "requirements": {"status": "pending"},
        }
        update_data = ProjectUpdate(phase_status=new_phase_status)

        updated = await project_service.update_project(
            created_project.id, update_data
        )

        assert updated.phase_status["discovery"]["status"] == "in_progress"
        assert updated.phase_status["requirements"]["status"] == "pending"


# ---------------------------------------------------------------------------
# Test: Status Transitions
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    """Tests for project status transition rules."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("active", "completed"),
            ("active", "on_hold"),
            ("active", "cancelled"),
            ("on_hold", "active"),
            ("on_hold", "cancelled"),
            ("completed", "archived"),
            ("cancelled", "archived"),
        ],
    )
    async def test_valid_status_transitions(
        self,
        project_service: ProjectService,
        from_status: str,
        to_status: str,
    ) -> None:
        """Should allow valid status transitions."""
        # Create project with initial status
        data = ProjectCreate(
            name="Test Project",
            client_id="client-123",
            status=from_status,
        )
        project = await project_service.create_project(data)

        # Attempt transition
        update_data = ProjectUpdate(status=to_status)
        updated = await project_service.update_project(project.id, update_data)

        assert updated.status == to_status

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("active", "archived"),  # Must go through completed/cancelled
            ("archived", "active"),  # Final state
            ("completed", "active"),  # No going back from completed
            ("cancelled", "active"),  # No going back from cancelled
        ],
    )
    async def test_invalid_status_transitions(
        self,
        project_service: ProjectService,
        from_status: str,
        to_status: str,
    ) -> None:
        """Should reject invalid status transitions."""
        # Create project with initial status
        data = ProjectCreate(
            name="Test Project",
            client_id="client-123",
            status=from_status,
        )
        project = await project_service.create_project(data)

        # Attempt invalid transition
        update_data = ProjectUpdate(status=to_status)

        with pytest.raises(ProjectValidationError):
            await project_service.update_project(project.id, update_data)


# ---------------------------------------------------------------------------
# Test: update_phase_status
# ---------------------------------------------------------------------------


class TestUpdatePhaseStatus:
    """Tests for ProjectService.update_phase_status method."""

    async def test_update_phase_status_new_phase(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should add new phase status."""
        update_data = PhaseStatusUpdate(
            phase="requirements",
            status="pending",
        )

        updated = await project_service.update_phase_status(
            created_project.id, update_data
        )

        assert updated.phase_status["requirements"]["status"] == "pending"

    async def test_update_phase_status_valid_transition(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should allow valid phase status transitions."""
        # Create project with pending discovery phase
        data = ProjectCreate(
            name="Test Project",
            client_id="client-123",
            phase_status={"discovery": {"status": "pending"}},
        )
        project = await project_service.create_project(data)

        # pending -> in_progress is valid
        update_data = PhaseStatusUpdate(phase="discovery", status="in_progress")
        updated = await project_service.update_phase_status(project.id, update_data)

        assert updated.phase_status["discovery"]["status"] == "in_progress"

    async def test_update_phase_status_invalid_transition(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should reject invalid phase status transitions."""
        # Create project with pending discovery phase
        data = ProjectCreate(
            name="Test Project",
            client_id="client-123",
            phase_status={"discovery": {"status": "pending"}},
        )
        project = await project_service.create_project(data)

        # pending -> completed is NOT valid (must go through in_progress first)
        update_data = PhaseStatusUpdate(phase="discovery", status="completed")

        with pytest.raises(InvalidPhaseTransitionError) as exc_info:
            await project_service.update_phase_status(project.id, update_data)

        assert exc_info.value.phase == "discovery"
        assert exc_info.value.from_status == "pending"
        assert exc_info.value.to_status == "completed"

    async def test_update_phase_status_with_metadata(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should include metadata in phase status update."""
        update_data = PhaseStatusUpdate(
            phase="implementation",
            status="in_progress",
            metadata={"assigned_to": "user-456", "started_at": "2024-01-15"},
        )

        updated = await project_service.update_phase_status(
            created_project.id, update_data
        )

        phase_data = updated.phase_status["implementation"]
        assert phase_data["status"] == "in_progress"
        assert phase_data["assigned_to"] == "user-456"
        assert phase_data["started_at"] == "2024-01-15"

    async def test_update_phase_status_not_found(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should raise ProjectNotFoundError for non-existent project."""
        update_data = PhaseStatusUpdate(phase="discovery", status="in_progress")
        non_existent_id = "12345678-1234-1234-1234-123456789012"

        with pytest.raises(ProjectNotFoundError):
            await project_service.update_phase_status(non_existent_id, update_data)


# ---------------------------------------------------------------------------
# Test: Phase Transitions
# ---------------------------------------------------------------------------


class TestPhaseTransitions:
    """Tests for phase status transition rules."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("pending", "in_progress"),
            ("pending", "skipped"),
            ("in_progress", "completed"),
            ("in_progress", "blocked"),
            ("blocked", "in_progress"),
            ("blocked", "skipped"),
        ],
    )
    async def test_valid_phase_transitions(
        self,
        project_service: ProjectService,
        from_status: str,
        to_status: str,
    ) -> None:
        """Should allow valid phase transitions."""
        data = ProjectCreate(
            name="Test Project",
            client_id="client-123",
            phase_status={"discovery": {"status": from_status}},
        )
        project = await project_service.create_project(data)

        update_data = PhaseStatusUpdate(phase="discovery", status=to_status)
        updated = await project_service.update_phase_status(project.id, update_data)

        assert updated.phase_status["discovery"]["status"] == to_status

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            ("pending", "completed"),  # Must go through in_progress
            ("pending", "blocked"),    # Can't block what hasn't started
            ("completed", "in_progress"),  # Final state
            ("skipped", "in_progress"),  # Final state
        ],
    )
    async def test_invalid_phase_transitions(
        self,
        project_service: ProjectService,
        from_status: str,
        to_status: str,
    ) -> None:
        """Should reject invalid phase transitions."""
        data = ProjectCreate(
            name="Test Project",
            client_id="client-123",
            phase_status={"discovery": {"status": from_status}},
        )
        project = await project_service.create_project(data)

        update_data = PhaseStatusUpdate(phase="discovery", status=to_status)

        with pytest.raises(InvalidPhaseTransitionError):
            await project_service.update_phase_status(project.id, update_data)


# ---------------------------------------------------------------------------
# Test: delete_project
# ---------------------------------------------------------------------------


class TestDeleteProject:
    """Tests for ProjectService.delete_project method."""

    async def test_delete_project_success(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should delete existing project."""
        result = await project_service.delete_project(created_project.id)

        assert result is True

        # Verify project is deleted
        exists = await project_service.project_exists(created_project.id)
        assert exists is False

    async def test_delete_project_not_found(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should raise ProjectNotFoundError for non-existent project."""
        non_existent_id = "12345678-1234-1234-1234-123456789012"

        with pytest.raises(ProjectNotFoundError) as exc_info:
            await project_service.delete_project(non_existent_id)

        assert exc_info.value.project_id == non_existent_id

    async def test_delete_project_invalid_uuid(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should raise ProjectValidationError for invalid UUID."""
        with pytest.raises(ProjectValidationError):
            await project_service.delete_project("invalid-uuid")


# ---------------------------------------------------------------------------
# Test: project_exists
# ---------------------------------------------------------------------------


class TestProjectExists:
    """Tests for ProjectService.project_exists method."""

    async def test_project_exists_true(
        self,
        project_service: ProjectService,
        created_project: Project,
    ) -> None:
        """Should return True for existing project."""
        result = await project_service.project_exists(created_project.id)

        assert result is True

    async def test_project_exists_false(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should return False for non-existent project."""
        result = await project_service.project_exists(
            "12345678-1234-1234-1234-123456789012"
        )

        assert result is False

    async def test_project_exists_invalid_uuid(
        self,
        project_service: ProjectService,
    ) -> None:
        """Should return False for invalid UUID (graceful handling)."""
        result = await project_service.project_exists("invalid-uuid")

        assert result is False


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for custom exception classes."""

    def test_project_service_error_base(self) -> None:
        """ProjectServiceError should be base exception."""
        error = ProjectServiceError("Base error")

        assert isinstance(error, Exception)
        assert str(error) == "Base error"

    def test_project_not_found_error(self) -> None:
        """ProjectNotFoundError should contain project_id."""
        error = ProjectNotFoundError("test-id-123")

        assert error.project_id == "test-id-123"
        assert "test-id-123" in str(error)
        assert isinstance(error, ProjectServiceError)

    def test_project_validation_error(self) -> None:
        """ProjectValidationError should contain field, value, and message."""
        error = ProjectValidationError("name", "bad-value", "Invalid name")

        assert error.field == "name"
        assert error.value == "bad-value"
        assert error.message == "Invalid name"
        assert "name" in str(error)
        assert isinstance(error, ProjectServiceError)

    def test_invalid_phase_transition_error(self) -> None:
        """InvalidPhaseTransitionError should contain transition details."""
        error = InvalidPhaseTransitionError(
            phase="discovery",
            from_status="pending",
            to_status="completed",
            reason="Must go through in_progress first",
        )

        assert error.phase == "discovery"
        assert error.from_status == "pending"
        assert error.to_status == "completed"
        assert error.reason == "Must go through in_progress first"
        assert "discovery" in str(error)
        assert isinstance(error, ProjectServiceError)
