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
from app.integrations.dataforseo import DataForSEOClient, KeywordVolumeData

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

    async def enrich_with_volume(
        self,
        keywords: list[str],
    ) -> dict[str, KeywordVolumeData]:
        """Enrich keywords with search volume data from DataForSEO.

        Calls DataForSEO API to get search volume, CPC, and competition
        data for each keyword. Handles failures gracefully by returning
        empty data for keywords that fail.

        Args:
            keywords: List of keyword strings to enrich.

        Returns:
            Dict mapping keyword (lowercase) to KeywordVolumeData.
            Keywords that fail lookup will not be included in the dict.
        """
        if not keywords:
            logger.debug("No keywords to enrich")
            return {}

        # Check if DataForSEO is available
        if not self._dataforseo.available:
            logger.warning(
                "DataForSEO not available, skipping volume enrichment",
                extra={"keyword_count": len(keywords)},
            )
            return {}

        logger.info(
            "Enriching keywords with volume data",
            extra={"keyword_count": len(keywords)},
        )

        try:
            # Call DataForSEO batch API
            result = await self._dataforseo.get_keyword_volume_batch(keywords)

            # Update stats
            self._stats.dataforseo_calls += 1
            if result.cost:
                self._stats.dataforseo_cost += result.cost
                logger.info(
                    "DataForSEO API cost",
                    extra={
                        "cost": result.cost,
                        "total_cost": self._stats.dataforseo_cost,
                    },
                )

            if not result.success:
                logger.warning(
                    "DataForSEO volume lookup failed",
                    extra={
                        "error": result.error,
                        "keyword_count": len(keywords),
                    },
                )
                self._stats.errors.append(
                    {
                        "error": result.error or "Unknown DataForSEO error",
                        "phase": "enrich_with_volume",
                        "keyword_count": len(keywords),
                    }
                )
                return {}

            # Build keyword -> volume data mapping
            volume_map: dict[str, KeywordVolumeData] = {}
            for kw_data in result.keywords:
                # Normalize keyword to lowercase for consistent lookup
                normalized_kw = kw_data.keyword.strip().lower()
                volume_map[normalized_kw] = kw_data

            # Update stats
            self._stats.keywords_enriched += len(volume_map)

            logger.info(
                "Volume enrichment complete",
                extra={
                    "keywords_requested": len(keywords),
                    "keywords_enriched": len(volume_map),
                    "cost": result.cost,
                    "duration_ms": result.duration_ms,
                },
            )

            return volume_map

        except Exception as e:
            logger.error(
                "Unexpected error during volume enrichment",
                extra={
                    "error": str(e),
                    "keyword_count": len(keywords),
                },
                exc_info=True,
            )
            self._stats.errors.append(
                {
                    "error": str(e),
                    "phase": "enrich_with_volume",
                    "keyword_count": len(keywords),
                }
            )
            return {}

    async def filter_to_specific(
        self,
        keywords_with_volume: dict[str, KeywordVolumeData],
        url: str,
        title: str | None,
        h1: str | None,
        content_excerpt: str | None,
        category: str | None,
    ) -> list[dict[str, Any]]:
        """Filter keywords to only those specific to this page's exact topic.

        Uses Claude to analyze keywords and filter out generic category terms,
        keeping only keywords that specifically match the page's content.

        Args:
            keywords_with_volume: Dict mapping keyword -> KeywordVolumeData.
            url: Page URL for context.
            title: Page title from HTML.
            h1: Main H1 heading from page.
            content_excerpt: First ~500 chars of body content.
            category: Page category (product, collection, blog, etc.).

        Returns:
            List of dicts with 'keyword', 'volume', 'cpc', 'competition',
            and 'relevance_score' (0.0-1.0). On API failure, returns all
            keywords with default relevance score of 0.5.
        """
        if not keywords_with_volume:
            logger.debug("No keywords to filter")
            return []

        # Filter out zero-volume keywords for the prompt
        keywords_with_positive_volume = {
            kw: data
            for kw, data in keywords_with_volume.items()
            if data.search_volume is not None and data.search_volume > 0
        }

        if not keywords_with_positive_volume:
            logger.warning(
                "No keywords with positive volume, using all keywords",
                extra={"url": url[:100], "total_keywords": len(keywords_with_volume)},
            )
            keywords_with_positive_volume = keywords_with_volume

        # Sort by volume for the prompt (descending)
        sorted_keywords = sorted(
            keywords_with_positive_volume.items(),
            key=lambda x: -(x[1].search_volume or 0),
        )

        # Format keywords for the prompt (limit to top 50 to avoid huge prompts)
        keywords_formatted = []
        for kw, data in sorted_keywords[:50]:
            vol_str = f"{data.search_volume:,}" if data.search_volume else "no data"
            keywords_formatted.append(f'  - "{kw}": {vol_str} searches/month')

        keywords_text = "\n".join(keywords_formatted)

        # Build the specificity filtering prompt
        prompt = f"""Filter this keyword list to only the MOST SPECIFIC keywords for this {category or 'web'} page.

Page content:
- URL: {url}
- Title: {title or 'N/A'}
- H1: {h1 or 'N/A'}
- Category: {category or 'other'}
- Body text sample: {(content_excerpt or '')[:400]}

All keywords with search volume:
{keywords_text}

Task: Return keywords that are SPECIFICALLY about THIS page's exact topic, with a relevance score.

SPECIFICITY CRITERIA (in order of importance):
1. Must reference the SPECIFIC subject of the page (team name, product name, exact collection)
2. Can include variations of the specific subject (different word orders, with/without modifiers)
3. Can include closely related terms (synonyms, related categories)
4. EXCLUDE generic category terms that apply to many pages
5. EXCLUDE broad terms that don't indicate THIS specific page

Examples:
✓ GOOD for "Toronto Blue Jays flags" collection page:
  - "toronto blue jays flags" (exact match) - relevance: 1.0
  - "blue jays flags" (specific team) - relevance: 0.95
  - "toronto blue jays banner" (specific team, synonym) - relevance: 0.9
  - "blue jays house flag" (specific team + product variation) - relevance: 0.85

✗ BAD for "Toronto Blue Jays flags" collection page:
  - "baseball flags" (too generic, applies to all teams)
  - "mlb flags" (too generic, applies to all teams)
  - "sports flags" (too generic, applies to all sports)

IMPORTANT: Return ONLY a JSON array of objects with "keyword" and "relevance_score" (0.0-1.0).
No explanations, no markdown.
Example: [{{"keyword": "keyword one", "relevance_score": 0.95}}, {{"keyword": "keyword two", "relevance_score": 0.8}}]"""

        try:
            # Call Claude API
            result = await self._claude.complete(
                user_prompt=prompt,
                max_tokens=1000,
                temperature=0.0,  # Deterministic for filtering
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

            specific_keywords = json.loads(response_text)

            # Validate response is a list
            if not isinstance(specific_keywords, list):
                raise ValueError("LLM response is not a list")

            # Build result list with volume data
            filtered_results: list[dict[str, Any]] = []
            for item in specific_keywords:
                if isinstance(item, dict) and "keyword" in item:
                    kw = item["keyword"].strip().lower()
                    relevance = item.get("relevance_score", 0.8)

                    # Validate relevance score is in range
                    if not isinstance(relevance, (int, float)):
                        relevance = 0.8
                    relevance = max(0.0, min(1.0, float(relevance)))

                    # Get volume data if available
                    volume_data = keywords_with_volume.get(kw)
                    if volume_data:
                        filtered_results.append(
                            {
                                "keyword": kw,
                                "volume": volume_data.search_volume,
                                "cpc": volume_data.cpc,
                                "competition": volume_data.competition,
                                "relevance_score": relevance,
                            }
                        )
                elif isinstance(item, str):
                    # Handle simple string format (backwards compatibility)
                    kw = item.strip().lower()
                    volume_data = keywords_with_volume.get(kw)
                    if volume_data:
                        filtered_results.append(
                            {
                                "keyword": kw,
                                "volume": volume_data.search_volume,
                                "cpc": volume_data.cpc,
                                "competition": volume_data.competition,
                                "relevance_score": 0.8,  # Default if not provided
                            }
                        )

            if len(filtered_results) < 2:
                raise ValueError(
                    f"LLM filtered too aggressively: only {len(filtered_results)} keywords"
                )

            logger.info(
                "Filtered to specific keywords",
                extra={
                    "url": url[:100],
                    "original_count": len(keywords_with_volume),
                    "filtered_count": len(filtered_results),
                    "category": category,
                },
            )

            return filtered_results

        except Exception as e:
            # Log error
            logger.warning(
                "Keyword specificity filtering failed, returning all keywords",
                extra={
                    "url": url[:100],
                    "error": str(e),
                    "keyword_count": len(keywords_with_volume),
                },
            )

            # Record error in stats
            self._stats.errors.append(
                {
                    "url": url,
                    "error": str(e),
                    "phase": "filter_to_specific",
                }
            )

            # Fallback: return all keywords with default relevance score
            fallback_results: list[dict[str, Any]] = []
            for kw, data in keywords_with_volume.items():
                fallback_results.append(
                    {
                        "keyword": kw,
                        "volume": data.search_volume,
                        "cpc": data.cpc,
                        "competition": data.competition,
                        "relevance_score": 0.5,  # Default relevance on failure
                    }
                )

            # Sort by volume descending
            fallback_results.sort(key=lambda x: -(x.get("volume") or 0))

            logger.info(
                "Using fallback: all keywords with default relevance",
                extra={
                    "url": url[:100],
                    "keyword_count": len(fallback_results),
                },
            )

            return fallback_results
