"""Tests for Projects API endpoints.

Tests all CRUD operations on the /api/v1/projects endpoints:
- List projects (empty and with data)
- Create project (valid data, missing fields, invalid URL)
- Get project (exists, not found)
- Update project (partial update, not found)
- Delete project (exists, not found)
- Delete project with cascade S3 file deletion
"""

import uuid
from collections.abc import AsyncGenerator
from io import BytesIO
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Mock S3 Client for Cascade Delete Tests
# ---------------------------------------------------------------------------


class MockS3Client:
    """Mock S3 client for testing cascade delete behavior."""

    def __init__(self) -> None:
        self._files: dict[str, tuple[bytes, str]] = {}
        self._available = True
        self._delete_calls: list[str] = []  # Track delete calls for assertions

    @property
    def available(self) -> bool:
        return self._available

    @property
    def bucket(self) -> str:
        return "test-bucket"

    @property
    def delete_calls(self) -> list[str]:
        """Return list of S3 keys that were deleted."""
        return self._delete_calls

    async def upload_file(
        self,
        key: str,
        file_obj: Any,
        content_type: str = "application/octet-stream",
    ) -> str:
        if isinstance(file_obj, bytes):
            content = file_obj
        elif isinstance(file_obj, BytesIO):
            content = file_obj.read()
        else:
            content = file_obj.read()
        self._files[key] = (content, content_type)
        return key

    async def get_file(self, key: str) -> bytes:
        if key not in self._files:
            raise Exception(f"Object not found: {key}")
        return self._files[key][0]

    async def delete_file(self, key: str) -> bool:
        self._delete_calls.append(key)
        if key in self._files:
            del self._files[key]
        return True

    async def file_exists(self, key: str) -> bool:
        return key in self._files

    async def get_file_metadata(self, key: str) -> dict[str, Any]:
        if key not in self._files:
            raise Exception(f"Object not found: {key}")
        content, content_type = self._files[key]
        return {"content_length": len(content), "content_type": content_type}

    def clear(self) -> None:
        self._files.clear()
        self._delete_calls.clear()


@pytest.fixture
def mock_s3_for_projects() -> MockS3Client:
    """Create a mock S3 client for project tests."""
    return MockS3Client()


@pytest.fixture
async def async_client_with_s3_for_projects(
    app,
    mock_db_manager,
    mock_redis_manager,
    mock_s3_for_projects: MockS3Client,
) -> AsyncGenerator[tuple[AsyncClient, MockS3Client], None]:
    """Create async test client with mocked S3 and return both client and mock."""
    from app.core.config import get_settings
    from app.integrations.s3 import get_s3
    from tests.conftest import get_test_settings

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_s3] = lambda: mock_s3_for_projects

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac, mock_s3_for_projects

    app.dependency_overrides.clear()


class TestListProjects:
    """Tests for GET /api/v1/projects endpoint."""

    @pytest.mark.asyncio
    async def test_list_projects_returns_valid_structure(self, async_client: AsyncClient) -> None:
        """Should return valid response structure for project list."""
        response = await async_client.get("/api/v1/projects")

        assert response.status_code == 200
        data = response.json()
        # Verify structure is correct
        assert "items" in data
        assert "total" in data
        assert "offset" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_projects_with_data(self, async_client: AsyncClient) -> None:
        """Should return created projects in the list."""
        # Get initial count
        initial_response = await async_client.get("/api/v1/projects")
        initial_total = initial_response.json()["total"]

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
        # Verify at least 2 new projects were added
        assert data["total"] >= initial_total + 2

        # Verify our projects are returned
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

    @pytest.mark.asyncio
    async def test_create_project_with_additional_info(
        self, async_client: AsyncClient
    ) -> None:
        """Should create project with additional_info field."""
        response = await async_client.post(
            "/api/v1/projects",
            json={
                "name": "Project With Notes",
                "site_url": "https://notes.example.com",
                "additional_info": "Client prefers blue colors and formal tone.",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Project With Notes"
        assert data["additional_info"] == "Client prefers blue colors and formal tone."

    @pytest.mark.asyncio
    async def test_create_project_without_additional_info(
        self, async_client: AsyncClient
    ) -> None:
        """Should create project with additional_info as None when not provided."""
        response = await async_client.post(
            "/api/v1/projects",
            json={
                "name": "Project No Notes",
                "site_url": "https://nonotes.example.com",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["additional_info"] is None


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


class TestProjectResponseFields:
    """Tests for computed fields in ProjectResponse."""

    @pytest.mark.asyncio
    async def test_response_includes_brand_config_status_pending(
        self, async_client: AsyncClient
    ) -> None:
        """Should return brand_config_status as 'pending' for new project."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"name": "New Project", "site_url": "https://new.example.com"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["brand_config_status"] == "pending"

    @pytest.mark.asyncio
    async def test_response_includes_has_brand_config_false(
        self, async_client: AsyncClient
    ) -> None:
        """Should return has_brand_config as False for project without brand config."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"name": "No Brand Config", "site_url": "https://nobrand.example.com"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["has_brand_config"] is False

    @pytest.mark.asyncio
    async def test_response_includes_uploaded_files_count_zero(
        self, async_client: AsyncClient
    ) -> None:
        """Should return uploaded_files_count as 0 for project without files."""
        response = await async_client.post(
            "/api/v1/projects",
            json={"name": "No Files", "site_url": "https://nofiles.example.com"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["uploaded_files_count"] == 0

    @pytest.mark.asyncio
    async def test_response_includes_uploaded_files_count_with_files(
        self,
        async_client_with_s3_for_projects: tuple[AsyncClient, MockS3Client],
    ) -> None:
        """Should return correct uploaded_files_count after uploading files."""
        client, _mock_s3 = async_client_with_s3_for_projects

        # Create a project
        create_response = await client.post(
            "/api/v1/projects",
            json={"name": "Has Files", "site_url": "https://hasfiles.example.com"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Upload 2 files
        await client.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("doc1.txt", b"content 1", "text/plain")},
        )
        await client.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("doc2.txt", b"content 2", "text/plain")},
        )

        # Get the project and verify count
        get_response = await client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["uploaded_files_count"] == 2

    @pytest.mark.asyncio
    async def test_list_response_includes_computed_fields(
        self, async_client: AsyncClient
    ) -> None:
        """Should include all computed fields in list response."""
        # Create a project
        await async_client.post(
            "/api/v1/projects",
            json={"name": "List Test", "site_url": "https://listtest.example.com"},
        )

        # List projects
        response = await async_client.get("/api/v1/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 1

        # Verify computed fields exist in list items
        project = data["items"][0]
        assert "brand_config_status" in project
        assert "has_brand_config" in project
        assert "uploaded_files_count" in project


class TestDeleteProjectWithFiles:
    """Tests for DELETE /api/v1/projects/{id} with S3 file cascade deletion."""

    @pytest.mark.asyncio
    async def test_delete_project_cascades_s3_files(
        self,
        async_client_with_s3_for_projects: tuple[AsyncClient, MockS3Client],
    ) -> None:
        """Should delete all project files from S3 when deleting a project."""
        client, mock_s3 = async_client_with_s3_for_projects

        # Create a project
        create_response = await client.post(
            "/api/v1/projects",
            json={"name": "Project With Files", "site_url": "https://files.example.com"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Upload multiple files
        await client.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("doc1.txt", b"content 1", "text/plain")},
        )
        await client.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("doc2.txt", b"content 2", "text/plain")},
        )

        # Verify files are in S3
        assert len(mock_s3._files) == 2

        # Clear delete call tracking before delete
        mock_s3._delete_calls.clear()

        # Delete the project
        response = await client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 204

        # Verify S3 delete was called for each file
        assert len(mock_s3.delete_calls) == 2
        # Verify all files are gone from mock S3
        assert len(mock_s3._files) == 0

    @pytest.mark.asyncio
    async def test_delete_project_no_files_still_succeeds(
        self,
        async_client_with_s3_for_projects: tuple[AsyncClient, MockS3Client],
    ) -> None:
        """Should successfully delete project even when it has no files."""
        client, mock_s3 = async_client_with_s3_for_projects

        # Create a project without any files
        create_response = await client.post(
            "/api/v1/projects",
            json={"name": "Empty Project", "site_url": "https://empty.example.com"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Delete the project
        response = await client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 204

        # Verify no S3 delete calls were made
        assert len(mock_s3.delete_calls) == 0

        # Verify project is gone
        get_response = await client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_project_files_only_for_that_project(
        self,
        async_client_with_s3_for_projects: tuple[AsyncClient, MockS3Client],
    ) -> None:
        """Should only delete files belonging to the deleted project."""
        client, mock_s3 = async_client_with_s3_for_projects

        # Create two projects
        create1 = await client.post(
            "/api/v1/projects",
            json={"name": "Project One", "site_url": "https://one.example.com"},
        )
        create2 = await client.post(
            "/api/v1/projects",
            json={"name": "Project Two", "site_url": "https://two.example.com"},
        )
        assert create1.status_code == 201
        assert create2.status_code == 201
        project1_id = create1.json()["id"]
        project2_id = create2.json()["id"]

        # Upload files to both projects
        await client.post(
            f"/api/v1/projects/{project1_id}/files",
            files={"file": ("project1_file.txt", b"p1 content", "text/plain")},
        )
        await client.post(
            f"/api/v1/projects/{project2_id}/files",
            files={"file": ("project2_file.txt", b"p2 content", "text/plain")},
        )

        # Verify both files are in S3
        assert len(mock_s3._files) == 2

        # Delete project 1
        mock_s3._delete_calls.clear()
        response = await client.delete(f"/api/v1/projects/{project1_id}")
        assert response.status_code == 204

        # Verify only 1 file was deleted from S3
        assert len(mock_s3.delete_calls) == 1
        # Verify the deleted file was from project 1
        assert project1_id in mock_s3.delete_calls[0]

        # Verify project 2's file is still in S3
        assert len(mock_s3._files) == 1
        # Verify the remaining file belongs to project 2
        remaining_key = list(mock_s3._files.keys())[0]
        assert project2_id in remaining_key


# ---------------------------------------------------------------------------
# Primary Keywords Status Tests
# ---------------------------------------------------------------------------


class TestPrimaryKeywordsStatus:
    """Tests for GET /projects/{id}/primary-keywords-status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_project_not_found(
        self, async_client: AsyncClient
    ) -> None:
        """GET primary-keywords-status returns 404 for non-existent project."""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/projects/{fake_id}/primary-keywords-status"
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_status_no_keywords_yet(
        self, async_client: AsyncClient
    ) -> None:
        """GET primary-keywords-status returns pending status for new project."""
        # Create a project
        create_response = await async_client.post(
            "/api/v1/projects",
            json={
                "name": "Status Test Project",
                "site_url": "https://status-test.example.com",
            },
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Get status before any keyword generation
        response = await async_client.get(
            f"/api/v1/projects/{project_id}/primary-keywords-status"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["total"] == 0
        assert data["completed"] == 0
        assert data["failed"] == 0
        assert data["current_page"] is None

    @pytest.mark.asyncio
    async def test_get_status_with_progress(
        self, async_client: AsyncClient, db_session: Any
    ) -> None:
        """GET primary-keywords-status returns accurate progress counts."""

        from app.models.project import Project

        # Create a project with phase_status containing keyword progress
        project = Project(
            name="Keyword Progress Test",
            site_url="https://progress-test.example.com",
            phase_status={
                "onboarding": {
                    "status": "generating_keywords",
                    "keywords": {
                        "status": "generating",
                        "total": 10,
                        "completed": 5,
                        "failed": 1,
                        "current_page": "https://example.com/products/widget",
                    },
                }
            },
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Get status
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/primary-keywords-status"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "generating"
        assert data["total"] == 10
        assert data["completed"] == 5
        assert data["failed"] == 1
        assert data["current_page"] == "https://example.com/products/widget"

    @pytest.mark.asyncio
    async def test_get_status_completed(
        self, async_client: AsyncClient, db_session: Any
    ) -> None:
        """GET primary-keywords-status returns completed status correctly."""
        from app.models.project import Project

        # Create a project with completed keyword generation
        project = Project(
            name="Completed Keywords Test",
            site_url="https://completed-test.example.com",
            phase_status={
                "onboarding": {
                    "status": "keywords_complete",
                    "keywords": {
                        "status": "completed",
                        "total": 15,
                        "completed": 14,
                        "failed": 1,
                        "current_page": None,
                    },
                }
            },
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Get status
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/primary-keywords-status"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["total"] == 15
        assert data["completed"] == 14
        assert data["failed"] == 1
        assert data["current_page"] is None

    @pytest.mark.asyncio
    async def test_get_status_failed(
        self, async_client: AsyncClient, db_session: Any
    ) -> None:
        """GET primary-keywords-status returns failed status with error."""
        from app.models.project import Project

        # Create a project with failed keyword generation
        project = Project(
            name="Failed Keywords Test",
            site_url="https://failed-test.example.com",
            phase_status={
                "onboarding": {
                    "keywords": {
                        "status": "failed",
                        "total": 10,
                        "completed": 3,
                        "failed": 7,
                        "current_page": None,
                    },
                }
            },
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Get status
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/primary-keywords-status"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["total"] == 10
        assert data["completed"] == 3
        assert data["failed"] == 7

    @pytest.mark.asyncio
    async def test_get_status_failed_with_error_message(
        self, async_client: AsyncClient, db_session: Any
    ) -> None:
        """GET primary-keywords-status returns error message when failed."""
        from app.models.project import Project

        # Create a project with failed keyword generation and error message
        project = Project(
            name="Failed With Error Test",
            site_url="https://failed-error-test.example.com",
            phase_status={
                "onboarding": {
                    "keywords": {
                        "status": "failed",
                        "total": 5,
                        "completed": 0,
                        "failed": 5,
                        "current_page": None,
                        "error": "API rate limit exceeded",
                    },
                }
            },
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Get status
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/primary-keywords-status"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "API rate limit exceeded"
