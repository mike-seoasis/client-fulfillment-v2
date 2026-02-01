"""APScheduler configuration with SQLAlchemy job store.

Features:
- PostgreSQL job persistence via SQLAlchemy job store
- Automatic connection recovery (Railway cold-starts)
- Comprehensive logging for all scheduler events
- Graceful shutdown handling
- Health checking

ERROR LOGGING REQUIREMENTS:
- Log all database connection errors with connection string (masked)
- Log job execution errors with full context
- Log slow job executions (>1 second) at WARNING level
- Log missed job executions at WARNING level
- Log scheduler lifecycle events at INFO level
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from apscheduler.events import (
    EVENT_JOB_ADDED,
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MAX_INSTANCES,
    EVENT_JOB_MISSED,
    EVENT_JOB_MODIFIED,
    EVENT_JOB_REMOVED,
    EVENT_SCHEDULER_PAUSED,
    EVENT_SCHEDULER_RESUMED,
    EVENT_SCHEDULER_SHUTDOWN,
    EVENT_SCHEDULER_STARTED,
    JobEvent,
    JobExecutionEvent,
    SchedulerEvent,
)
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import get_logger, scheduler_logger

logger = get_logger(__name__)

# Slow job threshold in milliseconds
SLOW_JOB_THRESHOLD_MS = 1000


class SchedulerState(Enum):
    """Scheduler state enumeration."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"


@dataclass
class JobInfo:
    """Information about a scheduled job."""

    id: str
    name: str | None
    trigger: str
    next_run_time: datetime | None
    pending: bool


class SchedulerServiceError(Exception):
    """Base exception for scheduler service errors."""

    pass


class SchedulerNotRunningError(SchedulerServiceError):
    """Raised when scheduler is not running."""

    pass


class JobNotFoundError(SchedulerServiceError):
    """Raised when a job is not found."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        super().__init__(f"Job not found: {job_id}")


class SchedulerManager:
    """Manages APScheduler with SQLAlchemy job store.

    This class provides a singleton pattern for managing the application's
    background scheduler. It uses PostgreSQL for job persistence and
    provides comprehensive logging for all scheduler events.
    """

    def __init__(self) -> None:
        self._scheduler: BackgroundScheduler | None = None
        self._state: SchedulerState = SchedulerState.STOPPED
        self._job_start_times: dict[str, float] = {}

    @property
    def state(self) -> SchedulerState:
        """Get current scheduler state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._state == SchedulerState.RUNNING

    def _get_db_url(self) -> str:
        """Get synchronous database URL for APScheduler.

        APScheduler's SQLAlchemyJobStore uses synchronous SQLAlchemy,
        so we need to convert the async URL to a sync one.
        """
        settings = get_settings()
        db_url = str(settings.database_url)

        # APScheduler uses sync SQLAlchemy, so use psycopg2 driver
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        elif db_url.startswith("postgresql+asyncpg://"):
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)

        # Add sslmode=require if not present (Railway requires SSL)
        if "sslmode=" not in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{separator}sslmode=require"

        return db_url

    def _setup_event_listeners(self, scheduler: BackgroundScheduler) -> None:
        """Set up event listeners for scheduler events."""

        def on_scheduler_event(event: SchedulerEvent) -> None:
            """Handle scheduler lifecycle events."""
            if event.code == EVENT_SCHEDULER_STARTED:
                job_count = len(scheduler.get_jobs())
                scheduler_logger.scheduler_start(job_count)
            elif event.code == EVENT_SCHEDULER_SHUTDOWN:
                scheduler_logger.scheduler_stop(graceful=True)
            elif event.code == EVENT_SCHEDULER_PAUSED:
                scheduler_logger.scheduler_pause()
            elif event.code == EVENT_SCHEDULER_RESUMED:
                scheduler_logger.scheduler_resume()

        def on_job_event(event: JobEvent) -> None:
            """Handle job lifecycle events."""
            job = scheduler.get_job(event.job_id)
            job_name = job.name if job else None
            trigger_str = str(job.trigger) if job else "unknown"

            if event.code == EVENT_JOB_ADDED:
                next_run = (
                    job.next_run_time.isoformat() if job and job.next_run_time else None
                )
                scheduler_logger.job_added(
                    job_id=event.job_id,
                    job_name=job_name,
                    trigger=trigger_str,
                    next_run=next_run,
                )
            elif event.code == EVENT_JOB_REMOVED:
                scheduler_logger.job_removed(
                    job_id=event.job_id,
                    job_name=job_name,
                )
            elif event.code == EVENT_JOB_MODIFIED:
                scheduler_logger.job_modified(
                    job_id=event.job_id,
                    job_name=job_name,
                )

        def on_job_execution_event(event: JobExecutionEvent) -> None:
            """Handle job execution events."""
            job = scheduler.get_job(event.job_id)
            job_name = job.name if job else None

            # Calculate duration from stored start time
            start_time = self._job_start_times.pop(event.job_id, None)
            duration_ms = (time.monotonic() - start_time) * 1000 if start_time else 0

            if event.code == EVENT_JOB_EXECUTED:
                scheduler_logger.job_execution_success(
                    job_id=event.job_id,
                    job_name=job_name,
                    duration_ms=duration_ms,
                    result=event.retval,
                )
                # Log slow job executions
                if duration_ms > SLOW_JOB_THRESHOLD_MS:
                    scheduler_logger.slow_job_execution(
                        job_id=event.job_id,
                        job_name=job_name,
                        duration_ms=duration_ms,
                        threshold_ms=SLOW_JOB_THRESHOLD_MS,
                    )
            elif event.code == EVENT_JOB_ERROR:
                scheduler_logger.job_execution_error(
                    job_id=event.job_id,
                    job_name=job_name,
                    duration_ms=duration_ms,
                    error=str(event.exception),
                    error_type=type(event.exception).__name__,
                )
            elif event.code == EVENT_JOB_MISSED:
                settings = get_settings()
                scheduled_time = (
                    event.scheduled_run_time.isoformat()
                    if event.scheduled_run_time
                    else "unknown"
                )
                scheduler_logger.job_missed(
                    job_id=event.job_id,
                    job_name=job_name,
                    scheduled_time=scheduled_time,
                    misfire_grace_time=settings.scheduler_misfire_grace_time,
                )
            elif event.code == EVENT_JOB_MAX_INSTANCES:
                max_instances = job.max_instances if job else 1
                scheduler_logger.job_max_instances_reached(
                    job_id=event.job_id,
                    job_name=job_name,
                    max_instances=max_instances,
                )

        # Register event listeners
        scheduler.add_listener(
            on_scheduler_event,
            EVENT_SCHEDULER_STARTED
            | EVENT_SCHEDULER_SHUTDOWN
            | EVENT_SCHEDULER_PAUSED
            | EVENT_SCHEDULER_RESUMED,
        )
        scheduler.add_listener(
            on_job_event,
            EVENT_JOB_ADDED | EVENT_JOB_REMOVED | EVENT_JOB_MODIFIED,
        )
        scheduler.add_listener(
            on_job_execution_event,
            EVENT_JOB_EXECUTED
            | EVENT_JOB_ERROR
            | EVENT_JOB_MISSED
            | EVENT_JOB_MAX_INSTANCES,
        )

    def init_scheduler(self) -> bool:
        """Initialize the scheduler with SQLAlchemy job store.

        Returns:
            True if initialization was successful, False otherwise.
        """
        settings = get_settings()

        if not settings.scheduler_enabled:
            logger.info("Scheduler is disabled via configuration")
            return False

        if self._scheduler is not None:
            logger.warning("Scheduler already initialized")
            return True

        self._state = SchedulerState.STARTING

        try:
            db_url = self._get_db_url()

            # Configure job stores
            jobstores = {
                "default": SQLAlchemyJobStore(
                    url=db_url,
                    tablename="apscheduler_jobs",
                )
            }

            # Configure executors
            executors = {
                "default": ThreadPoolExecutor(max_workers=10),
            }

            # Configure job defaults
            job_defaults = {
                "coalesce": settings.scheduler_job_coalesce,
                "max_instances": settings.scheduler_job_default_max_instances,
                "misfire_grace_time": settings.scheduler_misfire_grace_time,
            }

            # Create scheduler
            self._scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone="UTC",
            )

            # Set up event listeners
            self._setup_event_listeners(self._scheduler)

            logger.info("Scheduler initialized successfully")
            return True

        except Exception as e:
            self._state = SchedulerState.STOPPED
            scheduler_logger.jobstore_connection_error(
                store_name="default",
                error=str(e),
                error_type=type(e).__name__,
                connection_string=self._get_db_url(),
            )
            logger.error(f"Failed to initialize scheduler: {e}", exc_info=True)
            return False

    def start(self) -> bool:
        """Start the scheduler.

        Returns:
            True if started successfully, False otherwise.
        """
        if self._scheduler is None and not self.init_scheduler():
            return False

        if self._scheduler is None:
            return False

        if self._state == SchedulerState.RUNNING:
            logger.warning("Scheduler is already running")
            return True

        try:
            self._scheduler.start()
            self._state = SchedulerState.RUNNING
            return True
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}", exc_info=True)
            self._state = SchedulerState.STOPPED
            return False

    def stop(self, wait: bool = True) -> None:
        """Stop the scheduler.

        Args:
            wait: If True, wait for running jobs to complete.
        """
        if self._scheduler is None:
            return

        if self._state in (SchedulerState.STOPPED, SchedulerState.SHUTTING_DOWN):
            return

        self._state = SchedulerState.SHUTTING_DOWN

        try:
            self._scheduler.shutdown(wait=wait)
            self._state = SchedulerState.STOPPED
            self._scheduler = None
        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {e}", exc_info=True)
            self._state = SchedulerState.STOPPED
            self._scheduler = None

    def pause(self) -> None:
        """Pause the scheduler (stop processing jobs)."""
        if self._scheduler is None or self._state != SchedulerState.RUNNING:
            scheduler_logger.scheduler_not_available(
                operation="pause",
                reason="Scheduler is not running",
            )
            return

        self._scheduler.pause()
        self._state = SchedulerState.PAUSED

    def resume(self) -> None:
        """Resume the scheduler (continue processing jobs)."""
        if self._scheduler is None or self._state != SchedulerState.PAUSED:
            scheduler_logger.scheduler_not_available(
                operation="resume",
                reason="Scheduler is not paused",
            )
            return

        self._scheduler.resume()
        self._state = SchedulerState.RUNNING

    def add_job(
        self,
        func: Callable[..., Any],
        trigger: str = "interval",
        id: str | None = None,
        name: str | None = None,
        replace_existing: bool = True,
        **trigger_args: Any,
    ) -> str | None:
        """Add a job to the scheduler.

        Args:
            func: The function to execute.
            trigger: Trigger type ('interval', 'cron', 'date').
            id: Unique job ID.
            name: Human-readable job name.
            replace_existing: If True, replace existing job with same ID.
            **trigger_args: Arguments for the trigger (e.g., seconds=30, cron='0 * * * *').

        Returns:
            Job ID if successful, None otherwise.
        """
        if self._scheduler is None:
            scheduler_logger.scheduler_not_available(
                operation="add_job",
                reason="Scheduler is not initialized",
            )
            return None

        try:
            # Create appropriate trigger
            trigger_obj: CronTrigger | IntervalTrigger | DateTrigger
            if trigger == "cron":
                # Handle cron expression or individual cron fields
                if "cron" in trigger_args:
                    trigger_obj = CronTrigger.from_crontab(trigger_args.pop("cron"))
                else:
                    trigger_obj = CronTrigger(**trigger_args)
            elif trigger == "date":
                trigger_obj = DateTrigger(**trigger_args)
            else:  # interval
                trigger_obj = IntervalTrigger(**trigger_args)

            job = self._scheduler.add_job(
                func,
                trigger=trigger_obj,
                id=id,
                name=name,
                replace_existing=replace_existing,
            )

            # Store start time tracking for this job
            job_id: str = str(job.id)
            self._job_start_times[job_id] = time.monotonic()

            return job_id

        except Exception as e:
            logger.error(f"Failed to add job: {e}", exc_info=True)
            return None

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the scheduler.

        Args:
            job_id: The ID of the job to remove.

        Returns:
            True if removed successfully, False otherwise.
        """
        if self._scheduler is None:
            scheduler_logger.scheduler_not_available(
                operation="remove_job",
                reason="Scheduler is not initialized",
            )
            return False

        try:
            self._scheduler.remove_job(job_id)
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}", exc_info=True)
            return False

    def get_job(self, job_id: str) -> JobInfo | None:
        """Get information about a specific job.

        Args:
            job_id: The ID of the job.

        Returns:
            JobInfo if found, None otherwise.
        """
        if self._scheduler is None:
            return None

        job = self._scheduler.get_job(job_id)
        if job is None:
            return None

        return JobInfo(
            id=job.id,
            name=job.name,
            trigger=str(job.trigger),
            next_run_time=job.next_run_time,
            pending=job.pending,
        )

    def get_jobs(self) -> list[JobInfo]:
        """Get all scheduled jobs.

        Returns:
            List of JobInfo objects.
        """
        if self._scheduler is None:
            return []

        return [
            JobInfo(
                id=job.id,
                name=job.name,
                trigger=str(job.trigger),
                next_run_time=job.next_run_time,
                pending=job.pending,
            )
            for job in self._scheduler.get_jobs()
        ]

    def reschedule_job(
        self,
        job_id: str,
        trigger: str = "interval",
        **trigger_args: Any,
    ) -> bool:
        """Reschedule an existing job with a new trigger.

        Args:
            job_id: The ID of the job to reschedule.
            trigger: New trigger type.
            **trigger_args: Arguments for the new trigger.

        Returns:
            True if rescheduled successfully, False otherwise.
        """
        if self._scheduler is None:
            scheduler_logger.scheduler_not_available(
                operation="reschedule_job",
                reason="Scheduler is not initialized",
            )
            return False

        try:
            # Create appropriate trigger
            trigger_obj: CronTrigger | IntervalTrigger | DateTrigger
            if trigger == "cron":
                if "cron" in trigger_args:
                    trigger_obj = CronTrigger.from_crontab(trigger_args.pop("cron"))
                else:
                    trigger_obj = CronTrigger(**trigger_args)
            elif trigger == "date":
                trigger_obj = DateTrigger(**trigger_args)
            else:
                trigger_obj = IntervalTrigger(**trigger_args)

            self._scheduler.reschedule_job(job_id, trigger=trigger_obj)
            return True

        except Exception as e:
            logger.error(f"Failed to reschedule job {job_id}: {e}", exc_info=True)
            return False

    def run_job_now(self, job_id: str) -> bool:
        """Run a job immediately.

        Args:
            job_id: The ID of the job to run.

        Returns:
            True if job was triggered, False otherwise.
        """
        if self._scheduler is None:
            scheduler_logger.scheduler_not_available(
                operation="run_job_now",
                reason="Scheduler is not initialized",
            )
            return False

        job = self._scheduler.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id)

        try:
            # Store start time for this execution
            self._job_start_times[job_id] = time.monotonic()
            job.modify(next_run_time=datetime.now(job.trigger.timezone))
            return True
        except Exception as e:
            logger.error(f"Failed to run job {job_id}: {e}", exc_info=True)
            return False

    def check_health(self) -> dict[str, Any]:
        """Check scheduler health.

        Returns:
            Health status dictionary.
        """
        if self._scheduler is None:
            return {
                "status": "not_initialized",
                "running": False,
                "state": self._state.value,
                "job_count": 0,
            }

        jobs = self._scheduler.get_jobs()
        pending_jobs = [j for j in jobs if j.pending]

        return {
            "status": "ok" if self._state == SchedulerState.RUNNING else "degraded",
            "running": self._state == SchedulerState.RUNNING,
            "state": self._state.value,
            "job_count": len(jobs),
            "pending_jobs": len(pending_jobs),
        }


# Global scheduler manager instance
scheduler_manager = SchedulerManager()


def get_scheduler() -> SchedulerManager:
    """Get the scheduler manager instance.

    Usage:
        scheduler = get_scheduler()
        scheduler.add_job(my_func, trigger="interval", seconds=60)
    """
    return scheduler_manager
