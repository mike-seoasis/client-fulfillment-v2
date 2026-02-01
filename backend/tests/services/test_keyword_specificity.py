"""Unit tests for KeywordSpecificityService LLM-based keyword filtering.

Tests cover:
- SpecificityFilterRequest dataclass creation and validation
- SpecificityFilterResult dataclass and serialization
- KeywordSpecificityService initialization
- filter_keywords() method with various scenarios
- filter_keywords_for_request() convenience method
- Keyword normalization
- LLM response parsing (JSON, markdown code blocks)
- Singleton pattern and convenience functions
- Validation and exception handling
- Edge cases (empty inputs, invalid responses)

ERROR LOGGING REQUIREMENTS:
- Ensure test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage for KeywordSpecificityService.
"""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.keyword_specificity import (
    KeywordSpecificityFilterError,
    KeywordSpecificityService,
    KeywordSpecificityServiceError,
    KeywordSpecificityValidationError,
    SpecificityFilterRequest,
    SpecificityFilterResult,
    filter_keywords_by_specificity,
    get_keyword_specificity_service,
)
from app.services.keyword_volume import KeywordVolumeData

# Enable debug logging for test visibility
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_keywords() -> list[KeywordVolumeData]:
    """Create a set of sample keywords with volume data for testing."""
    logger.debug("Creating sample keywords fixture")
    return [
        KeywordVolumeData(
            keyword="airtight coffee containers",
            volume=1500,
            cpc=1.25,
            competition=0.65,
        ),
        KeywordVolumeData(
            keyword="kitchen storage",
            volume=5000,
            cpc=0.85,
            competition=0.45,
        ),
        KeywordVolumeData(
            keyword="coffee bean storage container",
            volume=2000,
            cpc=1.50,
            competition=0.70,
        ),
        KeywordVolumeData(
            keyword="vacuum coffee canister",
            volume=800,
            cpc=1.75,
            competition=0.55,
        ),
        KeywordVolumeData(
            keyword="food containers",
            volume=3000,
            cpc=0.60,
            competition=0.35,
        ),
    ]


@pytest.fixture
def mock_claude_response() -> MagicMock:
    """Create a mock Claude response with specific keywords."""
    logger.debug("Creating mock Claude response fixture")
    response = MagicMock()
    response.success = True
    response.text = json.dumps([
        "airtight coffee containers",
        "coffee bean storage container",
        "vacuum coffee canister",
    ])
    response.error = None
    response.status_code = 200
    response.input_tokens = 500
    response.output_tokens = 50
    response.request_id = "req-test-123"
    return response


@pytest.fixture
def mock_claude_client(mock_claude_response: MagicMock) -> AsyncMock:
    """Create a mock Claude client."""
    logger.debug("Creating mock Claude client fixture")
    client = AsyncMock()
    client.available = True
    client.complete = AsyncMock(return_value=mock_claude_response)
    return client


# ---------------------------------------------------------------------------
# Test: SpecificityFilterRequest Dataclass
# ---------------------------------------------------------------------------


class TestSpecificityFilterRequestDataclass:
    """Tests for the SpecificityFilterRequest dataclass."""

    def test_create_minimal_request(
        self, sample_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should create request with minimal required fields."""
        request = SpecificityFilterRequest(
            collection_title="Coffee Containers",
            url="https://example.com/collections/coffee",
            content_excerpt="Airtight coffee storage containers",
            keywords=sample_keywords,
        )
        assert request.collection_title == "Coffee Containers"
        assert request.url == "https://example.com/collections/coffee"
        assert request.content_excerpt == "Airtight coffee storage containers"
        assert len(request.keywords) == 5
        assert request.project_id is None
        assert request.page_id is None

    def test_create_full_request(
        self, sample_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should create request with all fields."""
        request = SpecificityFilterRequest(
            collection_title="Coffee Containers",
            url="https://example.com/collections/coffee",
            content_excerpt="Airtight coffee storage containers",
            keywords=sample_keywords,
            project_id="proj-123",
            page_id="page-456",
        )
        assert request.project_id == "proj-123"
        assert request.page_id == "page-456"


# ---------------------------------------------------------------------------
# Test: SpecificityFilterResult Dataclass
# ---------------------------------------------------------------------------


class TestSpecificityFilterResultDataclass:
    """Tests for the SpecificityFilterResult dataclass."""

    def test_create_success_result(
        self, sample_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should create a successful result."""
        specific_keywords = sample_keywords[:3]
        result = SpecificityFilterResult(
            success=True,
            specific_keywords=specific_keywords,
            filtered_count=3,
            original_count=5,
            filter_rate=0.4,
            duration_ms=150.5,
            input_tokens=500,
            output_tokens=50,
            request_id="req-123",
            project_id="proj-1",
            page_id="page-1",
        )
        assert result.success is True
        assert len(result.specific_keywords) == 3
        assert result.filtered_count == 3
        assert result.original_count == 5
        assert result.filter_rate == 0.4
        assert result.error is None
        assert result.duration_ms == 150.5
        assert result.input_tokens == 500
        assert result.output_tokens == 50
        assert result.request_id == "req-123"

    def test_create_failure_result(self) -> None:
        """Should create a failed result with error."""
        result = SpecificityFilterResult(
            success=False,
            error="Claude LLM not available",
            original_count=5,
            project_id="proj-1",
        )
        assert result.success is False
        assert result.error == "Claude LLM not available"
        assert result.specific_keywords == []
        assert result.filtered_count == 0

    def test_result_defaults(self) -> None:
        """Should have correct default values."""
        result = SpecificityFilterResult(success=True)
        assert result.specific_keywords == []
        assert result.filtered_count == 0
        assert result.original_count == 0
        assert result.filter_rate == 0.0
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.input_tokens is None
        assert result.output_tokens is None
        assert result.request_id is None
        assert result.project_id is None
        assert result.page_id is None

    def test_result_to_dict(
        self, sample_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should convert result to dictionary correctly."""
        result = SpecificityFilterResult(
            success=True,
            specific_keywords=sample_keywords[:2],
            filtered_count=2,
            original_count=5,
            filter_rate=0.6,
            duration_ms=100.0,
            input_tokens=500,
            output_tokens=50,
            request_id="req-123",
        )
        data = result.to_dict()

        assert data["success"] is True
        assert len(data["specific_keywords"]) == 2
        assert data["specific_keywords"][0]["keyword"] == "airtight coffee containers"
        assert data["specific_keywords"][0]["volume"] == 1500
        assert data["filtered_count"] == 2
        assert data["original_count"] == 5
        assert data["filter_rate"] == 0.6
        assert data["duration_ms"] == 100.0
        assert data["input_tokens"] == 500
        assert data["output_tokens"] == 50
        assert data["request_id"] == "req-123"


# ---------------------------------------------------------------------------
# Test: KeywordSpecificityService Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for KeywordSpecificityService initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize with default values."""
        service = KeywordSpecificityService()
        assert service._claude_client is None

    def test_custom_client_initialization(
        self, mock_claude_client: AsyncMock
    ) -> None:
        """Should accept custom Claude client."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)
        assert service._claude_client is mock_claude_client


# ---------------------------------------------------------------------------
# Test: Keyword Normalization
# ---------------------------------------------------------------------------


class TestKeywordNormalization:
    """Tests for keyword normalization method."""

    def test_normalize_lowercase(self) -> None:
        """Should convert to lowercase."""
        service = KeywordSpecificityService()
        assert service._normalize_keyword("COFFEE CONTAINERS") == "coffee containers"

    def test_normalize_strip_whitespace(self) -> None:
        """Should strip leading/trailing whitespace."""
        service = KeywordSpecificityService()
        assert service._normalize_keyword("  coffee  ") == "coffee"

    def test_normalize_single_spaces(self) -> None:
        """Should collapse multiple spaces to single."""
        service = KeywordSpecificityService()
        assert (
            service._normalize_keyword("coffee   bean   storage")
            == "coffee bean storage"
        )

    def test_normalize_combined(self) -> None:
        """Should handle all normalization together."""
        service = KeywordSpecificityService()
        assert (
            service._normalize_keyword("  COFFEE   BEAN   Storage  ")
            == "coffee bean storage"
        )


# ---------------------------------------------------------------------------
# Test: Prompt Building
# ---------------------------------------------------------------------------


class TestPromptBuilding:
    """Tests for prompt building functionality."""

    def test_build_prompt_basic(
        self, sample_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should build system and user prompts correctly."""
        service = KeywordSpecificityService()
        system_prompt, user_prompt = service._build_prompt(
            collection_title="Coffee Containers",
            url="https://example.com/collections/coffee",
            content_excerpt="Airtight coffee storage containers",
            keywords=sample_keywords,
            project_id="proj-1",
            page_id="page-1",
        )

        assert "SPECIFIC" in system_prompt
        assert "GENERIC" in system_prompt
        assert "Coffee Containers" in user_prompt
        assert "https://example.com/collections/coffee" in user_prompt
        assert "airtight coffee containers" in user_prompt

    def test_build_prompt_truncates_long_excerpt(
        self, sample_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should truncate long content excerpts."""
        service = KeywordSpecificityService()
        long_excerpt = "x" * 2000

        system_prompt, user_prompt = service._build_prompt(
            collection_title="Test",
            url="https://example.com",
            content_excerpt=long_excerpt,
            keywords=sample_keywords,
        )

        # Should be truncated to 1500 chars + "..."
        assert "..." in user_prompt
        # The full 2000 char excerpt should not be present
        assert "x" * 2000 not in user_prompt


# ---------------------------------------------------------------------------
# Test: filter_keywords Method
# ---------------------------------------------------------------------------


class TestFilterKeywords:
    """Tests for the filter_keywords method."""

    @pytest.mark.asyncio
    async def test_filter_keywords_success(
        self,
        sample_keywords: list[KeywordVolumeData],
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should filter keywords successfully."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com/collections/coffee",
            content_excerpt="Airtight coffee storage containers",
            keywords=sample_keywords,
            project_id="proj-1",
            page_id="page-1",
        )

        assert result.success is True
        assert result.filtered_count == 3
        assert result.original_count == 5
        assert result.filter_rate == 0.4
        assert len(result.specific_keywords) == 3

        # Verify the correct keywords were preserved
        specific_kw_texts = [kw.keyword for kw in result.specific_keywords]
        assert "airtight coffee containers" in specific_kw_texts
        assert "coffee bean storage container" in specific_kw_texts
        assert "vacuum coffee canister" in specific_kw_texts

    @pytest.mark.asyncio
    async def test_filter_keywords_empty_title(
        self,
        sample_keywords: list[KeywordVolumeData],
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should fail with empty collection title."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "empty" in result.error.lower() or "title" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filter_keywords_whitespace_title(
        self,
        sample_keywords: list[KeywordVolumeData],
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should fail with whitespace-only collection title."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="   ",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "title" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filter_keywords_empty_url(
        self,
        sample_keywords: list[KeywordVolumeData],
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should fail with empty URL."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "url" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filter_keywords_empty_keywords(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should fail with empty keywords list."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=[],
        )

        assert result.success is False
        assert result.error is not None
        assert "keyword" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filter_keywords_claude_unavailable(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should fail gracefully when Claude is unavailable."""
        mock_client = AsyncMock()
        mock_client.available = False
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "unavailable" in result.error.lower() or "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filter_keywords_llm_failure(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should handle LLM request failure."""
        mock_response = MagicMock()
        mock_response.success = False
        mock_response.text = None
        mock_response.error = "Rate limit exceeded"
        mock_response.status_code = 429
        mock_response.input_tokens = 0
        mock_response.output_tokens = 0
        mock_response.request_id = "req-fail"

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(return_value=mock_response)
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "Rate limit exceeded" in result.error

    @pytest.mark.asyncio
    async def test_filter_keywords_json_code_block(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should extract JSON from markdown code block."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = '```json\n["airtight coffee containers"]\n```'
        mock_response.error = None
        mock_response.status_code = 200
        mock_response.input_tokens = 500
        mock_response.output_tokens = 50
        mock_response.request_id = "req-123"

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(return_value=mock_response)
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is True
        assert result.filtered_count == 1
        assert result.specific_keywords[0].keyword == "airtight coffee containers"

    @pytest.mark.asyncio
    async def test_filter_keywords_generic_code_block(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should extract JSON from generic code block."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = '```\n["airtight coffee containers"]\n```'
        mock_response.error = None
        mock_response.status_code = 200
        mock_response.input_tokens = 500
        mock_response.output_tokens = 50
        mock_response.request_id = "req-123"

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(return_value=mock_response)
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is True
        assert result.filtered_count == 1

    @pytest.mark.asyncio
    async def test_filter_keywords_invalid_json(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should handle invalid JSON response."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = "not valid json at all"
        mock_response.error = None
        mock_response.status_code = 200
        mock_response.input_tokens = 500
        mock_response.output_tokens = 50
        mock_response.request_id = "req-123"

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(return_value=mock_response)
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "JSON" in result.error

    @pytest.mark.asyncio
    async def test_filter_keywords_non_list_response(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should handle non-list JSON response."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = '{"keywords": ["test"]}'  # Object, not list
        mock_response.error = None
        mock_response.status_code = 200
        mock_response.input_tokens = 500
        mock_response.output_tokens = 50
        mock_response.request_id = "req-123"

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(return_value=mock_response)
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "list" in result.error.lower()

    @pytest.mark.asyncio
    async def test_filter_keywords_preserves_volume_data(
        self,
        sample_keywords: list[KeywordVolumeData],
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should preserve volume data from original keywords."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is True
        # Find the airtight coffee containers keyword
        airtight_kw = next(
            kw for kw in result.specific_keywords
            if kw.keyword == "airtight coffee containers"
        )
        assert airtight_kw.volume == 1500
        assert airtight_kw.cpc == 1.25
        assert airtight_kw.competition == 0.65

    @pytest.mark.asyncio
    async def test_filter_keywords_case_insensitive_matching(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should match keywords case-insensitively."""
        mock_response = MagicMock()
        mock_response.success = True
        # LLM returns with different casing
        mock_response.text = '["AIRTIGHT COFFEE CONTAINERS"]'
        mock_response.error = None
        mock_response.status_code = 200
        mock_response.input_tokens = 500
        mock_response.output_tokens = 50
        mock_response.request_id = "req-123"

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(return_value=mock_response)
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is True
        assert result.filtered_count == 1
        # Should match and preserve original keyword
        assert result.specific_keywords[0].keyword == "airtight coffee containers"

    @pytest.mark.asyncio
    async def test_filter_keywords_unmatched_llm_keywords(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should handle keywords from LLM that don't match input."""
        mock_response = MagicMock()
        mock_response.success = True
        # LLM returns a keyword that wasn't in the input
        mock_response.text = '["airtight coffee containers", "imaginary keyword"]'
        mock_response.error = None
        mock_response.status_code = 200
        mock_response.input_tokens = 500
        mock_response.output_tokens = 50
        mock_response.request_id = "req-123"

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(return_value=mock_response)
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is True
        # Only the matching keyword should be in the result
        assert result.filtered_count == 1
        assert result.specific_keywords[0].keyword == "airtight coffee containers"

    @pytest.mark.asyncio
    async def test_filter_keywords_empty_llm_response(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should handle empty list from LLM (all keywords filtered)."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = "[]"
        mock_response.error = None
        mock_response.status_code = 200
        mock_response.input_tokens = 500
        mock_response.output_tokens = 10
        mock_response.request_id = "req-123"

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(return_value=mock_response)
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is True
        assert result.filtered_count == 0
        assert result.filter_rate == 1.0  # All filtered out
        assert result.specific_keywords == []

    @pytest.mark.asyncio
    async def test_filter_keywords_tracks_duration(
        self,
        sample_keywords: list[KeywordVolumeData],
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should track operation duration."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is True
        assert result.duration_ms >= 0
        assert isinstance(result.duration_ms, float)

    @pytest.mark.asyncio
    async def test_filter_keywords_exception_handling(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should handle unexpected exceptions gracefully."""
        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "Unexpected error" in result.error


# ---------------------------------------------------------------------------
# Test: filter_keywords_for_request Method
# ---------------------------------------------------------------------------


class TestFilterKeywordsForRequest:
    """Tests for the filter_keywords_for_request convenience method."""

    @pytest.mark.asyncio
    async def test_filter_keywords_for_request(
        self,
        sample_keywords: list[KeywordVolumeData],
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should filter keywords using request object."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)
        request = SpecificityFilterRequest(
            collection_title="Coffee Containers",
            url="https://example.com/collections/coffee",
            content_excerpt="Airtight coffee storage containers",
            keywords=sample_keywords,
            project_id="proj-1",
            page_id="page-1",
        )

        result = await service.filter_keywords_for_request(request)

        assert result.success is True
        assert result.project_id == "proj-1"
        assert result.page_id == "page-1"


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for KeywordSpecificity exception classes."""

    def test_service_error_base(self) -> None:
        """KeywordSpecificityServiceError should be base exception."""
        error = KeywordSpecificityServiceError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_validation_error(self) -> None:
        """KeywordSpecificityValidationError should contain field and value info."""
        error = KeywordSpecificityValidationError(
            field="collection_title",
            value="",
            message="Cannot be empty",
        )
        assert error.field == "collection_title"
        assert error.value == ""
        assert error.message == "Cannot be empty"
        assert "collection_title" in str(error)

    def test_filter_error(self) -> None:
        """KeywordSpecificityFilterError should contain context info."""
        error = KeywordSpecificityFilterError(
            message="Filter failed",
            project_id="proj-1",
            page_id="page-1",
        )
        assert error.project_id == "proj-1"
        assert error.page_id == "page-1"
        assert "Filter failed" in str(error)

    def test_exception_hierarchy(self) -> None:
        """All exceptions should inherit from base error."""
        assert issubclass(KeywordSpecificityValidationError, KeywordSpecificityServiceError)
        assert issubclass(KeywordSpecificityFilterError, KeywordSpecificityServiceError)


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton accessor and convenience functions."""

    def test_get_keyword_specificity_service_singleton(self) -> None:
        """get_keyword_specificity_service should return singleton."""
        # Clear the global instance first
        import app.services.keyword_specificity as ks_module

        original = ks_module._keyword_specificity_service
        ks_module._keyword_specificity_service = None

        try:
            service1 = get_keyword_specificity_service()
            service2 = get_keyword_specificity_service()
            assert service1 is service2
        finally:
            # Restore original
            ks_module._keyword_specificity_service = original

    @pytest.mark.asyncio
    async def test_filter_keywords_by_specificity_convenience(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """filter_keywords_by_specificity should use default service."""
        # We need to patch the Claude client used by the singleton
        with patch("app.services.keyword_specificity.get_claude") as mock_get_claude:
            mock_response = MagicMock()
            mock_response.success = True
            mock_response.text = '["airtight coffee containers"]'
            mock_response.error = None
            mock_response.status_code = 200
            mock_response.input_tokens = 500
            mock_response.output_tokens = 50
            mock_response.request_id = "req-123"

            mock_client = AsyncMock()
            mock_client.available = True
            mock_client.complete = AsyncMock(return_value=mock_response)
            mock_get_claude.return_value = mock_client

            result = await filter_keywords_by_specificity(
                collection_title="Coffee Containers",
                url="https://example.com",
                content_excerpt="Content",
                keywords=sample_keywords,
                project_id="proj-1",
            )

            assert result.success is True


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_single_keyword_input(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should handle single keyword input."""
        mock_claude_client.complete.return_value.text = '["single keyword"]'
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="Test",
            url="https://example.com",
            content_excerpt="Content",
            keywords=[KeywordVolumeData(keyword="single keyword", volume=100)],
        )

        assert result.success is True
        assert result.original_count == 1

    @pytest.mark.asyncio
    async def test_keywords_with_special_characters(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should handle keywords with special characters."""
        keywords = [
            KeywordVolumeData(keyword="coffee & tea containers", volume=100),
            KeywordVolumeData(keyword='12" storage jar', volume=200),
            KeywordVolumeData(keyword="café storage", volume=150),
        ]
        mock_claude_client.complete.return_value.text = '["coffee & tea containers"]'
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="Test",
            url="https://example.com",
            content_excerpt="Content",
            keywords=keywords,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_keywords_with_none_values(
        self,
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should handle keywords with None volume values."""
        keywords = [
            KeywordVolumeData(keyword="airtight containers", volume=None),
            KeywordVolumeData(keyword="coffee storage", volume=100),
        ]
        mock_claude_client.complete.return_value.text = '["airtight containers"]'
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="Test",
            url="https://example.com",
            content_excerpt="Content",
            keywords=keywords,
        )

        assert result.success is True
        # Should preserve the None volume
        assert result.specific_keywords[0].volume is None

    @pytest.mark.asyncio
    async def test_llm_response_with_non_string_items(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should skip non-string items in LLM response."""
        mock_response = MagicMock()
        mock_response.success = True
        mock_response.text = '["airtight coffee containers", null, 123, ""]'
        mock_response.error = None
        mock_response.status_code = 200
        mock_response.input_tokens = 500
        mock_response.output_tokens = 50
        mock_response.request_id = "req-123"

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.complete = AsyncMock(return_value=mock_response)
        service = KeywordSpecificityService(claude_client=mock_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="Content",
            keywords=sample_keywords,
        )

        assert result.success is True
        # Only the valid string should match
        assert result.filtered_count == 1

    @pytest.mark.asyncio
    async def test_empty_content_excerpt(
        self,
        sample_keywords: list[KeywordVolumeData],
        mock_claude_client: AsyncMock,
    ) -> None:
        """Should handle empty content excerpt."""
        service = KeywordSpecificityService(claude_client=mock_claude_client)

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com",
            content_excerpt="",
            keywords=sample_keywords,
        )

        # Should still work - content_excerpt defaults to "(no content available)"
        assert result.success is True
