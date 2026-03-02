"""Tests for outline workflow API endpoints.

Tests cover:
- PUT /pages/{pageId}/outline: saves outline_json (200), page not found (404),
  no content record (404)
- POST /pages/{pageId}/approve-outline: sets status approved (200),
  bad status (400), page not found (404)
- POST /pages/{pageId}/generate-from-outline: accepted (202),
  not approved (400), page not found (404)
- POST /generate-content with outline_first=true: accepted (202)
- GET /content-generation-status includes outline_status
- GET /pages/{pageId}/content includes outline_json, outline_status
"""

import uuid
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


SAMPLE_OUTLINE: dict[str, Any] = {
    "page_name": "Winter Boots Collection",
    "primary_keyword": "winter boots",
    "secondary_keywords": ["snow boots"],
    "date": "2026-03-02",
    "audience": "Shoppers looking for quality winter footwear.",
    "keyword_reference": {
        "lsi_terms": [{"term": "snow boots", "target_count": 3}],
        "keyword_variations": [],
    },
    "people_also_ask": ["What are the warmest winter boots?"],
    "top_ranked_results": [],
    "page_progression": [
        {"order": 1, "question_answered": "Why choose our boots?", "label": "why-choose", "tag": "h2", "headline": "Why Choose Our Winter Boots"},
    ],
    "section_details": [
        {
            "label": "why-choose",
            "tag": "h2",
            "headline": "Why Choose Our Winter Boots",
            "purpose": "Convince visitors of product quality",
            "key_points": ["Quality materials", "Warmth"],
            "client_notes": "",
        },
    ],
}


async def _create_project_page_content(
    db_session: AsyncSession,
    *,
    with_content: bool = True,
    content_status: str = "complete",
    outline_status: str | None = None,
    outline_json: dict | None = None,
) -> tuple[str, str]:
    """Helper to create a project, crawled page, and optionally page content.

    Returns (project_id, page_id).
    """
    from app.models.crawled_page import CrawledPage
    from app.models.page_content import PageContent
    from app.models.page_keywords import PageKeywords
    from app.models.project import Project

    project = Project(
        name=f"Outline API Test {uuid.uuid4().hex[:8]}",
        site_url=f"https://outline-api-{uuid.uuid4().hex[:8]}.example.com",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    page = CrawledPage(
        project_id=project.id,
        normalized_url=f"{project.site_url}/page1",
        status="completed",
        title="Page 1",
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)

    # Add approved keyword (needed for generate-content endpoint)
    kw = PageKeywords(
        crawled_page_id=page.id,
        primary_keyword="winter boots",
        is_approved=True,
    )
    db_session.add(kw)

    if with_content:
        pc = PageContent(
            crawled_page_id=page.id,
            status=content_status,
            page_title="Test Title",
            outline_status=outline_status,
            outline_json=outline_json,
        )
        db_session.add(pc)

    await db_session.commit()
    return project.id, page.id


# ---------------------------------------------------------------------------
# PUT /pages/{pageId}/outline
# ---------------------------------------------------------------------------


class TestUpdateOutline:
    """Tests for PUT /projects/{id}/pages/{page_id}/outline endpoint."""

    @pytest.mark.asyncio
    async def test_saves_outline_json(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PUT outline returns 200 and saves outline_json on PageContent."""
        project_id, page_id = await _create_project_page_content(db_session)

        response = await async_client.put(
            f"/api/v1/projects/{project_id}/pages/{page_id}/outline",
            json={"outline_json": SAMPLE_OUTLINE},
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("outline_json") == SAMPLE_OUTLINE

    @pytest.mark.asyncio
    async def test_returns_404_page_not_found(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PUT outline returns 404 when page does not exist."""
        from app.models.project import Project

        project = Project(
            name="Missing Page Outline Test",
            site_url="https://missing-page-outline.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        fake_page_id = str(uuid.uuid4())
        response = await async_client.put(
            f"/api/v1/projects/{project.id}/pages/{fake_page_id}/outline",
            json={"outline_json": SAMPLE_OUTLINE},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_no_content_record(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PUT outline returns 404 when no PageContent record exists."""
        project_id, page_id = await _create_project_page_content(
            db_session, with_content=False
        )

        response = await async_client.put(
            f"/api/v1/projects/{project_id}/pages/{page_id}/outline",
            json={"outline_json": SAMPLE_OUTLINE},
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /pages/{pageId}/approve-outline
# ---------------------------------------------------------------------------


class TestApproveOutline:
    """Tests for POST /projects/{id}/pages/{page_id}/approve-outline endpoint."""

    @pytest.mark.asyncio
    async def test_sets_outline_status_approved(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST approve-outline sets outline_status to 'approved'."""
        project_id, page_id = await _create_project_page_content(
            db_session,
            outline_status="draft",
            outline_json=SAMPLE_OUTLINE,
        )

        response = await async_client.post(
            f"/api/v1/projects/{project_id}/pages/{page_id}/approve-outline",
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("outline_status") == "approved"

    @pytest.mark.asyncio
    async def test_returns_400_when_not_draft(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST approve-outline returns 400 if outline_status is not 'draft'."""
        project_id, page_id = await _create_project_page_content(
            db_session,
            outline_status="approved",
            outline_json=SAMPLE_OUTLINE,
        )

        response = await async_client.post(
            f"/api/v1/projects/{project_id}/pages/{page_id}/approve-outline",
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_404_page_not_found(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST approve-outline returns 404 for non-existent page."""
        from app.models.project import Project

        project = Project(
            name="Missing Approve Test",
            site_url="https://missing-approve.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        fake_page_id = str(uuid.uuid4())
        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{fake_page_id}/approve-outline",
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_when_outline_status_is_none(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST approve-outline returns 400 when outline_status is None (no outline)."""
        project_id, page_id = await _create_project_page_content(
            db_session,
            outline_status=None,
            outline_json=None,
        )

        response = await async_client.post(
            f"/api/v1/projects/{project_id}/pages/{page_id}/approve-outline",
        )

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /pages/{pageId}/generate-from-outline
# ---------------------------------------------------------------------------


class TestGenerateFromOutline:
    """Tests for POST /projects/{id}/pages/{page_id}/generate-from-outline endpoint."""

    @pytest.mark.asyncio
    async def test_returns_202_when_approved(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST generate-from-outline returns 202 when outline_status is 'approved'."""
        from unittest.mock import patch

        project_id, page_id = await _create_project_page_content(
            db_session,
            outline_status="approved",
            outline_json=SAMPLE_OUTLINE,
        )

        with patch(
            "app.api.v1.content_generation._run_generate_from_outline_background",
            return_value=None,
        ):
            response = await async_client.post(
                f"/api/v1/projects/{project_id}/pages/{page_id}/generate-from-outline",
            )

        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_returns_400_when_not_approved(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST generate-from-outline returns 400 if outline_status is not 'approved'."""
        project_id, page_id = await _create_project_page_content(
            db_session,
            outline_status="draft",
            outline_json=SAMPLE_OUTLINE,
        )

        response = await async_client.post(
            f"/api/v1/projects/{project_id}/pages/{page_id}/generate-from-outline",
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_400_when_outline_status_is_none(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST generate-from-outline returns 400 when outline_status is None."""
        project_id, page_id = await _create_project_page_content(
            db_session,
            outline_status=None,
            outline_json=None,
        )

        response = await async_client.post(
            f"/api/v1/projects/{project_id}/pages/{page_id}/generate-from-outline",
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_returns_404_page_not_found(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST generate-from-outline returns 404 for non-existent page."""
        from app.models.project import Project

        project = Project(
            name="Missing Gen Outline Test",
            site_url="https://missing-gen-outline.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        fake_page_id = str(uuid.uuid4())
        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{fake_page_id}/generate-from-outline",
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /generate-content with outline_first=true
# ---------------------------------------------------------------------------


class TestGenerateContentOutlineFirst:
    """Tests for POST /generate-content with outline_first query param."""

    @pytest.mark.asyncio
    async def test_returns_202_with_outline_first(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST generate-content with outline_first=true returns 202.

        We patch the background task runner to avoid it trying to create
        real DB sessions (which hang in the test environment).
        """
        from unittest.mock import patch

        project_id, page_id = await _create_project_page_content(
            db_session, with_content=False
        )

        with patch(
            "app.api.v1.content_generation._run_generation_background",
            return_value=None,
        ):
            response = await async_client.post(
                f"/api/v1/projects/{project_id}/generate-content",
                params={"outline_first": "true"},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_returns_409_when_already_generating(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST generate-content with outline_first=true returns 409 if already running."""
        from unittest.mock import patch

        from app.api.v1.content_generation import _active_generations

        project_id, page_id = await _create_project_page_content(
            db_session, with_content=False
        )

        # Simulate an active generation
        _active_generations.add(project_id)

        try:
            response = await async_client.post(
                f"/api/v1/projects/{project_id}/generate-content",
                params={"outline_first": "true"},
            )

            assert response.status_code == 409
        finally:
            _active_generations.discard(project_id)


# ---------------------------------------------------------------------------
# GET /content-generation-status includes outline_status
# ---------------------------------------------------------------------------


class TestContentGenerationStatusOutline:
    """Tests for outline_status in content generation status endpoint."""

    @pytest.mark.asyncio
    async def test_includes_outline_status_in_page_items(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET content-generation-status includes outline_status per page."""
        project_id, page_id = await _create_project_page_content(
            db_session,
            outline_status="draft",
            outline_json=SAMPLE_OUTLINE,
        )

        response = await async_client.get(
            f"/api/v1/projects/{project_id}/content-generation-status",
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["pages"]) >= 1
        page_item = data["pages"][0]
        assert page_item.get("outline_status") == "draft"


# ---------------------------------------------------------------------------
# GET /pages/{pageId}/content includes outline fields
# ---------------------------------------------------------------------------


class TestGetPageContentOutlineFields:
    """Tests for outline fields in page content response."""

    @pytest.mark.asyncio
    async def test_includes_outline_json_and_status(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET page content includes outline_json and outline_status."""
        project_id, page_id = await _create_project_page_content(
            db_session,
            outline_status="approved",
            outline_json=SAMPLE_OUTLINE,
        )

        response = await async_client.get(
            f"/api/v1/projects/{project_id}/pages/{page_id}/content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("outline_json") == SAMPLE_OUTLINE
        assert data.get("outline_status") == "approved"

    @pytest.mark.asyncio
    async def test_outline_fields_null_when_not_set(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET page content returns null outline fields when not set."""
        project_id, page_id = await _create_project_page_content(db_session)

        response = await async_client.get(
            f"/api/v1/projects/{project_id}/pages/{page_id}/content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("outline_json") is None
        assert data.get("outline_status") is None
