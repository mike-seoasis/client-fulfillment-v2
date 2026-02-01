"""Unit tests for SecondaryKeywordService secondary keyword selection.

Tests cover:
- SecondaryKeywordRequest dataclass creation and validation
- SecondaryKeywordResult dataclass and serialization
- SecondaryKeywordService initialization
- select_secondary() method with various scenarios
- select_secondary_for_request() convenience method
- Keyword normalization
- Selection algorithm (specific + broader mix)
- used_primaries exclusion logic
- Configurable thresholds (min/max specific, min/max broader)
- Singleton pattern and convenience functions
- Validation and exception handling
- Edge cases (not enough keywords, all excluded)

ERROR LOGGING REQUIREMENTS:
- Ensure test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage for SecondaryKeywordService.
"""

import logging

import pytest

from app.services.keyword_volume import KeywordVolumeData
from app.services.secondary_keywords import (
    DEFAULT_BROADER_VOLUME_THRESHOLD,
    DEFAULT_MAX_BROADER_KEYWORDS,
    DEFAULT_MAX_SPECIFIC_KEYWORDS,
    DEFAULT_MIN_BROADER_KEYWORDS,
    DEFAULT_MIN_SPECIFIC_KEYWORDS,
    DEFAULT_TOTAL_SECONDARY_KEYWORDS,
    SecondaryKeywordRequest,
    SecondaryKeywordResult,
    SecondaryKeywordSelectionError,
    SecondaryKeywordService,
    SecondaryKeywordServiceError,
    SecondaryKeywordValidationError,
    get_secondary_keyword_service,
    select_secondary_keywords,
)

# Enable debug logging for test visibility
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def specific_keywords() -> list[KeywordVolumeData]:
    """Create specific keywords (output from Step 4)."""
    logger.debug("Creating specific keywords fixture")
    return [
        KeywordVolumeData(
            keyword="coffee bean storage container",  # Primary
            volume=2000,
            cpc=1.50,
            competition=0.70,
        ),
        KeywordVolumeData(
            keyword="airtight coffee containers",
            volume=1500,
            cpc=1.25,
            competition=0.65,
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
        KeywordVolumeData(
            keyword="sealed coffee container",
            volume=400,
            cpc=0.85,
            competition=0.35,
        ),
    ]


@pytest.fixture
def all_keywords() -> list[KeywordVolumeData]:
    """Create all keywords including broader terms."""
    logger.debug("Creating all keywords fixture")
    return [
        # Specific keywords (from Step 4)
        KeywordVolumeData(keyword="coffee bean storage container", volume=2000),
        KeywordVolumeData(keyword="airtight coffee containers", volume=1500),
        KeywordVolumeData(keyword="vacuum coffee canister", volume=800),
        KeywordVolumeData(keyword="coffee storage jar", volume=500),
        KeywordVolumeData(keyword="sealed coffee container", volume=400),
        # Broader keywords (not specific but high volume)
        KeywordVolumeData(keyword="kitchen storage", volume=5000),
        KeywordVolumeData(keyword="food containers", volume=3500),
        KeywordVolumeData(keyword="storage solutions", volume=2500),
        KeywordVolumeData(keyword="coffee accessories", volume=1500),
        # Low volume broader (below threshold)
        KeywordVolumeData(keyword="misc containers", volume=500),
    ]


@pytest.fixture
def service() -> SecondaryKeywordService:
    """Create a SecondaryKeywordService instance."""
    logger.debug("Creating SecondaryKeywordService")
    return SecondaryKeywordService()


# ---------------------------------------------------------------------------
# Test: Default Constants
# ---------------------------------------------------------------------------


class TestDefaultConstants:
    """Tests for default configuration constants."""

    def test_default_specific_keywords_range(self) -> None:
        """Should have correct default specific keyword range."""
        assert DEFAULT_MIN_SPECIFIC_KEYWORDS == 2
        assert DEFAULT_MAX_SPECIFIC_KEYWORDS == 3

    def test_default_broader_keywords_range(self) -> None:
        """Should have correct default broader keyword range."""
        assert DEFAULT_MIN_BROADER_KEYWORDS == 1
        assert DEFAULT_MAX_BROADER_KEYWORDS == 2

    def test_default_broader_volume_threshold(self) -> None:
        """Should have correct default volume threshold."""
        assert DEFAULT_BROADER_VOLUME_THRESHOLD == 1000

    def test_default_total_secondary_keywords(self) -> None:
        """Should have correct default total secondary keywords."""
        assert DEFAULT_TOTAL_SECONDARY_KEYWORDS == 5


# ---------------------------------------------------------------------------
# Test: SecondaryKeywordRequest Dataclass
# ---------------------------------------------------------------------------


class TestSecondaryKeywordRequestDataclass:
    """Tests for the SecondaryKeywordRequest dataclass."""

    def test_create_minimal_request(
        self,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should create request with minimal required fields."""
        request = SecondaryKeywordRequest(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
        )
        assert request.collection_title == "Coffee Containers"
        assert request.primary_keyword == "coffee bean storage container"
        assert len(request.specific_keywords) == 5
        assert len(request.all_keywords) == 10
        assert request.used_primaries == set()
        assert request.project_id is None
        assert request.page_id is None
        # Default thresholds
        assert request.min_specific == DEFAULT_MIN_SPECIFIC_KEYWORDS
        assert request.max_specific == DEFAULT_MAX_SPECIFIC_KEYWORDS
        assert request.min_broader == DEFAULT_MIN_BROADER_KEYWORDS
        assert request.max_broader == DEFAULT_MAX_BROADER_KEYWORDS
        assert request.broader_volume_threshold == DEFAULT_BROADER_VOLUME_THRESHOLD

    def test_create_full_request(
        self,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should create request with all fields."""
        request = SecondaryKeywordRequest(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            used_primaries={"espresso machine"},
            project_id="proj-123",
            page_id="page-456",
            min_specific=1,
            max_specific=4,
            min_broader=0,
            max_broader=3,
            broader_volume_threshold=500,
        )
        assert request.used_primaries == {"espresso machine"}
        assert request.project_id == "proj-123"
        assert request.page_id == "page-456"
        assert request.min_specific == 1
        assert request.max_specific == 4
        assert request.min_broader == 0
        assert request.max_broader == 3
        assert request.broader_volume_threshold == 500


# ---------------------------------------------------------------------------
# Test: SecondaryKeywordResult Dataclass
# ---------------------------------------------------------------------------


class TestSecondaryKeywordResultDataclass:
    """Tests for the SecondaryKeywordResult dataclass."""

    def test_create_success_result(
        self, specific_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should create a successful result."""
        result = SecondaryKeywordResult(
            success=True,
            secondary_keywords=specific_keywords[:3],
            specific_count=2,
            broader_count=1,
            total_count=3,
            duration_ms=5.5,
            project_id="proj-1",
            page_id="page-1",
        )
        assert result.success is True
        assert len(result.secondary_keywords) == 3
        assert result.specific_count == 2
        assert result.broader_count == 1
        assert result.total_count == 3
        assert result.error is None
        assert result.duration_ms == 5.5

    def test_create_failure_result(self) -> None:
        """Should create a failed result with error."""
        result = SecondaryKeywordResult(
            success=False,
            error="Primary keyword cannot be empty",
            project_id="proj-1",
        )
        assert result.success is False
        assert result.error == "Primary keyword cannot be empty"
        assert result.secondary_keywords == []
        assert result.total_count == 0

    def test_result_defaults(self) -> None:
        """Should have correct default values."""
        result = SecondaryKeywordResult(success=True)
        assert result.secondary_keywords == []
        assert result.specific_count == 0
        assert result.broader_count == 0
        assert result.total_count == 0
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.project_id is None
        assert result.page_id is None

    def test_result_to_dict(
        self, specific_keywords: list[KeywordVolumeData]
    ) -> None:
        """Should convert result to dictionary correctly."""
        result = SecondaryKeywordResult(
            success=True,
            secondary_keywords=specific_keywords[:2],
            specific_count=2,
            broader_count=0,
            total_count=2,
            duration_ms=10.0,
        )
        data = result.to_dict()

        assert data["success"] is True
        assert len(data["secondary_keywords"]) == 2
        assert data["secondary_keywords"][0]["keyword"] == "coffee bean storage container"
        assert data["specific_count"] == 2
        assert data["broader_count"] == 0
        assert data["total_count"] == 2
        assert data["duration_ms"] == 10.0
        assert data["error"] is None


# ---------------------------------------------------------------------------
# Test: SecondaryKeywordService Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for SecondaryKeywordService initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize without errors."""
        service = SecondaryKeywordService()
        assert service is not None


# ---------------------------------------------------------------------------
# Test: Keyword Normalization
# ---------------------------------------------------------------------------


class TestKeywordNormalization:
    """Tests for keyword normalization method."""

    def test_normalize_lowercase(self, service: SecondaryKeywordService) -> None:
        """Should convert to lowercase."""
        assert service._normalize_keyword("COFFEE CONTAINERS") == "coffee containers"

    def test_normalize_strip_whitespace(self, service: SecondaryKeywordService) -> None:
        """Should strip leading/trailing whitespace."""
        assert service._normalize_keyword("  coffee  ") == "coffee"

    def test_normalize_single_spaces(self, service: SecondaryKeywordService) -> None:
        """Should collapse multiple spaces to single."""
        assert (
            service._normalize_keyword("coffee   bean   storage")
            == "coffee bean storage"
        )


# ---------------------------------------------------------------------------
# Test: select_secondary Method - Basic Selection
# ---------------------------------------------------------------------------


class TestSelectSecondaryBasic:
    """Tests for basic select_secondary functionality."""

    @pytest.mark.asyncio
    async def test_select_secondary_basic(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should select a mix of specific and broader keywords."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            project_id="proj-1",
            page_id="page-1",
        )

        assert result.success is True
        assert result.total_count >= 3  # At least min specific + min broader
        assert result.total_count <= 5  # Max total
        assert result.specific_count >= 2  # Min specific
        assert result.broader_count >= 0  # At least 0 broader

    @pytest.mark.asyncio
    async def test_excludes_primary_keyword(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should not include the primary keyword in secondary selection."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
        )

        assert result.success is True
        secondary_kw_texts = [kw.keyword for kw in result.secondary_keywords]
        assert "coffee bean storage container" not in secondary_kw_texts

    @pytest.mark.asyncio
    async def test_includes_broader_terms(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should include broader terms with volume >= 1000."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
        )

        assert result.success is True
        # Should have at least one broader keyword
        secondary_kw_texts = [kw.keyword for kw in result.secondary_keywords]
        broader_in_results = [
            kw
            for kw in secondary_kw_texts
            if kw in ["kitchen storage", "food containers", "storage solutions"]
        ]
        assert len(broader_in_results) >= 1

    @pytest.mark.asyncio
    async def test_tracks_duration(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should track operation duration."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
        )

        assert result.success is True
        assert result.duration_ms >= 0
        assert isinstance(result.duration_ms, float)


# ---------------------------------------------------------------------------
# Test: select_secondary Method - Validation
# ---------------------------------------------------------------------------


class TestSelectSecondaryValidation:
    """Tests for select_secondary input validation."""

    @pytest.mark.asyncio
    async def test_empty_collection_title(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should fail with empty collection title."""
        result = await service.select_secondary(
            collection_title="",
            primary_keyword="coffee storage",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "title" in result.error.lower()

    @pytest.mark.asyncio
    async def test_whitespace_collection_title(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should fail with whitespace-only collection title."""
        result = await service.select_secondary(
            collection_title="   ",
            primary_keyword="coffee storage",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "title" in result.error.lower()

    @pytest.mark.asyncio
    async def test_empty_primary_keyword(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should fail with empty primary keyword."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "primary" in result.error.lower()

    @pytest.mark.asyncio
    async def test_whitespace_primary_keyword(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should fail with whitespace-only primary keyword."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="   ",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
        )

        assert result.success is False
        assert result.error is not None
        assert "primary" in result.error.lower()


# ---------------------------------------------------------------------------
# Test: select_secondary Method - used_primaries Exclusion
# ---------------------------------------------------------------------------


class TestSelectSecondaryUsedPrimaries:
    """Tests for used_primaries exclusion logic."""

    @pytest.mark.asyncio
    async def test_excludes_used_primaries(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should exclude keywords already used as primary elsewhere."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            used_primaries={"airtight coffee containers"},
        )

        assert result.success is True
        secondary_kw_texts = [kw.keyword for kw in result.secondary_keywords]
        assert "airtight coffee containers" not in secondary_kw_texts

    @pytest.mark.asyncio
    async def test_case_insensitive_exclusion(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should exclude case-insensitively."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            used_primaries={"AIRTIGHT COFFEE CONTAINERS"},
        )

        assert result.success is True
        secondary_kw_texts = [kw.keyword for kw in result.secondary_keywords]
        assert "airtight coffee containers" not in secondary_kw_texts

    @pytest.mark.asyncio
    async def test_empty_used_primaries(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should work with empty used_primaries set."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            used_primaries=set(),
        )

        assert result.success is True
        assert result.total_count >= 3

    @pytest.mark.asyncio
    async def test_none_used_primaries(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should work with None used_primaries (default)."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            used_primaries=None,
        )

        assert result.success is True


# ---------------------------------------------------------------------------
# Test: select_secondary Method - Custom Thresholds
# ---------------------------------------------------------------------------


class TestSelectSecondaryThresholds:
    """Tests for custom threshold configuration."""

    @pytest.mark.asyncio
    async def test_custom_max_specific(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should respect custom max_specific threshold."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            max_specific=1,  # Only 1 specific
            max_broader=4,
        )

        assert result.success is True
        # Should have at most 1 specific keyword
        assert result.specific_count <= 1

    @pytest.mark.asyncio
    async def test_custom_broader_volume_threshold(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should respect custom broader volume threshold."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            broader_volume_threshold=3000,  # High threshold
        )

        assert result.success is True
        # Only keywords with volume >= 3000 should be in broader
        # "kitchen storage" (5000) and "food containers" (3500)

    @pytest.mark.asyncio
    async def test_zero_broader_keywords(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should allow zero broader keywords."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            min_broader=0,
            max_broader=0,
        )

        assert result.success is True
        assert result.broader_count == 0
        # Should fill with specific keywords instead
        assert result.specific_count >= result.total_count


# ---------------------------------------------------------------------------
# Test: select_secondary Method - Fill Logic
# ---------------------------------------------------------------------------


class TestSelectSecondaryFillLogic:
    """Tests for slot filling when not enough broader keywords."""

    @pytest.mark.asyncio
    async def test_fills_with_specific_when_no_broader(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should fill remaining slots with specific when no broader available."""
        # All keywords are the same (no separate broader keywords)
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=specific_keywords,  # Same as specific
        )

        assert result.success is True
        # Should still have keywords, filled from specific
        assert result.total_count >= 2


# ---------------------------------------------------------------------------
# Test: select_secondary Method - Exception Handling
# ---------------------------------------------------------------------------


class TestSelectSecondaryExceptionHandling:
    """Tests for exception handling in select_secondary."""

    @pytest.mark.asyncio
    async def test_handles_empty_specific_keywords(
        self,
        service: SecondaryKeywordService,
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should handle empty specific keywords list."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=[],
            all_keywords=all_keywords,
        )

        assert result.success is True
        # Should still have broader keywords
        assert result.specific_count == 0

    @pytest.mark.asyncio
    async def test_handles_empty_all_keywords(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should handle empty all keywords list."""
        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=[],
        )

        assert result.success is True
        # Should still have specific keywords
        assert result.broader_count == 0


# ---------------------------------------------------------------------------
# Test: select_secondary_for_request Method
# ---------------------------------------------------------------------------


class TestSelectSecondaryForRequest:
    """Tests for the select_secondary_for_request convenience method."""

    @pytest.mark.asyncio
    async def test_select_secondary_for_request(
        self,
        service: SecondaryKeywordService,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should select secondary using request object."""
        request = SecondaryKeywordRequest(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            used_primaries=set(),
            project_id="proj-1",
            page_id="page-1",
        )

        result = await service.select_secondary_for_request(request)

        assert result.success is True
        assert result.project_id == "proj-1"
        assert result.page_id == "page-1"


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for SecondaryKeyword exception classes."""

    def test_service_error_base(self) -> None:
        """SecondaryKeywordServiceError should be base exception."""
        error = SecondaryKeywordServiceError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_validation_error(self) -> None:
        """SecondaryKeywordValidationError should contain field and value info."""
        error = SecondaryKeywordValidationError(
            field="collection_title",
            value="",
            message="Cannot be empty",
        )
        assert error.field == "collection_title"
        assert error.value == ""
        assert error.message == "Cannot be empty"
        assert "collection_title" in str(error)

    def test_selection_error(self) -> None:
        """SecondaryKeywordSelectionError should contain context info."""
        error = SecondaryKeywordSelectionError(
            message="Selection failed",
            project_id="proj-1",
            page_id="page-1",
        )
        assert error.project_id == "proj-1"
        assert error.page_id == "page-1"
        assert "Selection failed" in str(error)

    def test_exception_hierarchy(self) -> None:
        """All exceptions should inherit from base error."""
        assert issubclass(SecondaryKeywordValidationError, SecondaryKeywordServiceError)
        assert issubclass(SecondaryKeywordSelectionError, SecondaryKeywordServiceError)


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton accessor and convenience functions."""

    def test_get_secondary_keyword_service_singleton(self) -> None:
        """get_secondary_keyword_service should return singleton."""
        # Clear the global instance first
        import app.services.secondary_keywords as sk_module

        original = sk_module._secondary_keyword_service
        sk_module._secondary_keyword_service = None

        try:
            service1 = get_secondary_keyword_service()
            service2 = get_secondary_keyword_service()
            assert service1 is service2
        finally:
            # Restore original
            sk_module._secondary_keyword_service = original

    @pytest.mark.asyncio
    async def test_select_secondary_keywords_convenience(
        self,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """select_secondary_keywords should use default service."""
        result = await select_secondary_keywords(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=specific_keywords,
            all_keywords=all_keywords,
            project_id="proj-1",
        )

        assert result.success is True
        assert result.total_count >= 3


# ---------------------------------------------------------------------------
# Test: Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_single_specific_keyword(
        self,
        service: SecondaryKeywordService,
        all_keywords: list[KeywordVolumeData],
    ) -> None:
        """Should handle single specific keyword (excluding primary)."""
        specific = [
            KeywordVolumeData(keyword="primary keyword", volume=2000),
            KeywordVolumeData(keyword="only other specific", volume=500),
        ]

        result = await service.select_secondary(
            collection_title="Test",
            primary_keyword="primary keyword",
            specific_keywords=specific,
            all_keywords=all_keywords,
        )

        assert result.success is True
        # Should include the one non-primary specific keyword
        secondary_kw_texts = [kw.keyword for kw in result.secondary_keywords]
        assert "only other specific" in secondary_kw_texts

    @pytest.mark.asyncio
    async def test_all_keywords_excluded(
        self,
        service: SecondaryKeywordService,
    ) -> None:
        """Should handle when all specific keywords are excluded."""
        specific = [
            KeywordVolumeData(keyword="kw1", volume=1000),
            KeywordVolumeData(keyword="kw2", volume=900),
        ]
        all_kw = specific + [
            KeywordVolumeData(keyword="broader", volume=2000),
        ]

        result = await service.select_secondary(
            collection_title="Test",
            primary_keyword="kw1",  # Exclude this
            specific_keywords=specific,
            all_keywords=all_kw,
            used_primaries={"kw2"},  # Exclude this too
        )

        assert result.success is True
        # Should still have broader keywords
        secondary_kw_texts = [kw.keyword for kw in result.secondary_keywords]
        assert "kw1" not in secondary_kw_texts
        assert "kw2" not in secondary_kw_texts

    @pytest.mark.asyncio
    async def test_keywords_with_no_volume(
        self,
        service: SecondaryKeywordService,
    ) -> None:
        """Should skip keywords with None or zero volume."""
        specific = [
            KeywordVolumeData(keyword="primary", volume=2000),
            KeywordVolumeData(keyword="has volume", volume=500),
            KeywordVolumeData(keyword="no volume", volume=None),
            KeywordVolumeData(keyword="zero volume", volume=0),
        ]

        result = await service.select_secondary(
            collection_title="Test",
            primary_keyword="primary",
            specific_keywords=specific,
            all_keywords=specific,
        )

        assert result.success is True
        secondary_kw_texts = [kw.keyword for kw in result.secondary_keywords]
        assert "has volume" in secondary_kw_texts
        # Keywords with None/0 volume should not be in specific candidates
        # (they're filtered out)

    @pytest.mark.asyncio
    async def test_unicode_keywords(
        self,
        service: SecondaryKeywordService,
    ) -> None:
        """Should handle unicode in keywords."""
        specific = [
            KeywordVolumeData(keyword="primary", volume=2000),
            KeywordVolumeData(keyword="コーヒー storage", volume=1000),
            KeywordVolumeData(keyword="café containers", volume=800),
        ]
        all_kw = specific + [
            KeywordVolumeData(keyword="日本語 keyword", volume=1500),
        ]

        result = await service.select_secondary(
            collection_title="Test",
            primary_keyword="primary",
            specific_keywords=specific,
            all_keywords=all_kw,
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_large_keyword_lists(
        self,
        service: SecondaryKeywordService,
    ) -> None:
        """Should handle large keyword lists efficiently."""
        specific = [KeywordVolumeData(keyword=f"specific {i}", volume=100 + i) for i in range(50)]
        all_kw = specific + [
            KeywordVolumeData(keyword=f"broader {i}", volume=2000 + i) for i in range(50)
        ]

        result = await service.select_secondary(
            collection_title="Test",
            primary_keyword="specific 0",
            specific_keywords=specific,
            all_keywords=all_kw,
        )

        assert result.success is True
        assert result.total_count <= 5  # Still respects max

    @pytest.mark.asyncio
    async def test_duplicate_keywords_in_lists(
        self,
        service: SecondaryKeywordService,
    ) -> None:
        """Should handle duplicate keywords in input lists."""
        specific = [
            KeywordVolumeData(keyword="primary", volume=2000),
            KeywordVolumeData(keyword="duplicate", volume=1000),
            KeywordVolumeData(keyword="duplicate", volume=1000),  # Duplicate
            KeywordVolumeData(keyword="unique", volume=500),
        ]

        result = await service.select_secondary(
            collection_title="Test",
            primary_keyword="primary",
            specific_keywords=specific,
            all_keywords=specific,
        )

        assert result.success is True
        # Should not have duplicate in results
        secondary_kw_texts = [kw.keyword for kw in result.secondary_keywords]
        assert secondary_kw_texts.count("duplicate") <= 1

    @pytest.mark.asyncio
    async def test_broader_same_as_specific(
        self,
        service: SecondaryKeywordService,
    ) -> None:
        """Should not include specific keywords as broader."""
        specific = [
            KeywordVolumeData(keyword="primary", volume=2000),
            KeywordVolumeData(keyword="specific one", volume=1500),
            KeywordVolumeData(keyword="specific two", volume=1200),
        ]
        # all_keywords = specific (no separate broader)
        all_kw = specific

        result = await service.select_secondary(
            collection_title="Test",
            primary_keyword="primary",
            specific_keywords=specific,
            all_keywords=all_kw,
        )

        assert result.success is True
        # No broader keywords since all are specific
        assert result.broader_count == 0
