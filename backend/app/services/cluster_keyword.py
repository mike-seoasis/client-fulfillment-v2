"""Cluster keyword service for generating keyword clusters with brand context.

This service orchestrates keyword cluster generation by:
1. Building brand-aware context from BrandConfig v2_schema
2. Using Claude for cluster generation (Stages 1-3)
3. Using DataForSEO for search volume enrichment
"""

import json
import math
import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient
from app.integrations.dataforseo import DataForSEOClient
from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.keyword_cluster import ClusterPage, ClusterStatus, KeywordCluster
from app.models.page_keywords import PageKeywords

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

    @staticmethod
    def _keyword_to_slug(keyword: str) -> str:
        """Convert a keyword to a URL-safe slug for /collections/{slug}.

        Lowercase, replaces spaces/special chars with hyphens, strips leading/
        trailing hyphens, collapses consecutive hyphens, and truncates to 60 chars.

        Args:
            keyword: The keyword string to slugify.

        Returns:
            URL-safe slug string, max 60 characters.
        """
        slug = keyword.strip().lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s-]+", "-", slug)
        slug = slug.strip("-")
        if len(slug) > 60:
            slug = slug[:60].rstrip("-")
        return slug

    @staticmethod
    def _calculate_composite_score(
        volume: int | float | None,
        competition: float | None,
        relevance: float,
    ) -> float:
        """Calculate composite score for a keyword.

        Reuses the formula from PrimaryKeywordService.calculate_score():
        - Volume score (50%): log10(volume) * 10, capped at 50
        - Relevance score (35%): relevance * 100
        - Competition score (15%): (1 - competition) * 100

        Args:
            volume: Monthly search volume (can be 0, None, or positive).
            competition: Competition level 0.0-1.0 (or 0-100), or None.
            relevance: Relevance score from 0.0 to 1.0.

        Returns:
            Composite score as a float, rounded to 2 decimal places.
        """
        # Volume score: log10(volume) * 10, clamped to [0, 50]
        if volume is None or volume <= 0:
            volume_score = 0.0
        else:
            volume_score = min(50.0, max(0.0, math.log10(volume) * 10))

        # Competition score: (1 - competition) * 100
        if competition is None:
            competition_score = 50.0
        else:
            norm_competition = competition / 100.0 if competition > 1.0 else competition
            competition_score = (1.0 - norm_competition) * 100

        # Relevance score
        relevance_score = relevance * 100

        composite_score = (
            (volume_score * 0.50)
            + (relevance_score * 0.35)
            + (competition_score * 0.15)
        )

        return round(composite_score, 2)

    async def _filter_and_assign_roles(
        self,
        candidates: list[dict[str, Any]],
        seed_keyword: str,
    ) -> list[dict[str, Any]]:
        """Stage 3: Filter candidates and assign parent/child roles with URL slugs.

        Uses Claude Haiku to intelligently filter 15-20 candidates down to the
        best 8-12, removing near-duplicates and low-quality candidates. The seed
        keyword is always assigned as parent, others as children.

        Each result includes a composite score calculated using the same formula
        as PrimaryKeywordService.calculate_score().

        Args:
            candidates: Enriched candidate list from _enrich_with_volume().
            seed_keyword: The original seed keyword (assigned role='parent').

        Returns:
            Filtered list of 8-12 candidates sorted by composite_score descending,
            with parent always first. Each dict has: keyword, role, url_slug,
            expansion_strategy, reasoning, search_volume, cpc, competition,
            competition_level, composite_score.

        Raises:
            ValueError: If Claude returns unparseable JSON or too few results.
        """
        # Build candidate summary for the prompt
        candidate_lines: list[str] = []
        for i, c in enumerate(candidates, 1):
            vol = c.get("search_volume")
            cpc = c.get("cpc")
            comp = c.get("competition")
            comp_level = c.get("competition_level", "")
            vol_str = str(vol) if vol is not None else "N/A"
            cpc_str = f"${cpc:.2f}" if cpc is not None else "N/A"
            comp_str = f"{comp:.2f}" if comp is not None else "N/A"
            candidate_lines.append(
                f"{i}. \"{c['keyword']}\" — volume: {vol_str}, "
                f"CPC: {cpc_str}, competition: {comp_str} ({comp_level}), "
                f"strategy: {c.get('expansion_strategy', 'unknown')}"
            )

        candidates_text = "\n".join(candidate_lines)
        seed_normalized = seed_keyword.strip().lower()

        prompt = f"""You are an e-commerce SEO expert filtering keyword candidates for Shopify collection pages.

## Seed Keyword
"{seed_normalized}"

## Candidates (with search data)
{candidates_text}

## Your Task
Filter these candidates to the **best 8-12 keywords** for collection pages. Apply these rules:

### Selection Criteria
1. **Remove near-duplicates**: If two keywords would target the same products/intent, keep only the one with higher volume (e.g., "men's running shoes" and "running shoes for men" are duplicates — this is keyword cannibalization)
2. **Remove low-volume keywords**: Remove candidates with search_volume < 50, UNLESS removing them would leave fewer than 5 total candidates
3. **Prioritize commercial/transactional intent**: Collection pages need buying intent, not informational
4. **Prefer keywords that represent distinct product groupings**: Each collection page should serve a unique subset of products
5. **Good collection page keywords** are specific enough to curate a product set but broad enough to have meaningful search volume

### Role Assignment
- The seed keyword "{seed_normalized}" MUST be assigned role "parent"
- All other selected keywords get role "child"

### URL Slugs
- Generate a URL slug for each keyword in the format suitable for /collections/{{slug}}
- Lowercase, hyphens instead of spaces, no special characters, max 60 characters

## Output Format
Return ONLY a JSON array of objects. No explanations, no markdown code blocks.
Each object must have:
- "keyword": the keyword (lowercase)
- "role": "parent" or "child"
- "url_slug": the URL slug for /collections/
- "reasoning": why this keyword was selected (brief)
- "relevance": a score from 0.0 to 1.0 indicating how relevant this keyword is to the seed keyword and collection page intent

Example:
[{{"keyword": "hiking boots", "role": "parent", "url_slug": "hiking-boots", "reasoning": "High-volume seed keyword with strong commercial intent", "relevance": 0.95}}]"""

        result = await self._claude.complete(
            user_prompt=prompt,
            max_tokens=2000,
            temperature=0.0,
            model=HAIKU_MODEL,
        )

        if not result.success or not result.text:
            raise ValueError(
                f"Claude filtering failed: {result.error or 'Empty response'}"
            )

        # Parse JSON response — strip markdown code blocks if present
        response_text = result.text.strip()
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        filtered = json.loads(response_text)

        if not isinstance(filtered, list):
            raise ValueError("LLM filtering response is not a list")

        # Build lookup from original candidates for volume data
        candidate_map: dict[str, dict[str, Any]] = {}
        for c in candidates:
            candidate_map[c["keyword"].strip().lower()] = c

        # Process filtered results
        results: list[dict[str, Any]] = []
        for item in filtered:
            if not isinstance(item, dict):
                continue
            keyword = item.get("keyword")
            if not keyword or not isinstance(keyword, str):
                continue

            kw_normalized = keyword.strip().lower()
            original = candidate_map.get(kw_normalized, {})

            role = "parent" if kw_normalized == seed_normalized else "child"
            url_slug = self._keyword_to_slug(
                item.get("url_slug", kw_normalized)
            )
            relevance = item.get("relevance", 0.7)
            if not isinstance(relevance, (int, float)):
                relevance = 0.7

            search_volume = original.get("search_volume")
            cpc = original.get("cpc")
            competition = original.get("competition")
            competition_level = original.get("competition_level")

            composite_score = self._calculate_composite_score(
                volume=search_volume,
                competition=competition,
                relevance=float(relevance),
            )

            results.append(
                {
                    "keyword": kw_normalized,
                    "role": role,
                    "url_slug": url_slug,
                    "expansion_strategy": original.get(
                        "expansion_strategy", item.get("expansion_strategy", "unknown")
                    ),
                    "reasoning": item.get("reasoning", ""),
                    "search_volume": search_volume,
                    "cpc": cpc,
                    "competition": competition,
                    "competition_level": competition_level,
                    "composite_score": composite_score,
                }
            )

        if len(results) < 3:
            raise ValueError(
                f"Too few results after filtering: {len(results)} (expected 8-12)"
            )

        # Sort by composite_score descending, but parent always first
        parent = [r for r in results if r["role"] == "parent"]
        children = [r for r in results if r["role"] == "child"]
        children.sort(key=lambda x: -(x.get("composite_score") or 0))
        results = parent + children

        logger.info(
            "Stage 3 filtering complete",
            extra={
                "seed_keyword": seed_keyword,
                "input_candidates": len(candidates),
                "output_results": len(results),
                "parent_keyword": results[0]["keyword"] if results else None,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )

        return results

    async def generate_cluster(
        self,
        seed_keyword: str,
        project_id: str,
        brand_config: dict[str, Any],
        db: AsyncSession,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Orchestrate cluster generation: Stage 1 → 2 → 3, then persist.

        Runs the three pipeline stages sequentially:
        1. LLM candidate generation (Claude Haiku)
        2. DataForSEO volume enrichment (graceful degradation on failure)
        3. LLM filtering and role assignment (Claude Haiku)

        On success, creates a KeywordCluster record with status='suggestions_ready'
        and ClusterPage records for each filtered candidate.

        Args:
            seed_keyword: The seed keyword to build the cluster around.
            project_id: UUID of the parent project.
            brand_config: The v2_schema dict from BrandConfig model.
            db: AsyncSession for database operations.
            name: Optional display name for the cluster. Defaults to
                the seed keyword if not provided.

        Returns:
            Dict with keys: cluster_id, suggestions (list), generation_metadata,
            warnings (list of strings).

        Raises:
            ValueError: If Stage 1 or Stage 3 fails (total failure).
        """
        warnings: list[str] = []
        cluster_name = name or seed_keyword.strip()

        # Build brand context
        brand_context = self._build_brand_context(brand_config)

        # --- Stage 1: Generate candidates ---
        t1_start = time.perf_counter()
        try:
            candidates = await self._generate_candidates(seed_keyword, brand_context)
        except Exception as e:
            logger.error(
                "Stage 1 (candidate generation) failed",
                extra={"seed_keyword": seed_keyword, "error": str(e)},
                exc_info=True,
            )
            raise ValueError(f"Cluster generation failed at Stage 1: {e}") from e
        t1_ms = round((time.perf_counter() - t1_start) * 1000)

        candidates_generated = len(candidates)

        # --- Stage 2: Enrich with volume data ---
        t2_start = time.perf_counter()
        volume_unavailable = False
        try:
            candidates = await self._enrich_with_volume(candidates)
            # Check if volume was unavailable (flag set by _enrich_with_volume)
            if candidates and candidates[0].get("volume_unavailable"):
                volume_unavailable = True
                warnings.append(
                    "Search volume data unavailable — DataForSEO lookup failed or not configured. "
                    "Filtering proceeded without volume data."
                )
        except Exception as e:
            logger.warning(
                "Stage 2 (volume enrichment) failed, continuing without volume",
                extra={"seed_keyword": seed_keyword, "error": str(e)},
                exc_info=True,
            )
            volume_unavailable = True
            warnings.append(
                f"Search volume enrichment failed: {e}. "
                "Filtering proceeded without volume data."
                )
        t2_ms = round((time.perf_counter() - t2_start) * 1000)

        candidates_enriched = 0 if volume_unavailable else len(candidates)

        # --- Stage 3: Filter and assign roles ---
        t3_start = time.perf_counter()
        try:
            filtered = await self._filter_and_assign_roles(candidates, seed_keyword)
        except Exception as e:
            logger.error(
                "Stage 3 (filtering) failed",
                extra={"seed_keyword": seed_keyword, "error": str(e)},
                exc_info=True,
            )
            raise ValueError(f"Cluster generation failed at Stage 3: {e}") from e
        t3_ms = round((time.perf_counter() - t3_start) * 1000)

        total_ms = t1_ms + t2_ms + t3_ms

        generation_metadata: dict[str, Any] = {
            "stage1_time_ms": t1_ms,
            "stage2_time_ms": t2_ms,
            "stage3_time_ms": t3_ms,
            "total_time_ms": total_ms,
            "candidates_generated": candidates_generated,
            "candidates_enriched": candidates_enriched,
            "candidates_filtered": len(filtered),
            "volume_unavailable": volume_unavailable,
        }

        # --- Persist to database ---
        try:
            cluster = KeywordCluster(
                project_id=project_id,
                seed_keyword=seed_keyword.strip().lower(),
                name=cluster_name,
                status=ClusterStatus.SUGGESTIONS_READY.value,
                generation_metadata=generation_metadata,
            )
            db.add(cluster)
            await db.flush()  # Get cluster.id

            for page_data in filtered:
                cluster_page = ClusterPage(
                    cluster_id=cluster.id,
                    keyword=page_data["keyword"],
                    role=page_data["role"],
                    url_slug=page_data["url_slug"],
                    expansion_strategy=page_data.get("expansion_strategy"),
                    reasoning=page_data.get("reasoning"),
                    search_volume=page_data.get("search_volume"),
                    cpc=page_data.get("cpc"),
                    competition=page_data.get("competition"),
                    competition_level=page_data.get("competition_level"),
                    composite_score=page_data.get("composite_score"),
                )
                db.add(cluster_page)

            await db.commit()

            logger.info(
                "Cluster generation complete",
                extra={
                    "cluster_id": cluster.id,
                    "seed_keyword": seed_keyword,
                    "pages_created": len(filtered),
                    "total_time_ms": total_ms,
                },
            )

            return {
                "cluster_id": cluster.id,
                "suggestions": filtered,
                "generation_metadata": generation_metadata,
                "warnings": warnings,
            }

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to persist cluster to database",
                extra={"seed_keyword": seed_keyword, "error": str(e)},
                exc_info=True,
            )
            raise ValueError(f"Cluster generation failed during persistence: {e}") from e

    @staticmethod
    async def bulk_approve_cluster(
        cluster_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Bridge approved cluster pages into the content pipeline.

        For each approved ClusterPage, creates a CrawledPage (source='cluster',
        status='completed') and a PageKeywords record so the standard content
        generation pipeline can process them.

        Args:
            cluster_id: UUID of the KeywordCluster to approve.
            db: AsyncSession for database operations.

        Returns:
            Dict with bridged_count (int) and crawled_page_ids (list[str]).

        Raises:
            ValueError: If no approved pages exist (400-equivalent) or cluster
                status is already 'approved' or later (409-equivalent).
        """
        # Load the cluster
        result = await db.execute(
            select(KeywordCluster).where(KeywordCluster.id == cluster_id)
        )
        cluster = result.scalar_one_or_none()
        if cluster is None:
            raise ValueError(f"Cluster {cluster_id} not found")

        # 409-equivalent: cluster already approved or later
        approved_or_later = {
            ClusterStatus.APPROVED.value,
            ClusterStatus.CONTENT_GENERATING.value,
            ClusterStatus.COMPLETE.value,
        }
        if cluster.status in approved_or_later:
            raise ValueError(
                f"Cluster already has status '{cluster.status}' — cannot re-approve"
            )

        # Load approved ClusterPage records
        pages_result = await db.execute(
            select(ClusterPage).where(
                ClusterPage.cluster_id == cluster_id,
                ClusterPage.is_approved == True,  # noqa: E712
            )
        )
        approved_pages = list(pages_result.scalars().all())

        # 400-equivalent: no approved pages
        if not approved_pages:
            raise ValueError("No approved pages found for this cluster")

        crawled_page_ids: list[str] = []

        try:
            for cp in approved_pages:
                # Create CrawledPage for the content pipeline
                crawled_page = CrawledPage(
                    project_id=cluster.project_id,
                    normalized_url=cp.url_slug,
                    source="cluster",
                    status=CrawlStatus.COMPLETED.value,
                    category="collection",
                    title=cp.keyword,
                )
                db.add(crawled_page)
                await db.flush()  # Get crawled_page.id

                # Create PageKeywords for the content pipeline
                page_keywords = PageKeywords(
                    crawled_page_id=crawled_page.id,
                    primary_keyword=cp.keyword,
                    is_approved=True,
                    is_priority=cp.role == "parent",
                    search_volume=cp.search_volume,
                    composite_score=cp.composite_score,
                )
                db.add(page_keywords)

                # Link ClusterPage back to the new CrawledPage
                cp.crawled_page_id = crawled_page.id

                crawled_page_ids.append(crawled_page.id)

            # Update cluster status
            cluster.status = ClusterStatus.APPROVED.value

            await db.commit()

            logger.info(
                "Cluster bulk approve complete",
                extra={
                    "cluster_id": cluster_id,
                    "bridged_count": len(crawled_page_ids),
                },
            )

            return {
                "bridged_count": len(crawled_page_ids),
                "crawled_page_ids": crawled_page_ids,
            }

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to bridge cluster pages to content pipeline",
                extra={"cluster_id": cluster_id, "error": str(e)},
                exc_info=True,
            )
            raise ValueError(
                f"Cluster approval failed during persistence: {e}"
            ) from e
