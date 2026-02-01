"""Utility modules for the application.

This package contains shared utility functions and classes.
"""

from app.utils.change_detection import (
    VALID_CHANGE_TYPES,
    ChangeDetector,
    ChangeSummary,
    ChangeType,
    ContentHasher,
    PageChange,
    PageSnapshot,
    compute_content_hash,
    detect_changes,
    get_change_detector,
    get_content_hasher,
)
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
from app.utils.document_parser import (
    DocumentCorruptedError,
    DocumentFormat,
    DocumentMetadata,
    DocumentParser,
    DocumentParserError,
    DocumentParseResult,
    FileTooLargeError,
    UnsupportedFormatError,
    get_document_parser,
    parse_document,
    parse_document_file,
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
    # Document parsing
    "DocumentFormat",
    "DocumentMetadata",
    "DocumentParseResult",
    "DocumentParser",
    "DocumentParserError",
    "UnsupportedFormatError",
    "FileTooLargeError",
    "DocumentCorruptedError",
    "get_document_parser",
    "parse_document",
    "parse_document_file",
    # Change detection
    "ChangeType",
    "PageSnapshot",
    "PageChange",
    "ChangeSummary",
    "ContentHasher",
    "ChangeDetector",
    "get_content_hasher",
    "get_change_detector",
    "compute_content_hash",
    "detect_changes",
    "VALID_CHANGE_TYPES",
]
