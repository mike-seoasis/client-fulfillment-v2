"""Link planning service for building link graphs and selecting targets.

SiloLinkPlanner constructs two types of graphs:
- Cluster graph: parent/child + sibling adjacency from ClusterPage records
- Onboarding graph: pairwise label-overlap edges from onboarding CrawledPages

Target selection uses budgets (based on word count) to determine how many
outbound links each page gets, then selects the best targets per scope rules.

AnchorTextSelector handles anchor text diversity:
- Gathers candidates from primary keywords, POP variations, and LLM phrases
- Selects anchors with diversity tracking to avoid repetition
- Targets ~50-60% partial_match, ~10% exact_match, ~30% natural distribution
"""

import json
from itertools import combinations
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_api_key
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.keyword_cluster import ClusterPage
from app.models.page_content import PageContent
from app.models.page_keywords import PageKeywords

logger = get_logger(__name__)

# Haiku model for generating natural anchor text phrases
ANCHOR_LLM_MODEL = "claude-haiku-4-5-20251001"
ANCHOR_LLM_MAX_TOKENS = 256
ANCHOR_LLM_TEMPERATURE = 0.7

# Maximum times the same anchor text can be used for the same target
MAX_ANCHOR_REUSE = 3

LABEL_OVERLAP_THRESHOLD = 2


class SiloLinkPlanner:
    """Builds link graphs for cluster and onboarding page sets."""

    async def build_cluster_graph(
        self,
        cluster_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Build adjacency graph from cluster pages using parent/child hierarchy.

        Returns {pages: [...], edges: [...]} where edges have type
        'parent_child' or 'sibling'.
        """
        stmt = (
            select(ClusterPage)
            .options(joinedload(ClusterPage.crawled_page))
            .where(ClusterPage.cluster_id == cluster_id)
        )
        result = await db.execute(stmt)
        cluster_pages = result.unique().scalars().all()

        if len(cluster_pages) <= 1:
            pages = [
                {
                    "page_id": cp.id,
                    "crawled_page_id": cp.crawled_page_id,
                    "keyword": cp.keyword,
                    "role": cp.role,
                    "composite_score": cp.composite_score or 0.0,
                    "url": cp.crawled_page.normalized_url if cp.crawled_page else None,
                }
                for cp in cluster_pages
            ]
            return {"pages": pages, "edges": []}

        parents: list[ClusterPage] = []
        children: list[ClusterPage] = []
        for cp in cluster_pages:
            if cp.role == "parent":
                parents.append(cp)
            else:
                children.append(cp)

        pages = [
            {
                "page_id": cp.id,
                "crawled_page_id": cp.crawled_page_id,
                "keyword": cp.keyword,
                "role": cp.role,
                "composite_score": cp.composite_score or 0.0,
                "url": cp.crawled_page.normalized_url if cp.crawled_page else None,
            }
            for cp in cluster_pages
        ]

        edges: list[dict[str, str]] = []

        # Parent-child edges
        for parent in parents:
            for child in children:
                edges.append(
                    {
                        "source": parent.id,
                        "target": child.id,
                        "type": "parent_child",
                    }
                )

        # Sibling edges among children
        for a, b in combinations(children, 2):
            edges.append(
                {
                    "source": a.id,
                    "target": b.id,
                    "type": "sibling",
                }
            )

        logger.info(
            "Built cluster graph",
            extra={
                "cluster_id": cluster_id,
                "page_count": len(pages),
                "edge_count": len(edges),
            },
        )

        return {"pages": pages, "edges": edges}

    async def build_onboarding_graph(
        self,
        project_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Build label-overlap graph from onboarding pages.

        Only includes pages where PageContent.status='complete' and
        PageKeywords.is_approved=True. Edges are created between page pairs
        with label overlap >= LABEL_OVERLAP_THRESHOLD.
        """
        stmt = (
            select(CrawledPage)
            .join(PageContent, PageContent.crawled_page_id == CrawledPage.id)
            .join(PageKeywords, PageKeywords.crawled_page_id == CrawledPage.id)
            .where(
                CrawledPage.project_id == project_id,
                CrawledPage.source == "onboarding",
                PageContent.status == "complete",
                PageKeywords.is_approved.is_(True),
            )
            .options(joinedload(CrawledPage.keywords))
        )
        result = await db.execute(stmt)
        crawled_pages = result.unique().scalars().all()

        pages = [
            {
                "page_id": cp.id,
                "keyword": cp.keywords.primary_keyword if cp.keywords else "",
                "url": cp.normalized_url,
                "labels": cp.labels or [],
                "is_priority": cp.keywords.is_priority if cp.keywords else False,
            }
            for cp in crawled_pages
        ]

        edges: list[dict[str, Any]] = []
        for a, b in combinations(crawled_pages, 2):
            labels_a = set(a.labels or [])
            labels_b = set(b.labels or [])
            overlap = len(labels_a & labels_b)
            if overlap >= LABEL_OVERLAP_THRESHOLD:
                edges.append(
                    {
                        "source": a.id,
                        "target": b.id,
                        "weight": overlap,
                    }
                )

        logger.info(
            "Built onboarding graph",
            extra={
                "project_id": project_id,
                "page_count": len(pages),
                "edge_count": len(edges),
            },
        )

        return {"pages": pages, "edges": edges}


def calculate_budget(word_count: int) -> int:
    """Calculate the link budget for a page based on word count.

    Formula: clamp(word_count // 250, 3, 5)
    - Minimum 3 links regardless of word count
    - Maximum 5 links regardless of word count
    - 1 link per ~250 words in between
    """
    return max(3, min(word_count // 250, 5))


def select_targets_cluster(
    graph: dict[str, Any],
    budgets: dict[str, int],
) -> dict[str, list[dict[str, Any]]]:
    """Select link targets for each page in a cluster graph.

    For parent pages: select children sorted by composite_score (highest first).
    For child pages: slot 1 = parent (mandatory), remaining = siblings sorted
    by composite_score then least-linked-to.

    Args:
        graph: Output from build_cluster_graph with pages and edges.
        budgets: Dict mapping page_id to link budget (from calculate_budget).

    Returns:
        Dict mapping page_id to list of target dicts with page_id, keyword,
        url, is_mandatory, and composite_score.
    """
    # Identify parents and children
    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []
    for page in graph["pages"]:
        if page["role"] == "parent":
            parents.append(page)
        else:
            children.append(page)

    # Sort children by composite_score descending for consistent ordering
    children_sorted = sorted(
        children, key=lambda p: p.get("composite_score", 0.0), reverse=True
    )

    # Track inbound link counts for least-linked-to tiebreaker
    inbound_counts: dict[str, int] = {p["page_id"]: 0 for p in graph["pages"]}

    result: dict[str, list[dict[str, Any]]] = {}

    # Process parent pages first: select children by composite_score
    for parent in parents:
        budget = budgets.get(parent["page_id"], 3)
        targets: list[dict[str, Any]] = []

        for child in children_sorted:
            if len(targets) >= budget:
                break
            targets.append(
                {
                    "page_id": child["page_id"],
                    "keyword": child["keyword"],
                    "url": child["url"],
                    "is_mandatory": False,
                    "composite_score": child.get("composite_score", 0.0),
                }
            )
            inbound_counts[child["page_id"]] += 1

        result[parent["page_id"]] = targets

    # Process child pages: slot 1 = parent (mandatory), rest = siblings
    for child in children:
        budget = budgets.get(child["page_id"], 3)
        targets = []

        # Slot 1: mandatory parent link
        if parents:
            parent = parents[0]  # Clusters have one parent
            targets.append(
                {
                    "page_id": parent["page_id"],
                    "keyword": parent["keyword"],
                    "url": parent["url"],
                    "is_mandatory": True,
                    "composite_score": parent.get("composite_score", 0.0),
                }
            )
            inbound_counts[parent["page_id"]] += 1

        # Remaining slots: siblings by composite_score then least-linked-to
        siblings = [s for s in children_sorted if s["page_id"] != child["page_id"]]
        # Sort by composite_score desc, then by inbound_counts asc (least-linked-to)
        siblings_ranked = sorted(
            siblings,
            key=lambda s: (
                -s.get("composite_score", 0.0),
                inbound_counts.get(s["page_id"], 0),
            ),
        )

        for sibling in siblings_ranked:
            if len(targets) >= budget:
                break
            targets.append(
                {
                    "page_id": sibling["page_id"],
                    "keyword": sibling["keyword"],
                    "url": sibling["url"],
                    "is_mandatory": False,
                    "composite_score": sibling.get("composite_score", 0.0),
                }
            )
            inbound_counts[sibling["page_id"]] += 1

        result[child["page_id"]] = targets

    logger.info(
        "Selected cluster targets",
        extra={
            "page_count": len(result),
            "total_links": sum(len(t) for t in result.values()),
        },
    )

    return result


def select_targets_onboarding(
    graph: dict[str, Any],
    budgets: dict[str, int],
) -> dict[str, list[dict[str, Any]]]:
    """Select link targets for each page in an onboarding graph.

    Scores each eligible target per page:
        score = label_overlap + (2 if target is_priority else 0) - diversity_penalty
    where diversity_penalty = max(0, (inbound_counts[target] - avg_inbound) * 0.5)

    Selects top N within budget. Updates inbound counts after each page
    to spread links across targets.

    Args:
        graph: Output from build_onboarding_graph with pages and edges.
        budgets: Dict mapping page_id to link budget (from calculate_budget).

    Returns:
        Dict mapping page_id to list of target dicts with page_id, keyword,
        url, is_priority, label_overlap, and score.
    """
    pages_by_id: dict[str, dict[str, Any]] = {p["page_id"]: p for p in graph["pages"]}

    # Build adjacency map: page_id -> {neighbor_page_id: overlap_weight}
    adjacency: dict[str, dict[str, int]] = {p["page_id"]: {} for p in graph["pages"]}
    for edge in graph["edges"]:
        adjacency[edge["source"]][edge["target"]] = edge["weight"]
        adjacency[edge["target"]][edge["source"]] = edge["weight"]

    # Running inbound counts for diversity penalty
    inbound_counts: dict[str, int] = {p["page_id"]: 0 for p in graph["pages"]}

    result: dict[str, list[dict[str, Any]]] = {}

    for page in graph["pages"]:
        page_id = page["page_id"]
        budget = budgets.get(page_id, 3)
        neighbors = adjacency.get(page_id, {})

        if not neighbors:
            result[page_id] = []
            continue

        # Calculate average inbound across all pages for diversity penalty
        total_inbound = sum(inbound_counts.values())
        page_count = len(graph["pages"])
        avg_inbound = total_inbound / page_count if page_count > 0 else 0.0

        # Score each eligible target
        scored_targets: list[tuple[float, str]] = []
        for target_id, overlap in neighbors.items():
            target_page = pages_by_id[target_id]
            priority_bonus = 2.0 if target_page.get("is_priority") else 0.0
            excess_inbound = inbound_counts[target_id] - avg_inbound
            diversity_penalty = max(0.0, excess_inbound * 0.5)
            score = overlap + priority_bonus - diversity_penalty
            scored_targets.append((score, target_id))

        # Sort by score descending, then by page_id for stable ordering
        scored_targets.sort(key=lambda x: (-x[0], x[1]))

        # Select top N within budget
        targets: list[dict[str, Any]] = []
        for score, target_id in scored_targets:
            if len(targets) >= budget:
                break
            target_page = pages_by_id[target_id]
            targets.append(
                {
                    "page_id": target_id,
                    "keyword": target_page["keyword"],
                    "url": target_page["url"],
                    "is_priority": target_page.get("is_priority", False),
                    "label_overlap": neighbors[target_id],
                    "score": score,
                }
            )
            inbound_counts[target_id] += 1

        result[page_id] = targets

    logger.info(
        "Selected onboarding targets",
        extra={
            "page_count": len(result),
            "total_links": sum(len(t) for t in result.values()),
        },
    )

    return result


class AnchorTextSelector:
    """Selects diverse, SEO-optimized anchor text for internal links.

    Gathers candidates from three sources:
    1. Primary keyword (exact_match) from PageKeywords
    2. POP keyword variations (partial_match) from ContentBrief.keyword_targets
    3. LLM-generated natural phrases (natural) from Claude Haiku

    Tracks usage across a planning run to ensure diversity and avoid
    over-using the same anchor text for the same target page.
    """

    async def gather_candidates(
        self,
        target_page_id: str,
        db: AsyncSession,
    ) -> list[dict[str, Any]]:
        """Gather anchor text candidates for a target page.

        Returns candidates from 3 sources:
        - primary keyword tagged as 'exact_match'
        - POP keyword_targets variations tagged as 'partial_match'
        - Placeholder for LLM natural phrases (populated by generate_natural_phrases)

        Args:
            target_page_id: The crawled page ID to gather candidates for.
            db: Async database session.

        Returns:
            List of dicts with keys: anchor_text, anchor_type.
        """
        candidates: list[dict[str, Any]] = []

        # Source 1: Primary keyword from PageKeywords (exact_match)
        pk_stmt = select(PageKeywords).where(
            PageKeywords.crawled_page_id == target_page_id,
            PageKeywords.is_approved.is_(True),
        )
        pk_result = await db.execute(pk_stmt)
        page_kw = pk_result.scalars().first()

        primary_keyword: str | None = None
        if page_kw and page_kw.primary_keyword:
            primary_keyword = page_kw.primary_keyword
            candidates.append(
                {
                    "anchor_text": primary_keyword,
                    "anchor_type": "exact_match",
                }
            )

        # Source 2: POP keyword variations from ContentBrief (partial_match)
        cb_stmt = select(ContentBrief).where(
            ContentBrief.page_id == target_page_id,
        )
        cb_result = await db.execute(cb_stmt)
        content_brief = cb_result.scalars().first()

        if content_brief and content_brief.keyword_targets:
            for kt in content_brief.keyword_targets:
                kw = kt.get("keyword", "") if isinstance(kt, dict) else str(kt)
                # Skip the primary keyword (already added as exact_match)
                if kw and (
                    not primary_keyword or kw.lower() != primary_keyword.lower()
                ):
                    candidates.append(
                        {
                            "anchor_text": kw,
                            "anchor_type": "partial_match",
                        }
                    )

        # If no POP variations, add secondary keywords from PageKeywords as fallback
        if (
            not any(c["anchor_type"] == "partial_match" for c in candidates)
            and page_kw
            and page_kw.secondary_keywords
        ):
            for sk in page_kw.secondary_keywords:
                kw = str(sk) if sk else ""
                if kw:
                    candidates.append(
                        {
                            "anchor_text": kw,
                            "anchor_type": "partial_match",
                        }
                    )

        logger.info(
            "Gathered anchor candidates",
            extra={
                "target_page_id": target_page_id,
                "candidate_count": len(candidates),
                "types": {c["anchor_type"] for c in candidates},
            },
        )

        return candidates

    async def generate_natural_phrases(
        self,
        keywords: dict[str, str],
    ) -> dict[str, list[dict[str, Any]]]:
        """Generate natural anchor text phrases for multiple target pages via Claude Haiku.

        Batches all keywords into a single LLM call for efficiency.

        Args:
            keywords: Dict mapping target_page_id to primary keyword.

        Returns:
            Dict mapping target_page_id to list of candidate dicts with
            anchor_text and anchor_type='natural'.
        """
        if not keywords:
            return {}

        # Build a single batched prompt
        lines = []
        for i, (page_id, keyword) in enumerate(keywords.items()):
            lines.append(f"{i + 1}. [{page_id}] {keyword}")

        prompt = (
            "Generate 2-3 natural anchor text phrases (2-5 words each) for linking "
            "to pages about the following keywords. Phrases should read naturally "
            "in a sentence.\n\n"
            + "\n".join(lines)
            + "\n\nRespond with JSON only. Format:\n"
            '{"results": [{"id": "<page_id>", "phrases": ["phrase1", "phrase2"]}]}'
        )

        client = ClaudeClient(api_key=get_api_key())
        try:
            result = await client.complete(
                user_prompt=prompt,
                model=ANCHOR_LLM_MODEL,
                max_tokens=ANCHOR_LLM_MAX_TOKENS,
                temperature=ANCHOR_LLM_TEMPERATURE,
            )

            if not result.success or not result.text:
                logger.warning(
                    "LLM natural phrase generation failed",
                    extra={"error": result.error},
                )
                return {}

            # Parse response JSON
            response_text = result.text.strip()
            # Handle markdown code blocks
            if response_text.startswith("```"):
                response_lines = response_text.split("\n")
                response_lines = response_lines[1:]
                if response_lines and response_lines[-1].strip() == "```":
                    response_lines = response_lines[:-1]
                response_text = "\n".join(response_lines)

            parsed = json.loads(response_text)
            results_list = parsed.get("results", [])

            natural_candidates: dict[str, list[dict[str, Any]]] = {}
            for item in results_list:
                pid = item.get("id", "")
                phrases = item.get("phrases", [])
                if pid in keywords:
                    natural_candidates[pid] = [
                        {"anchor_text": p.strip(), "anchor_type": "natural"}
                        for p in phrases
                        if isinstance(p, str) and p.strip()
                    ]

            logger.info(
                "Generated natural anchor phrases",
                extra={
                    "page_count": len(natural_candidates),
                    "total_phrases": sum(len(v) for v in natural_candidates.values()),
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                },
            )

            return natural_candidates

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(
                "Failed to parse LLM natural phrases",
                extra={"error": str(e)},
            )
            return {}
        finally:
            await client.close()

    def select_anchor(
        self,
        candidates: list[dict[str, Any]],
        source_content: str,
        target_page_id: str,
        usage_tracker: dict[str, dict[str, int]],
    ) -> dict[str, Any] | None:
        """Select the best anchor text from candidates with diversity scoring.

        Scoring:
        - diversity_bonus: Fewer prior uses of this anchor for this target = higher
        - context_fit: +2 if anchor text appears in source content
        - Distribution targets: ~50-60% partial_match, ~10% exact_match, ~30% natural

        Rejects anchors used >= MAX_ANCHOR_REUSE times for the same target.

        Args:
            candidates: List of candidate dicts from gather_candidates.
            source_content: Text content of the source page (for context_fit).
            target_page_id: The target page these anchors link to.
            usage_tracker: Dict[target_page_id, Dict[anchor_text, count]].
                Mutated in-place to track usage.

        Returns:
            Dict with anchor_text, anchor_type, score. None if no viable candidate.
        """
        if not candidates:
            return None

        target_usage = usage_tracker.get(target_page_id, {})
        source_lower = source_content.lower()

        # Distribution weight by type (higher = preferred for distribution targets)
        type_weights = {
            "partial_match": 1.5,  # 50-60% target
            "natural": 1.0,  # ~30% target
            "exact_match": 0.3,  # ~10% target
        }

        scored: list[tuple[float, dict[str, Any]]] = []

        for candidate in candidates:
            anchor = candidate["anchor_text"]
            anchor_type = candidate["anchor_type"]
            use_count = target_usage.get(anchor, 0)

            # Reject if over-used
            if use_count >= MAX_ANCHOR_REUSE:
                continue

            # Diversity bonus: fewer uses = higher score
            diversity_bonus = max(0.0, 3.0 - use_count)

            # Context fit: anchor appears in source content
            context_fit = 2.0 if anchor.lower() in source_lower else 0.0

            # Type weight for distribution balance
            type_weight = type_weights.get(anchor_type, 1.0)

            score = diversity_bonus + context_fit + type_weight
            scored.append((score, candidate))

        if not scored:
            return None

        # Sort by score descending, stable on anchor_text for determinism
        scored.sort(key=lambda x: (-x[0], x[1]["anchor_text"]))

        best_score, best_candidate = scored[0]

        # Update usage tracker
        if target_page_id not in usage_tracker:
            usage_tracker[target_page_id] = {}
        usage_tracker[target_page_id][best_candidate["anchor_text"]] = (
            target_usage.get(best_candidate["anchor_text"], 0) + 1
        )

        return {
            "anchor_text": best_candidate["anchor_text"],
            "anchor_type": best_candidate["anchor_type"],
            "score": best_score,
        }
