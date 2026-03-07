"""Tests for Bible API endpoints.

Tests CRUD operations, import/export, and edge cases
for the /api/v1/projects/{project_id}/bibles endpoints.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.vertical_bible import VerticalBible


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_URL = "/api/v1/projects"


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    """Create a test project for bible tests."""
    project = Project(
        id=str(uuid.uuid4()),
        name="Bible Test Project",
        site_url="https://example.com",
        status="active",
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.fixture
async def bible(db_session: AsyncSession, project: Project) -> VerticalBible:
    """Create a test bible."""
    bible = VerticalBible(
        id=str(uuid.uuid4()),
        project_id=project.id,
        name="Test Bible",
        slug="test-bible",
        content_md="## Domain Overview\nTest content here.",
        trigger_keywords=["test keyword", "another keyword"],
        qa_rules={
            "preferred_terms": [
                {"use": "correct term", "instead_of": "wrong term"}
            ],
            "banned_claims": [],
            "feature_attribution": [],
            "term_context_rules": [],
        },
        sort_order=0,
        is_active=True,
    )
    db_session.add(bible)
    await db_session.flush()
    return bible


# =============================================================================
# API TESTS
# =============================================================================


class TestCreateBible:
    async def test_create_bible_201(
        self, async_client: AsyncClient, project: Project
    ):
        response = await async_client.post(
            f"{BASE_URL}/{project.id}/bibles",
            json={
                "name": "New Bible",
                "content_md": "# Knowledge\nSome content",
                "trigger_keywords": ["keyword1", "keyword2"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Bible"
        assert data["slug"] == "new-bible"
        assert data["trigger_keywords"] == ["keyword1", "keyword2"]
        assert data["is_active"] is True

    async def test_create_bible_404_project(self, async_client: AsyncClient):
        fake_id = str(uuid.uuid4())
        response = await async_client.post(
            f"{BASE_URL}/{fake_id}/bibles",
            json={"name": "Test"},
        )
        assert response.status_code == 404


class TestListBibles:
    async def test_list_bibles_200(
        self,
        async_client: AsyncClient,
        project: Project,
        bible: VerticalBible,
    ):
        response = await async_client.get(
            f"{BASE_URL}/{project.id}/bibles",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    async def test_list_bibles_empty(
        self, async_client: AsyncClient, project: Project
    ):
        # Create a fresh project with no bibles
        response = await async_client.get(
            f"{BASE_URL}/{project.id}/bibles",
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)


class TestGetBible:
    async def test_get_bible_200(
        self,
        async_client: AsyncClient,
        project: Project,
        bible: VerticalBible,
    ):
        response = await async_client.get(
            f"{BASE_URL}/{project.id}/bibles/{bible.id}",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == bible.id
        assert data["name"] == "Test Bible"
        assert data["content_md"] == "## Domain Overview\nTest content here."

    async def test_get_bible_404(
        self, async_client: AsyncClient, project: Project
    ):
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"{BASE_URL}/{project.id}/bibles/{fake_id}",
        )
        assert response.status_code == 404


class TestUpdateBible:
    async def test_update_bible_200(
        self,
        async_client: AsyncClient,
        project: Project,
        bible: VerticalBible,
    ):
        response = await async_client.put(
            f"{BASE_URL}/{project.id}/bibles/{bible.id}",
            json={
                "name": "Updated Bible Name",
                "content_md": "Updated content",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Bible Name"
        assert data["content_md"] == "Updated content"

    async def test_patch_bible_200(
        self,
        async_client: AsyncClient,
        project: Project,
        bible: VerticalBible,
    ):
        response = await async_client.patch(
            f"{BASE_URL}/{project.id}/bibles/{bible.id}",
            json={"is_active": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False
        assert data["name"] == "Test Bible"  # unchanged


class TestDeleteBible:
    async def test_delete_bible_204(
        self,
        async_client: AsyncClient,
        project: Project,
        bible: VerticalBible,
    ):
        response = await async_client.delete(
            f"{BASE_URL}/{project.id}/bibles/{bible.id}",
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = await async_client.get(
            f"{BASE_URL}/{project.id}/bibles/{bible.id}",
        )
        assert get_response.status_code == 404


class TestImportExport:
    async def test_import_bible_201(
        self, async_client: AsyncClient, project: Project
    ):
        markdown = """---
name: Imported Bible
trigger_keywords:
  - import keyword
sort_order: 1
---

## Imported Content
This was imported from markdown."""

        response = await async_client.post(
            f"{BASE_URL}/{project.id}/bibles/import",
            json={"markdown": markdown},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Imported Bible"
        assert data["trigger_keywords"] == ["import keyword"]
        assert data["sort_order"] == 1
        assert "## Imported Content" in data["content_md"]

    async def test_import_bible_422_no_name(
        self, async_client: AsyncClient, project: Project
    ):
        markdown = """---
trigger_keywords:
  - keyword
---

Content without a name."""

        response = await async_client.post(
            f"{BASE_URL}/{project.id}/bibles/import",
            json={"markdown": markdown},
        )
        assert response.status_code == 422

    async def test_export_bible_200(
        self,
        async_client: AsyncClient,
        project: Project,
        bible: VerticalBible,
    ):
        response = await async_client.get(
            f"{BASE_URL}/{project.id}/bibles/{bible.id}/export",
        )
        assert response.status_code == 200
        data = response.json()
        assert "---" in data["markdown"]
        assert "Test Bible" in data["markdown"]
        assert data["filename"] == "test-bible.md"

    async def test_export_import_roundtrip(
        self,
        async_client: AsyncClient,
        project: Project,
        bible: VerticalBible,
    ):
        # Export
        export_resp = await async_client.get(
            f"{BASE_URL}/{project.id}/bibles/{bible.id}/export",
        )
        assert export_resp.status_code == 200
        exported_md = export_resp.json()["markdown"]

        # Import
        import_resp = await async_client.post(
            f"{BASE_URL}/{project.id}/bibles/import",
            json={"markdown": exported_md},
        )
        assert import_resp.status_code == 201
        imported = import_resp.json()

        assert imported["name"] == bible.name
        assert imported["trigger_keywords"] == bible.trigger_keywords
