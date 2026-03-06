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
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient
from app.integrations.dataforseo import DataForSEOClient, KeywordVolumeData

if TYPE_CHECKING:
    from app.models.crawled_page import CrawledPage

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
        prompt = f"""Analyze this {category or "web"} page and generate high-level keyword ideas.

Page Data:
- URL: {url}
- Title: {title or "N/A"}
- H1: {h1 or "N/A"}
{f"- Headings: {headings_text}" if headings_text else ""}- Content excerpt (first 500 chars):
{(content_excerpt or "")[:500]}
- Category: {category or "other"}
{f"- Product count: {product_count}" if product_count else ""}

Generate 20-25 relevant keyword variations including:
- Head terms (short, 1-2 words, likely high volume)
- Mid-tail phrases (2-3 words, moderate volume)
- Long-tail phrases (4+ words, specific, lower competition)
- Question-based keywords (if relevant)
- Semantic variations and synonyms

Category-specific guidelines for {category or "other"} pages:
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
                response_text = (
                    response_text.split("```json")[1].split("```")[0].strip()
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            keywords = json.loads(response_text)

            # Validate response is a list of strings
            if not isinstance(keywords, list):
                raise ValueError("LLM response is not a list")

            # Filter to valid strings and clean up
            keywords = [
                k.strip().lower() for k in keywords if isinstance(k, str) and k.strip()
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
            # Log error — do NOT fall back to page title, as that creates
            # confusing fake keywords. Return empty list so the pipeline
            # fails cleanly and the user sees a clear error.
            logger.error(
                "Keyword generation failed",
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

            return []

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
        prompt = f"""Filter this keyword list to only the MOST SPECIFIC keywords for this {category or "web"} page.

Page content:
- URL: {url}
- Title: {title or "N/A"}
- H1: {h1 or "N/A"}
- Category: {category or "other"}
- Body text sample: {(content_excerpt or "")[:400]}

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
                response_text = (
                    response_text.split("```json")[1].split("```")[0].strip()
                )
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

    def calculate_score(
        self,
        volume: int | float | None,
        competition: float | None,
        relevance: float,
    ) -> dict[str, float]:
        """Calculate composite score for a keyword based on volume, competition, and relevance.

        The composite score weights three factors:
        - Volume score (50%): Logarithmic scale of search volume, capped at 50
        - Relevance score (35%): How well the keyword matches the page content
        - Competition score (15%): Inverse of competition (lower competition = higher score)

        Args:
            volume: Monthly search volume (can be 0, None, or positive int/float).
            competition: Competition level from 0.0 (low) to 1.0 (high), or None.
            relevance: Relevance score from 0.0 to 1.0.

        Returns:
            Dict with 'volume_score', 'competition_score', 'relevance_score',
            and 'composite_score' keys.
        """
        # Calculate volume score: log10(volume) * 10, clamped to [0, 50]
        # Handle zero/null volume gracefully
        if volume is None or volume <= 0:
            volume_score = 0.0
        else:
            volume_score = min(50.0, max(0.0, math.log10(volume) * 10))

        # Calculate competition score: (1 - competition) * 100
        # Lower competition = higher score
        # Handle None competition as mid-range (0.5)
        # Note: DataForSEO returns competition_index as 0-100, normalize if needed
        if competition is None:
            competition_score = 50.0
        else:
            # Normalize competition to 0-1 range if it's in 0-100 range
            norm_competition = competition / 100.0 if competition > 1.0 else competition
            competition_score = (1.0 - norm_competition) * 100

        # Calculate relevance score: relevance * 100
        relevance_score = relevance * 100

        # Calculate composite score with weights:
        # 50% volume, 35% relevance, 15% competition
        composite_score = (
            (volume_score * 0.50)
            + (relevance_score * 0.35)
            + (competition_score * 0.15)
        )

        return {
            "volume_score": round(volume_score, 2),
            "competition_score": round(competition_score, 2),
            "relevance_score": round(relevance_score, 2),
            "composite_score": round(composite_score, 2),
        }

    def select_primary_and_alternatives(
        self,
        scored_keywords: list[dict[str, Any]],
        used_primaries: set[str] | None = None,
    ) -> dict[str, Any]:
        """Select the best primary keyword and alternatives from scored keywords.

        Sorts keywords by composite_score descending and selects the highest-scoring
        keyword that hasn't already been used as a primary for another page.
        Also returns the next 4 highest-scoring alternatives.

        Duplicate prevention is critical for SEO - the same keyword should not
        target multiple pages on a site.

        Args:
            scored_keywords: List of keyword dicts, each must contain at least
                'keyword' and 'composite_score' keys. May also contain 'volume',
                'cpc', 'competition', 'relevance_score'.
            used_primaries: Optional set of keywords already assigned to other pages.
                If None, uses self._used_primary_keywords.

        Returns:
            Dict with:
            - 'primary': The selected primary keyword dict (or None if all used)
            - 'alternatives': List of up to 4 alternative keyword dicts
            - 'all_keywords': Full sorted list for reference
        """
        if not scored_keywords:
            logger.debug("No scored keywords to select from")
            return {
                "primary": None,
                "alternatives": [],
                "all_keywords": [],
            }

        # Use instance tracking set if not provided
        if used_primaries is None:
            used_primaries = self._used_primary_keywords

        # Sort by composite_score descending
        sorted_keywords = sorted(
            scored_keywords,
            key=lambda x: -(x.get("composite_score") or 0),
        )

        logger.debug(
            "Selecting primary from scored keywords",
            extra={
                "total_keywords": len(sorted_keywords),
                "used_primaries_count": len(used_primaries),
            },
        )

        # Find the first keyword not already used
        primary: dict[str, Any] | None = None
        alternatives: list[dict[str, Any]] = []
        alternatives_count = 0
        max_alternatives = 4

        for kw_data in sorted_keywords:
            keyword = kw_data.get("keyword", "").strip().lower()
            if not keyword:
                continue

            # Check if this keyword is already used as a primary elsewhere
            if keyword in used_primaries:
                logger.debug(
                    "Skipping keyword (already used as primary)",
                    extra={"keyword": keyword},
                )
                continue

            if primary is None:
                # This is our primary keyword
                primary = kw_data

                # Add to used_primaries set to prevent duplicate assignment
                self.add_used_keyword(keyword)

                logger.info(
                    "Selected primary keyword",
                    extra={
                        "keyword": keyword,
                        "composite_score": kw_data.get("composite_score"),
                        "volume": kw_data.get("volume"),
                    },
                )
            elif alternatives_count < max_alternatives:
                # Store as alternative
                alternatives.append(kw_data)
                alternatives_count += 1

            # Stop once we have primary + 4 alternatives
            if primary is not None and alternatives_count >= max_alternatives:
                break

        if primary is None:
            logger.warning(
                "Could not select primary keyword (all candidates already used)",
                extra={
                    "total_keywords": len(sorted_keywords),
                    "used_primaries_count": len(used_primaries),
                },
            )

        return {
            "primary": primary,
            "alternatives": alternatives,
            "all_keywords": sorted_keywords,
        }

    async def process_page(
        self,
        page: "CrawledPage",
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Process a single page through the full keyword generation pipeline.

        Orchestrates:
        1. generate_candidates - Get keyword ideas from page content
        2. enrich_with_volume - Add search volume data from DataForSEO
        3. filter_to_specific - Filter to page-specific keywords
        4. calculate_score - Score each keyword
        5. select_primary_and_alternatives - Pick primary and alternatives
        6. Create/update PageKeywords record in database

        Args:
            page: CrawledPage model instance with content data.
            db: AsyncSession for database operations.

        Returns:
            Dict with 'success' (bool), 'primary_keyword' (str or None),
            'page_id', 'error' (str, only on failure).
        """
        from app.models.page_keywords import PageKeywords

        # Extract all needed values immediately to avoid lazy-loading issues
        # in async context (accessing page attributes after db.commit() can
        # trigger greenlet errors)
        page_id = page.id
        url = page.normalized_url
        title = page.title
        headings = page.headings
        body_content = page.body_content
        product_count = page.product_count
        category = page.category

        # Extract H1 from headings
        h1_list = headings.get("h1", []) if headings else []
        h1 = h1_list[0] if h1_list else None
        content_excerpt = body_content[:500] if body_content else None

        logger.info(
            "Processing page for primary keyword",
            extra={"page_id": page_id, "url": url[:100]},
        )

        # Track page processing in stats
        self._stats.pages_processed += 1

        try:
            # Step 1: Generate keyword candidates from page content
            candidates = await self.generate_candidates(
                url=url,
                title=title,
                h1=h1,
                headings=headings,
                content_excerpt=content_excerpt,
                product_count=product_count,
                category=category,
            )

            if not candidates:
                raise ValueError("No keyword candidates generated")

            logger.debug(
                "Generated candidates",
                extra={"page_id": page_id, "candidate_count": len(candidates)},
            )

            # Step 2: Enrich with search volume data
            volume_data = await self.enrich_with_volume(candidates)

            logger.debug(
                "Enriched with volume",
                extra={"page_id": page_id, "enriched_count": len(volume_data)},
            )

            # Step 3: Filter to page-specific keywords
            # If no volume data, create minimal structure for filtering
            if not volume_data:
                # Create placeholder KeywordVolumeData for candidates without API data
                from app.integrations.dataforseo import KeywordVolumeData as KVD

                volume_data = {
                    kw: KVD(
                        keyword=kw,
                        search_volume=None,
                        cpc=None,
                        competition=None,
                        competition_level=None,
                        monthly_searches=None,
                        error=None,
                    )
                    for kw in candidates
                }

            filtered = await self.filter_to_specific(
                keywords_with_volume=volume_data,
                url=url,
                title=title,
                h1=h1,
                content_excerpt=content_excerpt,
                category=category,
            )

            if not filtered:
                raise ValueError("No keywords after filtering")

            logger.debug(
                "Filtered to specific",
                extra={"page_id": page_id, "filtered_count": len(filtered)},
            )

            # Step 4: Calculate composite score for each keyword
            scored_keywords: list[dict[str, Any]] = []
            for kw_data in filtered:
                scores = self.calculate_score(
                    volume=kw_data.get("volume"),
                    competition=kw_data.get("competition"),
                    relevance=kw_data.get("relevance_score", 0.5),
                )
                scored_kw = {
                    **kw_data,
                    "composite_score": scores["composite_score"],
                    "volume_score": scores["volume_score"],
                    "competition_score": scores["competition_score"],
                    "relevance_score_weighted": scores["relevance_score"],
                }
                scored_keywords.append(scored_kw)

            logger.debug(
                "Scored keywords",
                extra={"page_id": page_id, "scored_count": len(scored_keywords)},
            )

            # Step 5: Select primary and alternatives
            selection = self.select_primary_and_alternatives(scored_keywords)

            primary = selection.get("primary")
            alternatives = selection.get("alternatives", [])

            if primary is None:
                raise ValueError(
                    "Could not select primary keyword (all candidates already used)"
                )

            primary_keyword = primary.get("keyword", "")
            primary_score = primary.get("composite_score")
            primary_relevance = primary.get("relevance_score")
            primary_volume = primary.get("volume")

            # Extract alternative keyword data (full objects with volume, score, etc.)
            alternative_keywords = [
                {
                    "keyword": alt.get("keyword", ""),
                    "volume": alt.get("volume"),
                    "composite_score": alt.get("composite_score"),
                }
                for alt in alternatives
                if alt.get("keyword")
            ]

            logger.info(
                "Selected primary keyword",
                extra={
                    "page_id": page_id,
                    "primary": primary_keyword,
                    "score": primary_score,
                    "volume": primary_volume,
                    "alternatives_count": len(alternative_keywords),
                },
            )

            # Step 6: Create or update PageKeywords record
            # Query for existing record directly to avoid lazy-loading issues
            # in async context (page.keywords would trigger greenlet error)
            from sqlalchemy import select

            stmt = select(PageKeywords).where(PageKeywords.crawled_page_id == page_id)
            result = await db.execute(stmt)
            existing_keywords = result.scalar_one_or_none()

            if existing_keywords:
                # Update existing record
                existing_keywords.primary_keyword = primary_keyword
                existing_keywords.alternative_keywords = alternative_keywords
                existing_keywords.composite_score = primary_score
                existing_keywords.relevance_score = primary_relevance
                existing_keywords.search_volume = primary_volume
                # Keep approval status unchanged on update

                logger.debug(
                    "Updated existing PageKeywords",
                    extra={"page_id": page_id, "keywords_id": existing_keywords.id},
                )
            else:
                # Create new record
                new_keywords = PageKeywords(
                    crawled_page_id=page_id,
                    primary_keyword=primary_keyword,
                    secondary_keywords=[],  # Not used in this pipeline
                    alternative_keywords=alternative_keywords,
                    is_approved=False,
                    is_priority=False,
                    composite_score=primary_score,
                    relevance_score=primary_relevance,
                    search_volume=primary_volume,
                )
                db.add(new_keywords)

                logger.debug(
                    "Created new PageKeywords",
                    extra={"page_id": page_id},
                )

            # Commit changes
            await db.commit()

            # Update success stats
            self._stats.pages_succeeded += 1

            return {
                "success": True,
                "page_id": page_id,
                "primary_keyword": primary_keyword,
                "composite_score": primary_score,
                "alternatives": alternative_keywords,
            }

        except Exception as e:
            # Log error
            logger.error(
                "Failed to process page for keywords",
                extra={
                    "page_id": page_id,
                    "url": url[:100],
                    "error": str(e),
                },
                exc_info=True,
            )

            # Update failure stats
            self._stats.pages_failed += 1
            self._stats.errors.append(
                {
                    "page_id": page_id,
                    "url": url,
                    "error": str(e),
                    "phase": "process_page",
                }
            )

            # Rollback any partial changes
            await db.rollback()

            return {
                "success": False,
                "page_id": page_id,
                "primary_keyword": None,
                "error": str(e),
            }

    async def generate_for_project(
        self,
        project_id: str,
        db: AsyncSession,
        batch: int | None = None,
    ) -> dict[str, Any]:
        """Process all completed pages in a project to generate primary keywords.

        Orchestrates keyword generation for an entire project by:
        1. Loading all CrawledPages with status=completed
        2. Initializing/resetting the used_primaries tracking set
        3. Processing each page through the keyword pipeline
        4. Updating project.phase_status with progress after each page
        5. Returning final status with statistics

        Progress tracking in phase_status enables frontend polling during
        the generation process.

        Args:
            project_id: UUID of the project to process.
            db: AsyncSession for database operations.

        Returns:
            Dict with:
            - 'success': bool - True if generation completed (even with some failures)
            - 'status': str - 'completed', 'partial', or 'failed'
            - 'total': int - Total pages processed
            - 'completed': int - Pages with keywords successfully generated
            - 'failed': int - Pages that failed keyword generation
            - 'stats': dict - Full generation statistics summary
            - 'error': str (optional) - Error message if completely failed
        """
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified

        from app.models.crawled_page import CrawledPage, CrawlStatus
        from app.models.project import Project

        logger.info(
            "Starting keyword generation for project",
            extra={"project_id": project_id},
        )

        # Reset stats and used keywords tracking for fresh generation
        self.reset_stats()
        self.reset_used_keywords()

        try:
            # Load project
            project = await db.get(Project, project_id)
            if not project:
                logger.error(
                    "Project not found for keyword generation",
                    extra={"project_id": project_id},
                )
                return {
                    "success": False,
                    "status": "failed",
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "error": f"Project {project_id} not found",
                }

            # Load all completed crawled pages for this project
            # Use selectinload to eager-load keywords relationship to avoid
            # lazy loading issues in async context (greenlet error)
            from sqlalchemy.orm import selectinload

            stmt = (
                select(CrawledPage)
                .options(selectinload(CrawledPage.keywords))
                .where(CrawledPage.project_id == project_id)
                .where(CrawledPage.status == CrawlStatus.COMPLETED.value)
                .order_by(CrawledPage.normalized_url)
            )
            if batch is not None:
                stmt = stmt.where(CrawledPage.onboarding_batch == batch)
            result = await db.execute(stmt)
            pages = list(result.scalars().all())

            # Seed used keywords from ALL existing keywords in the project
            # (not just this batch) to avoid duplicate primary keywords
            if batch is not None:
                from app.models.page_keywords import PageKeywords

                all_kw_stmt = (
                    select(PageKeywords.primary_keyword)
                    .join(CrawledPage, PageKeywords.crawled_page_id == CrawledPage.id)
                    .where(
                        CrawledPage.project_id == project_id,
                        PageKeywords.primary_keyword.isnot(None),
                    )
                )
                all_kw_result = await db.execute(all_kw_stmt)
                existing_keywords = [
                    kw for kw in all_kw_result.scalars().all() if kw
                ]
                self.add_used_keywords(existing_keywords)

            total_pages = len(pages)

            if total_pages == 0:
                logger.warning(
                    "No completed pages found for keyword generation",
                    extra={"project_id": project_id},
                )
                return {
                    "success": True,
                    "status": "completed",
                    "total": 0,
                    "completed": 0,
                    "failed": 0,
                    "stats": self.get_stats_summary(),
                }

            logger.info(
                "Found pages for keyword generation",
                extra={"project_id": project_id, "page_count": total_pages},
            )

            # Initialize phase_status for keyword generation tracking
            if "onboarding" not in project.phase_status:
                project.phase_status["onboarding"] = {}

            project.phase_status["onboarding"]["keywords"] = {
                "status": "generating",
                "total": total_pages,
                "completed": 0,
                "failed": 0,
                "current_page": None,
            }
            flag_modified(project, "phase_status")
            await db.commit()

            # Process each page
            completed_count = 0
            failed_count = 0

            for idx, page in enumerate(pages):
                # Update progress with current page being processed
                project.phase_status["onboarding"]["keywords"]["current_page"] = (
                    page.normalized_url[:100]
                )
                flag_modified(project, "phase_status")
                await db.commit()

                logger.debug(
                    "Processing page for keywords",
                    extra={
                        "project_id": project_id,
                        "page_index": idx + 1,
                        "total_pages": total_pages,
                        "url": page.normalized_url[:100],
                    },
                )

                # Process the page
                page_result = await self.process_page(page, db)

                if page_result.get("success"):
                    completed_count += 1
                else:
                    failed_count += 1

                # Update progress after each page
                project.phase_status["onboarding"]["keywords"]["completed"] = (
                    completed_count
                )
                project.phase_status["onboarding"]["keywords"]["failed"] = failed_count
                flag_modified(project, "phase_status")
                await db.commit()

                logger.debug(
                    "Page keyword generation result",
                    extra={
                        "project_id": project_id,
                        "page_id": page.id,
                        "success": page_result.get("success"),
                        "primary_keyword": page_result.get("primary_keyword"),
                        "progress": f"{idx + 1}/{total_pages}",
                    },
                )

            # Determine final status
            if failed_count == 0:
                final_status = "completed"
            elif completed_count == 0:
                final_status = "failed"
            else:
                final_status = "partial"

            # Update phase_status with final status
            project.phase_status["onboarding"]["keywords"]["status"] = final_status
            project.phase_status["onboarding"]["keywords"]["current_page"] = None
            flag_modified(project, "phase_status")
            await db.commit()

            logger.info(
                "Keyword generation completed for project",
                extra={
                    "project_id": project_id,
                    "status": final_status,
                    "total": total_pages,
                    "completed": completed_count,
                    "failed": failed_count,
                    "stats": self.get_stats_summary(),
                },
            )

            return {
                "success": True,
                "status": final_status,
                "total": total_pages,
                "completed": completed_count,
                "failed": failed_count,
                "stats": self.get_stats_summary(),
            }

        except Exception as e:
            logger.error(
                "Keyword generation failed for project",
                extra={
                    "project_id": project_id,
                    "error": str(e),
                },
                exc_info=True,
            )

            # Try to update phase_status with failure
            try:
                project = await db.get(Project, project_id)
                if project:
                    if "onboarding" not in project.phase_status:
                        project.phase_status["onboarding"] = {}
                    project.phase_status["onboarding"]["keywords"] = {
                        "status": "failed",
                        "error": str(e),
                        "total": self._stats.pages_processed,
                        "completed": self._stats.pages_succeeded,
                        "failed": self._stats.pages_failed,
                    }
                    flag_modified(project, "phase_status")
                    await db.commit()
            except Exception as update_error:
                logger.error(
                    "Failed to update project phase_status after error",
                    extra={
                        "project_id": project_id,
                        "error": str(update_error),
                    },
                )

            return {
                "success": False,
                "status": "failed",
                "total": self._stats.pages_processed,
                "completed": self._stats.pages_succeeded,
                "failed": self._stats.pages_failed,
                "error": str(e),
                "stats": self.get_stats_summary(),
            }
