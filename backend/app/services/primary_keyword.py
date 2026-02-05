"""Primary keyword service for generating and scoring keywords.

This service orchestrates keyword generation for crawled pages by:
1. Using Claude to generate keyword candidates based on page content
2. Using DataForSEO to enrich candidates with search volume data
3. Scoring and ranking keywords by relevance and search potential
4. Tracking used keywords to prevent duplicates across pages

The service maintains state for:
- used_primary_keywords: Set of keywords already assigned to other pages
- stats: Metrics tracking for the generation process
"""

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient
from app.integrations.dataforseo import DataForSEOClient

logger = get_logger(__name__)


@dataclass
class KeywordGenerationStats:
    """Statistics for a keyword generation run."""

    pages_processed: int = 0
    pages_succeeded: int = 0
    pages_failed: int = 0
    keywords_generated: int = 0
    keywords_enriched: int = 0
    claude_calls: int = 0
    dataforseo_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    dataforseo_cost: float = 0.0
    errors: list[dict[str, Any]] = field(default_factory=list)


class PrimaryKeywordService:
    """Service for generating and scoring primary keywords for pages.

    Orchestrates keyword generation using:
    - Claude for intelligent keyword candidate generation
    - DataForSEO for search volume enrichment

    Maintains state to:
    - Prevent duplicate keyword assignments across pages
    - Track generation metrics and costs
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        dataforseo_client: DataForSEOClient,
    ) -> None:
        """Initialize the primary keyword service.

        Args:
            claude_client: ClaudeClient for LLM keyword generation.
            dataforseo_client: DataForSEOClient for search volume data.
        """
        self._claude = claude_client
        self._dataforseo = dataforseo_client

        # Track keywords already assigned to prevent duplicates
        self._used_primary_keywords: set[str] = set()

        # Track generation statistics
        self._stats = KeywordGenerationStats()

        logger.info(
            "PrimaryKeywordService initialized",
            extra={
                "claude_available": claude_client.available,
                "dataforseo_available": dataforseo_client.available,
            },
        )

    @property
    def used_primary_keywords(self) -> set[str]:
        """Get the set of keywords already used as primary keywords."""
        return self._used_primary_keywords

    @property
    def stats(self) -> KeywordGenerationStats:
        """Get current generation statistics."""
        return self._stats

    def add_used_keyword(self, keyword: str) -> None:
        """Mark a keyword as used (assigned as primary to a page).

        Args:
            keyword: Keyword to mark as used.
        """
        normalized = keyword.strip().lower()
        self._used_primary_keywords.add(normalized)
        logger.debug(
            "Keyword marked as used",
            extra={"keyword": normalized},
        )

    def add_used_keywords(self, keywords: list[str]) -> None:
        """Mark multiple keywords as used.

        Args:
            keywords: List of keywords to mark as used.
        """
        for keyword in keywords:
            self.add_used_keyword(keyword)

    def is_keyword_used(self, keyword: str) -> bool:
        """Check if a keyword has already been used.

        Args:
            keyword: Keyword to check.

        Returns:
            True if keyword is already used, False otherwise.
        """
        normalized = keyword.strip().lower()
        return normalized in self._used_primary_keywords

    def reset_stats(self) -> None:
        """Reset generation statistics to initial state."""
        self._stats = KeywordGenerationStats()
        logger.debug("Generation stats reset")

    def reset_used_keywords(self) -> None:
        """Clear all used keywords tracking."""
        self._used_primary_keywords.clear()
        logger.debug("Used keywords tracking cleared")

    def get_stats_summary(self) -> dict[str, Any]:
        """Get a summary of generation statistics.

        Returns:
            Dictionary with stats summary for API responses.
        """
        return {
            "pages_processed": self._stats.pages_processed,
            "pages_succeeded": self._stats.pages_succeeded,
            "pages_failed": self._stats.pages_failed,
            "keywords_generated": self._stats.keywords_generated,
            "keywords_enriched": self._stats.keywords_enriched,
            "claude_calls": self._stats.claude_calls,
            "dataforseo_calls": self._stats.dataforseo_calls,
            "total_input_tokens": self._stats.total_input_tokens,
            "total_output_tokens": self._stats.total_output_tokens,
            "dataforseo_cost": self._stats.dataforseo_cost,
            "error_count": len(self._stats.errors),
            "used_keywords_count": len(self._used_primary_keywords),
        }
