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
from app.integrations.keywords_everywhere import (
    KeywordData,
    KeywordDataResult,
    KeywordsEverywhereAuthError,
    KeywordsEverywhereCircuitOpenError,
    KeywordsEverywhereClient,
    KeywordsEverywhereError,
    KeywordsEverywhereRateLimitError,
    KeywordsEverywhereTimeoutError,
    close_keywords_everywhere,
    get_keywords_everywhere,
    init_keywords_everywhere,
    keywords_everywhere_client,
)
from app.integrations.perplexity import (
    CompletionResult as PerplexityCompletionResult,
)
from app.integrations.perplexity import (
    PerplexityAuthError,
    PerplexityCircuitOpenError,
    PerplexityClient,
    PerplexityError,
    PerplexityRateLimitError,
    PerplexityTimeoutError,
    WebsiteAnalysisResult,
    close_perplexity,
    get_perplexity,
    init_perplexity,
    perplexity_client,
)
from app.integrations.s3 import (
    S3AuthError,
    S3CircuitOpenError,
    S3Client,
    S3ConnectionError,
    S3Error,
    S3NotFoundError,
    S3TimeoutError,
    close_s3,
    get_s3,
    init_s3,
    s3_client,
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
    # Perplexity Client
    "PerplexityClient",
    "perplexity_client",
    "init_perplexity",
    "close_perplexity",
    "get_perplexity",
    # Perplexity Data classes
    "WebsiteAnalysisResult",
    "PerplexityCompletionResult",
    # Perplexity Exceptions
    "PerplexityError",
    "PerplexityTimeoutError",
    "PerplexityRateLimitError",
    "PerplexityAuthError",
    "PerplexityCircuitOpenError",
    # Keywords Everywhere Client
    "KeywordsEverywhereClient",
    "keywords_everywhere_client",
    "init_keywords_everywhere",
    "close_keywords_everywhere",
    "get_keywords_everywhere",
    # Keywords Everywhere Data classes
    "KeywordData",
    "KeywordDataResult",
    # Keywords Everywhere Exceptions
    "KeywordsEverywhereError",
    "KeywordsEverywhereTimeoutError",
    "KeywordsEverywhereRateLimitError",
    "KeywordsEverywhereAuthError",
    "KeywordsEverywhereCircuitOpenError",
    # S3 Client
    "S3Client",
    "s3_client",
    "init_s3",
    "close_s3",
    "get_s3",
    # S3 Exceptions
    "S3Error",
    "S3TimeoutError",
    "S3ConnectionError",
    "S3AuthError",
    "S3NotFoundError",
    "S3CircuitOpenError",
]
