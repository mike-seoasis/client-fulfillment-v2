"""Tests for content generation API endpoints.

Tests cover:
- POST /projects/{id}/generate-content: returns 202, validates approved keywords (400),
  prevents duplicates (409)
- GET /projects/{id}/content-generation-status: returns status with per-page breakdown
- GET /projects/{id}/pages/{page_id}/content: returns generated content (404 if not generated)
- GET /projects/{id}/pages/{page_id}/prompts: returns prompt logs (empty array if none)
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_active_generations() -> None:
    """Clear the module-level active generations tracking before each test."""
    from app.api.v1.content_generation import _active_generations
    _active_generations.clear()


# ---------------------------------------------------------------------------
# POST /projects/{id}/generate-content
# ---------------------------------------------------------------------------


class TestTriggerContentGeneration:
    """Tests for POST /projects/{id}/generate-content endpoint."""

    @pytest.mark.asyncio
    async def test_returns_202_with_approved_keywords(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST generate-content returns 202 when approved keywords exist."""
        from app.models.crawled_page import CrawledPage
        from app.models.page_keywords import PageKeywords
        from app.models.project import Project

        project = Project(
            name="Content Gen Test",
            site_url="https://cg-test.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        page = CrawledPage(
            project_id=project.id,
            normalized_url="https://cg-test.example.com/page1",
            status="completed",
            title="Page 1",
        )
        db_session.add(page)
        await db_session.commit()
        await db_session.refresh(page)

        keywords = PageKeywords(
            crawled_page_id=page.id,
            primary_keyword="test keyword",
            is_approved=True,
        )
        db_session.add(keywords)
        await db_session.commit()

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/generate-content",
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert "1 pages" in data["message"]

    @pytest.mark.asyncio
    async def test_returns_400_no_approved_keywords(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST generate-content returns 400 when no approved keywords exist."""
        from app.models.crawled_page import CrawledPage
        from app.models.page_keywords import PageKeywords
        from app.models.project import Project

        project = Project(
            name="No Approved Test",
            site_url="https://no-approved.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        page = CrawledPage(
            project_id=project.id,
            normalized_url="https://no-approved.example.com/page1",
            status="completed",
            title="Page 1",
        )
        db_session.add(page)
        await db_session.commit()
        await db_session.refresh(page)

        keywords = PageKeywords(
            crawled_page_id=page.id,
            primary_keyword="test keyword",
            is_approved=False,  # Not approved
        )
        db_session.add(keywords)
        await db_session.commit()

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/generate-content",
        )

        assert response.status_code == 400
        assert "no approved keywords" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_409_duplicate_generation(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST generate-content returns 409 if generation already in progress."""
        from app.api.v1.content_generation import _active_generations
        from app.models.crawled_page import CrawledPage
        from app.models.page_keywords import PageKeywords
        from app.models.project import Project

        project = Project(
            name="Duplicate Gen Test",
            site_url="https://dupe-gen.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        page = CrawledPage(
            project_id=project.id,
            normalized_url="https://dupe-gen.example.com/page1",
            status="completed",
            title="Page 1",
        )
        db_session.add(page)
        await db_session.commit()
        await db_session.refresh(page)

        keywords = PageKeywords(
            crawled_page_id=page.id,
            primary_keyword="test keyword",
            is_approved=True,
        )
        db_session.add(keywords)
        await db_session.commit()

        # Simulate active generation
        _active_generations.add(project.id)

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/generate-content",
        )

        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_404_project_not_found(
        self, async_client: AsyncClient
    ) -> None:
        """POST generate-content returns 404 for non-existent project."""
        fake_id = str(uuid.uuid4())
        response = await async_client.post(
            f"/api/v1/projects/{fake_id}/generate-content",
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/content-generation-status
# ---------------------------------------------------------------------------


class TestContentGenerationStatus:
    """Tests for GET /projects/{id}/content-generation-status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_idle_no_pages(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns idle status when project has no approved keywords."""
        from app.models.project import Project

        project = Project(
            name="Idle Status Test",
            site_url="https://idle-status.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/content-generation-status",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["overall_status"] == "idle"
        assert data["pages_total"] == 0
        assert data["pages_completed"] == 0
        assert data["pages_failed"] == 0
        assert data["pages"] == []

    @pytest.mark.asyncio
    async def test_returns_status_with_pages(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns correct status breakdown per page."""
        from app.models.crawled_page import CrawledPage
        from app.models.page_content import ContentStatus, PageContent
        from app.models.page_keywords import PageKeywords
        from app.models.project import Project

        project = Project(
            name="Status Pages Test",
            site_url="https://status-pages.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Page 1: completed content
        page1 = CrawledPage(
            project_id=project.id,
            normalized_url="https://status-pages.example.com/p1",
            status="completed",
            title="Page 1",
        )
        db_session.add(page1)
        await db_session.commit()
        await db_session.refresh(page1)

        kw1 = PageKeywords(
            crawled_page_id=page1.id,
            primary_keyword="keyword 1",
            is_approved=True,
        )
        pc1 = PageContent(
            crawled_page_id=page1.id,
            status=ContentStatus.COMPLETE.value,
            page_title="Generated Title 1",
        )
        db_session.add_all([kw1, pc1])

        # Page 2: pending content (no PageContent yet)
        page2 = CrawledPage(
            project_id=project.id,
            normalized_url="https://status-pages.example.com/p2",
            status="completed",
            title="Page 2",
        )
        db_session.add(page2)
        await db_session.commit()
        await db_session.refresh(page2)

        kw2 = PageKeywords(
            crawled_page_id=page2.id,
            primary_keyword="keyword 2",
            is_approved=True,
        )
        db_session.add(kw2)
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/content-generation-status",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pages_total"] == 2
        assert data["pages_completed"] == 1
        assert len(data["pages"]) == 2

    @pytest.mark.asyncio
    async def test_returns_404_project_not_found(
        self, async_client: AsyncClient
    ) -> None:
        """Returns 404 for non-existent project."""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/projects/{fake_id}/content-generation-status",
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/pages/{page_id}/content
# ---------------------------------------------------------------------------


class TestGetPageContent:
    """Tests for GET /projects/{id}/pages/{page_id}/content endpoint."""

    @pytest.mark.asyncio
    async def test_returns_content(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns generated content for a page."""
        from app.models.crawled_page import CrawledPage
        from app.models.page_content import ContentStatus, PageContent
        from app.models.project import Project

        project = Project(
            name="Get Content Test",
            site_url="https://get-content.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        page = CrawledPage(
            project_id=project.id,
            normalized_url="https://get-content.example.com/p1",
            status="completed",
            title="Page 1",
        )
        db_session.add(page)
        await db_session.commit()
        await db_session.refresh(page)

        pc = PageContent(
            crawled_page_id=page.id,
            status=ContentStatus.COMPLETE.value,
            page_title="Test Title",
            meta_description="Test Meta",
            top_description="Test Top",
            bottom_description="<p>Test Bottom</p>",
            word_count=25,
        )
        db_session.add(pc)
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page_title"] == "Test Title"
        assert data["meta_description"] == "Test Meta"
        assert data["status"] == "complete"
        assert data["word_count"] == 25

    @pytest.mark.asyncio
    async def test_returns_404_no_content(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns 404 when content has not been generated."""
        from app.models.crawled_page import CrawledPage
        from app.models.project import Project

        project = Project(
            name="No Content Test",
            site_url="https://no-content.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        page = CrawledPage(
            project_id=project.id,
            normalized_url="https://no-content.example.com/p1",
            status="completed",
            title="Page 1",
        )
        db_session.add(page)
        await db_session.commit()
        await db_session.refresh(page)

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_page_not_found(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns 404 for non-existent page."""
        from app.models.project import Project

        project = Project(
            name="Missing Page Test",
            site_url="https://missing-page.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        fake_page_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/pages/{fake_page_id}/content",
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/pages/{page_id}/prompts
# ---------------------------------------------------------------------------


class TestGetPagePrompts:
    """Tests for GET /projects/{id}/pages/{page_id}/prompts endpoint."""

    @pytest.mark.asyncio
    async def test_returns_prompt_logs(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns prompt log entries for a page."""
        from app.models.crawled_page import CrawledPage
        from app.models.page_content import PageContent
        from app.models.project import Project
        from app.models.prompt_log import PromptLog

        project = Project(
            name="Prompts Test",
            site_url="https://prompts-test.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        page = CrawledPage(
            project_id=project.id,
            normalized_url="https://prompts-test.example.com/p1",
            status="completed",
            title="Page 1",
        )
        db_session.add(page)
        await db_session.commit()
        await db_session.refresh(page)

        pc = PageContent(
            crawled_page_id=page.id,
            status="complete",
        )
        db_session.add(pc)
        await db_session.commit()
        await db_session.refresh(pc)

        log1 = PromptLog(
            page_content_id=pc.id,
            step="content_writing",
            role="system",
            prompt_text="System prompt text",
            response_text="Response text",
            model="claude-sonnet-4-5-20250929",
            input_tokens=500,
            output_tokens=300,
        )
        log2 = PromptLog(
            page_content_id=pc.id,
            step="content_writing",
            role="user",
            prompt_text="User prompt text",
            response_text="Response text",
            model="claude-sonnet-4-5-20250929",
            input_tokens=500,
            output_tokens=300,
        )
        db_session.add_all([log1, log2])
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/pages/{page.id}/prompts",
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        roles = {item["role"] for item in data}
        assert "system" in roles
        assert "user" in roles

        # Verify response fields
        for item in data:
            assert "id" in item
            assert "step" in item
            assert "prompt_text" in item
            assert "response_text" in item
            assert "model" in item
            assert "input_tokens" in item
            assert "created_at" in item

    @pytest.mark.asyncio
    async def test_returns_empty_array_no_prompts(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns empty array when no prompt logs exist for the page."""
        from app.models.crawled_page import CrawledPage
        from app.models.project import Project

        project = Project(
            name="No Prompts Test",
            site_url="https://no-prompts.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        page = CrawledPage(
            project_id=project.id,
            normalized_url="https://no-prompts.example.com/p1",
            status="completed",
            title="Page 1",
        )
        db_session.add(page)
        await db_session.commit()
        await db_session.refresh(page)

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/pages/{page.id}/prompts",
        )

        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_returns_404_page_not_found(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Returns 404 for non-existent page."""
        from app.models.project import Project

        project = Project(
            name="Missing Prompts Page Test",
            site_url="https://missing-prompts.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        fake_page_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/pages/{fake_page_id}/prompts",
        )

        assert response.status_code == 404
