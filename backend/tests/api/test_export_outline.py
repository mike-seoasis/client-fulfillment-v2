"""Tests for outline export to Google Doc endpoint.

Tests cover:
- POST /projects/{id}/pages/{page_id}/export-outline: creates doc, returns URL
- Idempotent: returns existing URL without re-exporting
- 400 when no outline_json
- 404 when page or content not found
- 500 when Google API fails
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_project(db: AsyncSession, name: str = "Test Project"):
    from app.models.project import Project

    project = Project(name=name, site_url=f"https://{name.lower().replace(' ', '-')}.example.com")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def _create_page(db: AsyncSession, project_id: str, url_suffix: str = "/page1"):
    from app.models.crawled_page import CrawledPage

    page = CrawledPage(
        project_id=project_id,
        normalized_url=f"https://test.example.com{url_suffix}",
        status="completed",
        title=f"Page {url_suffix}",
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


async def _create_keywords(db: AsyncSession, page_id: str, keyword: str = "test keyword"):
    from app.models.page_keywords import PageKeywords

    kw = PageKeywords(
        crawled_page_id=page_id,
        primary_keyword=keyword,
        is_approved=True,
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw


async def _create_content(
    db: AsyncSession,
    page_id: str,
    *,
    outline_json=None,
    outline_status: str | None = "draft",
    google_doc_url: str | None = None,
):
    from app.models.page_content import PageContent

    content = PageContent(
        crawled_page_id=page_id,
        status="complete",
        page_title="Test Title",
        outline_json=outline_json,
        outline_status=outline_status,
        google_doc_url=google_doc_url,
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


SAMPLE_OUTLINE = {
    "page_name": "Test Page",
    "audience": "SEO professionals",
    "sections": [
        {
            "headline": "Introduction",
            "purpose": "Set the scene",
            "key_points": ["Point 1", "Point 2"],
            "client_notes": "Keep it short",
        }
    ],
    "keywords": ["seo", "ranking"],
    "people_also_ask": ["What is SEO?"],
    "competitors": ["https://example.com/competitor"],
}

MOCK_DOC_URL = "https://docs.google.com/document/d/abc123/edit"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExportOutline:
    """Tests for POST /{project_id}/pages/{page_id}/export-outline."""

    @pytest.mark.asyncio
    async def test_export_success(self, async_client: AsyncClient, db_session: AsyncSession):
        """Exporting an outline creates a doc and returns the URL."""
        project = await _create_project(db_session)
        page = await _create_page(db_session, project.id)
        await _create_keywords(db_session, page.id, "test keyword")
        await _create_content(db_session, page.id, outline_json=SAMPLE_OUTLINE)

        with patch("app.services.outline_export.export_outline_to_google") as mock_export:
            from app.services.outline_export import ExportResult

            mock_export.return_value = ExportResult(
                success=True, google_doc_url=MOCK_DOC_URL
            )

            resp = await async_client.post(
                f"/api/v1/projects/{project.id}/pages/{page.id}/export-outline"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["google_doc_url"] == MOCK_DOC_URL

    @pytest.mark.asyncio
    async def test_export_idempotent(self, async_client: AsyncClient, db_session: AsyncSession):
        """If google_doc_url already exists, return it without re-exporting."""
        project = await _create_project(db_session)
        page = await _create_page(db_session, project.id)
        await _create_content(
            db_session,
            page.id,
            outline_json=SAMPLE_OUTLINE,
            google_doc_url=MOCK_DOC_URL,
        )

        # Should NOT call the export service
        with patch("app.services.outline_export.export_outline_to_google") as mock_export:
            resp = await async_client.post(
                f"/api/v1/projects/{project.id}/pages/{page.id}/export-outline"
            )
            mock_export.assert_not_called()

        assert resp.status_code == 200
        data = resp.json()
        assert data["google_doc_url"] == MOCK_DOC_URL

    @pytest.mark.asyncio
    async def test_export_no_outline_returns_400(self, async_client: AsyncClient, db_session: AsyncSession):
        """Returns 400 when no outline_json exists."""
        project = await _create_project(db_session)
        page = await _create_page(db_session, project.id)
        await _create_content(db_session, page.id, outline_json=None, outline_status=None)

        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/export-outline"
        )

        assert resp.status_code == 400
        assert "outline" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_export_no_content_returns_404(self, async_client: AsyncClient, db_session: AsyncSession):
        """Returns 404 when page has no content record."""
        project = await _create_project(db_session)
        page = await _create_page(db_session, project.id)

        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/export-outline"
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_missing_page_returns_404(self, async_client: AsyncClient, db_session: AsyncSession):
        """Returns 404 for a non-existent page."""
        project = await _create_project(db_session)

        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/00000000-0000-0000-0000-000000000000/export-outline"
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_export_failure_returns_500(self, async_client: AsyncClient, db_session: AsyncSession):
        """Returns 500 when the Google API export fails."""
        project = await _create_project(db_session)
        page = await _create_page(db_session, project.id)
        await _create_keywords(db_session, page.id)
        await _create_content(db_session, page.id, outline_json=SAMPLE_OUTLINE)

        with patch("app.services.outline_export.export_outline_to_google") as mock_export:
            from app.services.outline_export import ExportResult

            mock_export.return_value = ExportResult(
                success=False, error="Google API error"
            )

            resp = await async_client.post(
                f"/api/v1/projects/{project.id}/pages/{page.id}/export-outline"
            )

        assert resp.status_code == 500
        assert "Google API error" in resp.json()["detail"]
