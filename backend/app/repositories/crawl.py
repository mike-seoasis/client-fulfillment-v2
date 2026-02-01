"""CrawlRepository for page storage with deduplication.

Handles all database operations for CrawledPage entities.
Follows the layered architecture pattern: API -> Service -> Repository -> Database.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import db_logger, get_logger
from app.models.crawled_page import CrawledPage

logger = get_logger(__name__)


class CrawlRepository:
    """Repository for CrawledPage CRUD operations.

    Handles page storage with URL deduplication via normalized_url.
    All methods accept an AsyncSession and handle database operations
    with comprehensive logging as required.

    Deduplication Strategy:
    - Pages are uniquely identified by (project_id, normalized_url)
    - On duplicate, update existing page instead of creating new
    - content_hash allows change detection for re-crawled pages
    """

    TABLE_NAME = "crawled_pages"
    SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session
        logger.debug("CrawlRepository initialized")

    async def create(
        self,
        project_id: str,
        normalized_url: str,
        raw_url: str | None = None,
        category: str | None = None,
        labels: list[str] | None = None,
        title: str | None = None,
        content_hash: str | None = None,
    ) -> CrawledPage:
        """Create a new crawled page.

        Args:
            project_id: Project UUID
            normalized_url: Canonical URL after normalization
            raw_url: Original URL before normalization
            category: Page category (e.g., 'homepage', 'product')
            labels: List of labels/tags for the page
            title: Page title extracted from HTML
            content_hash: Hash of page content for change detection

        Returns:
            Created CrawledPage instance

        Raises:
            IntegrityError: If page with same (project_id, normalized_url) exists
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Creating crawled page",
            extra={
                "project_id": project_id,
                "normalized_url": normalized_url[:200] if normalized_url else "",
                "category": category,
            },
        )

        try:
            page = CrawledPage(
                project_id=project_id,
                normalized_url=normalized_url,
                raw_url=raw_url,
                category=category,
                labels=labels or [],
                title=title,
                content_hash=content_hash,
                last_crawled_at=datetime.now(UTC),
            )
            self.session.add(page)
            await self.session.flush()
            await self.session.refresh(page)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Crawled page created successfully",
                extra={
                    "page_id": page.id,
                    "project_id": project_id,
                    "normalized_url": normalized_url[:200] if normalized_url else "",
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query="INSERT INTO crawled_pages",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return page

        except IntegrityError as e:
            logger.error(
                "Failed to create page - integrity error (duplicate URL)",
                extra={
                    "project_id": project_id,
                    "normalized_url": normalized_url[:200] if normalized_url else "",
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
                context=f"Creating page for project_id={project_id}",
            )
            raise

    async def get_by_id(self, page_id: str) -> CrawledPage | None:
        """Get a crawled page by ID.

        Args:
            page_id: UUID of the page

        Returns:
            CrawledPage instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching page by ID",
            extra={"page_id": page_id},
        )

        try:
            result = await self.session.execute(
                select(CrawledPage).where(CrawledPage.id == page_id)
            )
            page = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Page fetch completed",
                extra={
                    "page_id": page_id,
                    "found": page is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM crawled_pages WHERE id={page_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return page

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch page by ID",
                extra={
                    "page_id": page_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_normalized_url(
        self,
        project_id: str,
        normalized_url: str,
    ) -> CrawledPage | None:
        """Get a crawled page by normalized URL within a project.

        This is the primary deduplication lookup method.

        Args:
            project_id: Project UUID
            normalized_url: Canonical URL after normalization

        Returns:
            CrawledPage instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching page by normalized URL",
            extra={
                "project_id": project_id,
                "normalized_url": normalized_url[:200] if normalized_url else "",
            },
        )

        try:
            result = await self.session.execute(
                select(CrawledPage).where(
                    CrawledPage.project_id == project_id,
                    CrawledPage.normalized_url == normalized_url,
                )
            )
            page = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Page fetch by URL completed",
                extra={
                    "project_id": project_id,
                    "normalized_url": normalized_url[:200] if normalized_url else "",
                    "found": page is not None,
                    "page_id": page.id if page else None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM crawled_pages WHERE project_id={project_id} AND normalized_url=...",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return page

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch page by normalized URL",
                extra={
                    "project_id": project_id,
                    "normalized_url": normalized_url[:200] if normalized_url else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def upsert(
        self,
        project_id: str,
        normalized_url: str,
        raw_url: str | None = None,
        category: str | None = None,
        labels: list[str] | None = None,
        title: str | None = None,
        content_hash: str | None = None,
    ) -> tuple[CrawledPage, bool]:
        """Create or update a crawled page (deduplication by normalized_url).

        This is the primary method for storing crawled pages with deduplication.
        If a page with the same (project_id, normalized_url) exists, it updates
        the existing page. Otherwise, it creates a new one.

        Args:
            project_id: Project UUID
            normalized_url: Canonical URL after normalization
            raw_url: Original URL before normalization
            category: Page category (e.g., 'homepage', 'product')
            labels: List of labels/tags for the page
            title: Page title extracted from HTML
            content_hash: Hash of page content for change detection

        Returns:
            Tuple of (CrawledPage, created) where created is True if new page was created

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Upserting crawled page",
            extra={
                "project_id": project_id,
                "normalized_url": normalized_url[:200] if normalized_url else "",
                "category": category,
            },
        )

        try:
            # Check if page exists
            existing = await self.get_by_normalized_url(project_id, normalized_url)

            if existing:
                # Update existing page
                old_content_hash = existing.content_hash
                update_values: dict[str, Any] = {
                    "last_crawled_at": datetime.now(UTC),
                }

                if raw_url is not None:
                    update_values["raw_url"] = raw_url
                if category is not None:
                    update_values["category"] = category
                if labels is not None:
                    update_values["labels"] = labels
                if title is not None:
                    update_values["title"] = title
                if content_hash is not None:
                    update_values["content_hash"] = content_hash

                await self.session.execute(
                    update(CrawledPage)
                    .where(CrawledPage.id == existing.id)
                    .values(**update_values)
                )
                await self.session.flush()
                await self.session.refresh(existing)

                # Log if content changed
                if (
                    content_hash
                    and old_content_hash
                    and content_hash != old_content_hash
                ):
                    logger.info(
                        "Page content changed during re-crawl",
                        extra={
                            "page_id": existing.id,
                            "project_id": project_id,
                            "normalized_url": normalized_url[:200]
                            if normalized_url
                            else "",
                            "old_hash": old_content_hash[:16]
                            if old_content_hash
                            else None,
                            "new_hash": content_hash[:16] if content_hash else None,
                        },
                    )

                duration_ms = (time.monotonic() - start_time) * 1000
                logger.debug(
                    "Crawled page updated (upsert)",
                    extra={
                        "page_id": existing.id,
                        "project_id": project_id,
                        "normalized_url": normalized_url[:200]
                        if normalized_url
                        else "",
                        "duration_ms": round(duration_ms, 2),
                    },
                )

                if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                    db_logger.slow_query(
                        query=f"UPSERT crawled_pages page_id={existing.id}",
                        duration_ms=duration_ms,
                        table=self.TABLE_NAME,
                    )

                return existing, False

            else:
                # Create new page
                page = await self.create(
                    project_id=project_id,
                    normalized_url=normalized_url,
                    raw_url=raw_url,
                    category=category,
                    labels=labels,
                    title=title,
                    content_hash=content_hash,
                )

                duration_ms = (time.monotonic() - start_time) * 1000
                logger.debug(
                    "Crawled page created (upsert)",
                    extra={
                        "page_id": page.id,
                        "project_id": project_id,
                        "normalized_url": normalized_url[:200]
                        if normalized_url
                        else "",
                        "duration_ms": round(duration_ms, 2),
                    },
                )

                return page, True

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Upserting page for project_id={project_id}",
            )
            raise

    async def get_by_project(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CrawledPage]:
        """Get all crawled pages for a project with pagination.

        Args:
            project_id: Project UUID
            limit: Maximum number of pages to return (default: 100)
            offset: Number of pages to skip (default: 0)

        Returns:
            List of CrawledPage instances

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching pages by project",
            extra={
                "project_id": project_id,
                "limit": limit,
                "offset": offset,
            },
        )

        try:
            result = await self.session.execute(
                select(CrawledPage)
                .where(CrawledPage.project_id == project_id)
                .order_by(CrawledPage.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            pages = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Pages fetch by project completed",
                extra={
                    "project_id": project_id,
                    "count": len(pages),
                    "limit": limit,
                    "offset": offset,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM crawled_pages WHERE project_id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return pages

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch pages by project",
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

    async def get_by_category(
        self,
        project_id: str,
        category: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CrawledPage]:
        """Get all crawled pages for a project with a specific category.

        Args:
            project_id: Project UUID
            category: Page category to filter by
            limit: Maximum number of pages to return (default: 100)
            offset: Number of pages to skip (default: 0)

        Returns:
            List of CrawledPage instances

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching pages by category",
            extra={
                "project_id": project_id,
                "category": category,
                "limit": limit,
                "offset": offset,
            },
        )

        try:
            result = await self.session.execute(
                select(CrawledPage)
                .where(
                    CrawledPage.project_id == project_id,
                    CrawledPage.category == category,
                )
                .order_by(CrawledPage.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            pages = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Pages fetch by category completed",
                extra={
                    "project_id": project_id,
                    "category": category,
                    "count": len(pages),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM crawled_pages WHERE project_id={project_id} AND category={category}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return pages

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch pages by category",
                extra={
                    "project_id": project_id,
                    "category": category,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update(
        self,
        page_id: str,
        category: str | None = None,
        labels: list[str] | None = None,
        title: str | None = None,
        content_hash: str | None = None,
    ) -> CrawledPage | None:
        """Update a crawled page.

        Args:
            page_id: UUID of the page to update
            category: New category (optional)
            labels: New labels (optional)
            title: New title (optional)
            content_hash: New content hash (optional)

        Returns:
            Updated CrawledPage instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()

        # Build update dict with only provided values
        update_values: dict[str, Any] = {}
        if category is not None:
            update_values["category"] = category
        if labels is not None:
            update_values["labels"] = labels
        if title is not None:
            update_values["title"] = title
        if content_hash is not None:
            update_values["content_hash"] = content_hash

        if not update_values:
            logger.debug(
                "No update values provided, returning existing page",
                extra={"page_id": page_id},
            )
            return await self.get_by_id(page_id)

        logger.debug(
            "Updating crawled page",
            extra={
                "page_id": page_id,
                "update_fields": list(update_values.keys()),
            },
        )

        # Get current page to verify it exists
        current_page = await self.get_by_id(page_id)
        if current_page is None:
            logger.debug(
                "Page not found for update",
                extra={"page_id": page_id},
            )
            return None

        try:
            # Log category transition if applicable
            if category is not None and current_page.category != category:
                logger.info(
                    "Page category transition",
                    extra={
                        "page_id": page_id,
                        "from_category": current_page.category,
                        "to_category": category,
                    },
                )

            await self.session.execute(
                update(CrawledPage)
                .where(CrawledPage.id == page_id)
                .values(**update_values)
            )
            await self.session.flush()

            # Refresh to get updated values
            updated_page = await self.get_by_id(page_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Page updated successfully",
                extra={
                    "page_id": page_id,
                    "update_fields": list(update_values.keys()),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"UPDATE crawled_pages WHERE id={page_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return updated_page

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating page_id={page_id}",
            )
            raise

    async def delete(self, page_id: str) -> bool:
        """Delete a crawled page.

        Args:
            page_id: UUID of the page to delete

        Returns:
            True if page was deleted, False if not found

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting page",
            extra={"page_id": page_id},
        )

        try:
            result = await self.session.execute(
                delete(CrawledPage).where(CrawledPage.id == page_id)
            )
            await self.session.flush()

            deleted = result.rowcount > 0

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Page delete completed",
                extra={
                    "page_id": page_id,
                    "deleted": deleted,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"DELETE FROM crawled_pages WHERE id={page_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return deleted

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting page_id={page_id}",
            )
            raise

    async def delete_by_project(self, project_id: str) -> int:
        """Delete all crawled pages for a project.

        Args:
            project_id: Project UUID

        Returns:
            Number of pages deleted

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting all pages for project",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                delete(CrawledPage).where(CrawledPage.project_id == project_id)
            )
            await self.session.flush()

            deleted_count = result.rowcount

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                "Project pages deleted",
                extra={
                    "project_id": project_id,
                    "deleted_count": deleted_count,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"DELETE FROM crawled_pages WHERE project_id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return deleted_count

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting pages for project_id={project_id}",
            )
            raise

    async def exists(self, page_id: str) -> bool:
        """Check if a page exists.

        Args:
            page_id: UUID of the page

        Returns:
            True if page exists, False otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Checking page existence",
            extra={"page_id": page_id},
        )

        try:
            result = await self.session.execute(
                select(CrawledPage.id).where(CrawledPage.id == page_id)
            )
            exists = result.scalar_one_or_none() is not None

            logger.debug(
                "Page existence check completed",
                extra={
                    "page_id": page_id,
                    "exists": exists,
                },
            )

            return exists

        except SQLAlchemyError as e:
            logger.error(
                "Failed to check page existence",
                extra={
                    "page_id": page_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def url_exists(
        self,
        project_id: str,
        normalized_url: str,
    ) -> bool:
        """Check if a URL has already been crawled for a project.

        This is the primary deduplication check method.

        Args:
            project_id: Project UUID
            normalized_url: Canonical URL after normalization

        Returns:
            True if URL exists, False otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Checking URL existence",
            extra={
                "project_id": project_id,
                "normalized_url": normalized_url[:200] if normalized_url else "",
            },
        )

        try:
            result = await self.session.execute(
                select(CrawledPage.id).where(
                    CrawledPage.project_id == project_id,
                    CrawledPage.normalized_url == normalized_url,
                )
            )
            exists = result.scalar_one_or_none() is not None

            logger.debug(
                "URL existence check completed",
                extra={
                    "project_id": project_id,
                    "normalized_url": normalized_url[:200] if normalized_url else "",
                    "exists": exists,
                },
            )

            return exists

        except SQLAlchemyError as e:
            logger.error(
                "Failed to check URL existence",
                extra={
                    "project_id": project_id,
                    "normalized_url": normalized_url[:200] if normalized_url else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def count(self, project_id: str | None = None) -> int:
        """Count total number of crawled pages.

        Args:
            project_id: Optional project UUID to filter by

        Returns:
            Total count of pages

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Counting pages",
            extra={"project_id": project_id},
        )

        try:
            stmt = select(func.count()).select_from(CrawledPage)
            if project_id:
                stmt = stmt.where(CrawledPage.project_id == project_id)

            result = await self.session.execute(stmt)
            count = result.scalar_one()

            logger.debug(
                "Page count completed",
                extra={
                    "project_id": project_id,
                    "count": count,
                },
            )

            return count

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count pages",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def count_by_category(
        self,
        project_id: str,
        category: str,
    ) -> int:
        """Count pages with a specific category in a project.

        Args:
            project_id: Project UUID
            category: Category to count

        Returns:
            Count of pages with the given category

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Counting pages by category",
            extra={
                "project_id": project_id,
                "category": category,
            },
        )

        try:
            result = await self.session.execute(
                select(func.count())
                .select_from(CrawledPage)
                .where(
                    CrawledPage.project_id == project_id,
                    CrawledPage.category == category,
                )
            )
            count = result.scalar_one()

            logger.debug(
                "Page count by category completed",
                extra={
                    "project_id": project_id,
                    "category": category,
                    "count": count,
                },
            )

            return count

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count pages by category",
                extra={
                    "project_id": project_id,
                    "category": category,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_changed_pages(
        self,
        project_id: str,
        since: datetime,
    ) -> list[CrawledPage]:
        """Get pages that have been modified since a given time.

        Useful for incremental processing workflows.

        Args:
            project_id: Project UUID
            since: Datetime to check for changes from

        Returns:
            List of CrawledPage instances modified since the given time

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching changed pages",
            extra={
                "project_id": project_id,
                "since": since.isoformat(),
            },
        )

        try:
            result = await self.session.execute(
                select(CrawledPage)
                .where(
                    CrawledPage.project_id == project_id,
                    CrawledPage.updated_at > since,
                )
                .order_by(CrawledPage.updated_at.desc())
            )
            pages = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Changed pages fetch completed",
                extra={
                    "project_id": project_id,
                    "since": since.isoformat(),
                    "count": len(pages),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM crawled_pages WHERE project_id={project_id} AND updated_at > ...",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return pages

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch changed pages",
                extra={
                    "project_id": project_id,
                    "since": since.isoformat(),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_urls_for_project(self, project_id: str) -> set[str]:
        """Get all normalized URLs for a project.

        Useful for deduplication checks during batch operations.

        Args:
            project_id: Project UUID

        Returns:
            Set of normalized URLs

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching URLs for project",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                select(CrawledPage.normalized_url).where(
                    CrawledPage.project_id == project_id
                )
            )
            urls = {row[0] for row in result.all()}

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "URLs fetch completed",
                extra={
                    "project_id": project_id,
                    "count": len(urls),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT normalized_url FROM crawled_pages WHERE project_id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return urls

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch URLs for project",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise
