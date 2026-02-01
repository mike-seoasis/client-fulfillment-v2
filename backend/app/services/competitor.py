"""CompetitorService for competitor content fetching and scraping.

Orchestrates competitor scraping operations using the Crawl4AI integration.
Handles URL validation, content extraction, and progress tracking.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, competitor_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (status changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.crawl4ai import (
    Crawl4AIError,
    CrawlOptions,
    get_crawl4ai,
)
from app.models.competitor import Competitor
from app.repositories.competitor import CompetitorRepository

logger = get_logger(__name__)

# Threshold for logging slow operations
SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second

# Maximum pages to scrape per competitor
MAX_PAGES_PER_COMPETITOR = 20

# Valid status values
VALID_STATUSES = frozenset({"pending", "scraping", "completed", "failed"})


class CompetitorServiceError(Exception):
    """Base exception for CompetitorService errors."""

    pass


class CompetitorValidationError(CompetitorServiceError):
    """Raised when competitor validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class CompetitorNotFoundError(CompetitorServiceError):
    """Raised when a competitor is not found."""

    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} not found: {entity_id}")


class CompetitorDuplicateError(CompetitorServiceError):
    """Raised when a duplicate competitor URL is added."""

    def __init__(self, url: str, project_id: str):
        self.url = url
        self.project_id = project_id
        super().__init__(f"Competitor URL already exists for project: {url[:100]}")


@dataclass
class ScrapeConfig:
    """Configuration for a scrape operation."""

    max_pages: int = MAX_PAGES_PER_COMPETITOR
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    wait_for: str | None = None
    bypass_cache: bool = False

    def to_crawl_options(self) -> CrawlOptions:
        """Convert to Crawl4AI options."""
        return CrawlOptions(
            wait_for=self.wait_for,
            bypass_cache=self.bypass_cache,
        )


@dataclass
class ScrapeResult:
    """Result of a scrape operation."""

    success: bool
    pages_scraped: int = 0
    content: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


class CompetitorService:
    """Service for competitor content fetching and scraping.

    Provides business logic for:
    - Adding competitor URLs to a project
    - Triggering scraping operations
    - Retrieving scraped content
    - Managing competitor status
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize service with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self._session = session
        self._repository = CompetitorRepository(session)
        logger.debug("CompetitorService initialized")

    def _validate_url(self, url: str) -> str:
        """Validate and normalize a competitor URL.

        Args:
            url: URL to validate

        Returns:
            Normalized URL

        Raises:
            CompetitorValidationError: If URL is invalid
        """
        if not url or not url.strip():
            raise CompetitorValidationError("url", url, "URL cannot be empty")

        url = url.strip()

        # Add scheme if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                raise CompetitorValidationError(
                    "url", url, "URL must have a valid domain"
                )
            # Normalize to just scheme + netloc for the base URL
            normalized = f"{parsed.scheme}://{parsed.netloc}"
            return normalized
        except Exception as e:
            raise CompetitorValidationError(
                "url", url, f"Invalid URL format: {e}"
            ) from e

    async def add_competitor(
        self,
        project_id: str,
        url: str,
        name: str | None = None,
    ) -> Competitor:
        """Add a new competitor to a project.

        Args:
            project_id: Project UUID
            url: Competitor website URL
            name: Optional friendly name

        Returns:
            Created Competitor instance

        Raises:
            CompetitorValidationError: If URL is invalid
            CompetitorDuplicateError: If URL already exists for project
        """
        start_time = time.monotonic()
        logger.debug(
            "Adding competitor",
            extra={
                "project_id": project_id,
                "url": url[:200] if url else "",
                "name": name,
            },
        )

        # Validate URL
        normalized_url = self._validate_url(url)

        try:
            competitor = await self._repository.create(
                project_id=project_id,
                url=normalized_url,
                name=name,
            )
            await self._session.commit()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                "Competitor added",
                extra={
                    "competitor_id": competitor.id,
                    "project_id": project_id,
                    "url": normalized_url[:200],
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return competitor

        except IntegrityError:
            await self._session.rollback()
            logger.warning(
                "Duplicate competitor URL",
                extra={
                    "project_id": project_id,
                    "url": normalized_url[:200],
                },
            )
            raise CompetitorDuplicateError(normalized_url, project_id)

    async def get_competitor(self, competitor_id: str) -> Competitor:
        """Get a competitor by ID.

        Args:
            competitor_id: UUID of the competitor

        Returns:
            Competitor instance

        Raises:
            CompetitorNotFoundError: If competitor not found
        """
        logger.debug(
            "Getting competitor",
            extra={"competitor_id": competitor_id},
        )

        competitor = await self._repository.get_by_id(competitor_id)
        if competitor is None:
            raise CompetitorNotFoundError("Competitor", competitor_id)

        return competitor

    async def list_competitors(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> tuple[list[Competitor], int]:
        """List competitors for a project with pagination.

        Args:
            project_id: Project UUID
            limit: Maximum number to return
            offset: Number to skip
            status: Optional status filter

        Returns:
            Tuple of (list of competitors, total count)
        """
        logger.debug(
            "Listing competitors",
            extra={
                "project_id": project_id,
                "limit": limit,
                "offset": offset,
                "status": status,
            },
        )

        competitors = await self._repository.get_by_project(
            project_id=project_id,
            limit=limit,
            offset=offset,
            status=status,
        )
        total = await self._repository.count(project_id=project_id, status=status)

        return competitors, total

    async def delete_competitor(self, competitor_id: str) -> bool:
        """Delete a competitor.

        Args:
            competitor_id: UUID of the competitor

        Returns:
            True if deleted, False if not found
        """
        logger.debug(
            "Deleting competitor",
            extra={"competitor_id": competitor_id},
        )

        deleted = await self._repository.delete(competitor_id)
        if deleted:
            await self._session.commit()
            logger.info(
                "Competitor deleted",
                extra={"competitor_id": competitor_id},
            )

        return deleted

    async def start_scrape(
        self,
        competitor_id: str,
        config: ScrapeConfig | None = None,
    ) -> Competitor:
        """Start scraping a competitor website.

        Args:
            competitor_id: UUID of the competitor
            config: Optional scrape configuration

        Returns:
            Updated Competitor instance

        Raises:
            CompetitorNotFoundError: If competitor not found
            CompetitorValidationError: If competitor is already being scraped
        """
        start_time = time.monotonic()
        config = config or ScrapeConfig()

        competitor = await self.get_competitor(competitor_id)

        # Check if already scraping
        if competitor.status == "scraping":
            raise CompetitorValidationError(
                "status",
                competitor.status,
                "Competitor is already being scraped",
            )

        logger.info(
            "Starting competitor scrape",
            extra={
                "competitor_id": competitor_id,
                "project_id": competitor.project_id,
                "url": competitor.url[:200],
                "max_pages": config.max_pages,
            },
        )

        # Update status to scraping
        await self._repository.update_status(competitor_id, "scraping")
        await self._session.commit()

        # Perform the scrape
        result = await self._scrape_competitor(competitor, config)

        # Update with results
        final_status = "completed" if result.success else "failed"
        await self._repository.update_status(
            competitor_id,
            final_status,
            error_message=result.error,
        )
        await self._repository.update_content(
            competitor_id,
            content=result.content,
            pages_scraped=result.pages_scraped,
        )
        await self._session.commit()

        # Refresh and return
        updated = await self.get_competitor(competitor_id)

        duration_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "Competitor scrape completed",
            extra={
                "competitor_id": competitor_id,
                "status": final_status,
                "pages_scraped": result.pages_scraped,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return updated

    async def _scrape_competitor(
        self,
        competitor: Competitor,
        config: ScrapeConfig,
    ) -> ScrapeResult:
        """Perform the actual scraping operation.

        Args:
            competitor: Competitor to scrape
            config: Scrape configuration

        Returns:
            ScrapeResult with scraped content
        """
        start_time = time.monotonic()
        pages: list[dict[str, Any]] = []
        metadata: dict[str, Any] = {
            "domain": urlparse(competitor.url).netloc,
            "scrape_started_at": datetime.now(UTC).isoformat(),
        }

        try:
            # Get Crawl4AI client
            crawl4ai = await get_crawl4ai()

            if not crawl4ai.available:
                logger.warning(
                    "Crawl4AI not available",
                    extra={"competitor_id": competitor.id},
                )
                return ScrapeResult(
                    success=False,
                    error="Crawl4AI service not configured",
                    duration_ms=(time.monotonic() - start_time) * 1000,
                )

            # Scrape the main URL
            options = config.to_crawl_options()
            result = await crawl4ai.crawl(competitor.url, options)

            if not result.success:
                logger.warning(
                    "Competitor scrape failed",
                    extra={
                        "competitor_id": competitor.id,
                        "url": competitor.url[:200],
                        "error": result.error,
                    },
                )
                return ScrapeResult(
                    success=False,
                    error=result.error or "Failed to scrape URL",
                    duration_ms=(time.monotonic() - start_time) * 1000,
                )

            # Extract main page content
            main_page = {
                "url": competitor.url,
                "title": result.metadata.get("title", ""),
                "description": result.metadata.get("description", ""),
                "content": result.markdown[:10000] if result.markdown else "",
                "scraped_at": datetime.now(UTC).isoformat(),
            }
            pages.append(main_page)

            # Extract links for additional pages
            internal_links = self._filter_internal_links(
                result.links or [],
                competitor.url,
                config.max_pages - 1,  # Subtract 1 for main page
            )

            # Scrape additional pages if we have internal links
            if internal_links:
                additional_results = await crawl4ai.crawl_many(
                    internal_links,
                    options,
                )

                for crawl_result in additional_results:
                    if crawl_result.success:
                        pages.append({
                            "url": crawl_result.url,
                            "title": crawl_result.metadata.get("title", ""),
                            "description": crawl_result.metadata.get("description", ""),
                            "content": crawl_result.markdown[:10000] if crawl_result.markdown else "",
                            "scraped_at": datetime.now(UTC).isoformat(),
                        })

            # Build content structure
            content = {
                "title": main_page.get("title", ""),
                "description": main_page.get("description", ""),
                "pages": pages,
                "metadata": {
                    **metadata,
                    "total_links_found": len(result.links or []),
                    "scrape_completed_at": datetime.now(UTC).isoformat(),
                },
            }

            duration_ms = (time.monotonic() - start_time) * 1000
            return ScrapeResult(
                success=True,
                pages_scraped=len(pages),
                content=content,
                duration_ms=duration_ms,
            )

        except Crawl4AIError as e:
            logger.error(
                "Crawl4AI error during competitor scrape",
                extra={
                    "competitor_id": competitor.id,
                    "url": competitor.url[:200],
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return ScrapeResult(
                success=False,
                error=str(e),
                duration_ms=(time.monotonic() - start_time) * 1000,
            )

        except Exception as e:
            logger.error(
                "Unexpected error during competitor scrape",
                extra={
                    "competitor_id": competitor.id,
                    "url": competitor.url[:200],
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return ScrapeResult(
                success=False,
                error=f"Unexpected error: {e}",
                duration_ms=(time.monotonic() - start_time) * 1000,
            )

    def _filter_internal_links(
        self,
        links: list[dict[str, str]],
        base_url: str,
        max_count: int,
    ) -> list[str]:
        """Filter links to only include internal links.

        Args:
            links: List of link dictionaries with 'href' key
            base_url: Base URL to filter against
            max_count: Maximum number of links to return

        Returns:
            List of internal URLs
        """
        if not links or max_count <= 0:
            return []

        base_parsed = urlparse(base_url)
        base_domain = base_parsed.netloc
        seen: set[str] = set()
        internal_links: list[str] = []

        for link in links:
            href = link.get("href", "")
            if not href:
                continue

            # Parse the link
            try:
                parsed = urlparse(href)

                # Handle relative URLs
                if not parsed.netloc:
                    href = f"{base_parsed.scheme}://{base_domain}{parsed.path}"
                    parsed = urlparse(href)

                # Check if internal
                if parsed.netloc != base_domain:
                    continue

                # Normalize and dedupe
                normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if normalized in seen or normalized == base_url:
                    continue

                seen.add(normalized)
                internal_links.append(normalized)

                if len(internal_links) >= max_count:
                    break

            except Exception:
                continue

        return internal_links

    async def rescrape_competitor(
        self,
        competitor_id: str,
        config: ScrapeConfig | None = None,
    ) -> Competitor:
        """Re-scrape a competitor (force refresh).

        Args:
            competitor_id: UUID of the competitor
            config: Optional scrape configuration

        Returns:
            Updated Competitor instance
        """
        config = config or ScrapeConfig(bypass_cache=True)
        config.bypass_cache = True  # Force cache bypass for rescrape

        return await self.start_scrape(competitor_id, config)
