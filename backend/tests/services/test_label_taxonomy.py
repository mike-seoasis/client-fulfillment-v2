"""Unit tests for LabelTaxonomyService.

Tests cover:
- Taxonomy generation and storage in phase_status
- Label assignment validation against taxonomy
- Invalid label rejection
- Label count validation (2-5 labels per page)
- Validation helpers

Note: Tests mock the Claude client to avoid API calls.
"""

import json
import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.claude import CompletionResult
from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.project import Project
from app.services.label_taxonomy import (
    MAX_LABELS_PER_PAGE,
    MIN_LABELS_PER_PAGE,
    GeneratedTaxonomy,
    LabelTaxonomyService,
    TaxonomyLabel,
    get_project_taxonomy_labels,
    validate_labels,
    validate_page_labels,
)

# ---------------------------------------------------------------------------
# Mock Claude Client
# ---------------------------------------------------------------------------


class MockClaudeClient:
    """Mock Claude client for testing LabelTaxonomyService."""

    def __init__(
        self,
        taxonomy_response: dict[str, Any] | None = None,
        assignment_response: dict[str, Any] | None = None,
        fail_taxonomy: bool = False,
        fail_assignment: bool = False,
    ) -> None:
        """Initialize mock client.

        Args:
            taxonomy_response: JSON response for taxonomy generation.
            assignment_response: JSON response for label assignment.
            fail_taxonomy: Whether taxonomy generation should fail.
            fail_assignment: Whether label assignment should fail.
        """
        self._taxonomy_response = taxonomy_response or self._default_taxonomy()
        self._assignment_response = assignment_response or self._default_assignment()
        self._fail_taxonomy = fail_taxonomy
        self._fail_assignment = fail_assignment

        # Track calls
        self.complete_calls: list[dict[str, Any]] = []

    def _default_taxonomy(self) -> dict[str, Any]:
        """Default taxonomy response."""
        return {
            "labels": [
                {
                    "name": "product-listing",
                    "description": "Pages showing multiple products",
                    "examples": ["/collections/*", "/shop/*"],
                },
                {
                    "name": "product-detail",
                    "description": "Individual product pages",
                    "examples": ["/products/*"],
                },
                {
                    "name": "blog-post",
                    "description": "Blog articles and content",
                    "examples": ["/blog/*", "/articles/*"],
                },
                {
                    "name": "about-us",
                    "description": "Company information pages",
                    "examples": ["/about", "/our-story"],
                },
                {
                    "name": "customer-support",
                    "description": "Help and FAQ pages",
                    "examples": ["/faq", "/help", "/contact"],
                },
            ],
            "reasoning": "Taxonomy covers main e-commerce page types",
        }

    def _default_assignment(self) -> dict[str, Any]:
        """Default assignment response."""
        return {
            "labels": ["product-listing", "blog-post"],
            "confidence": 0.85,
            "reasoning": "Page contains product listings with blog content",
        }

    async def complete(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> CompletionResult:
        """Mock completion request."""
        self.complete_calls.append({
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        })

        # Determine which type of request this is based on user prompt content
        # Taxonomy generation prompts ask to "generate a taxonomy" from pages
        # Assignment prompts ask to "Assign labels" to a page
        is_taxonomy_request = "Generate a taxonomy" in user_prompt or "generate a taxonomy" in user_prompt.lower()
        is_assignment_request = "Assign labels" in user_prompt or "assign labels" in user_prompt.lower()

        if is_taxonomy_request:
            if self._fail_taxonomy:
                return CompletionResult(
                    success=False,
                    error="API error during taxonomy generation",
                )
            return CompletionResult(
                success=True,
                text=json.dumps(self._taxonomy_response),
                input_tokens=100,
                output_tokens=200,
            )
        elif is_assignment_request:
            if self._fail_assignment:
                return CompletionResult(
                    success=False,
                    error="API error during label assignment",
                )
            return CompletionResult(
                success=True,
                text=json.dumps(self._assignment_response),
                input_tokens=50,
                output_tokens=100,
            )
        else:
            # Unknown request type - return generic success
            return CompletionResult(
                success=True,
                text="{}",
                input_tokens=10,
                output_tokens=10,
            )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_project(db_session: AsyncSession) -> Project:
    """Create a test project."""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Project",
        site_url="https://example.com",
        phase_status={},
    )
    db_session.add(project)
    await db_session.commit()
    return project


@pytest.fixture
async def test_project_with_taxonomy(db_session: AsyncSession) -> Project:
    """Create a test project with an existing taxonomy."""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Project with Taxonomy",
        site_url="https://example.com",
        phase_status={
            "onboarding": {
                "taxonomy": {
                    "labels": [
                        {"name": "product-listing", "description": "Product pages", "examples": []},
                        {"name": "blog-post", "description": "Blog articles", "examples": []},
                        {"name": "about-us", "description": "Company info", "examples": []},
                        {"name": "customer-support", "description": "Help pages", "examples": []},
                        {"name": "trail-running", "description": "Trail running products", "examples": []},
                    ],
                    "reasoning": "Test taxonomy",
                    "generated_at": "2024-01-01T00:00:00Z",
                },
            },
        },
    )
    db_session.add(project)
    await db_session.commit()
    return project


@pytest.fixture
async def completed_pages(
    db_session: AsyncSession,
    test_project: Project,
) -> list[CrawledPage]:
    """Create completed pages for taxonomy generation."""
    pages = []
    page_data = [
        {"url": "https://example.com/products/shoe-1", "title": "Running Shoe"},
        {"url": "https://example.com/collections/trail", "title": "Trail Running Collection"},
        {"url": "https://example.com/blog/running-tips", "title": "10 Running Tips"},
        {"url": "https://example.com/about", "title": "About Us"},
    ]

    for data in page_data:
        page = CrawledPage(
            id=str(uuid.uuid4()),
            project_id=test_project.id,
            normalized_url=data["url"],
            raw_url=data["url"],
            status=CrawlStatus.COMPLETED.value,
            title=data["title"],
            meta_description=f"Description for {data['title']}",
            body_content="Sample content for the page.",
            word_count=100,
        )
        pages.append(page)
        db_session.add(page)

    await db_session.commit()
    return pages


@pytest.fixture
async def completed_page_with_taxonomy(
    db_session: AsyncSession,
    test_project_with_taxonomy: Project,
) -> CrawledPage:
    """Create a completed page for a project that has a taxonomy."""
    page = CrawledPage(
        id=str(uuid.uuid4()),
        project_id=test_project_with_taxonomy.id,
        normalized_url="https://example.com/products/test-product",
        raw_url="https://example.com/products/test-product",
        status=CrawlStatus.COMPLETED.value,
        title="Test Product Page",
        meta_description="A test product page",
        body_content="Product content here.",
        word_count=50,
    )
    db_session.add(page)
    await db_session.commit()
    return page


@pytest.fixture
def mock_claude_client() -> MockClaudeClient:
    """Create a mock Claude client."""
    return MockClaudeClient()


@pytest.fixture
def label_taxonomy_service(mock_claude_client: MockClaudeClient) -> LabelTaxonomyService:
    """Create LabelTaxonomyService with mock client."""
    return LabelTaxonomyService(mock_claude_client)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestTaxonomyGenerationStorage:
    """Tests for taxonomy generation and storage in phase_status."""

    async def test_generate_taxonomy_stores_in_phase_status(
        self,
        db_session: AsyncSession,
        test_project: Project,
        completed_pages: list[CrawledPage],
        label_taxonomy_service: LabelTaxonomyService,
    ) -> None:
        """Test that generated taxonomy is stored in project.phase_status."""
        result = await label_taxonomy_service.generate_taxonomy(
            db_session, test_project.id
        )

        assert result is not None
        assert len(result.labels) == 5
        assert result.reasoning == "Taxonomy covers main e-commerce page types"

        # Verify storage in phase_status
        await db_session.refresh(test_project)
        taxonomy_data = test_project.phase_status.get("onboarding", {}).get("taxonomy")

        assert taxonomy_data is not None
        assert len(taxonomy_data["labels"]) == 5
        assert taxonomy_data["reasoning"] == "Taxonomy covers main e-commerce page types"
        assert "generated_at" in taxonomy_data

    async def test_generate_taxonomy_returns_none_for_no_pages(
        self,
        db_session: AsyncSession,
        test_project: Project,
        label_taxonomy_service: LabelTaxonomyService,
    ) -> None:
        """Test that taxonomy generation returns None when no completed pages exist."""
        result = await label_taxonomy_service.generate_taxonomy(
            db_session, test_project.id
        )

        assert result is None

    async def test_generate_taxonomy_returns_none_on_api_failure(
        self,
        db_session: AsyncSession,
        test_project: Project,
        completed_pages: list[CrawledPage],
    ) -> None:
        """Test that taxonomy generation returns None on Claude API failure."""
        mock_client = MockClaudeClient(fail_taxonomy=True)
        service = LabelTaxonomyService(mock_client)  # type: ignore[arg-type]

        result = await service.generate_taxonomy(db_session, test_project.id)

        assert result is None

    async def test_generate_taxonomy_includes_page_summaries(
        self,
        db_session: AsyncSession,
        test_project: Project,
        completed_pages: list[CrawledPage],
    ) -> None:
        """Test that taxonomy generation prompt includes page summaries."""
        mock_client = MockClaudeClient()
        service = LabelTaxonomyService(mock_client)  # type: ignore[arg-type]

        await service.generate_taxonomy(db_session, test_project.id)

        # Check the prompt includes page data
        assert len(mock_client.complete_calls) == 1
        user_prompt = mock_client.complete_calls[0]["user_prompt"]

        for page in completed_pages:
            assert page.normalized_url in user_prompt
            assert page.title in user_prompt


class TestLabelAssignmentValidation:
    """Tests for label assignment validation against taxonomy."""

    async def test_assign_labels_uses_taxonomy(
        self,
        db_session: AsyncSession,
        test_project_with_taxonomy: Project,
        completed_page_with_taxonomy: CrawledPage,
    ) -> None:
        """Test that label assignment uses the project's taxonomy."""
        mock_client = MockClaudeClient()
        service = LabelTaxonomyService(mock_client)  # type: ignore[arg-type]

        assignments = await service.assign_labels(
            db_session, test_project_with_taxonomy.id
        )

        assert len(assignments) == 1
        assert assignments[0].success is True
        # Labels should be from the taxonomy
        for label in assignments[0].labels:
            assert label in {"product-listing", "blog-post", "about-us", "customer-support", "trail-running"}

    async def test_assign_labels_stores_in_page(
        self,
        db_session: AsyncSession,
        test_project_with_taxonomy: Project,
        completed_page_with_taxonomy: CrawledPage,
    ) -> None:
        """Test that assigned labels are stored in the CrawledPage.labels field."""
        mock_client = MockClaudeClient()
        service = LabelTaxonomyService(mock_client)  # type: ignore[arg-type]

        await service.assign_labels(db_session, test_project_with_taxonomy.id)

        await db_session.refresh(completed_page_with_taxonomy)
        assert completed_page_with_taxonomy.labels is not None
        assert len(completed_page_with_taxonomy.labels) >= 1

    async def test_assign_labels_returns_empty_for_no_taxonomy(
        self,
        db_session: AsyncSession,
        test_project: Project,
        completed_pages: list[CrawledPage],
        label_taxonomy_service: LabelTaxonomyService,
    ) -> None:
        """Test that label assignment returns empty list when no taxonomy exists."""
        assignments = await label_taxonomy_service.assign_labels(
            db_session, test_project.id
        )

        assert assignments == []


class TestInvalidLabelRejection:
    """Tests for invalid label rejection."""

    async def test_invalid_labels_filtered_out(
        self,
        db_session: AsyncSession,
        test_project_with_taxonomy: Project,
        completed_page_with_taxonomy: CrawledPage,
    ) -> None:
        """Test that labels not in taxonomy are filtered out."""
        # Mock client returns labels that don't all exist in taxonomy
        mock_client = MockClaudeClient(
            assignment_response={
                "labels": ["product-listing", "invalid-label", "nonexistent-label"],
                "confidence": 0.8,
                "reasoning": "Test with invalid labels",
            }
        )
        service = LabelTaxonomyService(mock_client)  # type: ignore[arg-type]

        assignments = await service.assign_labels(
            db_session, test_project_with_taxonomy.id
        )

        assert len(assignments) == 1
        # Only valid labels should remain
        assert "product-listing" in assignments[0].labels
        assert "invalid-label" not in assignments[0].labels
        assert "nonexistent-label" not in assignments[0].labels

    def test_validate_labels_rejects_invalid(self) -> None:
        """Test that validate_labels rejects labels not in taxonomy."""
        taxonomy = {"product-listing", "blog-post", "about-us"}
        labels = ["product-listing", "invalid-label"]

        result = validate_labels(labels, taxonomy)

        assert result.valid is False
        assert any(e.code == "invalid_labels" for e in result.errors)
        assert "invalid-label" in str(result.error_messages)

    def test_validate_labels_all_invalid(self) -> None:
        """Test validation when all labels are invalid."""
        taxonomy = {"product-listing", "blog-post"}
        labels = ["invalid-1", "invalid-2"]

        result = validate_labels(labels, taxonomy)

        assert result.valid is False
        errors = [e.code for e in result.errors]
        assert "invalid_labels" in errors


class TestLabelCountValidation:
    """Tests for label count validation (2-5 labels per page)."""

    def test_validate_labels_too_few(self) -> None:
        """Test validation rejects too few labels (< 2)."""
        taxonomy = {"label-1", "label-2", "label-3"}
        labels = ["label-1"]  # Only 1 label

        result = validate_labels(labels, taxonomy)

        assert result.valid is False
        assert any(e.code == "too_few_labels" for e in result.errors)
        error = next(e for e in result.errors if e.code == "too_few_labels")
        assert error.details["min_required"] == MIN_LABELS_PER_PAGE
        assert error.details["actual_count"] == 1

    def test_validate_labels_too_many(self) -> None:
        """Test validation rejects too many labels (> 5)."""
        taxonomy = {"label-1", "label-2", "label-3", "label-4", "label-5", "label-6", "label-7"}
        labels = ["label-1", "label-2", "label-3", "label-4", "label-5", "label-6"]  # 6 labels

        result = validate_labels(labels, taxonomy)

        assert result.valid is False
        assert any(e.code == "too_many_labels" for e in result.errors)
        error = next(e for e in result.errors if e.code == "too_many_labels")
        assert error.details["max_allowed"] == MAX_LABELS_PER_PAGE
        assert error.details["actual_count"] == 6

    def test_validate_labels_valid_count(self) -> None:
        """Test validation passes for valid label count (2-5)."""
        taxonomy = {"label-1", "label-2", "label-3", "label-4", "label-5"}

        # Test minimum (2)
        result_min = validate_labels(["label-1", "label-2"], taxonomy)
        assert result_min.valid is True
        assert len(result_min.errors) == 0

        # Test middle (3)
        result_mid = validate_labels(["label-1", "label-2", "label-3"], taxonomy)
        assert result_mid.valid is True

        # Test maximum (5)
        result_max = validate_labels(
            ["label-1", "label-2", "label-3", "label-4", "label-5"],
            taxonomy
        )
        assert result_max.valid is True

    def test_validate_labels_custom_count_limits(self) -> None:
        """Test validation with custom min/max label counts."""
        taxonomy = {"a", "b", "c", "d", "e", "f", "g", "h", "i", "j"}

        # Custom: 1-10 labels allowed
        result = validate_labels(
            ["a"],
            taxonomy,
            min_labels=1,
            max_labels=10,
        )
        assert result.valid is True

        # Custom: 3-4 labels allowed
        result = validate_labels(
            ["a", "b"],  # 2 labels
            taxonomy,
            min_labels=3,
            max_labels=4,
        )
        assert result.valid is False
        assert any(e.code == "too_few_labels" for e in result.errors)


class TestLabelNormalization:
    """Tests for label normalization during validation."""

    def test_validate_labels_normalizes_case(self) -> None:
        """Test that labels are normalized to lowercase."""
        taxonomy = {"product-listing", "blog-post"}
        labels = ["PRODUCT-LISTING", "Blog-Post"]

        result = validate_labels(labels, taxonomy)

        assert result.valid is True
        assert "product-listing" in result.labels
        assert "blog-post" in result.labels

    def test_validate_labels_strips_whitespace(self) -> None:
        """Test that labels have whitespace stripped."""
        taxonomy = {"product-listing", "blog-post"}
        labels = ["  product-listing  ", "blog-post\t"]

        result = validate_labels(labels, taxonomy)

        assert result.valid is True
        assert result.labels == ["product-listing", "blog-post"]

    def test_validate_labels_removes_duplicates(self) -> None:
        """Test that duplicate labels are removed."""
        taxonomy = {"label-1", "label-2", "label-3"}
        labels = ["label-1", "label-2", "label-1", "label-2", "label-3"]

        result = validate_labels(labels, taxonomy)

        assert result.valid is True
        assert len(result.labels) == 3
        assert result.labels == ["label-1", "label-2", "label-3"]

    def test_validate_labels_ignores_empty_strings(self) -> None:
        """Test that empty strings are ignored."""
        taxonomy = {"label-1", "label-2"}
        labels = ["label-1", "", "  ", "label-2"]

        result = validate_labels(labels, taxonomy)

        assert result.valid is True
        assert len(result.labels) == 2


class TestValidationHelpers:
    """Tests for validation helper functions."""

    async def test_get_project_taxonomy_labels_returns_set(
        self,
        db_session: AsyncSession,
        test_project_with_taxonomy: Project,
    ) -> None:
        """Test that get_project_taxonomy_labels returns a set of label names."""
        labels = await get_project_taxonomy_labels(
            db_session, test_project_with_taxonomy.id
        )

        assert labels is not None
        assert isinstance(labels, set)
        assert "product-listing" in labels
        assert "blog-post" in labels
        assert len(labels) == 5

    async def test_get_project_taxonomy_labels_returns_none_for_no_taxonomy(
        self,
        db_session: AsyncSession,
        test_project: Project,
    ) -> None:
        """Test that get_project_taxonomy_labels returns None when no taxonomy exists."""
        labels = await get_project_taxonomy_labels(db_session, test_project.id)

        assert labels is None

    async def test_get_project_taxonomy_labels_returns_none_for_invalid_project(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test that get_project_taxonomy_labels returns None for invalid project ID."""
        labels = await get_project_taxonomy_labels(db_session, str(uuid.uuid4()))

        assert labels is None

    async def test_validate_page_labels_loads_taxonomy(
        self,
        db_session: AsyncSession,
        test_project_with_taxonomy: Project,
    ) -> None:
        """Test that validate_page_labels loads taxonomy and validates."""
        result = await validate_page_labels(
            db_session,
            test_project_with_taxonomy.id,
            ["product-listing", "blog-post"],
        )

        assert result.valid is True
        assert len(result.labels) == 2

    async def test_validate_page_labels_returns_error_for_no_taxonomy(
        self,
        db_session: AsyncSession,
        test_project: Project,
    ) -> None:
        """Test that validate_page_labels returns error when no taxonomy exists."""
        result = await validate_page_labels(
            db_session,
            test_project.id,
            ["some-label"],
        )

        assert result.valid is False
        assert any(e.code == "no_taxonomy" for e in result.errors)


class TestAssignmentAPIFailure:
    """Tests for label assignment API failure handling."""

    async def test_assign_labels_returns_failure_on_api_error(
        self,
        db_session: AsyncSession,
        test_project_with_taxonomy: Project,
        completed_page_with_taxonomy: CrawledPage,
    ) -> None:
        """Test that label assignment handles API failures gracefully."""
        mock_client = MockClaudeClient(fail_assignment=True)
        service = LabelTaxonomyService(mock_client)  # type: ignore[arg-type]

        assignments = await service.assign_labels(
            db_session, test_project_with_taxonomy.id
        )

        assert len(assignments) == 1
        assert assignments[0].success is False
        assert assignments[0].error is not None

    async def test_assign_labels_handles_json_parse_error(
        self,
        db_session: AsyncSession,
        test_project_with_taxonomy: Project,
        completed_page_with_taxonomy: CrawledPage,
    ) -> None:
        """Test that label assignment handles malformed JSON responses."""

        class BadJsonClient(MockClaudeClient):
            async def complete(self, *args, **kwargs) -> CompletionResult:
                return CompletionResult(
                    success=True,
                    text="This is not valid JSON",
                )

        service = LabelTaxonomyService(BadJsonClient())  # type: ignore[arg-type]

        assignments = await service.assign_labels(
            db_session, test_project_with_taxonomy.id
        )

        assert len(assignments) == 1
        assert assignments[0].success is False
        assert "JSON parse error" in (assignments[0].error or "")


class TestTaxonomyDataclass:
    """Tests for taxonomy dataclasses."""

    def test_taxonomy_label_dataclass(self) -> None:
        """Test TaxonomyLabel dataclass."""
        label = TaxonomyLabel(
            name="product-listing",
            description="Pages showing products",
            examples=["/collections/*"],
        )

        assert label.name == "product-listing"
        assert label.description == "Pages showing products"
        assert label.examples == ["/collections/*"]

    def test_generated_taxonomy_dataclass(self) -> None:
        """Test GeneratedTaxonomy dataclass."""
        labels = [
            TaxonomyLabel(name="l1", description="d1", examples=[]),
            TaxonomyLabel(name="l2", description="d2", examples=[]),
        ]
        taxonomy = GeneratedTaxonomy(labels=labels, reasoning="Test reasoning")

        assert len(taxonomy.labels) == 2
        assert taxonomy.reasoning == "Test reasoning"


class TestValidationResultErrorMessages:
    """Tests for LabelValidationResult.error_messages property."""

    def test_error_messages_property(self) -> None:
        """Test that error_messages property returns list of message strings."""
        taxonomy = {"label-1"}
        labels = ["invalid-label"]  # 1 invalid label, also too few

        result = validate_labels(labels, taxonomy)

        assert result.valid is False
        messages = result.error_messages
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert all(isinstance(m, str) for m in messages)

    def test_empty_error_messages_for_valid_result(self) -> None:
        """Test that error_messages is empty for valid result."""
        taxonomy = {"label-1", "label-2"}
        labels = ["label-1", "label-2"]

        result = validate_labels(labels, taxonomy)

        assert result.valid is True
        assert result.error_messages == []
