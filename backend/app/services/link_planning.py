"""Link planning service for building link graphs, selecting targets, and orchestrating
the full link planning pipeline.

SiloLinkPlanner constructs three types of graphs:
- Cluster graph: parent/child + sibling adjacency from ClusterPage records
- Onboarding graph: pairwise label-overlap edges from onboarding CrawledPages
- Blog graph: blog posts link UP to cluster pages and sideways to sibling blogs

Target selection uses budgets (based on word count) to determine how many
outbound links each page gets, then selects the best targets per scope rules.

AnchorTextSelector handles anchor text diversity:
- Gathers candidates from primary keywords, POP variations, and LLM phrases
- Selects anchors with diversity tracking to avoid repetition
- Targets ~50-60% partial_match, ~10% exact_match, ~30% natural distribution

Pipeline orchestrator (run_link_planning_pipeline) runs the 4-step sequence:
1. Build link graph
2. Select targets + anchor text
3. Inject links (rule-based + LLM fallback)
4. Validate all rules
"""

import json
from itertools import combinations
from typing import Any, Literal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import db_manager
from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_api_key
from app.models.blog import BlogCampaign, BlogPost
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.internal_link import InternalLink, LinkPlanSnapshot
from app.models.keyword_cluster import ClusterPage
from app.models.page_content import PageContent
from app.models.page_keywords import PageKeywords
from app.models.project import Project
from app.services.link_injection import (
    LinkInjector,
    LinkValidator,
    strip_internal_links,
)

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
        all_cluster_pages = result.unique().scalars().all()

        # Filter to only approved pages with a valid crawled_page_id
        cluster_pages = [
            cp
            for cp in all_cluster_pages
            if cp.crawled_page_id is not None and cp.is_approved
        ]

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
        """Build label-overlap graph from collection pages.

        Includes both onboarding pages and cluster pages with approved content.
        Only includes pages where PageContent.status='complete' and
        PageKeywords.is_approved=True. Cluster pages additionally require
        PageContent.is_approved=True (export-ready).
        """
        from sqlalchemy import and_, or_

        stmt = (
            select(CrawledPage)
            .join(PageContent, PageContent.crawled_page_id == CrawledPage.id)
            .join(PageKeywords, PageKeywords.crawled_page_id == CrawledPage.id)
            .where(
                CrawledPage.project_id == project_id,
                or_(
                    CrawledPage.source == "onboarding",
                    and_(
                        CrawledPage.source == "cluster",
                        PageContent.is_approved.is_(True),
                    ),
                ),
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

        # Build a fully-connected graph: every page can potentially link to
        # every other page. Label overlap is used as the edge weight so that
        # target selection prefers topically related pages, but no page is
        # excluded. Budgets (3-5 links per page) constrain link density.
        edges: list[dict[str, Any]] = []
        for a, b in combinations(crawled_pages, 2):
            labels_a = set(a.labels or [])
            labels_b = set(b.labels or [])
            overlap = len(labels_a & labels_b)
            # Minimum weight of 1 so even pages with no label overlap
            # get a non-zero base score in target selection
            edges.append(
                {
                    "source": a.id,
                    "target": b.id,
                    "weight": max(overlap, 1),
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

    async def build_blog_graph(
        self,
        campaign_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Build link graph for blog posts within a campaign's cluster silo.

        Blog posts are leaf nodes. They link:
        - UP to cluster pages (2-4 links, parent page mandatory as first)
        - SIDEWAYS to sibling blogs (1-2 links)
        Total budget: 3-6 per blog post. Links never cross outside the cluster.

        Creates CrawledPage records (source='blog') to bridge blog posts into
        the InternalLink infrastructure which uses CrawledPage IDs.

        Returns {blog_posts: [...], cluster_pages: [...], edges: [...]}
        where each blog_post has a crawled_page_id for InternalLink bridging.
        """
        # Load campaign to get cluster_id and project_id
        campaign_stmt = select(BlogCampaign).where(BlogCampaign.id == campaign_id)
        campaign_result = await db.execute(campaign_stmt)
        campaign = campaign_result.scalar_one_or_none()
        if campaign is None:
            raise ValueError(f"Blog campaign {campaign_id} not found")

        cluster_id = campaign.cluster_id
        project_id = campaign.project_id

        # Load approved blog posts for this campaign
        posts_stmt = select(BlogPost).where(
            BlogPost.campaign_id == campaign_id,
            BlogPost.is_approved.is_(True),
            BlogPost.content.isnot(None),
        )
        posts_result = await db.execute(posts_stmt)
        blog_posts = list(posts_result.scalars().all())

        if not blog_posts:
            return {"blog_posts": [], "cluster_pages": [], "edges": []}

        # Load approved cluster pages (link targets)
        cluster_stmt = (
            select(ClusterPage)
            .options(joinedload(ClusterPage.crawled_page))
            .where(
                ClusterPage.cluster_id == cluster_id,
                ClusterPage.is_approved.is_(True),
            )
        )
        cluster_result = await db.execute(cluster_stmt)
        cluster_pages = [
            cp
            for cp in cluster_result.unique().scalars().all()
            if cp.crawled_page_id is not None
        ]

        # Create or reuse CrawledPage records for blog posts (source='blog')
        blog_crawled_map: dict[str, str] = {}  # blog_post.id -> crawled_page_id
        for post in blog_posts:
            # Check if CrawledPage already exists for this blog post slug
            existing_stmt = select(CrawledPage).where(
                CrawledPage.project_id == project_id,
                CrawledPage.normalized_url == post.url_slug,
                CrawledPage.source == "blog",
            )
            existing_result = await db.execute(existing_stmt)
            crawled_page = existing_result.scalar_one_or_none()

            if crawled_page is None:
                crawled_page = CrawledPage(
                    project_id=project_id,
                    normalized_url=post.url_slug,
                    source="blog",
                    status=CrawlStatus.COMPLETED.value,
                    category="blog",
                    title=post.title or post.primary_keyword,
                    word_count=len((post.content or "").split()),
                )
                db.add(crawled_page)
                await db.flush()

            blog_crawled_map[post.id] = crawled_page.id

        # Build graph nodes
        blog_post_nodes = [
            {
                "post_id": post.id,
                "crawled_page_id": blog_crawled_map[post.id],
                "keyword": post.primary_keyword,
                "url_slug": post.url_slug,
                "role": "blog",
            }
            for post in blog_posts
        ]

        cluster_page_nodes = [
            {
                "page_id": cp.id,
                "crawled_page_id": cp.crawled_page_id,
                "keyword": cp.keyword,
                "role": cp.role,
                "url": cp.crawled_page.normalized_url if cp.crawled_page else None,
            }
            for cp in cluster_pages
        ]

        # Build edges: blog → cluster pages (UP) and blog → sibling blogs (SIDEWAYS)
        edges: list[dict[str, Any]] = []

        for post_node in blog_post_nodes:
            # UP edges: blog → each cluster page
            for cp_node in cluster_page_nodes:
                edges.append(
                    {
                        "source": post_node["crawled_page_id"],
                        "target": cp_node["crawled_page_id"],
                        "type": "blog_to_cluster",
                        "target_role": cp_node["role"],
                    }
                )

            # SIDEWAYS edges: blog → sibling blogs
            for sibling_node in blog_post_nodes:
                if sibling_node["post_id"] != post_node["post_id"]:
                    edges.append(
                        {
                            "source": post_node["crawled_page_id"],
                            "target": sibling_node["crawled_page_id"],
                            "type": "blog_to_blog",
                        }
                    )

        logger.info(
            "Built blog graph",
            extra={
                "campaign_id": campaign_id,
                "blog_count": len(blog_post_nodes),
                "cluster_page_count": len(cluster_page_nodes),
                "edge_count": len(edges),
            },
        )

        return {
            "blog_posts": blog_post_nodes,
            "cluster_pages": cluster_page_nodes,
            "edges": edges,
        }


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

    # Build ClusterPage.id → crawled_page_id lookup for target dicts
    cp_to_crawled: dict[str, str] = {}
    for page in graph["pages"]:
        cp_id = page.get("page_id", "")
        crawled_id = page.get("crawled_page_id")
        if cp_id and crawled_id:
            cp_to_crawled[cp_id] = crawled_id

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
                    "crawled_page_id": cp_to_crawled.get(child["page_id"]),
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
                    "crawled_page_id": cp_to_crawled.get(parent["page_id"]),
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
                    "crawled_page_id": cp_to_crawled.get(sibling["page_id"]),
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


def select_targets_blog(
    graph: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Select link targets for each blog post in a blog graph.

    Blog posts link UP to cluster pages (2-4, parent mandatory as first)
    and SIDEWAYS to sibling blogs (1-2). Total budget: 3-6.

    Args:
        graph: Output from build_blog_graph with blog_posts, cluster_pages, edges.

    Returns:
        Dict mapping blog crawled_page_id to list of target dicts.
    """
    blog_posts = graph["blog_posts"]
    cluster_pages = graph["cluster_pages"]

    # Identify parent and child cluster pages
    parent_pages = [cp for cp in cluster_pages if cp["role"] == "parent"]
    child_pages = [cp for cp in cluster_pages if cp["role"] != "parent"]

    # Track inbound counts for diversity
    inbound_counts: dict[str, int] = {}
    for cp in cluster_pages:
        inbound_counts[cp["crawled_page_id"]] = 0
    for bp in blog_posts:
        inbound_counts[bp["crawled_page_id"]] = 0

    result: dict[str, list[dict[str, Any]]] = {}

    for blog_node in blog_posts:
        source_id = blog_node["crawled_page_id"]
        targets: list[dict[str, Any]] = []

        # Slot 1: mandatory parent link (first link)
        if parent_pages:
            parent = parent_pages[0]
            targets.append(
                {
                    "crawled_page_id": parent["crawled_page_id"],
                    "keyword": parent["keyword"],
                    "url": parent.get("url"),
                    "is_mandatory": True,
                    "role": "parent",
                }
            )
            inbound_counts[parent["crawled_page_id"]] += 1

        # Slots 2-4: additional cluster pages (children), sorted by least-linked
        children_ranked = sorted(
            child_pages,
            key=lambda c: inbound_counts.get(c["crawled_page_id"], 0),
        )
        cluster_link_budget = min(
            3, len(children_ranked)
        )  # 2-4 total cluster links (1 parent + up to 3 children)
        for child in children_ranked:
            if len(targets) >= 1 + cluster_link_budget:
                break
            targets.append(
                {
                    "crawled_page_id": child["crawled_page_id"],
                    "keyword": child["keyword"],
                    "url": child.get("url"),
                    "is_mandatory": False,
                    "role": "child",
                }
            )
            inbound_counts[child["crawled_page_id"]] += 1

        # Sideways slots: 1-2 sibling blogs
        siblings = [bp for bp in blog_posts if bp["post_id"] != blog_node["post_id"]]
        siblings_ranked = sorted(
            siblings,
            key=lambda s: inbound_counts.get(s["crawled_page_id"], 0),
        )
        sibling_budget = min(2, len(siblings_ranked))
        for sibling in siblings_ranked[:sibling_budget]:
            targets.append(
                {
                    "crawled_page_id": sibling["crawled_page_id"],
                    "keyword": sibling["keyword"],
                    "url": sibling.get("url_slug"),
                    "is_mandatory": False,
                    "role": "blog",
                }
            )
            inbound_counts[sibling["crawled_page_id"]] += 1

        # Enforce total budget cap of 6
        targets = targets[:6]
        result[source_id] = targets

    logger.info(
        "Selected blog targets",
        extra={
            "blog_count": len(result),
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


# ---------------------------------------------------------------------------
# Pipeline progress tracking
# ---------------------------------------------------------------------------

# Module-level dict for progress polling, keyed by (project_id, scope, cluster_id).
# Follows the same pattern as content_generation.py's background task state.
_pipeline_progress: dict[tuple[str, str, str | None], dict[str, Any]] = {}


def get_pipeline_progress(
    project_id: str,
    scope: str,
    cluster_id: str | None = None,
) -> dict[str, Any] | None:
    """Return the current pipeline progress for a given key, or None if not running."""
    return _pipeline_progress.get((project_id, scope, cluster_id))


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------


async def run_link_planning_pipeline(
    project_id: str,
    scope: Literal["onboarding", "cluster"],
    cluster_id: str | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Run the full link planning pipeline: graph → targets → inject → validate.

    Designed to be called from a FastAPI BackgroundTask. Tracks progress in the
    module-level ``_pipeline_progress`` dict so the frontend can poll status.

    Args:
        project_id: UUID of the project.
        scope: 'onboarding' or 'cluster'.
        cluster_id: Required when scope='cluster', None for onboarding.
        db: Async database session (used for read-only graph building; the
            pipeline creates its own sessions for writes to enable rollback).

    Returns:
        Dict with pipeline result summary.
    """
    progress_key = (project_id, scope, cluster_id)
    progress: dict[str, Any] = {
        "current_step": 1,
        "step_label": "Building link graph",
        "pages_processed": 0,
        "total_pages": 0,
        "status": "planning",
    }
    _pipeline_progress[progress_key] = progress

    planner = SiloLinkPlanner()
    injector = LinkInjector()
    validator = LinkValidator()
    anchor_selector = AnchorTextSelector()

    try:
        # ------------------------------------------------------------------
        # Step 1: Build link graph
        # ------------------------------------------------------------------
        progress["current_step"] = 1
        progress["step_label"] = "Building link graph"

        if scope == "cluster":
            if cluster_id is None:
                raise ValueError("cluster_id is required for cluster scope")
            graph = await planner.build_cluster_graph(cluster_id, db)
        else:
            graph = await planner.build_onboarding_graph(project_id, db)

        pages = graph["pages"]
        progress["total_pages"] = len(pages)

        if not pages:
            progress["status"] = "complete"
            logger.info(
                "Link planning pipeline: no pages found",
                extra={"project_id": project_id, "scope": scope},
            )
            return {"status": "complete", "total_pages": 0, "total_links": 0}

        logger.info(
            "Step 1 complete: graph built",
            extra={
                "project_id": project_id,
                "scope": scope,
                "page_count": len(pages),
                "edge_count": len(graph["edges"]),
            },
        )

        # ------------------------------------------------------------------
        # Step 2: Select targets + anchor text for all pages
        # ------------------------------------------------------------------
        progress["current_step"] = 2
        progress["step_label"] = "Selecting targets and anchor text"

        # Load word counts to compute budgets
        page_ids = _extract_page_ids(pages, scope)
        word_counts = await _load_word_counts(db, page_ids)
        budgets = {pid: calculate_budget(wc) for pid, wc in word_counts.items()}

        # Select targets per scope
        if scope == "cluster":
            targets_map = select_targets_cluster(graph, budgets)
        else:
            targets_map = select_targets_onboarding(graph, budgets)

        # Gather anchor candidates and generate natural phrases
        # Build keyword map for LLM natural phrase generation
        keyword_map: dict[str, str] = {}
        for page in pages:
            pid = _page_id_for_scope(page, scope)
            kw = page.get("keyword", "")
            if kw:
                keyword_map[pid] = kw

        natural_phrases = await anchor_selector.generate_natural_phrases(keyword_map)

        # Select anchors for each page's targets
        usage_tracker: dict[str, dict[str, int]] = {}
        # page_link_plans: list of (source_page_id, target_info_with_anchor)
        page_link_plans: dict[str, list[dict[str, Any]]] = {}

        for page in pages:
            source_id = _page_id_for_scope(page, scope)
            page_targets = targets_map.get(page.get("page_id", source_id), [])
            planned_links: list[dict[str, Any]] = []

            # Load source page content for context_fit scoring
            source_content = await _load_page_content_text(db, source_id)

            for target in page_targets:
                target_id = _page_id_for_scope(target, scope)

                # Gather candidates from DB
                candidates = await anchor_selector.gather_candidates(target_id, db)

                # Append natural phrase candidates if available
                if target_id in natural_phrases:
                    candidates.extend(natural_phrases[target_id])

                anchor_result = anchor_selector.select_anchor(
                    candidates, source_content, target_id, usage_tracker
                )

                if anchor_result is None:
                    # Fallback: use the target keyword as exact_match
                    anchor_result = {
                        "anchor_text": target.get("keyword", "link"),
                        "anchor_type": "exact_match",
                        "score": 0.0,
                    }

                planned_links.append(
                    {
                        **target,
                        "anchor_text": anchor_result["anchor_text"],
                        "anchor_type": anchor_result["anchor_type"],
                        "target_page_id": target_id,
                    }
                )

            page_link_plans[source_id] = planned_links
            progress["pages_processed"] = len(page_link_plans)

        logger.info(
            "Step 2 complete: targets and anchors selected",
            extra={
                "project_id": project_id,
                "total_planned_links": sum(len(v) for v in page_link_plans.values()),
            },
        )

        # ------------------------------------------------------------------
        # Resolve slug-only URLs to full URLs using project site_url
        # (Cluster pages have slug-only normalized_url, e.g. "best-camping-coffee-maker")
        # ------------------------------------------------------------------
        project_obj = await db.get(Project, project_id)
        site_base = (project_obj.site_url or "").rstrip("/") if project_obj else ""

        for _source_id, link_list in page_link_plans.items():
            for lp in link_list:
                url = lp.get("url", "")
                if url and not url.startswith("http"):
                    lp["url"] = f"{site_base}/{url.lstrip('/')}"

        # ------------------------------------------------------------------
        # Step 3: Inject links into content
        # ------------------------------------------------------------------
        progress["current_step"] = 3
        progress["step_label"] = "Injecting links into content"
        progress["pages_processed"] = 0

        # Collect all injection results before persisting anything.
        # Each entry: (source_id, target_id, anchor_text, anchor_type,
        #              placement_method, position, is_mandatory, updated_html)
        injection_results: list[dict[str, Any]] = []
        # Track updated HTML per source page for validation + DB write
        pages_html: dict[str, str] = {}

        pages_processed = 0
        for source_id, planned_links in page_link_plans.items():
            try:
                html = await _load_bottom_description(db, source_id)
                if not html:
                    logger.warning(
                        "No bottom_description for page, skipping injection",
                        extra={"page_id": source_id},
                    )
                    pages_processed += 1
                    progress["pages_processed"] = pages_processed
                    continue

                current_html = html
                for link_plan in planned_links:
                    anchor_text = link_plan["anchor_text"]
                    target_url = link_plan.get("url", "")
                    target_id = link_plan["target_page_id"]
                    is_mandatory = link_plan.get("is_mandatory", False)

                    # Try rule-based first
                    modified_html, p_idx = injector.inject_rule_based(
                        current_html, anchor_text, target_url
                    )

                    if p_idx is not None:
                        current_html = modified_html
                        injection_results.append(
                            {
                                "source_page_id": source_id,
                                "target_page_id": target_id,
                                "anchor_text": anchor_text,
                                "anchor_type": link_plan["anchor_type"],
                                "placement_method": "rule_based",
                                "position_in_content": p_idx,
                                "is_mandatory": is_mandatory,
                            }
                        )
                    else:
                        # LLM fallback
                        target_keyword = link_plan.get("keyword", "")
                        modified_html, p_idx = await injector.inject_llm_fallback(
                            current_html,
                            anchor_text,
                            target_url,
                            target_keyword,
                            mandatory_parent=is_mandatory,
                        )
                        if p_idx is not None:
                            current_html = modified_html
                            injection_results.append(
                                {
                                    "source_page_id": source_id,
                                    "target_page_id": target_id,
                                    "anchor_text": anchor_text,
                                    "anchor_type": link_plan["anchor_type"],
                                    "placement_method": "llm_fallback",
                                    "position_in_content": p_idx,
                                    "is_mandatory": is_mandatory,
                                }
                            )
                        else:
                            logger.warning(
                                "Link injection failed (both rule-based and LLM)",
                                extra={
                                    "source_page_id": source_id,
                                    "target_page_id": target_id,
                                    "anchor_text": anchor_text,
                                },
                            )

                pages_html[source_id] = current_html

            except Exception:
                logger.error(
                    "Injection failed for page, skipping",
                    extra={"page_id": source_id},
                    exc_info=True,
                )

            pages_processed += 1
            progress["pages_processed"] = pages_processed

        logger.info(
            "Step 3 complete: links injected",
            extra={
                "project_id": project_id,
                "injected_count": len(injection_results),
                "pages_with_html": len(pages_html),
            },
        )

        # ------------------------------------------------------------------
        # Step 4: Validate all rules
        # ------------------------------------------------------------------
        progress["current_step"] = 4
        progress["step_label"] = "Validating link rules"
        progress["pages_processed"] = 0

        # Build cluster_data for cluster scope validation
        cluster_data: dict[str, Any] | None = None
        if scope == "cluster":
            parent_url = ""
            for p in pages:
                if p.get("role") == "parent" and p.get("url"):
                    parent_url = p["url"]
                    break
            cluster_data = {"pages": pages, "parent_url": parent_url}

        # Create temporary InternalLink-like objects for validation
        # (validator expects objects with .source_page_id, .target_page_id, etc.)
        temp_links = [_LinkProxy({**r, "scope": scope}) for r in injection_results]

        validation = validator.validate_links(
            temp_links, pages_html, scope, cluster_data
        )

        logger.info(
            "Step 4 complete: validation done",
            extra={
                "project_id": project_id,
                "passed": validation["passed"],
            },
        )

        # ------------------------------------------------------------------
        # Persist: Create InternalLink rows + update PageContent
        # ------------------------------------------------------------------
        async with db_manager.session_factory() as write_db:
            # Create InternalLink rows
            created_links: list[InternalLink] = []
            for result_dict in injection_results:
                # Determine status based on validation
                source_id = result_dict["source_page_id"]
                # Find validation status for this link's source page
                link_status = "injected"
                if validation["passed"]:
                    link_status = "verified"
                else:
                    # Check if this specific page had failures
                    for page_result in validation.get("results", []):
                        if page_result["page_id"] == source_id:
                            failing = [
                                r["rule"]
                                for r in page_result["rules"]
                                if not r["passed"]
                            ]
                            if failing:
                                link_status = f"failed:{','.join(failing)}"
                            else:
                                link_status = "verified"
                            break

                link = InternalLink(
                    source_page_id=result_dict["source_page_id"],
                    target_page_id=result_dict["target_page_id"],
                    project_id=project_id,
                    cluster_id=cluster_id,
                    scope=scope,
                    anchor_text=result_dict["anchor_text"],
                    anchor_type=result_dict["anchor_type"],
                    placement_method=result_dict["placement_method"],
                    position_in_content=result_dict["position_in_content"],
                    is_mandatory=result_dict["is_mandatory"],
                    status=link_status,
                )
                write_db.add(link)
                created_links.append(link)

            # Update PageContent.bottom_description with injected HTML
            for page_id, updated_html in pages_html.items():
                stmt = select(PageContent).where(PageContent.crawled_page_id == page_id)
                pc_result = await write_db.execute(stmt)
                pc = pc_result.scalar_one_or_none()
                if pc is not None:
                    pc.bottom_description = updated_html

            await write_db.commit()

            logger.info(
                "Pipeline persist complete",
                extra={
                    "project_id": project_id,
                    "links_created": len(created_links),
                    "pages_updated": len(pages_html),
                },
            )

        progress["status"] = "complete"
        progress["pages_processed"] = len(pages)
        progress["total_links"] = len(injection_results)

        return {
            "status": "complete",
            "total_pages": len(pages),
            "total_links": len(injection_results),
            "validation_passed": validation["passed"],
            "validation_results": validation["results"],
        }

    except Exception as exc:
        progress["status"] = "failed"
        progress["step_label"] = f"Failed: {exc}"
        logger.error(
            "Link planning pipeline failed",
            extra={"project_id": project_id, "scope": scope, "error": str(exc)},
            exc_info=True,
        )
        raise


# ---------------------------------------------------------------------------
# Re-plan flow: snapshot → strip → delete → re-run
# ---------------------------------------------------------------------------


async def replan_links(
    project_id: str,
    scope: Literal["onboarding", "cluster"],
    cluster_id: str | None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Re-plan links by snapshotting current state, cleaning up, then re-running.

    Steps:
    1. Create a LinkPlanSnapshot with all current InternalLink rows and
       pre-strip bottom_description for each page in scope.
    2. Strip all internal links from bottom_description for each page in scope.
    3. Delete all InternalLink rows for the scope.
    4. Run the full pipeline from scratch.

    The snapshot is created BEFORE stripping/deleting — it's the rollback point.

    Args:
        project_id: UUID of the project.
        scope: 'onboarding' or 'cluster'.
        cluster_id: Required when scope='cluster', None for onboarding.
        db: Async database session (read-only; writes use db_manager sessions).

    Returns:
        Dict with pipeline result summary from run_link_planning_pipeline.
    """
    logger.info(
        "Starting re-plan flow",
        extra={"project_id": project_id, "scope": scope, "cluster_id": cluster_id},
    )

    # ------------------------------------------------------------------
    # Step 1: Snapshot current plan data
    # ------------------------------------------------------------------

    # Load existing InternalLink rows for this scope
    link_stmt = select(InternalLink).where(
        InternalLink.project_id == project_id,
        InternalLink.scope == scope,
    )
    if scope == "cluster" and cluster_id:
        link_stmt = link_stmt.where(InternalLink.cluster_id == cluster_id)

    link_result = await db.execute(link_stmt)
    existing_links = link_result.scalars().all()

    if not existing_links:
        # No existing links — just run the pipeline directly
        logger.info(
            "No existing links found, running pipeline directly",
            extra={"project_id": project_id, "scope": scope},
        )
        return await run_link_planning_pipeline(project_id, scope, cluster_id, db)

    # Collect unique source page IDs to snapshot their content
    source_page_ids = list({lnk.source_page_id for lnk in existing_links})

    # Load pre-strip bottom_description for each page
    pc_stmt = select(PageContent).where(
        PageContent.crawled_page_id.in_(source_page_ids)
    )
    pc_result = await db.execute(pc_stmt)
    page_contents = {pc.crawled_page_id: pc for pc in pc_result.scalars().all()}

    # Build snapshot plan_data
    pages_snapshot: list[dict[str, Any]] = []
    for page_id in source_page_ids:
        pc = page_contents.get(page_id)
        page_links = [
            {
                "target_id": lnk.target_page_id,
                "anchor_text": lnk.anchor_text,
                "anchor_type": lnk.anchor_type,
                "placement_method": lnk.placement_method,
                "is_mandatory": lnk.is_mandatory,
                "status": lnk.status,
            }
            for lnk in existing_links
            if lnk.source_page_id == page_id
        ]
        pages_snapshot.append(
            {
                "page_id": page_id,
                "pre_injection_content": pc.bottom_description if pc else None,
                "links": page_links,
            }
        )

    plan_data: dict[str, Any] = {
        "pages": pages_snapshot,
        "metadata": {
            "scope": scope,
            "cluster_id": cluster_id,
            "total_pages": len(source_page_ids),
        },
    }

    # Persist snapshot
    async with db_manager.session_factory() as write_db:
        snapshot = LinkPlanSnapshot(
            project_id=project_id,
            cluster_id=cluster_id,
            scope=scope,
            plan_data=plan_data,
            total_links=len(existing_links),
        )
        write_db.add(snapshot)
        await write_db.commit()

    logger.info(
        "Snapshot created",
        extra={
            "project_id": project_id,
            "snapshot_links": len(existing_links),
            "snapshot_pages": len(source_page_ids),
        },
    )

    # ------------------------------------------------------------------
    # Step 2: Strip internal links from bottom_description
    # ------------------------------------------------------------------

    # Get site_domain for accurate internal link detection
    proj_stmt = select(Project).where(Project.id == project_id)
    proj_result = await db.execute(proj_stmt)
    project = proj_result.scalar_one_or_none()
    site_domain: str | None = None
    if project and project.site_url:
        from urllib.parse import urlparse

        parsed = urlparse(project.site_url)
        site_domain = parsed.netloc or parsed.path

    async with db_manager.session_factory() as write_db:
        for page_id in source_page_ids:
            pc_load_stmt = select(PageContent).where(
                PageContent.crawled_page_id == page_id
            )
            pc_load_result = await write_db.execute(pc_load_stmt)
            pc = pc_load_result.scalar_one_or_none()
            if pc and pc.bottom_description:
                pc.bottom_description = strip_internal_links(
                    pc.bottom_description, site_domain
                )
        await write_db.commit()

    logger.info(
        "Stripped internal links from pages",
        extra={"project_id": project_id, "pages_stripped": len(source_page_ids)},
    )

    # ------------------------------------------------------------------
    # Step 3: Delete all InternalLink rows for the scope
    # ------------------------------------------------------------------
    async with db_manager.session_factory() as write_db:
        del_stmt = delete(InternalLink).where(
            InternalLink.project_id == project_id,
            InternalLink.scope == scope,
        )
        if scope == "cluster" and cluster_id:
            del_stmt = del_stmt.where(InternalLink.cluster_id == cluster_id)

        del_result = await write_db.execute(del_stmt)
        deleted_count: int = del_result.rowcount  # type: ignore[attr-defined,union-attr,unused-ignore]
        await write_db.commit()

    logger.info(
        "Deleted existing InternalLink rows",
        extra={"project_id": project_id, "deleted_count": deleted_count},
    )

    # ------------------------------------------------------------------
    # Step 4: Run full pipeline from scratch
    # ------------------------------------------------------------------
    return await run_link_planning_pipeline(project_id, scope, cluster_id, db)


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------


class _LinkProxy:
    """Lightweight proxy that mimics InternalLink attributes for validation."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.id = data.get("id", "temp")
        self.source_page_id: str = data["source_page_id"]
        self.target_page_id: str = data["target_page_id"]
        self.anchor_text: str = data["anchor_text"]
        self.anchor_type: str = data["anchor_type"]
        self.scope: str = data.get("scope", "")
        self.status: str = "injected"


def _extract_page_ids(pages: list[dict[str, Any]], scope: str) -> list[str]:
    """Extract the correct page ID field based on scope.

    For cluster scope, pages have both ``page_id`` (ClusterPage.id) and
    ``crawled_page_id`` (CrawledPage.id). We need the crawled_page_id for
    DB lookups on PageContent / PageKeywords.
    """
    ids: list[str] = []
    for p in pages:
        pid = p.get("crawled_page_id") or p.get("page_id", "")
        if pid:
            ids.append(pid)
    return ids


def _page_id_for_scope(page: dict[str, Any], scope: str) -> str:
    """Get the canonical page ID (crawled_page_id) from a graph page dict."""
    crawled: str = page.get("crawled_page_id") or page.get("page_id", "")
    return crawled


async def _load_word_counts(
    db: AsyncSession,
    page_ids: list[str],
) -> dict[str, int]:
    """Load word counts from PageContent for a list of page IDs."""
    if not page_ids:
        return {}

    stmt = select(PageContent).where(PageContent.crawled_page_id.in_(page_ids))
    result = await db.execute(stmt)
    word_counts: dict[str, int] = {}
    for pc in result.scalars().all():
        word_counts[pc.crawled_page_id] = pc.word_count or 0
    return word_counts


async def _load_page_content_text(db: AsyncSession, page_id: str) -> str:
    """Load the bottom_description text for a page (used for anchor context_fit)."""
    stmt = select(PageContent).where(PageContent.crawled_page_id == page_id)
    result = await db.execute(stmt)
    pc = result.scalar_one_or_none()
    if pc and pc.bottom_description:
        return pc.bottom_description
    return ""


async def _load_bottom_description(db: AsyncSession, page_id: str) -> str:
    """Load bottom_description HTML for a page."""
    stmt = select(PageContent).where(PageContent.crawled_page_id == page_id)
    result = await db.execute(stmt)
    pc = result.scalar_one_or_none()
    if pc and pc.bottom_description:
        return pc.bottom_description
    return ""


# ---------------------------------------------------------------------------
# Blog link planning pipeline
# ---------------------------------------------------------------------------

# Module-level dict for blog link planning progress, keyed by blog_post_id.
_blog_link_progress: dict[str, dict[str, Any]] = {}


def get_blog_link_progress(blog_post_id: str) -> dict[str, Any] | None:
    """Return the current blog link planning progress for a post, or None."""
    return _blog_link_progress.get(blog_post_id)


async def run_blog_link_planning(
    blog_post_id: str,
    campaign_id: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Run link planning for a single blog post.

    Steps:
    1. Build blog graph (creates CrawledPage bridging records)
    2. Select targets (UP to cluster + SIDEWAYS to siblings)
    3. Generate anchor text and inject links into blog content
    4. Validate and persist InternalLink rows
    5. Update BlogPost.content with injected HTML

    Args:
        blog_post_id: UUID of the BlogPost to plan links for.
        campaign_id: UUID of the BlogCampaign.
        db: Async database session.

    Returns:
        Dict with pipeline result summary.
    """
    progress: dict[str, Any] = {
        "status": "planning",
        "step": "building_graph",
        "links_planned": 0,
    }
    _blog_link_progress[blog_post_id] = progress

    planner = SiloLinkPlanner()
    injector = LinkInjector()
    validator = LinkValidator()
    anchor_selector = AnchorTextSelector()

    try:
        # Step 1: Build blog graph
        graph = await planner.build_blog_graph(campaign_id, db)

        if not graph["blog_posts"]:
            progress["status"] = "complete"
            return {"status": "complete", "links_planned": 0}

        # Find our blog post's crawled_page_id
        source_crawled_id: str | None = None
        for bp in graph["blog_posts"]:
            if bp["post_id"] == blog_post_id:
                source_crawled_id = bp["crawled_page_id"]
                break

        if source_crawled_id is None:
            progress["status"] = "failed"
            progress["error"] = (
                "Blog post not found in graph (not approved or no content?)"
            )
            return {"status": "failed", "error": progress["error"]}

        # Step 2: Select targets
        progress["step"] = "selecting_targets"
        targets_map = select_targets_blog(graph)
        my_targets = targets_map.get(source_crawled_id, [])

        if not my_targets:
            progress["status"] = "complete"
            return {"status": "complete", "links_planned": 0}

        # Get project info for URL resolution
        campaign_stmt = select(BlogCampaign).where(BlogCampaign.id == campaign_id)
        campaign_result = await db.execute(campaign_stmt)
        campaign = campaign_result.scalar_one()
        project_obj = await db.get(Project, campaign.project_id)
        site_base = (project_obj.site_url or "").rstrip("/") if project_obj else ""

        # Step 3: Generate anchor text and inject
        progress["step"] = "injecting_links"

        # Load the blog post content for injection
        post_stmt = select(BlogPost).where(BlogPost.id == blog_post_id)
        post_result = await db.execute(post_stmt)
        blog_post = post_result.scalar_one()

        current_html = blog_post.content or ""
        if not current_html:
            progress["status"] = "failed"
            progress["error"] = "Blog post has no content"
            return {"status": "failed", "error": progress["error"]}

        # Generate anchor text candidates
        keyword_map: dict[str, str] = {}
        for target in my_targets:
            tid = target["crawled_page_id"]
            kw = target.get("keyword", "")
            if kw:
                keyword_map[tid] = kw

        natural_phrases = await anchor_selector.generate_natural_phrases(keyword_map)

        usage_tracker: dict[str, dict[str, int]] = {}
        injection_results: list[dict[str, Any]] = []

        for target in my_targets:
            target_id = target["crawled_page_id"]
            target_keyword = target.get("keyword", "")
            is_mandatory = target.get("is_mandatory", False)

            # Resolve URL
            target_url = target.get("url") or target.get("url_slug", "")
            if target_url and not target_url.startswith("http"):
                target_url = f"{site_base}/{target_url.lstrip('/')}"

            # Gather anchor candidates from DB (if target has PageKeywords/ContentBrief)
            candidates = await anchor_selector.gather_candidates(target_id, db)

            # Append natural phrases
            if target_id in natural_phrases:
                candidates.extend(natural_phrases[target_id])

            # If no candidates from DB, use the keyword directly
            if not candidates:
                candidates = [
                    {"anchor_text": target_keyword, "anchor_type": "exact_match"}
                ]

            anchor_result = anchor_selector.select_anchor(
                candidates, current_html, target_id, usage_tracker
            )
            if anchor_result is None:
                anchor_result = {
                    "anchor_text": target_keyword or "link",
                    "anchor_type": "exact_match",
                    "score": 0.0,
                }

            anchor_text = anchor_result["anchor_text"]

            # Try rule-based injection
            modified_html, p_idx = injector.inject_rule_based(
                current_html, anchor_text, target_url
            )

            if p_idx is not None:
                current_html = modified_html
                injection_results.append(
                    {
                        "source_page_id": source_crawled_id,
                        "target_page_id": target_id,
                        "anchor_text": anchor_text,
                        "anchor_type": anchor_result["anchor_type"],
                        "placement_method": "rule_based",
                        "position_in_content": p_idx,
                        "is_mandatory": is_mandatory,
                    }
                )
            else:
                # LLM fallback
                modified_html, p_idx = await injector.inject_llm_fallback(
                    current_html,
                    anchor_text,
                    target_url,
                    target_keyword,
                    mandatory_parent=is_mandatory,
                )
                if p_idx is not None:
                    current_html = modified_html
                    injection_results.append(
                        {
                            "source_page_id": source_crawled_id,
                            "target_page_id": target_id,
                            "anchor_text": anchor_text,
                            "anchor_type": anchor_result["anchor_type"],
                            "placement_method": "llm_fallback",
                            "position_in_content": p_idx,
                            "is_mandatory": is_mandatory,
                        }
                    )
                else:
                    logger.warning(
                        "Blog link injection failed for target",
                        extra={
                            "blog_post_id": blog_post_id,
                            "target_id": target_id,
                            "anchor_text": anchor_text,
                        },
                    )

        # Step 4: Validate
        progress["step"] = "validating"

        # Build cluster_data for silo validation
        all_page_ids = {bp["crawled_page_id"] for bp in graph["blog_posts"]}
        all_page_ids |= {cp["crawled_page_id"] for cp in graph["cluster_pages"]}

        blog_cluster_data: dict[str, Any] = {
            "pages": [
                *[
                    {
                        "crawled_page_id": cp["crawled_page_id"],
                        "role": cp["role"],
                        "url": cp.get("url"),
                    }
                    for cp in graph["cluster_pages"]
                ],
                *[
                    {
                        "crawled_page_id": bp["crawled_page_id"],
                        "role": "blog",
                        "url": bp.get("url_slug"),
                    }
                    for bp in graph["blog_posts"]
                ],
            ],
        }

        temp_links = [_LinkProxy({**r, "scope": "blog"}) for r in injection_results]
        pages_html = {source_crawled_id: current_html}

        validation = validator.validate_links(
            temp_links, pages_html, "blog", blog_cluster_data
        )

        # Step 5: Persist InternalLink rows and update BlogPost.content
        progress["step"] = "persisting"

        async with db_manager.session_factory() as write_db:
            for result_dict in injection_results:
                link_status = "verified" if validation["passed"] else "injected"
                link = InternalLink(
                    source_page_id=result_dict["source_page_id"],
                    target_page_id=result_dict["target_page_id"],
                    project_id=campaign.project_id,
                    cluster_id=campaign.cluster_id,
                    scope="blog",
                    anchor_text=result_dict["anchor_text"],
                    anchor_type=result_dict["anchor_type"],
                    placement_method=result_dict["placement_method"],
                    position_in_content=result_dict["position_in_content"],
                    is_mandatory=result_dict["is_mandatory"],
                    status=link_status,
                )
                write_db.add(link)

            # Update BlogPost.content with injected HTML
            post_update_stmt = select(BlogPost).where(BlogPost.id == blog_post_id)
            post_update_result = await write_db.execute(post_update_stmt)
            post_to_update = post_update_result.scalar_one()
            post_to_update.content = current_html

            await write_db.commit()

        progress["status"] = "complete"
        progress["links_planned"] = len(injection_results)

        logger.info(
            "Blog link planning complete",
            extra={
                "blog_post_id": blog_post_id,
                "links_injected": len(injection_results),
                "validation_passed": validation["passed"],
            },
        )

        return {
            "status": "complete",
            "links_planned": len(injection_results),
            "validation_passed": validation["passed"],
        }

    except Exception as exc:
        progress["status"] = "failed"
        progress["error"] = str(exc)
        logger.error(
            "Blog link planning failed",
            extra={"blog_post_id": blog_post_id, "error": str(exc)},
            exc_info=True,
        )
        raise
    finally:
        # Clean up progress after a delay (let polling catch final state)
        # In production this would be cleaned by a TTL; here we leave it
        pass
