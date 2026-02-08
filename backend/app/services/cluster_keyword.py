"""Cluster keyword service for generating keyword clusters with brand context.

This service orchestrates keyword cluster generation by:
1. Building brand-aware context from BrandConfig v2_schema
2. Using Claude for cluster generation (Stages 1-3)
3. Using DataForSEO for search volume enrichment
"""

import json
from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient
from app.integrations.dataforseo import DataForSEOClient

HAIKU_MODEL = "claude-haiku-4-5-20251001"

logger = get_logger(__name__)


class ClusterKeywordService:
    """Service for generating keyword clusters with brand context.

    Orchestrates cluster generation using:
    - Claude for intelligent cluster and page generation
    - DataForSEO for search volume enrichment
    - Brand config context for brand-aware prompts
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        dataforseo_client: DataForSEOClient,
    ) -> None:
        """Initialize the cluster keyword service.

        Args:
            claude_client: ClaudeClient for LLM cluster generation.
            dataforseo_client: DataForSEOClient for search volume data.
        """
        self._claude = claude_client
        self._dataforseo = dataforseo_client

        logger.info(
            "ClusterKeywordService initialized",
            extra={
                "claude_available": claude_client.available,
                "dataforseo_available": dataforseo_client.available,
            },
        )

    @staticmethod
    def _build_brand_context(brand_config: dict[str, Any]) -> str:
        """Build a brand context string from v2_schema for prompt injection.

        Extracts key brand information from the v2_schema JSON structure
        to provide relevant context for cluster generation prompts.

        Sections extracted:
        - brand_foundation: company name, primary products, price point, sales channels
        - target_audience: primary persona name and summary
        - competitor_context: competitor names

        Missing or incomplete sections are silently skipped.

        Args:
            brand_config: The v2_schema dict from BrandConfig model.

        Returns:
            Formatted string suitable for prompt injection. Returns empty
            string if no usable data is found.
        """
        parts: list[str] = []

        # Brand foundation
        brand_foundation = brand_config.get("brand_foundation")
        if isinstance(brand_foundation, dict):
            foundation_parts: list[str] = []

            company_overview = brand_foundation.get("company_overview")
            if isinstance(company_overview, dict):
                company_name = company_overview.get("company_name")
                if company_name:
                    foundation_parts.append(f"Company: {company_name}")

            what_they_sell = brand_foundation.get("what_they_sell")
            if isinstance(what_they_sell, dict):
                primary_products = what_they_sell.get("primary_products_services")
                if primary_products:
                    foundation_parts.append(f"Primary Products: {primary_products}")

                price_point = what_they_sell.get("price_point")
                if price_point:
                    foundation_parts.append(f"Price Point: {price_point}")

                sales_channels = what_they_sell.get("sales_channels")
                if sales_channels:
                    foundation_parts.append(f"Sales Channels: {sales_channels}")

            if foundation_parts:
                parts.append("## Brand\n" + "\n".join(foundation_parts))

        # Target audience — primary persona
        target_audience = brand_config.get("target_audience")
        if isinstance(target_audience, dict):
            personas = target_audience.get("personas")
            if isinstance(personas, list) and len(personas) > 0:
                primary_persona = personas[0]
                if isinstance(primary_persona, dict):
                    persona_parts: list[str] = []

                    persona_name = primary_persona.get("name")
                    if persona_name:
                        persona_parts.append(f"Primary Persona: {persona_name}")

                    summary = primary_persona.get("summary")
                    if summary:
                        persona_parts.append(f"Summary: {summary}")

                    if persona_parts:
                        parts.append(
                            "## Target Audience\n" + "\n".join(persona_parts)
                        )

        # Competitor context — competitor names
        competitor_context = brand_config.get("competitor_context")
        if isinstance(competitor_context, dict):
            direct_competitors = competitor_context.get("direct_competitors")
            if isinstance(direct_competitors, list) and len(direct_competitors) > 0:
                names: list[str] = []
                for comp in direct_competitors:
                    if isinstance(comp, dict):
                        name = comp.get("name")
                        if name:
                            names.append(name)
                if names:
                    parts.append("## Competitors\n" + ", ".join(names))

        return "\n\n".join(parts)

    async def _generate_candidates(
        self,
        seed_keyword: str,
        brand_context: str,
    ) -> list[dict[str, Any]]:
        """Stage 1: Expand a seed keyword into 15-20 collection page candidates.

        Uses Claude Haiku with an 11-strategy expansion prompt to generate
        keyword candidates suitable as standalone Shopify collection pages.

        The seed keyword is always included as the first candidate with
        role hint 'parent'.

        Args:
            seed_keyword: The seed keyword to expand.
            brand_context: Brand context string from _build_brand_context().

        Returns:
            List of dicts with keys: keyword, expansion_strategy, rationale,
            estimated_intent. The seed keyword is first with role='parent'.

        Raises:
            ValueError: If Claude returns too few candidates or unparseable JSON.
        """
        brand_section = ""
        if brand_context:
            brand_section = f"""
## Brand Context
{brand_context}
"""

        prompt = f"""You are an e-commerce SEO strategist. Given a seed keyword, generate 15-20 collection page keyword ideas using the expansion strategies below.

## Seed Keyword
"{seed_keyword}"
{brand_section}
## Expansion Strategies (use as many as relevant)
1. **Demographic** — Target a specific audience segment (e.g., "women's hiking boots")
2. **Attribute** — Add a product attribute (e.g., "waterproof hiking boots")
3. **Price/Value** — Add price or value modifier (e.g., "affordable hiking boots")
4. **Use-Case** — Target a specific use case (e.g., "hiking boots for backpacking")
5. **Comparison/Intent** — Add buying or comparison intent (e.g., "best hiking boots")
6. **Seasonal/Occasion** — Target a season or occasion (e.g., "winter hiking boots")
7. **Material/Type** — Specify material or type (e.g., "leather hiking boots")
8. **Experience Level** — Target skill level (e.g., "beginner hiking boots")
9. **Problem/Solution** — Address a pain point (e.g., "wide-feet hiking boots")
10. **Terrain/Environment** — Specify terrain or environment (e.g., "mountain hiking boots")
11. **Values/Lifestyle** — Align with values (e.g., "vegan hiking boots")

## Rules
- Each keyword must be viable as a standalone Shopify collection page (NOT a blog post)
- Focus on commercial/transactional intent
- Order results by estimated commercial value (highest first)
- Do NOT include the seed keyword itself — it will be added separately

## Output Format
Return ONLY a JSON array of objects. No explanations, no markdown code blocks.
Each object must have:
- "keyword": the collection page keyword
- "expansion_strategy": which strategy was used (one of the 11 above)
- "rationale": brief reason why this is a good collection page
- "estimated_intent": one of "transactional", "commercial", "informational"

Example:
[{{"keyword": "women's hiking boots", "expansion_strategy": "demographic", "rationale": "Large audience segment with distinct needs", "estimated_intent": "commercial"}}]"""

        result = await self._claude.complete(
            user_prompt=prompt,
            max_tokens=1500,
            temperature=0.4,
            model=HAIKU_MODEL,
        )

        if not result.success or not result.text:
            raise ValueError(
                f"Claude candidate generation failed: {result.error or 'Empty response'}"
            )

        # Parse JSON response — strip markdown code blocks if present
        response_text = result.text.strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        candidates = json.loads(response_text)

        if not isinstance(candidates, list):
            raise ValueError("LLM response is not a list")

        # Validate each candidate has required fields
        valid_candidates: list[dict[str, Any]] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            keyword = item.get("keyword")
            if not keyword or not isinstance(keyword, str):
                continue
            valid_candidates.append(
                {
                    "keyword": keyword.strip().lower(),
                    "expansion_strategy": item.get("expansion_strategy", "unknown"),
                    "rationale": item.get("rationale", ""),
                    "estimated_intent": item.get("estimated_intent", "commercial"),
                }
            )

        if len(valid_candidates) < 5:
            raise ValueError(
                f"Too few valid candidates: {len(valid_candidates)} (expected 15-20)"
            )

        # Prepend seed keyword as parent
        seed_candidate: dict[str, Any] = {
            "keyword": seed_keyword.strip().lower(),
            "expansion_strategy": "seed",
            "rationale": "Original seed keyword — parent of this cluster",
            "estimated_intent": "commercial",
            "role_hint": "parent",
        }

        # Deduplicate: remove seed from generated list if Claude included it
        seed_normalized = seed_keyword.strip().lower()
        valid_candidates = [
            c for c in valid_candidates if c["keyword"] != seed_normalized
        ]

        result_list = [seed_candidate] + valid_candidates

        logger.info(
            "Generated cluster candidates",
            extra={
                "seed_keyword": seed_keyword,
                "candidate_count": len(result_list),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )

        return result_list

    async def _enrich_with_volume(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Stage 2: Enrich candidates with search volume data from DataForSEO.

        Extracts keyword strings from candidates and calls the DataForSEO
        batch API to get search volume, CPC, and competition data. Merges
        the volume data back into each candidate dict.

        If DataForSEO is unavailable (not configured) or the API call fails,
        returns candidates unchanged with a 'volume_unavailable' flag set to
        True on each candidate.

        Args:
            candidates: List of candidate dicts from _generate_candidates().
                Each must have a 'keyword' key.

        Returns:
            The same list of candidate dicts, enriched with 'search_volume',
            'cpc', 'competition', and 'competition_level' keys. If volume
            data is unavailable, candidates are returned unchanged with
            'volume_unavailable' set to True.
        """
        if not candidates:
            return candidates

        # Check if DataForSEO is available
        if not self._dataforseo.available:
            logger.warning(
                "DataForSEO not available, skipping cluster volume enrichment",
                extra={"candidate_count": len(candidates)},
            )
            for candidate in candidates:
                candidate["volume_unavailable"] = True
            return candidates

        # Extract keyword strings for batch lookup
        keywords = [c["keyword"] for c in candidates]

        logger.info(
            "Enriching cluster candidates with volume data",
            extra={"candidate_count": len(candidates)},
        )

        try:
            result = await self._dataforseo.get_keyword_volume_batch(keywords)

            if not result.success:
                logger.warning(
                    "DataForSEO volume lookup failed for cluster candidates",
                    extra={
                        "error": result.error,
                        "candidate_count": len(candidates),
                    },
                )
                for candidate in candidates:
                    candidate["volume_unavailable"] = True
                return candidates

            # Build keyword -> volume data mapping (normalized to lowercase)
            volume_map: dict[str, Any] = {}
            for kw_data in result.keywords:
                normalized = kw_data.keyword.strip().lower()
                volume_map[normalized] = {
                    "search_volume": kw_data.search_volume,
                    "cpc": kw_data.cpc,
                    "competition": kw_data.competition,
                    "competition_level": kw_data.competition_level,
                }

            # Merge volume data into candidates
            enriched_count = 0
            for candidate in candidates:
                normalized_kw = candidate["keyword"].strip().lower()
                vol = volume_map.get(normalized_kw)
                if vol:
                    candidate["search_volume"] = vol["search_volume"]
                    candidate["cpc"] = vol["cpc"]
                    candidate["competition"] = vol["competition"]
                    candidate["competition_level"] = vol["competition_level"]
                    enriched_count += 1
                else:
                    candidate["search_volume"] = None
                    candidate["cpc"] = None
                    candidate["competition"] = None
                    candidate["competition_level"] = None

            logger.info(
                "Cluster volume enrichment complete",
                extra={
                    "candidates_total": len(candidates),
                    "candidates_enriched": enriched_count,
                    "cost": result.cost,
                    "duration_ms": result.duration_ms,
                },
            )

            return candidates

        except Exception as e:
            logger.error(
                "Unexpected error during cluster volume enrichment",
                extra={
                    "error": str(e),
                    "candidate_count": len(candidates),
                },
                exc_info=True,
            )
            for candidate in candidates:
                candidate["volume_unavailable"] = True
            return candidates
