"""ScheduleService with validation logic.

Orchestrates business logic for CrawlSchedule entities between API layer and repository.
Handles validation, business rules, and logging as required.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, schedule_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (is_active changes) at INFO level
- Add timing logs for operations >1 second
"""

import re
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.crawl_schedule import CrawlSchedule
from app.repositories.schedule import ScheduleRepository
from app.schemas.schedule import (
    ScheduleConfigCreate,
    ScheduleConfigUpdate,
)

logger = get_logger(__name__)

# Threshold for logging slow operations
SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second


class ScheduleServiceError(Exception):
    """Base exception for ScheduleService errors."""

    pass


class ScheduleNotFoundError(ScheduleServiceError):
    """Raised when a schedule is not found."""

    def __init__(self, schedule_id: str):
        self.schedule_id = schedule_id
        super().__init__(f"Schedule not found: {schedule_id}")


class ScheduleValidationError(ScheduleServiceError):
    """Raised when schedule validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class ScheduleService:
    """Service for CrawlSchedule business logic and validation.

    Coordinates between API layer and repository, handling:
    - Input validation
    - Business rules
    - Logging requirements
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session
        self.repository = ScheduleRepository(session)
        logger.debug("ScheduleService initialized")

    async def create_schedule(
        self,
        project_id: str,
        data: ScheduleConfigCreate,
    ) -> CrawlSchedule:
        """Create a new schedule configuration.

        Args:
            project_id: UUID of the parent project
            data: Validated schedule creation data

        Returns:
            Created CrawlSchedule instance

        Raises:
            ScheduleValidationError: If validation fails
        """
        start_time = time.monotonic()
        logger.debug(
            "Creating schedule",
            extra={
                "project_id": project_id,
                "schedule_type": data.schedule_type,
                "start_url": data.start_url[:50] + "..." if len(data.start_url) > 50 else data.start_url,
            },
        )

        try:
            # Additional business validation
            self._validate_uuid(project_id, "project_id")
            self._validate_schedule_type_cron(data.schedule_type, data.cron_expression)

            schedule = await self.repository.create(
                project_id=project_id,
                schedule_type=data.schedule_type,
                start_url=data.start_url,
                cron_expression=data.cron_expression,
                max_pages=data.max_pages,
                max_depth=data.max_depth,
                config=data.config,
                is_active=data.is_active,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Schedule created successfully",
                extra={
                    "schedule_id": schedule.id,
                    "project_id": project_id,
                    "schedule_type": data.schedule_type,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow schedule creation",
                    extra={
                        "schedule_id": schedule.id,
                        "project_id": project_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return schedule

        except ScheduleServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to create schedule",
                extra={
                    "project_id": project_id,
                    "schedule_type": data.schedule_type,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_schedule(self, schedule_id: str) -> CrawlSchedule:
        """Get a schedule by ID.

        Args:
            schedule_id: UUID of the schedule

        Returns:
            CrawlSchedule instance

        Raises:
            ScheduleNotFoundError: If schedule is not found
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching schedule",
            extra={"schedule_id": schedule_id},
        )

        try:
            self._validate_uuid(schedule_id, "schedule_id")

            schedule = await self.repository.get_by_id(schedule_id)
            if schedule is None:
                logger.debug(
                    "Schedule not found",
                    extra={"schedule_id": schedule_id},
                )
                raise ScheduleNotFoundError(schedule_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Schedule fetched successfully",
                extra={
                    "schedule_id": schedule_id,
                    "project_id": schedule.project_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow schedule fetch",
                    extra={
                        "schedule_id": schedule_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return schedule

        except ScheduleServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to fetch schedule",
                extra={
                    "schedule_id": schedule_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_schedule_or_none(self, schedule_id: str) -> CrawlSchedule | None:
        """Get a schedule by ID, returning None if not found.

        Args:
            schedule_id: UUID of the schedule

        Returns:
            CrawlSchedule instance or None if not found
        """
        logger.debug(
            "Fetching schedule (nullable)",
            extra={"schedule_id": schedule_id},
        )

        try:
            self._validate_uuid(schedule_id, "schedule_id")
            return await self.repository.get_by_id(schedule_id)
        except ScheduleValidationError:
            return None
        except Exception as e:
            logger.error(
                "Failed to fetch schedule",
                extra={
                    "schedule_id": schedule_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def list_schedules(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CrawlSchedule], int]:
        """List all schedules for a project with pagination.

        Args:
            project_id: UUID of the project
            limit: Maximum number of schedules to return
            offset: Number of schedules to skip

        Returns:
            Tuple of (list of schedules, total count)

        Raises:
            ScheduleValidationError: If pagination params are invalid
        """
        start_time = time.monotonic()
        logger.debug(
            "Listing schedules",
            extra={
                "project_id": project_id,
                "limit": limit,
                "offset": offset,
            },
        )

        try:
            self._validate_uuid(project_id, "project_id")
            self._validate_pagination(limit, offset)

            schedules = await self.repository.get_by_project(
                project_id=project_id,
                limit=limit,
                offset=offset,
            )
            total = await self.repository.count_by_project(project_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Schedules listed",
                extra={
                    "project_id": project_id,
                    "count": len(schedules),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow schedule list",
                    extra={
                        "project_id": project_id,
                        "limit": limit,
                        "offset": offset,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return schedules, total

        except ScheduleServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to list schedules",
                extra={
                    "project_id": project_id,
                    "limit": limit,
                    "offset": offset,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update_schedule(
        self,
        schedule_id: str,
        data: ScheduleConfigUpdate,
    ) -> CrawlSchedule:
        """Update a schedule configuration.

        Args:
            schedule_id: UUID of the schedule to update
            data: Validated update data

        Returns:
            Updated CrawlSchedule instance

        Raises:
            ScheduleNotFoundError: If schedule is not found
            ScheduleValidationError: If validation fails
        """
        start_time = time.monotonic()
        logger.debug(
            "Updating schedule",
            extra={
                "schedule_id": schedule_id,
                "update_fields": [
                    k for k, v in data.model_dump().items() if v is not None
                ],
            },
        )

        try:
            self._validate_uuid(schedule_id, "schedule_id")

            # Verify schedule exists
            existing = await self.repository.get_by_id(schedule_id)
            if existing is None:
                raise ScheduleNotFoundError(schedule_id)

            # Validate schedule_type and cron_expression combination if either is being updated
            schedule_type = data.schedule_type or existing.schedule_type
            cron_expression = (
                data.cron_expression
                if data.cron_expression is not None
                else existing.cron_expression
            )
            if data.schedule_type is not None or data.cron_expression is not None:
                self._validate_schedule_type_cron(schedule_type, cron_expression)

            # Log is_active transition if applicable
            if data.is_active is not None and data.is_active != existing.is_active:
                logger.info(
                    "Schedule activation state transition",
                    extra={
                        "schedule_id": schedule_id,
                        "project_id": existing.project_id,
                        "from_active": existing.is_active,
                        "to_active": data.is_active,
                    },
                )

            schedule = await self.repository.update(
                schedule_id=schedule_id,
                schedule_type=data.schedule_type,
                cron_expression=data.cron_expression,
                start_url=data.start_url,
                max_pages=data.max_pages,
                max_depth=data.max_depth,
                config=data.config,
                is_active=data.is_active,
            )

            if schedule is None:
                raise ScheduleNotFoundError(schedule_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Schedule updated successfully",
                extra={
                    "schedule_id": schedule_id,
                    "project_id": schedule.project_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow schedule update",
                    extra={
                        "schedule_id": schedule_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return schedule

        except ScheduleServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to update schedule",
                extra={
                    "schedule_id": schedule_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule configuration.

        Args:
            schedule_id: UUID of the schedule to delete

        Returns:
            True if schedule was deleted

        Raises:
            ScheduleNotFoundError: If schedule is not found
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting schedule",
            extra={"schedule_id": schedule_id},
        )

        try:
            self._validate_uuid(schedule_id, "schedule_id")

            deleted = await self.repository.delete(schedule_id)
            if not deleted:
                raise ScheduleNotFoundError(schedule_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Schedule deleted successfully",
                extra={
                    "schedule_id": schedule_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow schedule delete",
                    extra={
                        "schedule_id": schedule_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return True

        except ScheduleServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to delete schedule",
                extra={
                    "schedule_id": schedule_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def schedule_exists(self, schedule_id: str) -> bool:
        """Check if a schedule exists.

        Args:
            schedule_id: UUID of the schedule

        Returns:
            True if schedule exists
        """
        logger.debug(
            "Checking schedule existence",
            extra={"schedule_id": schedule_id},
        )

        try:
            self._validate_uuid(schedule_id, "schedule_id")
            return await self.repository.exists(schedule_id)
        except ScheduleValidationError:
            return False
        except Exception as e:
            logger.error(
                "Failed to check schedule existence",
                extra={
                    "schedule_id": schedule_id,
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
            ScheduleValidationError: If value is not a valid UUID
        """
        if not value or not isinstance(value, str):
            logger.warning(
                "Validation failed: empty or invalid UUID",
                extra={"field": field, "value": value},
            )
            raise ScheduleValidationError(field, value, "UUID is required")

        # Basic UUID format check (36 chars with hyphens)
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(value):
            logger.warning(
                "Validation failed: invalid UUID format",
                extra={"field": field, "value": value},
            )
            raise ScheduleValidationError(field, value, "Invalid UUID format")

    def _validate_schedule_type_cron(
        self,
        schedule_type: str,
        cron_expression: str | None,
    ) -> None:
        """Validate schedule_type and cron_expression consistency.

        Args:
            schedule_type: Type of schedule
            cron_expression: Cron expression (required if type is 'cron')

        Raises:
            ScheduleValidationError: If validation fails
        """
        if schedule_type == "cron" and not cron_expression:
            logger.warning(
                "Validation failed: cron schedule requires cron_expression",
                extra={
                    "field": "cron_expression",
                    "schedule_type": schedule_type,
                },
            )
            raise ScheduleValidationError(
                "cron_expression",
                None,
                "cron_expression is required when schedule_type is 'cron'",
            )

        if schedule_type != "cron" and cron_expression:
            logger.warning(
                "Validation failed: cron_expression provided for non-cron schedule",
                extra={
                    "field": "cron_expression",
                    "schedule_type": schedule_type,
                    "cron_expression": cron_expression,
                },
            )
            raise ScheduleValidationError(
                "cron_expression",
                cron_expression,
                f"cron_expression should only be provided when schedule_type is 'cron', not '{schedule_type}'",
            )

    def _validate_pagination(self, limit: int, offset: int) -> None:
        """Validate pagination parameters.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Raises:
            ScheduleValidationError: If parameters are invalid
        """
        if limit < 1:
            logger.warning(
                "Validation failed: invalid limit",
                extra={"field": "limit", "value": limit},
            )
            raise ScheduleValidationError("limit", limit, "Limit must be at least 1")

        if limit > 1000:
            logger.warning(
                "Validation failed: limit too large",
                extra={"field": "limit", "value": limit, "max": 1000},
            )
            raise ScheduleValidationError("limit", limit, "Limit cannot exceed 1000")

        if offset < 0:
            logger.warning(
                "Validation failed: invalid offset",
                extra={"field": "offset", "value": offset},
            )
            raise ScheduleValidationError("offset", offset, "Offset cannot be negative")
