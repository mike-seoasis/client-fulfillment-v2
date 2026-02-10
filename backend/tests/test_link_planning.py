"""Tests for SiloLinkPlanner graph construction: build_cluster_graph and build_onboarding_graph.

Tests cover:
- Cluster graph: parent + children produce parent_child + sibling edges
- Cluster graph: single page returns no edges
- Onboarding graph: overlapping labels produce edges with correct weights
- Onboarding graph: pages below threshold (1 shared label) have no edges
- Onboarding graph: pages with no labels have no edges
- Both modes: only pages with complete content and approved keywords included
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawled_page import CrawledPage
from app.models.keyword_cluster import ClusterPage, KeywordCluster
from app.models.page_content import PageContent
from app.models.page_keywords import PageKeywords
from app.models.project import Project
from app.services.link_planning import SiloLinkPlanner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(db: AsyncSession) -> Project:
    """Create and add a test project."""
    project = Project(
        id=str(uuid4()),
        name="Test Project",
        site_url="https://example.com",
    )
    db.add(project)
    return project


def _make_cluster(db: AsyncSession, project_id: str) -> KeywordCluster:
    """Create and add a test cluster."""
    cluster = KeywordCluster(
        id=str(uuid4()),
        project_id=project_id,
        seed_keyword="hiking boots",
        name="Hiking Boots",
        status="suggestions_ready",
    )
    db.add(cluster)
    return cluster


def _make_crawled_page(
    db: AsyncSession,
    project_id: str,
    *,
    source: str = "onboarding",
    url: str | None = None,
    labels: list[str] | None = None,
) -> CrawledPage:
    """Create and add a test crawled page."""
    page = CrawledPage(
        id=str(uuid4()),
        project_id=project_id,
        normalized_url=url or f"https://example.com/{uuid4().hex[:8]}",
        source=source,
        status="completed",
        labels=labels,
    )
    db.add(page)
    return page


def _make_cluster_page(
    db: AsyncSession,
    cluster_id: str,
    crawled_page: CrawledPage,
    *,
    role: str = "child",
    keyword: str = "test keyword",
    composite_score: float = 50.0,
) -> ClusterPage:
    """Create and add a test cluster page linked to a crawled page."""
    cp = ClusterPage(
        id=str(uuid4()),
        cluster_id=cluster_id,
        crawled_page_id=crawled_page.id,
        keyword=keyword,
        role=role,
        url_slug=keyword.replace(" ", "-"),
        composite_score=composite_score,
        is_approved=True,
    )
    db.add(cp)
    return cp


def _make_page_content(
    db: AsyncSession,
    crawled_page_id: str,
    *,
    status: str = "complete",
) -> PageContent:
    """Create and add page content for a crawled page."""
    pc = PageContent(
        id=str(uuid4()),
        crawled_page_id=crawled_page_id,
        status=status,
    )
    db.add(pc)
    return pc


def _make_page_keywords(
    db: AsyncSession,
    crawled_page_id: str,
    *,
    primary_keyword: str = "test keyword",
    is_approved: bool = True,
    is_priority: bool = False,
) -> PageKeywords:
    """Create and add page keywords for a crawled page."""
    pk = PageKeywords(
        id=str(uuid4()),
        crawled_page_id=crawled_page_id,
        primary_keyword=primary_keyword,
        is_approved=is_approved,
        is_priority=is_priority,
    )
    db.add(pk)
    return pk


# ---------------------------------------------------------------------------
# Tests: build_cluster_graph
# ---------------------------------------------------------------------------


class TestBuildClusterGraph:
    """Tests for SiloLinkPlanner.build_cluster_graph."""

    @pytest.mark.asyncio
    async def test_parent_with_5_children_produces_correct_edges(
        self, db_session: AsyncSession
    ):
        """Cluster with parent + 5 children produces parent_child + sibling edges."""
        project = _make_project(db_session)
        cluster = _make_cluster(db_session, project.id)

        # Create parent crawled page + cluster page
        parent_cp = _make_crawled_page(
            db_session, project.id, source="cluster", url="https://example.com/parent"
        )
        _make_cluster_page(
            db_session,
            cluster.id,
            parent_cp,
            role="parent",
            keyword="hiking boots",
            composite_score=90.0,
        )

        # Create 5 child crawled pages + cluster pages
        for i in range(5):
            child_cp = _make_crawled_page(
                db_session,
                project.id,
                source="cluster",
                url=f"https://example.com/child-{i}",
            )
            _make_cluster_page(
                db_session,
                cluster.id,
                child_cp,
                role="child",
                keyword=f"child keyword {i}",
                composite_score=80.0 - i * 5,
            )

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_cluster_graph(cluster.id, db_session)

        # 6 pages total (1 parent + 5 children)
        assert len(graph["pages"]) == 6

        # Verify page fields
        for page in graph["pages"]:
            assert "page_id" in page
            assert "crawled_page_id" in page
            assert "keyword" in page
            assert "role" in page
            assert "composite_score" in page
            assert "url" in page

        # Count edge types
        parent_child_edges = [e for e in graph["edges"] if e["type"] == "parent_child"]
        sibling_edges = [e for e in graph["edges"] if e["type"] == "sibling"]

        # parent_child: 1 parent × 5 children = 5 edges
        assert len(parent_child_edges) == 5

        # sibling: C(5,2) = 10 edges
        assert len(sibling_edges) == 10

        # Total edges = 15
        assert len(graph["edges"]) == 15

    @pytest.mark.asyncio
    async def test_cluster_with_only_1_page_returns_no_edges(
        self, db_session: AsyncSession
    ):
        """Cluster with only 1 page returns graph with no edges."""
        project = _make_project(db_session)
        cluster = _make_cluster(db_session, project.id)

        single_cp = _make_crawled_page(
            db_session, project.id, source="cluster", url="https://example.com/single"
        )
        _make_cluster_page(
            db_session,
            cluster.id,
            single_cp,
            role="parent",
            keyword="solo keyword",
        )

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_cluster_graph(cluster.id, db_session)

        assert len(graph["pages"]) == 1
        assert graph["edges"] == []

    @pytest.mark.asyncio
    async def test_empty_cluster_returns_empty_graph(
        self, db_session: AsyncSession
    ):
        """Cluster with 0 pages returns empty pages and edges."""
        project = _make_project(db_session)
        cluster = _make_cluster(db_session, project.id)
        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_cluster_graph(cluster.id, db_session)

        assert graph["pages"] == []
        assert graph["edges"] == []

    @pytest.mark.asyncio
    async def test_edge_source_and_target_are_cluster_page_ids(
        self, db_session: AsyncSession
    ):
        """Edge source and target use ClusterPage.id (not CrawledPage.id)."""
        project = _make_project(db_session)
        cluster = _make_cluster(db_session, project.id)

        parent_cp = _make_crawled_page(
            db_session, project.id, source="cluster", url="https://example.com/p"
        )
        parent = _make_cluster_page(
            db_session, cluster.id, parent_cp, role="parent", keyword="parent kw"
        )

        child_cp = _make_crawled_page(
            db_session, project.id, source="cluster", url="https://example.com/c"
        )
        child = _make_cluster_page(
            db_session, cluster.id, child_cp, role="child", keyword="child kw"
        )

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_cluster_graph(cluster.id, db_session)

        # Get ClusterPage IDs from the page list
        page_ids = {p["page_id"] for p in graph["pages"]}
        assert parent.id in page_ids
        assert child.id in page_ids

        # Edge source/target should be ClusterPage IDs
        edge = graph["edges"][0]
        assert edge["source"] in page_ids
        assert edge["target"] in page_ids


# ---------------------------------------------------------------------------
# Tests: build_onboarding_graph
# ---------------------------------------------------------------------------


class TestBuildOnboardingGraph:
    """Tests for SiloLinkPlanner.build_onboarding_graph."""

    @pytest.mark.asyncio
    async def test_overlapping_labels_produce_edges_with_correct_weights(
        self, db_session: AsyncSession
    ):
        """Pages with overlapping labels produce edges with correct weights."""
        project = _make_project(db_session)

        # Page A: labels ["seo", "content", "marketing"]
        page_a = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/page-a",
            labels=["seo", "content", "marketing"],
        )
        _make_page_content(db_session, page_a.id, status="complete")
        _make_page_keywords(db_session, page_a.id, primary_keyword="seo tips")

        # Page B: labels ["seo", "content", "analytics"]
        page_b = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/page-b",
            labels=["seo", "content", "analytics"],
        )
        _make_page_content(db_session, page_b.id, status="complete")
        _make_page_keywords(db_session, page_b.id, primary_keyword="content strategy")

        # Page C: labels ["seo", "content", "marketing", "analytics"]
        page_c = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/page-c",
            labels=["seo", "content", "marketing", "analytics"],
        )
        _make_page_content(db_session, page_c.id, status="complete")
        _make_page_keywords(db_session, page_c.id, primary_keyword="seo analytics")

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_onboarding_graph(project.id, db_session)

        assert len(graph["pages"]) == 3

        # All pairs have >= 2 shared labels → 3 edges (A-B, A-C, B-C)
        assert len(graph["edges"]) == 3

        # Build edge lookup for weight verification
        edge_map: dict[tuple[str, ...], int] = {}
        for edge in graph["edges"]:
            key = tuple(sorted([edge["source"], edge["target"]]))
            edge_map[key] = edge["weight"]

        # A & B share {"seo", "content"} = 2
        ab_key = tuple(sorted([page_a.id, page_b.id]))
        assert edge_map[ab_key] == 2
        # A & C share {"seo", "content", "marketing"} = 3
        ac_key = tuple(sorted([page_a.id, page_c.id]))
        assert edge_map[ac_key] == 3
        # B & C share {"seo", "content", "analytics"} = 3
        bc_key = tuple(sorted([page_b.id, page_c.id]))
        assert edge_map[bc_key] == 3
    @pytest.mark.asyncio
    async def test_pages_below_threshold_have_no_edge(
        self, db_session: AsyncSession
    ):
        """Pages with only 1 shared label (below threshold of 2) have no edge."""
        project = _make_project(db_session)

        # Page A: labels ["seo", "marketing"]
        page_a = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/below-a",
            labels=["seo", "marketing"],
        )
        _make_page_content(db_session, page_a.id, status="complete")
        _make_page_keywords(db_session, page_a.id, primary_keyword="kw a")

        # Page B: labels ["seo", "analytics"] — only "seo" overlaps (1 < 2)
        page_b = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/below-b",
            labels=["seo", "analytics"],
        )
        _make_page_content(db_session, page_b.id, status="complete")
        _make_page_keywords(db_session, page_b.id, primary_keyword="kw b")

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_onboarding_graph(project.id, db_session)

        assert len(graph["pages"]) == 2
        assert graph["edges"] == []

    @pytest.mark.asyncio
    async def test_pages_with_no_labels_have_no_edges(
        self, db_session: AsyncSession
    ):
        """Pages with no labels produce no edges."""
        project = _make_project(db_session)

        # Page A: no labels
        page_a = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/nolabel-a",
            labels=None,
        )
        _make_page_content(db_session, page_a.id, status="complete")
        _make_page_keywords(db_session, page_a.id, primary_keyword="kw a")

        # Page B: empty labels
        page_b = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/nolabel-b",
            labels=[],
        )
        _make_page_content(db_session, page_b.id, status="complete")
        _make_page_keywords(db_session, page_b.id, primary_keyword="kw b")

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_onboarding_graph(project.id, db_session)

        assert len(graph["pages"]) == 2
        assert graph["edges"] == []

    @pytest.mark.asyncio
    async def test_page_fields_include_labels_and_priority(
        self, db_session: AsyncSession
    ):
        """Onboarding graph pages include labels and is_priority fields."""
        project = _make_project(db_session)

        page = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/fields-test",
            labels=["seo", "content"],
        )
        _make_page_content(db_session, page.id, status="complete")
        _make_page_keywords(
            db_session, page.id, primary_keyword="seo tips", is_priority=True
        )

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_onboarding_graph(project.id, db_session)

        assert len(graph["pages"]) == 1
        p = graph["pages"][0]
        assert p["page_id"] == page.id
        assert p["keyword"] == "seo tips"
        assert p["labels"] == ["seo", "content"]
        assert p["is_priority"] is True
        assert p["url"] == "https://example.com/fields-test"


# ---------------------------------------------------------------------------
# Tests: content and keyword filtering (both modes)
# ---------------------------------------------------------------------------


class TestGraphFiltering:
    """Tests verifying only pages with complete content and approved keywords are included."""

    @pytest.mark.asyncio
    async def test_onboarding_excludes_incomplete_content(
        self, db_session: AsyncSession
    ):
        """Onboarding graph excludes pages where PageContent.status != 'complete'."""
        project = _make_project(db_session)

        # Page with complete content → included
        good_page = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/good",
            labels=["seo", "content"],
        )
        _make_page_content(db_session, good_page.id, status="complete")
        _make_page_keywords(db_session, good_page.id, primary_keyword="good kw")

        # Page with pending content → excluded
        pending_page = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/pending",
            labels=["seo", "content"],
        )
        _make_page_content(db_session, pending_page.id, status="pending")
        _make_page_keywords(db_session, pending_page.id, primary_keyword="pending kw")

        # Page with failed content → excluded
        failed_page = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/failed",
            labels=["seo", "content"],
        )
        _make_page_content(db_session, failed_page.id, status="failed")
        _make_page_keywords(db_session, failed_page.id, primary_keyword="failed kw")

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_onboarding_graph(project.id, db_session)

        page_ids = {p["page_id"] for p in graph["pages"]}
        assert good_page.id in page_ids
        assert pending_page.id not in page_ids
        assert failed_page.id not in page_ids

    @pytest.mark.asyncio
    async def test_onboarding_excludes_unapproved_keywords(
        self, db_session: AsyncSession
    ):
        """Onboarding graph excludes pages where PageKeywords.is_approved is False."""
        project = _make_project(db_session)

        # Page with approved keywords → included
        approved_page = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/approved",
            labels=["seo"],
        )
        _make_page_content(db_session, approved_page.id, status="complete")
        _make_page_keywords(
            db_session, approved_page.id, primary_keyword="approved kw", is_approved=True
        )

        # Page with unapproved keywords → excluded
        unapproved_page = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/unapproved",
            labels=["seo"],
        )
        _make_page_content(db_session, unapproved_page.id, status="complete")
        _make_page_keywords(
            db_session,
            unapproved_page.id,
            primary_keyword="unapproved kw",
            is_approved=False,
        )

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_onboarding_graph(project.id, db_session)

        page_ids = {p["page_id"] for p in graph["pages"]}
        assert approved_page.id in page_ids
        assert unapproved_page.id not in page_ids

    @pytest.mark.asyncio
    async def test_onboarding_excludes_pages_without_content(
        self, db_session: AsyncSession
    ):
        """Onboarding graph excludes pages that have no PageContent record at all."""
        project = _make_project(db_session)

        # Page with content → included
        with_content = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/has-content",
            labels=["seo"],
        )
        _make_page_content(db_session, with_content.id, status="complete")
        _make_page_keywords(db_session, with_content.id, primary_keyword="kw1")

        # Page without content → excluded (no PageContent record)
        no_content = _make_crawled_page(
            db_session,
            project.id,
            url="https://example.com/no-content",
            labels=["seo"],
        )
        _make_page_keywords(db_session, no_content.id, primary_keyword="kw2")

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_onboarding_graph(project.id, db_session)

        page_ids = {p["page_id"] for p in graph["pages"]}
        assert with_content.id in page_ids
        assert no_content.id not in page_ids

    @pytest.mark.asyncio
    async def test_onboarding_excludes_cluster_source_pages(
        self, db_session: AsyncSession
    ):
        """Onboarding graph only includes pages with source='onboarding'."""
        project = _make_project(db_session)

        # Onboarding page → included
        onboarding_page = _make_crawled_page(
            db_session,
            project.id,
            source="onboarding",
            url="https://example.com/onboarding",
            labels=["seo"],
        )
        _make_page_content(db_session, onboarding_page.id, status="complete")
        _make_page_keywords(db_session, onboarding_page.id, primary_keyword="kw1")

        # Cluster page → excluded from onboarding graph
        cluster_page = _make_crawled_page(
            db_session,
            project.id,
            source="cluster",
            url="https://example.com/cluster",
            labels=["seo"],
        )
        _make_page_content(db_session, cluster_page.id, status="complete")
        _make_page_keywords(db_session, cluster_page.id, primary_keyword="kw2")

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_onboarding_graph(project.id, db_session)

        page_ids = {p["page_id"] for p in graph["pages"]}
        assert onboarding_page.id in page_ids
        assert cluster_page.id not in page_ids

    @pytest.mark.asyncio
    async def test_cluster_graph_only_includes_cluster_pages(
        self, db_session: AsyncSession
    ):
        """Cluster graph only includes pages belonging to the specified cluster."""
        project = _make_project(db_session)
        cluster_a = _make_cluster(db_session, project.id)
        cluster_b = _make_cluster(db_session, project.id)

        # Pages in cluster A
        cp_a1 = _make_crawled_page(
            db_session, project.id, source="cluster", url="https://example.com/a1"
        )
        _make_cluster_page(
            db_session, cluster_a.id, cp_a1, role="parent", keyword="kw a1"
        )

        cp_a2 = _make_crawled_page(
            db_session, project.id, source="cluster", url="https://example.com/a2"
        )
        _make_cluster_page(
            db_session, cluster_a.id, cp_a2, role="child", keyword="kw a2"
        )

        # Page in cluster B — should NOT appear in cluster A's graph
        cp_b1 = _make_crawled_page(
            db_session, project.id, source="cluster", url="https://example.com/b1"
        )
        _make_cluster_page(
            db_session, cluster_b.id, cp_b1, role="parent", keyword="kw b1"
        )

        await db_session.flush()

        planner = SiloLinkPlanner()
        graph = await planner.build_cluster_graph(cluster_a.id, db_session)

        page_ids = {p["crawled_page_id"] for p in graph["pages"]}
        assert cp_a1.id in page_ids
        assert cp_a2.id in page_ids
        assert cp_b1.id not in page_ids
