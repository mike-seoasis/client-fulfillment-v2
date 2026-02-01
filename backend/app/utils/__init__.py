"""Utility modules for the application.

This package contains shared utility functions and classes.
"""

from app.utils.content_signals import (
    VALID_SIGNAL_TYPES,
    ContentAnalysis,
    ContentSignal,
    ContentSignalDetector,
    SignalPattern,
    SignalType,
    analyze_content_signals,
    get_content_signal_detector,
)
from app.utils.crawl_queue import (
    CrawlQueueLogger,
    QueuedURL,
    URLPriority,
    URLPriorityQueue,
    crawl_queue_logger,
)
from app.utils.url import (
    URLNormalizationOptions,
    URLNormalizer,
    normalize_url,
)
from app.utils.url_categorizer import (
    VALID_PAGE_CATEGORIES,
    CategoryRule,
    URLCategorizer,
    categorize_url,
    get_url_categorizer,
)

__all__ = [
    # URL normalization
    "normalize_url",
    "URLNormalizer",
    "URLNormalizationOptions",
    # URL categorization
    "categorize_url",
    "CategoryRule",
    "URLCategorizer",
    "get_url_categorizer",
    "VALID_PAGE_CATEGORIES",
    # Content signal detection
    "SignalType",
    "ContentSignal",
    "ContentAnalysis",
    "SignalPattern",
    "ContentSignalDetector",
    "get_content_signal_detector",
    "analyze_content_signals",
    "VALID_SIGNAL_TYPES",
    # Crawl queue
    "URLPriority",
    "URLPriorityQueue",
    "QueuedURL",
    "CrawlQueueLogger",
    "crawl_queue_logger",
]
