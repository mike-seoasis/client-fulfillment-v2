"""Change detection algorithm for comparing crawl results.

Implements content hash comparison to detect changes between crawls:
- Content hash: Computed from semantic content (title, h1, meta_description, body text)
- Page comparison: Match by normalized URL, classify as new/removed/changed/unchanged
- Change summary: Aggregate statistics with significance detection

Significance threshold: 5+ new pages OR 10%+ content changes.

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
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger("change_detection")

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000

# Default significance thresholds
DEFAULT_NEW_PAGE_THRESHOLD = 5
DEFAULT_CHANGE_PERCENTAGE_THRESHOLD = 0.10  # 10%

# Maximum content length for hashing (to prevent memory issues)
MAX_CONTENT_LENGTH_FOR_HASH = 5000


class ChangeType(Enum):
    """Types of changes detected between crawls."""

    NEW = "new"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


@dataclass
class PageSnapshot:
    """Snapshot of a page at a point in time for comparison.

    Attributes:
        url: Normalized URL of the page
        content_hash: Hash of semantic content
        title: Page title (optional, for context in reports)
        page_id: Database page ID (optional)
    """

    url: str
    content_hash: str | None
    title: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "content_hash": self.content_hash,
            "title": self.title[:100] if self.title else None,
            "page_id": self.page_id,
        }


@dataclass
class PageChange:
    """Represents a detected change for a single page.

    Attributes:
        url: Normalized URL of the page
        change_type: Type of change (new, removed, changed, unchanged)
        old_hash: Previous content hash (for changed/removed)
        new_hash: New content hash (for new/changed)
        title: Page title (optional)
        page_id: Database page ID (optional)
    """

    url: str
    change_type: ChangeType
    old_hash: str | None = None
    new_hash: str | None = None
    title: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "change_type": self.change_type.value,
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "title": self.title[:100] if self.title else None,
            "page_id": self.page_id,
        }


@dataclass
class ChangeSummary:
    """Summary of changes detected between two crawls.

    Attributes:
        crawl_id: ID of the new crawl
        compared_to: ID of the previous crawl being compared to
        new_pages: Count of new pages found
        removed_pages: Count of pages no longer present
        changed_pages: Count of pages with content changes
        unchanged_pages: Count of pages without changes
        new_page_urls: List of URLs for new pages
        removed_page_urls: List of URLs for removed pages
        changed_page_urls: List of URLs for changed pages
        is_significant: Whether changes meet significance threshold
        changes: Detailed list of all page changes
        computed_at: When the comparison was performed
    """

    crawl_id: str
    compared_to: str
    new_pages: int = 0
    removed_pages: int = 0
    changed_pages: int = 0
    unchanged_pages: int = 0
    new_page_urls: list[str] = field(default_factory=list)
    removed_page_urls: list[str] = field(default_factory=list)
    changed_page_urls: list[str] = field(default_factory=list)
    is_significant: bool = False
    changes: list[PageChange] = field(default_factory=list)
    computed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Set computed_at if not provided."""
        if self.computed_at is None:
            from datetime import UTC

            self.computed_at = datetime.now(UTC)

    @property
    def total_pages(self) -> int:
        """Total pages in the new crawl."""
        return self.new_pages + self.changed_pages + self.unchanged_pages

    @property
    def total_changes(self) -> int:
        """Total number of changes (new + removed + changed)."""
        return self.new_pages + self.removed_pages + self.changed_pages

    @property
    def change_percentage(self) -> float:
        """Percentage of pages that changed (for pages that existed in both crawls)."""
        comparable_pages = self.changed_pages + self.unchanged_pages
        if comparable_pages == 0:
            return 0.0
        return self.changed_pages / comparable_pages

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization.

        Matches the JSON schema from the spec.
        """
        return {
            "crawl_id": self.crawl_id,
            "compared_to": self.compared_to,
            "summary": {
                "new_pages": self.new_pages,
                "removed_pages": self.removed_pages,
                "changed_pages": self.changed_pages,
                "unchanged_pages": self.unchanged_pages,
            },
            "new_page_urls": self.new_page_urls[:100],  # Limit for large changes
            "removed_page_urls": self.removed_page_urls[:100],
            "changed_page_urls": self.changed_page_urls[:100],
            "is_significant": self.is_significant,
            "computed_at": self.computed_at.isoformat() if self.computed_at else None,
            "total_pages": self.total_pages,
            "total_changes": self.total_changes,
            "change_percentage": round(self.change_percentage, 4),
        }


class ContentHasher:
    """Computes content hashes for change detection.

    Creates semantic content hashes from page content fields:
    - title: Page title
    - h1: Primary heading
    - meta_description: Meta description
    - body_text: First N characters of body content

    Uses MD5 for fast comparison (not cryptographic security).

    Example:
        hasher = ContentHasher()
        hash1 = hasher.compute_hash(
            title="Product Name",
            h1="Product Name",
            meta_description="Buy our product",
            body_text="Product details...",
        )
    """

    def __init__(
        self,
        max_content_length: int = MAX_CONTENT_LENGTH_FOR_HASH,
        include_whitespace: bool = False,
    ) -> None:
        """Initialize the content hasher.

        Args:
            max_content_length: Maximum body text length to include in hash
            include_whitespace: If False, normalize whitespace before hashing
        """
        logger.debug(
            "ContentHasher.__init__ called",
            extra={
                "max_content_length": max_content_length,
                "include_whitespace": include_whitespace,
            },
        )
        self._max_content_length = max_content_length
        self._include_whitespace = include_whitespace

    @property
    def max_content_length(self) -> int:
        """Get the maximum content length for hashing."""
        return self._max_content_length

    def _normalize_text(self, text: str | None) -> str:
        """Normalize text for consistent hashing.

        Args:
            text: Text to normalize

        Returns:
            Normalized text (lowercased, whitespace normalized)
        """
        if not text:
            return ""

        normalized = text.strip().lower()

        if not self._include_whitespace:
            # Normalize all whitespace to single spaces
            import re

            normalized = re.sub(r"\s+", " ", normalized)

        return normalized

    def compute_hash(
        self,
        title: str | None = None,
        h1: str | None = None,
        meta_description: str | None = None,
        body_text: str | None = None,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> str:
        """Compute a content hash from page content fields.

        The hash is computed from a normalized concatenation of:
        title|h1|meta_description|body_text[:max_content_length]

        Args:
            title: Page title
            h1: Primary heading (H1)
            meta_description: Meta description content
            body_text: Body text content
            project_id: Optional project ID for logging
            page_id: Optional page ID for logging

        Returns:
            MD5 hex digest of the content
        """
        start_time = time.monotonic()
        logger.debug(
            "compute_hash() called",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "has_title": title is not None,
                "has_h1": h1 is not None,
                "has_meta": meta_description is not None,
                "body_length": len(body_text) if body_text else 0,
            },
        )

        try:
            # Normalize each component
            norm_title = self._normalize_text(title)
            norm_h1 = self._normalize_text(h1)
            norm_meta = self._normalize_text(meta_description)

            # Truncate and normalize body text
            truncated_body = ""
            if body_text:
                truncated_body = self._normalize_text(
                    body_text[: self._max_content_length]
                )

            # Create content string with delimiter
            content = f"{norm_title}|{norm_h1}|{norm_meta}|{truncated_body}"

            # Compute MD5 hash
            content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Content hash computed",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "content_hash": content_hash,
                    "content_length": len(content),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow content hash computation",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "content_length": len(content),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return content_hash

        except Exception as e:
            logger.error(
                "Content hash computation failed",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise

    def compute_hash_from_dict(
        self,
        data: dict[str, Any],
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> str:
        """Compute content hash from a dictionary with content fields.

        Extracts title, h1 (or first heading), meta_description, and body_text
        from the provided dictionary.

        Args:
            data: Dictionary with content fields
            project_id: Optional project ID for logging
            page_id: Optional page ID for logging

        Returns:
            MD5 hex digest of the content
        """
        logger.debug(
            "compute_hash_from_dict() called",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "keys": list(data.keys())[:10],
            },
        )

        # Extract fields with fallbacks for common naming variations
        title = data.get("title") or data.get("page_title")
        h1 = data.get("h1") or data.get("heading") or data.get("main_heading")

        # Check for headings list
        if not h1 and "headings" in data:
            headings = data.get("headings", [])
            if headings and len(headings) > 0:
                h1 = headings[0] if isinstance(headings[0], str) else str(headings[0])

        meta_description = (
            data.get("meta_description")
            or data.get("description")
            or data.get("meta_desc")
        )

        body_text = (
            data.get("body_text")
            or data.get("content")
            or data.get("text")
            or data.get("markdown")
        )

        return self.compute_hash(
            title=title,
            h1=h1,
            meta_description=meta_description,
            body_text=body_text,
            project_id=project_id,
            page_id=page_id,
        )


class ChangeDetector:
    """Detects changes between two sets of crawled pages.

    Compares page snapshots by normalized URL and content hash to identify:
    - New pages: Present in new crawl but not in previous
    - Removed pages: Present in previous crawl but not in new
    - Changed pages: Present in both but with different content hash
    - Unchanged pages: Present in both with same content hash

    Example:
        detector = ChangeDetector()

        # Previous crawl results
        previous = [
            PageSnapshot(url="https://example.com/page1", content_hash="abc123"),
            PageSnapshot(url="https://example.com/page2", content_hash="def456"),
        ]

        # New crawl results
        current = [
            PageSnapshot(url="https://example.com/page1", content_hash="abc123"),  # unchanged
            PageSnapshot(url="https://example.com/page3", content_hash="ghi789"),  # new
        ]

        summary = detector.compare(
            crawl_id="new-crawl-id",
            previous_crawl_id="prev-crawl-id",
            previous_pages=previous,
            current_pages=current,
        )

        print(summary.to_dict())
    """

    def __init__(
        self,
        new_page_threshold: int = DEFAULT_NEW_PAGE_THRESHOLD,
        change_percentage_threshold: float = DEFAULT_CHANGE_PERCENTAGE_THRESHOLD,
    ) -> None:
        """Initialize the change detector.

        Args:
            new_page_threshold: Number of new pages to trigger significance
            change_percentage_threshold: Percentage of changed pages to trigger significance
        """
        logger.debug(
            "ChangeDetector.__init__ called",
            extra={
                "new_page_threshold": new_page_threshold,
                "change_percentage_threshold": change_percentage_threshold,
            },
        )

        if new_page_threshold < 0:
            logger.warning(
                "Validation failed: negative new_page_threshold",
                extra={
                    "field": "new_page_threshold",
                    "value": new_page_threshold,
                },
            )
            raise ValueError("new_page_threshold must be non-negative")

        if not 0.0 <= change_percentage_threshold <= 1.0:
            logger.warning(
                "Validation failed: invalid change_percentage_threshold",
                extra={
                    "field": "change_percentage_threshold",
                    "value": change_percentage_threshold,
                },
            )
            raise ValueError("change_percentage_threshold must be between 0.0 and 1.0")

        self._new_page_threshold = new_page_threshold
        self._change_percentage_threshold = change_percentage_threshold

    @property
    def new_page_threshold(self) -> int:
        """Get the new page threshold for significance."""
        return self._new_page_threshold

    @property
    def change_percentage_threshold(self) -> float:
        """Get the change percentage threshold for significance."""
        return self._change_percentage_threshold

    def compare(
        self,
        crawl_id: str,
        previous_crawl_id: str,
        previous_pages: list[PageSnapshot],
        current_pages: list[PageSnapshot],
        project_id: str | None = None,
    ) -> ChangeSummary:
        """Compare two sets of crawled pages to detect changes.

        Args:
            crawl_id: ID of the current/new crawl
            previous_crawl_id: ID of the previous crawl
            previous_pages: Page snapshots from previous crawl
            current_pages: Page snapshots from current crawl
            project_id: Optional project ID for logging

        Returns:
            ChangeSummary with detected changes
        """
        start_time = time.monotonic()
        logger.debug(
            "compare() called",
            extra={
                "project_id": project_id,
                "crawl_id": crawl_id,
                "previous_crawl_id": previous_crawl_id,
                "previous_page_count": len(previous_pages),
                "current_page_count": len(current_pages),
            },
        )

        try:
            # Index previous pages by URL
            prev_by_url: dict[str, PageSnapshot] = {p.url: p for p in previous_pages}
            curr_by_url: dict[str, PageSnapshot] = {p.url: p for p in current_pages}

            prev_urls = set(prev_by_url.keys())
            curr_urls = set(curr_by_url.keys())

            # Calculate change sets
            new_urls = curr_urls - prev_urls
            removed_urls = prev_urls - curr_urls
            common_urls = prev_urls & curr_urls

            # Classify common URLs as changed or unchanged
            changed_urls: set[str] = set()
            unchanged_urls: set[str] = set()

            for url in common_urls:
                prev_hash = prev_by_url[url].content_hash
                curr_hash = curr_by_url[url].content_hash

                if prev_hash != curr_hash:
                    changed_urls.add(url)
                else:
                    unchanged_urls.add(url)

            # Build changes list
            changes: list[PageChange] = []

            # New pages
            for url in sorted(new_urls):
                page = curr_by_url[url]
                changes.append(
                    PageChange(
                        url=url,
                        change_type=ChangeType.NEW,
                        new_hash=page.content_hash,
                        title=page.title,
                        page_id=page.page_id,
                    )
                )

            # Removed pages
            for url in sorted(removed_urls):
                page = prev_by_url[url]
                changes.append(
                    PageChange(
                        url=url,
                        change_type=ChangeType.REMOVED,
                        old_hash=page.content_hash,
                        title=page.title,
                        page_id=page.page_id,
                    )
                )

            # Changed pages
            for url in sorted(changed_urls):
                prev_page = prev_by_url[url]
                curr_page = curr_by_url[url]
                changes.append(
                    PageChange(
                        url=url,
                        change_type=ChangeType.CHANGED,
                        old_hash=prev_page.content_hash,
                        new_hash=curr_page.content_hash,
                        title=curr_page.title,
                        page_id=curr_page.page_id,
                    )
                )

            # Unchanged pages (not typically needed in detail but track for completeness)
            for url in sorted(unchanged_urls):
                curr_page = curr_by_url[url]
                changes.append(
                    PageChange(
                        url=url,
                        change_type=ChangeType.UNCHANGED,
                        old_hash=curr_page.content_hash,
                        new_hash=curr_page.content_hash,
                        title=curr_page.title,
                        page_id=curr_page.page_id,
                    )
                )

            # Create summary
            summary = ChangeSummary(
                crawl_id=crawl_id,
                compared_to=previous_crawl_id,
                new_pages=len(new_urls),
                removed_pages=len(removed_urls),
                changed_pages=len(changed_urls),
                unchanged_pages=len(unchanged_urls),
                new_page_urls=sorted(new_urls),
                removed_page_urls=sorted(removed_urls),
                changed_page_urls=sorted(changed_urls),
                changes=changes,
            )

            # Determine significance
            summary.is_significant = self._is_significant(summary)

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log state transition (comparison completed)
            logger.info(
                "Change detection completed",
                extra={
                    "project_id": project_id,
                    "crawl_id": crawl_id,
                    "previous_crawl_id": previous_crawl_id,
                    "new_pages": summary.new_pages,
                    "removed_pages": summary.removed_pages,
                    "changed_pages": summary.changed_pages,
                    "unchanged_pages": summary.unchanged_pages,
                    "is_significant": summary.is_significant,
                    "change_percentage": round(summary.change_percentage, 4),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow change detection",
                    extra={
                        "project_id": project_id,
                        "crawl_id": crawl_id,
                        "page_count": len(previous_pages) + len(current_pages),
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return summary

        except Exception as e:
            logger.error(
                "Change detection failed",
                extra={
                    "project_id": project_id,
                    "crawl_id": crawl_id,
                    "previous_crawl_id": previous_crawl_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            raise

    def _is_significant(self, summary: ChangeSummary) -> bool:
        """Determine if changes are significant.

        Significant means:
        - 5+ new pages, OR
        - 10%+ of existing pages changed content

        Args:
            summary: The change summary to evaluate

        Returns:
            True if changes are significant
        """
        # Check new page threshold
        if summary.new_pages >= self._new_page_threshold:
            logger.debug(
                "Changes significant: new page threshold met",
                extra={
                    "new_pages": summary.new_pages,
                    "threshold": self._new_page_threshold,
                },
            )
            return True

        # Check change percentage threshold
        if summary.change_percentage >= self._change_percentage_threshold:
            logger.debug(
                "Changes significant: change percentage threshold met",
                extra={
                    "change_percentage": round(summary.change_percentage, 4),
                    "threshold": self._change_percentage_threshold,
                },
            )
            return True

        return False

    def compare_from_dicts(
        self,
        crawl_id: str,
        previous_crawl_id: str,
        previous_pages: list[dict[str, Any]],
        current_pages: list[dict[str, Any]],
        url_key: str = "normalized_url",
        hash_key: str = "content_hash",
        title_key: str = "title",
        id_key: str = "id",
        project_id: str | None = None,
    ) -> ChangeSummary:
        """Compare pages from dictionary representations.

        Convenience method for comparing pages from database query results
        or API responses.

        Args:
            crawl_id: ID of the current crawl
            previous_crawl_id: ID of the previous crawl
            previous_pages: Previous page data as dicts
            current_pages: Current page data as dicts
            url_key: Key for URL in dicts
            hash_key: Key for content hash in dicts
            title_key: Key for title in dicts
            id_key: Key for page ID in dicts
            project_id: Optional project ID for logging

        Returns:
            ChangeSummary with detected changes
        """
        logger.debug(
            "compare_from_dicts() called",
            extra={
                "project_id": project_id,
                "crawl_id": crawl_id,
                "previous_page_count": len(previous_pages),
                "current_page_count": len(current_pages),
            },
        )

        def to_snapshot(d: dict[str, Any]) -> PageSnapshot:
            return PageSnapshot(
                url=d.get(url_key, ""),
                content_hash=d.get(hash_key),
                title=d.get(title_key),
                page_id=d.get(id_key),
            )

        prev_snapshots = [to_snapshot(p) for p in previous_pages if p.get(url_key)]
        curr_snapshots = [to_snapshot(p) for p in current_pages if p.get(url_key)]

        return self.compare(
            crawl_id=crawl_id,
            previous_crawl_id=previous_crawl_id,
            previous_pages=prev_snapshots,
            current_pages=curr_snapshots,
            project_id=project_id,
        )


# Default instances for convenience
_default_hasher: ContentHasher | None = None
_default_detector: ChangeDetector | None = None


def get_content_hasher() -> ContentHasher:
    """Get the default ContentHasher instance (singleton).

    Returns:
        Default ContentHasher instance.
    """
    global _default_hasher
    if _default_hasher is None:
        _default_hasher = ContentHasher()
    return _default_hasher


def get_change_detector() -> ChangeDetector:
    """Get the default ChangeDetector instance (singleton).

    Returns:
        Default ChangeDetector instance.
    """
    global _default_detector
    if _default_detector is None:
        _default_detector = ChangeDetector()
    return _default_detector


def compute_content_hash(
    title: str | None = None,
    h1: str | None = None,
    meta_description: str | None = None,
    body_text: str | None = None,
    project_id: str | None = None,
    page_id: str | None = None,
) -> str:
    """Convenience function to compute content hash.

    Args:
        title: Page title
        h1: Primary heading (H1)
        meta_description: Meta description content
        body_text: Body text content
        project_id: Optional project ID for logging
        page_id: Optional page ID for logging

    Returns:
        MD5 hex digest of the content

    Example:
        >>> hash = compute_content_hash(
        ...     title="My Product",
        ...     h1="My Product",
        ...     meta_description="Buy my product today",
        ...     body_text="Product details and description...",
        ... )
        >>> print(hash)
        'a1b2c3d4e5f6...'
    """
    hasher = get_content_hasher()
    return hasher.compute_hash(
        title=title,
        h1=h1,
        meta_description=meta_description,
        body_text=body_text,
        project_id=project_id,
        page_id=page_id,
    )


def detect_changes(
    crawl_id: str,
    previous_crawl_id: str,
    previous_pages: list[PageSnapshot],
    current_pages: list[PageSnapshot],
    project_id: str | None = None,
) -> ChangeSummary:
    """Convenience function to detect changes between crawls.

    Args:
        crawl_id: ID of the current crawl
        previous_crawl_id: ID of the previous crawl
        previous_pages: Page snapshots from previous crawl
        current_pages: Page snapshots from current crawl
        project_id: Optional project ID for logging

    Returns:
        ChangeSummary with detected changes

    Example:
        >>> previous = [
        ...     PageSnapshot(url="https://example.com/a", content_hash="hash1"),
        ...     PageSnapshot(url="https://example.com/b", content_hash="hash2"),
        ... ]
        >>> current = [
        ...     PageSnapshot(url="https://example.com/a", content_hash="hash1"),  # unchanged
        ...     PageSnapshot(url="https://example.com/c", content_hash="hash3"),  # new
        ... ]
        >>> summary = detect_changes("crawl2", "crawl1", previous, current)
        >>> print(summary.new_pages)
        1
        >>> print(summary.removed_pages)
        1
    """
    detector = get_change_detector()
    return detector.compare(
        crawl_id=crawl_id,
        previous_crawl_id=previous_crawl_id,
        previous_pages=previous_pages,
        current_pages=current_pages,
        project_id=project_id,
    )


# Valid change types for external validation
VALID_CHANGE_TYPES = frozenset(c.value for c in ChangeType)
