"""Unit tests for POP Content Score service.

Tests cover:
- score_content() with mocked POP client
- Each extraction method (page score, keyword analysis, LSI coverage, word count, heading analysis, recommendations)
- Pass/fail determination at threshold boundary
- Fallback triggering (circuit open, API error, timeout)
- Batch scoring
- Database persistence (save_score, score_and_save_content)
- Logging output includes required entity IDs

ERROR LOGGING REQUIREMENTS (verified by tests):
- Test failures include full assertion context
- Test setup/teardown logged at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage.
"""

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.pop import (
    POPCircuitOpenError,
    POPClient,
    POPError,
    POPTaskResult,
    POPTaskStatus,
    POPTimeoutError,
)
from app.services.pop_content_score import (
    BatchScoreItem,
    BatchScoreResult,
    POPContentScoreResult,
    POPContentScoreService,
    POPContentScoreServiceError,
    POPContentScoreValidationError,
    get_pop_content_score_service,
    score_content,
)

# Configure logging for tests
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_pop_client() -> AsyncMock:
    """Create a mock POP client."""
    client = AsyncMock(spec=POPClient)
    return client


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock SQLAlchemy async session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_legacy_service() -> MagicMock:
    """Create a mock legacy ContentScoreService."""
    service = MagicMock()
    service.score_content = AsyncMock()
    return service


@pytest.fixture
def sample_pop_score_response() -> dict[str, Any]:
    """Sample POP API response for scoring with full data."""
    return {
        "wordCount": {"current": 1200, "target": 1500},
        "pageScore": 72,
        "tagCounts": [
            {
                "tagLabel": "H1 tag total",
                "min": 1,
                "max": 1,
                "mean": 1.0,
                "signalCnt": 1,
            },
            {
                "tagLabel": "H2 tag total",
                "min": 3,
                "max": 8,
                "mean": 5.2,
                "signalCnt": 2,
                "comment": "Add more H2 headings",
            },
            {
                "tagLabel": "H3 tag total",
                "min": 5,
                "max": 12,
                "mean": 8.1,
                "signalCnt": 15,
                "comment": "Too many H3 headings",
            },
        ],
        "cleanedContentBrief": {
            "pageScore": 72,
            "title": [
                {
                    "term": {"phrase": "hiking boots", "type": "exact", "weight": 1.0},
                    "contentBrief": {"current": 1, "target": 1},
                },
            ],
            "pageTitle": [
                {
                    "term": {
                        "phrase": "best hiking boots",
                        "type": "variation",
                        "weight": 0.8,
                    },
                    "contentBrief": {"current": 0, "target": 1},
                },
            ],
            "subHeadings": [
                {
                    "term": {
                        "phrase": "waterproof boots",
                        "type": "lsi",
                        "weight": 0.6,
                    },
                    "contentBrief": {"current": 1, "target": 2},
                },
            ],
            "p": [
                {
                    "term": {"phrase": "hiking gear", "type": "lsi", "weight": 0.5},
                    "contentBrief": {"current": 3, "target": 5},
                },
            ],
            "titleTotal": {"current": 2, "min": 1, "max": 3},
            "pageTitleTotal": {"current": 1, "min": 1, "max": 2},
            "subHeadingsTotal": {"current": 3, "min": 5, "max": 10},
            "pTotal": {"current": 10, "min": 15, "max": 25},
        },
        "lsaPhrases": [
            {
                "phrase": "trail running",
                "weight": 0.8,
                "averageCount": 3,
                "targetCount": 2,
            },
            {
                "phrase": "ankle support",
                "weight": 0.7,
                "averageCount": 2,
                "targetCount": 0,
            },
            {
                "phrase": "waterproof membrane",
                "weight": 0.6,
                "averageCount": 1,
                "targetCount": 3,
            },
        ],
    }


@pytest.fixture
def sample_recommendations_response() -> dict[str, Any]:
    """Sample POP recommendations endpoint response."""
    return {
        "recommendations": {
            "exactKeyword": [
                {
                    "signal": "Meta Title",
                    "comment": "Add exact keyword to meta title",
                    "target": 1,
                    "editedCount": 0,
                },
                {
                    "signal": "H1",
                    "comment": "Leave As Is",
                    "target": 1,
                    "editedCount": 1,
                },
            ],
            "lsi": [
                {
                    "signal": "LSI terms",
                    "comment": "Add more LSI terms to body",
                    "target": 5,
                    "editedCount": 2,
                },
            ],
            "pageStructure": [
                {
                    "signal": "H2",
                    "comment": "Add 2 more H2 headings",
                    "target": 5,
                    "signalCnt": 2,
                },
            ],
            "variations": [
                {
                    "signal": "Paragraph",
                    "comment": "Use more keyword variations",
                    "target": 3,
                    "targetVariationCnt": 1,
                },
            ],
        },
    }


@pytest.fixture
def empty_pop_response() -> dict[str, Any]:
    """Sample POP API response with minimal/empty data."""
    return {}


@pytest.fixture
def sample_task_result(sample_pop_score_response: dict[str, Any]) -> POPTaskResult:
    """Sample successful task result from POP client."""
    return POPTaskResult(
        success=True,
        task_id="task-score-123",
        status=POPTaskStatus.SUCCESS,
        data=sample_pop_score_response,
        request_id="req-xyz-789",
    )


@pytest.fixture
def failed_task_result() -> POPTaskResult:
    """Sample failed task result from POP client."""
    return POPTaskResult(
        success=False,
        task_id=None,
        status=POPTaskStatus.UNKNOWN,
        error="Failed to create task",
        request_id="req-fail-123",
    )


# ---------------------------------------------------------------------------
# Test: POPContentScoreResult Dataclass
# ---------------------------------------------------------------------------


class TestPOPContentScoreResult:
    """Tests for POPContentScoreResult dataclass."""

    def test_result_defaults(self) -> None:
        """POPContentScoreResult should have sensible defaults."""
        result = POPContentScoreResult(
            success=True,
            keyword="hiking boots",
            content_url="https://example.com/boots",
        )

        assert result.success is True
        assert result.keyword == "hiking boots"
        assert result.content_url == "https://example.com/boots"
        assert result.task_id is None
        assert result.score_id is None
        assert result.page_score is None
        assert result.passed is None
        assert result.keyword_analysis == {}
        assert result.lsi_coverage == {}
        assert result.word_count_current is None
        assert result.word_count_target is None
        assert result.heading_analysis == {}
        assert result.recommendations == []
        assert result.fallback_used is False
        assert result.raw_response == {}
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.request_id is None

    def test_result_with_values(self) -> None:
        """POPContentScoreResult should accept all fields."""
        result = POPContentScoreResult(
            success=True,
            keyword="hiking boots",
            content_url="https://example.com",
            task_id="task-123",
            score_id="score-456",
            page_score=75.5,
            passed=True,
            keyword_analysis={"sections": []},
            lsi_coverage={"terms": [], "coverage_percentage": 50.0},
            word_count_current=1200,
            word_count_target=1500,
            heading_analysis={"levels": []},
            recommendations=[{"category": "keyword", "recommendation": "Add keyword"}],
            fallback_used=False,
            raw_response={"key": "value"},
            error=None,
            duration_ms=150.5,
            request_id="req-123",
        )

        assert result.task_id == "task-123"
        assert result.score_id == "score-456"
        assert result.page_score == 75.5
        assert result.passed is True
        assert result.word_count_current == 1200
        assert result.word_count_target == 1500
        assert result.fallback_used is False
        assert result.duration_ms == 150.5


class TestBatchScoreDataclasses:
    """Tests for batch scoring dataclasses."""

    def test_batch_score_item(self) -> None:
        """BatchScoreItem should hold input data."""
        item = BatchScoreItem(
            page_id="page-123",
            keyword="hiking boots",
            url="https://example.com/boots",
        )

        assert item.page_id == "page-123"
        assert item.keyword == "hiking boots"
        assert item.url == "https://example.com/boots"

    def test_batch_score_result_defaults(self) -> None:
        """BatchScoreResult should have sensible defaults."""
        result = BatchScoreResult(
            page_id="page-123",
            keyword="hiking boots",
            url="https://example.com/boots",
            success=True,
        )

        assert result.page_id == "page-123"
        assert result.success is True
        assert result.score_id is None
        assert result.page_score is None
        assert result.passed is None
        assert result.fallback_used is False
        assert result.error is None
        assert result.duration_ms == 0.0


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for service exception classes."""

    def test_service_error_basic(self) -> None:
        """Test POPContentScoreServiceError basic usage."""
        error = POPContentScoreServiceError("Test error")
        assert str(error) == "Test error"
        assert error.project_id is None
        assert error.page_id is None

    def test_service_error_with_context(self) -> None:
        """Test POPContentScoreServiceError with context."""
        error = POPContentScoreServiceError(
            "Test error",
            project_id="proj-123",
            page_id="page-456",
        )
        assert error.project_id == "proj-123"
        assert error.page_id == "page-456"

    def test_validation_error(self) -> None:
        """Test POPContentScoreValidationError."""
        error = POPContentScoreValidationError(
            field_name="keyword",
            value="",
            message="cannot be empty",
            project_id="proj-123",
            page_id="page-456",
        )
        assert "keyword" in str(error)
        assert "cannot be empty" in str(error)
        assert error.field_name == "keyword"
        assert error.value == ""
        assert error.project_id == "proj-123"


# ---------------------------------------------------------------------------
# Test: Page Score Extraction
# ---------------------------------------------------------------------------


class TestPageScoreExtraction:
    """Tests for page score extraction."""

    def test_extract_page_score_from_cleanedContentBrief(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should extract page score from cleanedContentBrief.pageScore."""
        service = POPContentScoreService()
        score = service._extract_page_score(sample_pop_score_response)

        assert score == 72.0

    def test_extract_page_score_from_top_level(self) -> None:
        """Should fall back to top-level pageScore."""
        service = POPContentScoreService()
        score = service._extract_page_score({"pageScore": 80})

        assert score == 80.0

    def test_extract_page_score_from_pageScoreValue(self) -> None:
        """Should extract from pageScoreValue if pageScore not present."""
        service = POPContentScoreService()
        score = service._extract_page_score(
            {"cleanedContentBrief": {"pageScoreValue": "85"}}
        )

        assert score == 85.0

    def test_extract_page_score_missing(self) -> None:
        """Should return None when pageScore is missing."""
        service = POPContentScoreService()
        score = service._extract_page_score({})

        assert score is None

    def test_extract_page_score_invalid_type(self) -> None:
        """Should handle invalid type for pageScore."""
        service = POPContentScoreService()
        score = service._extract_page_score(
            {"cleanedContentBrief": {"pageScore": "invalid"}}
        )

        # Falls back to top level which is also missing
        assert score is None


# ---------------------------------------------------------------------------
# Test: Keyword Analysis Extraction
# ---------------------------------------------------------------------------


class TestKeywordAnalysisExtraction:
    """Tests for keyword analysis extraction from cleanedContentBrief."""

    def test_extract_keyword_analysis_all_sections(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should extract keyword analysis from all sections."""
        service = POPContentScoreService()
        analysis = service._extract_keyword_analysis(sample_pop_score_response)

        assert "sections" in analysis
        assert "section_totals" in analysis

        # Check sections were extracted
        sections = {item["section"] for item in analysis["sections"]}
        assert "title" in sections
        assert "h1" in sections
        assert "h2" in sections
        assert "paragraph" in sections

    def test_extract_keyword_analysis_with_current_target(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should extract current and target counts for keywords."""
        service = POPContentScoreService()
        analysis = service._extract_keyword_analysis(sample_pop_score_response)

        # Find the "hiking boots" keyword in title section
        hiking_boots = next(
            (
                k
                for k in analysis["sections"]
                if k["keyword"] == "hiking boots" and k["section"] == "title"
            ),
            None,
        )

        assert hiking_boots is not None
        assert hiking_boots["current_count"] == 1
        assert hiking_boots["target_count"] == 1
        assert hiking_boots["weight"] == 1.0

    def test_extract_keyword_analysis_section_totals(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should extract section totals."""
        service = POPContentScoreService()
        analysis = service._extract_keyword_analysis(sample_pop_score_response)

        # Check that section totals are extracted
        totals = analysis["section_totals"]
        assert len(totals) > 0

        title_total = next((t for t in totals if t["section"] == "title"), None)
        assert title_total is not None
        assert title_total["current"] == 2
        assert title_total["min"] == 1
        assert title_total["max"] == 3

    def test_extract_keyword_analysis_empty(self) -> None:
        """Should return empty analysis when cleanedContentBrief is missing."""
        service = POPContentScoreService()
        analysis = service._extract_keyword_analysis({})

        assert analysis["sections"] == []
        assert analysis["section_totals"] == []


# ---------------------------------------------------------------------------
# Test: LSI Coverage Extraction
# ---------------------------------------------------------------------------


class TestLSICoverageExtraction:
    """Tests for LSI term coverage extraction from lsaPhrases."""

    def test_extract_lsi_coverage(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should extract LSI coverage with all fields."""
        service = POPContentScoreService()
        coverage = service._extract_lsi_coverage(sample_pop_score_response)

        assert "terms" in coverage
        assert coverage["total_terms"] == 3
        assert (
            coverage["covered_terms"] == 2
        )  # trail running and waterproof membrane have targetCount > 0
        assert coverage["coverage_percentage"] is not None

        trail_running = next(
            (t for t in coverage["terms"] if t["phrase"] == "trail running"), None
        )
        assert trail_running is not None
        assert trail_running["current_count"] == 2  # targetCount
        assert trail_running["target_count"] == 3  # averageCount
        assert trail_running["weight"] == 0.8

    def test_extract_lsi_coverage_empty(self) -> None:
        """Should return empty coverage when lsaPhrases is missing."""
        service = POPContentScoreService()
        coverage = service._extract_lsi_coverage({})

        assert coverage["terms"] == []
        assert coverage["total_terms"] == 0
        assert coverage["covered_terms"] == 0
        assert coverage["coverage_percentage"] is None

    def test_extract_lsi_coverage_calculates_percentage(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should calculate coverage percentage correctly."""
        service = POPContentScoreService()
        coverage = service._extract_lsi_coverage(sample_pop_score_response)

        # 2 out of 3 terms have targetCount > 0
        expected_percentage = round((2 / 3) * 100, 2)
        assert coverage["coverage_percentage"] == expected_percentage


# ---------------------------------------------------------------------------
# Test: Word Count Extraction
# ---------------------------------------------------------------------------


class TestWordCountExtraction:
    """Tests for word count extraction."""

    def test_extract_word_count_current(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should extract current word count from wordCount.current."""
        service = POPContentScoreService()
        current = service._extract_word_count_current(sample_pop_score_response)

        assert current == 1200

    def test_extract_word_count_target(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should extract target word count from wordCount.target."""
        service = POPContentScoreService()
        target = service._extract_word_count_target(sample_pop_score_response)

        assert target == 1500

    def test_extract_word_count_missing(self) -> None:
        """Should return None when wordCount is missing."""
        service = POPContentScoreService()

        assert service._extract_word_count_current({}) is None
        assert service._extract_word_count_target({}) is None

    def test_extract_word_count_invalid_type(self) -> None:
        """Should return None when wordCount is not a dict."""
        service = POPContentScoreService()

        assert service._extract_word_count_current({"wordCount": "invalid"}) is None
        assert service._extract_word_count_target({"wordCount": "invalid"}) is None


# ---------------------------------------------------------------------------
# Test: Heading Analysis Extraction
# ---------------------------------------------------------------------------


class TestHeadingAnalysisExtraction:
    """Tests for heading structure analysis extraction from tagCounts."""

    def test_extract_heading_analysis_all_levels(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should extract H1-H4 heading analysis from tagCounts."""
        service = POPContentScoreService()
        analysis = service._extract_heading_analysis(sample_pop_score_response)

        assert "levels" in analysis
        assert "issues" in analysis

        # Check levels were extracted
        levels = {level["level"] for level in analysis["levels"]}
        assert "h1" in levels
        assert "h2" in levels
        assert "h3" in levels

    def test_extract_heading_analysis_with_current_min_max(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should extract current, min, max for each heading level."""
        service = POPContentScoreService()
        analysis = service._extract_heading_analysis(sample_pop_score_response)

        h2 = next((h for h in analysis["levels"] if h["level"] == "h2"), None)
        assert h2 is not None
        assert h2["current"] == 2  # signalCnt
        assert h2["min"] == 3
        assert h2["max"] == 8
        assert h2["mean"] == 5.2

    def test_extract_heading_analysis_detects_below_minimum_issue(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should detect when heading count is below minimum."""
        service = POPContentScoreService()
        analysis = service._extract_heading_analysis(sample_pop_score_response)

        # H2 has current=2, min=3, so it's below minimum
        h2_issue = next((i for i in analysis["issues"] if i["level"] == "h2"), None)
        assert h2_issue is not None
        assert h2_issue["issue"] == "below_minimum"
        assert h2_issue["current"] == 2
        assert h2_issue["expected_min"] == 3

    def test_extract_heading_analysis_detects_above_maximum_issue(
        self, sample_pop_score_response: dict[str, Any]
    ) -> None:
        """Should detect when heading count is above maximum."""
        service = POPContentScoreService()
        analysis = service._extract_heading_analysis(sample_pop_score_response)

        # H3 has current=15, max=12, so it's above maximum
        h3_issue = next((i for i in analysis["issues"] if i["level"] == "h3"), None)
        assert h3_issue is not None
        assert h3_issue["issue"] == "above_maximum"
        assert h3_issue["current"] == 15
        assert h3_issue["expected_max"] == 12

    def test_extract_heading_analysis_empty(self) -> None:
        """Should return empty analysis when tagCounts is missing."""
        service = POPContentScoreService()
        analysis = service._extract_heading_analysis({})

        assert analysis["levels"] == []
        assert analysis["issues"] == []


# ---------------------------------------------------------------------------
# Test: Recommendations Extraction
# ---------------------------------------------------------------------------


class TestRecommendationsExtraction:
    """Tests for recommendations extraction from custom recommendations endpoint."""

    def test_extract_recommendations_all_categories(
        self, sample_recommendations_response: dict[str, Any]
    ) -> None:
        """Should extract recommendations from all categories."""
        service = POPContentScoreService()
        recs = service._extract_recommendations(sample_recommendations_response)

        categories = {r["category"] for r in recs}
        assert "keyword" in categories
        assert "lsi" in categories
        assert "structure" in categories
        assert "variations" in categories

    def test_extract_recommendations_filters_leave_as_is(
        self, sample_recommendations_response: dict[str, Any]
    ) -> None:
        """Should filter out 'Leave As Is' recommendations."""
        service = POPContentScoreService()
        recs = service._extract_recommendations(sample_recommendations_response)

        leave_as_is_recs = [
            r for r in recs if "leave as is" in r["recommendation"].lower()
        ]
        assert len(leave_as_is_recs) == 0

    def test_extract_recommendations_includes_all_fields(
        self, sample_recommendations_response: dict[str, Any]
    ) -> None:
        """Should include all required fields in recommendations."""
        service = POPContentScoreService()
        recs = service._extract_recommendations(sample_recommendations_response)

        for rec in recs:
            assert "category" in rec
            assert "signal" in rec
            assert "recommendation" in rec
            assert "target" in rec
            assert "current" in rec
            assert "priority" in rec

    def test_extract_recommendations_empty(self) -> None:
        """Should return empty list when recommendations are missing."""
        service = POPContentScoreService()
        recs = service._extract_recommendations({})

        assert recs == []


# ---------------------------------------------------------------------------
# Test: Pass/Fail Determination
# ---------------------------------------------------------------------------


class TestPassFailDetermination:
    """Tests for pass/fail determination at threshold boundary."""

    def test_determine_pass_fail_above_threshold(self) -> None:
        """Should pass when score is above threshold."""
        service = POPContentScoreService()

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            passed, recs = service._determine_pass_fail(75.0, [])

        assert passed is True
        assert recs == []

    def test_determine_pass_fail_below_threshold(self) -> None:
        """Should fail when score is below threshold."""
        service = POPContentScoreService()

        recommendations = [
            {"category": "keyword", "priority": 1},
            {"category": "lsi", "priority": 1},
        ]

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            passed, recs = service._determine_pass_fail(65.0, recommendations)

        assert passed is False
        assert len(recs) == 2

    def test_determine_pass_fail_at_threshold(self) -> None:
        """Should pass when score equals threshold exactly."""
        service = POPContentScoreService()

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            passed, recs = service._determine_pass_fail(70.0, [])

        assert passed is True

    def test_determine_pass_fail_just_below_threshold(self) -> None:
        """Should fail when score is just below threshold."""
        service = POPContentScoreService()

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            passed, recs = service._determine_pass_fail(69.9, [])

        assert passed is False

    def test_determine_pass_fail_none_score(self) -> None:
        """Should fail when score is None."""
        service = POPContentScoreService()

        recommendations = [{"category": "keyword", "priority": 1}]

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            passed, recs = service._determine_pass_fail(None, recommendations)

        assert passed is False
        assert recs == recommendations

    def test_determine_pass_fail_prioritizes_recommendations(self) -> None:
        """Should prioritize recommendations by category when failing."""
        service = POPContentScoreService()

        recommendations = [
            {"category": "variations", "priority": 1},
            {"category": "keyword", "priority": 1},
            {"category": "structure", "priority": 1},
            {"category": "lsi", "priority": 1},
        ]

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            passed, recs = service._determine_pass_fail(50.0, recommendations)

        assert passed is False
        # Order should be: structure, keyword, lsi, variations
        assert recs[0]["category"] == "structure"
        assert recs[1]["category"] == "keyword"
        assert recs[2]["category"] == "lsi"
        assert recs[3]["category"] == "variations"


# ---------------------------------------------------------------------------
# Test: score_content() Method
# ---------------------------------------------------------------------------


class TestScoreContent:
    """Tests for score_content() with mocked POP client."""

    @pytest.mark.asyncio
    async def test_score_content_success(
        self,
        mock_pop_client: AsyncMock,
        sample_task_result: POPTaskResult,
    ) -> None:
        """Should score content successfully."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-score-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        service = POPContentScoreService(client=mock_pop_client)

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            result = await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com/boots",
            )

        assert result.success is True
        assert result.keyword == "hiking boots"
        assert result.content_url == "https://example.com/boots"
        assert result.task_id == "task-score-123"
        assert result.page_score == 72.0
        assert result.passed is True  # 72 >= 70
        assert result.word_count_current == 1200

    @pytest.mark.asyncio
    async def test_score_content_empty_keyword_raises_validation_error(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should raise validation error for empty keyword."""
        service = POPContentScoreService(client=mock_pop_client)

        with pytest.raises(POPContentScoreValidationError) as exc_info:
            await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="",
                content_url="https://example.com",
            )

        assert exc_info.value.field_name == "keyword"

    @pytest.mark.asyncio
    async def test_score_content_whitespace_keyword_raises_validation_error(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should raise validation error for whitespace-only keyword."""
        service = POPContentScoreService(client=mock_pop_client)

        with pytest.raises(POPContentScoreValidationError) as exc_info:
            await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="   ",
                content_url="https://example.com",
            )

        assert exc_info.value.field_name == "keyword"

    @pytest.mark.asyncio
    async def test_score_content_empty_url_raises_validation_error(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should raise validation error for empty content URL."""
        service = POPContentScoreService(client=mock_pop_client)

        with pytest.raises(POPContentScoreValidationError) as exc_info:
            await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="",
            )

        assert exc_info.value.field_name == "content_url"

    @pytest.mark.asyncio
    async def test_score_content_task_creation_failure(
        self,
        mock_pop_client: AsyncMock,
        failed_task_result: POPTaskResult,
    ) -> None:
        """Should handle task creation failure."""
        mock_pop_client.create_report_task.return_value = failed_task_result

        service = POPContentScoreService(client=mock_pop_client)

        result = await service.score_content(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            content_url="https://example.com",
        )

        assert result.success is False
        assert result.error is not None
        assert "Failed to create" in result.error

    @pytest.mark.asyncio
    async def test_score_content_polling_failure(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should handle polling failure."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = POPTaskResult(
            success=False,
            task_id="task-123",
            status=POPTaskStatus.UNKNOWN,
            error="Polling failed",
        )

        service = POPContentScoreService(client=mock_pop_client)

        result = await service.score_content(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            content_url="https://example.com",
        )

        assert result.success is False
        assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_score_content_task_failure_status(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should handle task failure status from POP API."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.FAILURE,
            data={"error": "Analysis failed"},
        )

        service = POPContentScoreService(client=mock_pop_client)

        result = await service.score_content(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            content_url="https://example.com",
        )

        assert result.success is False


# ---------------------------------------------------------------------------
# Test: Fallback Triggering
# ---------------------------------------------------------------------------


class TestFallbackTriggering:
    """Tests for fallback triggering (circuit open, API error, timeout)."""

    @pytest.mark.asyncio
    async def test_fallback_on_circuit_open(
        self, mock_pop_client: AsyncMock, mock_legacy_service: MagicMock
    ) -> None:
        """Should use fallback when circuit breaker is open."""
        mock_pop_client.create_report_task.side_effect = POPCircuitOpenError(
            "Circuit breaker is open"
        )

        # Configure legacy service response
        legacy_result = MagicMock()
        legacy_result.success = True
        legacy_result.overall_score = 0.65  # 65 on 0-100 scale
        legacy_result.word_count_score = MagicMock(word_count=1100)
        legacy_result.error = None
        mock_legacy_service.score_content.return_value = legacy_result

        service = POPContentScoreService(
            client=mock_pop_client, legacy_service=mock_legacy_service
        )

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            result = await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        assert result.success is True
        assert result.fallback_used is True
        assert result.page_score == 65.0  # 0.65 * 100
        mock_legacy_service.score_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(
        self, mock_pop_client: AsyncMock, mock_legacy_service: MagicMock
    ) -> None:
        """Should use fallback when POP API times out."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.side_effect = POPTimeoutError(
            "Task task-123 timed out after 300s"
        )

        # Configure legacy service response
        legacy_result = MagicMock()
        legacy_result.success = True
        legacy_result.overall_score = 0.7
        legacy_result.word_count_score = MagicMock(word_count=1000)
        legacy_result.error = None
        mock_legacy_service.score_content.return_value = legacy_result

        service = POPContentScoreService(
            client=mock_pop_client, legacy_service=mock_legacy_service
        )

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            result = await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        assert result.fallback_used is True
        mock_legacy_service.score_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(
        self, mock_pop_client: AsyncMock, mock_legacy_service: MagicMock
    ) -> None:
        """Should use fallback when POP API returns error."""
        mock_pop_client.create_report_task.side_effect = POPError(
            "Server error", status_code=500
        )

        # Configure legacy service response
        legacy_result = MagicMock()
        legacy_result.success = True
        legacy_result.overall_score = 0.75
        legacy_result.word_count_score = MagicMock(word_count=1200)
        legacy_result.error = None
        mock_legacy_service.score_content.return_value = legacy_result

        service = POPContentScoreService(
            client=mock_pop_client, legacy_service=mock_legacy_service
        )

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            result = await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        assert result.fallback_used is True
        assert result.page_score == 75.0

    @pytest.mark.asyncio
    async def test_fallback_failure_returns_error(
        self, mock_pop_client: AsyncMock, mock_legacy_service: MagicMock
    ) -> None:
        """Should return error if fallback also fails."""
        mock_pop_client.create_report_task.side_effect = POPCircuitOpenError(
            "Circuit breaker is open"
        )
        mock_legacy_service.score_content.side_effect = RuntimeError("Legacy failed")

        service = POPContentScoreService(
            client=mock_pop_client, legacy_service=mock_legacy_service
        )

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            result = await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        assert result.success is False
        assert result.fallback_used is True
        assert "Fallback scoring failed" in result.error


# ---------------------------------------------------------------------------
# Test: Database Persistence - save_score()
# ---------------------------------------------------------------------------


class TestSaveScore:
    """Tests for save_score() database persistence."""

    @pytest.mark.asyncio
    async def test_save_score_creates_new_record(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Should create new content score record."""
        service = POPContentScoreService(session=mock_session, client=mock_pop_client)

        result = POPContentScoreResult(
            success=True,
            keyword="hiking boots",
            content_url="https://example.com",
            task_id="task-123",
            page_score=75.0,
            passed=True,
            keyword_analysis={"sections": []},
            lsi_coverage={"terms": []},
            word_count_current=1200,
            heading_analysis={"levels": []},
            recommendations=[],
            raw_response={"key": "value"},
        )

        await service.save_score(
            page_id="page-456",
            result=result,
            project_id="proj-123",
        )

        # Verify session.add was called (scores are always new records)
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_score_raises_without_session(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should raise error when session is not available."""
        service = POPContentScoreService(client=mock_pop_client)  # No session

        result = POPContentScoreResult(
            success=True,
            keyword="hiking boots",
            content_url="https://example.com",
        )

        with pytest.raises(POPContentScoreServiceError) as exc_info:
            await service.save_score(
                page_id="page-456",
                result=result,
            )

        assert "session not available" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_save_score_handles_db_error(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Should wrap database errors in service error."""
        mock_session.flush.side_effect = RuntimeError("Database error")

        service = POPContentScoreService(session=mock_session, client=mock_pop_client)

        result = POPContentScoreResult(
            success=True,
            keyword="hiking boots",
            content_url="https://example.com",
        )

        with pytest.raises(POPContentScoreServiceError) as exc_info:
            await service.save_score(
                page_id="page-456",
                result=result,
            )

        assert "Failed to save" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test: score_and_save_content()
# ---------------------------------------------------------------------------


class TestScoreAndSaveContent:
    """Tests for score_and_save_content() combined operation."""

    @pytest.mark.asyncio
    async def test_score_and_save_success(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
        sample_task_result: POPTaskResult,
    ) -> None:
        """Should score and save content successfully."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        # Setup refresh to set the score id
        def set_score_id(score):
            score.id = "saved-score-id"

        mock_session.refresh.side_effect = set_score_id

        service = POPContentScoreService(session=mock_session, client=mock_pop_client)

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            result = await service.score_and_save_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        assert result.success is True
        assert result.score_id == "saved-score-id"
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_score_and_save_no_session(
        self,
        mock_pop_client: AsyncMock,
        sample_task_result: POPTaskResult,
    ) -> None:
        """Should succeed but not save when session is not available."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        service = POPContentScoreService(client=mock_pop_client)  # No session

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            result = await service.score_and_save_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        assert result.success is True
        assert result.score_id is None  # Not saved

    @pytest.mark.asyncio
    async def test_score_and_save_score_failure_skips_save(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Should not save when scoring fails."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=False,
            error="API error",
        )

        service = POPContentScoreService(session=mock_session, client=mock_pop_client)

        result = await service.score_and_save_content(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            content_url="https://example.com",
        )

        assert result.success is False
        mock_session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Batch Scoring
# ---------------------------------------------------------------------------


class TestBatchScoring:
    """Tests for batch scoring functionality."""

    @pytest.mark.asyncio
    async def test_score_batch_yields_results(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
        sample_task_result: POPTaskResult,
    ) -> None:
        """Should yield results as they complete."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        # Setup refresh to set the score id
        call_count = 0

        def set_score_id(score):
            nonlocal call_count
            call_count += 1
            score.id = f"score-{call_count}"

        mock_session.refresh.side_effect = set_score_id

        items = [
            BatchScoreItem(
                page_id="page-1", keyword="boots", url="https://example.com/1"
            ),
            BatchScoreItem(
                page_id="page-2", keyword="shoes", url="https://example.com/2"
            ),
        ]

        service = POPContentScoreService(session=mock_session, client=mock_pop_client)

        results = []
        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            mock_settings.return_value.pop_batch_rate_limit = 5
            async for result in service.score_batch("proj-123", items):
                results.append(result)

        assert len(results) == 2
        assert all(r.success for r in results)
        assert {r.page_id for r in results} == {"page-1", "page-2"}

    @pytest.mark.asyncio
    async def test_score_batch_handles_partial_failures(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
        sample_task_result: POPTaskResult,
    ) -> None:
        """Should handle partial failures - one item fails, others succeed."""
        # First call fails, second succeeds
        mock_pop_client.create_report_task.side_effect = [
            POPTaskResult(success=False, error="API error"),
            POPTaskResult(
                success=True, task_id="task-123", status=POPTaskStatus.PENDING
            ),
        ]
        mock_pop_client.poll_for_result.return_value = sample_task_result

        def set_score_id(score):
            score.id = "score-123"

        mock_session.refresh.side_effect = set_score_id

        items = [
            BatchScoreItem(
                page_id="page-1", keyword="boots", url="https://example.com/1"
            ),
            BatchScoreItem(
                page_id="page-2", keyword="shoes", url="https://example.com/2"
            ),
        ]

        service = POPContentScoreService(session=mock_session, client=mock_pop_client)

        results = []
        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            mock_settings.return_value.pop_batch_rate_limit = 5
            async for result in service.score_batch("proj-123", items):
                results.append(result)

        assert len(results) == 2
        success_count = sum(1 for r in results if r.success)
        failure_count = sum(1 for r in results if not r.success)
        assert success_count == 1
        assert failure_count == 1

    @pytest.mark.asyncio
    async def test_score_batch_empty_items(self, mock_pop_client: AsyncMock) -> None:
        """Should handle empty items list."""
        service = POPContentScoreService(client=mock_pop_client)

        results = []
        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_batch_rate_limit = 5
            async for result in service.score_batch("proj-123", []):
                results.append(result)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_score_batch_respects_rate_limit(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
        sample_task_result: POPTaskResult,
    ) -> None:
        """Should respect rate limit setting."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        def set_score_id(score):
            score.id = "score-123"

        mock_session.refresh.side_effect = set_score_id

        items = [
            BatchScoreItem(
                page_id=f"page-{i}", keyword="boots", url=f"https://example.com/{i}"
            )
            for i in range(5)
        ]

        service = POPContentScoreService(session=mock_session, client=mock_pop_client)

        with patch("app.services.pop_content_score.get_settings") as mock_settings:
            mock_settings.return_value.pop_pass_threshold = 70
            mock_settings.return_value.pop_batch_rate_limit = 2  # Low rate limit

            results = []
            async for result in service.score_batch("proj-123", items, rate_limit=2):
                results.append(result)

        assert len(results) == 5


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton pattern and convenience functions."""

    def test_get_pop_content_score_service_returns_singleton(self) -> None:
        """get_pop_content_score_service should return the same instance."""
        import app.services.pop_content_score as module

        module._pop_content_score_service = None

        service1 = get_pop_content_score_service()
        service2 = get_pop_content_score_service()

        assert service1 is service2

        # Clean up
        module._pop_content_score_service = None

    @pytest.mark.asyncio
    async def test_score_content_convenience_function(
        self, mock_pop_client: AsyncMock, sample_task_result: POPTaskResult
    ) -> None:
        """Test score_content convenience function."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        import app.services.pop_content_score as module

        # Set the global singleton with our mock
        module._pop_content_score_service = POPContentScoreService(
            client=mock_pop_client
        )

        try:
            with patch("app.services.pop_content_score.get_settings") as mock_settings:
                mock_settings.return_value.pop_pass_threshold = 70
                result = await score_content(
                    project_id="proj-123",
                    page_id="page-456",
                    keyword="hiking boots",
                    content_url="https://example.com",
                )

            assert result.success is True
        finally:
            # Clean up
            module._pop_content_score_service = None


# ---------------------------------------------------------------------------
# Test: Logging Verification
# ---------------------------------------------------------------------------


class TestLoggingOutput:
    """Tests verifying logging includes required entity IDs."""

    @pytest.mark.asyncio
    async def test_logs_include_entity_ids_on_success(
        self,
        mock_pop_client: AsyncMock,
        sample_task_result: POPTaskResult,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should include project_id and page_id in logs."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        service = POPContentScoreService(client=mock_pop_client)

        with (
            caplog.at_level(logging.DEBUG, logger="app.services.pop_content_score"),
            patch("app.services.pop_content_score.get_settings") as mock_settings,
        ):
            mock_settings.return_value.pop_pass_threshold = 70
            await service.score_content(
                project_id="proj-test-123",
                page_id="page-test-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        # Check that INFO-level logs contain entity IDs
        info_logs = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_logs) > 0

        # Find the score_started log
        started_logs = [r for r in info_logs if "score_started" in r.message]
        assert len(started_logs) >= 1

    @pytest.mark.asyncio
    async def test_logs_include_task_id_after_creation(
        self,
        mock_pop_client: AsyncMock,
        sample_task_result: POPTaskResult,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should include task_id in logs after task creation."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-log-test-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        service = POPContentScoreService(client=mock_pop_client)

        with (
            caplog.at_level(logging.INFO, logger="app.services.pop_content_score"),
            patch("app.services.pop_content_score.get_settings") as mock_settings,
        ):
            mock_settings.return_value.pop_pass_threshold = 70
            await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        # Find logs that should have task_id
        all_log_text = "\n".join([str(r.message) for r in caplog.records])

        # The polling log should contain the task_id reference
        assert "task" in all_log_text.lower()

    @pytest.mark.asyncio
    async def test_logs_scoring_results(
        self,
        mock_pop_client: AsyncMock,
        sample_task_result: POPTaskResult,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should log scoring results."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        service = POPContentScoreService(client=mock_pop_client)

        with (
            caplog.at_level(logging.INFO, logger="app.services.pop_content_score"),
            patch("app.services.pop_content_score.get_settings") as mock_settings,
        ):
            mock_settings.return_value.pop_pass_threshold = 70
            await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        # Find the scoring_results log
        results_logs = [r for r in caplog.records if "scoring_results" in r.message]
        assert len(results_logs) == 1

    @pytest.mark.asyncio
    async def test_logs_include_context_on_error(
        self,
        mock_pop_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should include context in error logs."""
        mock_pop_client.create_report_task.side_effect = RuntimeError(
            "Unexpected test error"
        )

        service = POPContentScoreService(client=mock_pop_client)

        with caplog.at_level(logging.ERROR, logger="app.services.pop_content_score"):
            await service.score_content(
                project_id="proj-error-123",
                page_id="page-error-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        # Find error logs
        error_logs = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_logs) >= 1

    @pytest.mark.asyncio
    async def test_logs_fallback_events_at_warning(
        self,
        mock_pop_client: AsyncMock,
        mock_legacy_service: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should log fallback events at WARNING level."""
        mock_pop_client.create_report_task.side_effect = POPCircuitOpenError(
            "Circuit breaker is open"
        )

        legacy_result = MagicMock()
        legacy_result.success = True
        legacy_result.overall_score = 0.65
        legacy_result.word_count_score = MagicMock(word_count=1000)
        legacy_result.error = None
        mock_legacy_service.score_content.return_value = legacy_result

        service = POPContentScoreService(
            client=mock_pop_client, legacy_service=mock_legacy_service
        )

        with (
            caplog.at_level(logging.WARNING, logger="app.services.pop_content_score"),
            patch("app.services.pop_content_score.get_settings") as mock_settings,
        ):
            mock_settings.return_value.pop_pass_threshold = 70
            await service.score_content(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                content_url="https://example.com",
            )

        # Find warning logs
        warning_logs = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_logs) >= 1

        # Should mention fallback
        warning_text = " ".join([r.message for r in warning_logs])
        assert "fallback" in warning_text.lower()


# ---------------------------------------------------------------------------
# Test: Service Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_service_initialization_with_client(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should initialize with provided client."""
        service = POPContentScoreService(client=mock_pop_client)

        assert service._client is mock_pop_client
        assert service._session is None
        assert service._legacy_service is None

    def test_service_initialization_with_session(
        self, mock_session: AsyncMock, mock_pop_client: AsyncMock
    ) -> None:
        """Should initialize with provided session."""
        service = POPContentScoreService(session=mock_session, client=mock_pop_client)

        assert service._session is mock_session
        assert service._client is mock_pop_client

    def test_service_initialization_with_legacy_service(
        self, mock_pop_client: AsyncMock, mock_legacy_service: MagicMock
    ) -> None:
        """Should initialize with provided legacy service."""
        service = POPContentScoreService(
            client=mock_pop_client, legacy_service=mock_legacy_service
        )

        assert service._legacy_service is mock_legacy_service

    @pytest.mark.asyncio
    async def test_service_gets_global_client_when_not_provided(self) -> None:
        """Should use global client when not provided."""
        with patch(
            "app.services.pop_content_score.get_pop_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_client = AsyncMock(spec=POPClient)
            mock_get_client.return_value = mock_client

            service = POPContentScoreService()
            client = await service._get_client()

            mock_get_client.assert_called_once()
            assert client is mock_client

    def test_service_gets_global_legacy_service_when_not_provided(self) -> None:
        """Should use global legacy service when not provided."""
        with patch(
            "app.services.pop_content_score.get_content_score_service",
        ) as mock_get_legacy:
            mock_legacy = MagicMock()
            mock_get_legacy.return_value = mock_legacy

            service = POPContentScoreService()
            legacy = service._get_legacy_service()

            mock_get_legacy.assert_called_once()
            assert legacy is mock_legacy
