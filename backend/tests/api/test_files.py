"""Tests for Files API endpoints.

Tests all file upload operations on the /api/v1/projects/{project_id}/files endpoints:
- Upload files (PDF, DOCX, TXT)
- Upload validation (size, content type, project exists)
- List files for project
- Delete file
"""

import uuid
from collections.abc import AsyncGenerator
from io import BytesIO
from typing import Any

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Mock S3 Client Fixture
# ---------------------------------------------------------------------------


class S3NotFoundError(Exception):
    """Mock S3 not found error for testing."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        key: str | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.key = key


class MockS3Client:
    """Mock S3 client for testing.

    Stores uploaded files in memory and provides basic CRUD operations.
    """

    def __init__(self) -> None:
        self._files: dict[str, tuple[bytes, str]] = {}  # key -> (content, content_type)
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    @property
    def bucket(self) -> str:
        return "test-bucket"

    async def upload_file(
        self,
        key: str,
        file_obj: Any,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to mock storage."""
        if isinstance(file_obj, bytes):
            content = file_obj
        elif isinstance(file_obj, BytesIO):
            content = file_obj.read()
        else:
            content = file_obj.read()

        self._files[key] = (content, content_type)
        return key

    async def get_file(self, key: str) -> bytes:
        """Get a file from mock storage."""
        if key not in self._files:
            raise S3NotFoundError(
                f"Object not found: {key}", operation="get_file", key=key
            )
        return self._files[key][0]

    async def delete_file(self, key: str) -> bool:
        """Delete a file from mock storage."""
        if key in self._files:
            del self._files[key]
        return True

    async def file_exists(self, key: str) -> bool:
        """Check if a file exists in mock storage."""
        return key in self._files

    async def get_file_metadata(self, key: str) -> dict[str, Any]:
        """Get metadata for a file in mock storage."""
        if key not in self._files:
            raise S3NotFoundError(
                f"Object not found: {key}", operation="get_metadata", key=key
            )
        content, content_type = self._files[key]
        return {
            "content_length": len(content),
            "content_type": content_type,
            "last_modified": None,
            "etag": None,
        }

    def clear(self) -> None:
        """Clear all stored files."""
        self._files.clear()


@pytest.fixture
def mock_s3() -> MockS3Client:
    """Create a mock S3 client."""
    return MockS3Client()


@pytest.fixture
async def async_client_with_s3(
    app,
    mock_db_manager,
    mock_redis_manager,
    mock_s3: MockS3Client,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with mocked S3."""
    from app.core.config import get_settings
    from app.integrations.s3 import get_s3
    from tests.conftest import get_test_settings

    # Override dependencies
    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_s3] = lambda: mock_s3

    from httpx import ASGITransport
    from httpx import AsyncClient as HttpxAsyncClient

    async with HttpxAsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


async def create_test_project(client: AsyncClient) -> str:
    """Create a test project and return its ID."""
    response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Test Project for Files",
            "site_url": "https://test-files.example.com",
        },
    )
    assert response.status_code == 201
    project_id: str = response.json()["id"]
    return project_id


def create_test_pdf() -> bytes:
    """Create minimal PDF file content for testing."""
    # Minimal valid PDF structure
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [] /Count 0 >>
endobj
xref
0 3
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
trailer
<< /Size 3 /Root 1 0 R >>
startxref
107
%%EOF"""


def create_test_docx() -> bytes:
    """Create minimal DOCX file content for testing.

    DOCX is a ZIP archive containing XML files.
    """
    import zipfile

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Minimal content types
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        # Minimal rels
        zf.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
        )
        # Minimal document
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Test content</w:t></w:r></w:p></w:body>"
            "</w:document>",
        )
    return buffer.getvalue()


def create_test_txt() -> bytes:
    """Create simple TXT file content for testing."""
    return b"This is a test text file.\nIt has multiple lines.\n"


# ---------------------------------------------------------------------------
# Upload File Tests
# ---------------------------------------------------------------------------


class TestUploadFile:
    """Tests for POST /api/v1/projects/{project_id}/files endpoint."""

    @pytest.mark.asyncio
    async def test_upload_pdf_file(self, async_client_with_s3: AsyncClient) -> None:
        """Should upload a PDF file successfully."""
        project_id = await create_test_project(async_client_with_s3)
        pdf_content = create_test_pdf()

        response = await async_client_with_s3.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("test.pdf", pdf_content, "application/pdf")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.pdf"
        assert data["content_type"] == "application/pdf"
        assert data["file_size"] == len(pdf_content)
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_upload_docx_file(self, async_client_with_s3: AsyncClient) -> None:
        """Should upload a DOCX file successfully."""
        project_id = await create_test_project(async_client_with_s3)
        docx_content = create_test_docx()

        response = await async_client_with_s3.post(
            f"/api/v1/projects/{project_id}/files",
            files={
                "file": (
                    "test.docx",
                    docx_content,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.docx"
        assert (
            data["content_type"]
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert data["file_size"] == len(docx_content)

    @pytest.mark.asyncio
    async def test_upload_txt_file(self, async_client_with_s3: AsyncClient) -> None:
        """Should upload a TXT file successfully."""
        project_id = await create_test_project(async_client_with_s3)
        txt_content = create_test_txt()

        response = await async_client_with_s3.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("test.txt", txt_content, "text/plain")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.txt"
        assert data["content_type"] == "text/plain"
        assert data["file_size"] == len(txt_content)

    @pytest.mark.asyncio
    async def test_upload_to_nonexistent_project(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should return 404 when uploading to non-existent project."""
        non_existent_id = str(uuid.uuid4())
        txt_content = create_test_txt()

        response = await async_client_with_s3.post(
            f"/api/v1/projects/{non_existent_id}/files",
            files={"file": ("test.txt", txt_content, "text/plain")},
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_upload_oversized_file(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should return 413 when file exceeds maximum size (10MB)."""
        project_id = await create_test_project(async_client_with_s3)
        # Create content larger than 10MB
        oversized_content = b"x" * (10 * 1024 * 1024 + 1)

        response = await async_client_with_s3.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("large.txt", oversized_content, "text/plain")},
        )

        assert response.status_code == 413
        data = response.json()
        assert "detail" in data
        assert "size" in data["detail"].lower() or "10" in data["detail"]

    @pytest.mark.asyncio
    async def test_upload_unsupported_type(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should return 415 when file type is not supported."""
        project_id = await create_test_project(async_client_with_s3)
        # Try to upload an image file (not in allowed types)
        image_content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        response = await async_client_with_s3.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("test.png", image_content, "image/png")},
        )

        assert response.status_code == 415
        data = response.json()
        assert "detail" in data
        assert (
            "unsupported" in data["detail"].lower() or "type" in data["detail"].lower()
        )

    @pytest.mark.asyncio
    async def test_upload_unsupported_type_json(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should return 415 for JSON files (not in allowed types)."""
        project_id = await create_test_project(async_client_with_s3)
        json_content = b'{"key": "value"}'

        response = await async_client_with_s3.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("data.json", json_content, "application/json")},
        )

        assert response.status_code == 415


# ---------------------------------------------------------------------------
# List Files Tests
# ---------------------------------------------------------------------------


class TestListFiles:
    """Tests for GET /api/v1/projects/{project_id}/files endpoint."""

    @pytest.mark.asyncio
    async def test_list_files_empty(self, async_client_with_s3: AsyncClient) -> None:
        """Should return empty list when no files exist."""
        project_id = await create_test_project(async_client_with_s3)

        response = await async_client_with_s3.get(
            f"/api/v1/projects/{project_id}/files"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_files_with_data(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should return all uploaded files."""
        project_id = await create_test_project(async_client_with_s3)

        # Upload multiple files
        await async_client_with_s3.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("doc1.txt", b"content1", "text/plain")},
        )
        await async_client_with_s3.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("doc2.pdf", create_test_pdf(), "application/pdf")},
        )

        response = await async_client_with_s3.get(
            f"/api/v1/projects/{project_id}/files"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        filenames = [f["filename"] for f in data["items"]]
        assert "doc1.txt" in filenames
        assert "doc2.pdf" in filenames

    @pytest.mark.asyncio
    async def test_list_files_nonexistent_project(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should return 404 when project does not exist."""
        non_existent_id = str(uuid.uuid4())

        response = await async_client_with_s3.get(
            f"/api/v1/projects/{non_existent_id}/files"
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_list_files_isolation(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should only return files for the specific project."""
        # Create two projects
        project1_id = await create_test_project(async_client_with_s3)
        # Create second project manually to avoid name collision
        response = await async_client_with_s3.post(
            "/api/v1/projects",
            json={"name": "Second Project", "site_url": "https://second.example.com"},
        )
        assert response.status_code == 201
        project2_id = response.json()["id"]

        # Upload files to each project
        await async_client_with_s3.post(
            f"/api/v1/projects/{project1_id}/files",
            files={"file": ("project1_file.txt", b"content1", "text/plain")},
        )
        await async_client_with_s3.post(
            f"/api/v1/projects/{project2_id}/files",
            files={"file": ("project2_file.txt", b"content2", "text/plain")},
        )

        # Verify each project only sees its own files
        response1 = await async_client_with_s3.get(
            f"/api/v1/projects/{project1_id}/files"
        )
        response2 = await async_client_with_s3.get(
            f"/api/v1/projects/{project2_id}/files"
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert data1["total"] == 1
        assert data2["total"] == 1
        assert data1["items"][0]["filename"] == "project1_file.txt"
        assert data2["items"][0]["filename"] == "project2_file.txt"


# ---------------------------------------------------------------------------
# Delete File Tests
# ---------------------------------------------------------------------------


class TestDeleteFile:
    """Tests for DELETE /api/v1/projects/{project_id}/files/{file_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_file_exists(self, async_client_with_s3: AsyncClient) -> None:
        """Should delete file and return 204."""
        project_id = await create_test_project(async_client_with_s3)

        # Upload a file
        upload_response = await async_client_with_s3.post(
            f"/api/v1/projects/{project_id}/files",
            files={"file": ("to_delete.txt", b"delete me", "text/plain")},
        )
        assert upload_response.status_code == 201
        file_id = upload_response.json()["id"]

        # Delete the file
        response = await async_client_with_s3.delete(
            f"/api/v1/projects/{project_id}/files/{file_id}"
        )

        assert response.status_code == 204
        assert response.content == b""

        # Verify file is gone
        list_response = await async_client_with_s3.get(
            f"/api/v1/projects/{project_id}/files"
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_delete_file_not_found(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should return 404 when file does not exist."""
        project_id = await create_test_project(async_client_with_s3)
        non_existent_file_id = str(uuid.uuid4())

        response = await async_client_with_s3.delete(
            f"/api/v1/projects/{project_id}/files/{non_existent_file_id}"
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_delete_file_wrong_project(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should return 404 when file belongs to different project."""
        project1_id = await create_test_project(async_client_with_s3)
        response = await async_client_with_s3.post(
            "/api/v1/projects",
            json={"name": "Other Project", "site_url": "https://other.example.com"},
        )
        assert response.status_code == 201
        project2_id = response.json()["id"]

        # Upload file to project1
        upload_response = await async_client_with_s3.post(
            f"/api/v1/projects/{project1_id}/files",
            files={"file": ("owned_by_p1.txt", b"belongs to project1", "text/plain")},
        )
        assert upload_response.status_code == 201
        file_id = upload_response.json()["id"]

        # Try to delete from project2
        response = await async_client_with_s3.delete(
            f"/api/v1/projects/{project2_id}/files/{file_id}"
        )

        assert response.status_code == 404

        # Verify file still exists in project1
        list_response = await async_client_with_s3.get(
            f"/api/v1/projects/{project1_id}/files"
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_delete_file_nonexistent_project(
        self, async_client_with_s3: AsyncClient
    ) -> None:
        """Should return 404 when project does not exist."""
        non_existent_project_id = str(uuid.uuid4())
        non_existent_file_id = str(uuid.uuid4())

        response = await async_client_with_s3.delete(
            f"/api/v1/projects/{non_existent_project_id}/files/{non_existent_file_id}"
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
