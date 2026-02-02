"""Integration tests for projects API endpoints.

Tests cover:
- CRUD operations for projects
- Validation error handling
- Not found error handling
- Request logging and request_id headers
- Structured error responses with proper codes

ERROR LOGGING REQUIREMENTS (verified by tests):
- All requests include X-Request-ID header in response
- Validation errors return 422 with structured response
- Not found errors return 404 with structured response
- Successful operations return proper status codes
"""

import uuid

from fastapi.testclient import TestClient


class TestListProjects:
    """Tests for GET /api/v1/projects endpoint."""

    def test_list_projects_returns_empty_list(self, client: TestClient) -> None:
        """Test listing projects when none exist."""
        response = client.get("/api/v1/projects")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_projects_includes_request_id(self, client: TestClient) -> None:
        """Test list projects response includes X-Request-ID header."""
        response = client.get("/api/v1/projects")

        assert "X-Request-ID" in response.headers

    def test_list_projects_with_pagination(self, client: TestClient) -> None:
        """Test listing projects with custom limit and offset."""
        response = client.get("/api/v1/projects?limit=10&offset=5")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5

    def test_list_projects_invalid_limit(self, client: TestClient) -> None:
        """Test listing projects with invalid limit returns validation error."""
        response = client.get("/api/v1/projects?limit=0")

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert "code" in data
        assert data["code"] == "VALIDATION_ERROR"
        assert "request_id" in data

    def test_list_projects_limit_too_large(self, client: TestClient) -> None:
        """Test listing projects with limit exceeding maximum."""
        response = client.get("/api/v1/projects?limit=1001")

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"


class TestCreateProject:
    """Tests for POST /api/v1/projects endpoint."""

    def test_create_project_success(self, client: TestClient) -> None:
        """Test creating a project successfully."""
        project_data = {
            "name": "Test Project",
            "client_id": "test-client-123",
        }

        response = client.post("/api/v1/projects", json=project_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Project"
        assert data["client_id"] == "test-client-123"
        assert data["status"] == "active"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_project_with_status(self, client: TestClient) -> None:
        """Test creating a project with custom status."""
        project_data = {
            "name": "Project with Status",
            "client_id": "test-client-456",
            "status": "on_hold",
        }

        response = client.post("/api/v1/projects", json=project_data)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "on_hold"

    def test_create_project_missing_name(self, client: TestClient) -> None:
        """Test creating project without name returns validation error."""
        project_data = {
            "client_id": "test-client",
        }

        response = client.post("/api/v1/projects", json=project_data)

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["code"] == "VALIDATION_ERROR"
        assert "request_id" in data

    def test_create_project_empty_name(self, client: TestClient) -> None:
        """Test creating project with empty name returns validation error."""
        project_data = {
            "name": "",
            "client_id": "test-client",
        }

        response = client.post("/api/v1/projects", json=project_data)

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"

    def test_create_project_invalid_status(self, client: TestClient) -> None:
        """Test creating project with invalid status returns validation error."""
        project_data = {
            "name": "Test Project",
            "client_id": "test-client",
            "status": "invalid_status",
        }

        response = client.post("/api/v1/projects", json=project_data)

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"

    def test_create_project_includes_request_id(self, client: TestClient) -> None:
        """Test create project response includes X-Request-ID header."""
        project_data = {
            "name": "Test Project",
            "client_id": "test-client",
        }

        response = client.post("/api/v1/projects", json=project_data)

        assert "X-Request-ID" in response.headers


class TestGetProject:
    """Tests for GET /api/v1/projects/{project_id} endpoint."""

    def test_get_project_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent project returns 404."""
        fake_id = str(uuid.uuid4())

        response = client.get(f"/api/v1/projects/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["code"] == "NOT_FOUND"
        assert "request_id" in data

    def test_get_project_invalid_uuid(self, client: TestClient) -> None:
        """Test getting project with invalid UUID returns validation error."""
        response = client.get("/api/v1/projects/not-a-uuid")

        # Invalid UUID format should return 400 or 404
        assert response.status_code in (400, 404)
        data = response.json()
        assert "error" in data
        assert "request_id" in data

    def test_get_project_success(self, client: TestClient) -> None:
        """Test getting an existing project."""
        # First create a project
        create_response = client.post(
            "/api/v1/projects",
            json={"name": "Get Test Project", "client_id": "get-test-client"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Then get it
        response = client.get(f"/api/v1/projects/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["name"] == "Get Test Project"


class TestUpdateProject:
    """Tests for PUT /api/v1/projects/{project_id} endpoint."""

    def test_update_project_not_found(self, client: TestClient) -> None:
        """Test updating a non-existent project returns 404."""
        fake_id = str(uuid.uuid4())

        response = client.put(
            f"/api/v1/projects/{fake_id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "NOT_FOUND"

    def test_update_project_success(self, client: TestClient) -> None:
        """Test updating an existing project."""
        # First create a project
        create_response = client.post(
            "/api/v1/projects",
            json={"name": "Original Name", "client_id": "update-test-client"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Then update it
        response = client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    def test_update_project_invalid_status(self, client: TestClient) -> None:
        """Test updating project with invalid status returns validation error."""
        # First create a project
        create_response = client.post(
            "/api/v1/projects",
            json={"name": "Status Test", "client_id": "status-test-client"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Try to update with invalid status
        response = client.put(
            f"/api/v1/projects/{project_id}",
            json={"status": "bad_status"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"


class TestDeleteProject:
    """Tests for DELETE /api/v1/projects/{project_id} endpoint."""

    def test_delete_project_not_found(self, client: TestClient) -> None:
        """Test deleting a non-existent project returns 404."""
        fake_id = str(uuid.uuid4())

        response = client.delete(f"/api/v1/projects/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "NOT_FOUND"

    def test_delete_project_success(self, client: TestClient) -> None:
        """Test deleting an existing project."""
        # First create a project
        create_response = client.post(
            "/api/v1/projects",
            json={"name": "Delete Test", "client_id": "delete-test-client"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        # Then delete it
        response = client.delete(f"/api/v1/projects/{project_id}")

        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/v1/projects/{project_id}")
        assert get_response.status_code == 404


class TestUpdateProjectPhase:
    """Tests for PATCH /api/v1/projects/{project_id}/phases endpoint."""

    def test_update_phase_not_found(self, client: TestClient) -> None:
        """Test updating phase of non-existent project returns 404."""
        fake_id = str(uuid.uuid4())

        response = client.patch(
            f"/api/v1/projects/{fake_id}/phases",
            json={"phase": "discovery", "status": "in_progress"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "NOT_FOUND"

    def test_update_phase_invalid_phase_name(self, client: TestClient) -> None:
        """Test updating with invalid phase name returns validation error."""
        # First create a project
        create_response = client.post(
            "/api/v1/projects",
            json={"name": "Phase Test", "client_id": "phase-test-client"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/projects/{project_id}/phases",
            json={"phase": "invalid_phase", "status": "in_progress"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"

    def test_update_phase_invalid_status(self, client: TestClient) -> None:
        """Test updating with invalid phase status returns validation error."""
        # First create a project
        create_response = client.post(
            "/api/v1/projects",
            json={"name": "Phase Test 2", "client_id": "phase-test-client-2"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/projects/{project_id}/phases",
            json={"phase": "discovery", "status": "bad_status"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["code"] == "VALIDATION_ERROR"

    def test_update_phase_success(self, client: TestClient) -> None:
        """Test updating project phase successfully."""
        # First create a project
        create_response = client.post(
            "/api/v1/projects",
            json={"name": "Phase Success Test", "client_id": "phase-success-client"},
        )
        assert create_response.status_code == 201
        project_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/projects/{project_id}/phases",
            json={"phase": "discovery", "status": "in_progress"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["phase_status"]["discovery"]["status"] == "in_progress"
