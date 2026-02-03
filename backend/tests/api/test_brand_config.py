"""Tests for Brand Config API endpoints.

Tests all brand config management operations on the /api/v1/projects/{project_id}/brand-config endpoints:
- Get brand config
- Update brand config sections
- Regenerate brand config sections
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.database import DatabaseManager
from app.integrations.claude import get_claude
from app.integrations.crawl4ai import get_crawl4ai
from app.integrations.perplexity import get_perplexity
from app.models.brand_config import BrandConfig
from app.models.project import Project
from tests.conftest import get_test_settings

# ---------------------------------------------------------------------------
# Mock Integration Clients
# ---------------------------------------------------------------------------


class MockClaudeClient:
    """Mock Claude client for testing."""

    def __init__(self, available: bool = True) -> None:
        self._available = available
        self._response_json = '{"test": "data"}'

    @property
    def available(self) -> bool:
        return self._available

    async def complete(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> MagicMock:
        """Return mock completion result."""
        result = MagicMock()
        result.success = True
        result.text = self._response_json
        result.error = None
        result.input_tokens = 100
        result.output_tokens = 50
        result.duration_ms = 500
        return result


class MockPerplexityClient:
    """Mock Perplexity client for testing."""

    def __init__(self, available: bool = True) -> None:
        self._available = available

    @property
    def available(self) -> bool:
        return self._available

    async def research_brand(
        self, site_url: str, brand_name: str
    ) -> MagicMock:
        """Return mock research result."""
        result = MagicMock()
        result.success = True
        result.raw_text = "Brand research results"
        result.citations = ["https://example.com"]
        result.error = None
        return result


class MockCrawl4AIClient:
    """Mock Crawl4AI client for testing."""

    def __init__(self, available: bool = True) -> None:
        self._available = available

    @property
    def available(self) -> bool:
        return self._available

    async def crawl(self, url: str) -> MagicMock:
        """Return mock crawl result."""
        result = MagicMock()
        result.success = True
        result.markdown = "# Website Content\n\nTest content"
        result.metadata = {"title": "Test Site"}
        result.error = None
        return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def async_client_with_mocks(
    app,
    mock_db_manager: DatabaseManager,
    mock_redis_manager,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with mocked integration clients."""
    mock_claude = MockClaudeClient()
    mock_perplexity = MockPerplexityClient()
    mock_crawl4ai = MockCrawl4AIClient()

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_claude] = lambda: mock_claude
    app.dependency_overrides[get_perplexity] = lambda: mock_perplexity
    app.dependency_overrides[get_crawl4ai] = lambda: mock_crawl4ai

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def async_client_claude_unavailable(
    app,
    mock_db_manager: DatabaseManager,
    mock_redis_manager,
) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client with Claude unavailable."""
    mock_claude = MockClaudeClient(available=False)
    mock_perplexity = MockPerplexityClient()
    mock_crawl4ai = MockCrawl4AIClient()

    app.dependency_overrides[get_settings] = get_test_settings
    app.dependency_overrides[get_claude] = lambda: mock_claude
    app.dependency_overrides[get_perplexity] = lambda: mock_perplexity
    app.dependency_overrides[get_crawl4ai] = lambda: mock_crawl4ai

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_v2_schema() -> dict[str, Any]:
    """Sample v2_schema for testing."""
    return {
        "version": "2.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_documents": [],
        "brand_foundation": {
            "company_overview": {
                "company_name": "Test Corp",
                "industry": "Technology",
            }
        },
        "target_audience": {
            "primary_persona": {
                "name": "Tech Professional",
            }
        },
        "voice_dimensions": {
            "formality": {"score": 5, "description": "Balanced"},
        },
        "voice_characteristics": {
            "we_are": [{"characteristic": "Helpful"}],
        },
        "writing_style": {
            "sentence_structure": {"average_sentence_length": "12-18 words"},
        },
        "vocabulary": {
            "power_words": ["innovative", "reliable"],
        },
        "trust_elements": {
            "hard_numbers": {"customer_count": "1000+"},
        },
        "examples_bank": {
            "headlines_that_work": ["Test headline"],
        },
        "competitor_context": {
            "direct_competitors": [],
        },
        "ai_prompt_snippet": {
            "snippet": "Write in a helpful, professional tone.",
        },
    }


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestGetBrandConfig:
    """Tests for GET /api/v1/projects/{project_id}/brand-config"""

    async def test_get_brand_config_success(
        self,
        async_client: AsyncClient,
        db_session,
        sample_v2_schema: dict[str, Any],
    ) -> None:
        """Test getting brand config for a project."""
        # Create project
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        # Create brand config
        brand_config = BrandConfig(
            id=str(uuid.uuid4()),
            project_id=project.id,
            brand_name="Test Corp",
            domain="test.com",
            v2_schema=sample_v2_schema,
        )
        db_session.add(brand_config)
        await db_session.commit()

        # Get brand config
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/brand-config"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == brand_config.id
        assert data["project_id"] == project.id
        assert data["brand_name"] == "Test Corp"
        assert data["domain"] == "test.com"
        assert data["v2_schema"]["version"] == "2.0"
        assert "brand_foundation" in data["v2_schema"]

    async def test_get_brand_config_not_generated(
        self,
        async_client: AsyncClient,
        db_session,
    ) -> None:
        """Test getting brand config when not generated yet returns 404."""
        # Create project without brand config
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/brand-config"
        )

        assert response.status_code == 404
        assert "not generated yet" in response.json()["detail"]

    async def test_get_brand_config_project_not_found(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test getting brand config for nonexistent project returns 404."""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/projects/{fake_id}/brand-config"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestUpdateBrandConfig:
    """Tests for PATCH /api/v1/projects/{project_id}/brand-config"""

    async def test_update_brand_config_single_section(
        self,
        async_client: AsyncClient,
        db_session,
        sample_v2_schema: dict[str, Any],
    ) -> None:
        """Test updating a single section of brand config."""
        # Create project and brand config
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        brand_config = BrandConfig(
            id=str(uuid.uuid4()),
            project_id=project.id,
            brand_name="Test Corp",
            v2_schema=sample_v2_schema,
        )
        db_session.add(brand_config)
        await db_session.commit()

        # Update brand_foundation section
        new_foundation = {
            "company_overview": {
                "company_name": "Updated Corp",
                "industry": "Software",
            }
        }

        response = await async_client.patch(
            f"/api/v1/projects/{project.id}/brand-config",
            json={"sections": {"brand_foundation": new_foundation}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["v2_schema"]["brand_foundation"]["company_overview"]["company_name"] == "Updated Corp"
        assert data["v2_schema"]["brand_foundation"]["company_overview"]["industry"] == "Software"
        # Other sections should remain unchanged
        assert "target_audience" in data["v2_schema"]

    async def test_update_brand_config_multiple_sections(
        self,
        async_client: AsyncClient,
        db_session,
        sample_v2_schema: dict[str, Any],
    ) -> None:
        """Test updating multiple sections at once."""
        # Create project and brand config
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        brand_config = BrandConfig(
            id=str(uuid.uuid4()),
            project_id=project.id,
            brand_name="Test Corp",
            v2_schema=sample_v2_schema,
        )
        db_session.add(brand_config)
        await db_session.commit()

        # Update multiple sections
        response = await async_client.patch(
            f"/api/v1/projects/{project.id}/brand-config",
            json={
                "sections": {
                    "brand_foundation": {"updated": True},
                    "vocabulary": {"power_words": ["new", "words"]},
                }
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["v2_schema"]["brand_foundation"]["updated"] is True
        assert data["v2_schema"]["vocabulary"]["power_words"] == ["new", "words"]

    async def test_update_brand_config_invalid_section(
        self,
        async_client: AsyncClient,
        db_session,
        sample_v2_schema: dict[str, Any],
    ) -> None:
        """Test updating with invalid section name returns 422."""
        # Create project and brand config
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        brand_config = BrandConfig(
            id=str(uuid.uuid4()),
            project_id=project.id,
            brand_name="Test Corp",
            v2_schema=sample_v2_schema,
        )
        db_session.add(brand_config)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/projects/{project.id}/brand-config",
            json={"sections": {"invalid_section": {"data": "test"}}},
        )

        assert response.status_code == 422

    async def test_update_brand_config_not_generated(
        self,
        async_client: AsyncClient,
        db_session,
    ) -> None:
        """Test updating brand config when not generated returns 404."""
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        response = await async_client.patch(
            f"/api/v1/projects/{project.id}/brand-config",
            json={"sections": {"brand_foundation": {"test": True}}},
        )

        assert response.status_code == 404


class TestRegenerateBrandConfig:
    """Tests for POST /api/v1/projects/{project_id}/brand-config/regenerate"""

    async def test_regenerate_single_section(
        self,
        async_client_with_mocks: AsyncClient,
        db_session,
        sample_v2_schema: dict[str, Any],
    ) -> None:
        """Test regenerating a single section."""
        # Create project and brand config
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        brand_config = BrandConfig(
            id=str(uuid.uuid4()),
            project_id=project.id,
            brand_name="Test Corp",
            v2_schema=sample_v2_schema,
        )
        db_session.add(brand_config)
        await db_session.commit()

        response = await async_client_with_mocks.post(
            f"/api/v1/projects/{project.id}/brand-config/regenerate",
            json={"section": "brand_foundation"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "v2_schema" in data
        # The mock returns {"test": "data"} for brand_foundation
        assert data["v2_schema"]["brand_foundation"] == {"test": "data"}

    async def test_regenerate_multiple_sections(
        self,
        async_client_with_mocks: AsyncClient,
        db_session,
        sample_v2_schema: dict[str, Any],
    ) -> None:
        """Test regenerating multiple sections."""
        # Create project and brand config
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        brand_config = BrandConfig(
            id=str(uuid.uuid4()),
            project_id=project.id,
            brand_name="Test Corp",
            v2_schema=sample_v2_schema,
        )
        db_session.add(brand_config)
        await db_session.commit()

        response = await async_client_with_mocks.post(
            f"/api/v1/projects/{project.id}/brand-config/regenerate",
            json={"sections": ["brand_foundation", "vocabulary"]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["v2_schema"]["brand_foundation"] == {"test": "data"}
        assert data["v2_schema"]["vocabulary"] == {"test": "data"}

    async def test_regenerate_invalid_section(
        self,
        async_client_with_mocks: AsyncClient,
        db_session,
        sample_v2_schema: dict[str, Any],
    ) -> None:
        """Test regenerating with invalid section returns 422."""
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        brand_config = BrandConfig(
            id=str(uuid.uuid4()),
            project_id=project.id,
            brand_name="Test Corp",
            v2_schema=sample_v2_schema,
        )
        db_session.add(brand_config)
        await db_session.commit()

        response = await async_client_with_mocks.post(
            f"/api/v1/projects/{project.id}/brand-config/regenerate",
            json={"section": "invalid_section_name"},
        )

        assert response.status_code == 422

    async def test_regenerate_brand_config_not_generated(
        self,
        async_client_with_mocks: AsyncClient,
        db_session,
    ) -> None:
        """Test regenerating brand config when not generated returns 404."""
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        response = await async_client_with_mocks.post(
            f"/api/v1/projects/{project.id}/brand-config/regenerate",
            json={"section": "brand_foundation"},
        )

        assert response.status_code == 404

    async def test_regenerate_claude_unavailable(
        self,
        async_client_claude_unavailable: AsyncClient,
        db_session,
        sample_v2_schema: dict[str, Any],
    ) -> None:
        """Test regenerating when Claude is unavailable returns 503."""
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project",
            site_url="https://test.com",
        )
        db_session.add(project)
        await db_session.commit()

        brand_config = BrandConfig(
            id=str(uuid.uuid4()),
            project_id=project.id,
            brand_name="Test Corp",
            v2_schema=sample_v2_schema,
        )
        db_session.add(brand_config)
        await db_session.commit()

        response = await async_client_claude_unavailable.post(
            f"/api/v1/projects/{project.id}/brand-config/regenerate",
            json={"section": "brand_foundation"},
        )

        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]
