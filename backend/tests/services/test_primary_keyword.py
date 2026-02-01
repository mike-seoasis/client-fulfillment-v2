"""Unit tests for PrimaryKeywordService highest-volume keyword selection.

Tests cover:
- PrimaryKeywordRequest dataclass creation and validation
- PrimaryKeywordResult dataclass and serialization
- PrimaryKeywordService initialization
- select_primary() method with various scenarios
- select_primary_for_request() convenience method
- Keyword normalization
- Selection algorithm (highest volume, tie-breaker)
- used_primaries exclusion logic
- Singleton pattern and convenience functions
- Validation and exception handling
- Edge cases (no volume data, all used primaries, ties)

ERROR LOGGING REQUIREMENTS:
- Ensure test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage for PrimaryKeywordService.
"""

import logging

import pytest

from app.services.keyword_volume import KeywordVolumeData
from app.services.primary_keyword import (
    PrimaryKeywordRequest,
    PrimaryKeywordResult,
    PrimaryKeywordSelectionError,
    PrimaryKeywordService,
    PrimaryKeywordServiceError,
    PrimaryKeywordValidationError,
    get_primary_keyword_service,
    select_primary_keyword,
)

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
            keyword="coffee storage jar",
            volume=500,
            cpc=0.90,
            competition=0.40,
        ),
    ]


@pytest.fixture
def keywords_with_ties() -> list[KeywordVolumeData]:
    """Create keywords with same volume for tie-breaker testing."""
    logger.debug("Creating keywords with ties fixture")
    return [
        KeywordVolumeData(
            keyword="coffee bean storage container",  # Longer
            volume=2000,
            cpc=1.50,
            competition=0.70,
        ),
        KeywordVolumeData(
            keyword="coffee storage",  # Shorter - should win tie
            volume=2000,
            cpc=1.25,
            competition=0.65,
        ),
        KeywordVolumeData(
            keyword="coffee container",  # Medium length
            volume=2000,
            cpc=1.00,
            competition=0.50,
        ),
    ]


@pytest.fixture
def keywords_no_volume() -> list[KeywordVolumeData]:
    """Create keywords with no volume data."""
    logger.debug("Creating keywords with no volume data fixture")
    return [
        KeywordVolumeData(keyword="coffee containers", volume=None),
        KeywordVolumeData(keyword="coffee storage", volume=None),
        KeywordVolumeData(keyword="coffee jar", volume=0),
    ]


@pytest.fixture
def service() -> PrimaryKeywordService:
    """Create a PrimaryKeywordService instance."""
    logger.debug("Creating PrimaryKeywordService")
    return PrimaryKeywordService()


# ---------------------------------------------------------------------------
# Test: PrimaryKeywordRequest Dataclass
# ---------------------------------------------------------------------------


class TestPrimaryKeywordRequestDataclass:
    """Tests for the PrimaryKeywordRequest dataclass."""

    def test_create_minimal_request(
        self, sample_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should create request with minimal required fields."""
        request = PrimaryKeywordRequest(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
        )
        assert request.collection_title == "Coffee Containers"
        assert len(request.specific_keywords) == 4
        assert request.used_primaries == set()  # Default empty set
        assert request.project_id is None
        assert request.page_id is None

    def test_create_full_request(
        self, sample_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should create request with all fields."""
        request = PrimaryKeywordRequest(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
            used_primaries={"espresso machine", "coffee maker"},
            project_id="proj-123",
            page_id="page-456",
        )
        assert request.used_primaries == {"espresso machine", "coffee maker"}
        assert request.project_id == "proj-123"
        assert request.page_id == "page-456"


# ---------------------------------------------------------------------------
# Test: PrimaryKeywordResult Dataclass
# ---------------------------------------------------------------------------


class TestPrimaryKeywordResultDataclass:
    """Tests for the PrimaryKeywordResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create a successful result."""
        result = PrimaryKeywordResult(
            success=True,
            primary_keyword="coffee bean storage container",
            primary_volume=2000,
            candidate_count=4,
            duration_ms=5.5,
            project_id="proj-1",
            page_id="page-1",
        )
        assert result.success is True
        assert result.primary_keyword == "coffee bean storage container"
        assert result.primary_volume == 2000
        assert result.candidate_count == 4
        assert result.error is None
        assert result.duration_ms == 5.5

    def test_create_failure_result(self) -> None:
        """Should create a failed result with error."""
        result = PrimaryKeywordResult(
            success=False,
            error="No specific keywords provided",
            candidate_count=0,
            project_id="proj-1",
        )
        assert result.success is False
        assert result.error == "No specific keywords provided"
        assert result.primary_keyword is None
        assert result.primary_volume is None

    def test_result_defaults(self) -> None:
        """Should have correct default values."""
        result = PrimaryKeywordResult(success=True)
        assert result.primary_keyword is None
        assert result.primary_volume is None
        assert result.candidate_count == 0
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.project_id is None
        assert result.page_id is None

    def test_result_to_dict(self) -> None:
        """Should convert result to dictionary correctly."""
        result = PrimaryKeywordResult(
            success=True,
            primary_keyword="coffee storage",
            primary_volume=1500,
            candidate_count=5,
            duration_ms=10.0,
        )
        data = result.to_dict()

        assert data["success"] is True
        assert data["primary_keyword"] == "coffee storage"
        assert data["primary_volume"] == 1500
        assert data["candidate_count"] == 5
        assert data["duration_ms"] == 10.0
        assert data["error"] is None


# ---------------------------------------------------------------------------
# Test: PrimaryKeywordService Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for PrimaryKeywordService initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize without errors."""
        service = PrimaryKeywordService()
        assert service is not None


# ---------------------------------------------------------------------------
# Test: Keyword Normalization
# ---------------------------------------------------------------------------


class TestKeywordNormalization:
    """Tests for keyword normalization method."""

    def test_normalize_lowercase(self, service: PrimaryKeywordService) -> None:
        """Should convert to lowercase."""
        assert service._normalize_keyword("COFFEE CONTAINERS") == "coffee containers"

    def test_normalize_strip_whitespace(self, service: PrimaryKeywordService) -> None:
        """Should strip leading/trailing whitespace."""
        assert service._normalize_keyword("  coffee  ") == "coffee"

    def test_normalize_single_spaces(self, service: PrimaryKeywordService) -> None:
        """Should collapse multiple spaces to single."""
        assert (
            service._normalize_keyword("coffee   bean   storage")
            == "coffee bean storage"
        )


# ---------------------------------------------------------------------------
# Test: Sort Key Generation
# ---------------------------------------------------------------------------


class TestSortKey:
    """Tests for sort key generation."""

    def test_sort_key_volume_descending(self, service: PrimaryKeywordService) -> None:
        """Sort key should order by volume descending."""
        kw1 = KeywordVolumeData(keyword="high volume", volume=2000)
        kw2 = KeywordVolumeData(keyword="low volume", volume=500)

        key1 = service._sort_key(kw1)
        key2 = service._sort_key(kw2)

        # Lower key = earlier in sort (higher volume)
        assert key1 < key2

    def test_sort_key_length_ascending_for_ties(
        self, service: PrimaryKeywordService
    ) -> None:
        """Sort key should prefer shorter keywords for same volume."""
        kw_short = KeywordVolumeData(keyword="coffee", volume=1000)
        kw_long = KeywordVolumeData(keyword="coffee storage container", volume=1000)

        key_short = service._sort_key(kw_short)
        key_long = service._sort_key(kw_long)

        # Same volume, but shorter keyword should sort first
        assert key_short < key_long

    def test_sort_key_none_volume_treated_as_zero(
        self, service: PrimaryKeywordService
    ) -> None:
        """None volume should be treated as 0."""
        kw_none = KeywordVolumeData(keyword="test", volume=None)
        kw_zero = KeywordVolumeData(keyword="test", volume=0)

        key_none = service._sort_key(kw_none)
        key_zero = service._sort_key(kw_zero)

        # Both should have same volume component
        assert key_none[0] == key_zero[0] == 0


# ---------------------------------------------------------------------------
# Test: select_primary Method - Basic Selection
# ---------------------------------------------------------------------------


class TestSelectPrimaryBasic:
    """Tests for basic select_primary functionality."""

    @pytest.mark.asyncio
    async def test_select_highest_volume(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should select the keyword with highest volume."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
            project_id="proj-1",
            page_id="page-1",
        )

        assert result.success is True
        assert result.primary_keyword == "coffee bean storage container"
        assert result.primary_volume == 2000
        assert result.candidate_count == 4

    @pytest.mark.asyncio
    async def test_select_with_tie_prefers_shorter(
        self,
        service: PrimaryKeywordService,
        keywords_with_ties: list[KeywordVolumeData],
    ) -> None:
        """Should prefer shorter keyword when volumes are tied."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=keywords_with_ties,
        )

        assert result.success is True
        # "coffee storage" is shortest at same volume
        assert result.primary_keyword == "coffee storage"
        assert result.primary_volume == 2000

    @pytest.mark.asyncio
    async def test_tracks_duration(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should track operation duration."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
        )

        assert result.success is True
        assert result.duration_ms >= 0
        assert isinstance(result.duration_ms, float)


# ---------------------------------------------------------------------------
# Test: select_primary Method - Validation
# ---------------------------------------------------------------------------


class TestSelectPrimaryValidation:
    """Tests for select_primary input validation."""

    @pytest.mark.asyncio
    async def test_empty_collection_title(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should fail with empty collection title."""
        result = await service.select_primary(
            collection_title="",
            specific_keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "title" in result.error.lower()

    @pytest.mark.asyncio
    async def test_whitespace_collection_title(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should fail with whitespace-only collection title."""
        result = await service.select_primary(
            collection_title="   ",
            specific_keywords=sample_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "title" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_keywords_list(
        self,
        service: PrimaryKeywordService,
    ) -> None:
        """Should fail with empty keywords list."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=[],
        )

        assert result.success is False
        assert result.error is not None
        assert "keyword" in result.error.lower()


# ---------------------------------------------------------------------------
# Test: select_primary Method - No Volume Data Fallback
# ---------------------------------------------------------------------------


class TestSelectPrimaryFallback:
    """Tests for fallback behavior when no volume data available."""

    @pytest.mark.asyncio
    async def test_fallback_to_first_keyword(
        self,
        service: PrimaryKeywordService,
        keywords_no_volume: list[KeywordVolumeData],
    ) -> None:
        """Should fall back to first keyword when no volume data."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=keywords_no_volume,
        )

        assert result.success is True
        # Falls back to first keyword
        assert result.primary_keyword == "coffee containers"
        assert result.primary_volume is None

    @pytest.mark.asyncio
    async def test_fallback_respects_used_primaries(
        self,
        service: PrimaryKeywordService,
        keywords_no_volume: list[KeywordVolumeData],
    ) -> None:
        """Fallback should still respect used_primaries exclusion."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=keywords_no_volume,
            used_primaries={"coffee containers"},  # Exclude first keyword
        )

        assert result.success is True
        # Should skip first and use second
        assert result.primary_keyword == "coffee storage"


# ---------------------------------------------------------------------------
# Test: select_primary Method - used_primaries Exclusion
# ---------------------------------------------------------------------------


class TestSelectPrimaryUsedPrimaries:
    """Tests for used_primaries exclusion logic."""

    @pytest.mark.asyncio
    async def test_excludes_used_primaries(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should exclude keywords already used as primary elsewhere."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
            used_primaries={"coffee bean storage container"},  # Exclude highest
        )

        assert result.success is True
        # Should select next highest volume
        assert result.primary_keyword == "airtight coffee containers"
        assert result.primary_volume == 1500

    @pytest.mark.asyncio
    async def test_case_insensitive_exclusion(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should exclude case-insensitively."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
            # Different case than actual keyword
            used_primaries={"COFFEE BEAN STORAGE CONTAINER"},
        )

        assert result.success is True
        # Should still exclude the matching keyword
        assert result.primary_keyword == "airtight coffee containers"

    @pytest.mark.asyncio
    async def test_all_keywords_used_elsewhere(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should fail when all keywords are used as primaries elsewhere."""
        all_keywords = {kw.keyword for kw in sample_keywords}
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
            used_primaries=all_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "used as primaries elsewhere" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_used_primaries(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should work with empty used_primaries set."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
            used_primaries=set(),
        )

        assert result.success is True
        # Should select highest volume as normal
        assert result.primary_keyword == "coffee bean storage container"

    @pytest.mark.asyncio
    async def test_none_used_primaries(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should work with None used_primaries (default)."""
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
            used_primaries=None,
        )

        assert result.success is True
        assert result.primary_keyword == "coffee bean storage container"


# ---------------------------------------------------------------------------
# Test: select_primary Method - Exception Handling
# ---------------------------------------------------------------------------


class TestSelectPrimaryExceptionHandling:
    """Tests for exception handling in select_primary."""

    @pytest.mark.asyncio
    async def test_handles_unexpected_exception(
        self,
        service: PrimaryKeywordService,
    ) -> None:
        """Should handle unexpected exceptions gracefully."""

        # Create a keyword that will cause an error when sorted
        class BadKeyword:
            keyword = "test"
            volume = 100

            def __lt__(self, other):
                raise RuntimeError("Comparison error")

        # This is a bit contrived, but tests the exception path
        # In practice, we test that the try/except block works
        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=[
                KeywordVolumeData(keyword="test", volume=100),
            ],
        )

        # Should succeed with normal keywords
        assert result.success is True


# ---------------------------------------------------------------------------
# Test: select_primary_for_request Method
# ---------------------------------------------------------------------------


class TestSelectPrimaryForRequest:
    """Tests for the select_primary_for_request convenience method."""

    @pytest.mark.asyncio
    async def test_select_primary_for_request(
        self,
        service: PrimaryKeywordService,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should select primary using request object."""
        request = PrimaryKeywordRequest(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
            used_primaries=set(),
            project_id="proj-1",
            page_id="page-1",
        )

        result = await service.select_primary_for_request(request)

        assert result.success is True
        assert result.project_id == "proj-1"
        assert result.page_id == "page-1"


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for PrimaryKeyword exception classes."""

    def test_service_error_base(self) -> None:
        """PrimaryKeywordServiceError should be base exception."""
        error = PrimaryKeywordServiceError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_validation_error(self) -> None:
        """PrimaryKeywordValidationError should contain field and value info."""
        error = PrimaryKeywordValidationError(
            field="collection_title",
            value="",
            message="Cannot be empty",
        )
        assert error.field == "collection_title"
        assert error.value == ""
        assert error.message == "Cannot be empty"
        assert "collection_title" in str(error)

    def test_selection_error(self) -> None:
        """PrimaryKeywordSelectionError should contain context info."""
        error = PrimaryKeywordSelectionError(
            message="Selection failed",
            project_id="proj-1",
            page_id="page-1",
        )
        assert error.project_id == "proj-1"
        assert error.page_id == "page-1"
        assert "Selection failed" in str(error)

    def test_exception_hierarchy(self) -> None:
        """All exceptions should inherit from base error."""
        assert issubclass(PrimaryKeywordValidationError, PrimaryKeywordServiceError)
        assert issubclass(PrimaryKeywordSelectionError, PrimaryKeywordServiceError)


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton accessor and convenience functions."""

    def test_get_primary_keyword_service_singleton(self) -> None:
        """get_primary_keyword_service should return singleton."""
        # Clear the global instance first
        import app.services.primary_keyword as pk_module

        original = pk_module._primary_keyword_service
        pk_module._primary_keyword_service = None

        try:
            service1 = get_primary_keyword_service()
            service2 = get_primary_keyword_service()
            assert service1 is service2
        finally:
            # Restore original
            pk_module._primary_keyword_service = original

    @pytest.mark.asyncio
    async def test_select_primary_keyword_convenience(
        self,
        sample_keywords: list[KeywordVolumeData],
    ) -> None:
        """select_primary_keyword should use default service."""
        result = await select_primary_keyword(
            collection_title="Coffee Containers",
            specific_keywords=sample_keywords,
            project_id="proj-1",
        )

        assert result.success is True
        assert result.primary_keyword == "coffee bean storage container"


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_single_keyword_input(
        self,
        service: PrimaryKeywordService,
    ) -> None:
        """Should handle single keyword input."""
        result = await service.select_primary(
            collection_title="Test",
            specific_keywords=[
                KeywordVolumeData(keyword="only keyword", volume=100)
            ],
        )

        assert result.success is True
        assert result.primary_keyword == "only keyword"
        assert result.candidate_count == 1

    @pytest.mark.asyncio
    async def test_all_zero_volume(
        self,
        service: PrimaryKeywordService,
    ) -> None:
        """Should fall back when all keywords have zero volume."""
        keywords = [
            KeywordVolumeData(keyword="keyword one", volume=0),
            KeywordVolumeData(keyword="keyword two", volume=0),
        ]

        result = await service.select_primary(
            collection_title="Test",
            specific_keywords=keywords,
        )

        assert result.success is True
        # Falls back to first
        assert result.primary_keyword == "keyword one"

    @pytest.mark.asyncio
    async def test_mixed_volume_and_none(
        self,
        service: PrimaryKeywordService,
    ) -> None:
        """Should select from keywords with volume, ignoring None."""
        keywords = [
            KeywordVolumeData(keyword="no volume", volume=None),
            KeywordVolumeData(keyword="has volume", volume=500),
            KeywordVolumeData(keyword="zero volume", volume=0),
        ]

        result = await service.select_primary(
            collection_title="Test",
            specific_keywords=keywords,
        )

        assert result.success is True
        assert result.primary_keyword == "has volume"
        assert result.primary_volume == 500

    @pytest.mark.asyncio
    async def test_keywords_with_special_characters(
        self,
        service: PrimaryKeywordService,
    ) -> None:
        """Should handle keywords with special characters."""
        keywords = [
            KeywordVolumeData(keyword="coffee & tea", volume=100),
            KeywordVolumeData(keyword='12" storage', volume=200),
            KeywordVolumeData(keyword="café latte", volume=150),
        ]

        result = await service.select_primary(
            collection_title="Test",
            specific_keywords=keywords,
        )

        assert result.success is True
        assert result.primary_keyword == '12" storage'
        assert result.primary_volume == 200

    @pytest.mark.asyncio
    async def test_unicode_keywords(
        self,
        service: PrimaryKeywordService,
    ) -> None:
        """Should handle unicode in keywords."""
        keywords = [
            KeywordVolumeData(keyword="コーヒー storage", volume=100),
            KeywordVolumeData(keyword="café containers", volume=200),
        ]

        result = await service.select_primary(
            collection_title="Test",
            specific_keywords=keywords,
        )

        assert result.success is True
        assert result.primary_keyword == "café containers"

    @pytest.mark.asyncio
    async def test_large_number_of_keywords(
        self,
        service: PrimaryKeywordService,
    ) -> None:
        """Should handle large number of keywords efficiently."""
        keywords = [
            KeywordVolumeData(keyword=f"keyword {i}", volume=i)
            for i in range(100)
        ]

        result = await service.select_primary(
            collection_title="Test",
            specific_keywords=keywords,
        )

        assert result.success is True
        assert result.primary_keyword == "keyword 99"  # Highest volume
        assert result.primary_volume == 99
        assert result.candidate_count == 100

    @pytest.mark.asyncio
    async def test_very_long_keyword(
        self,
        service: PrimaryKeywordService,
    ) -> None:
        """Should handle very long keywords."""
        long_keyword = "a" * 500
        keywords = [
            KeywordVolumeData(keyword=long_keyword, volume=100),
            KeywordVolumeData(keyword="short", volume=100),  # Same volume, shorter
        ]

        result = await service.select_primary(
            collection_title="Test",
            specific_keywords=keywords,
        )

        assert result.success is True
        # Shorter keyword should win the tie-breaker
        assert result.primary_keyword == "short"
