"""Tests for Projects API endpoints.

Tests all CRUD operations on the /api/v1/projects endpoints:
- List projects (empty and with data)
- Create project (valid data, missing fields, invalid URL)
- Get project (exists, not found)
- Update project (partial update, not found)
- Delete project (exists, not found)
"""

import uuid

import pytest
from httpx import AsyncClient


class TestListProjects:
    """Tests for GET /api/v1/projects endpoint."""

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, async_client: AsyncClient) -> None:
        """Should return empty list when no projects exist."""
        response = await async_client.get("/api/v1/projects")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_projects_with_data(self, async_client: AsyncClient) -> None:
        """Should return all created projects."""
        # Create test projects
        project1 = await async_client.post(
            "/api/v1/projects",
            json={"name": "Project Alpha", "site_url": "https://alpha.example.com"},
        )
        project2 = await async_client.post(
            "/api/v1/projects",
            json={"name": "Project Beta", "site_url": "https://beta.example.com"},
        )
        assert project1.status_code == 201
        assert project2.status_code == 201

        # List projects
        response = await async_client.get("/api/v1/projects")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        # Verify projects are returned (most recently updated first)
        names = [p["name"] for p in data["items"]]
        assert "Project Alpha" in names
        assert "Project Beta" in names


class TestCreateProject:
    """Tests for POST /api/v1/projects endpoint."""

    @pytest.mark.asyncio
    async def test_create_project_valid(self, async_client: AsyncClient) -> None:
        """Should create project with valid data."""
        response = await async_client.post(
            "/api/v1/projects",
            json={
                "name": "Test Project",
                "site_url": "https://example.com",
                "client_id": "client-123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Project"
        assert data["site_url"] == "https://example.com/"  # Normalized with trailing slash
        assert data["client_id"] == "client-123"
        assert data["status"] == "active"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_create_project_minimal(self, async_client: AsyncClient) -> None:
        """Should create project with only required fields."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"name": "Minimal Project", "site_url": "https://minimal.com"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Project"
        assert data["client_id"] is None
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_project_missing_name(self, async_client: AsyncClient) -> None:
        """Should return 422 when name is missing."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"site_url": "https://example.com"},
        )

        assert response.status_code == 422
        data = response.json()
        # App uses custom error format with error/code/request_id
        assert "error" in data
        assert "name" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_create_project_missing_site_url(
        self, async_client: AsyncClient
    ) -> None:
        """Should return 422 when site_url is missing."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"name": "No URL Project"},
        )

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert "site_url" in data["error"]

    @pytest.mark.asyncio
    async def test_create_project_invalid_url(self, async_client: AsyncClient) -> None:
        """Should return 422 when site_url is invalid."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"name": "Invalid URL Project", "site_url": "not-a-valid-url"},
        )

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert "url" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_create_project_empty_name(self, async_client: AsyncClient) -> None:
        """Should return 422 when name is empty string."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"name": "", "site_url": "https://example.com"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_whitespace_name(
        self, async_client: AsyncClient
    ) -> None:
        """Should return 422 when name is only whitespace."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"name": "   ", "site_url": "https://example.com"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_with_status(self, async_client: AsyncClient) -> None:
        """Should create project with custom status."""
        response = await async_client.post(
            "/api/v1/projects",
            json={
                "name": "On Hold Project",
                "site_url": "https://onhold.com",
                "status": "on_hold",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "on_hold"

    @pytest.mark.asyncio
    async def test_create_project_invalid_status(
        self, async_client: AsyncClient
    ) -> None:
        """Should return 422 when status is invalid."""
        response = await async_client.post(
            "/api/v1/projects",
            json={
                "name": "Bad Status Project",
                "site_url": "https://badstatus.com",
                "status": "invalid_status",
            },
        )

        assert response.status_code == 422


class TestGetProject:
    """Tests for GET /api/v1/projects/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_project_exists(self, async_client: AsyncClient) -> None:
        """Should return project when it exists."""
        # Create a project
        create_response = await async_client.post(
            "/api/v1/projects",
            json={"name": "Retrievable Project", "site_url": "https://retrieve.com"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Get the project
        response = await async_client.get(f"/api/v1/projects/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "Retrievable Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, async_client: AsyncClient) -> None:
        """Should return 404 when project does not exist."""
        non_existent_id = str(uuid.uuid4())
        response = await async_client.get(f"/api/v1/projects/{non_existent_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestUpdateProject:
    """Tests for PATCH /api/v1/projects/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_project_partial(self, async_client: AsyncClient) -> None:
        """Should update only provided fields."""
        # Create a project
        create_response = await async_client.post(
            "/api/v1/projects",
            json={
                "name": "Original Name",
                "site_url": "https://original.com",
                "status": "active",
            },
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]
        original_url = create_response.json()["site_url"]

        # Update only the name
        response = await async_client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["site_url"] == original_url  # Unchanged
        assert data["status"] == "active"  # Unchanged

    @pytest.mark.asyncio
    async def test_update_project_site_url(self, async_client: AsyncClient) -> None:
        """Should update site_url."""
        # Create a project
        create_response = await async_client.post(
            "/api/v1/projects",
            json={"name": "URL Update Test", "site_url": "https://old.com"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Update the site_url
        response = await async_client.patch(
            f"/api/v1/projects/{project_id}",
            json={"site_url": "https://new.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "new.com" in data["site_url"]

    @pytest.mark.asyncio
    async def test_update_project_status(self, async_client: AsyncClient) -> None:
        """Should update status."""
        # Create a project
        create_response = await async_client.post(
            "/api/v1/projects",
            json={"name": "Status Update", "site_url": "https://status.com"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Update status
        response = await async_client.patch(
            f"/api/v1/projects/{project_id}",
            json={"status": "completed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_update_project_not_found(self, async_client: AsyncClient) -> None:
        """Should return 404 when project does not exist."""
        non_existent_id = str(uuid.uuid4())
        response = await async_client.patch(
            f"/api/v1/projects/{non_existent_id}",
            json={"name": "Doesn't Matter"},
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_update_project_invalid_status(
        self, async_client: AsyncClient
    ) -> None:
        """Should return 422 when status is invalid."""
        # Create a project
        create_response = await async_client.post(
            "/api/v1/projects",
            json={"name": "Invalid Status Update", "site_url": "https://invalid.com"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Try to update with invalid status
        response = await async_client.patch(
            f"/api/v1/projects/{project_id}",
            json={"status": "not_a_real_status"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_update_project_invalid_url(self, async_client: AsyncClient) -> None:
        """Should return 422 when site_url is invalid."""
        # Create a project
        create_response = await async_client.post(
            "/api/v1/projects",
            json={"name": "Invalid URL Update", "site_url": "https://valid.com"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Try to update with invalid URL
        response = await async_client.patch(
            f"/api/v1/projects/{project_id}",
            json={"site_url": "not-a-url"},
        )

        assert response.status_code == 422


class TestDeleteProject:
    """Tests for DELETE /api/v1/projects/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_project_exists(self, async_client: AsyncClient) -> None:
        """Should delete project and return 204."""
        # Create a project
        create_response = await async_client.post(
            "/api/v1/projects",
            json={"name": "To Be Deleted", "site_url": "https://delete.com"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Delete the project
        response = await async_client.delete(f"/api/v1/projects/{project_id}")

        assert response.status_code == 204
        assert response.content == b""  # No content

        # Verify project is gone
        get_response = await async_client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, async_client: AsyncClient) -> None:
        """Should return 404 when project does not exist."""
        non_existent_id = str(uuid.uuid4())
        response = await async_client.delete(f"/api/v1/projects/{non_existent_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
