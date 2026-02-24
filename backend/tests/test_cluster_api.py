"""Integration tests for cluster API endpoints.

Tests the following endpoints end-to-end:
- POST /api/v1/projects/{project_id}/clusters (create cluster)
- GET /api/v1/projects/{project_id}/clusters (list clusters)
- GET /api/v1/projects/{project_id}/clusters/{cluster_id} (cluster detail)
- PATCH /api/v1/projects/{project_id}/clusters/{cluster_id}/pages/{page_id} (update page)
- POST /api/v1/projects/{project_id}/clusters/{cluster_id}/approve (bulk approve)
- DELETE /api/v1/projects/{project_id}/clusters/{cluster_id} (delete cluster)
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.claude import CompletionResult
from app.integrations.dataforseo import KeywordVolumeData, KeywordVolumeResult
from app.models.crawled_page import CrawledPage
from app.models.keyword_cluster import ClusterPage, ClusterStatus, KeywordCluster
from app.models.page_keywords import PageKeywords
from app.models.project import Project

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_claude_client(available: bool = True) -> MagicMock:
    client = MagicMock()
    client.available = available
    client.complete = AsyncMock()
    return client


def _make_dataforseo_client(available: bool = True) -> MagicMock:
    client = MagicMock()
    client.available = available
    client.get_keyword_volume_batch = AsyncMock()
    return client


def _stage1_response(seed: str = "running shoes") -> str:
    """Return Claude Stage 1 JSON response (candidate generation)."""
    return (
        '[\n'
        f'  {{"keyword": "best {seed}", "expansion_strategy": "attribute", '
        f'"rationale": "Quality modifier", "estimated_intent": "commercial"}},\n'
        f'  {{"keyword": "cheap {seed}", "expansion_strategy": "price_value", '
        f'"rationale": "Budget modifier", "estimated_intent": "transactional"}},\n'
        f'  {{"keyword": "{seed} for women", "expansion_strategy": "demographic", '
        f'"rationale": "Gender segment", "estimated_intent": "commercial"}},\n'
        f'  {{"keyword": "{seed} for men", "expansion_strategy": "demographic", '
        f'"rationale": "Gender segment", "estimated_intent": "commercial"}},\n'
        f'  {{"keyword": "trail {seed}", "expansion_strategy": "terrain", '
        f'"rationale": "Terrain segment", "estimated_intent": "commercial"}}\n'
        ']'
    )


def _stage3_response(seed: str = "running shoes") -> str:
    """Return Claude Stage 3 JSON response (filtering & role assignment)."""
    return (
        '[\n'
        f'  {{"keyword": "{seed}", "role": "parent", "relevance_score": 1.0, "reasoning": "Seed keyword"}},\n'
        f'  {{"keyword": "best {seed}", "role": "child", "relevance_score": 0.9, "reasoning": "High volume modifier"}},\n'
        f'  {{"keyword": "trail {seed}", "role": "child", "relevance_score": 0.8, "reasoning": "Terrain niche"}}\n'
        ']'
    )


def _volume_result(keywords: list[str]) -> KeywordVolumeResult:
    """Return a DataForSEO volume result for a list of keywords."""
    kw_data = [
        KeywordVolumeData(
            keyword=kw,
            search_volume=1000 + i * 500,
            cpc=1.5 + i * 0.5,
            competition=0.3 + i * 0.1,
            competition_level="MEDIUM",
        )
        for i, kw in enumerate(keywords)
    ]
    return KeywordVolumeResult(success=True, keywords=kw_data)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class TestClusterAPI:
    """Integration tests for cluster API endpoints."""

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
    async def cluster_draft(
        self, db_session: AsyncSession, project: Project
    ) -> KeywordCluster:
        """Create a draft cluster with pages (status=suggestions_ready)."""
        cluster = KeywordCluster(
            id=str(uuid4()),
            project_id=project.id,
            seed_keyword="running shoes",
            name="Running Shoes Cluster",
            status=ClusterStatus.SUGGESTIONS_READY.value,
            generation_metadata={"total_time_ms": 5000},
        )
        db_session.add(cluster)
        await db_session.flush()

        # Parent page
        parent = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="running shoes",
            role="parent",
            url_slug="running-shoes",
            expansion_strategy="seed",
            search_volume=5000,
            cpc=2.5,
            competition=0.4,
            competition_level="MEDIUM",
            composite_score=75.0,
            is_approved=True,
        )
        # Child pages
        child1 = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="best running shoes",
            role="child",
            url_slug="best-running-shoes",
            expansion_strategy="attribute",
            search_volume=3000,
            cpc=1.8,
            competition=0.3,
            competition_level="LOW",
            composite_score=65.0,
            is_approved=True,
        )
        child2 = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="trail running shoes",
            role="child",
            url_slug="trail-running-shoes",
            expansion_strategy="terrain",
            search_volume=2000,
            cpc=1.2,
            competition=0.5,
            competition_level="MEDIUM",
            composite_score=55.0,
            is_approved=False,
        )
        db_session.add_all([parent, child1, child2])
        await db_session.commit()
        return cluster

    @pytest.fixture
    async def cluster_approved(
        self, db_session: AsyncSession, project: Project
    ) -> KeywordCluster:
        """Create an approved cluster."""
        cluster = KeywordCluster(
            id=str(uuid4()),
            project_id=project.id,
            seed_keyword="hiking boots",
            name="Hiking Boots Cluster",
            status=ClusterStatus.APPROVED.value,
            generation_metadata={},
        )
        db_session.add(cluster)
        await db_session.commit()
        return cluster

    # -------------------------------------------------------------------
    # POST create cluster
    # -------------------------------------------------------------------

    async def test_create_cluster_success(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """POST create cluster returns 200 with valid response schema."""
        seed = "running shoes"
        mock_claude = _make_claude_client()
        mock_dataforseo = _make_dataforseo_client()

        # Stage 1 + Stage 3 responses
        mock_claude.complete.side_effect = [
            CompletionResult(
                success=True,
                text=_stage1_response(seed),
                input_tokens=500,
                output_tokens=300,
            ),
            CompletionResult(
                success=True,
                text=_stage3_response(seed),
                input_tokens=600,
                output_tokens=400,
            ),
        ]

        # Stage 2: volume data
        mock_dataforseo.get_keyword_volume_batch.return_value = _volume_result(
            [seed, f"best {seed}", f"cheap {seed}", f"{seed} for women",
             f"{seed} for men", f"trail {seed}"]
        )

        with (
            patch("app.api.v1.clusters.get_claude", return_value=mock_claude),
            patch("app.api.v1.clusters.get_dataforseo", return_value=mock_dataforseo),
        ):
            resp = await async_client.post(
                f"/api/v1/projects/{project.id}/clusters",
                json={"seed_keyword": seed, "name": "Running Shoes"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["seed_keyword"] == seed
        assert data["name"] == "Running Shoes"
        assert data["status"] == ClusterStatus.SUGGESTIONS_READY.value
        assert isinstance(data["pages"], list)
        assert len(data["pages"]) >= 1
        # Verify parent page exists
        roles = [p["role"] for p in data["pages"]]
        assert "parent" in roles

    async def test_create_cluster_invalid_project_returns_404(
        self,
        async_client: AsyncClient,
    ):
        """POST create cluster with non-existent project returns 404."""
        fake_id = str(uuid4())
        mock_claude = _make_claude_client()
        mock_dataforseo = _make_dataforseo_client()

        with (
            patch("app.api.v1.clusters.get_claude", return_value=mock_claude),
            patch("app.api.v1.clusters.get_dataforseo", return_value=mock_dataforseo),
        ):
            resp = await async_client.post(
                f"/api/v1/projects/{fake_id}/clusters",
                json={"seed_keyword": "test keyword"},
            )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # -------------------------------------------------------------------
    # GET list clusters
    # -------------------------------------------------------------------

    async def test_list_clusters_returns_page_and_approved_counts(
        self,
        async_client: AsyncClient,
        project: Project,
        cluster_draft: KeywordCluster,
    ):
        """GET list clusters returns page_count and approved_count."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/clusters",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Find our cluster
        cluster_data = next(c for c in data if c["id"] == cluster_draft.id)
        assert cluster_data["seed_keyword"] == "running shoes"
        assert cluster_data["page_count"] == 3
        assert cluster_data["approved_count"] == 2  # parent + child1

    async def test_list_clusters_empty_project(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """GET list clusters for project with no clusters returns empty list."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/clusters",
        )

        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_clusters_invalid_project_returns_404(
        self,
        async_client: AsyncClient,
    ):
        """GET list clusters with non-existent project returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.get(
            f"/api/v1/projects/{fake_id}/clusters",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # -------------------------------------------------------------------
    # GET cluster detail
    # -------------------------------------------------------------------

    async def test_get_cluster_detail_returns_all_page_fields(
        self,
        async_client: AsyncClient,
        project: Project,
        cluster_draft: KeywordCluster,
    ):
        """GET cluster detail returns all ClusterPage fields."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/clusters/{cluster_draft.id}",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == cluster_draft.id
        assert data["seed_keyword"] == "running shoes"
        assert len(data["pages"]) == 3

        # Verify page schema has all expected fields
        page = data["pages"][0]
        expected_fields = {
            "id", "keyword", "role", "url_slug", "expansion_strategy",
            "reasoning", "search_volume", "cpc", "competition",
            "competition_level", "composite_score", "is_approved",
            "crawled_page_id",
        }
        assert expected_fields.issubset(set(page.keys()))

    async def test_get_cluster_detail_invalid_cluster_returns_404(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """GET cluster detail with non-existent cluster_id returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/clusters/{fake_id}",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    async def test_get_cluster_detail_invalid_project_returns_404(
        self,
        async_client: AsyncClient,
    ):
        """GET cluster detail with non-existent project returns 404."""
        fake_project = str(uuid4())
        fake_cluster = str(uuid4())
        resp = await async_client.get(
            f"/api/v1/projects/{fake_project}/clusters/{fake_cluster}",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # -------------------------------------------------------------------
    # PATCH update cluster page
    # -------------------------------------------------------------------

    async def test_update_page_approve(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
        cluster_draft: KeywordCluster,
    ):
        """PATCH update page toggles is_approved."""
        # Get the unapproved child page
        stmt = select(ClusterPage).where(
            ClusterPage.cluster_id == cluster_draft.id,
            ClusterPage.is_approved == False,  # noqa: E712
        )
        result = await db_session.execute(stmt)
        page = result.scalar_one()

        resp = await async_client.patch(
            f"/api/v1/projects/{project.id}/clusters/{cluster_draft.id}/pages/{page.id}",
            json={"is_approved": True},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_approved"] is True
        assert data["id"] == page.id

    async def test_update_page_edit_keyword(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
        cluster_draft: KeywordCluster,
    ):
        """PATCH update page edits keyword."""
        stmt = select(ClusterPage).where(
            ClusterPage.cluster_id == cluster_draft.id,
            ClusterPage.role == "parent",
        )
        result = await db_session.execute(stmt)
        page = result.scalar_one()

        resp = await async_client.patch(
            f"/api/v1/projects/{project.id}/clusters/{cluster_draft.id}/pages/{page.id}",
            json={"keyword": "running sneakers"},
        )

        assert resp.status_code == 200
        assert resp.json()["keyword"] == "running sneakers"

    async def test_update_page_edit_slug(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
        cluster_draft: KeywordCluster,
    ):
        """PATCH update page edits url_slug."""
        stmt = select(ClusterPage).where(
            ClusterPage.cluster_id == cluster_draft.id,
            ClusterPage.role == "parent",
        )
        result = await db_session.execute(stmt)
        page = result.scalar_one()

        resp = await async_client.patch(
            f"/api/v1/projects/{project.id}/clusters/{cluster_draft.id}/pages/{page.id}",
            json={"url_slug": "running-sneakers"},
        )

        assert resp.status_code == 200
        assert resp.json()["url_slug"] == "running-sneakers"

    async def test_update_page_reassign_parent(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
        cluster_draft: KeywordCluster,
    ):
        """PATCH update page with role=parent demotes current parent to child."""
        # Get a child page
        stmt = select(ClusterPage).where(
            ClusterPage.cluster_id == cluster_draft.id,
            ClusterPage.role == "child",
        )
        result = await db_session.execute(stmt)
        child_page = result.scalars().first()
        assert child_page is not None

        # Get current parent ID
        parent_stmt = select(ClusterPage.id).where(
            ClusterPage.cluster_id == cluster_draft.id,
            ClusterPage.role == "parent",
        )
        parent_result = await db_session.execute(parent_stmt)
        old_parent_id = parent_result.scalar_one()

        resp = await async_client.patch(
            f"/api/v1/projects/{project.id}/clusters/{cluster_draft.id}/pages/{child_page.id}",
            json={"role": "parent"},
        )

        assert resp.status_code == 200
        assert resp.json()["role"] == "parent"

        # Verify old parent is now child — use the GET detail endpoint
        detail_resp = await async_client.get(
            f"/api/v1/projects/{project.id}/clusters/{cluster_draft.id}",
        )
        pages = detail_resp.json()["pages"]
        old_parent_data = next(p for p in pages if p["id"] == old_parent_id)
        assert old_parent_data["role"] == "child"

    async def test_update_page_invalid_page_returns_404(
        self,
        async_client: AsyncClient,
        project: Project,
        cluster_draft: KeywordCluster,
    ):
        """PATCH update page with non-existent page_id returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.patch(
            f"/api/v1/projects/{project.id}/clusters/{cluster_draft.id}/pages/{fake_id}",
            json={"is_approved": True},
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # -------------------------------------------------------------------
    # POST bulk-approve
    # -------------------------------------------------------------------

    async def test_bulk_approve_creates_crawled_pages_and_keywords(
        self,
        async_client: AsyncClient,
        async_session_factory,
        project: Project,
        cluster_draft: KeywordCluster,
    ):
        """POST approve creates CrawledPage + PageKeywords, returns bridged_count."""
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/clusters/{cluster_draft.id}/approve",
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["bridged_count"] == 2  # parent + child1 are approved

        # Use a fresh session to verify DB records (avoids greenlet issues)
        async with async_session_factory() as fresh_session:
            # Verify CrawledPage records created
            cp_stmt = select(CrawledPage).where(
                CrawledPage.source == "cluster",
                CrawledPage.project_id == project.id,
            )
            cp_result = await fresh_session.execute(cp_stmt)
            crawled_pages = list(cp_result.scalars().all())
            assert len(crawled_pages) == 2

            # Verify PageKeywords records created
            cp_ids = [cp.id for cp in crawled_pages]
            pk_stmt = select(PageKeywords).where(
                PageKeywords.crawled_page_id.in_(cp_ids)
            )
            pk_result = await fresh_session.execute(pk_stmt)
            page_keywords = list(pk_result.scalars().all())
            assert len(page_keywords) == 2

            # Verify cluster status updated
            cluster_stmt = select(KeywordCluster).where(
                KeywordCluster.id == cluster_draft.id
            )
            cluster_result = await fresh_session.execute(cluster_stmt)
            cluster = cluster_result.scalar_one()
            assert cluster.status == ClusterStatus.APPROVED.value

    async def test_bulk_approve_no_approved_pages_returns_400(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
    ):
        """POST approve with no approved pages returns 400."""
        # Create cluster with no approved pages
        cluster = KeywordCluster(
            id=str(uuid4()),
            project_id=project.id,
            seed_keyword="sandals",
            name="Sandals Cluster",
            status=ClusterStatus.SUGGESTIONS_READY.value,
            generation_metadata={},
        )
        db_session.add(cluster)
        await db_session.flush()

        page = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="sandals",
            role="parent",
            url_slug="sandals",
            is_approved=False,
        )
        db_session.add(page)
        await db_session.commit()

        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/clusters/{cluster.id}/approve",
        )

        assert resp.status_code == 400
        assert "No approved pages" in resp.json()["detail"]

    async def test_bulk_approve_already_approved_returns_409(
        self,
        async_client: AsyncClient,
        project: Project,
        cluster_approved: KeywordCluster,
    ):
        """POST approve on already-approved cluster returns 409."""
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/clusters/{cluster_approved.id}/approve",
        )

        assert resp.status_code == 409
        assert "cannot re-approve" in resp.json()["detail"]

    # -------------------------------------------------------------------
    # DELETE cluster
    # -------------------------------------------------------------------

    async def test_delete_draft_cluster_success(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        project: Project,
        cluster_draft: KeywordCluster,
    ):
        """DELETE draft cluster returns 204 and removes from DB."""
        resp = await async_client.delete(
            f"/api/v1/projects/{project.id}/clusters/{cluster_draft.id}",
        )

        assert resp.status_code == 204

        # Verify cluster is gone
        stmt = select(KeywordCluster).where(
            KeywordCluster.id == cluster_draft.id
        )
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

    async def test_delete_approved_cluster_returns_409(
        self,
        async_client: AsyncClient,
        project: Project,
        cluster_approved: KeywordCluster,
    ):
        """DELETE approved cluster returns 409."""
        resp = await async_client.delete(
            f"/api/v1/projects/{project.id}/clusters/{cluster_approved.id}",
        )

        assert resp.status_code == 409
        assert "Cannot delete" in resp.json()["detail"]

    async def test_delete_invalid_cluster_returns_404(
        self,
        async_client: AsyncClient,
        project: Project,
    ):
        """DELETE non-existent cluster returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.delete(
            f"/api/v1/projects/{project.id}/clusters/{fake_id}",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    async def test_delete_invalid_project_returns_404(
        self,
        async_client: AsyncClient,
    ):
        """DELETE with non-existent project returns 404."""
        fake_project = str(uuid4())
        fake_cluster = str(uuid4())
        resp = await async_client.delete(
            f"/api/v1/projects/{fake_project}/clusters/{fake_cluster}",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]
