"""Integration tests for internal links API endpoints.

Tests the following 8 endpoints end-to-end:
- POST /api/v1/projects/{project_id}/links/plan (trigger link planning)
- GET /api/v1/projects/{project_id}/links/plan/status (poll planning status)
- GET /api/v1/projects/{project_id}/links (link map)
- GET /api/v1/projects/{project_id}/links/page/{page_id} (page link details)
- GET /api/v1/projects/{project_id}/links/suggestions/{target_page_id} (anchor suggestions)
- POST /api/v1/projects/{project_id}/links (add manual link)
- DELETE /api/v1/projects/{project_id}/links/{link_id} (remove link)
- PUT /api/v1/projects/{project_id}/links/{link_id} (edit link anchor text)
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.internal_link import InternalLink
from app.models.keyword_cluster import ClusterPage, ClusterStatus, KeywordCluster
from app.models.page_content import ContentStatus, PageContent
from app.models.page_keywords import PageKeywords
from app.models.project import Project

# ---------------------------------------------------------------------------
# Sample HTML content for injection tests
# ---------------------------------------------------------------------------

SAMPLE_HTML = (
    "<h2>Running Shoes Guide</h2>"
    "<p>Running shoes are essential for any runner. "
    "Choosing the right pair can improve performance and prevent injury.</p>"
    "<p>There are many types of trail running shoes available on the market. "
    "Each type is designed for different terrain and running styles.</p>"
    "<p>Consider factors like cushioning, stability, and fit "
    "when selecting your next pair of running shoes.</p>"
)

SAMPLE_HTML_WITH_LINK = (
    "<h2>Running Shoes Guide</h2>"
    "<p>Running shoes are essential for any runner. "
    'Choosing the right pair of <a href="https://example.com/best-running-shoes">'
    "best running shoes</a> can improve performance and prevent injury.</p>"
    "<p>There are many types of trail running shoes available on the market. "
    "Each type is designed for different terrain and running styles.</p>"
    "<p>Consider factors like cushioning, stability, and fit "
    "when selecting your next pair of running shoes.</p>"
)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestLinksAPI:
    """Integration tests for links API endpoints."""

    # -----------------------------------------------------------------------
    # Fixtures
    # -----------------------------------------------------------------------

    @pytest.fixture
    async def project(self, db_session: AsyncSession) -> Project:
        """Create a project for testing."""
        p = Project(
            id=str(uuid4()),
            name="Test Project",
            site_url="https://example.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(p)
        await db_session.commit()
        return p

    @pytest.fixture
    async def cluster(
        self, db_session: AsyncSession, project: Project
    ) -> KeywordCluster:
        """Create an approved cluster with approved pages."""
        cluster = KeywordCluster(
            id=str(uuid4()),
            project_id=project.id,
            seed_keyword="running shoes",
            name="Running Shoes Cluster",
            status=ClusterStatus.APPROVED.value,
            generation_metadata={},
        )
        db_session.add(cluster)
        await db_session.flush()
        return cluster

    @pytest.fixture
    async def pages(
        self, db_session: AsyncSession, project: Project
    ) -> tuple[CrawledPage, CrawledPage, CrawledPage]:
        """Create 3 crawled pages for the project."""
        page1 = CrawledPage(
            id=str(uuid4()),
            project_id=project.id,
            normalized_url="https://example.com/running-shoes",
            title="Running Shoes",
            source="cluster",
            status="completed",
            labels=[],
        )
        page2 = CrawledPage(
            id=str(uuid4()),
            project_id=project.id,
            normalized_url="https://example.com/best-running-shoes",
            title="Best Running Shoes",
            source="cluster",
            status="completed",
            labels=[],
        )
        page3 = CrawledPage(
            id=str(uuid4()),
            project_id=project.id,
            normalized_url="https://example.com/trail-running-shoes",
            title="Trail Running Shoes",
            source="cluster",
            status="completed",
            labels=[],
        )
        db_session.add_all([page1, page2, page3])
        await db_session.commit()
        return (page1, page2, page3)

    @pytest.fixture
    async def cluster_pages(
        self,
        db_session: AsyncSession,
        cluster: KeywordCluster,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
    ) -> list[ClusterPage]:
        """Create cluster pages linking cluster to crawled pages."""
        page1, page2, page3 = pages
        cp_parent = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="running shoes",
            role="parent",
            url_slug="running-shoes",
            is_approved=True,
            crawled_page_id=page1.id,
            composite_score=80.0,
        )
        cp_child1 = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="best running shoes",
            role="child",
            url_slug="best-running-shoes",
            is_approved=True,
            crawled_page_id=page2.id,
            composite_score=70.0,
        )
        cp_child2 = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="trail running shoes",
            role="child",
            url_slug="trail-running-shoes",
            is_approved=True,
            crawled_page_id=page3.id,
            composite_score=60.0,
        )
        db_session.add_all([cp_parent, cp_child1, cp_child2])
        await db_session.commit()
        return [cp_parent, cp_child1, cp_child2]

    @pytest.fixture
    async def page_contents(
        self,
        db_session: AsyncSession,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
    ) -> list[PageContent]:
        """Create complete page content for all pages."""
        contents = []
        for page in pages:
            pc = PageContent(
                id=str(uuid4()),
                crawled_page_id=page.id,
                page_title=page.title,
                meta_description=f"Meta for {page.title}",
                top_description="<p>Top content</p>",
                bottom_description=SAMPLE_HTML,
                word_count=500,
                status=ContentStatus.COMPLETE.value,
            )
            contents.append(pc)
            db_session.add(pc)
        await db_session.commit()
        return contents

    @pytest.fixture
    async def page_keywords(
        self,
        db_session: AsyncSession,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
    ) -> list[PageKeywords]:
        """Create approved keywords for all pages."""
        keywords = []
        kw_names = ["running shoes", "best running shoes", "trail running shoes"]
        for page, kw_name in zip(pages, kw_names, strict=True):
            pk = PageKeywords(
                id=str(uuid4()),
                crawled_page_id=page.id,
                primary_keyword=kw_name,
                secondary_keywords=["athletic footwear"],
                alternative_keywords=[],
                is_approved=True,
                is_priority=True,
            )
            keywords.append(pk)
            db_session.add(pk)
        await db_session.commit()
        return keywords

    @pytest.fixture
    async def content_brief(
        self,
        db_session: AsyncSession,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
    ) -> ContentBrief:
        """Create a content brief for the second page (target for suggestions)."""
        brief = ContentBrief(
            id=str(uuid4()),
            page_id=pages[1].id,
            keyword="best running shoes",
            keyword_targets=[
                {"keyword": "best running shoes"},
                {"keyword": "top rated running shoes"},
                {"keyword": "running shoe reviews"},
            ],
            heading_targets=[],
            lsi_terms=[],
        )
        db_session.add(brief)
        await db_session.commit()
        return brief

    @pytest.fixture
    async def existing_link(
        self,
        db_session: AsyncSession,
        project: Project,
        cluster: KeywordCluster,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        page_contents: list[PageContent],
    ) -> InternalLink:
        """Create an existing internal link from page1 -> page2."""
        link = InternalLink(
            id=str(uuid4()),
            source_page_id=pages[0].id,
            target_page_id=pages[1].id,
            project_id=project.id,
            cluster_id=cluster.id,
            scope="cluster",
            anchor_text="best running shoes",
            anchor_type="exact_match",
            position_in_content=0,
            is_mandatory=False,
            placement_method="rule_based",
            status="verified",
        )
        db_session.add(link)

        # Update page content to include the link
        page_contents[0].bottom_description = SAMPLE_HTML_WITH_LINK
        await db_session.commit()
        return link

    @pytest.fixture
    async def mandatory_link(
        self,
        db_session: AsyncSession,
        project: Project,
        cluster: KeywordCluster,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
    ) -> InternalLink:
        """Create a mandatory internal link (cannot be deleted)."""
        link = InternalLink(
            id=str(uuid4()),
            source_page_id=pages[1].id,
            target_page_id=pages[0].id,
            project_id=project.id,
            cluster_id=cluster.id,
            scope="cluster",
            anchor_text="running shoes",
            anchor_type="exact_match",
            position_in_content=0,
            is_mandatory=True,
            placement_method="rule_based",
            status="verified",
        )
        db_session.add(link)
        await db_session.commit()
        return link

    # -----------------------------------------------------------------------
    # POST /links/plan — trigger link planning
    # -----------------------------------------------------------------------

    async def test_plan_links_success_cluster(
        self,
        async_client: AsyncClient,
        project: Project,
        cluster: KeywordCluster,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        cluster_pages: list[ClusterPage],
        page_contents: list[PageContent],
        page_keywords: list[PageKeywords],
    ):
        """POST plan links with valid cluster data returns 202."""
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/links/plan",
            json={"scope": "cluster", "cluster_id": cluster.id},
        )

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "planning"
        assert data["current_step"] == 1

        # Clean up active plans for other tests
        from app.api.v1.links import _active_plans

        _active_plans.discard((project.id, "cluster", cluster.id))

    async def test_plan_links_400_prerequisites_not_met(
        self,
        async_client: AsyncClient,
        project: Project,
        cluster: KeywordCluster,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        cluster_pages: list[ClusterPage],
    ):
        """POST plan links returns 400 when content is not complete."""
        # No page_contents or page_keywords fixtures → prerequisites fail
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/links/plan",
            json={"scope": "cluster", "cluster_id": cluster.id},
        )

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "Content not complete" in detail or "Keywords not approved" in detail

    async def test_plan_links_400_invalid_scope_missing_cluster_id(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """POST plan links with scope='cluster' but no cluster_id returns 400."""
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/links/plan",
            json={"scope": "cluster"},
        )

        assert resp.status_code == 400
        assert "cluster_id is required" in resp.json()["detail"]

    async def test_plan_links_400_cluster_not_enough_pages(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
    ):
        """POST plan links returns 400 when cluster has < 2 approved pages."""
        # Create cluster with only 1 approved page
        cluster = KeywordCluster(
            id=str(uuid4()),
            project_id=project.id,
            seed_keyword="solo",
            name="Solo Cluster",
            status=ClusterStatus.APPROVED.value,
            generation_metadata={},
        )
        db_session.add(cluster)
        await db_session.flush()

        cp = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="solo keyword",
            role="parent",
            url_slug="solo",
            is_approved=True,
        )
        db_session.add(cp)
        await db_session.commit()

        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/links/plan",
            json={"scope": "cluster", "cluster_id": cluster.id},
        )

        assert resp.status_code == 400
        assert "at least 2 approved pages" in resp.json()["detail"]

    # -----------------------------------------------------------------------
    # GET /links/plan/status — poll planning status
    # -----------------------------------------------------------------------

    async def test_get_plan_status_idle(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """GET plan status when no pipeline is running returns idle."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/links/plan/status",
            params={"scope": "onboarding"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "idle"
        assert data["pages_processed"] == 0
        assert data["total_pages"] == 0

    async def test_get_plan_status_during_planning(
        self,
        async_client: AsyncClient,
        project: Project,
        cluster: KeywordCluster,
    ):
        """GET plan status returns correct step during active planning."""
        # Inject progress into the module-level dict
        from app.services.link_planning import _pipeline_progress

        progress_key = (project.id, "cluster", cluster.id)
        _pipeline_progress[progress_key] = {
            "status": "planning",
            "current_step": 2,
            "step_label": "Selecting targets",
            "pages_processed": 1,
            "total_pages": 3,
        }

        try:
            resp = await async_client.get(
                f"/api/v1/projects/{project.id}/links/plan/status",
                params={"scope": "cluster", "cluster_id": cluster.id},
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "planning"
            assert data["current_step"] == 2
            assert data["step_label"] == "Selecting targets"
            assert data["pages_processed"] == 1
            assert data["total_pages"] == 3
        finally:
            _pipeline_progress.pop(progress_key, None)

    async def test_get_plan_status_complete(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """GET plan status returns complete with total_links."""
        from app.services.link_planning import _pipeline_progress

        progress_key = (project.id, "onboarding", None)
        _pipeline_progress[progress_key] = {
            "status": "complete",
            "current_step": 4,
            "step_label": "Complete",
            "pages_processed": 5,
            "total_pages": 5,
            "total_links": 15,
        }

        try:
            resp = await async_client.get(
                f"/api/v1/projects/{project.id}/links/plan/status",
                params={"scope": "onboarding"},
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "complete"
            assert data["total_links"] == 15
        finally:
            _pipeline_progress.pop(progress_key, None)

    # -----------------------------------------------------------------------
    # GET /links — link map
    # -----------------------------------------------------------------------

    async def test_get_link_map_cluster_scope(
        self,
        async_client: AsyncClient,
        project: Project,
        cluster: KeywordCluster,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        cluster_pages: list[ClusterPage],
        page_keywords: list[PageKeywords],
        existing_link: InternalLink,
    ):
        """GET link map for cluster scope returns stats and page summaries."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/links",
            params={"scope": "cluster", "cluster_id": cluster.id},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["scope"] == "cluster"
        assert data["total_links"] == 1
        assert data["total_pages"] >= 1
        assert "avg_links_per_page" in data
        assert "validation_pass_rate" in data
        assert "anchor_diversity" in data
        assert isinstance(data["pages"], list)
        assert len(data["pages"]) >= 1
        # Cluster scope includes hierarchy
        assert data["hierarchy"] is not None

    async def test_get_link_map_onboarding_scope(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """GET link map for onboarding scope with no links returns empty stats."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/links",
            params={"scope": "onboarding"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["scope"] == "onboarding"
        assert data["total_links"] == 0
        assert data["total_pages"] == 0
        assert data["pages"] == []
        assert data["hierarchy"] is None

    # -----------------------------------------------------------------------
    # GET /links/page/{page_id} — page link details
    # -----------------------------------------------------------------------

    async def test_get_page_links_outbound_and_inbound(
        self,
        async_client: AsyncClient,
        project: Project,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        existing_link: InternalLink,
    ):
        """GET page links returns outbound + inbound lists."""
        # page1 has outbound link to page2
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/links/page/{pages[0].id}",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["outbound_links"]) == 1
        assert data["outbound_links"][0]["target_page_id"] == pages[1].id
        assert data["outbound_links"][0]["anchor_text"] == "best running shoes"
        assert isinstance(data["inbound_links"], list)
        assert "diversity_score" in data

        # page2 has inbound link from page1
        resp2 = await async_client.get(
            f"/api/v1/projects/{project.id}/links/page/{pages[1].id}",
        )

        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["inbound_links"]) == 1
        assert data2["inbound_links"][0]["source_page_id"] == pages[0].id

    async def test_get_page_links_404_for_invalid_page(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """GET page links with non-existent page returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/links/page/{fake_id}",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # -----------------------------------------------------------------------
    # GET /links/suggestions/{target_page_id} — anchor suggestions
    # -----------------------------------------------------------------------

    async def test_get_anchor_suggestions_returns_keyword_and_variations(
        self,
        async_client: AsyncClient,
        project: Project,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        page_keywords: list[PageKeywords],
        content_brief: ContentBrief,
        existing_link: InternalLink,
    ):
        """GET suggestions returns primary keyword, POP variations, and usage counts."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/links/suggestions/{pages[1].id}",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["primary_keyword"] == "best running shoes"
        # POP variations should exclude the primary keyword
        assert "top rated running shoes" in data["pop_variations"]
        assert "running shoe reviews" in data["pop_variations"]
        assert "best running shoes" not in data["pop_variations"]
        # Usage counts from existing link targeting page2
        assert isinstance(data["usage_counts"], dict)
        assert data["usage_counts"].get("best running shoes", 0) >= 1

    async def test_get_anchor_suggestions_404_for_invalid_page(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """GET suggestions with non-existent page returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/links/suggestions/{fake_id}",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # -----------------------------------------------------------------------
    # POST /links — add manual link
    # -----------------------------------------------------------------------

    async def test_add_link_success(
        self,
        async_client: AsyncClient,
        project: Project,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        cluster_pages: list[ClusterPage],
        page_contents: list[PageContent],
        page_keywords: list[PageKeywords],
    ):
        """POST add link with valid data returns 201."""
        # Mock the LLM fallback so we don't need real API calls
        with patch(
            "app.api.v1.links.LinkInjector.inject_llm_fallback",
            new_callable=AsyncMock,
        ) as mock_llm:
            # Rule-based injection should succeed for "trail running shoes"
            # since it appears in SAMPLE_HTML
            resp = await async_client.post(
                f"/api/v1/projects/{project.id}/links",
                json={
                    "source_page_id": pages[0].id,
                    "target_page_id": pages[2].id,
                    "anchor_text": "trail running shoes",
                    "anchor_type": "exact_match",
                },
            )

            assert resp.status_code == 201
            data = resp.json()
            assert data["source_page_id"] == pages[0].id
            assert data["target_page_id"] == pages[2].id
            assert data["anchor_text"] == "trail running shoes"
            assert data["status"] == "verified"
            assert data["placement_method"] == "rule_based"
            # LLM fallback should not have been called
            mock_llm.assert_not_called()

    async def test_add_link_400_self_link(
        self,
        async_client: AsyncClient,
        project: Project,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        page_contents: list[PageContent],
    ):
        """POST add link with same source and target returns 400."""
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/links",
            json={
                "source_page_id": pages[0].id,
                "target_page_id": pages[0].id,
                "anchor_text": "self link",
                "anchor_type": "natural",
            },
        )

        assert resp.status_code == 400
        assert "self-link" in resp.json()["detail"].lower()

    async def test_add_link_400_duplicate(
        self,
        async_client: AsyncClient,
        project: Project,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        page_contents: list[PageContent],
        existing_link: InternalLink,
    ):
        """POST add link with duplicate source->target returns 400."""
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/links",
            json={
                "source_page_id": pages[0].id,
                "target_page_id": pages[1].id,
                "anchor_text": "another anchor",
                "anchor_type": "natural",
            },
        )

        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    # -----------------------------------------------------------------------
    # DELETE /links/{link_id} — remove link
    # -----------------------------------------------------------------------

    async def test_remove_link_success_discretionary(
        self,
        async_client: AsyncClient,
        async_session_factory,
        project: Project,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        existing_link: InternalLink,
    ):
        """DELETE discretionary link returns 204 and sets status='removed'."""
        resp = await async_client.delete(
            f"/api/v1/projects/{project.id}/links/{existing_link.id}",
        )

        assert resp.status_code == 204

        # Use fresh session to verify DB state (API commits on its own session)
        async with async_session_factory() as fresh_session:
            stmt = select(InternalLink).where(InternalLink.id == existing_link.id)
            result = await fresh_session.execute(stmt)
            link = result.scalar_one()
            assert link.status == "removed"

    async def test_remove_link_400_mandatory(
        self,
        async_client: AsyncClient,
        project: Project,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        page_contents: list[PageContent],
        mandatory_link: InternalLink,
    ):
        """DELETE mandatory link returns 400."""
        resp = await async_client.delete(
            f"/api/v1/projects/{project.id}/links/{mandatory_link.id}",
        )

        assert resp.status_code == 400
        assert "mandatory" in resp.json()["detail"].lower()

    async def test_remove_link_404_invalid_id(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """DELETE non-existent link returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.delete(
            f"/api/v1/projects/{project.id}/links/{fake_id}",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # -----------------------------------------------------------------------
    # PUT /links/{link_id} — edit link anchor text
    # -----------------------------------------------------------------------

    async def test_edit_link_success(
        self,
        async_client: AsyncClient,
        async_session_factory,
        project: Project,
        pages: tuple[CrawledPage, CrawledPage, CrawledPage],
        existing_link: InternalLink,
    ):
        """PUT edit link updates anchor text in DB and content."""
        new_anchor = "top running shoes"
        resp = await async_client.put(
            f"/api/v1/projects/{project.id}/links/{existing_link.id}",
            json={"anchor_text": new_anchor, "anchor_type": "partial_match"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["anchor_text"] == new_anchor
        assert data["anchor_type"] == "partial_match"

        # Use fresh session to verify DB state (API commits on its own session)
        async with async_session_factory() as fresh_session:
            # Verify link row was updated
            stmt = select(InternalLink).where(InternalLink.id == existing_link.id)
            result = await fresh_session.execute(stmt)
            link = result.scalar_one()
            assert link.anchor_text == new_anchor
            assert link.anchor_type == "partial_match"

            # Verify content was updated
            content_stmt = select(PageContent).where(
                PageContent.crawled_page_id == pages[0].id,
            )
            content_result = await fresh_session.execute(content_stmt)
            content = content_result.scalar_one()
            assert new_anchor in content.bottom_description

    async def test_edit_link_404_invalid_id(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """PUT edit link with non-existent link returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.put(
            f"/api/v1/projects/{project.id}/links/{fake_id}",
            json={"anchor_text": "new text", "anchor_type": "natural"},
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]
