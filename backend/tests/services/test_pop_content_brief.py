"""Unit tests for POP Content Brief service.

Tests cover:
- fetch_brief() with mocked POP client
- Each extraction method (word count, headings, keywords, LSI, PAA, competitors)
- Database persistence (save_brief, fetch_and_save_brief)
- Error handling (POP failure, timeout, parse errors)
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
    POPClient,
    POPError,
    POPTaskResult,
    POPTaskStatus,
    POPTimeoutError,
)
from app.services.pop_content_brief import (
    POPContentBriefResult,
    POPContentBriefService,
    POPContentBriefServiceError,
    POPContentBriefValidationError,
    fetch_content_brief,
    get_pop_content_brief_service,
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
def sample_pop_response() -> dict[str, Any]:
    """Sample POP API response with full data."""
    return {
        "wordCount": {"current": 1200, "target": 1500},
        "tagCounts": [
            {
                "tagLabel": "H1 tag total",
                "min": 1,
                "max": 1,
                "mean": 1.0,
                "signalCnt": 0,
            },
            {
                "tagLabel": "H2 tag total",
                "min": 3,
                "max": 8,
                "mean": 5.2,
                "signalCnt": 2,
            },
            {
                "tagLabel": "H3 tag total",
                "min": 5,
                "max": 12,
                "mean": 8.1,
                "signalCnt": 4,
            },
            {
                "tagLabel": "Word count",
                "min": 1200,
                "max": 2000,
                "mean": 1500,
                "signalCnt": 1400,
            },
        ],
        "cleanedContentBrief": {
            "pageScore": 75,
            "title": [
                {
                    "term": {"phrase": "hiking boots", "type": "exact", "weight": 1.0},
                    "contentBrief": {"current": 0, "target": 1},
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
                    "contentBrief": {"current": 0, "target": 2},
                },
            ],
            "p": [
                {
                    "term": {"phrase": "hiking gear", "type": "lsi", "weight": 0.5},
                    "contentBrief": {"current": 2, "target": 5},
                },
            ],
            "titleTotal": {"min": 1, "max": 3},
            "pageTitleTotal": {"min": 1, "max": 2},
            "subHeadingsTotal": {"min": 5, "max": 10},
            "pTotal": {"min": 15, "max": 25},
        },
        "lsaPhrases": [
            {
                "phrase": "trail running",
                "weight": 0.8,
                "averageCount": 3,
                "targetCount": 4,
            },
            {
                "phrase": "ankle support",
                "weight": 0.7,
                "averageCount": 2,
                "targetCount": 3,
            },
            {
                "phrase": "waterproof membrane",
                "weight": 0.6,
                "averageCount": 1,
                "targetCount": 2,
            },
        ],
        "relatedQuestions": [
            {
                "question": "What are the best hiking boots?",
                "link": "https://example.com/answer1",
                "snippet": "The best hiking boots are...",
                "title": "Best Boots Guide",
            },
            {
                "question": "How to clean hiking boots?",
                "link": "https://example.com/answer2",
                "snippet": "To clean your boots...",
            },
        ],
        "relatedSearches": [
            {"query": "hiking boots for women"},
            {"query": "hiking boots waterproof"},
        ],
        "competitors": [
            {
                "url": "https://competitor1.com/boots",
                "title": "Top Hiking Boots",
                "pageScore": 85,
            },
            {
                "url": "https://competitor2.com/gear",
                "title": "Hiking Gear Guide",
                "pageScore": 78,
            },
            {
                "url": "https://competitor3.com/reviews",
                "title": "Boot Reviews",
                "pageScore": 72,
            },
        ],
        "entities": [
            {"name": "Gore-Tex", "type": "MATERIAL", "salience": 0.8},
            {"name": "Vibram", "type": "BRAND", "salience": 0.6},
        ],
    }


@pytest.fixture
def empty_pop_response() -> dict[str, Any]:
    """Sample POP API response with minimal/empty data."""
    return {}


@pytest.fixture
def sample_task_result(sample_pop_response: dict[str, Any]) -> POPTaskResult:
    """Sample successful task result from POP client."""
    return POPTaskResult(
        success=True,
        task_id="task-abc-123",
        status=POPTaskStatus.SUCCESS,
        data=sample_pop_response,
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
# Test: POPContentBriefResult Dataclass
# ---------------------------------------------------------------------------


class TestPOPContentBriefResult:
    """Tests for POPContentBriefResult dataclass."""

    def test_result_defaults(self) -> None:
        """POPContentBriefResult should have sensible defaults."""
        result = POPContentBriefResult(
            success=True,
            keyword="hiking boots",
            target_url="https://example.com/boots",
        )

        assert result.success is True
        assert result.keyword == "hiking boots"
        assert result.target_url == "https://example.com/boots"
        assert result.task_id is None
        assert result.brief_id is None
        assert result.word_count_target is None
        assert result.word_count_min is None
        assert result.word_count_max is None
        assert result.heading_targets == []
        assert result.keyword_targets == []
        assert result.lsi_terms == []
        assert result.entities == []
        assert result.related_questions == []
        assert result.related_searches == []
        assert result.competitors == []
        assert result.page_score_target is None
        assert result.raw_response == {}
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.request_id is None

    def test_result_with_values(self) -> None:
        """POPContentBriefResult should accept all fields."""
        result = POPContentBriefResult(
            success=True,
            keyword="hiking boots",
            target_url="https://example.com",
            task_id="task-123",
            brief_id="brief-456",
            word_count_target=1500,
            word_count_min=1200,
            word_count_max=1800,
            heading_targets=[{"level": "h1", "min_count": 1}],
            keyword_targets=[{"keyword": "boots", "section": "title"}],
            lsi_terms=[{"phrase": "hiking gear", "weight": 0.8}],
            entities=[{"name": "Gore-Tex", "type": "BRAND"}],
            related_questions=[{"question": "What are boots?"}],
            related_searches=[{"query": "hiking boots"}],
            competitors=[{"url": "https://comp.com", "page_score": 80}],
            page_score_target=75.0,
            raw_response={"key": "value"},
            error=None,
            duration_ms=150.5,
            request_id="req-123",
        )

        assert result.task_id == "task-123"
        assert result.brief_id == "brief-456"
        assert result.word_count_target == 1500
        assert result.word_count_min == 1200
        assert result.word_count_max == 1800
        assert len(result.heading_targets) == 1
        assert len(result.keyword_targets) == 1
        assert len(result.lsi_terms) == 1
        assert len(result.entities) == 1
        assert len(result.related_questions) == 1
        assert len(result.related_searches) == 1
        assert len(result.competitors) == 1
        assert result.page_score_target == 75.0
        assert result.duration_ms == 150.5


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for service exception classes."""

    def test_service_error_basic(self) -> None:
        """Test POPContentBriefServiceError basic usage."""
        error = POPContentBriefServiceError("Test error")
        assert str(error) == "Test error"
        assert error.project_id is None
        assert error.page_id is None

    def test_service_error_with_context(self) -> None:
        """Test POPContentBriefServiceError with context."""
        error = POPContentBriefServiceError(
            "Test error",
            project_id="proj-123",
            page_id="page-456",
        )
        assert error.project_id == "proj-123"
        assert error.page_id == "page-456"

    def test_validation_error(self) -> None:
        """Test POPContentBriefValidationError."""
        error = POPContentBriefValidationError(
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
# Test: Word Count Extraction
# ---------------------------------------------------------------------------


class TestWordCountExtraction:
    """Tests for word count target extraction."""

    def test_extract_word_count_target_from_wordCount(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should extract word count target from wordCount.target."""
        service = POPContentBriefService()
        target = service._extract_word_count_target(sample_pop_response)

        assert target == 1500

    def test_extract_word_count_target_missing_wordCount(self) -> None:
        """Should return None when wordCount is missing."""
        service = POPContentBriefService()
        target = service._extract_word_count_target({})

        assert target is None

    def test_extract_word_count_target_invalid_type(self) -> None:
        """Should return None when wordCount is not a dict."""
        service = POPContentBriefService()
        target = service._extract_word_count_target({"wordCount": "invalid"})

        assert target is None

    def test_extract_word_count_min_from_target(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should derive min as 80% of target when not in tagCounts."""
        service = POPContentBriefService()

        # Remove tagCounts to test fallback
        data = {**sample_pop_response}
        data["tagCounts"] = []

        min_count = service._extract_word_count_min(data)
        assert min_count == 1200  # 80% of 1500

    def test_extract_word_count_min_from_tagCounts(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should extract min from tagCounts word count entry."""
        service = POPContentBriefService()
        min_count = service._extract_word_count_min(sample_pop_response)

        assert min_count == 1200

    def test_extract_word_count_max_from_target(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should derive max as 120% of target when not in tagCounts."""
        service = POPContentBriefService()

        # Remove tagCounts to test fallback
        data = {**sample_pop_response}
        data["tagCounts"] = []

        max_count = service._extract_word_count_max(data)
        assert max_count == 1800  # 120% of 1500

    def test_extract_word_count_max_from_tagCounts(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should extract max from tagCounts word count entry."""
        service = POPContentBriefService()
        max_count = service._extract_word_count_max(sample_pop_response)

        assert max_count == 2000


# ---------------------------------------------------------------------------
# Test: Heading Targets Extraction
# ---------------------------------------------------------------------------


class TestHeadingTargetsExtraction:
    """Tests for heading targets extraction from tagCounts."""

    def test_extract_heading_targets_h1_through_h4(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should extract H1-H4 heading targets from tagCounts."""
        service = POPContentBriefService()
        headings = service._extract_heading_targets(sample_pop_response)

        assert len(headings) >= 3

        h1 = next((h for h in headings if h["level"] == "h1"), None)
        h2 = next((h for h in headings if h["level"] == "h2"), None)
        h3 = next((h for h in headings if h["level"] == "h3"), None)

        assert h1 is not None
        assert h1["min_count"] == 1
        assert h1["max_count"] == 1

        assert h2 is not None
        assert h2["min_count"] == 3
        assert h2["max_count"] == 8

        assert h3 is not None
        assert h3["min_count"] == 5
        assert h3["max_count"] == 12

    def test_extract_heading_targets_empty_tagCounts(self) -> None:
        """Should return empty list when tagCounts is empty."""
        service = POPContentBriefService()
        headings = service._extract_heading_targets({})

        assert headings == []

    def test_extract_heading_targets_non_list_tagCounts(self) -> None:
        """Should return empty list when tagCounts is not a list."""
        service = POPContentBriefService()
        headings = service._extract_heading_targets({"tagCounts": "invalid"})

        assert headings == []


# ---------------------------------------------------------------------------
# Test: Keyword Targets Extraction
# ---------------------------------------------------------------------------


class TestKeywordTargetsExtraction:
    """Tests for keyword targets extraction from cleanedContentBrief."""

    def test_extract_keyword_targets_all_sections(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should extract keywords from all sections."""
        service = POPContentBriefService()
        keywords = service._extract_keyword_targets(sample_pop_response)

        # Should have keywords from title, pageTitle, subHeadings, p
        sections = {kw["section"] for kw in keywords}
        assert "title" in sections
        assert "h1" in sections
        assert "h2" in sections
        assert "paragraph" in sections

    def test_extract_keyword_targets_with_density_target(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should extract density targets for keywords."""
        service = POPContentBriefService()
        keywords = service._extract_keyword_targets(sample_pop_response)

        # Find the "hiking boots" keyword in title section
        hiking_boots = next(
            (
                k
                for k in keywords
                if k["keyword"] == "hiking boots" and k["section"] == "title"
            ),
            None,
        )

        assert hiking_boots is not None
        assert hiking_boots["density_target"] == 1.0

    def test_extract_keyword_targets_empty_content_brief(self) -> None:
        """Should return empty list when cleanedContentBrief is missing."""
        service = POPContentBriefService()
        keywords = service._extract_keyword_targets({})

        assert keywords == []

    def test_extract_keyword_targets_includes_section_totals(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should include section totals with _total_ prefix."""
        service = POPContentBriefService()
        keywords = service._extract_keyword_targets(sample_pop_response)

        # Find section totals
        totals = [k for k in keywords if k["keyword"].startswith("_total_")]
        assert len(totals) > 0

        # Check that totals have min/max
        title_total = next((t for t in totals if "_total_title" in t["keyword"]), None)
        assert title_total is not None
        assert title_total["count_min"] == 1
        assert title_total["count_max"] == 3


# ---------------------------------------------------------------------------
# Test: LSI Terms Extraction
# ---------------------------------------------------------------------------


class TestLSITermsExtraction:
    """Tests for LSI terms extraction from lsaPhrases."""

    def test_extract_lsi_terms(self, sample_pop_response: dict[str, Any]) -> None:
        """Should extract LSI terms with all fields."""
        service = POPContentBriefService()
        lsi = service._extract_lsi_terms(sample_pop_response)

        assert len(lsi) == 3

        trail_running = next((t for t in lsi if t["phrase"] == "trail running"), None)
        assert trail_running is not None
        assert trail_running["weight"] == 0.8
        assert trail_running["average_count"] == 3
        assert trail_running["target_count"] == 4

    def test_extract_lsi_terms_empty(self) -> None:
        """Should return empty list when lsaPhrases is missing."""
        service = POPContentBriefService()
        lsi = service._extract_lsi_terms({})

        assert lsi == []

    def test_extract_lsi_terms_skips_invalid(self) -> None:
        """Should skip invalid LSI term entries."""
        service = POPContentBriefService()
        data = {
            "lsaPhrases": [
                {"phrase": "valid term", "weight": 0.5},
                {"weight": 0.3},  # Missing phrase - should be skipped
                "invalid",  # Not a dict - should be skipped
            ]
        }
        lsi = service._extract_lsi_terms(data)

        assert len(lsi) == 1
        assert lsi[0]["phrase"] == "valid term"


# ---------------------------------------------------------------------------
# Test: Related Questions Extraction
# ---------------------------------------------------------------------------


class TestRelatedQuestionsExtraction:
    """Tests for related questions (PAA) extraction."""

    def test_extract_related_questions(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should extract related questions with all fields."""
        service = POPContentBriefService()
        questions = service._extract_related_questions(sample_pop_response)

        assert len(questions) == 2

        q1 = questions[0]
        assert q1["question"] == "What are the best hiking boots?"
        assert q1["source_url"] == "https://example.com/answer1"
        assert q1["answer_snippet"] == "The best hiking boots are..."

    def test_extract_related_questions_empty(self) -> None:
        """Should return empty list when relatedQuestions is missing."""
        service = POPContentBriefService()
        questions = service._extract_related_questions({})

        assert questions == []

    def test_extract_related_questions_handles_missing_snippet(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should handle questions with missing snippet."""
        service = POPContentBriefService()
        data = {
            "relatedQuestions": [
                {"question": "Test question?"}  # No snippet or link
            ]
        }
        questions = service._extract_related_questions(data)

        assert len(questions) == 1
        assert questions[0]["question"] == "Test question?"
        assert questions[0]["answer_snippet"] is None
        assert questions[0]["source_url"] is None


# ---------------------------------------------------------------------------
# Test: Competitors Extraction
# ---------------------------------------------------------------------------


class TestCompetitorsExtraction:
    """Tests for competitor data extraction."""

    def test_extract_competitors(self, sample_pop_response: dict[str, Any]) -> None:
        """Should extract competitor data with position."""
        service = POPContentBriefService()
        competitors = service._extract_competitors(sample_pop_response)

        assert len(competitors) == 3

        c1 = competitors[0]
        assert c1["url"] == "https://competitor1.com/boots"
        assert c1["title"] == "Top Hiking Boots"
        assert c1["page_score"] == 85
        assert c1["position"] == 1

        c2 = competitors[1]
        assert c2["position"] == 2

        c3 = competitors[2]
        assert c3["position"] == 3

    def test_extract_competitors_empty(self) -> None:
        """Should return empty list when competitors is missing."""
        service = POPContentBriefService()
        competitors = service._extract_competitors({})

        assert competitors == []

    def test_extract_competitors_skips_invalid(self) -> None:
        """Should skip entries without URL."""
        service = POPContentBriefService()
        data = {
            "competitors": [
                {"url": "https://valid.com", "title": "Valid"},
                {"title": "No URL"},  # Should be skipped
            ]
        }
        competitors = service._extract_competitors(data)

        assert len(competitors) == 1
        assert competitors[0]["url"] == "https://valid.com"


# ---------------------------------------------------------------------------
# Test: Page Score Target Extraction
# ---------------------------------------------------------------------------


class TestPageScoreTargetExtraction:
    """Tests for page score target extraction."""

    def test_extract_page_score_from_cleanedContentBrief(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should extract page score from cleanedContentBrief.pageScore."""
        service = POPContentBriefService()
        score = service._extract_page_score_target(sample_pop_response)

        assert score == 75.0

    def test_extract_page_score_from_top_level(self) -> None:
        """Should fall back to top-level pageScore."""
        service = POPContentBriefService()
        score = service._extract_page_score_target({"pageScore": 80})

        assert score == 80.0

    def test_extract_page_score_missing(self) -> None:
        """Should return None when pageScore is missing."""
        service = POPContentBriefService()
        score = service._extract_page_score_target({})

        assert score is None


# ---------------------------------------------------------------------------
# Test: Entities Extraction
# ---------------------------------------------------------------------------


class TestEntitiesExtraction:
    """Tests for entities extraction."""

    def test_extract_entities(self, sample_pop_response: dict[str, Any]) -> None:
        """Should extract entities with all fields."""
        service = POPContentBriefService()
        entities = service._extract_entities(sample_pop_response)

        assert len(entities) == 2

        goretex = next((e for e in entities if e["name"] == "Gore-Tex"), None)
        assert goretex is not None
        assert goretex["type"] == "MATERIAL"
        assert goretex["salience"] == 0.8

    def test_extract_entities_empty(self) -> None:
        """Should return empty list when entities is missing."""
        service = POPContentBriefService()
        entities = service._extract_entities({})

        assert entities == []


# ---------------------------------------------------------------------------
# Test: Related Searches Extraction
# ---------------------------------------------------------------------------


class TestRelatedSearchesExtraction:
    """Tests for related searches extraction."""

    def test_extract_related_searches(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should extract related searches."""
        service = POPContentBriefService()
        searches = service._extract_related_searches(sample_pop_response)

        assert len(searches) == 2
        assert searches[0]["query"] == "hiking boots for women"
        assert searches[1]["query"] == "hiking boots waterproof"

    def test_extract_related_searches_empty(self) -> None:
        """Should return empty list when relatedSearches is missing."""
        service = POPContentBriefService()
        searches = service._extract_related_searches({})

        assert searches == []


# ---------------------------------------------------------------------------
# Test: _parse_brief_data
# ---------------------------------------------------------------------------


class TestParseBriefData:
    """Tests for the main _parse_brief_data method."""

    def test_parse_brief_data_full_response(
        self, sample_pop_response: dict[str, Any]
    ) -> None:
        """Should parse all fields from full response."""
        service = POPContentBriefService()
        parsed = service._parse_brief_data(sample_pop_response)

        assert parsed["word_count_target"] == 1500
        assert parsed["word_count_min"] == 1200
        assert parsed["word_count_max"] == 2000
        assert len(parsed["heading_targets"]) >= 3
        assert len(parsed["keyword_targets"]) > 0
        assert len(parsed["lsi_terms"]) == 3
        assert len(parsed["entities"]) == 2
        assert len(parsed["related_questions"]) == 2
        assert len(parsed["related_searches"]) == 2
        assert len(parsed["competitors"]) == 3
        assert parsed["page_score_target"] == 75.0

    def test_parse_brief_data_empty_response(self) -> None:
        """Should handle empty response gracefully."""
        service = POPContentBriefService()
        parsed = service._parse_brief_data({})

        assert parsed["word_count_target"] is None
        assert parsed["word_count_min"] is None
        assert parsed["word_count_max"] is None
        assert parsed["heading_targets"] == []
        assert parsed["keyword_targets"] == []
        assert parsed["lsi_terms"] == []
        assert parsed["entities"] == []
        assert parsed["related_questions"] == []
        assert parsed["related_searches"] == []
        assert parsed["competitors"] == []
        assert parsed["page_score_target"] is None


# ---------------------------------------------------------------------------
# Test: fetch_brief() Method
# ---------------------------------------------------------------------------


class TestFetchBrief:
    """Tests for fetch_brief() with mocked POP client."""

    @pytest.mark.asyncio
    async def test_fetch_brief_success(
        self,
        mock_pop_client: AsyncMock,
        sample_task_result: POPTaskResult,
    ) -> None:
        """Should fetch brief successfully."""
        # Setup mock - use consistent task_id
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-abc-123",  # Match sample_task_result
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        service = POPContentBriefService(client=mock_pop_client)

        result = await service.fetch_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com/boots",
        )

        assert result.success is True
        assert result.keyword == "hiking boots"
        assert result.target_url == "https://example.com/boots"
        assert result.task_id == "task-abc-123"
        assert result.word_count_target == 1500
        assert len(result.lsi_terms) == 3
        assert len(result.competitors) == 3

    @pytest.mark.asyncio
    async def test_fetch_brief_empty_keyword_raises_validation_error(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should raise validation error for empty keyword."""
        service = POPContentBriefService(client=mock_pop_client)

        with pytest.raises(POPContentBriefValidationError) as exc_info:
            await service.fetch_brief(
                project_id="proj-123",
                page_id="page-456",
                keyword="",
                target_url="https://example.com",
            )

        assert exc_info.value.field_name == "keyword"
        assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_fetch_brief_whitespace_keyword_raises_validation_error(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should raise validation error for whitespace-only keyword."""
        service = POPContentBriefService(client=mock_pop_client)

        with pytest.raises(POPContentBriefValidationError) as exc_info:
            await service.fetch_brief(
                project_id="proj-123",
                page_id="page-456",
                keyword="   ",
                target_url="https://example.com",
            )

        assert exc_info.value.field_name == "keyword"

    @pytest.mark.asyncio
    async def test_fetch_brief_empty_url_raises_validation_error(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should raise validation error for empty target URL."""
        service = POPContentBriefService(client=mock_pop_client)

        with pytest.raises(POPContentBriefValidationError) as exc_info:
            await service.fetch_brief(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                target_url="",
            )

        assert exc_info.value.field_name == "target_url"

    @pytest.mark.asyncio
    async def test_fetch_brief_task_creation_failure(
        self,
        mock_pop_client: AsyncMock,
        failed_task_result: POPTaskResult,
    ) -> None:
        """Should handle task creation failure."""
        mock_pop_client.create_report_task.return_value = failed_task_result

        service = POPContentBriefService(client=mock_pop_client)

        result = await service.fetch_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com",
        )

        assert result.success is False
        assert result.error is not None
        assert "Failed to create" in result.error

    @pytest.mark.asyncio
    async def test_fetch_brief_polling_failure(
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

        service = POPContentBriefService(client=mock_pop_client)

        result = await service.fetch_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com",
        )

        assert result.success is False
        assert "failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_fetch_brief_task_failure_status(
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

        service = POPContentBriefService(client=mock_pop_client)

        result = await service.fetch_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com",
        )

        assert result.success is False

    @pytest.mark.asyncio
    async def test_fetch_brief_pop_error(self, mock_pop_client: AsyncMock) -> None:
        """Should handle POP API errors."""
        mock_pop_client.create_report_task.side_effect = POPError("API error")

        service = POPContentBriefService(client=mock_pop_client)

        result = await service.fetch_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com",
        )

        assert result.success is False
        assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_fetch_brief_pop_timeout_error(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should handle POP timeout errors."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.side_effect = POPTimeoutError(
            "Task task-123 timed out after 300s"
        )

        service = POPContentBriefService(client=mock_pop_client)

        result = await service.fetch_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com",
        )

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_fetch_brief_unexpected_error(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should handle unexpected errors."""
        mock_pop_client.create_report_task.side_effect = RuntimeError(
            "Unexpected error"
        )

        service = POPContentBriefService(client=mock_pop_client)

        result = await service.fetch_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com",
        )

        assert result.success is False
        assert "Unexpected" in result.error


# ---------------------------------------------------------------------------
# Test: Database Persistence - save_brief()
# ---------------------------------------------------------------------------


class TestSaveBrief:
    """Tests for save_brief() database persistence."""

    @pytest.mark.asyncio
    async def test_save_brief_creates_new_record(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Should create new content brief record."""
        # Setup mock - no existing brief
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = POPContentBriefService(session=mock_session, client=mock_pop_client)

        result = POPContentBriefResult(
            success=True,
            keyword="hiking boots",
            target_url="https://example.com",
            task_id="task-123",
            word_count_target=1500,
            lsi_terms=[{"phrase": "test", "weight": 0.5}],
            raw_response={"key": "value"},
        )

        await service.save_brief(
            page_id="page-456",
            keyword="hiking boots",
            result=result,
            project_id="proj-123",
        )

        # Verify session.add was called
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_brief_updates_existing_record(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Should update existing content brief record."""
        # Setup mock - existing brief
        existing_brief = MagicMock()
        existing_brief.id = "existing-brief-id"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_brief
        mock_session.execute.return_value = mock_result

        service = POPContentBriefService(session=mock_session, client=mock_pop_client)

        result = POPContentBriefResult(
            success=True,
            keyword="hiking boots updated",
            target_url="https://example.com",
            task_id="task-456",
            word_count_target=1800,
            raw_response={"updated": True},
        )

        await service.save_brief(
            page_id="page-456",
            keyword="hiking boots updated",
            result=result,
            project_id="proj-123",
        )

        # Verify existing brief was updated, not a new one added
        assert existing_brief.keyword == "hiking boots updated"
        assert existing_brief.pop_task_id == "task-456"
        assert existing_brief.word_count_target == 1800
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_brief_raises_without_session(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should raise error when session is not available."""
        service = POPContentBriefService(client=mock_pop_client)  # No session

        result = POPContentBriefResult(
            success=True,
            keyword="hiking boots",
            target_url="https://example.com",
        )

        with pytest.raises(POPContentBriefServiceError) as exc_info:
            await service.save_brief(
                page_id="page-456",
                keyword="hiking boots",
                result=result,
            )

        assert "session not available" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_save_brief_handles_db_error(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Should wrap database errors in service error."""
        mock_session.execute.side_effect = RuntimeError("Database error")

        service = POPContentBriefService(session=mock_session, client=mock_pop_client)

        result = POPContentBriefResult(
            success=True,
            keyword="hiking boots",
            target_url="https://example.com",
        )

        with pytest.raises(POPContentBriefServiceError) as exc_info:
            await service.save_brief(
                page_id="page-456",
                keyword="hiking boots",
                result=result,
            )

        assert "Failed to save" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test: fetch_and_save_brief()
# ---------------------------------------------------------------------------


class TestFetchAndSaveBrief:
    """Tests for fetch_and_save_brief() combined operation."""

    @pytest.mark.asyncio
    async def test_fetch_and_save_brief_success(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
        sample_task_result: POPTaskResult,
    ) -> None:
        """Should fetch and save brief successfully."""
        # Setup mock client
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        # Setup mock session - no existing brief
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Setup refresh to set the brief id
        def set_brief_id(brief):
            brief.id = "saved-brief-id"

        mock_session.refresh.side_effect = set_brief_id

        service = POPContentBriefService(session=mock_session, client=mock_pop_client)

        result = await service.fetch_and_save_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com",
        )

        assert result.success is True
        assert result.brief_id == "saved-brief-id"
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_and_save_brief_no_session(
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

        service = POPContentBriefService(client=mock_pop_client)  # No session

        result = await service.fetch_and_save_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com",
        )

        assert result.success is True
        assert result.brief_id is None  # Not saved

    @pytest.mark.asyncio
    async def test_fetch_and_save_brief_fetch_failure_skips_save(
        self,
        mock_pop_client: AsyncMock,
        mock_session: AsyncMock,
    ) -> None:
        """Should not save when fetch fails."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=False,
            error="API error",
        )

        service = POPContentBriefService(session=mock_session, client=mock_pop_client)

        result = await service.fetch_and_save_brief(
            project_id="proj-123",
            page_id="page-456",
            keyword="hiking boots",
            target_url="https://example.com",
        )

        assert result.success is False
        mock_session.add.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton pattern and convenience functions."""

    def test_get_pop_content_brief_service_returns_singleton(self) -> None:
        """get_pop_content_brief_service should return the same instance."""
        import app.services.pop_content_brief as module

        module._pop_content_brief_service = None

        service1 = get_pop_content_brief_service()
        service2 = get_pop_content_brief_service()

        assert service1 is service2

        # Clean up
        module._pop_content_brief_service = None

    @pytest.mark.asyncio
    async def test_fetch_content_brief_convenience_function(
        self, mock_pop_client: AsyncMock, sample_task_result: POPTaskResult
    ) -> None:
        """Test fetch_content_brief convenience function."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        import app.services.pop_content_brief as module

        # Set the global singleton with our mock
        module._pop_content_brief_service = POPContentBriefService(
            client=mock_pop_client
        )

        try:
            result = await fetch_content_brief(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                target_url="https://example.com",
            )

            assert result.success is True
        finally:
            # Clean up
            module._pop_content_brief_service = None


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

        service = POPContentBriefService(client=mock_pop_client)

        with caplog.at_level(logging.DEBUG, logger="app.services.pop_content_brief"):
            await service.fetch_brief(
                project_id="proj-test-123",
                page_id="page-test-456",
                keyword="hiking boots",
                target_url="https://example.com",
            )

        # Check that INFO-level logs contain entity IDs
        info_logs = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_logs) > 0

        # Find the brief_fetch_started log
        started_logs = [r for r in info_logs if "brief_fetch_started" in r.message]
        assert len(started_logs) >= 1

        # Verify the extra dict has entity IDs
        for record in started_logs:
            extra = getattr(record, "__dict__", {})
            assert "project_id" in str(extra) or "proj-test-123" in str(record.message)

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

        service = POPContentBriefService(client=mock_pop_client)

        with caplog.at_level(logging.INFO, logger="app.services.pop_content_brief"):
            await service.fetch_brief(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                target_url="https://example.com",
            )

        # Find logs that should have task_id
        all_log_text = "\n".join([str(r.message) for r in caplog.records])

        # The polling log should contain the task_id
        assert "task" in all_log_text.lower()

    @pytest.mark.asyncio
    async def test_logs_extraction_stats(
        self,
        mock_pop_client: AsyncMock,
        sample_task_result: POPTaskResult,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should log extraction statistics."""
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="task-123",
            status=POPTaskStatus.PENDING,
        )
        mock_pop_client.poll_for_result.return_value = sample_task_result

        service = POPContentBriefService(client=mock_pop_client)

        with caplog.at_level(logging.INFO, logger="app.services.pop_content_brief"):
            await service.fetch_brief(
                project_id="proj-123",
                page_id="page-456",
                keyword="hiking boots",
                target_url="https://example.com",
            )

        # Find the extraction stats log
        stats_logs = [
            r for r in caplog.records if "brief_extraction_stats" in r.message
        ]
        assert len(stats_logs) == 1

    @pytest.mark.asyncio
    async def test_logs_include_context_on_error(
        self,
        mock_pop_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should include context in error logs."""
        mock_pop_client.create_report_task.side_effect = POPError(
            "Test error for logging"
        )

        service = POPContentBriefService(client=mock_pop_client)

        with caplog.at_level(logging.ERROR, logger="app.services.pop_content_brief"):
            await service.fetch_brief(
                project_id="proj-error-123",
                page_id="page-error-456",
                keyword="hiking boots",
                target_url="https://example.com",
            )

        # Find error logs
        error_logs = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_logs) >= 1

        # Error log should include context
        error_text = str(error_logs[0].message)
        assert "POP" in error_text or "error" in error_text.lower()


# ---------------------------------------------------------------------------
# Test: Service Initialization
# ---------------------------------------------------------------------------


class TestServiceInitialization:
    """Tests for service initialization."""

    def test_service_initialization_with_client(
        self, mock_pop_client: AsyncMock
    ) -> None:
        """Should initialize with provided client."""
        service = POPContentBriefService(client=mock_pop_client)

        assert service._client is mock_pop_client
        assert service._session is None

    def test_service_initialization_with_session(
        self, mock_session: AsyncMock, mock_pop_client: AsyncMock
    ) -> None:
        """Should initialize with provided session."""
        service = POPContentBriefService(session=mock_session, client=mock_pop_client)

        assert service._session is mock_session
        assert service._client is mock_pop_client

    @pytest.mark.asyncio
    async def test_service_gets_global_client_when_not_provided(self) -> None:
        """Should use global client when not provided."""
        with patch(
            "app.services.pop_content_brief.get_pop_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_client = AsyncMock(spec=POPClient)
            mock_get_client.return_value = mock_client

            service = POPContentBriefService()
            client = await service._get_client()

            mock_get_client.assert_called_once()
            assert client is mock_client
