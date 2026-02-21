"""Blog topic discovery service for generating blog topics from POP content briefs.

This service orchestrates blog topic discovery using a 4-stage pipeline:
1. Extract seeds from existing POP briefs (related_searches + related_questions)
2. Expand seeds into blog topic candidates using Claude Haiku
3. Enrich candidates with search volume data from DataForSEO
4. Filter and rank candidates using Claude Haiku, generate URL slugs
"""

import json
import re
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient
from app.integrations.dataforseo import DataForSEOClient
from app.models.blog import BlogCampaign, BlogPost, CampaignStatus, PostStatus
from app.models.content_brief import ContentBrief
from app.models.keyword_cluster import ClusterPage, KeywordCluster

HAIKU_MODEL = "claude-haiku-4-5-20251001"

logger = get_logger(__name__)


class BlogTopicDiscoveryService:
    """Service for discovering blog topics from existing POP content briefs.

    Orchestrates topic discovery using:
    - POP briefs for seed extraction (related_searches, related_questions)
    - Claude for topic expansion and filtering
    - DataForSEO for search volume enrichment
    - Brand config context for brand-aware prompts
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        dataforseo_client: DataForSEOClient,
    ) -> None:
        self._claude = claude_client
        self._dataforseo = dataforseo_client

        logger.info(
            "BlogTopicDiscoveryService initialized",
            extra={
                "claude_available": claude_client.available,
                "dataforseo_available": dataforseo_client.available,
            },
        )

    @staticmethod
    def _build_brand_context(brand_config: dict[str, Any]) -> str:
        """Build a brand context string from v2_schema for prompt injection.

        Reuses the same extraction pattern as ClusterKeywordService._build_brand_context.
        """
        parts: list[str] = []

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

    async def extract_pop_seeds(
        self,
        cluster_id: str,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Stage 1: Extract seed topics from POP briefs on approved cluster pages.

        Queries approved ClusterPages that have linked CrawledPages with
        ContentBriefs. Extracts related_searches and related_questions from
        each brief's JSONB columns. Deduplicates and returns seeds with
        source_page_id.

        Returns:
            List of dicts with keys: seed, source_type, source_page_id.
        """
        # Query approved cluster pages that have a crawled_page_id
        stmt = (
            select(ClusterPage)
            .where(
                ClusterPage.cluster_id == cluster_id,
                ClusterPage.is_approved == True,  # noqa: E712
                ClusterPage.crawled_page_id.isnot(None),
            )
        )
        result = await db.execute(stmt)
        approved_pages = list(result.scalars().all())

        if not approved_pages:
            logger.warning(
                "No approved cluster pages with crawled_page_id found",
                extra={"cluster_id": cluster_id},
            )
            return []

        # Collect crawled_page_ids to look up content briefs
        crawled_page_ids = [p.crawled_page_id for p in approved_pages if p.crawled_page_id]

        # Query content briefs for those crawled pages
        brief_stmt = (
            select(ContentBrief)
            .where(ContentBrief.page_id.in_(crawled_page_ids))
        )
        brief_result = await db.execute(brief_stmt)
        briefs = list(brief_result.scalars().all())

        # Build page_id -> cluster_page_id mapping
        crawled_to_cluster: dict[str, str] = {}
        for cp in approved_pages:
            if cp.crawled_page_id:
                crawled_to_cluster[cp.crawled_page_id] = cp.id

        # Extract seeds from briefs
        seen: set[str] = set()
        seeds: list[dict[str, Any]] = []

        for brief in briefs:
            source_page_id = crawled_to_cluster.get(brief.page_id)

            # Extract related_searches (list[str])
            if isinstance(brief.related_searches, list):
                for search in brief.related_searches:
                    if isinstance(search, str):
                        normalized = search.strip().lower()
                        if normalized and normalized not in seen:
                            seen.add(normalized)
                            seeds.append({
                                "seed": normalized,
                                "source_type": "related_search",
                                "source_page_id": source_page_id,
                            })

            # Extract related_questions (list[str])
            if isinstance(brief.related_questions, list):
                for question in brief.related_questions:
                    if isinstance(question, str):
                        normalized = question.strip().lower()
                        if normalized and normalized not in seen:
                            seen.add(normalized)
                            seeds.append({
                                "seed": normalized,
                                "source_type": "related_question",
                                "source_page_id": source_page_id,
                            })

        logger.info(
            "Extracted POP seeds",
            extra={
                "cluster_id": cluster_id,
                "approved_pages": len(approved_pages),
                "briefs_found": len(briefs),
                "seeds_extracted": len(seeds),
            },
        )

        return seeds

    async def expand_topics(
        self,
        seeds: list[dict[str, Any]],
        brand_context: str,
    ) -> list[dict[str, Any]]:
        """Stage 2: Expand seeds into 15-25 blog topic candidates using Claude Haiku.

        Focuses on informational intent (how-to, guide, comparison, listicle).
        Tags each candidate with source_page_id from the seed that inspired it.

        Returns:
            List of candidate dicts with keys: topic, format_type, rationale,
            source_page_id.

        Raises:
            ValueError: If Claude returns unparseable JSON or too few candidates.
        """
        # Build seed summary for the prompt
        seed_lines: list[str] = []
        for i, s in enumerate(seeds, 1):
            seed_lines.append(
                f'{i}. "{s["seed"]}" (from {s["source_type"]})'
            )
        seeds_text = "\n".join(seed_lines)

        brand_section = ""
        if brand_context:
            brand_section = f"""
## Brand Context
{brand_context}

Use this context to ensure blog topics are relevant to the brand's audience and products.
"""

        prompt = f"""You are an SEO content strategist specializing in keyword research for blog content. Given seed topics from existing content briefs, generate 15-25 blog keyword candidates that people actually type into Google.

## Seed Topics (from POP content briefs)
{seeds_text}
{brand_section}
## CRITICAL: Generate Search Keywords, NOT Blog Titles
Your output must be **real search queries** — the exact phrases people type into Google. These will be validated against search volume data, so they must match how people actually search.

**DO:**
- "best joint supplements for dogs" (real search query)
- "glucosamine for dogs" (real search query)
- "how to help dog with arthritis" (real search query)
- "dog joint supplement reviews" (real search query)

**DO NOT:**
- "best joint supplements for senior dogs: a complete guide" (this is a blog title, not a search query)
- "glucosamine vs chondroitin for dogs: which works better" (nobody types colons into Google)
- "omega fatty acids for dogs: benefits for joint health and mobility" (way too long, title-style)

## Requirements
- Focus on **informational intent** — queries people search to learn, compare, or decide
- Keep keywords **short and natural** — 3-7 words, like actual Google searches
- NO colons, subtitles, or editorial phrasing
- Topics should be related to but distinct from the seed keywords
- Avoid overly broad topics (e.g., "shoes" is too broad; "how to clean white sneakers" is good)
- Avoid topics that would cannibalize collection/product pages

## Output Format
Return ONLY a JSON array of objects. No explanations, no markdown code blocks.
Each object must have:
- "topic": the search keyword/phrase people type into Google (lowercase, no colons or subtitles)
- "format_type": one of "how-to", "guide", "comparison", "listicle", "faq", "review"
- "rationale": brief reason why this is a good blog topic
- "source_seed_index": which seed number (1-based) inspired this topic

Example:
[{{"topic": "how to clean white sneakers", "format_type": "how-to", "rationale": "High search volume question related to product care", "source_seed_index": 3}}]"""

        result = await self._claude.complete(
            user_prompt=prompt,
            max_tokens=2000,
            temperature=0.4,
            model=HAIKU_MODEL,
        )

        if not result.success or not result.text:
            raise ValueError(
                f"Claude topic expansion failed: {result.error or 'Empty response'}"
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

        # Validate and enrich candidates with source_page_id
        valid_candidates: list[dict[str, Any]] = []
        for item in candidates:
            if not isinstance(item, dict):
                continue
            topic = item.get("topic")
            if not topic or not isinstance(topic, str):
                continue

            # Map source_seed_index back to source_page_id
            source_seed_index = item.get("source_seed_index")
            source_page_id = None
            if isinstance(source_seed_index, int) and 1 <= source_seed_index <= len(seeds):
                source_page_id = seeds[source_seed_index - 1].get("source_page_id")

            valid_candidates.append({
                "topic": topic.strip().lower(),
                "format_type": item.get("format_type", "guide"),
                "rationale": item.get("rationale", ""),
                "source_page_id": source_page_id,
            })

        if len(valid_candidates) < 5:
            raise ValueError(
                f"Too few valid candidates: {len(valid_candidates)} (expected 15-25)"
            )

        logger.info(
            "Expanded seeds into blog topic candidates",
            extra={
                "seed_count": len(seeds),
                "candidate_count": len(valid_candidates),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )

        return valid_candidates

    async def enrich_with_volume(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Stage 3: Enrich candidates with search volume data from DataForSEO.

        Reuses the exact pattern from ClusterKeywordService._enrich_with_volume.
        Filters zero-volume topics and merges volume/CPC/competition data.

        Returns:
            The same list of candidate dicts, enriched with search volume data.
            If DataForSEO is unavailable, candidates are returned with
            'volume_unavailable' set to True.
        """
        if not candidates:
            return candidates

        if not self._dataforseo.available:
            logger.warning(
                "DataForSEO not available, skipping blog topic volume enrichment",
                extra={"candidate_count": len(candidates)},
            )
            for candidate in candidates:
                candidate["volume_unavailable"] = True
            return candidates

        keywords = [c["topic"] for c in candidates]

        logger.info(
            "Enriching blog topic candidates with volume data",
            extra={"candidate_count": len(candidates)},
        )

        try:
            result = await self._dataforseo.get_keyword_volume_batch(keywords)

            if not result.success:
                logger.warning(
                    "DataForSEO volume lookup failed for blog topic candidates",
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
                normalized_kw = candidate["topic"].strip().lower()
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

            # Filter zero-volume topics
            before_count = len(candidates)
            candidates = [
                c for c in candidates
                if c.get("search_volume") and c["search_volume"] > 0
            ]
            filtered_count = before_count - len(candidates)

            logger.info(
                "Blog topic volume enrichment complete",
                extra={
                    "candidates_total": before_count,
                    "candidates_enriched": enriched_count,
                    "zero_volume_filtered": filtered_count,
                    "remaining": len(candidates),
                    "cost": result.cost,
                    "duration_ms": result.duration_ms,
                },
            )

            return candidates

        except Exception as e:
            logger.error(
                "Unexpected error during blog topic volume enrichment",
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
    def _topic_to_slug(topic: str) -> str:
        """Convert a blog topic to a URL-safe slug.

        Lowercase, replaces spaces/special chars with hyphens, strips leading/
        trailing hyphens, collapses consecutive hyphens, and truncates to 80 chars.
        """
        slug = topic.strip().lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s-]+", "-", slug)
        slug = slug.strip("-")
        if len(slug) > 80:
            slug = slug[:80].rstrip("-")
        return slug

    async def filter_and_rank(
        self,
        candidates: list[dict[str, Any]],
        cluster_name: str,
    ) -> list[dict[str, Any]]:
        """Stage 4: Filter to best 8-15 topics, remove near-duplicates, generate slugs.

        Uses Claude Haiku to intelligently filter and rank candidates.
        Assigns relevance scores and generates URL slugs.

        Returns:
            Filtered list of 8-15 candidates sorted by relevance_score descending.
            Each dict has: topic, format_type, url_slug, relevance_score,
            reasoning, search_volume, cpc, competition, competition_level,
            source_page_id.

        Raises:
            ValueError: If Claude returns unparseable JSON or too few results.
        """
        # Build candidate summary for the prompt
        candidate_lines: list[str] = []
        for i, c in enumerate(candidates, 1):
            vol = c.get("search_volume")
            cpc = c.get("cpc")
            comp = c.get("competition")
            vol_str = str(vol) if vol is not None else "N/A"
            cpc_str = f"${cpc:.2f}" if cpc is not None else "N/A"
            comp_str = f"{comp:.2f}" if comp is not None else "N/A"
            candidate_lines.append(
                f'{i}. "{c["topic"]}" — volume: {vol_str}, '
                f"CPC: {cpc_str}, competition: {comp_str}, "
                f'format: {c.get("format_type", "guide")}'
            )

        candidates_text = "\n".join(candidate_lines)

        prompt = f"""You are an SEO content strategist filtering blog topic candidates for a content campaign.

## Cluster/Niche
"{cluster_name}"

## Candidates (with search data)
{candidates_text}

## Your Task
Filter these candidates to the **best 8-15 blog topics**. Apply these rules:

### Selection Criteria
1. **Remove near-duplicates**: If two topics target the same search intent, keep only the one with higher volume
2. **Prioritize informational intent**: Blog posts should answer questions, teach, compare, or inform
3. **Prefer topics with search volume >= 50**: Only include lower-volume topics if they fill a critical content gap
4. **Diversity of format types**: Ensure a mix of how-to, guides, comparisons, and listicles
5. **Relevance to cluster**: Topics must be related to the "{cluster_name}" niche

### Scoring
- Assign a relevance_score from 0.0 to 1.0 for each topic
- Higher scores for: higher volume, clearer informational intent, stronger relevance to the cluster

### Content Classification
For each topic, assign:
- **format_type**: exactly one of "how-to", "guide", "comparison", "listicle", "faq", "review"
- **intent_type**: "informational" or "commercial"
  - "commercial" = money pages (comparison, "best X for Y", review, "vs" topics)
  - "informational" = everything else (how-to, guides, explainers, FAQ)
  Money pages earn the most AI citations and should be prioritized.

### URL Slugs
- Generate a blog URL slug for each topic (e.g., "how-to-clean-white-sneakers")
- Lowercase, hyphens instead of spaces, no special characters, max 80 characters

## Output Format
Return ONLY a JSON array of objects. No explanations, no markdown code blocks.
Each object must have:
- "source_index": the candidate number from the list above (1-based integer). This MUST match exactly — it is used to carry over search volume data.
- "topic": the blog topic keyword (lowercase). Use the EXACT keyword from the candidate list — do NOT rephrase.
- "topic_title": a compelling, SEO-friendly page title for this blog post (50-65 chars, title case)
- "alternative_keywords": 2-3 alternative keyword phrasings a user could target instead (lowercase). These should be semantically similar but vary in wording, long-tail phrasing, or angle.
- "format_type": one of "how-to", "guide", "comparison", "listicle", "faq", "review"
- "intent_type": "informational" or "commercial"
- "url_slug": the URL slug for /blog/
- "relevance_score": a score from 0.0 to 1.0
- "reasoning": why this topic was selected (brief)

Example:
[{{"source_index": 3, "topic": "best running shoes for flat feet", "topic_title": "Best Running Shoes for Flat Feet in 2025", "alternative_keywords": ["running shoes for flat feet", "top flat feet running shoes", "flat feet shoe recommendations"], "format_type": "comparison", "intent_type": "commercial", "url_slug": "best-running-shoes-for-flat-feet", "relevance_score": 0.95, "reasoning": "High-volume commercial comparison query — money page opportunity"}}]"""

        result = await self._claude.complete(
            user_prompt=prompt,
            max_tokens=3000,
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

        # Build lookups from original candidates for volume data and source_page_id
        # Index-based lookup (primary) + topic-string lookup (fallback)
        candidate_by_index: dict[int, dict[str, Any]] = {}
        candidate_by_topic: dict[str, dict[str, Any]] = {}
        for i, c in enumerate(candidates, 1):
            candidate_by_index[i] = c
            candidate_by_topic[c["topic"].strip().lower()] = c

        # Process filtered results
        results: list[dict[str, Any]] = []
        for item in filtered:
            if not isinstance(item, dict):
                continue
            topic = item.get("topic")
            if not topic or not isinstance(topic, str):
                continue

            topic_normalized = topic.strip().lower()

            # Look up original candidate: prefer source_index, fall back to topic match
            source_index = item.get("source_index")
            original: dict[str, Any] = {}
            if isinstance(source_index, int) and source_index in candidate_by_index:
                original = candidate_by_index[source_index]
            elif topic_normalized in candidate_by_topic:
                original = candidate_by_topic[topic_normalized]
            else:
                logger.warning(
                    "Stage 4 topic could not be matched to original candidate — "
                    "volume data will be lost",
                    extra={
                        "topic": topic_normalized,
                        "source_index": source_index,
                    },
                )

            url_slug = self._topic_to_slug(
                item.get("url_slug", topic_normalized)
            )
            relevance_score = item.get("relevance_score", 0.7)
            if not isinstance(relevance_score, (int, float)):
                relevance_score = 0.7

            # Determine intent_type (default to informational)
            intent_type = item.get("intent_type", "informational")
            if intent_type not in ("informational", "commercial"):
                intent_type = "informational"

            # Validate alternative_keywords
            raw_alts = item.get("alternative_keywords", [])
            alternative_keywords = [
                a.strip().lower()
                for a in raw_alts
                if isinstance(a, str) and a.strip()
            ][:3]

            results.append({
                "topic": topic_normalized,
                "topic_title": item.get("topic_title"),
                "alternative_keywords": alternative_keywords,
                "format_type": item.get("format_type", original.get("format_type", "guide")),
                "intent_type": intent_type,
                "url_slug": url_slug,
                "relevance_score": float(relevance_score),
                "reasoning": item.get("reasoning", ""),
                "search_volume": original.get("search_volume"),
                "cpc": original.get("cpc"),
                "competition": original.get("competition"),
                "competition_level": original.get("competition_level"),
                "source_page_id": original.get("source_page_id"),
            })

        # Sort by relevance_score descending
        results.sort(key=lambda x: -(x.get("relevance_score") or 0))

        logger.info(
            "Stage 4 filtering complete",
            extra={
                "cluster_name": cluster_name,
                "input_candidates": len(candidates),
                "output_results": len(results),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )

        return results

    async def discover_topics(
        self,
        cluster_id: str,
        project_id: str,
        brand_config: dict[str, Any],
        db: AsyncSession,
        name: str | None = None,
    ) -> dict[str, Any]:
        """Orchestrate topic discovery: Stage 1 → 2 → 3 → 4, then persist.

        Runs the four pipeline stages sequentially:
        1. Extract POP seeds from approved cluster pages
        2. Expand seeds into blog topic candidates (Claude Haiku)
        3. Enrich with search volume (DataForSEO, graceful degradation)
        4. Filter and rank candidates (Claude Haiku)

        On success, creates a BlogCampaign with status='planning' and
        BlogPost records with status='keyword_pending'.

        Args:
            cluster_id: UUID of the keyword cluster to discover topics for.
            project_id: UUID of the parent project.
            brand_config: The v2_schema dict from BrandConfig model.
            db: AsyncSession for database operations.
            name: Optional display name for the campaign.

        Returns:
            Dict with keys: campaign_id, suggestion_count, suggestions,
            generation_metadata, warnings.

        Raises:
            ValueError: If Stage 1 returns no seeds, or Stage 2/4 fails.
        """
        warnings: list[str] = []
        volume_unavailable = False

        # Build brand context
        brand_context = self._build_brand_context(brand_config)

        # --- Stage 1: Extract POP seeds ---
        t1_start = time.perf_counter()
        seeds = await self.extract_pop_seeds(cluster_id, db)
        t1_ms = round((time.perf_counter() - t1_start) * 1000)

        if not seeds:
            raise ValueError(
                "No seeds found — cluster has no approved pages with POP briefs. "
                "Approve cluster pages and run POP analysis first."
            )

        # --- Stage 2: Expand topics ---
        t2_start = time.perf_counter()
        try:
            candidates = await self.expand_topics(seeds, brand_context)
        except Exception as e:
            logger.error(
                "Stage 2 (topic expansion) failed",
                extra={"cluster_id": cluster_id, "error": str(e)},
                exc_info=True,
            )
            raise ValueError(f"Blog topic discovery failed at Stage 2: {e}") from e
        t2_ms = round((time.perf_counter() - t2_start) * 1000)

        # --- Stage 3: Enrich with volume ---
        t3_start = time.perf_counter()
        try:
            enriched = await self.enrich_with_volume(candidates)
            if enriched and enriched[0].get("volume_unavailable"):
                volume_unavailable = True
                warnings.append(
                    "Search volume data unavailable — DataForSEO lookup failed or not configured. "
                    "Filtering proceeded without volume data."
                )
                # Use all candidates without volume filtering
                candidates = enriched
            else:
                candidates = enriched
        except Exception as e:
            logger.warning(
                "Stage 3 (volume enrichment) failed, continuing without volume",
                extra={"cluster_id": cluster_id, "error": str(e)},
                exc_info=True,
            )
            volume_unavailable = True
            warnings.append(
                f"Search volume enrichment failed: {e}. "
                "Filtering proceeded without volume data."
            )
        t3_ms = round((time.perf_counter() - t3_start) * 1000)

        # Resolve cluster name for Stage 4
        cluster_result = await db.execute(
            select(KeywordCluster).where(KeywordCluster.id == cluster_id)
        )
        cluster = cluster_result.scalar_one_or_none()
        cluster_name = name or (cluster.name if cluster else "unknown")
        campaign_name = name or f"Blog: {cluster_name}"

        # --- Stage 4: Filter and rank ---
        t4_start = time.perf_counter()
        try:
            filtered = await self.filter_and_rank(candidates, cluster_name)
        except Exception as e:
            logger.error(
                "Stage 4 (filtering) failed",
                extra={"cluster_id": cluster_id, "error": str(e)},
                exc_info=True,
            )
            raise ValueError(f"Blog topic discovery failed at Stage 4: {e}") from e
        t4_ms = round((time.perf_counter() - t4_start) * 1000)

        # --- Enrich alternative keywords with volume data ---
        if not volume_unavailable and self._dataforseo.available:
            try:
                all_alt_keywords: list[str] = []
                for topic in filtered:
                    for kw in topic.get("alternative_keywords", []):
                        if isinstance(kw, str) and kw not in all_alt_keywords:
                            all_alt_keywords.append(kw)

                if all_alt_keywords:
                    alt_result = await self._dataforseo.get_keyword_volume_batch(
                        all_alt_keywords
                    )
                    if alt_result.success:
                        alt_volume_map: dict[str, int | None] = {}
                        for kw_data in alt_result.keywords:
                            alt_volume_map[kw_data.keyword.strip().lower()] = (
                                kw_data.search_volume
                            )

                        # Replace plain strings with {keyword, volume} dicts
                        for topic in filtered:
                            enriched_alts: list[dict[str, Any]] = []
                            for kw in topic.get("alternative_keywords", []):
                                vol = alt_volume_map.get(kw.strip().lower())
                                enriched_alts.append(
                                    {"keyword": kw, "volume": vol}
                                )
                            topic["alternative_keywords"] = enriched_alts

                        logger.info(
                            "Alternative keyword volume enrichment complete",
                            extra={
                                "alt_keywords_total": len(all_alt_keywords),
                                "alt_keywords_enriched": len(alt_volume_map),
                            },
                        )
                    else:
                        # Fallback: wrap as objects without volume
                        for topic in filtered:
                            topic["alternative_keywords"] = [
                                {"keyword": kw, "volume": None}
                                for kw in topic.get("alternative_keywords", [])
                                if isinstance(kw, str)
                            ]
                else:
                    # No alternatives to enrich — ensure consistent format
                    for topic in filtered:
                        topic["alternative_keywords"] = []

            except Exception as e:
                logger.warning(
                    "Alternative keyword enrichment failed, continuing without",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                for topic in filtered:
                    topic["alternative_keywords"] = [
                        {"keyword": kw, "volume": None}
                        for kw in topic.get("alternative_keywords", [])
                        if isinstance(kw, str)
                    ]
        else:
            # Volume unavailable — wrap alternatives as objects without volume
            for topic in filtered:
                topic["alternative_keywords"] = [
                    {"keyword": kw, "volume": None}
                    for kw in topic.get("alternative_keywords", [])
                    if isinstance(kw, str)
                ]

        total_ms = t1_ms + t2_ms + t3_ms + t4_ms

        generation_metadata: dict[str, Any] = {
            "stage1_time_ms": t1_ms,
            "stage2_time_ms": t2_ms,
            "stage3_time_ms": t3_ms,
            "stage4_time_ms": t4_ms,
            "total_time_ms": total_ms,
            "seeds_extracted": len(seeds),
            "candidates_expanded": len(candidates),
            "candidates_filtered": len(filtered),
            "volume_unavailable": volume_unavailable,
        }

        # --- Persist to database ---
        try:
            campaign = BlogCampaign(
                project_id=project_id,
                cluster_id=cluster_id,
                name=campaign_name,
                status=CampaignStatus.PLANNING.value,
                generation_metadata=generation_metadata,
            )
            db.add(campaign)
            await db.flush()  # Get campaign.id

            for topic_data in filtered:
                # Store format_type and intent_type in pop_brief JSONB
                # to avoid a DB migration
                discovery_metadata = {
                    "format_type": topic_data.get("format_type", "guide"),
                    "intent_type": topic_data.get("intent_type", "informational"),
                    "relevance_score": topic_data.get("relevance_score"),
                    "reasoning": topic_data.get("reasoning", ""),
                    "cpc": topic_data.get("cpc"),
                    "competition_level": topic_data.get("competition_level"),
                    "topic_title": topic_data.get("topic_title"),
                    "alternative_keywords": topic_data.get("alternative_keywords", []),
                }

                blog_post = BlogPost(
                    campaign_id=campaign.id,
                    primary_keyword=topic_data["topic"],
                    url_slug=topic_data["url_slug"],
                    search_volume=topic_data.get("search_volume"),
                    source_page_id=topic_data.get("source_page_id"),
                    status=PostStatus.KEYWORD_PENDING.value,
                    pop_brief={"discovery_metadata": discovery_metadata},
                )
                db.add(blog_post)

            await db.commit()

            logger.info(
                "Blog topic discovery complete",
                extra={
                    "campaign_id": campaign.id,
                    "cluster_id": cluster_id,
                    "posts_created": len(filtered),
                    "total_time_ms": total_ms,
                },
            )

            return {
                "campaign_id": campaign.id,
                "suggestion_count": len(filtered),
                "suggestions": filtered,
                "generation_metadata": generation_metadata,
                "warnings": warnings,
            }

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to persist blog campaign to database",
                extra={"cluster_id": cluster_id, "error": str(e)},
                exc_info=True,
            )
            raise ValueError(
                f"Blog topic discovery failed during persistence: {e}"
            ) from e
