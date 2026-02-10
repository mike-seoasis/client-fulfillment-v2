"""Tests for SiloLinkPlanner graph construction and target selection.

Tests cover:
- Cluster graph: parent + children produce parent_child + sibling edges
- Cluster graph: single page returns no edges
- Onboarding graph: overlapping labels produce edges with correct weights
- Onboarding graph: pages below threshold (1 shared label) have no edges
- Onboarding graph: pages with no labels have no edges
- Both modes: only pages with complete content and approved keywords included
- calculate_budget: word count → link budget clamped to 3-5
- select_targets_cluster: parent/child targeting with hierarchy rules
- select_targets_onboarding: label overlap + priority bonus + diversity penalty
"""

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawled_page import CrawledPage
from app.models.keyword_cluster import ClusterPage, KeywordCluster
from app.models.page_content import PageContent
from app.models.page_keywords import PageKeywords
from app.models.project import Project
from app.services.link_planning import (
    SiloLinkPlanner,
    calculate_budget,
    select_targets_cluster,
    select_targets_onboarding,
)

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


# ---------------------------------------------------------------------------
# Tests: calculate_budget (S9-016)
# ---------------------------------------------------------------------------


class TestCalculateBudget:
    """Tests for calculate_budget — pure function, no DB needed."""

    def test_200_words_returns_3(self):
        """200 words → 200 // 250 = 0, clamped to min 3."""
        assert calculate_budget(200) == 3

    def test_1000_words_returns_4(self):
        """1000 words → 1000 // 250 = 4, within range."""
        assert calculate_budget(1000) == 4

    def test_2000_words_returns_5(self):
        """2000 words → 2000 // 250 = 8, clamped to max 5."""
        assert calculate_budget(2000) == 5

    def test_0_words_returns_3(self):
        """0 words → clamped to min 3."""
        assert calculate_budget(0) == 3

    def test_750_words_returns_3(self):
        """750 words → 750 // 250 = 3, exactly at minimum."""
        assert calculate_budget(750) == 3

    def test_1250_words_returns_5(self):
        """1250 words → 1250 // 250 = 5, exactly at maximum."""
        assert calculate_budget(1250) == 5


# ---------------------------------------------------------------------------
# Tests: select_targets_cluster (S9-016)
# ---------------------------------------------------------------------------


def _make_cluster_graph(
    parent_score: float = 90.0,
    child_count: int = 5,
    child_base_score: float = 80.0,
) -> dict[str, Any]:
    """Build a synthetic cluster graph dict (mimics build_cluster_graph output)."""
    pages = [
        {
            "page_id": "parent-1",
            "crawled_page_id": "cp-parent-1",
            "keyword": "parent keyword",
            "role": "parent",
            "composite_score": parent_score,
            "url": "https://example.com/parent",
        }
    ]
    edges = []
    for i in range(child_count):
        child_id = f"child-{i}"
        pages.append(
            {
                "page_id": child_id,
                "crawled_page_id": f"cp-{child_id}",
                "keyword": f"child keyword {i}",
                "role": "child",
                "composite_score": child_base_score - i * 5,
                "url": f"https://example.com/{child_id}",
            }
        )
        # Parent-child edge
        edges.append({"source": "parent-1", "target": child_id, "type": "parent_child"})

    # Sibling edges among children
    for i in range(child_count):
        for j in range(i + 1, child_count):
            edges.append(
                {"source": f"child-{i}", "target": f"child-{j}", "type": "sibling"}
            )

    return {"pages": pages, "edges": edges}


class TestSelectTargetsCluster:
    """Tests for select_targets_cluster — pure function, no DB needed."""

    def test_child_gets_parent_as_first_target_plus_siblings(self):
        """Child gets parent as mandatory first target, then siblings by composite_score."""
        graph = _make_cluster_graph(child_count=4)
        budgets = {p["page_id"]: 4 for p in graph["pages"]}

        result = select_targets_cluster(graph, budgets)

        # Each child should have parent as first (mandatory) target
        for i in range(4):
            child_id = f"child-{i}"
            targets = result[child_id]
            assert targets[0]["page_id"] == "parent-1"
            assert targets[0]["is_mandatory"] is True

            # Remaining should be siblings (not self)
            sibling_ids = [t["page_id"] for t in targets[1:]]
            assert child_id not in sibling_ids
            for sid in sibling_ids:
                assert sid.startswith("child-")

    def test_parent_gets_children_sorted_by_composite_score(self):
        """Parent gets children sorted by composite_score descending."""
        graph = _make_cluster_graph(child_count=5)
        budgets = {"parent-1": 5, **{f"child-{i}": 4 for i in range(5)}}

        result = select_targets_cluster(graph, budgets)

        parent_targets = result["parent-1"]
        assert len(parent_targets) == 5

        # Should be ordered by composite_score descending
        scores = [t["composite_score"] for t in parent_targets]
        assert scores == sorted(scores, reverse=True)

        # None should be mandatory for parent's targets
        for t in parent_targets:
            assert t["is_mandatory"] is False

    def test_small_cluster_2_pages_partially_fills_budget(self):
        """Small cluster (parent + 1 child) partially fills budget without error."""
        graph = _make_cluster_graph(child_count=1)
        budgets = {"parent-1": 4, "child-0": 4}

        result = select_targets_cluster(graph, budgets)

        # Parent can only target 1 child (budget 4 but only 1 child available)
        assert len(result["parent-1"]) == 1
        assert result["parent-1"][0]["page_id"] == "child-0"

        # Child gets parent (mandatory) + 0 siblings = 1 target (budget 4 but only parent available)
        assert len(result["child-0"]) == 1
        assert result["child-0"][0]["page_id"] == "parent-1"
        assert result["child-0"][0]["is_mandatory"] is True

    def test_child_siblings_ordered_by_composite_score(self):
        """Child's sibling targets are ordered by composite_score (highest first)."""
        graph = _make_cluster_graph(child_count=5)
        # Give child-0 a budget of 5 (1 parent + 4 siblings)
        budgets = {"parent-1": 5, **{f"child-{i}": 5 for i in range(5)}}

        result = select_targets_cluster(graph, budgets)

        # child-0's targets: index 0 = parent, indices 1+ = siblings by score
        child_0_targets = result["child-0"]
        assert child_0_targets[0]["page_id"] == "parent-1"
        sibling_scores = [t["composite_score"] for t in child_0_targets[1:]]
        assert sibling_scores == sorted(sibling_scores, reverse=True)


# ---------------------------------------------------------------------------
# Tests: select_targets_onboarding (S9-016)
# ---------------------------------------------------------------------------


def _make_onboarding_graph(
    page_count: int = 6,
    labels_per_page: list[list[str]] | None = None,
    priorities: list[bool] | None = None,
) -> dict[str, Any]:
    """Build a synthetic onboarding graph dict (mimics build_onboarding_graph output)."""
    if labels_per_page is None:
        # Default: overlapping labels so edges exist between most pairs
        base_labels = [
            ["seo", "content", "marketing"],
            ["seo", "content", "analytics"],
            ["seo", "marketing", "analytics"],
            ["content", "marketing", "analytics"],
            ["seo", "content", "marketing", "analytics"],
            ["seo", "content", "email"],
        ]
        labels_per_page = base_labels[:page_count]

    if priorities is None:
        priorities = [False] * page_count

    pages = []
    for i in range(page_count):
        pages.append(
            {
                "page_id": f"page-{i}",
                "keyword": f"keyword {i}",
                "url": f"https://example.com/page-{i}",
                "labels": labels_per_page[i] if i < len(labels_per_page) else [],
                "is_priority": priorities[i] if i < len(priorities) else False,
            }
        )

    # Compute edges based on label overlap >= 2
    edges = []
    for i in range(page_count):
        for j in range(i + 1, page_count):
            labels_i = set(labels_per_page[i] if i < len(labels_per_page) else [])
            labels_j = set(labels_per_page[j] if j < len(labels_per_page) else [])
            overlap = len(labels_i & labels_j)
            if overlap >= 2:
                edges.append(
                    {"source": f"page-{i}", "target": f"page-{j}", "weight": overlap}
                )

    return {"pages": pages, "edges": edges}


class TestSelectTargetsOnboarding:
    """Tests for select_targets_onboarding — pure function, no DB needed."""

    def test_priority_page_bonus_wins_tiebreakers(self):
        """Priority page gets +2 bonus, winning tiebreakers over non-priority."""
        # 3 pages with identical label overlap (2 shared labels each pair)
        # page-1 is priority, page-0 and page-2 are not
        graph = _make_onboarding_graph(
            page_count=3,
            labels_per_page=[
                ["seo", "content"],
                ["seo", "content"],
                ["seo", "content"],
            ],
            priorities=[False, True, False],
        )
        budgets = {"page-0": 3, "page-1": 3, "page-2": 3}

        result = select_targets_onboarding(graph, budgets)

        # For page-0: both page-1 (priority) and page-2 have overlap=2
        # page-1 gets +2 bonus → score = 2 + 2 = 4 vs page-2 score = 2 + 0 = 2
        # So page-1 should be first target for page-0
        assert result["page-0"][0]["page_id"] == "page-1"
        assert result["page-0"][0]["is_priority"] is True

    def test_diversity_penalty_prevents_one_page_getting_all_links(self):
        """Diversity penalty prevents a single page from hogging all inbound links."""
        # 5 pages all connected to each other (same labels)
        # Without diversity: one popular target might get picked by everyone
        # With diversity: inbound counts should be more evenly distributed
        graph = _make_onboarding_graph(
            page_count=5,
            labels_per_page=[
                ["seo", "content", "marketing"],
                ["seo", "content", "marketing"],
                ["seo", "content", "marketing"],
                ["seo", "content", "marketing"],
                ["seo", "content", "marketing"],
            ],
            priorities=[False, False, False, False, False],
        )
        budgets = {f"page-{i}": 3 for i in range(5)}

        result = select_targets_onboarding(graph, budgets)

        # Count inbound links per page
        inbound: dict[str, int] = {f"page-{i}": 0 for i in range(5)}
        for _page_id, targets in result.items():
            for t in targets:
                inbound[t["page_id"]] += 1

        # With diversity penalty, no page should have dramatically more inbound
        # than others. The max inbound should be at most 2x the min inbound.
        inbound_values = list(inbound.values())
        assert max(inbound_values) <= min(inbound_values) + 3  # reasonable spread

    def test_page_with_no_eligible_targets_gets_empty_list(self):
        """A page with no edges (no eligible targets) gets an empty target list."""
        # page-0 has no label overlap with others (unique labels)
        graph = _make_onboarding_graph(
            page_count=3,
            labels_per_page=[
                ["unique1", "unique2"],  # no overlap with others
                ["seo", "content"],
                ["seo", "content"],
            ],
        )
        budgets = {"page-0": 3, "page-1": 3, "page-2": 3}

        result = select_targets_onboarding(graph, budgets)

        # page-0 has no eligible targets (no edges)
        assert result["page-0"] == []

        # page-1 and page-2 still link to each other
        assert len(result["page-1"]) >= 1
        assert len(result["page-2"]) >= 1

    def test_targets_include_label_overlap_and_score(self):
        """Selected targets include label_overlap and score fields."""
        graph = _make_onboarding_graph(
            page_count=3,
            labels_per_page=[
                ["seo", "content", "marketing"],
                ["seo", "content"],
                ["seo", "content", "marketing"],
            ],
        )
        budgets = {"page-0": 3, "page-1": 3, "page-2": 3}

        result = select_targets_onboarding(graph, budgets)

        for page_targets in result.values():
            for target in page_targets:
                assert "label_overlap" in target
                assert "score" in target
                assert isinstance(target["label_overlap"], int)
                assert isinstance(target["score"], float)

    def test_budget_limits_number_of_targets(self):
        """Budget correctly limits the number of targets per page."""
        # All pages connected with overlap >= 2
        graph = _make_onboarding_graph(
            page_count=6,
            labels_per_page=[
                ["seo", "content", "marketing"],
                ["seo", "content", "analytics"],
                ["seo", "marketing", "analytics"],
                ["content", "marketing", "analytics"],
                ["seo", "content", "marketing", "analytics"],
                ["seo", "content", "email"],
            ],
        )
        budgets = {f"page-{i}": 3 for i in range(6)}

        result = select_targets_onboarding(graph, budgets)

        # No page should exceed its budget
        for page_id, targets in result.items():
            assert len(targets) <= budgets[page_id]
