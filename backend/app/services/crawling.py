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
from app.services.content_extraction import extract_content_from_html

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

        NOTE: This method separates network operations (parallel) from database
        operations (sequential) to avoid AsyncSession concurrency issues.
        SQLAlchemy's AsyncSession is not safe for concurrent access from
        multiple coroutines.

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
            logger.warning(
                "No pages found for provided IDs", extra={"page_ids": page_ids}
            )
            return {}

        # Mark all pages as CRAWLING first (sequential db operation)
        for page in pages.values():
            page.status = CrawlStatus.CRAWLING.value
        await db.flush()

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self._settings.crawl_concurrency)

        # Crawl all pages in parallel with semaphore (network only, no db access)
        async def crawl_with_semaphore(
            page_id: str, url: str
        ) -> tuple[str, CrawlResult]:
            async with semaphore:
                logger.debug(
                    "Starting crawl",
                    extra={"page_id": page_id, "url": url},
                )
                crawl_result = await self._client.crawl(url)
                return page_id, crawl_result

        tasks = [
            crawl_with_semaphore(page.id, page.normalized_url)
            for page in pages.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and update pages (sequential db operations)
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

            # Update the page with crawl result
            matched_page = pages.get(page_id)
            if matched_page:
                self._apply_crawl_result(matched_page, crawl_result)

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

    def _apply_crawl_result(self, page: CrawledPage, crawl_result: CrawlResult) -> None:
        """Apply crawl result to a page object.

        Args:
            page: CrawledPage to update.
            crawl_result: Result from the crawl operation.
        """
        if crawl_result.success:
            page.status = CrawlStatus.COMPLETED.value
            page.crawl_error = None
            page.last_crawled_at = datetime.now(UTC)

            # Extract structured content from HTML using BeautifulSoup
            extracted = extract_content_from_html(
                html=crawl_result.html,
                markdown=crawl_result.markdown,
                cleaned_html=crawl_result.cleaned_html,
            )

            # Apply extracted content to page
            page.title = extracted.title
            page.meta_description = extracted.meta_description
            page.headings = extracted.headings
            page.body_content = extracted.body_content
            page.word_count = extracted.word_count
            page.product_count = extracted.product_count

            logger.info(
                "Crawl completed",
                extra={
                    "page_id": page.id,
                    "url": page.normalized_url,
                    "word_count": page.word_count,
                    "headings_count": sum(len(h) for h in extracted.headings.values()),
                    "product_count": page.product_count,
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
