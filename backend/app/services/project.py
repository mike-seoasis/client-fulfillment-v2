"""ProjectService with validation logic.

Orchestrates business logic for Project entities between API layer and repository.
Handles validation, business rules, and logging as required.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.project import Project
from app.repositories.project import ProjectRepository
from app.schemas.project import (
    VALID_PHASE_STATUSES,
    VALID_PHASES,
    VALID_PROJECT_STATUSES,
    PhaseStatusUpdate,
    ProjectCreate,
    ProjectUpdate,
)

logger = get_logger(__name__)

# Threshold for logging slow operations
SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second


class ProjectServiceError(Exception):
    """Base exception for ProjectService errors."""

    pass


class ProjectNotFoundError(ProjectServiceError):
    """Raised when a project is not found."""

    def __init__(self, project_id: str):
        self.project_id = project_id
        super().__init__(f"Project not found: {project_id}")


class ProjectValidationError(ProjectServiceError):
    """Raised when project validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class InvalidPhaseTransitionError(ProjectServiceError):
    """Raised when a phase transition is not allowed."""

    def __init__(self, phase: str, from_status: str, to_status: str, reason: str):
        self.phase = phase
        self.from_status = from_status
        self.to_status = to_status
        self.reason = reason
        super().__init__(
            f"Invalid phase transition for '{phase}': {from_status} -> {to_status}. {reason}"
        )


class ProjectService:
    """Service for Project business logic and validation.

    Coordinates between API layer and repository, handling:
    - Input validation
    - Business rules (e.g., phase transition rules)
    - Logging requirements
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session
        self.repository = ProjectRepository(session)
        logger.debug("ProjectService initialized")

    async def create_project(self, data: ProjectCreate) -> Project:
        """Create a new project with validation.

        Args:
            data: Validated project creation data

        Returns:
            Created Project instance

        Raises:
            ProjectValidationError: If validation fails
        """
        start_time = time.monotonic()
        logger.debug(
            "Creating project",
            extra={
                "name": data.name,
                "client_id": data.client_id,
                "status": data.status,
            },
        )

        try:
            # Additional business validation
            self._validate_project_name(data.name)
            self._validate_initial_phase_status(data.phase_status)

            project = await self.repository.create(
                name=data.name,
                client_id=data.client_id,
                status=data.status,
                phase_status=data.phase_status,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project created successfully",
                extra={
                    "project_id": project.id,
                    "name": project.name,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow project creation",
                    extra={
                        "project_id": project.id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return project

        except ProjectServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to create project",
                extra={
                    "name": data.name,
                    "client_id": data.client_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_project(self, project_id: str) -> Project:
        """Get a project by ID.

        Args:
            project_id: UUID of the project

        Returns:
            Project instance

        Raises:
            ProjectNotFoundError: If project is not found
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching project",
            extra={"project_id": project_id},
        )

        try:
            self._validate_uuid(project_id, "project_id")

            project = await self.repository.get_by_id(project_id)
            if project is None:
                logger.debug(
                    "Project not found",
                    extra={"project_id": project_id},
                )
                raise ProjectNotFoundError(project_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project fetched successfully",
                extra={
                    "project_id": project_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow project fetch",
                    extra={
                        "project_id": project_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return project

        except ProjectServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to fetch project",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_project_or_none(self, project_id: str) -> Project | None:
        """Get a project by ID, returning None if not found.

        Args:
            project_id: UUID of the project

        Returns:
            Project instance or None if not found
        """
        logger.debug(
            "Fetching project (nullable)",
            extra={"project_id": project_id},
        )

        try:
            self._validate_uuid(project_id, "project_id")
            return await self.repository.get_by_id(project_id)
        except ProjectValidationError:
            return None
        except Exception as e:
            logger.error(
                "Failed to fetch project",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_projects_by_client(self, client_id: str) -> list[Project]:
        """Get all projects for a client.

        Args:
            client_id: Client identifier

        Returns:
            List of Project instances
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching projects by client",
            extra={"client_id": client_id},
        )

        try:
            self._validate_client_id(client_id)

            projects = await self.repository.get_by_client_id(client_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Client projects fetched",
                extra={
                    "client_id": client_id,
                    "count": len(projects),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow client projects fetch",
                    extra={
                        "client_id": client_id,
                        "count": len(projects),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return projects

        except ProjectServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to fetch projects by client",
                extra={
                    "client_id": client_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_projects_by_status(self, status: str) -> list[Project]:
        """Get all projects with a specific status.

        Args:
            status: Project status to filter by

        Returns:
            List of Project instances

        Raises:
            ProjectValidationError: If status is invalid
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching projects by status",
            extra={"status": status},
        )

        try:
            self._validate_status(status)

            projects = await self.repository.get_by_status(status)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Status projects fetched",
                extra={
                    "status": status,
                    "count": len(projects),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow status projects fetch",
                    extra={
                        "status": status,
                        "count": len(projects),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return projects

        except ProjectServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to fetch projects by status",
                extra={
                    "status": status,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def list_projects(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Project], int]:
        """List all projects with pagination.

        Args:
            limit: Maximum number of projects to return
            offset: Number of projects to skip

        Returns:
            Tuple of (list of projects, total count)

        Raises:
            ProjectValidationError: If pagination params are invalid
        """
        start_time = time.monotonic()
        logger.debug(
            "Listing projects",
            extra={"limit": limit, "offset": offset},
        )

        try:
            self._validate_pagination(limit, offset)

            projects = await self.repository.list_all(limit=limit, offset=offset)
            total = await self.repository.count()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Projects listed",
                extra={
                    "count": len(projects),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow project list",
                    extra={
                        "limit": limit,
                        "offset": offset,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return projects, total

        except ProjectServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to list projects",
                extra={
                    "limit": limit,
                    "offset": offset,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update_project(
        self,
        project_id: str,
        data: ProjectUpdate,
    ) -> Project:
        """Update a project.

        Args:
            project_id: UUID of the project to update
            data: Validated update data

        Returns:
            Updated Project instance

        Raises:
            ProjectNotFoundError: If project is not found
            ProjectValidationError: If validation fails
        """
        start_time = time.monotonic()
        logger.debug(
            "Updating project",
            extra={
                "project_id": project_id,
                "update_fields": [
                    k for k, v in data.model_dump().items() if v is not None
                ],
            },
        )

        try:
            self._validate_uuid(project_id, "project_id")

            # Verify project exists
            existing = await self.repository.get_by_id(project_id)
            if existing is None:
                raise ProjectNotFoundError(project_id)

            # Validate status transition if status is being updated
            if data.status is not None and data.status != existing.status:
                self._validate_status_transition(existing.status, data.status)
                logger.info(
                    "Project status transition",
                    extra={
                        "project_id": project_id,
                        "from_status": existing.status,
                        "to_status": data.status,
                    },
                )

            # Validate phase_status if being updated
            if data.phase_status is not None:
                self._validate_phase_status_update(
                    existing.phase_status, data.phase_status
                )

            project = await self.repository.update(
                project_id=project_id,
                name=data.name,
                status=data.status,
                phase_status=data.phase_status,
            )

            if project is None:
                raise ProjectNotFoundError(project_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project updated successfully",
                extra={
                    "project_id": project_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow project update",
                    extra={
                        "project_id": project_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return project

        except ProjectServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to update project",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update_phase_status(
        self,
        project_id: str,
        data: PhaseStatusUpdate,
    ) -> Project:
        """Update a specific phase's status.

        Args:
            project_id: UUID of the project
            data: Phase status update data

        Returns:
            Updated Project instance

        Raises:
            ProjectNotFoundError: If project is not found
            InvalidPhaseTransitionError: If phase transition is not allowed
        """
        start_time = time.monotonic()
        logger.debug(
            "Updating phase status",
            extra={
                "project_id": project_id,
                "phase": data.phase,
                "new_status": data.status,
            },
        )

        try:
            self._validate_uuid(project_id, "project_id")

            # Get existing project to validate transition
            existing = await self.repository.get_by_id(project_id)
            if existing is None:
                raise ProjectNotFoundError(project_id)

            # Get current phase status
            current_phase_data = existing.phase_status.get(data.phase, {})
            current_status = (
                current_phase_data.get("status") if current_phase_data else None
            )

            # Validate phase transition
            if current_status and current_status != data.status:
                self._validate_phase_transition(
                    phase=data.phase,
                    from_status=current_status,
                    to_status=data.status,
                )
                logger.info(
                    "Phase status transition",
                    extra={
                        "project_id": project_id,
                        "phase": data.phase,
                        "from_status": current_status,
                        "to_status": data.status,
                    },
                )

            project = await self.repository.update_phase_status(
                project_id=project_id,
                phase=data.phase,
                status=data.status,
                metadata=data.metadata,
            )

            if project is None:
                raise ProjectNotFoundError(project_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Phase status updated successfully",
                extra={
                    "project_id": project_id,
                    "phase": data.phase,
                    "status": data.status,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow phase status update",
                    extra={
                        "project_id": project_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return project

        except ProjectServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to update phase status",
                extra={
                    "project_id": project_id,
                    "phase": data.phase,
                    "status": data.status,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project.

        Args:
            project_id: UUID of the project to delete

        Returns:
            True if project was deleted

        Raises:
            ProjectNotFoundError: If project is not found
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting project",
            extra={"project_id": project_id},
        )

        try:
            self._validate_uuid(project_id, "project_id")

            deleted = await self.repository.delete(project_id)
            if not deleted:
                raise ProjectNotFoundError(project_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project deleted successfully",
                extra={
                    "project_id": project_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow project delete",
                    extra={
                        "project_id": project_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return True

        except ProjectServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to delete project",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def project_exists(self, project_id: str) -> bool:
        """Check if a project exists.

        Args:
            project_id: UUID of the project

        Returns:
            True if project exists
        """
        logger.debug(
            "Checking project existence",
            extra={"project_id": project_id},
        )

        try:
            self._validate_uuid(project_id, "project_id")
            return await self.repository.exists(project_id)
        except ProjectValidationError:
            return False
        except Exception as e:
            logger.error(
                "Failed to check project existence",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Validation Methods
    # -------------------------------------------------------------------------

    def _validate_uuid(self, value: str, field: str) -> None:
        """Validate a UUID string.

        Args:
            value: String to validate as UUID
            field: Field name for error messages

        Raises:
            ProjectValidationError: If value is not a valid UUID
        """
        if not value or not isinstance(value, str):
            logger.warning(
                "Validation failed: empty or invalid UUID",
                extra={"field": field, "value": value},
            )
            raise ProjectValidationError(field, value, "UUID is required")

        # Basic UUID format check (36 chars with hyphens or 32 without)
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(value):
            logger.warning(
                "Validation failed: invalid UUID format",
                extra={"field": field, "value": value},
            )
            raise ProjectValidationError(field, value, "Invalid UUID format")

    def _validate_project_name(self, name: str) -> None:
        """Validate project name business rules.

        Args:
            name: Project name to validate

        Raises:
            ProjectValidationError: If name fails validation
        """
        if len(name) < 2:
            logger.warning(
                "Validation failed: project name too short",
                extra={"field": "name", "value": name, "min_length": 2},
            )
            raise ProjectValidationError(
                "name", name, "Project name must be at least 2 characters"
            )

    def _validate_client_id(self, client_id: str) -> None:
        """Validate client ID.

        Args:
            client_id: Client ID to validate

        Raises:
            ProjectValidationError: If client_id is invalid
        """
        if not client_id or not client_id.strip():
            logger.warning(
                "Validation failed: empty client_id",
                extra={"field": "client_id", "value": client_id},
            )
            raise ProjectValidationError(
                "client_id", client_id, "Client ID is required"
            )

    def _validate_status(self, status: str) -> None:
        """Validate project status.

        Args:
            status: Status to validate

        Raises:
            ProjectValidationError: If status is invalid
        """
        if status not in VALID_PROJECT_STATUSES:
            logger.warning(
                "Validation failed: invalid status",
                extra={
                    "field": "status",
                    "value": status,
                    "valid": list(VALID_PROJECT_STATUSES),
                },
            )
            raise ProjectValidationError(
                "status",
                status,
                f"Must be one of: {', '.join(sorted(VALID_PROJECT_STATUSES))}",
            )

    def _validate_status_transition(self, from_status: str, to_status: str) -> None:
        """Validate project status transition.

        Args:
            from_status: Current status
            to_status: Target status

        Raises:
            ProjectValidationError: If transition is not allowed
        """
        # Define allowed transitions
        allowed_transitions: dict[str, set[str]] = {
            "active": {"completed", "on_hold", "cancelled"},
            "on_hold": {"active", "cancelled"},
            "completed": {"archived"},
            "cancelled": {"archived"},
            "archived": set(),  # Final state - no transitions allowed
        }

        allowed = allowed_transitions.get(from_status, set())
        if to_status not in allowed:
            logger.warning(
                "Validation failed: invalid status transition",
                extra={
                    "from_status": from_status,
                    "to_status": to_status,
                    "allowed": list(allowed),
                },
            )
            raise ProjectValidationError(
                "status",
                to_status,
                f"Cannot transition from '{from_status}' to '{to_status}'. "
                f"Allowed: {', '.join(sorted(allowed)) if allowed else 'none'}",
            )

    def _validate_initial_phase_status(self, phase_status: dict[str, Any]) -> None:
        """Validate initial phase_status for new project.

        Args:
            phase_status: Phase status dict to validate

        Raises:
            ProjectValidationError: If validation fails
        """
        for phase_name, phase_data in phase_status.items():
            if phase_name not in VALID_PHASES:
                logger.warning(
                    "Validation failed: invalid phase name",
                    extra={
                        "field": "phase_status",
                        "phase": phase_name,
                        "valid": list(VALID_PHASES),
                    },
                )
                raise ProjectValidationError(
                    "phase_status",
                    phase_name,
                    f"Invalid phase '{phase_name}'. Must be one of: {', '.join(sorted(VALID_PHASES))}",
                )

            if isinstance(phase_data, dict) and "status" in phase_data:
                status = phase_data["status"]
                if status not in VALID_PHASE_STATUSES:
                    logger.warning(
                        "Validation failed: invalid phase status",
                        extra={
                            "field": "phase_status",
                            "phase": phase_name,
                            "status": status,
                            "valid": list(VALID_PHASE_STATUSES),
                        },
                    )
                    raise ProjectValidationError(
                        "phase_status",
                        status,
                        f"Invalid status '{status}' for phase '{phase_name}'. "
                        f"Must be one of: {', '.join(sorted(VALID_PHASE_STATUSES))}",
                    )

    def _validate_phase_status_update(
        self,
        current_phase_status: dict[str, Any],
        new_phase_status: dict[str, Any],
    ) -> None:
        """Validate phase_status update.

        Args:
            current_phase_status: Current phase status dict
            new_phase_status: New phase status dict

        Raises:
            ProjectValidationError: If validation fails
            InvalidPhaseTransitionError: If transition is not allowed
        """
        # First validate structure
        self._validate_initial_phase_status(new_phase_status)

        # Then validate transitions for each changed phase
        for phase_name, new_data in new_phase_status.items():
            if not isinstance(new_data, dict):
                continue

            new_status = new_data.get("status")
            if not new_status:
                continue

            current_data = current_phase_status.get(phase_name, {})
            current_status = (
                current_data.get("status") if isinstance(current_data, dict) else None
            )

            if current_status and current_status != new_status:
                self._validate_phase_transition(phase_name, current_status, new_status)

    def _validate_phase_transition(
        self,
        phase: str,
        from_status: str,
        to_status: str,
    ) -> None:
        """Validate phase status transition.

        Args:
            phase: Phase name
            from_status: Current phase status
            to_status: Target phase status

        Raises:
            InvalidPhaseTransitionError: If transition is not allowed
        """
        # Define allowed phase transitions
        allowed_transitions: dict[str, set[str]] = {
            "pending": {"in_progress", "skipped"},
            "in_progress": {"completed", "blocked"},
            "blocked": {"in_progress", "skipped"},
            "completed": set(),  # Final state for phase
            "skipped": set(),  # Final state for phase
        }

        allowed = allowed_transitions.get(from_status, set())
        if to_status not in allowed:
            logger.warning(
                "Validation failed: invalid phase transition",
                extra={
                    "phase": phase,
                    "from_status": from_status,
                    "to_status": to_status,
                    "allowed": list(allowed),
                },
            )
            raise InvalidPhaseTransitionError(
                phase=phase,
                from_status=from_status,
                to_status=to_status,
                reason=f"Allowed transitions from '{from_status}': {', '.join(sorted(allowed)) if allowed else 'none'}",
            )

    def _validate_pagination(self, limit: int, offset: int) -> None:
        """Validate pagination parameters.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Raises:
            ProjectValidationError: If parameters are invalid
        """
        if limit < 1:
            logger.warning(
                "Validation failed: invalid limit",
                extra={"field": "limit", "value": limit},
            )
            raise ProjectValidationError("limit", limit, "Limit must be at least 1")

        if limit > 1000:
            logger.warning(
                "Validation failed: limit too large",
                extra={"field": "limit", "value": limit, "max": 1000},
            )
            raise ProjectValidationError("limit", limit, "Limit cannot exceed 1000")

        if offset < 0:
            logger.warning(
                "Validation failed: invalid offset",
                extra={"field": "offset", "value": offset},
            )
            raise ProjectValidationError("offset", offset, "Offset cannot be negative")
