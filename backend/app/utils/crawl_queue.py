"""Priority queue for URL crawling with configurable priority levels.

URLs are prioritized for crawling based on their type:
- Priority 0 (HOMEPAGE): The site's homepage/start URL - crawl first
- Priority 1 (INCLUDE): URLs matching include patterns - crawl second
- Priority 2 (OTHER): All other discovered URLs - crawl last

This ensures the most important pages are crawled first within depth/page limits.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Log validation failures with field names and rejected values
- Log state transitions (queue additions/removals) at INFO level
"""

import heapq
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import IntEnum
from fnmatch import fnmatch
from typing import Any
from urllib.parse import urlparse

from app.core.logging import get_logger
from app.utils.url import URLNormalizationOptions, URLNormalizer

logger = get_logger("crawl_queue")


class URLPriority(IntEnum):
    """URL priority levels for crawl ordering.

    Lower values = higher priority (processed first).
    """
    HOMEPAGE = 0  # Start URL / homepage - highest priority
    INCLUDE = 1   # URLs matching include patterns
    OTHER = 2     # All other discovered URLs


@dataclass(order=True)
class QueuedURL:
    """A URL in the crawl queue with priority and metadata.

    Uses dataclass ordering for heap operations (compares by priority first,
    then by depth, then by timestamp to ensure FIFO within same priority/depth).
    """
    priority: int
    depth: int
    timestamp: float = field(compare=True)  # For FIFO within same priority/depth
    url: str = field(compare=False)
    normalized_url: str = field(compare=False)
    parent_url: str | None = field(compare=False, default=None)

    def __post_init__(self) -> None:
        """Log queue item creation at DEBUG level."""
        logger.debug(
            "QueuedURL created",
            extra={
                "url": self.url[:200],
                "normalized_url": self.normalized_url[:200],
                "priority": self.priority,
                "priority_name": URLPriority(self.priority).name,
                "depth": self.depth,
            },
        )


class CrawlQueueLogger:
    """Logger for crawl queue operations with comprehensive logging."""

    def __init__(self) -> None:
        self.logger = get_logger("crawl_queue")

    def queue_initialized(
        self,
        start_url: str,
        include_patterns: list[str],
        exclude_patterns: list[str],
    ) -> None:
        """Log queue initialization at INFO level."""
        self.logger.info(
            "Crawl queue initialized",
            extra={
                "start_url": start_url[:200],
                "include_pattern_count": len(include_patterns),
                "exclude_pattern_count": len(exclude_patterns),
            },
        )

    def url_added(
        self,
        url: str,
        priority: URLPriority,
        depth: int,
        queue_size: int,
    ) -> None:
        """Log URL addition at DEBUG level."""
        self.logger.debug(
            "URL added to queue",
            extra={
                "url": url[:200],
                "priority": priority.value,
                "priority_name": priority.name,
                "depth": depth,
                "queue_size": queue_size,
            },
        )

    def url_popped(
        self,
        url: str,
        priority: URLPriority,
        depth: int,
        remaining_size: int,
    ) -> None:
        """Log URL removal at DEBUG level."""
        self.logger.debug(
            "URL popped from queue",
            extra={
                "url": url[:200],
                "priority": priority.value,
                "priority_name": priority.name,
                "depth": depth,
                "remaining_size": remaining_size,
            },
        )

    def url_skipped(
        self,
        url: str,
        reason: str,
        pattern: str | None = None,
    ) -> None:
        """Log skipped URL at DEBUG level."""
        self.logger.debug(
            f"URL skipped: {reason}",
            extra={
                "url": url[:200],
                "reason": reason,
                "pattern": pattern[:100] if pattern else None,
            },
        )

    def url_already_seen(self, url: str, normalized_url: str) -> None:
        """Log already-seen URL at DEBUG level."""
        self.logger.debug(
            "URL already seen, skipping",
            extra={
                "url": url[:200],
                "normalized_url": normalized_url[:200],
            },
        )

    def priority_determined(
        self,
        url: str,
        priority: URLPriority,
        is_homepage: bool,
        matched_include: bool,
    ) -> None:
        """Log priority determination at DEBUG level."""
        self.logger.debug(
            "URL priority determined",
            extra={
                "url": url[:200],
                "priority": priority.value,
                "priority_name": priority.name,
                "is_homepage": is_homepage,
                "matched_include_pattern": matched_include,
            },
        )

    def queue_stats(
        self,
        total_size: int,
        seen_count: int,
        priority_counts: dict[str, int],
    ) -> None:
        """Log queue statistics at INFO level."""
        self.logger.info(
            "Crawl queue statistics",
            extra={
                "queue_size": total_size,
                "urls_seen": seen_count,
                "priority_distribution": priority_counts,
            },
        )

    def validation_failure(
        self,
        field_name: str,
        rejected_value: str,
        reason: str,
    ) -> None:
        """Log validation failure at WARNING level."""
        self.logger.warning(
            "URL validation failed",
            extra={
                "field": field_name,
                "rejected_value": rejected_value[:200] if rejected_value else None,
                "reason": reason,
            },
        )

    def operation_error(
        self,
        operation: str,
        error: Exception,
        url: str | None = None,
    ) -> None:
        """Log operation error with full stack trace."""
        self.logger.error(
            f"Crawl queue operation failed: {operation}",
            extra={
                "operation": operation,
                "url": url[:200] if url else None,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
            exc_info=True,
        )


# Singleton logger instance
crawl_queue_logger = CrawlQueueLogger()


class URLPriorityQueue:
    """Priority queue for URL crawling.

    Manages a queue of URLs to crawl, prioritizing by:
    1. URL type (homepage > include patterns > other)
    2. Crawl depth (shallower first within same type)
    3. Discovery time (FIFO within same type/depth)

    Features:
    - Deduplication via normalized URLs
    - Pattern-based include/exclude filtering
    - Configurable priority assignment
    - Comprehensive logging for debugging

    Example usage:
        queue = URLPriorityQueue(
            start_url="https://example.com",
            include_patterns=["/**/products/*", "/**/services/*"],
            exclude_patterns=["/admin/*", "/api/*"],
        )

        # Add discovered URLs
        queue.add("https://example.com/products/item1", parent_url="https://example.com")
        queue.add("https://example.com/about", parent_url="https://example.com")

        # Process in priority order
        while not queue.empty():
            queued = queue.pop()
            # crawl queued.url...
    """

    def __init__(
        self,
        start_url: str,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        normalizer_options: URLNormalizationOptions | None = None,
    ) -> None:
        """Initialize the priority queue.

        Args:
            start_url: The homepage/starting URL (priority 0)
            include_patterns: Glob patterns for priority 1 URLs (e.g., "/**/products/*")
            exclude_patterns: Glob patterns to exclude (never added to queue)
            normalizer_options: URL normalization options

        Raises:
            ValueError: If start_url is invalid
        """
        logger.debug(
            "URLPriorityQueue.__init__ called",
            extra={
                "start_url": start_url[:200] if start_url else "",
                "include_pattern_count": len(include_patterns) if include_patterns else 0,
                "exclude_pattern_count": len(exclude_patterns) if exclude_patterns else 0,
            },
        )

        if not start_url or not start_url.strip():
            crawl_queue_logger.validation_failure("start_url", repr(start_url), "URL cannot be empty")
            raise ValueError("start_url cannot be empty")

        self._start_url = start_url.strip()
        self._include_patterns = include_patterns or []
        self._exclude_patterns = exclude_patterns or []

        # URL normalizer for deduplication
        self._normalizer = URLNormalizer(normalizer_options)

        try:
            self._normalized_start_url = self._normalizer.normalize(self._start_url)
        except ValueError as e:
            crawl_queue_logger.validation_failure("start_url", start_url[:200], str(e))
            raise

        # Parse start URL to extract base domain for same-domain checks
        parsed_start = urlparse(self._normalized_start_url)
        self._start_domain = parsed_start.netloc
        self._start_scheme = parsed_start.scheme

        # Priority queue (heap) and seen set
        self._heap: list[QueuedURL] = []
        self._seen: set[str] = set()

        # Add start URL as first item
        self._add_internal(
            url=self._start_url,
            normalized_url=self._normalized_start_url,
            priority=URLPriority.HOMEPAGE,
            depth=0,
            parent_url=None,
        )

        crawl_queue_logger.queue_initialized(
            self._start_url,
            self._include_patterns,
            self._exclude_patterns,
        )

    @property
    def start_url(self) -> str:
        """Get the start URL."""
        return self._start_url

    @property
    def start_domain(self) -> str:
        """Get the start domain (for same-domain checks)."""
        return self._start_domain

    def _add_internal(
        self,
        url: str,
        normalized_url: str,
        priority: URLPriority,
        depth: int,
        parent_url: str | None,
    ) -> None:
        """Internal method to add URL to heap."""
        queued = QueuedURL(
            priority=priority.value,
            depth=depth,
            timestamp=time.monotonic(),
            url=url,
            normalized_url=normalized_url,
            parent_url=parent_url,
        )
        heapq.heappush(self._heap, queued)
        self._seen.add(normalized_url)

        crawl_queue_logger.url_added(url, priority, depth, len(self._heap))

    def _determine_priority(self, url: str, path: str) -> URLPriority:
        """Determine the priority for a URL based on patterns.

        Args:
            url: The full URL
            path: The URL path component

        Returns:
            URLPriority value
        """
        # Check if it's the homepage
        is_homepage = self._normalizer.is_same_page(url, self._start_url)
        if is_homepage:
            crawl_queue_logger.priority_determined(url, URLPriority.HOMEPAGE, True, False)
            return URLPriority.HOMEPAGE

        # Check include patterns
        for pattern in self._include_patterns:
            if fnmatch(path, pattern):
                crawl_queue_logger.priority_determined(url, URLPriority.INCLUDE, False, True)
                return URLPriority.INCLUDE

        # Default to OTHER
        crawl_queue_logger.priority_determined(url, URLPriority.OTHER, False, False)
        return URLPriority.OTHER

    def _is_excluded(self, path: str) -> tuple[bool, str | None]:
        """Check if URL path matches any exclude pattern.

        Args:
            path: The URL path component

        Returns:
            Tuple of (is_excluded, matching_pattern)
        """
        for pattern in self._exclude_patterns:
            if fnmatch(path, pattern):
                return True, pattern
        return False, None

    def _is_same_domain(self, url: str) -> bool:
        """Check if URL is on the same domain as start URL.

        Args:
            url: URL to check

        Returns:
            True if same domain
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc == self._start_domain
        except Exception:
            return False

    def add(
        self,
        url: str,
        parent_url: str | None = None,
        depth: int | None = None,
    ) -> bool:
        """Add a URL to the queue if not already seen and not excluded.

        Args:
            url: URL to add
            parent_url: URL of the page where this URL was discovered
            depth: Crawl depth (auto-calculated from parent if not provided)

        Returns:
            True if URL was added, False if skipped

        Raises:
            ValueError: If URL is invalid
        """
        logger.debug(
            "add() called",
            extra={
                "url": url[:200] if url else "",
                "parent_url": parent_url[:200] if parent_url else None,
                "depth": depth,
            },
        )

        if not url or not url.strip():
            crawl_queue_logger.validation_failure("url", repr(url), "URL cannot be empty")
            return False

        url = url.strip()

        # Normalize URL
        try:
            normalized_url = self._normalizer.normalize(url)
        except ValueError as e:
            crawl_queue_logger.url_skipped(url, f"Invalid URL: {e}")
            return False

        # Check if already seen
        if normalized_url in self._seen:
            crawl_queue_logger.url_already_seen(url, normalized_url)
            return False

        # Check if same domain (only crawl same domain by default)
        if not self._is_same_domain(url):
            crawl_queue_logger.url_skipped(url, "Different domain", self._start_domain)
            return False

        # Check exclude patterns
        parsed = urlparse(normalized_url)
        path = parsed.path or "/"

        is_excluded, pattern = self._is_excluded(path)
        if is_excluded:
            crawl_queue_logger.url_skipped(url, "Matched exclude pattern", pattern)
            # Still mark as seen to avoid re-checking
            self._seen.add(normalized_url)
            return False

        # Determine priority
        priority = self._determine_priority(url, path)

        # Calculate depth
        if depth is None:
            depth = 1  # Default depth for discovered URLs

        # Add to queue
        self._add_internal(url, normalized_url, priority, depth, parent_url)

        return True

    def add_many(
        self,
        urls: list[str],
        parent_url: str | None = None,
        depth: int | None = None,
    ) -> int:
        """Add multiple URLs to the queue.

        Args:
            urls: List of URLs to add
            parent_url: URL of the page where URLs were discovered
            depth: Crawl depth for all URLs

        Returns:
            Number of URLs actually added
        """
        logger.debug(
            "add_many() called",
            extra={
                "url_count": len(urls),
                "parent_url": parent_url[:200] if parent_url else None,
                "depth": depth,
            },
        )

        added = 0
        for url in urls:
            if self.add(url, parent_url=parent_url, depth=depth):
                added += 1

        logger.debug(
            "add_many() completed",
            extra={
                "urls_provided": len(urls),
                "urls_added": added,
                "urls_skipped": len(urls) - added,
            },
        )

        return added

    def pop(self) -> QueuedURL | None:
        """Remove and return the highest-priority URL.

        Returns:
            QueuedURL with highest priority, or None if queue is empty
        """
        if not self._heap:
            logger.debug("pop() called on empty queue")
            return None

        queued = heapq.heappop(self._heap)

        crawl_queue_logger.url_popped(
            queued.url,
            URLPriority(queued.priority),
            queued.depth,
            len(self._heap),
        )

        return queued

    def peek(self) -> QueuedURL | None:
        """View the highest-priority URL without removing it.

        Returns:
            QueuedURL with highest priority, or None if queue is empty
        """
        if not self._heap:
            return None
        return self._heap[0]

    def empty(self) -> bool:
        """Check if the queue is empty.

        Returns:
            True if queue has no URLs
        """
        return len(self._heap) == 0

    def __len__(self) -> int:
        """Get number of URLs in queue."""
        return len(self._heap)

    def __bool__(self) -> bool:
        """Check if queue has items."""
        return len(self._heap) > 0

    def seen_count(self) -> int:
        """Get number of unique URLs seen (including already crawled)."""
        return len(self._seen)

    def has_seen(self, url: str) -> bool:
        """Check if a URL has already been seen.

        Args:
            url: URL to check

        Returns:
            True if URL has been seen
        """
        try:
            normalized = self._normalizer.normalize(url)
            return normalized in self._seen
        except ValueError:
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dict with queue stats
        """
        # Count by priority
        priority_counts: dict[str, int] = {
            "homepage": 0,
            "include": 0,
            "other": 0,
        }

        for queued in self._heap:
            if queued.priority == URLPriority.HOMEPAGE:
                priority_counts["homepage"] += 1
            elif queued.priority == URLPriority.INCLUDE:
                priority_counts["include"] += 1
            else:
                priority_counts["other"] += 1

        stats = {
            "queue_size": len(self._heap),
            "seen_count": len(self._seen),
            "priority_counts": priority_counts,
            "start_url": self._start_url,
            "start_domain": self._start_domain,
            "include_patterns": self._include_patterns,
            "exclude_patterns": self._exclude_patterns,
        }

        crawl_queue_logger.queue_stats(
            len(self._heap),
            len(self._seen),
            priority_counts,
        )

        return stats

    def __iter__(self) -> Iterator[QueuedURL]:
        """Iterate over queue in priority order (destructive - empties queue)."""
        while self._heap:
            item = self.pop()
            if item:
                yield item

    def clear(self) -> None:
        """Clear the queue (but keep seen set)."""
        logger.debug("clear() called", extra={"items_cleared": len(self._heap)})
        self._heap.clear()

    def reset(self) -> None:
        """Reset the queue completely (clear queue and seen set)."""
        logger.debug(
            "reset() called",
            extra={
                "queue_cleared": len(self._heap),
                "seen_cleared": len(self._seen),
            },
        )
        self._heap.clear()
        self._seen.clear()

        # Re-add start URL
        self._add_internal(
            url=self._start_url,
            normalized_url=self._normalized_start_url,
            priority=URLPriority.HOMEPAGE,
            depth=0,
            parent_url=None,
        )
