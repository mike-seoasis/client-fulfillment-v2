"""Integration tests for the export CSV endpoint.

Tests the GET /api/v1/projects/{project_id}/export endpoint end-to-end,
verifying HTTP responses, CSV content, and error handling.
"""

import csv
import io
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawled_page import CrawledPage
from app.models.page_content import PageContent
from app.models.project import Project


class TestExportEndpoint:
    """Integration tests for GET /api/v1/projects/{project_id}/export."""

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
    async def approved_pages(
        self, db_session: AsyncSession, project: Project
    ) -> list[tuple[CrawledPage, PageContent]]:
        """Create two approved pages with content."""
        results = []
        for handle, title, meta, top, body in [
            (
                "running-shoes",
                "Running Shoes",
                "Best running shoes",
                "Top runners choice",
                "<p>Running body</p>",
            ),
            (
                "hiking-boots",
                "Hiking Boots",
                "Best hiking boots",
                "Top hikers choice",
                "<p>Hiking body</p>",
            ),
        ]:
            page = CrawledPage(
                id=str(uuid4()),
                project_id=project.id,
                normalized_url=f"https://store.com/collections/{handle}",
                status="completed",
                labels=[],
            )
            db_session.add(page)
            await db_session.flush()

            content = PageContent(
                id=str(uuid4()),
                crawled_page_id=page.id,
                page_title=title,
                meta_description=meta,
                top_description=top,
                bottom_description=body,
                status="complete",
                is_approved=True,
            )
            db_session.add(content)
            results.append((page, content))

        await db_session.commit()
        return results

    @pytest.fixture
    async def unapproved_page(
        self, db_session: AsyncSession, project: Project
    ) -> tuple[CrawledPage, PageContent]:
        """Create an unapproved page with content."""
        page = CrawledPage(
            id=str(uuid4()),
            project_id=project.id,
            normalized_url="https://store.com/collections/sandals",
            status="completed",
            labels=[],
        )
        db_session.add(page)
        await db_session.flush()

        content = PageContent(
            id=str(uuid4()),
            crawled_page_id=page.id,
            page_title="Sandals",
            meta_description="Best sandals",
            top_description="Top sandals",
            bottom_description="<p>Sandals body</p>",
            status="complete",
            is_approved=False,
        )
        db_session.add(content)
        await db_session.commit()
        return page, content

    def _parse_csv(self, body: str) -> list[list[str]]:
        """Parse CSV response body, stripping BOM."""
        clean = body.lstrip("\ufeff")
        reader = csv.reader(io.StringIO(clean))
        return list(reader)

    async def test_export_with_page_ids_filter(
        self,
        async_client: AsyncClient,
        project: Project,
        approved_pages: list[tuple[CrawledPage, PageContent]],
    ):
        """Export with page_ids filter returns only selected pages in CSV."""
        # Request only the first approved page
        target_page = approved_pages[0][0]
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/export",
            params={"page_ids": target_page.id},
        )

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

        rows = self._parse_csv(resp.text)
        # Header + 1 data row
        assert len(rows) == 2
        assert rows[1][0] == "running-shoes"

    async def test_export_without_page_ids_returns_all_approved(
        self,
        async_client: AsyncClient,
        project: Project,
        approved_pages: list[tuple[CrawledPage, PageContent]],
    ):
        """Export without page_ids returns all approved pages."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/export",
        )

        assert resp.status_code == 200

        rows = self._parse_csv(resp.text)
        # Header + 2 data rows
        assert len(rows) == 3
        handles = {rows[1][0], rows[2][0]}
        assert handles == {"running-shoes", "hiking-boots"}

    async def test_export_no_approved_pages_returns_400(
        self,
        async_client: AsyncClient,
        project: Project,
        unapproved_page: tuple[CrawledPage, PageContent],
    ):
        """Export with no approved pages returns HTTP 400."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/export",
        )

        assert resp.status_code == 400
        assert "No approved pages" in resp.json()["detail"]

    async def test_export_mixed_approved_unapproved_page_ids(
        self,
        async_client: AsyncClient,
        project: Project,
        approved_pages: list[tuple[CrawledPage, PageContent]],
        unapproved_page: tuple[CrawledPage, PageContent],
    ):
        """Export with mix of approved and unapproved page_ids includes only approved."""
        approved_id = approved_pages[0][0].id
        unapproved_id = unapproved_page[0].id
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/export",
            params={"page_ids": f"{approved_id},{unapproved_id}"},
        )

        assert resp.status_code == 200

        rows = self._parse_csv(resp.text)
        # Header + 1 data row (only the approved one)
        assert len(rows) == 2
        assert rows[1][0] == "running-shoes"

    async def test_export_invalid_project_id_returns_404(
        self,
        async_client: AsyncClient,
    ):
        """Export with non-existent project_id returns HTTP 404."""
        fake_id = str(uuid4())
        resp = await async_client.get(
            f"/api/v1/projects/{fake_id}/export",
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    async def test_export_csv_headers_are_matrixify_columns(
        self,
        async_client: AsyncClient,
        project: Project,
        approved_pages: list[tuple[CrawledPage, PageContent]],
    ):
        """CSV headers match the required Matrixify column names."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/export",
        )

        assert resp.status_code == 200

        rows = self._parse_csv(resp.text)
        assert rows[0] == [
            "Handle",
            "Title",
            "Body (HTML)",
            "SEO Description",
            "Metafield: custom.top_description [single_line_text_field]",
        ]

    async def test_export_content_disposition_header(
        self,
        async_client: AsyncClient,
        project: Project,
        approved_pages: list[tuple[CrawledPage, PageContent]],
    ):
        """Response includes Content-Disposition with sanitized filename."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/export",
        )

        assert resp.status_code == 200
        disposition = resp.headers["content-disposition"]
        assert "test-project-matrixify-export.csv" in disposition
