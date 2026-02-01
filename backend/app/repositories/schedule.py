"""ScheduleRepository with CRUD operations.

Handles all database operations for CrawlSchedule entities.
Follows the layered architecture pattern: API -> Service -> Repository -> Database.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, schedule_id) in all logs
- Log validation failures with field names and rejected values
- Log state transitions (is_active changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import db_logger, get_logger
from app.models.crawl_schedule import CrawlSchedule

logger = get_logger(__name__)


class ScheduleRepository:
    """Repository for CrawlSchedule CRUD operations.

    All methods accept an AsyncSession and handle database operations
    with comprehensive logging as required.
    """

    TABLE_NAME = "crawl_schedules"
    SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session
        logger.debug("ScheduleRepository initialized")

    async def create(
        self,
        project_id: str,
        schedule_type: str,
        start_url: str,
        cron_expression: str | None = None,
        max_pages: int | None = None,
        max_depth: int | None = None,
        config: dict[str, Any] | None = None,
        is_active: bool = True,
    ) -> CrawlSchedule:
        """Create a new schedule configuration.

        Args:
            project_id: UUID of the parent project
            schedule_type: Type of schedule (manual, daily, weekly, monthly, cron)
            start_url: URL to start crawling from
            cron_expression: Cron expression for custom schedules
            max_pages: Maximum pages to crawl per run
            max_depth: Maximum crawl depth
            config: Additional configuration (selectors, patterns, etc.)
            is_active: Whether the schedule is active

        Returns:
            Created CrawlSchedule instance

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Creating schedule",
            extra={
                "project_id": project_id,
                "schedule_type": schedule_type,
                "start_url": start_url[:50] + "..." if len(start_url) > 50 else start_url,
                "is_active": is_active,
            },
        )

        try:
            schedule = CrawlSchedule(
                project_id=project_id,
                schedule_type=schedule_type,
                start_url=start_url,
                cron_expression=cron_expression,
                max_pages=max_pages,
                max_depth=max_depth,
                config=config or {},
                is_active=is_active,
            )
            self.session.add(schedule)
            await self.session.flush()
            await self.session.refresh(schedule)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Schedule created successfully",
                extra={
                    "schedule_id": schedule.id,
                    "project_id": project_id,
                    "schedule_type": schedule_type,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query="INSERT INTO crawl_schedules",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return schedule

        except IntegrityError as e:
            logger.error(
                "Failed to create schedule - integrity error",
                extra={
                    "project_id": project_id,
                    "schedule_type": schedule_type,
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
                context=f"Creating schedule for project_id={project_id}",
            )
            raise

    async def get_by_id(self, schedule_id: str) -> CrawlSchedule | None:
        """Get a schedule by ID.

        Args:
            schedule_id: UUID of the schedule

        Returns:
            CrawlSchedule instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching schedule by ID",
            extra={"schedule_id": schedule_id},
        )

        try:
            result = await self.session.execute(
                select(CrawlSchedule).where(CrawlSchedule.id == schedule_id)
            )
            schedule = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Schedule fetch completed",
                extra={
                    "schedule_id": schedule_id,
                    "found": schedule is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM crawl_schedules WHERE id={schedule_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return schedule

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch schedule by ID",
                extra={
                    "schedule_id": schedule_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_project(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CrawlSchedule]:
        """Get all schedules for a project with pagination.

        Args:
            project_id: UUID of the project
            limit: Maximum number of schedules to return
            offset: Number of schedules to skip

        Returns:
            List of CrawlSchedule instances

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching schedules by project",
            extra={
                "project_id": project_id,
                "limit": limit,
                "offset": offset,
            },
        )

        try:
            result = await self.session.execute(
                select(CrawlSchedule)
                .where(CrawlSchedule.project_id == project_id)
                .order_by(CrawlSchedule.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            schedules = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project schedules fetch completed",
                extra={
                    "project_id": project_id,
                    "count": len(schedules),
                    "limit": limit,
                    "offset": offset,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM crawl_schedules WHERE project_id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return schedules

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch schedules by project",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update(
        self,
        schedule_id: str,
        schedule_type: str | None = None,
        cron_expression: str | None = None,
        start_url: str | None = None,
        max_pages: int | None = None,
        max_depth: int | None = None,
        config: dict[str, Any] | None = None,
        is_active: bool | None = None,
        last_run_at: datetime | None = None,
        next_run_at: datetime | None = None,
    ) -> CrawlSchedule | None:
        """Update a schedule configuration.

        Args:
            schedule_id: UUID of the schedule to update
            schedule_type: New schedule type
            cron_expression: New cron expression
            start_url: New start URL
            max_pages: New max pages
            max_depth: New max depth
            config: New config dict
            is_active: New active status
            last_run_at: Update last run timestamp
            next_run_at: Update next run timestamp

        Returns:
            Updated CrawlSchedule instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()

        # Build update dict with only provided values
        update_values: dict[str, Any] = {}
        if schedule_type is not None:
            update_values["schedule_type"] = schedule_type
        if cron_expression is not None:
            update_values["cron_expression"] = cron_expression
        if start_url is not None:
            update_values["start_url"] = start_url
        if max_pages is not None:
            update_values["max_pages"] = max_pages
        if max_depth is not None:
            update_values["max_depth"] = max_depth
        if config is not None:
            update_values["config"] = config
        if is_active is not None:
            update_values["is_active"] = is_active
        if last_run_at is not None:
            update_values["last_run_at"] = last_run_at
        if next_run_at is not None:
            update_values["next_run_at"] = next_run_at

        if not update_values:
            logger.debug(
                "No update values provided, returning existing schedule",
                extra={"schedule_id": schedule_id},
            )
            return await self.get_by_id(schedule_id)

        logger.debug(
            "Updating schedule",
            extra={
                "schedule_id": schedule_id,
                "update_fields": list(update_values.keys()),
            },
        )

        # Get current schedule to log state transitions
        current_schedule = await self.get_by_id(schedule_id)
        if current_schedule is None:
            logger.debug(
                "Schedule not found for update",
                extra={"schedule_id": schedule_id},
            )
            return None

        try:
            # Log is_active transition if applicable
            if is_active is not None and current_schedule.is_active != is_active:
                logger.info(
                    "Schedule activation state transition",
                    extra={
                        "schedule_id": schedule_id,
                        "project_id": current_schedule.project_id,
                        "from_active": current_schedule.is_active,
                        "to_active": is_active,
                    },
                )

            await self.session.execute(
                update(CrawlSchedule)
                .where(CrawlSchedule.id == schedule_id)
                .values(**update_values)
            )
            await self.session.flush()

            # Refresh to get updated values
            updated_schedule = await self.get_by_id(schedule_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Schedule updated successfully",
                extra={
                    "schedule_id": schedule_id,
                    "update_fields": list(update_values.keys()),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"UPDATE crawl_schedules WHERE id={schedule_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return updated_schedule

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating schedule_id={schedule_id}",
            )
            raise

    async def delete(self, schedule_id: str) -> bool:
        """Delete a schedule configuration.

        Args:
            schedule_id: UUID of the schedule to delete

        Returns:
            True if schedule was deleted, False if not found

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting schedule",
            extra={"schedule_id": schedule_id},
        )

        try:
            result = await self.session.execute(
                delete(CrawlSchedule).where(CrawlSchedule.id == schedule_id)
            )
            await self.session.flush()

            deleted = result.rowcount > 0

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Schedule delete completed",
                extra={
                    "schedule_id": schedule_id,
                    "deleted": deleted,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"DELETE FROM crawl_schedules WHERE id={schedule_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return deleted

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting schedule_id={schedule_id}",
            )
            raise

    async def delete_by_project(self, project_id: str) -> int:
        """Delete all schedules for a project.

        Args:
            project_id: UUID of the project

        Returns:
            Number of schedules deleted

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting schedules by project",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                delete(CrawlSchedule).where(CrawlSchedule.project_id == project_id)
            )
            await self.session.flush()

            deleted_count = result.rowcount

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project schedules delete completed",
                extra={
                    "project_id": project_id,
                    "deleted_count": deleted_count,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"DELETE FROM crawl_schedules WHERE project_id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return deleted_count

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting schedules for project_id={project_id}",
            )
            raise

    async def exists(self, schedule_id: str) -> bool:
        """Check if a schedule exists.

        Args:
            schedule_id: UUID of the schedule

        Returns:
            True if schedule exists, False otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Checking schedule existence",
            extra={"schedule_id": schedule_id},
        )

        try:
            result = await self.session.execute(
                select(CrawlSchedule.id).where(CrawlSchedule.id == schedule_id)
            )
            exists = result.scalar_one_or_none() is not None

            logger.debug(
                "Schedule existence check completed",
                extra={
                    "schedule_id": schedule_id,
                    "exists": exists,
                },
            )

            return exists

        except SQLAlchemyError as e:
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

    async def count_by_project(self, project_id: str) -> int:
        """Count schedules for a project.

        Args:
            project_id: UUID of the project

        Returns:
            Count of schedules for the project

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Counting schedules by project",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                select(func.count())
                .select_from(CrawlSchedule)
                .where(CrawlSchedule.project_id == project_id)
            )
            count = result.scalar_one()

            logger.debug(
                "Schedule count by project completed",
                extra={
                    "project_id": project_id,
                    "count": count,
                },
            )

            return count

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count schedules by project",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_active_schedules(self) -> list[CrawlSchedule]:
        """Get all active schedules across all projects.

        Returns:
            List of active CrawlSchedule instances

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug("Fetching all active schedules")

        try:
            result = await self.session.execute(
                select(CrawlSchedule)
                .where(CrawlSchedule.is_active.is_(True))
                .order_by(CrawlSchedule.next_run_at.asc().nulls_last())
            )
            schedules = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Active schedules fetch completed",
                extra={
                    "count": len(schedules),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query="SELECT FROM crawl_schedules WHERE is_active=true",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return schedules

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch active schedules",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise
