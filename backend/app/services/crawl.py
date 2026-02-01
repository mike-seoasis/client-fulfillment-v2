"""CrawlService with include/exclude pattern matching.

Orchestrates web crawling operations using the URLPriorityQueue for URL management
and the Crawl4AI integration for actual crawling. Handles pattern-based URL filtering.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import hashlib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from fnmatch import fnmatch
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.websocket import connection_manager
from app.integrations.crawl4ai import (
    Crawl4AIClient,
    CrawlOptions,
    CrawlResult,
)
from app.models.crawl_history import CrawlHistory
from app.models.crawled_page import CrawledPage
from app.utils.crawl_queue import URLPriority, URLPriorityQueue
from app.utils.url import normalize_url
from app.utils.url_categorizer import get_url_categorizer

logger = get_logger(__name__)

# Threshold for logging slow operations
SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second


class CrawlServiceError(Exception):
    """Base exception for CrawlService errors."""

    pass


class CrawlValidationError(CrawlServiceError):
    """Raised when crawl validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class CrawlNotFoundError(CrawlServiceError):
    """Raised when a crawl job or page is not found."""

    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} not found: {entity_id}")


class CrawlPatternError(CrawlServiceError):
    """Raised when pattern matching fails or patterns are invalid."""

    def __init__(self, pattern: str, message: str):
        self.pattern = pattern
        self.message = message
        super().__init__(f"Invalid pattern '{pattern}': {message}")


@dataclass
class CrawlConfig:
    """Configuration for a crawl operation."""

    start_url: str
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    max_pages: int = 100
    max_depth: int = 3
    crawl_options: CrawlOptions | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for storage."""
        return {
            "start_url": self.start_url,
            "include_patterns": self.include_patterns,
            "exclude_patterns": self.exclude_patterns,
            "max_pages": self.max_pages,
            "max_depth": self.max_depth,
        }


@dataclass
class CrawlProgress:
    """Progress tracking for a crawl operation."""

    pages_crawled: int = 0
    pages_failed: int = 0
    pages_skipped: int = 0
    urls_discovered: int = 0
    current_depth: int = 0
    status: str = "pending"
    errors: list[dict[str, Any]] = field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert progress to dictionary for storage."""
        return {
            "pages_crawled": self.pages_crawled,
            "pages_failed": self.pages_failed,
            "pages_skipped": self.pages_skipped,
            "urls_discovered": self.urls_discovered,
            "current_depth": self.current_depth,
        }


class PatternMatcher:
    """URL pattern matching for include/exclude filtering.

    Supports glob patterns for flexible URL matching:
    - `/products/*` - matches /products/item1, /products/item2
    - `/**/products/*` - matches /any/path/products/item
    - `*.pdf` - matches any URL ending in .pdf
    """

    def __init__(
        self,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        """Initialize pattern matcher.

        Args:
            include_patterns: Glob patterns for URLs to include (high priority)
            exclude_patterns: Glob patterns for URLs to exclude (checked first)
        """
        logger.debug(
            "PatternMatcher.__init__ called",
            extra={
                "include_pattern_count": len(include_patterns) if include_patterns else 0,
                "exclude_pattern_count": len(exclude_patterns) if exclude_patterns else 0,
            },
        )

        self._include_patterns = include_patterns or []
        self._exclude_patterns = exclude_patterns or []

        # Validate patterns
        for pattern in self._include_patterns:
            self._validate_pattern(pattern, "include")
        for pattern in self._exclude_patterns:
            self._validate_pattern(pattern, "exclude")

    def _validate_pattern(self, pattern: str, pattern_type: str) -> None:
        """Validate a glob pattern.

        Args:
            pattern: Pattern to validate
            pattern_type: Type of pattern ('include' or 'exclude')

        Raises:
            CrawlPatternError: If pattern is invalid
        """
        if not pattern or not pattern.strip():
            logger.warning(
                "Validation failed: empty pattern",
                extra={"field": f"{pattern_type}_patterns", "value": pattern},
            )
            raise CrawlPatternError(pattern, "Pattern cannot be empty")

        # Check for obviously invalid patterns
        if pattern.count("**") > 5:
            logger.warning(
                "Validation failed: too many wildcards",
                extra={"field": f"{pattern_type}_patterns", "value": pattern},
            )
            raise CrawlPatternError(pattern, "Pattern has too many ** wildcards")

    @property
    def include_patterns(self) -> list[str]:
        """Get include patterns."""
        return self._include_patterns.copy()

    @property
    def exclude_patterns(self) -> list[str]:
        """Get exclude patterns."""
        return self._exclude_patterns.copy()

    def matches_include(self, url: str) -> tuple[bool, str | None]:
        """Check if URL matches any include pattern.

        Args:
            url: URL to check

        Returns:
            Tuple of (matches, matched_pattern)
        """
        logger.debug(
            "matches_include() called",
            extra={"url": url[:200] if url else ""},
        )

        if not self._include_patterns:
            # No include patterns means all URLs are included
            return True, None

        try:
            parsed = urlparse(url)
            path = parsed.path or "/"
        except Exception as e:
            logger.warning(
                "Failed to parse URL for include matching",
                extra={
                    "url": url[:200] if url else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            return False, None

        for pattern in self._include_patterns:
            if fnmatch(path, pattern):
                logger.debug(
                    "URL matched include pattern",
                    extra={"url": url[:200], "pattern": pattern},
                )
                return True, pattern

        logger.debug(
            "URL did not match any include pattern",
            extra={"url": url[:200], "pattern_count": len(self._include_patterns)},
        )
        return False, None

    def matches_exclude(self, url: str) -> tuple[bool, str | None]:
        """Check if URL matches any exclude pattern.

        Args:
            url: URL to check

        Returns:
            Tuple of (matches, matched_pattern)
        """
        logger.debug(
            "matches_exclude() called",
            extra={"url": url[:200] if url else ""},
        )

        if not self._exclude_patterns:
            return False, None

        try:
            parsed = urlparse(url)
            path = parsed.path or "/"
        except Exception as e:
            logger.warning(
                "Failed to parse URL for exclude matching",
                extra={
                    "url": url[:200] if url else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            return False, None

        for pattern in self._exclude_patterns:
            if fnmatch(path, pattern):
                logger.debug(
                    "URL matched exclude pattern",
                    extra={"url": url[:200], "pattern": pattern},
                )
                return True, pattern

        return False, None

    def should_crawl(self, url: str) -> tuple[bool, str]:
        """Determine if URL should be crawled based on patterns.

        Exclusion patterns are checked first, then inclusion patterns.

        Args:
            url: URL to check

        Returns:
            Tuple of (should_crawl, reason)
        """
        logger.debug(
            "should_crawl() called",
            extra={"url": url[:200] if url else ""},
        )

        # Check exclusions first
        is_excluded, exclude_pattern = self.matches_exclude(url)
        if is_excluded:
            reason = f"Excluded by pattern: {exclude_pattern}"
            logger.debug(
                "URL should not be crawled",
                extra={"url": url[:200], "reason": reason},
            )
            return False, reason

        # Check inclusions
        is_included, include_pattern = self.matches_include(url)
        if is_included:
            if include_pattern:
                reason = f"Included by pattern: {include_pattern}"
            else:
                reason = "Included (no patterns specified)"
            logger.debug(
                "URL should be crawled",
                extra={"url": url[:200], "reason": reason},
            )
            return True, reason

        reason = "Not matched by any include pattern"
        logger.debug(
            "URL should not be crawled",
            extra={"url": url[:200], "reason": reason},
        )
        return False, reason

    def determine_priority(self, url: str) -> URLPriority:
        """Determine crawl priority for URL based on patterns.

        Args:
            url: URL to determine priority for

        Returns:
            URLPriority value
        """
        is_included, _ = self.matches_include(url)
        if is_included and self._include_patterns:
            return URLPriority.INCLUDE
        return URLPriority.OTHER


class CrawlService:
    """Service for orchestrating web crawling operations.

    Coordinates between:
    - URLPriorityQueue for URL management and prioritization
    - PatternMatcher for include/exclude filtering
    - Crawl4AIClient for actual crawling
    - Database for persistence

    Example usage:
        async with get_session() as session:
            service = CrawlService(session, crawl4ai_client)

            # Start a crawl
            history = await service.start_crawl(
                project_id="...",
                config=CrawlConfig(
                    start_url="https://example.com",
                    include_patterns=["/products/*", "/services/*"],
                    exclude_patterns=["/admin/*", "/api/*"],
                    max_pages=50,
                ),
            )

            # Check progress
            progress = await service.get_crawl_progress(history.id)
    """

    def __init__(
        self,
        session: AsyncSession,
        crawl4ai_client: Crawl4AIClient | None = None,
    ) -> None:
        """Initialize CrawlService.

        Args:
            session: Async SQLAlchemy session
            crawl4ai_client: Optional Crawl4AI client (uses global if not provided)
        """
        self.session = session
        self._crawl4ai = crawl4ai_client
        logger.debug("CrawlService initialized")

    async def _get_crawl4ai(self) -> Crawl4AIClient:
        """Get Crawl4AI client (lazy load if needed)."""
        if self._crawl4ai is None:
            from app.integrations.crawl4ai import get_crawl4ai

            self._crawl4ai = await get_crawl4ai()
        return self._crawl4ai

    # -------------------------------------------------------------------------
    # Pattern Matching Methods
    # -------------------------------------------------------------------------

    def create_pattern_matcher(
        self,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> PatternMatcher:
        """Create a pattern matcher with validation.

        Args:
            include_patterns: Glob patterns for URLs to include
            exclude_patterns: Glob patterns for URLs to exclude

        Returns:
            Configured PatternMatcher

        Raises:
            CrawlPatternError: If patterns are invalid
        """
        start_time = time.monotonic()
        logger.debug(
            "Creating pattern matcher",
            extra={
                "include_patterns": include_patterns[:5] if include_patterns else [],
                "exclude_patterns": exclude_patterns[:5] if exclude_patterns else [],
            },
        )

        try:
            matcher = PatternMatcher(
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Pattern matcher created",
                extra={"duration_ms": round(duration_ms, 2)},
            )

            return matcher

        except CrawlPatternError:
            raise
        except Exception as e:
            logger.error(
                "Failed to create pattern matcher",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    def filter_urls(
        self,
        urls: list[str],
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[str]:
        """Filter URLs using include/exclude patterns.

        Args:
            urls: List of URLs to filter
            include_patterns: Glob patterns for URLs to include
            exclude_patterns: Glob patterns for URLs to exclude

        Returns:
            Filtered list of URLs that should be crawled
        """
        start_time = time.monotonic()
        logger.debug(
            "filter_urls() called",
            extra={
                "url_count": len(urls),
                "include_pattern_count": len(include_patterns) if include_patterns else 0,
                "exclude_pattern_count": len(exclude_patterns) if exclude_patterns else 0,
            },
        )

        try:
            matcher = self.create_pattern_matcher(
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )

            filtered: list[str] = []
            excluded_count = 0
            not_included_count = 0

            for url in urls:
                should_crawl, reason = matcher.should_crawl(url)
                if should_crawl:
                    filtered.append(url)
                elif "Excluded" in reason:
                    excluded_count += 1
                else:
                    not_included_count += 1

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "URLs filtered",
                extra={
                    "input_count": len(urls),
                    "output_count": len(filtered),
                    "excluded_count": excluded_count,
                    "not_included_count": not_included_count,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow URL filtering",
                    extra={
                        "url_count": len(urls),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return filtered

        except CrawlServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to filter URLs",
                extra={
                    "url_count": len(urls),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Crawl Job Management
    # -------------------------------------------------------------------------

    async def create_crawl_history(
        self,
        project_id: str,
        config: CrawlConfig,
        trigger_type: str = "manual",
        schedule_id: str | None = None,
    ) -> CrawlHistory:
        """Create a new crawl history record.

        Args:
            project_id: Project UUID
            config: Crawl configuration
            trigger_type: How the crawl was triggered
            schedule_id: Optional schedule UUID

        Returns:
            Created CrawlHistory record
        """
        start_time = time.monotonic()
        logger.debug(
            "Creating crawl history",
            extra={
                "project_id": project_id,
                "start_url": config.start_url[:200],
                "trigger_type": trigger_type,
                "schedule_id": schedule_id,
            },
        )

        try:
            self._validate_uuid(project_id, "project_id")
            if schedule_id:
                self._validate_uuid(schedule_id, "schedule_id")
            self._validate_url(config.start_url, "start_url")

            history = CrawlHistory(
                project_id=project_id,
                schedule_id=schedule_id,
                status="pending",
                trigger_type=trigger_type,
                stats=config.to_dict(),
            )

            self.session.add(history)
            await self.session.flush()
            await self.session.refresh(history)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                "Crawl history created",
                extra={
                    "crawl_id": history.id,
                    "project_id": project_id,
                    "status": "pending",
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow crawl history creation",
                    extra={
                        "crawl_id": history.id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return history

        except CrawlServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to create crawl history",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update_crawl_status(
        self,
        crawl_id: str,
        status: str,
        progress: CrawlProgress | None = None,
        error_message: str | None = None,
    ) -> CrawlHistory:
        """Update crawl job status.

        Args:
            crawl_id: Crawl history UUID
            status: New status
            progress: Optional progress update
            error_message: Optional error message

        Returns:
            Updated CrawlHistory record
        """
        start_time = time.monotonic()
        logger.debug(
            "Updating crawl status",
            extra={
                "crawl_id": crawl_id,
                "new_status": status,
            },
        )

        try:
            self._validate_uuid(crawl_id, "crawl_id")
            self._validate_crawl_status(status)

            stmt = select(CrawlHistory).where(CrawlHistory.id == crawl_id)
            result = await self.session.execute(stmt)
            history = result.scalar_one_or_none()

            if history is None:
                raise CrawlNotFoundError("CrawlHistory", crawl_id)

            old_status = history.status

            # Update fields
            history.status = status

            if progress:
                history.pages_crawled = progress.pages_crawled
                history.pages_failed = progress.pages_failed
                history.stats = {**history.stats, **progress.to_dict()}
                history.error_log = progress.errors

            if error_message:
                history.error_message = error_message

            # Set timestamps based on status
            if status == "running" and history.started_at is None:
                history.started_at = datetime.now(UTC)

            if status in ("completed", "failed", "cancelled"):
                history.completed_at = datetime.now(UTC)

            await self.session.flush()
            await self.session.refresh(history)

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log state transition at INFO level
            if old_status != status:
                logger.info(
                    "Crawl status transition",
                    extra={
                        "crawl_id": crawl_id,
                        "from_status": old_status,
                        "to_status": status,
                        "pages_crawled": history.pages_crawled,
                        "pages_failed": history.pages_failed,
                    },
                )
            else:
                logger.debug(
                    "Crawl status updated (no change)",
                    extra={
                        "crawl_id": crawl_id,
                        "status": status,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow crawl status update",
                    extra={
                        "crawl_id": crawl_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return history

        except CrawlServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to update crawl status",
                extra={
                    "crawl_id": crawl_id,
                    "status": status,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_crawl_history(self, crawl_id: str) -> CrawlHistory:
        """Get crawl history by ID.

        Args:
            crawl_id: Crawl history UUID

        Returns:
            CrawlHistory record

        Raises:
            CrawlNotFoundError: If not found
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching crawl history",
            extra={"crawl_id": crawl_id},
        )

        try:
            self._validate_uuid(crawl_id, "crawl_id")

            stmt = select(CrawlHistory).where(CrawlHistory.id == crawl_id)
            result = await self.session.execute(stmt)
            history = result.scalar_one_or_none()

            if history is None:
                logger.debug("Crawl history not found", extra={"crawl_id": crawl_id})
                raise CrawlNotFoundError("CrawlHistory", crawl_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Crawl history fetched",
                extra={
                    "crawl_id": crawl_id,
                    "status": history.status,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow crawl history fetch",
                    extra={
                        "crawl_id": crawl_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return history

        except CrawlServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to fetch crawl history",
                extra={
                    "crawl_id": crawl_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Page Management
    # -------------------------------------------------------------------------

    async def save_crawled_page(
        self,
        project_id: str,
        url: str,
        crawl_result: CrawlResult,
        category: str | None = None,
        labels: list[str] | None = None,
        auto_categorize: bool = True,
    ) -> CrawledPage:
        """Save a crawled page to the database.

        Args:
            project_id: Project UUID
            url: Original URL
            crawl_result: Result from Crawl4AI
            category: Optional page category. If None and auto_categorize=True,
                     category will be determined by URL pattern rules.
            labels: Optional labels
            auto_categorize: If True and category is None, automatically
                            categorize the page based on URL patterns.

        Returns:
            Created or updated CrawledPage
        """
        start_time = time.monotonic()
        logger.debug(
            "Saving crawled page",
            extra={
                "project_id": project_id,
                "url": url[:200],
                "success": crawl_result.success,
                "auto_categorize": auto_categorize,
            },
        )

        try:
            self._validate_uuid(project_id, "project_id")
            self._validate_url(url, "url")

            # Normalize URL
            normalized = normalize_url(url)

            # Generate content hash if we have content
            content_hash = None
            if crawl_result.markdown:
                content_hash = hashlib.sha256(
                    crawl_result.markdown.encode()
                ).hexdigest()

            # Extract title from metadata
            title = crawl_result.metadata.get("title")

            # Auto-categorize if no category provided and auto_categorize is enabled
            if category is None and auto_categorize:
                categorizer = get_url_categorizer()
                category, matched_pattern = categorizer.categorize(normalized)
                logger.debug(
                    "Auto-categorized page by URL pattern",
                    extra={
                        "project_id": project_id,
                        "url": normalized[:200],
                        "category": category,
                        "matched_pattern": matched_pattern,
                    },
                )

            # Check if page exists
            stmt = select(CrawledPage).where(
                CrawledPage.project_id == project_id,
                CrawledPage.normalized_url == normalized,
            )
            result = await self.session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing page
                old_category = existing.category
                existing.raw_url = url
                existing.content_hash = content_hash
                existing.title = title
                existing.last_crawled_at = datetime.now(UTC)
                if category:
                    existing.category = category
                if labels:
                    existing.labels = labels

                page = existing

                # Log category change at INFO level (state transition)
                if old_category != page.category:
                    logger.info(
                        "Page category changed",
                        extra={
                            "page_id": page.id,
                            "project_id": project_id,
                            "url": normalized[:200],
                            "old_category": old_category,
                            "new_category": page.category,
                        },
                    )
                else:
                    logger.debug(
                        "Updated existing crawled page",
                        extra={
                            "page_id": page.id,
                            "project_id": project_id,
                            "url": normalized[:200],
                            "category": page.category,
                        },
                    )
            else:
                # Create new page
                page = CrawledPage(
                    project_id=project_id,
                    normalized_url=normalized,
                    raw_url=url,
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
                "Crawled page saved",
                extra={
                    "page_id": page.id,
                    "project_id": project_id,
                    "url": normalized[:200],
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow page save",
                    extra={
                        "page_id": page.id,
                        "project_id": project_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return page

        except CrawlServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to save crawled page",
                extra={
                    "project_id": project_id,
                    "url": url[:200] if url else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_crawled_pages(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CrawledPage]:
        """Get crawled pages for a project.

        Args:
            project_id: Project UUID
            limit: Maximum pages to return
            offset: Offset for pagination

        Returns:
            List of CrawledPage records
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching crawled pages",
            extra={
                "project_id": project_id,
                "limit": limit,
                "offset": offset,
            },
        )

        try:
            self._validate_uuid(project_id, "project_id")
            self._validate_pagination(limit, offset)

            stmt = (
                select(CrawledPage)
                .where(CrawledPage.project_id == project_id)
                .order_by(CrawledPage.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(stmt)
            pages = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Crawled pages fetched",
                extra={
                    "project_id": project_id,
                    "count": len(pages),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow pages fetch",
                    extra={
                        "project_id": project_id,
                        "count": len(pages),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return pages

        except CrawlServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to fetch crawled pages",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # Crawl Execution
    # -------------------------------------------------------------------------

    async def start_crawl(
        self,
        project_id: str,
        config: CrawlConfig,
        trigger_type: str = "manual",
        schedule_id: str | None = None,
    ) -> CrawlHistory:
        """Start a new crawl job.

        Creates a crawl history record and returns it. The actual crawling
        should be executed via run_crawl() or queued as a background job.

        Args:
            project_id: Project UUID
            config: Crawl configuration
            trigger_type: How the crawl was triggered
            schedule_id: Optional schedule UUID

        Returns:
            Created CrawlHistory record
        """
        start_time = time.monotonic()
        logger.debug(
            "Starting crawl",
            extra={
                "project_id": project_id,
                "start_url": config.start_url[:200],
                "include_patterns": config.include_patterns[:5],
                "exclude_patterns": config.exclude_patterns[:5],
                "max_pages": config.max_pages,
                "max_depth": config.max_depth,
            },
        )

        try:
            # Create history record
            history = await self.create_crawl_history(
                project_id=project_id,
                config=config,
                trigger_type=trigger_type,
                schedule_id=schedule_id,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                "Crawl started",
                extra={
                    "crawl_id": history.id,
                    "project_id": project_id,
                    "start_url": config.start_url[:200],
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return history

        except CrawlServiceError:
            raise
        except Exception as e:
            logger.error(
                "Failed to start crawl",
                extra={
                    "project_id": project_id,
                    "start_url": config.start_url[:200] if config else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def run_crawl(
        self,
        crawl_id: str,
        config: CrawlConfig,
    ) -> CrawlProgress:
        """Execute a crawl job.

        Uses the URLPriorityQueue for URL management and Crawl4AI for crawling.

        Args:
            crawl_id: Crawl history UUID
            config: Crawl configuration

        Returns:
            Final CrawlProgress
        """
        start_time = time.monotonic()
        logger.debug(
            "Running crawl",
            extra={
                "crawl_id": crawl_id,
                "start_url": config.start_url[:200],
                "max_pages": config.max_pages,
                "max_depth": config.max_depth,
            },
        )

        progress = CrawlProgress(started_at=datetime.now(UTC))

        try:
            # Validate inputs
            self._validate_uuid(crawl_id, "crawl_id")
            self._validate_url(config.start_url, "start_url")

            # Get crawl history to extract project_id
            history = await self.get_crawl_history(crawl_id)
            project_id = history.project_id

            # Mark as running
            progress.status = "running"
            await self.update_crawl_status(crawl_id, "running", progress)
            # Broadcast initial progress to WebSocket subscribers
            await self._broadcast_progress(project_id, crawl_id, progress)

            # Create queue and pattern matcher
            queue = URLPriorityQueue(
                start_url=config.start_url,
                include_patterns=config.include_patterns,
                exclude_patterns=config.exclude_patterns,
            )

            # Create pattern matcher for additional filtering
            matcher = self.create_pattern_matcher(
                include_patterns=config.include_patterns,
                exclude_patterns=config.exclude_patterns,
            )

            # Get Crawl4AI client
            crawl4ai = await self._get_crawl4ai()

            # Crawl loop
            while not queue.empty() and progress.pages_crawled < config.max_pages:
                queued_url = queue.pop()
                if queued_url is None:
                    break

                # Check depth limit
                if queued_url.depth > config.max_depth:
                    progress.pages_skipped += 1
                    logger.debug(
                        "Skipping URL (max depth exceeded)",
                        extra={
                            "url": queued_url.url[:200],
                            "depth": queued_url.depth,
                            "max_depth": config.max_depth,
                        },
                    )
                    continue

                progress.current_depth = max(progress.current_depth, queued_url.depth)

                # Crawl the URL
                try:
                    result = await crawl4ai.crawl(
                        queued_url.url,
                        options=config.crawl_options,
                    )

                    if result.success:
                        # Save the page
                        await self.save_crawled_page(
                            project_id=project_id,
                            url=queued_url.url,
                            crawl_result=result,
                        )
                        progress.pages_crawled += 1

                        # Extract and queue new URLs
                        if result.links and queued_url.depth < config.max_depth:
                            new_urls = [
                                link.get("href", "")
                                for link in result.links
                                if link.get("href")
                            ]

                            # Filter URLs through pattern matcher
                            for new_url in new_urls:
                                should_crawl, _ = matcher.should_crawl(new_url)
                                if should_crawl and queue.add(
                                    new_url,
                                    parent_url=queued_url.url,
                                    depth=queued_url.depth + 1,
                                ):
                                    progress.urls_discovered += 1

                        logger.debug(
                            "Page crawled successfully",
                            extra={
                                "crawl_id": crawl_id,
                                "url": queued_url.url[:200],
                                "pages_crawled": progress.pages_crawled,
                            },
                        )
                    else:
                        progress.pages_failed += 1
                        progress.errors.append({
                            "url": queued_url.url,
                            "error": result.error or "Unknown error",
                            "timestamp": datetime.now(UTC).isoformat(),
                        })
                        logger.warning(
                            "Page crawl failed",
                            extra={
                                "crawl_id": crawl_id,
                                "url": queued_url.url[:200],
                                "error": result.error,
                            },
                        )

                except Exception as e:
                    progress.pages_failed += 1
                    progress.errors.append({
                        "url": queued_url.url,
                        "error": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    })
                    logger.error(
                        "Exception during page crawl",
                        extra={
                            "crawl_id": crawl_id,
                            "url": queued_url.url[:200],
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                        exc_info=True,
                    )

                # Periodically update progress and broadcast via WebSocket
                if (progress.pages_crawled + progress.pages_failed) % 10 == 0:
                    await self.update_crawl_status(crawl_id, "running", progress)
                    # Broadcast progress to WebSocket subscribers
                    await self._broadcast_progress(project_id, crawl_id, progress)

            # Mark as completed
            progress.status = "completed"
            progress.completed_at = datetime.now(UTC)
            await self.update_crawl_status(crawl_id, "completed", progress)
            # Broadcast final progress to WebSocket subscribers
            await self._broadcast_progress(project_id, crawl_id, progress)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                "Crawl completed",
                extra={
                    "crawl_id": crawl_id,
                    "pages_crawled": progress.pages_crawled,
                    "pages_failed": progress.pages_failed,
                    "urls_discovered": progress.urls_discovered,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return progress

        except CrawlServiceError:
            progress.status = "failed"
            progress.completed_at = datetime.now(UTC)
            await self.update_crawl_status(
                crawl_id, "failed", progress, error_message=str(progress.errors[-1] if progress.errors else "Unknown error")
            )
            # Broadcast failure to WebSocket subscribers
            await self._broadcast_progress(project_id, crawl_id, progress)
            raise
        except Exception as e:
            progress.status = "failed"
            progress.completed_at = datetime.now(UTC)
            progress.errors.append({
                "url": "N/A",
                "error": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
            })
            await self.update_crawl_status(crawl_id, "failed", progress, error_message=str(e))
            # Broadcast failure to WebSocket subscribers
            await self._broadcast_progress(project_id, crawl_id, progress)
            logger.error(
                "Crawl failed with exception",
                extra={
                    "crawl_id": crawl_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    # -------------------------------------------------------------------------
    # WebSocket Progress Broadcasting
    # -------------------------------------------------------------------------

    async def _broadcast_progress(
        self,
        project_id: str,
        crawl_id: str,
        progress: CrawlProgress,
    ) -> int:
        """Broadcast crawl progress update via WebSocket.

        Args:
            project_id: Project UUID
            crawl_id: Crawl history UUID
            progress: Current progress state

        Returns:
            Number of connections the message was sent to

        ERROR LOGGING REQUIREMENTS:
        - Log broadcast failures per-client
        - Include connection_id in all WebSocket logs
        """
        try:
            progress_data = {
                "pages_crawled": progress.pages_crawled,
                "pages_failed": progress.pages_failed,
                "pages_skipped": progress.pages_skipped,
                "urls_discovered": progress.urls_discovered,
                "current_depth": progress.current_depth,
                "status": progress.status,
                "started_at": progress.started_at.isoformat() if progress.started_at else None,
                "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
                "error_count": len(progress.errors),
            }

            sent_count = await connection_manager.broadcast_progress_update(
                project_id=project_id,
                crawl_id=crawl_id,
                progress=progress_data,
            )

            logger.debug(
                "Progress broadcast completed",
                extra={
                    "project_id": project_id,
                    "crawl_id": crawl_id,
                    "sent_count": sent_count,
                    "status": progress.status,
                },
            )

            return sent_count

        except Exception as e:
            # Don't fail the crawl if WebSocket broadcast fails
            logger.warning(
                "Failed to broadcast progress via WebSocket",
                extra={
                    "project_id": project_id,
                    "crawl_id": crawl_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            return 0

    # -------------------------------------------------------------------------
    # Validation Methods
    # -------------------------------------------------------------------------

    def _validate_uuid(self, value: str, field: str) -> None:
        """Validate a UUID string."""
        import re

        if not value or not isinstance(value, str):
            logger.warning(
                "Validation failed: empty or invalid UUID",
                extra={"field": field, "value": value},
            )
            raise CrawlValidationError(field, value, "UUID is required")

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if not uuid_pattern.match(value):
            logger.warning(
                "Validation failed: invalid UUID format",
                extra={"field": field, "value": value},
            )
            raise CrawlValidationError(field, value, "Invalid UUID format")

    def _validate_url(self, value: str, field: str) -> None:
        """Validate a URL string."""
        if not value or not isinstance(value, str):
            logger.warning(
                "Validation failed: empty URL",
                extra={"field": field, "value": value},
            )
            raise CrawlValidationError(field, value, "URL is required")

        try:
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Missing scheme or netloc")
        except Exception:
            logger.warning(
                "Validation failed: invalid URL format",
                extra={"field": field, "value": value[:200] if value else ""},
            )
            raise CrawlValidationError(field, value, "Invalid URL format")

    def _validate_crawl_status(self, status: str) -> None:
        """Validate crawl status."""
        valid_statuses = {"pending", "running", "completed", "failed", "cancelled"}
        if status not in valid_statuses:
            logger.warning(
                "Validation failed: invalid crawl status",
                extra={"field": "status", "value": status, "valid": list(valid_statuses)},
            )
            raise CrawlValidationError(
                "status", status, f"Must be one of: {', '.join(sorted(valid_statuses))}"
            )

    def _validate_pagination(self, limit: int, offset: int) -> None:
        """Validate pagination parameters."""
        if limit < 1:
            logger.warning(
                "Validation failed: invalid limit",
                extra={"field": "limit", "value": limit},
            )
            raise CrawlValidationError("limit", limit, "Limit must be at least 1")

        if limit > 1000:
            logger.warning(
                "Validation failed: limit too large",
                extra={"field": "limit", "value": limit, "max": 1000},
            )
            raise CrawlValidationError("limit", limit, "Limit cannot exceed 1000")

        if offset < 0:
            logger.warning(
                "Validation failed: invalid offset",
                extra={"field": "offset", "value": offset},
            )
            raise CrawlValidationError("offset", offset, "Offset cannot be negative")

    # -------------------------------------------------------------------------
    # Fetch-Only Mode for Re-crawling Specific URLs
    # -------------------------------------------------------------------------

    async def fetch_urls(
        self,
        project_id: str,
        urls: list[str],
        crawl_options: CrawlOptions | None = None,
        update_existing: bool = True,
    ) -> list[tuple[str, CrawlResult, bool]]:
        """Fetch specific URLs without full crawl discovery.

        This is a "fetch-only" mode that re-crawls specific URLs without
        using the URLPriorityQueue or discovering new links. Useful for:
        - Re-crawling pages that may have changed
        - Refreshing content for specific URLs
        - Updating metadata for existing pages

        Args:
            project_id: Project UUID
            urls: List of URLs to fetch
            crawl_options: Optional crawl options to apply
            update_existing: If True, update existing pages; if False, skip them

        Returns:
            List of tuples: (url, CrawlResult, was_updated)

        ERROR LOGGING:
        - Log all API requests with method, endpoint, timing
        - Log API errors with status code and response body
        - Implement retry logic with attempt logging
        - Log network failures distinctly from API errors
        - Include request_id from response headers in logs
        - Log cache hits/misses at DEBUG level
        """
        start_time = time.monotonic()
        logger.info(
            "Starting fetch-only crawl",
            extra={
                "project_id": project_id,
                "url_count": len(urls),
                "update_existing": update_existing,
            },
        )

        try:
            self._validate_uuid(project_id, "project_id")
            if not urls:
                logger.warning(
                    "Validation failed: empty URL list",
                    extra={"field": "urls", "value": []},
                )
                raise CrawlValidationError("urls", [], "At least one URL is required")

            # Validate all URLs
            for url in urls:
                self._validate_url(url, "urls[]")

            results: list[tuple[str, CrawlResult, bool]] = []
            crawl4ai = await self._get_crawl4ai()

            for url in urls:
                fetch_start_time = time.monotonic()
                normalized = normalize_url(url)

                # Check if page exists (for cache hit/miss logging)
                existing = await self._get_existing_page(project_id, normalized)
                if existing:
                    logger.debug(
                        "Cache HIT: page exists in database",
                        extra={
                            "project_id": project_id,
                            "url": url[:200],
                            "page_id": existing.id,
                            "last_crawled_at": existing.last_crawled_at.isoformat() if existing.last_crawled_at else None,
                        },
                    )
                    if not update_existing:
                        logger.debug(
                            "Skipping existing page (update_existing=False)",
                            extra={
                                "project_id": project_id,
                                "url": url[:200],
                                "page_id": existing.id,
                            },
                        )
                        # Return a result indicating we skipped
                        results.append((url, CrawlResult(
                            success=True,
                            url=url,
                            metadata={"skipped": True, "reason": "update_existing=False"},
                        ), False))
                        continue
                else:
                    logger.debug(
                        "Cache MISS: page not in database",
                        extra={
                            "project_id": project_id,
                            "url": url[:200],
                        },
                    )

                # Fetch the URL with retry logic
                result = await self._fetch_url_with_retry(
                    crawl4ai,
                    url,
                    crawl_options,
                )

                was_updated = False
                if result.success:
                    # Save the page
                    await self.save_crawled_page(
                        project_id=project_id,
                        url=url,
                        crawl_result=result,
                    )
                    was_updated = True

                fetch_duration_ms = (time.monotonic() - fetch_start_time) * 1000
                logger.info(
                    "Fetch completed for URL",
                    extra={
                        "project_id": project_id,
                        "url": url[:200],
                        "success": result.success,
                        "was_updated": was_updated,
                        "duration_ms": round(fetch_duration_ms, 2),
                        "status_code": result.status_code,
                    },
                )

                results.append((url, result, was_updated))

            total_duration_ms = (time.monotonic() - start_time) * 1000
            success_count = sum(1 for _, r, _ in results if r.success)
            updated_count = sum(1 for _, _, was_updated in results if was_updated)

            logger.info(
                "Fetch-only crawl completed",
                extra={
                    "project_id": project_id,
                    "url_count": len(urls),
                    "success_count": success_count,
                    "updated_count": updated_count,
                    "duration_ms": round(total_duration_ms, 2),
                },
            )

            if total_duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow fetch-only operation",
                    extra={
                        "project_id": project_id,
                        "url_count": len(urls),
                        "duration_ms": round(total_duration_ms, 2),
                    },
                )

            return results

        except CrawlServiceError:
            raise
        except Exception as e:
            logger.error(
                "Fetch-only crawl failed with exception",
                extra={
                    "project_id": project_id,
                    "url_count": len(urls),
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def _get_existing_page(
        self,
        project_id: str,
        normalized_url: str,
    ) -> CrawledPage | None:
        """Get existing page by normalized URL.

        Args:
            project_id: Project UUID
            normalized_url: Normalized URL to look up

        Returns:
            CrawledPage if found, None otherwise
        """
        from sqlalchemy import select

        stmt = select(CrawledPage).where(
            CrawledPage.project_id == project_id,
            CrawledPage.normalized_url == normalized_url,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _fetch_url_with_retry(
        self,
        crawl4ai: Crawl4AIClient,
        url: str,
        crawl_options: CrawlOptions | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> CrawlResult:
        """Fetch a single URL with retry logic and detailed logging.

        Implements comprehensive error logging:
        - Log all API requests with method, endpoint, timing
        - Log API errors with status code and response body
        - Retry logic with attempt logging
        - Network failures vs API errors distinction
        - request_id from response headers (if available)

        Args:
            crawl4ai: Crawl4AI client
            url: URL to fetch
            crawl_options: Optional crawl options
            max_retries: Maximum retry attempts
            base_delay: Base delay between retries (exponential backoff)

        Returns:
            CrawlResult from the fetch
        """
        import asyncio

        last_error: Exception | None = None

        for attempt in range(max_retries):
            attempt_start_time = time.monotonic()

            try:
                logger.debug(
                    "API request: crawl URL",
                    extra={
                        "method": "POST",
                        "endpoint": "/crawl",
                        "url": url[:200],
                        "retry_attempt": attempt,
                        "max_retries": max_retries,
                    },
                )

                result = await crawl4ai.crawl(url, options=crawl_options)

                attempt_duration_ms = (time.monotonic() - attempt_start_time) * 1000

                # Log successful API response
                logger.debug(
                    "API response: crawl completed",
                    extra={
                        "method": "POST",
                        "endpoint": "/crawl",
                        "url": url[:200],
                        "success": result.success,
                        "status_code": result.status_code,
                        "duration_ms": round(attempt_duration_ms, 2),
                        "retry_attempt": attempt,
                        "request_id": result.metadata.get("request_id") if result.metadata else None,
                    },
                )

                if result.success:
                    return result

                # API returned error response (not network failure)
                if result.status_code and result.status_code >= 400:
                    logger.warning(
                        "API error response",
                        extra={
                            "url": url[:200],
                            "status_code": result.status_code,
                            "error": result.error,
                            "retry_attempt": attempt,
                            "request_id": result.metadata.get("request_id") if result.metadata else None,
                        },
                    )

                    # Don't retry 4xx client errors (except 429 rate limit)
                    if 400 <= result.status_code < 500 and result.status_code != 429:
                        return result

                    # Retry on 5xx or 429 with exponential backoff
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.info(
                            "Retrying API request",
                            extra={
                                "url": url[:200],
                                "retry_attempt": attempt + 1,
                                "delay_seconds": delay,
                                "reason": f"status_code={result.status_code}",
                            },
                        )
                        await asyncio.sleep(delay)
                        continue

                return result

            except Exception as e:
                attempt_duration_ms = (time.monotonic() - attempt_start_time) * 1000
                last_error = e

                # Distinguish network failures from API errors
                error_category = self._categorize_error(e)

                logger.error(
                    f"{error_category} during URL fetch",
                    extra={
                        "url": url[:200],
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "error_category": error_category,
                        "retry_attempt": attempt,
                        "duration_ms": round(attempt_duration_ms, 2),
                    },
                    exc_info=True,
                )

                # Retry on network failures with exponential backoff
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.info(
                        "Retrying after network failure",
                        extra={
                            "url": url[:200],
                            "retry_attempt": attempt + 1,
                            "delay_seconds": delay,
                            "error_type": type(e).__name__,
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

        # All retries exhausted
        logger.error(
            "All retry attempts exhausted",
            extra={
                "url": url[:200],
                "max_retries": max_retries,
                "last_error_type": type(last_error).__name__ if last_error else None,
                "last_error_message": str(last_error) if last_error else None,
            },
        )

        return CrawlResult(
            success=False,
            url=url,
            error=str(last_error) if last_error else "All retry attempts exhausted",
        )

    def _categorize_error(self, error: Exception) -> str:
        """Categorize an error as network failure or API error.

        Args:
            error: The exception to categorize

        Returns:
            Error category string
        """
        from app.integrations.crawl4ai import (
            Crawl4AIAuthError,
            Crawl4AICircuitOpenError,
            Crawl4AIRateLimitError,
            Crawl4AITimeoutError,
        )

        if isinstance(error, Crawl4AITimeoutError):
            return "Network timeout"
        elif isinstance(error, Crawl4AIRateLimitError):
            return "API rate limit"
        elif isinstance(error, Crawl4AIAuthError):
            return "API authentication error"
        elif isinstance(error, Crawl4AICircuitOpenError):
            return "Circuit breaker open"
        elif "connection" in str(error).lower() or "network" in str(error).lower():
            return "Network failure"
        else:
            return "API error"
