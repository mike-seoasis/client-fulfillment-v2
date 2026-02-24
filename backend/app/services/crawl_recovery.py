"""Crawl Recovery Service for handling interrupted crawls on startup.

This service detects and recovers crawls that were interrupted due to:
- Server restarts/deployments
- Crashes
- Process termination

Recovery Strategy:
1. On startup, find crawls in 'running' or 'pending' state that appear abandoned
2. Mark them as 'interrupted' with metadata about the interruption
3. Optionally restart them (configurable behavior)

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, crawl_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.crawl_history import CrawlHistory

logger = get_logger(__name__)

# Threshold for logging slow operations
SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second

# Default timeout for considering a crawl as abandoned (in minutes)
DEFAULT_STALE_THRESHOLD_MINUTES = 5


@dataclass
class InterruptedCrawl:
    """Represents a crawl that was interrupted and needs recovery."""

    crawl_id: str
    project_id: str
    status: str
    started_at: datetime | None
    updated_at: datetime
    pages_crawled: int
    pages_failed: int
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryResult:
    """Result of a crawl recovery operation."""

    crawl_id: str
    project_id: str
    previous_status: str
    new_status: str
    action_taken: str
    recovered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None


@dataclass
class RecoverySummary:
    """Summary of all recovery operations performed on startup."""

    total_found: int = 0
    total_recovered: int = 0
    total_failed: int = 0
    results: list[RecoveryResult] = field(default_factory=list)
    duration_ms: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class CrawlRecoveryService:
    """Service for detecting and recovering interrupted crawls.

    This service should be called during application startup to handle
    any crawls that were left in an inconsistent state.

    Example usage:
        async with get_session() as session:
            service = CrawlRecoveryService(session)

            # Find interrupted crawls
            interrupted = await service.find_interrupted_crawls()

            # Recover all interrupted crawls
            summary = await service.recover_all_interrupted_crawls()

            # Or recover individually
            for crawl in interrupted:
                result = await service.recover_interrupted_crawl(crawl.crawl_id)
    """

    def __init__(
        self,
        session: AsyncSession,
        stale_threshold_minutes: int = DEFAULT_STALE_THRESHOLD_MINUTES,
    ) -> None:
        """Initialize CrawlRecoveryService.

        Args:
            session: Async SQLAlchemy session
            stale_threshold_minutes: Minutes after which a 'running' crawl
                                     is considered abandoned
        """
        self.session = session
        self.stale_threshold_minutes = stale_threshold_minutes
        logger.debug(
            "CrawlRecoveryService initialized",
            extra={"stale_threshold_minutes": stale_threshold_minutes},
        )

    async def find_interrupted_crawls(
        self,
        stale_threshold_minutes: int | None = None,
    ) -> list[InterruptedCrawl]:
        """Find crawls that appear to be interrupted/abandoned.

        A crawl is considered interrupted if:
        - Status is 'running' AND updated_at is older than stale_threshold
        - Status is 'pending' AND started_at is set but old (rare edge case)

        Args:
            stale_threshold_minutes: Override default threshold (optional)

        Returns:
            List of InterruptedCrawl objects
        """
        start_time = time.monotonic()
        threshold = stale_threshold_minutes or self.stale_threshold_minutes
        cutoff_time = datetime.now(UTC) - timedelta(minutes=threshold)

        logger.debug(
            "find_interrupted_crawls() called",
            extra={
                "stale_threshold_minutes": threshold,
                "cutoff_time": cutoff_time.isoformat(),
            },
        )

        try:
            # Query for crawls that appear abandoned
            # Status is 'running' and hasn't been updated recently
            stmt = (
                select(CrawlHistory)
                .where(
                    and_(
                        CrawlHistory.status.in_(["running", "pending"]),
                        CrawlHistory.updated_at < cutoff_time,
                    )
                )
                .order_by(CrawlHistory.updated_at.asc())
            )

            result = await self.session.execute(stmt)
            histories = list(result.scalars().all())

            interrupted: list[InterruptedCrawl] = []
            for history in histories:
                interrupted.append(
                    InterruptedCrawl(
                        crawl_id=history.id,
                        project_id=history.project_id,
                        status=history.status,
                        started_at=history.started_at,
                        updated_at=history.updated_at,
                        pages_crawled=history.pages_crawled,
                        pages_failed=history.pages_failed,
                        stats=history.stats or {},
                    )
                )

            duration_ms = (time.monotonic() - start_time) * 1000

            if interrupted:
                logger.info(
                    "Found interrupted crawls",
                    extra={
                        "count": len(interrupted),
                        "crawl_ids": [c.crawl_id for c in interrupted],
                        "duration_ms": round(duration_ms, 2),
                    },
                )
            else:
                logger.debug(
                    "No interrupted crawls found",
                    extra={"duration_ms": round(duration_ms, 2)},
                )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow interrupted crawls query",
                    extra={"duration_ms": round(duration_ms, 2)},
                )

            return interrupted

        except Exception as e:
            logger.error(
                "Failed to find interrupted crawls",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def recover_interrupted_crawl(
        self,
        crawl_id: str,
        mark_as_failed: bool = True,
    ) -> RecoveryResult:
        """Recover a single interrupted crawl.

        Recovery options:
        - mark_as_failed=True (default): Mark as 'failed' with interruption metadata
        - mark_as_failed=False: Mark as 'interrupted' status (requires status support)

        Args:
            crawl_id: UUID of the crawl to recover
            mark_as_failed: If True, mark as 'failed'; otherwise uses 'interrupted'

        Returns:
            RecoveryResult with details of the recovery action
        """
        start_time = time.monotonic()
        logger.debug(
            "recover_interrupted_crawl() called",
            extra={
                "crawl_id": crawl_id,
                "mark_as_failed": mark_as_failed,
            },
        )

        try:
            # Fetch the crawl history
            stmt = select(CrawlHistory).where(CrawlHistory.id == crawl_id)
            result = await self.session.execute(stmt)
            history = result.scalar_one_or_none()

            if history is None:
                logger.warning(
                    "Crawl not found for recovery",
                    extra={"crawl_id": crawl_id},
                )
                return RecoveryResult(
                    crawl_id=crawl_id,
                    project_id="unknown",
                    previous_status="unknown",
                    new_status="unknown",
                    action_taken="not_found",
                    error="Crawl not found",
                )

            previous_status = history.status

            # Only recover crawls that are actually in an inconsistent state
            if previous_status not in ("running", "pending"):
                logger.debug(
                    "Crawl not in recoverable state",
                    extra={
                        "crawl_id": crawl_id,
                        "project_id": history.project_id,
                        "status": previous_status,
                    },
                )
                return RecoveryResult(
                    crawl_id=crawl_id,
                    project_id=history.project_id,
                    previous_status=previous_status,
                    new_status=previous_status,
                    action_taken="skipped",
                    error=f"Crawl not in recoverable state: {previous_status}",
                )

            # Determine new status
            new_status = "failed" if mark_as_failed else "interrupted"

            # Update the crawl with recovery metadata
            now = datetime.now(UTC)
            recovery_info = {
                "interrupted": True,
                "interrupted_at": now.isoformat(),
                "recovery_reason": "server_restart",
                "previous_status": previous_status,
                "pages_crawled_at_interruption": history.pages_crawled,
                "pages_failed_at_interruption": history.pages_failed,
            }

            # Merge with existing stats
            updated_stats = {**(history.stats or {}), "recovery": recovery_info}

            # Update the record
            update_stmt = (
                update(CrawlHistory)
                .where(CrawlHistory.id == crawl_id)
                .values(
                    status=new_status,
                    completed_at=now,
                    updated_at=now,
                    stats=updated_stats,
                    error_message=f"Crawl interrupted due to server restart. "
                    f"Progress: {history.pages_crawled} pages crawled, "
                    f"{history.pages_failed} failed.",
                )
            )
            await self.session.execute(update_stmt)

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log state transition at INFO level
            logger.info(
                "Crawl recovery: status transition",
                extra={
                    "crawl_id": crawl_id,
                    "project_id": history.project_id,
                    "from_status": previous_status,
                    "to_status": new_status,
                    "pages_crawled": history.pages_crawled,
                    "pages_failed": history.pages_failed,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow crawl recovery",
                    extra={
                        "crawl_id": crawl_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return RecoveryResult(
                crawl_id=crawl_id,
                project_id=history.project_id,
                previous_status=previous_status,
                new_status=new_status,
                action_taken="recovered",
            )

        except Exception as e:
            logger.error(
                "Failed to recover interrupted crawl",
                extra={
                    "crawl_id": crawl_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return RecoveryResult(
                crawl_id=crawl_id,
                project_id="unknown",
                previous_status="unknown",
                new_status="unknown",
                action_taken="error",
                error=str(e),
            )

    async def recover_all_interrupted_crawls(
        self,
        stale_threshold_minutes: int | None = None,
        mark_as_failed: bool = True,
    ) -> RecoverySummary:
        """Recover all interrupted crawls found in the database.

        This is the main method to call during application startup.

        Args:
            stale_threshold_minutes: Override default threshold (optional)
            mark_as_failed: If True, mark recovered crawls as 'failed'

        Returns:
            RecoverySummary with details of all recovery operations
        """
        start_time = time.monotonic()
        summary = RecoverySummary(started_at=datetime.now(UTC))

        logger.info(
            "Starting crawl recovery process",
            extra={
                "stale_threshold_minutes": stale_threshold_minutes
                or self.stale_threshold_minutes,
                "mark_as_failed": mark_as_failed,
            },
        )

        try:
            # Find all interrupted crawls
            interrupted = await self.find_interrupted_crawls(stale_threshold_minutes)
            summary.total_found = len(interrupted)

            if not interrupted:
                summary.duration_ms = (time.monotonic() - start_time) * 1000
                summary.completed_at = datetime.now(UTC)
                logger.info(
                    "Crawl recovery completed: no interrupted crawls found",
                    extra={"duration_ms": round(summary.duration_ms, 2)},
                )
                return summary

            # Recover each crawl
            for crawl in interrupted:
                result = await self.recover_interrupted_crawl(
                    crawl.crawl_id,
                    mark_as_failed=mark_as_failed,
                )
                summary.results.append(result)

                if result.action_taken == "recovered":
                    summary.total_recovered += 1
                elif result.action_taken == "error":
                    summary.total_failed += 1

            # Commit all changes
            await self.session.commit()

            summary.duration_ms = (time.monotonic() - start_time) * 1000
            summary.completed_at = datetime.now(UTC)

            logger.info(
                "Crawl recovery completed",
                extra={
                    "total_found": summary.total_found,
                    "total_recovered": summary.total_recovered,
                    "total_failed": summary.total_failed,
                    "duration_ms": round(summary.duration_ms, 2),
                },
            )

            if summary.duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow crawl recovery process",
                    extra={
                        "total_found": summary.total_found,
                        "duration_ms": round(summary.duration_ms, 2),
                    },
                )

            return summary

        except Exception as e:
            summary.duration_ms = (time.monotonic() - start_time) * 1000
            summary.completed_at = datetime.now(UTC)

            logger.error(
                "Crawl recovery process failed",
                extra={
                    "total_found": summary.total_found,
                    "total_recovered": summary.total_recovered,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(summary.duration_ms, 2),
                },
                exc_info=True,
            )
            raise


# Singleton instance and getter
_recovery_service: CrawlRecoveryService | None = None


async def get_crawl_recovery_service(
    session: AsyncSession,
    stale_threshold_minutes: int = DEFAULT_STALE_THRESHOLD_MINUTES,
) -> CrawlRecoveryService:
    """Get or create a CrawlRecoveryService instance.

    Note: Unlike other services, this does not use a global singleton
    because it requires a database session that should be scoped to
    the startup operation.

    Args:
        session: Async SQLAlchemy session
        stale_threshold_minutes: Minutes after which a crawl is considered stale

    Returns:
        CrawlRecoveryService instance
    """
    return CrawlRecoveryService(
        session=session,
        stale_threshold_minutes=stale_threshold_minutes,
    )


async def run_startup_recovery(
    session: AsyncSession,
    stale_threshold_minutes: int = DEFAULT_STALE_THRESHOLD_MINUTES,
) -> RecoverySummary:
    """Convenience function to run crawl recovery during startup.

    This is the main entry point for the lifespan manager to use.

    Args:
        session: Async SQLAlchemy session
        stale_threshold_minutes: Minutes after which a crawl is considered stale

    Returns:
        RecoverySummary with details of recovery operations
    """
    logger.info(
        "Running startup crawl recovery",
        extra={"stale_threshold_minutes": stale_threshold_minutes},
    )

    service = await get_crawl_recovery_service(session, stale_threshold_minutes)
    return await service.recover_all_interrupted_crawls()
