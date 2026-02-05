"""Tests for Primary Keywords API endpoints.

Tests specifically for keyword generation endpoints:
- POST /api/v1/projects/{project_id}/generate-primary-keywords

Note: Other primary keyword endpoints (status, pages-with-keywords, approve, etc.)
are tested in test_projects.py.
"""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient


class TestGeneratePrimaryKeywords:
    """Tests for POST /projects/{id}/generate-primary-keywords endpoint."""

    @pytest.mark.asyncio
    async def test_generate_primary_keywords_returns_202(
        self, async_client: AsyncClient, db_session: Any
    ) -> None:
        """POST generate-primary-keywords returns 202 Accepted with task_id."""
        from app.models.crawled_page import CrawledPage
        from app.models.project import Project

        # Create project
        project = Project(
            name="Keyword Generation Test",
            site_url="https://keyword-gen.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Create completed pages (required for generation)
        pages = []
        for i in range(3):
            page = CrawledPage(
                project_id=project.id,
                normalized_url=f"https://keyword-gen.example.com/page{i}",
                status="completed",
                title=f"Page {i}",
            )
            db_session.add(page)
            pages.append(page)
        await db_session.commit()

        # Trigger keyword generation
        response = await async_client.post(
            f"/api/v1/projects/{project.id}/generate-primary-keywords",
        )

        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert "status" in data
        assert data["status"] == "Keyword generation started"
        assert data["page_count"] == "3"

    @pytest.mark.asyncio
    async def test_generate_primary_keywords_project_not_found(
        self, async_client: AsyncClient
    ) -> None:
        """POST generate-primary-keywords returns 404 for non-existent project."""
        fake_id = str(uuid.uuid4())
        response = await async_client.post(
            f"/api/v1/projects/{fake_id}/generate-primary-keywords",
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_generate_primary_keywords_no_completed_pages(
        self, async_client: AsyncClient, db_session: Any
    ) -> None:
        """POST generate-primary-keywords returns 400 when no completed pages exist."""
        from app.models.project import Project

        # Create project without any pages
        project = Project(
            name="Empty Project Test",
            site_url="https://empty-project.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/generate-primary-keywords",
        )

        assert response.status_code == 400
        assert "no completed pages" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_generate_primary_keywords_only_pending_pages(
        self, async_client: AsyncClient, db_session: Any
    ) -> None:
        """POST generate-primary-keywords returns 400 when only pending/failed pages exist."""
        from app.models.crawled_page import CrawledPage
        from app.models.project import Project

        project = Project(
            name="Pending Pages Test",
            site_url="https://pending-pages.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Create pages that are not completed
        pending_page = CrawledPage(
            project_id=project.id,
            normalized_url="https://pending-pages.example.com/pending",
            status="pending",
            title="Pending Page",
        )
        failed_page = CrawledPage(
            project_id=project.id,
            normalized_url="https://pending-pages.example.com/failed",
            status="failed",
            title="Failed Page",
        )
        db_session.add_all([pending_page, failed_page])
        await db_session.commit()

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/generate-primary-keywords",
        )

        assert response.status_code == 400
        assert "no completed pages" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_generate_primary_keywords_response_includes_page_count(
        self, async_client: AsyncClient, db_session: Any
    ) -> None:
        """POST generate-primary-keywords response includes correct page_count."""
        from app.models.crawled_page import CrawledPage
        from app.models.project import Project

        project = Project(
            name="Page Count Test",
            site_url="https://page-count.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Create 5 completed pages
        for i in range(5):
            page = CrawledPage(
                project_id=project.id,
                normalized_url=f"https://page-count.example.com/page{i}",
                status="completed",
                title=f"Page {i}",
            )
            db_session.add(page)
        await db_session.commit()

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/generate-primary-keywords",
        )

        assert response.status_code == 202
        data = response.json()
        assert data["page_count"] == "5"

    @pytest.mark.asyncio
    async def test_generate_primary_keywords_returns_valid_task_id(
        self, async_client: AsyncClient, db_session: Any
    ) -> None:
        """POST generate-primary-keywords returns a valid UUID task_id."""
        import uuid

        from app.models.crawled_page import CrawledPage
        from app.models.project import Project

        project = Project(
            name="Task ID Test",
            site_url="https://task-id.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        page = CrawledPage(
            project_id=project.id,
            normalized_url="https://task-id.example.com/products",
            status="completed",
            title="Products Page",
        )
        db_session.add(page)
        await db_session.commit()

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/generate-primary-keywords",
        )

        assert response.status_code == 202
        task_id = response.json()["task_id"]

        # Verify it's a valid UUID
        parsed_uuid = uuid.UUID(task_id)
        assert str(parsed_uuid) == task_id
