"""Tests for Crawling API endpoints.

Integration tests for the URL upload, crawl progress, page listing,
taxonomy, label updates, and retry functionality.

Tests:
- POST /api/v1/projects/{id}/urls - URL upload creates pages and starts crawl
- GET /api/v1/projects/{id}/crawl-status - Returns correct progress
- GET /api/v1/projects/{id}/pages - Returns all pages with data
- GET /api/v1/projects/{id}/taxonomy - Returns labels
- PUT /api/v1/projects/{id}/pages/{page_id}/labels - Validates and saves labels
- POST /api/v1/projects/{id}/pages/{page_id}/retry - Resets failed page
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.project import Project

# ---------------------------------------------------------------------------
# Mock Crawl4AI Client
# ---------------------------------------------------------------------------


class MockCrawlResult:
    """Mock result from Crawl4AI."""

    def __init__(
        self,
        url: str,
        success: bool = True,
        html: str = "<html><head><title>Test Page</title></head><body>Test content</body></html>",
        markdown: str = "# Test Page\n\nTest content here.",
        error: str | None = None,
    ):
        self.url = url
        self.success = success
        self.html = html
        self.markdown = markdown
        self.error_message = error


class MockCrawl4AIClient:
    """Mock Crawl4AI client for testing."""

    def __init__(self) -> None:
        self._crawl_calls: list[str] = []
        self._results: dict[str, MockCrawlResult] = {}
        self._default_success = True

    def set_result(self, url: str, result: MockCrawlResult) -> None:
        """Set a specific result for a URL."""
        self._results[url] = result

    def set_default_success(self, success: bool) -> None:
        """Set default success state for URLs without specific results."""
        self._default_success = success

    @property
    def crawl_calls(self) -> list[str]:
        """Return list of URLs that were crawled."""
        return self._crawl_calls

    async def crawl(self, url: str) -> MockCrawlResult:
        """Mock crawl method."""
        self._crawl_calls.append(url)
        if url in self._results:
            return self._results[url]
        return MockCrawlResult(url=url, success=self._default_success)


@pytest.fixture
def mock_crawl4ai() -> MockCrawl4AIClient:
    """Create a mock Crawl4AI client."""
    return MockCrawl4AIClient()


@pytest.fixture
async def async_client_with_crawl4ai(
    app,
    mock_db_manager,
    mock_redis_manager,
    mock_crawl4ai: MockCrawl4AIClient,
) -> AsyncGenerator[tuple[AsyncClient, MockCrawl4AIClient], None]:
    """Create async test client with mocked Crawl4AI."""
    from app.core.config import get_settings
    from app.integrations.crawl4ai import get_crawl4ai
    from tests.conftest import get_test_settings

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_crawl4ai] = lambda: mock_crawl4ai

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac, mock_crawl4ai

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


async def create_test_project(
    client: AsyncClient, name: str = "Test Project"
) -> dict[str, Any]:
    """Create a test project and return its data."""
    response = await client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "site_url": f"https://{name.lower().replace(' ', '-')}.example.com",
        },
    )
    assert response.status_code == 201
    return response.json()


async def create_crawled_page(
    db: AsyncSession,
    project_id: str,
    url: str,
    status: str = CrawlStatus.PENDING.value,
    title: str | None = None,
    labels: list[str] | None = None,
    crawl_error: str | None = None,
    word_count: int | None = None,
    product_count: int | None = None,
) -> CrawledPage:
    """Create a crawled page directly in the database."""
    page = CrawledPage(
        project_id=project_id,
        normalized_url=url,
        raw_url=url,
        status=status,
        title=title,
        labels=labels or [],
        crawl_error=crawl_error,
        word_count=word_count,
        product_count=product_count,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


async def setup_project_with_taxonomy(
    db: AsyncSession,
    client: AsyncClient,
    taxonomy_labels: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a project with a taxonomy in phase_status."""
    # Create project via API
    project_data = await create_test_project(client, "Taxonomy Test Project")
    project_id = project_data["id"]

    # Set up taxonomy directly in database
    project = await db.get(Project, project_id)
    assert project is not None

    default_labels = [
        {
            "name": "product-detail",
            "description": "Product detail pages",
            "examples": ["/products/"],
        },
        {
            "name": "category-page",
            "description": "Category listing pages",
            "examples": ["/collections/"],
        },
        {"name": "about-page", "description": "About us pages", "examples": ["/about"]},
        {"name": "blog-post", "description": "Blog articles", "examples": ["/blog/"]},
        {
            "name": "contact-page",
            "description": "Contact pages",
            "examples": ["/contact"],
        },
    ]

    project.phase_status = {
        "onboarding": {
            "taxonomy": {
                "labels": taxonomy_labels or default_labels,
                "reasoning": "Test taxonomy",
                "generated_at": "2026-01-01T00:00:00Z",
            }
        }
    }
    flag_modified(project, "phase_status")
    await db.commit()

    return project_data


# ---------------------------------------------------------------------------
# Test URL Upload Endpoint
# ---------------------------------------------------------------------------


class TestUrlUpload:
    """Tests for POST /api/v1/projects/{id}/urls endpoint."""

    @pytest.mark.asyncio
    async def test_upload_urls_creates_pages(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should create CrawledPage records for uploaded URLs."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "URL Upload Test")
        project_id = project["id"]

        response = await client.post(
            f"/api/v1/projects/{project_id}/urls",
            json={
                "urls": [
                    "https://example.com/page1",
                    "https://example.com/page2",
                    "https://example.com/page3",
                ]
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["pages_created"] == 3
        assert data["pages_skipped"] == 0
        assert data["total_urls"] == 3
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_upload_urls_skips_duplicates(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should skip duplicate URLs within the same project."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Duplicate URL Test")
        project_id = project["id"]

        # Upload first batch
        response1 = await client.post(
            f"/api/v1/projects/{project_id}/urls",
            json={"urls": ["https://example.com/page1", "https://example.com/page2"]},
        )
        assert response1.status_code == 202
        assert response1.json()["pages_created"] == 2

        # Upload second batch with one duplicate
        response2 = await client.post(
            f"/api/v1/projects/{project_id}/urls",
            json={"urls": ["https://example.com/page2", "https://example.com/page3"]},
        )
        assert response2.status_code == 202
        data = response2.json()
        assert data["pages_created"] == 1
        assert data["pages_skipped"] == 1

    @pytest.mark.asyncio
    async def test_upload_urls_normalizes_urls(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should normalize URLs and detect duplicates with trailing slashes."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Normalize URL Test")
        project_id = project["id"]

        # Upload URL without trailing slash
        response1 = await client.post(
            f"/api/v1/projects/{project_id}/urls",
            json={"urls": ["https://example.com/page"]},
        )
        assert response1.status_code == 202
        assert response1.json()["pages_created"] == 1

        # Upload same URL with trailing slash (should be skipped)
        response2 = await client.post(
            f"/api/v1/projects/{project_id}/urls",
            json={"urls": ["https://example.com/page/"]},
        )
        assert response2.status_code == 202
        assert response2.json()["pages_skipped"] == 1

    @pytest.mark.asyncio
    async def test_upload_urls_project_not_found(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should return 404 when project doesn't exist."""
        client, _mock_crawl = async_client_with_crawl4ai
        fake_id = str(uuid.uuid4())

        response = await client.post(
            f"/api/v1/projects/{fake_id}/urls",
            json={"urls": ["https://example.com/page1"]},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_urls_validates_url_format(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should reject invalid URLs."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Invalid URL Test")
        project_id = project["id"]

        response = await client.post(
            f"/api/v1/projects/{project_id}/urls",
            json={"urls": ["not-a-valid-url", "also-invalid"]},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Test Crawl Status Endpoint
# ---------------------------------------------------------------------------


class TestCrawlStatus:
    """Tests for GET /api/v1/projects/{id}/crawl-status endpoint."""

    @pytest.mark.asyncio
    async def test_crawl_status_returns_progress(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return correct progress counts."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Crawl Status Test")
        project_id = project["id"]

        # Create pages with various statuses
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/pending",
            CrawlStatus.PENDING.value,
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/crawling",
            CrawlStatus.CRAWLING.value,
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/completed1",
            CrawlStatus.COMPLETED.value,
            title="Page 1",
            word_count=100,
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/completed2",
            CrawlStatus.COMPLETED.value,
            title="Page 2",
            word_count=200,
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/failed",
            CrawlStatus.FAILED.value,
            crawl_error="Connection timeout",
        )

        response = await client.get(f"/api/v1/projects/{project_id}/crawl-status")

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_id
        assert data["progress"]["total"] == 5
        assert data["progress"]["pending"] == 1
        assert data["progress"]["completed"] == 2
        assert data["progress"]["failed"] == 1

    @pytest.mark.asyncio
    async def test_crawl_status_crawling_when_pending(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return status 'crawling' when pages are pending."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Status Crawling Test")
        project_id = project["id"]

        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/pending",
            CrawlStatus.PENDING.value,
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/completed",
            CrawlStatus.COMPLETED.value,
        )

        response = await client.get(f"/api/v1/projects/{project_id}/crawl-status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "crawling"

    @pytest.mark.asyncio
    async def test_crawl_status_labeling_when_no_labels(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return status 'labeling' when all crawled but no labels."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Status Labeling Test")
        project_id = project["id"]

        # All completed, no labels
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page1",
            CrawlStatus.COMPLETED.value,
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page2",
            CrawlStatus.COMPLETED.value,
        )

        response = await client.get(f"/api/v1/projects/{project_id}/crawl-status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "labeling"

    @pytest.mark.asyncio
    async def test_crawl_status_complete_when_has_labels(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return status 'complete' when all crawled with labels."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Status Complete Test")
        project_id = project["id"]

        # All completed with labels
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page1",
            CrawlStatus.COMPLETED.value,
            labels=["product-detail"],
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page2",
            CrawlStatus.COMPLETED.value,
            labels=["category-page"],
        )

        response = await client.get(f"/api/v1/projects/{project_id}/crawl-status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "complete"

    @pytest.mark.asyncio
    async def test_crawl_status_returns_page_summaries(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return page summaries with correct data."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Page Summary Test")
        project_id = project["id"]

        page = await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/products",
            CrawlStatus.COMPLETED.value,
            title="Products Page",
            word_count=500,
            product_count=25,
            labels=["product-listing", "high-traffic"],
        )

        response = await client.get(f"/api/v1/projects/{project_id}/crawl-status")

        assert response.status_code == 200
        data = response.json()
        assert len(data["pages"]) == 1
        page_summary = data["pages"][0]
        assert page_summary["id"] == page.id
        assert page_summary["url"] == "https://example.com/products"
        assert page_summary["status"] == "completed"
        assert page_summary["title"] == "Products Page"
        assert page_summary["word_count"] == 500
        assert page_summary["product_count"] == 25
        assert page_summary["labels"] == ["product-listing", "high-traffic"]

    @pytest.mark.asyncio
    async def test_crawl_status_project_not_found(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should return 404 when project doesn't exist."""
        client, _mock_crawl = async_client_with_crawl4ai
        fake_id = str(uuid.uuid4())

        response = await client.get(f"/api/v1/projects/{fake_id}/crawl-status")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test Pages Endpoint
# ---------------------------------------------------------------------------


class TestPagesEndpoint:
    """Tests for GET /api/v1/projects/{id}/pages endpoint."""

    @pytest.mark.asyncio
    async def test_pages_returns_all_pages(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return all pages with full data."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "List Pages Test")
        project_id = project["id"]

        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page1",
            CrawlStatus.COMPLETED.value,
            title="Page 1",
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page2",
            CrawlStatus.COMPLETED.value,
            title="Page 2",
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page3",
            CrawlStatus.FAILED.value,
            crawl_error="Timeout",
        )

        response = await client.get(f"/api/v1/projects/{project_id}/pages")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Verify full page data is returned
        urls = {page["normalized_url"] for page in data}
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls
        assert "https://example.com/page3" in urls

    @pytest.mark.asyncio
    async def test_pages_filter_by_status(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should filter pages by status query parameter."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Filter Pages Test")
        project_id = project["id"]

        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/completed1",
            CrawlStatus.COMPLETED.value,
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/completed2",
            CrawlStatus.COMPLETED.value,
        )
        await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/failed",
            CrawlStatus.FAILED.value,
        )

        response = await client.get(
            f"/api/v1/projects/{project_id}/pages?status=completed"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(page["status"] == "completed" for page in data)

    @pytest.mark.asyncio
    async def test_pages_returns_empty_list(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should return empty list when no pages exist."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Empty Pages Test")
        project_id = project["id"]

        response = await client.get(f"/api/v1/projects/{project_id}/pages")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_pages_project_not_found(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should return 404 when project doesn't exist."""
        client, _mock_crawl = async_client_with_crawl4ai
        fake_id = str(uuid.uuid4())

        response = await client.get(f"/api/v1/projects/{fake_id}/pages")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test Taxonomy Endpoint
# ---------------------------------------------------------------------------


class TestTaxonomyEndpoint:
    """Tests for GET /api/v1/projects/{id}/taxonomy endpoint."""

    @pytest.mark.asyncio
    async def test_taxonomy_returns_labels(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return taxonomy labels from project."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await setup_project_with_taxonomy(db_session, client)
        project_id = project["id"]

        response = await client.get(f"/api/v1/projects/{project_id}/taxonomy")

        assert response.status_code == 200
        data = response.json()
        assert "labels" in data
        assert len(data["labels"]) == 5
        assert "generated_at" in data

        # Verify label structure
        label_names = {label["name"] for label in data["labels"]}
        assert "product-detail" in label_names
        assert "category-page" in label_names

    @pytest.mark.asyncio
    async def test_taxonomy_not_yet_generated(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should return 404 when taxonomy not generated."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "No Taxonomy Test")
        project_id = project["id"]

        response = await client.get(f"/api/v1/projects/{project_id}/taxonomy")

        assert response.status_code == 404
        assert "Taxonomy not yet generated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_taxonomy_project_not_found(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should return 404 when project doesn't exist."""
        client, _mock_crawl = async_client_with_crawl4ai
        fake_id = str(uuid.uuid4())

        response = await client.get(f"/api/v1/projects/{fake_id}/taxonomy")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test Label Update Endpoint
# ---------------------------------------------------------------------------


class TestLabelUpdate:
    """Tests for PUT /api/v1/projects/{id}/pages/{page_id}/labels endpoint."""

    @pytest.mark.asyncio
    async def test_label_update_validates_and_saves(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should validate labels against taxonomy and save them."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await setup_project_with_taxonomy(db_session, client)
        project_id = project["id"]

        # Create a page
        page = await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page",
            CrawlStatus.COMPLETED.value,
        )

        response = await client.put(
            f"/api/v1/projects/{project_id}/pages/{page.id}/labels",
            json={"labels": ["product-detail", "category-page", "about-page"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert sorted(data["labels"]) == sorted(
            ["product-detail", "category-page", "about-page"]
        )

    @pytest.mark.asyncio
    async def test_label_update_rejects_invalid_labels(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should reject labels not in taxonomy."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await setup_project_with_taxonomy(db_session, client)
        project_id = project["id"]

        page = await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page",
            CrawlStatus.COMPLETED.value,
        )

        response = await client.put(
            f"/api/v1/projects/{project_id}/pages/{page.id}/labels",
            json={"labels": ["product-detail", "invalid-label", "another-bad-one"]},
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_label_update_rejects_too_few_labels(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should reject when fewer than 2 labels provided."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await setup_project_with_taxonomy(db_session, client)
        project_id = project["id"]

        page = await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page",
            CrawlStatus.COMPLETED.value,
        )

        response = await client.put(
            f"/api/v1/projects/{project_id}/pages/{page.id}/labels",
            json={"labels": ["product-detail"]},  # Only 1 label
        )

        assert response.status_code == 400
        assert "2" in response.json()["detail"]  # Error should mention minimum

    @pytest.mark.asyncio
    async def test_label_update_rejects_too_many_labels(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should reject when more than 5 labels provided."""
        client, _mock_crawl = async_client_with_crawl4ai

        # Create taxonomy with more labels for this test
        more_labels = [
            {"name": f"label-{i}", "description": f"Label {i}", "examples": []}
            for i in range(10)
        ]
        project = await setup_project_with_taxonomy(
            db_session, client, taxonomy_labels=more_labels
        )
        project_id = project["id"]

        page = await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page",
            CrawlStatus.COMPLETED.value,
        )

        response = await client.put(
            f"/api/v1/projects/{project_id}/pages/{page.id}/labels",
            json={
                "labels": [
                    "label-0",
                    "label-1",
                    "label-2",
                    "label-3",
                    "label-4",
                    "label-5",
                ]
            },  # 6 labels
        )

        assert response.status_code == 400
        assert "5" in response.json()["detail"]  # Error should mention maximum

    @pytest.mark.asyncio
    async def test_label_update_normalizes_labels(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should normalize labels to lowercase."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await setup_project_with_taxonomy(db_session, client)
        project_id = project["id"]

        page = await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/page",
            CrawlStatus.COMPLETED.value,
        )

        response = await client.put(
            f"/api/v1/projects/{project_id}/pages/{page.id}/labels",
            json={"labels": ["PRODUCT-DETAIL", "Category-Page", "  about-page  "]},
        )

        assert response.status_code == 200
        data = response.json()
        # All should be lowercase and trimmed
        assert sorted(data["labels"]) == sorted(
            ["product-detail", "category-page", "about-page"]
        )

    @pytest.mark.asyncio
    async def test_label_update_page_not_found(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return 404 when page doesn't exist."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await setup_project_with_taxonomy(db_session, client)
        project_id = project["id"]
        fake_page_id = str(uuid.uuid4())

        response = await client.put(
            f"/api/v1/projects/{project_id}/pages/{fake_page_id}/labels",
            json={"labels": ["product-detail", "category-page"]},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_label_update_page_wrong_project(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return 404 when page belongs to different project."""
        client, _mock_crawl = async_client_with_crawl4ai

        # Create two projects
        project1 = await setup_project_with_taxonomy(db_session, client)
        project2 = await create_test_project(client, "Other Project")

        # Create page in project1
        page = await create_crawled_page(
            db_session,
            project1["id"],
            "https://example.com/page",
            CrawlStatus.COMPLETED.value,
        )

        # Try to update page labels via project2 endpoint
        response = await client.put(
            f"/api/v1/projects/{project2['id']}/pages/{page.id}/labels",
            json={"labels": ["product-detail", "category-page"]},
        )

        assert response.status_code == 404
        assert "not found in project" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test Retry Endpoint
# ---------------------------------------------------------------------------


class TestRetryEndpoint:
    """Tests for POST /api/v1/projects/{id}/pages/{page_id}/retry endpoint."""

    @pytest.mark.asyncio
    async def test_retry_resets_failed_page(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should reset page status to pending and clear error."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Retry Test")
        project_id = project["id"]

        # Create a failed page
        page = await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/failed",
            CrawlStatus.FAILED.value,
            crawl_error="Connection timeout",
        )

        response = await client.post(
            f"/api/v1/projects/{project_id}/pages/{page.id}/retry"
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["crawl_error"] is None

    @pytest.mark.asyncio
    async def test_retry_can_retry_any_status(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should allow retry on pages of any status."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Retry Any Status Test")
        project_id = project["id"]

        # Create a completed page (maybe we want to re-crawl for fresh content)
        page = await create_crawled_page(
            db_session,
            project_id,
            "https://example.com/completed",
            CrawlStatus.COMPLETED.value,
            title="Old Title",
        )

        response = await client.post(
            f"/api/v1/projects/{project_id}/pages/{page.id}/retry"
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"

    @pytest.mark.asyncio
    async def test_retry_page_not_found(
        self, async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient]
    ) -> None:
        """Should return 404 when page doesn't exist."""
        client, _mock_crawl = async_client_with_crawl4ai
        project = await create_test_project(client, "Retry Not Found Test")
        fake_page_id = str(uuid.uuid4())

        response = await client.post(
            f"/api/v1/projects/{project['id']}/pages/{fake_page_id}/retry"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_project_not_found(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return 404 when project doesn't exist."""
        client, _mock_crawl = async_client_with_crawl4ai
        fake_project_id = str(uuid.uuid4())
        fake_page_id = str(uuid.uuid4())

        response = await client.post(
            f"/api/v1/projects/{fake_project_id}/pages/{fake_page_id}/retry"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_page_wrong_project(
        self,
        async_client_with_crawl4ai: tuple[AsyncClient, MockCrawl4AIClient],
        db_session: AsyncSession,
    ) -> None:
        """Should return 404 when page belongs to different project."""
        client, _mock_crawl = async_client_with_crawl4ai

        # Create two projects
        project1 = await create_test_project(client, "Project 1")
        project2 = await create_test_project(client, "Project 2")

        # Create page in project1
        page = await create_crawled_page(
            db_session,
            project1["id"],
            "https://example.com/page",
            CrawlStatus.FAILED.value,
        )

        # Try to retry via project2 endpoint
        response = await client.post(
            f"/api/v1/projects/{project2['id']}/pages/{page.id}/retry"
        )

        assert response.status_code == 404
        assert "not found in project" in response.json()["detail"].lower()
