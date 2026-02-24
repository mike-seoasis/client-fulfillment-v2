"""ProjectRepository with CRUD operations.

Handles all database operations for Project entities.
Follows the layered architecture pattern: API -> Service -> Repository -> Database.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id) in all logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import db_logger, get_logger
from app.models.project import Project

logger = get_logger(__name__)


class ProjectRepository:
    """Repository for Project CRUD operations.

    All methods accept an AsyncSession and handle database operations
    with comprehensive logging as required.
    """

    TABLE_NAME = "projects"
    SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session
        logger.debug("ProjectRepository initialized")

    async def create(
        self,
        name: str,
        client_id: str,
        status: str = "active",
        phase_status: dict[str, Any] | None = None,
    ) -> Project:
        """Create a new project.

        Args:
            name: Project name
            client_id: Client identifier
            status: Project status (default: 'active')
            phase_status: Initial phase status dict (default: empty dict)

        Returns:
            Created Project instance

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Creating project",
            extra={
                "name": name,
                "client_id": client_id,
                "status": status,
            },
        )

        try:
            project = Project(
                name=name,
                client_id=client_id,
                status=status,
                phase_status=phase_status or {},
            )
            self.session.add(project)
            await self.session.flush()
            await self.session.refresh(project)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project created successfully",
                extra={
                    "project_id": project.id,
                    "name": name,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query="INSERT INTO projects",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return project

        except IntegrityError as e:
            logger.error(
                "Failed to create project - integrity error",
                extra={
                    "name": name,
                    "client_id": client_id,
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
                context=f"Creating project name={name}",
            )
            raise

    async def get_by_id(self, project_id: str) -> Project | None:
        """Get a project by ID.

        Args:
            project_id: UUID of the project

        Returns:
            Project instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching project by ID",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                select(Project).where(Project.id == project_id)
            )
            project = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project fetch completed",
                extra={
                    "project_id": project_id,
                    "found": project is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM projects WHERE id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return project

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch project by ID",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_client_id(self, client_id: str) -> list[Project]:
        """Get all projects for a client.

        Args:
            client_id: Client identifier

        Returns:
            List of Project instances

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching projects by client ID",
            extra={"client_id": client_id},
        )

        try:
            result = await self.session.execute(
                select(Project)
                .where(Project.client_id == client_id)
                .order_by(Project.created_at.desc())
            )
            projects = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Client projects fetch completed",
                extra={
                    "client_id": client_id,
                    "count": len(projects),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM projects WHERE client_id={client_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return projects

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch projects by client ID",
                extra={
                    "client_id": client_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_status(self, status: str) -> list[Project]:
        """Get all projects with a specific status.

        Args:
            status: Project status to filter by

        Returns:
            List of Project instances

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching projects by status",
            extra={"status": status},
        )

        try:
            result = await self.session.execute(
                select(Project)
                .where(Project.status == status)
                .order_by(Project.created_at.desc())
            )
            projects = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Status projects fetch completed",
                extra={
                    "status": status,
                    "count": len(projects),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM projects WHERE status={status}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return projects

        except SQLAlchemyError as e:
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

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Project]:
        """List all projects with pagination.

        Args:
            limit: Maximum number of projects to return (default: 100)
            offset: Number of projects to skip (default: 0)

        Returns:
            List of Project instances

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Listing projects",
            extra={"limit": limit, "offset": offset},
        )

        try:
            result = await self.session.execute(
                select(Project)
                .order_by(Project.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            projects = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project list completed",
                extra={
                    "count": len(projects),
                    "limit": limit,
                    "offset": offset,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM projects LIMIT {limit} OFFSET {offset}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return projects

        except SQLAlchemyError as e:
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

    async def update(
        self,
        project_id: str,
        name: str | None = None,
        status: str | None = None,
        phase_status: dict[str, Any] | None = None,
    ) -> Project | None:
        """Update a project.

        Args:
            project_id: UUID of the project to update
            name: New name (optional)
            status: New status (optional)
            phase_status: New phase status dict (optional)

        Returns:
            Updated Project instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()

        # Build update dict with only provided values
        update_values: dict[str, Any] = {}
        if name is not None:
            update_values["name"] = name
        if status is not None:
            update_values["status"] = status
        if phase_status is not None:
            update_values["phase_status"] = phase_status

        if not update_values:
            logger.debug(
                "No update values provided, returning existing project",
                extra={"project_id": project_id},
            )
            return await self.get_by_id(project_id)

        logger.debug(
            "Updating project",
            extra={
                "project_id": project_id,
                "update_fields": list(update_values.keys()),
            },
        )

        # Get current project to log state transitions
        current_project = await self.get_by_id(project_id)
        if current_project is None:
            logger.debug(
                "Project not found for update",
                extra={"project_id": project_id},
            )
            return None

        try:
            # Log status transition if applicable
            if status is not None and current_project.status != status:
                logger.info(
                    "Project status transition",
                    extra={
                        "project_id": project_id,
                        "from_status": current_project.status,
                        "to_status": status,
                    },
                )

            # Log phase status changes if applicable
            if phase_status is not None:
                self._log_phase_status_changes(
                    project_id,
                    current_project.phase_status,
                    phase_status,
                )

            await self.session.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(**update_values)
            )
            await self.session.flush()

            # Refresh to get updated values
            updated_project = await self.get_by_id(project_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project updated successfully",
                extra={
                    "project_id": project_id,
                    "update_fields": list(update_values.keys()),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"UPDATE projects WHERE id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return updated_project

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating project_id={project_id}",
            )
            raise

    async def update_phase_status(
        self,
        project_id: str,
        phase: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> Project | None:
        """Update a specific phase's status.

        This is a convenience method for updating individual phase statuses
        without replacing the entire phase_status dict.

        Args:
            project_id: UUID of the project
            phase: Phase name (e.g., 'discovery', 'requirements')
            status: New status for the phase
            metadata: Additional phase metadata (optional)

        Returns:
            Updated Project instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Updating project phase status",
            extra={
                "project_id": project_id,
                "phase": phase,
                "status": status,
            },
        )

        try:
            project = await self.get_by_id(project_id)
            if project is None:
                logger.debug(
                    "Project not found for phase status update",
                    extra={"project_id": project_id},
                )
                return None

            # Get current phase status
            current_phase_status = project.phase_status.copy()
            old_phase_data = current_phase_status.get(phase, {})
            old_status = old_phase_data.get("status") if old_phase_data else None

            # Build new phase data
            new_phase_data: dict[str, Any] = {"status": status}
            if metadata:
                new_phase_data.update(metadata)

            # Log phase transition
            if old_status != status:
                logger.info(
                    "Project phase status transition",
                    extra={
                        "project_id": project_id,
                        "phase": phase,
                        "from_status": old_status or "unset",
                        "to_status": status,
                    },
                )

            # Update phase status
            current_phase_status[phase] = new_phase_data

            await self.session.execute(
                update(Project)
                .where(Project.id == project_id)
                .values(phase_status=current_phase_status)
            )
            await self.session.flush()

            updated_project = await self.get_by_id(project_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Phase status updated successfully",
                extra={
                    "project_id": project_id,
                    "phase": phase,
                    "status": status,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"UPDATE projects phase_status WHERE id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return updated_project

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating phase_status for project_id={project_id}, phase={phase}",
            )
            raise

    async def delete(self, project_id: str) -> bool:
        """Delete a project.

        Args:
            project_id: UUID of the project to delete

        Returns:
            True if project was deleted, False if not found

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting project",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                delete(Project).where(Project.id == project_id)
            )
            await self.session.flush()

            deleted = result.rowcount > 0

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project delete completed",
                extra={
                    "project_id": project_id,
                    "deleted": deleted,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"DELETE FROM projects WHERE id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return deleted

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting project_id={project_id}",
            )
            raise

    async def exists(self, project_id: str) -> bool:
        """Check if a project exists.

        Args:
            project_id: UUID of the project

        Returns:
            True if project exists, False otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Checking project existence",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                select(Project.id).where(Project.id == project_id)
            )
            exists = result.scalar_one_or_none() is not None

            logger.debug(
                "Project existence check completed",
                extra={
                    "project_id": project_id,
                    "exists": exists,
                },
            )

            return exists

        except SQLAlchemyError as e:
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

    async def count(self) -> int:
        """Count total number of projects.

        Returns:
            Total count of projects

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug("Counting projects")

        try:
            from sqlalchemy import func

            result = await self.session.execute(
                select(func.count()).select_from(Project)
            )
            count = result.scalar_one()

            logger.debug(
                "Project count completed",
                extra={"count": count},
            )

            return count

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count projects",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def count_by_status(self, status: str) -> int:
        """Count projects with a specific status.

        Args:
            status: Project status to count

        Returns:
            Count of projects with the given status

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Counting projects by status",
            extra={"status": status},
        )

        try:
            from sqlalchemy import func

            result = await self.session.execute(
                select(func.count())
                .select_from(Project)
                .where(Project.status == status)
            )
            count = result.scalar_one()

            logger.debug(
                "Project count by status completed",
                extra={
                    "status": status,
                    "count": count,
                },
            )

            return count

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count projects by status",
                extra={
                    "status": status,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    def _log_phase_status_changes(
        self,
        project_id: str,
        old_phase_status: dict[str, Any],
        new_phase_status: dict[str, Any],
    ) -> None:
        """Log changes to phase statuses.

        Args:
            project_id: Project UUID
            old_phase_status: Previous phase_status dict
            new_phase_status: New phase_status dict
        """
        all_phases = set(old_phase_status.keys()) | set(new_phase_status.keys())

        for phase in all_phases:
            old_data = old_phase_status.get(phase, {})
            new_data = new_phase_status.get(phase, {})

            old_status = old_data.get("status") if old_data else None
            new_status = new_data.get("status") if new_data else None

            if old_status != new_status:
                logger.info(
                    "Project phase status transition",
                    extra={
                        "project_id": project_id,
                        "phase": phase,
                        "from_status": old_status or "unset",
                        "to_status": new_status or "removed",
                    },
                )
