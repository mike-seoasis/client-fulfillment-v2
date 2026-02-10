"""Link planning service for building link graphs and selecting targets.

SiloLinkPlanner constructs two types of graphs:
- Cluster graph: parent/child + sibling adjacency from ClusterPage records
- Onboarding graph: pairwise label-overlap edges from onboarding CrawledPages

Target selection uses budgets (based on word count) to determine how many
outbound links each page gets, then selects the best targets per scope rules.
"""

from itertools import combinations
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging import get_logger
from app.models.crawled_page import CrawledPage
from app.models.keyword_cluster import ClusterPage
from app.models.page_content import PageContent
from app.models.page_keywords import PageKeywords

logger = get_logger(__name__)

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
