"""Integrations layer - External service clients.

Integrations handle communication with external APIs and services.
They abstract the details of external service protocols.
"""

from app.integrations.claude import (
    DEFAULT_CATEGORIES,
    CategorizationResult,
    ClaudeAuthError,
    ClaudeCircuitOpenError,
    ClaudeClient,
    ClaudeError,
    ClaudeRateLimitError,
    ClaudeTimeoutError,
    CompletionResult,
    claude_client,
    close_claude,
    get_claude,
    init_claude,
)
from app.integrations.crawl4ai import (
    Crawl4AIAuthError,
    Crawl4AICircuitOpenError,
    Crawl4AIClient,
    Crawl4AIError,
    Crawl4AIRateLimitError,
    Crawl4AITimeoutError,
    CrawlOptions,
    CrawlResult,
    close_crawl4ai,
    crawl4ai_client,
    get_crawl4ai,
    init_crawl4ai,
)

__all__ = [
    # Crawl4AI Client
    "Crawl4AIClient",
    "crawl4ai_client",
    "init_crawl4ai",
    "close_crawl4ai",
    "get_crawl4ai",
    # Crawl4AI Data classes
    "CrawlResult",
    "CrawlOptions",
    # Crawl4AI Exceptions
    "Crawl4AIError",
    "Crawl4AITimeoutError",
    "Crawl4AIRateLimitError",
    "Crawl4AIAuthError",
    "Crawl4AICircuitOpenError",
    # Claude Client
    "ClaudeClient",
    "claude_client",
    "init_claude",
    "close_claude",
    "get_claude",
    # Claude Data classes
    "CategorizationResult",
    "CompletionResult",
    "DEFAULT_CATEGORIES",
    # Claude Exceptions
    "ClaudeError",
    "ClaudeTimeoutError",
    "ClaudeRateLimitError",
    "ClaudeAuthError",
    "ClaudeCircuitOpenError",
]
