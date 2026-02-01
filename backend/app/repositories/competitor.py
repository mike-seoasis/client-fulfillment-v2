"""CompetitorRepository for competitor data storage and retrieval.

Handles all database operations for Competitor entities.
Follows the layered architecture pattern: API -> Service -> Repository -> Database.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, competitor_id) in all logs
- Log validation failures with field names and rejected values
- Log state transitions (status changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import db_logger, get_logger
from app.models.competitor import Competitor

logger = get_logger(__name__)


class CompetitorRepository:
    """Repository for Competitor CRUD operations.

    Handles competitor storage with URL deduplication per project.
    All methods accept an AsyncSession and handle database operations
    with comprehensive logging as required.

    Deduplication Strategy:
    - Competitors are uniquely identified by (project_id, url)
    - On duplicate, an IntegrityError is raised
    """

    TABLE_NAME = "competitors"
    SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session
        logger.debug("CompetitorRepository initialized")

    async def create(
        self,
        project_id: str,
        url: str,
        name: str | None = None,
    ) -> Competitor:
        """Create a new competitor.

        Args:
            project_id: Project UUID
            url: The competitor website URL
            name: Optional friendly name for the competitor

        Returns:
            Created Competitor instance

        Raises:
            IntegrityError: If competitor with same (project_id, url) exists
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Creating competitor",
            extra={
                "project_id": project_id,
                "url": url[:200] if url else "",
                "name": name,
            },
        )

        try:
            competitor = Competitor(
                project_id=project_id,
                url=url,
                name=name,
                status="pending",
            )
            self.session.add(competitor)
            await self.session.flush()
            await self.session.refresh(competitor)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Competitor created successfully",
                extra={
                    "competitor_id": competitor.id,
                    "project_id": project_id,
                    "url": url[:200] if url else "",
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query="INSERT INTO competitors",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return competitor

        except IntegrityError as e:
            logger.error(
                "Failed to create competitor - integrity error (duplicate URL)",
                extra={
                    "project_id": project_id,
                    "url": url[:200] if url else "",
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
                context=f"Creating competitor for project_id={project_id}",
            )
            raise

    async def get_by_id(self, competitor_id: str) -> Competitor | None:
        """Get a competitor by ID.

        Args:
            competitor_id: UUID of the competitor

        Returns:
            Competitor instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching competitor by ID",
            extra={"competitor_id": competitor_id},
        )

        try:
            result = await self.session.execute(
                select(Competitor).where(Competitor.id == competitor_id)
            )
            competitor = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Competitor fetch completed",
                extra={
                    "competitor_id": competitor_id,
                    "found": competitor is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM competitors WHERE id={competitor_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return competitor

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch competitor by ID",
                extra={
                    "competitor_id": competitor_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_url(
        self,
        project_id: str,
        url: str,
    ) -> Competitor | None:
        """Get a competitor by URL within a project.

        Args:
            project_id: Project UUID
            url: The competitor website URL

        Returns:
            Competitor instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching competitor by URL",
            extra={
                "project_id": project_id,
                "url": url[:200] if url else "",
            },
        )

        try:
            result = await self.session.execute(
                select(Competitor).where(
                    Competitor.project_id == project_id,
                    Competitor.url == url,
                )
            )
            competitor = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Competitor fetch by URL completed",
                extra={
                    "project_id": project_id,
                    "url": url[:200] if url else "",
                    "found": competitor is not None,
                    "competitor_id": competitor.id if competitor else None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM competitors WHERE project_id={project_id} AND url=...",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return competitor

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch competitor by URL",
                extra={
                    "project_id": project_id,
                    "url": url[:200] if url else "",
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
        status: str | None = None,
    ) -> list[Competitor]:
        """Get all competitors for a project with pagination.

        Args:
            project_id: Project UUID
            limit: Maximum number of competitors to return (default: 100)
            offset: Number of competitors to skip (default: 0)
            status: Optional status filter

        Returns:
            List of Competitor instances

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching competitors by project",
            extra={
                "project_id": project_id,
                "limit": limit,
                "offset": offset,
                "status": status,
            },
        )

        try:
            query = select(Competitor).where(Competitor.project_id == project_id)

            if status:
                query = query.where(Competitor.status == status)

            query = query.order_by(Competitor.created_at.desc()).limit(limit).offset(offset)

            result = await self.session.execute(query)
            competitors = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Competitors fetch by project completed",
                extra={
                    "project_id": project_id,
                    "count": len(competitors),
                    "limit": limit,
                    "offset": offset,
                    "status": status,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM competitors WHERE project_id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return competitors

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch competitors by project",
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

    async def update_status(
        self,
        competitor_id: str,
        status: str,
        error_message: str | None = None,
    ) -> Competitor | None:
        """Update competitor status.

        Args:
            competitor_id: UUID of the competitor
            status: New status value
            error_message: Optional error message (for failed status)

        Returns:
            Updated Competitor instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()

        # Get current competitor to log status transition
        current = await self.get_by_id(competitor_id)
        if current is None:
            logger.debug(
                "Competitor not found for status update",
                extra={"competitor_id": competitor_id},
            )
            return None

        logger.info(
            "Competitor status transition",
            extra={
                "competitor_id": competitor_id,
                "from_status": current.status,
                "to_status": status,
            },
        )

        try:
            update_values: dict[str, Any] = {"status": status}
            if error_message is not None:
                update_values["error_message"] = error_message

            # Set scrape timestamps based on status
            if status == "scraping":
                update_values["scrape_started_at"] = datetime.now(UTC)
            elif status in ("completed", "failed"):
                update_values["scrape_completed_at"] = datetime.now(UTC)

            await self.session.execute(
                update(Competitor)
                .where(Competitor.id == competitor_id)
                .values(**update_values)
            )
            await self.session.flush()

            # Refresh to get updated values
            updated = await self.get_by_id(competitor_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Competitor status updated",
                extra={
                    "competitor_id": competitor_id,
                    "status": status,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"UPDATE competitors SET status={status} WHERE id={competitor_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return updated

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating status for competitor_id={competitor_id}",
            )
            raise

    async def update_content(
        self,
        competitor_id: str,
        content: dict[str, Any],
        pages_scraped: int,
    ) -> Competitor | None:
        """Update competitor scraped content.

        Args:
            competitor_id: UUID of the competitor
            content: JSONB content data
            pages_scraped: Number of pages successfully scraped

        Returns:
            Updated Competitor instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Updating competitor content",
            extra={
                "competitor_id": competitor_id,
                "pages_scraped": pages_scraped,
                "content_keys": list(content.keys()) if content else [],
            },
        )

        try:
            await self.session.execute(
                update(Competitor)
                .where(Competitor.id == competitor_id)
                .values(
                    content=content,
                    pages_scraped=pages_scraped,
                )
            )
            await self.session.flush()

            # Refresh to get updated values
            updated = await self.get_by_id(competitor_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Competitor content updated",
                extra={
                    "competitor_id": competitor_id,
                    "pages_scraped": pages_scraped,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"UPDATE competitors SET content=... WHERE id={competitor_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return updated

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating content for competitor_id={competitor_id}",
            )
            raise

    async def delete(self, competitor_id: str) -> bool:
        """Delete a competitor.

        Args:
            competitor_id: UUID of the competitor to delete

        Returns:
            True if competitor was deleted, False if not found

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting competitor",
            extra={"competitor_id": competitor_id},
        )

        try:
            result = await self.session.execute(
                delete(Competitor).where(Competitor.id == competitor_id)
            )
            await self.session.flush()

            deleted = result.rowcount > 0

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Competitor delete completed",
                extra={
                    "competitor_id": competitor_id,
                    "deleted": deleted,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"DELETE FROM competitors WHERE id={competitor_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return deleted

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting competitor_id={competitor_id}",
            )
            raise

    async def delete_by_project(self, project_id: str) -> int:
        """Delete all competitors for a project.

        Args:
            project_id: Project UUID

        Returns:
            Number of competitors deleted

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting all competitors for project",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                delete(Competitor).where(Competitor.project_id == project_id)
            )
            await self.session.flush()

            deleted_count = result.rowcount

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                "Project competitors deleted",
                extra={
                    "project_id": project_id,
                    "deleted_count": deleted_count,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"DELETE FROM competitors WHERE project_id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return deleted_count

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting competitors for project_id={project_id}",
            )
            raise

    async def count(
        self,
        project_id: str | None = None,
        status: str | None = None,
    ) -> int:
        """Count total number of competitors.

        Args:
            project_id: Optional project UUID to filter by
            status: Optional status to filter by

        Returns:
            Total count of competitors

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Counting competitors",
            extra={"project_id": project_id, "status": status},
        )

        try:
            stmt = select(func.count()).select_from(Competitor)
            if project_id:
                stmt = stmt.where(Competitor.project_id == project_id)
            if status:
                stmt = stmt.where(Competitor.status == status)

            result = await self.session.execute(stmt)
            count = result.scalar_one()

            logger.debug(
                "Competitor count completed",
                extra={
                    "project_id": project_id,
                    "status": status,
                    "count": count,
                },
            )

            return count

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count competitors",
                extra={
                    "project_id": project_id,
                    "status": status,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def url_exists(
        self,
        project_id: str,
        url: str,
    ) -> bool:
        """Check if a competitor URL already exists for a project.

        Args:
            project_id: Project UUID
            url: The competitor website URL

        Returns:
            True if URL exists, False otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Checking competitor URL existence",
            extra={
                "project_id": project_id,
                "url": url[:200] if url else "",
            },
        )

        try:
            result = await self.session.execute(
                select(Competitor.id).where(
                    Competitor.project_id == project_id,
                    Competitor.url == url,
                )
            )
            exists = result.scalar_one_or_none() is not None

            logger.debug(
                "Competitor URL existence check completed",
                extra={
                    "project_id": project_id,
                    "url": url[:200] if url else "",
                    "exists": exists,
                },
            )

            return exists

        except SQLAlchemyError as e:
            logger.error(
                "Failed to check competitor URL existence",
                extra={
                    "project_id": project_id,
                    "url": url[:200] if url else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise
