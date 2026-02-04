"""Crawling service for parallel page crawling with concurrency control.

Provides business logic for crawling pages using Crawl4AI integration.
Uses asyncio.Semaphore for concurrency limiting and asyncio.gather for parallel execution.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.crawl4ai import Crawl4AIClient, CrawlResult
from app.models.crawled_page import CrawledPage, CrawlStatus

logger = get_logger(__name__)


class CrawlingService:
    """Service for crawling pages with parallel execution and concurrency control."""

    def __init__(self, crawl4ai_client: Crawl4AIClient) -> None:
        """Initialize the crawling service.

        Args:
            crawl4ai_client: Crawl4AI client for making crawl requests.
        """
        self._client = crawl4ai_client
        self._settings = get_settings()

    async def crawl_urls(
        self,
        db: AsyncSession,
        page_ids: list[str],
    ) -> dict[str, CrawlResult]:
        """Crawl multiple pages in parallel with concurrency limiting.

        Updates page status through lifecycle: pending -> crawling -> completed/failed.

        Args:
            db: AsyncSession for database operations.
            page_ids: List of CrawledPage IDs to crawl.

        Returns:
            Dict mapping page_id to CrawlResult.
        """
        if not page_ids:
            return {}

        # Fetch all pages in a single query
        stmt = select(CrawledPage).where(CrawledPage.id.in_(page_ids))
        result = await db.execute(stmt)
        pages = {page.id: page for page in result.scalars().all()}

        if not pages:
            logger.warning("No pages found for provided IDs", extra={"page_ids": page_ids})
            return {}

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self._settings.crawl_concurrency)

        # Crawl all pages in parallel with semaphore
        async def crawl_with_semaphore(page: CrawledPage) -> tuple[str, CrawlResult]:
            async with semaphore:
                return await self._crawl_single_page(db, page)

        tasks = [crawl_with_semaphore(page) for page in pages.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        crawl_results: dict[str, CrawlResult] = {}
        for item in results:
            if isinstance(item, BaseException):
                logger.error(
                    "Unexpected error during crawl",
                    extra={"error": str(item), "error_type": type(item).__name__},
                )
                continue
            # item is tuple[str, CrawlResult] at this point
            page_id, crawl_result = item
            crawl_results[page_id] = crawl_result

        # Flush all changes to database
        await db.flush()

        logger.info(
            "Crawl batch completed",
            extra={
                "total_pages": len(page_ids),
                "successful": sum(1 for r in crawl_results.values() if r.success),
                "failed": sum(1 for r in crawl_results.values() if not r.success),
            },
        )

        return crawl_results

    async def _crawl_single_page(
        self,
        db: AsyncSession,
        page: CrawledPage,
    ) -> tuple[str, CrawlResult]:
        """Crawl a single page and update its status.

        Args:
            db: AsyncSession for database operations.
            page: CrawledPage to crawl.

        Returns:
            Tuple of (page_id, CrawlResult).
        """
        # Update status to crawling
        page.status = CrawlStatus.CRAWLING.value
        await db.flush()

        logger.debug(
            "Starting crawl",
            extra={"page_id": page.id, "url": page.normalized_url},
        )

        # Perform the crawl
        crawl_result = await self._client.crawl(page.normalized_url)

        # Update page based on result
        if crawl_result.success:
            page.status = CrawlStatus.COMPLETED.value
            page.body_content = crawl_result.markdown
            page.crawl_error = None
            page.last_crawled_at = datetime.now(UTC)

            # Extract metadata if available
            if crawl_result.metadata:
                if "title" in crawl_result.metadata:
                    page.title = crawl_result.metadata["title"]
                if "description" in crawl_result.metadata:
                    page.meta_description = crawl_result.metadata["description"]

            # Calculate word count from markdown
            if crawl_result.markdown:
                page.word_count = len(crawl_result.markdown.split())

            logger.info(
                "Crawl completed",
                extra={
                    "page_id": page.id,
                    "url": page.normalized_url,
                    "word_count": page.word_count,
                    "duration_ms": crawl_result.duration_ms,
                },
            )
        else:
            page.status = CrawlStatus.FAILED.value
            page.crawl_error = crawl_result.error
            page.last_crawled_at = datetime.now(UTC)

            logger.warning(
                "Crawl failed",
                extra={
                    "page_id": page.id,
                    "url": page.normalized_url,
                    "error": crawl_result.error,
                    "status_code": crawl_result.status_code,
                },
            )

        return page.id, crawl_result

    async def crawl_pending_pages(
        self,
        db: AsyncSession,
        project_id: str,
        limit: int | None = None,
    ) -> dict[str, CrawlResult]:
        """Crawl all pending pages for a project.

        Args:
            db: AsyncSession for database operations.
            project_id: Project ID to crawl pages for.
            limit: Maximum number of pages to crawl (optional).

        Returns:
            Dict mapping page_id to CrawlResult.
        """
        # Find pending pages for the project
        stmt = (
            select(CrawledPage.id)
            .where(CrawledPage.project_id == project_id)
            .where(CrawledPage.status == CrawlStatus.PENDING.value)
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        page_ids = list(result.scalars().all())

        if not page_ids:
            logger.info(
                "No pending pages to crawl",
                extra={"project_id": project_id},
            )
            return {}

        logger.info(
            "Starting crawl for pending pages",
            extra={"project_id": project_id, "page_count": len(page_ids)},
        )

        return await self.crawl_urls(db, page_ids)
