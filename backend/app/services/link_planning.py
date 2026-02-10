"""Link planning service for building link graphs.

SiloLinkPlanner constructs two types of graphs:
- Cluster graph: parent/child + sibling adjacency from ClusterPage records
- Onboarding graph: pairwise label-overlap edges from onboarding CrawledPages
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
                    "url": cp.crawled_page.normalized_url
                    if cp.crawled_page
                    else None,
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
                "url": cp.crawled_page.normalized_url
                if cp.crawled_page
                else None,
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
