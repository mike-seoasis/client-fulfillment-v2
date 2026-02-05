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

import json
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

    async def generate_candidates(
        self,
        url: str,
        title: str | None,
        h1: str | None,
        headings: dict[str, Any] | None,
        content_excerpt: str | None,
        product_count: int | None,
        category: str | None,
    ) -> list[str]:
        """Generate keyword candidates from page content using Claude.

        Uses LLM to analyze page content and generate 20-25 relevant keyword
        variations including head terms, mid-tail, and long-tail phrases.

        Args:
            url: Page URL for context.
            title: Page title from HTML.
            h1: Main H1 heading from page.
            headings: Dict with h1, h2, h3 arrays of headings.
            content_excerpt: First ~500 chars of body content.
            product_count: Number of products on page (for collection pages).
            category: Page category (product, collection, blog, etc.).

        Returns:
            List of keyword strings (20-25 keywords on success, fallback to
            title/H1 on API failure).
        """
        # Build category-specific guidelines
        category_guidelines = {
            "product": """- Focus on buyer intent (product name, features, benefits, use cases)
- Include product specifications and variations
- Add price/quality modifiers (cheap, premium, best, affordable)
- Consider user problems this product solves""",
            "collection": """- Focus on category terms + modifiers (best, top, cheap, premium)
- Include related categories and subcategories
- Add shopping intent keywords (buy, shop, find)
- Consider collection theme variations
- This is an e-commerce collection page with {product_count} products""",
            "blog": """- Focus on informational intent (how to, what is, guide, tutorial)
- Include question-based keywords
- Add topic variations and related concepts
- Consider user learning goals""",
            "homepage": """- Focus on brand name and main product categories
- Include branded variations
- Add top-level category terms
- Consider what the site is known for""",
            "other": """- Analyze page content and generate relevant topic keywords
- Focus on page purpose and main theme
- Include variations of main concepts""",
        }

        guidelines = category_guidelines.get(
            category or "other", category_guidelines["other"]
        )

        # Format product count for collection pages
        if category == "collection" and product_count:
            guidelines = guidelines.format(product_count=product_count)
        else:
            guidelines = guidelines.replace(
                "- This is an e-commerce collection page with {product_count} products",
                "",
            )

        # Build headings summary
        headings_text = ""
        if headings:
            h1_list = headings.get("h1", [])
            h2_list = headings.get("h2", [])
            if h1_list:
                headings_text += f"H1: {', '.join(h1_list[:3])}\n"
            if h2_list:
                headings_text += f"H2: {', '.join(h2_list[:5])}"

        # Build prompt
        prompt = f"""Analyze this {category or 'web'} page and generate high-level keyword ideas.

Page Data:
- URL: {url}
- Title: {title or 'N/A'}
- H1: {h1 or 'N/A'}
{f'- Headings: {headings_text}' if headings_text else ''}- Content excerpt (first 500 chars):
{(content_excerpt or '')[:500]}
- Category: {category or 'other'}
{f'- Product count: {product_count}' if product_count else ''}

Generate 20-25 relevant keyword variations including:
- Head terms (short, 1-2 words, likely high volume)
- Mid-tail phrases (2-3 words, moderate volume)
- Long-tail phrases (4+ words, specific, lower competition)
- Question-based keywords (if relevant)
- Semantic variations and synonyms

Category-specific guidelines for {category or 'other'} pages:
{guidelines}

IMPORTANT: Return ONLY a JSON array of keyword strings. No explanations, no markdown, just the array.
Example: ["keyword one", "keyword two", "keyword three"]"""

        try:
            # Call Claude API
            result = await self._claude.complete(
                user_prompt=prompt,
                max_tokens=500,
                temperature=0.3,  # Slight variation for diverse keywords
            )

            # Update stats
            self._stats.claude_calls += 1
            if result.input_tokens:
                self._stats.total_input_tokens += result.input_tokens
            if result.output_tokens:
                self._stats.total_output_tokens += result.output_tokens

            if not result.success or not result.text:
                raise ValueError(result.error or "Empty response from Claude")

            # Parse JSON response
            response_text = result.text.strip()

            # Handle markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            keywords = json.loads(response_text)

            # Validate response is a list of strings
            if not isinstance(keywords, list):
                raise ValueError("LLM response is not a list")

            # Filter to valid strings and clean up
            keywords = [
                k.strip().lower()
                for k in keywords
                if isinstance(k, str) and k.strip()
            ]

            if len(keywords) < 5:
                raise ValueError(f"LLM generated too few keywords: {len(keywords)}")

            # Update stats
            self._stats.keywords_generated += len(keywords)

            logger.info(
                "Generated keyword candidates",
                extra={
                    "url": url[:100],
                    "keyword_count": len(keywords),
                    "category": category,
                },
            )

            return keywords

        except Exception as e:
            # Log error
            logger.warning(
                "Keyword generation failed, using fallback",
                extra={
                    "url": url[:100],
                    "error": str(e),
                    "category": category,
                },
            )

            # Record error in stats
            self._stats.errors.append(
                {
                    "url": url,
                    "error": str(e),
                    "phase": "generate_candidates",
                }
            )

            # Fallback: extract keywords from title and H1
            fallback_keywords: list[str] = []
            if title:
                fallback_keywords.append(title.strip().lower())
            if h1 and (not title or h1.strip().lower() != title.strip().lower()):
                fallback_keywords.append(h1.strip().lower())

            logger.info(
                "Using fallback keywords from title/H1",
                extra={
                    "url": url[:100],
                    "fallback_count": len(fallback_keywords),
                },
            )

            self._stats.keywords_generated += len(fallback_keywords)
            return fallback_keywords
