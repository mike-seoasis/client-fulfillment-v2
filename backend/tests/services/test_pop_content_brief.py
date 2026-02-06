"""Tests for POP content brief service.

Tests cover:
- Parse helpers: lsi_terms, related_searches, competitors, related_questions,
  heading_targets, keyword_targets, word_count_range, page_score
- Mock mode returns full 3-step fixture data
- Caching returns existing brief without API call
- force_refresh bypasses cache and updates existing brief
- Error handling returns failure result
"""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pop import POPMockClient, POPTaskResult, POPTaskStatus, POPTimeoutError
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.project import Project
from app.services.pop_content_brief import (
    ContentBriefResult,
    _parse_competitors,
    _parse_heading_targets,
    _parse_keyword_targets,
    _parse_lsi_terms,
    _parse_page_score,
    _parse_related_questions,
    _parse_related_searches,
    _parse_word_count_range,
    fetch_content_brief,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    """Create a test project."""
    project = Project(
        name="Brief Test Project",
        site_url="https://brief-test.example.com",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def crawled_page(db_session: AsyncSession, project: Project) -> CrawledPage:
    """Create a test crawled page."""
    page = CrawledPage(
        project_id=project.id,
        normalized_url="https://brief-test.example.com/shoes",
        status="completed",
        title="Running Shoes",
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)
    return page


# ---------------------------------------------------------------------------
# Parse helper tests — existing
# ---------------------------------------------------------------------------


class TestParseLsiTerms:
    """Tests for _parse_lsi_terms helper."""

    def test_parses_valid_lsa_phrases(self) -> None:
        response = {
            "lsaPhrases": [
                {"phrase": "running shoes", "weight": 85, "averageCount": 3.2, "targetCount": 4},
                {"phrase": "athletic footwear", "weight": 60, "averageCount": 1.5, "targetCount": 2},
            ]
        }
        result = _parse_lsi_terms(response)
        assert len(result) == 2
        assert result[0]["phrase"] == "running shoes"
        assert result[0]["weight"] == 85
        assert result[1]["targetCount"] == 2

    def test_returns_empty_for_missing_key(self) -> None:
        assert _parse_lsi_terms({}) == []

    def test_returns_empty_for_non_list(self) -> None:
        assert _parse_lsi_terms({"lsaPhrases": "invalid"}) == []

    def test_skips_items_without_phrase(self) -> None:
        response = {
            "lsaPhrases": [
                {"phrase": "valid term", "weight": 50},
                {"weight": 30},  # no phrase key
                "just a string",
            ]
        }
        result = _parse_lsi_terms(response)
        assert len(result) == 1
        assert result[0]["phrase"] == "valid term"

    def test_defaults_missing_fields_to_zero(self) -> None:
        response = {"lsaPhrases": [{"phrase": "minimal term"}]}
        result = _parse_lsi_terms(response)
        assert result[0]["weight"] == 0
        assert result[0]["averageCount"] == 0
        assert result[0]["targetCount"] == 0


class TestParseRelatedSearches:
    """Tests for _parse_related_searches helper."""

    def test_parses_valid_variations(self) -> None:
        response = {"variations": ["shoes online", "best running shoes"]}
        result = _parse_related_searches(response)
        assert result == ["shoes online", "best running shoes"]

    def test_returns_empty_for_missing_key(self) -> None:
        assert _parse_related_searches({}) == []

    def test_returns_empty_for_non_list(self) -> None:
        assert _parse_related_searches({"variations": 42}) == []

    def test_filters_non_strings(self) -> None:
        response = {"variations": ["valid", 123, None, "also valid"]}
        result = _parse_related_searches(response)
        assert result == ["valid", "also valid"]


# ---------------------------------------------------------------------------
# Parse helper tests — new (3-step data)
# ---------------------------------------------------------------------------


class TestParseCompetitors:
    """Tests for _parse_competitors helper."""

    def test_parses_valid_competitors(self) -> None:
        response = {
            "competitors": [
                {
                    "url": "https://example.com/shoes",
                    "h2Texts": ["Best Shoes", "Top Picks"],
                    "h3Texts": ["Price Range"],
                    "pageScore": 85.5,
                    "wordCount": 1200,
                },
                {
                    "url": "https://other.com/shoes",
                    "pageScore": 72.0,
                    "wordCount": 800,
                },
            ]
        }
        result = _parse_competitors(response)
        assert len(result) == 2
        assert result[0]["url"] == "https://example.com/shoes"
        assert result[0]["pageScore"] == 85.5
        assert result[0]["wordCount"] == 1200
        assert len(result[0]["h2Texts"]) == 2
        # Missing lists default to empty
        assert result[1]["h2Texts"] == []
        assert result[1]["h3Texts"] == []

    def test_returns_empty_for_missing_key(self) -> None:
        assert _parse_competitors({}) == []

    def test_returns_empty_for_non_list(self) -> None:
        assert _parse_competitors({"competitors": "invalid"}) == []

    def test_skips_non_dict_items(self) -> None:
        response = {"competitors": [{"url": "https://a.com"}, "not a dict", 123]}
        result = _parse_competitors(response)
        assert len(result) == 1


class TestParseRelatedQuestions:
    """Tests for _parse_related_questions helper."""

    def test_parses_valid_questions(self) -> None:
        response = {
            "relatedQuestions": [
                "What are the best running shoes?",
                "How to choose running shoes?",
            ]
        }
        result = _parse_related_questions(response)
        assert len(result) == 2
        assert "best running shoes" in result[0]

    def test_returns_empty_for_missing_key(self) -> None:
        assert _parse_related_questions({}) == []

    def test_filters_non_strings(self) -> None:
        response = {"relatedQuestions": ["valid question?", 42, None]}
        result = _parse_related_questions(response)
        assert result == ["valid question?"]


class TestParseHeadingTargets:
    """Tests for _parse_heading_targets helper."""

    def test_parses_from_page_structure(self) -> None:
        response = {
            "pageStructure": [
                {"signal": "H1", "mean": 1.0, "min": 1, "max": 1},
                {"signal": "H2", "mean": 5.3, "min": 3, "max": 8},
                {"signal": "H3", "mean": 8.0, "min": 5, "max": 12},
                {"signal": "Paragraph Text", "mean": 12.0, "min": 8, "max": 15},
            ]
        }
        result = _parse_heading_targets(response)
        assert len(result) == 4
        assert result[0]["tag"] == "H1"
        assert result[0]["target"] == 1
        assert result[0]["min"] == 1
        assert result[0]["max"] == 1
        assert result[1]["target"] == 5  # round(5.3)
        assert result[0]["source"] == "recommendations"

    def test_falls_back_to_tag_counts(self) -> None:
        response = {
            "tagCounts": {"h1": 1, "h2": 4, "h3": 7}
        }
        result = _parse_heading_targets(response)
        assert len(result) == 3
        assert any(h["tag"] == "h2" and h["target"] == 4 for h in result)
        assert all(h["source"] == "tagCounts" for h in result)

    def test_prefers_page_structure_over_tag_counts(self) -> None:
        response = {
            "pageStructure": [{"signal": "H2", "mean": 6.0, "min": 3, "max": 10}],
            "tagCounts": {"h2": 4},
        }
        result = _parse_heading_targets(response)
        assert len(result) == 1
        assert result[0]["target"] == 6
        assert result[0]["source"] == "recommendations"

    def test_returns_empty_for_no_data(self) -> None:
        assert _parse_heading_targets({}) == []


class TestParseKeywordTargets:
    """Tests for _parse_keyword_targets helper."""

    def test_parses_exact_and_lsi(self) -> None:
        response = {
            "exactKeyword": [
                {"signal": "Meta Title", "target": 1, "comment": "Include keyword"},
                {"signal": "H1", "target": 1, "comment": "Use in H1"},
            ],
            "lsi": [
                {"signal": "Paragraph Text", "phrase": "best shoes", "target": 3},
                {"signal": "Bold", "phrase": "running", "target": 1},
            ],
        }
        result = _parse_keyword_targets(response)
        assert len(result) == 4
        exact_targets = [t for t in result if t["type"] == "exact"]
        lsi_targets = [t for t in result if t["type"] == "lsi"]
        assert len(exact_targets) == 2
        assert len(lsi_targets) == 2
        assert exact_targets[0]["comment"] == "Include keyword"
        assert lsi_targets[0]["phrase"] == "best shoes"

    def test_returns_empty_for_missing_keys(self) -> None:
        assert _parse_keyword_targets({}) == []

    def test_handles_partial_data(self) -> None:
        response = {
            "exactKeyword": [{"signal": "H1", "target": 1}],
        }
        result = _parse_keyword_targets(response)
        assert len(result) == 1
        assert result[0]["type"] == "exact"


class TestParseWordCountRange:
    """Tests for _parse_word_count_range helper."""

    def test_parses_valid_range(self) -> None:
        response = {
            "wordCount": {
                "avg": 1000,
                "competitorsMin": 600,
                "competitorsMax": 1500,
            }
        }
        wc_min, wc_max = _parse_word_count_range(response)
        assert wc_min == 600
        assert wc_max == 1500

    def test_returns_none_for_missing_key(self) -> None:
        wc_min, wc_max = _parse_word_count_range({})
        assert wc_min is None
        assert wc_max is None

    def test_returns_none_for_non_dict(self) -> None:
        wc_min, wc_max = _parse_word_count_range({"wordCount": 500})
        assert wc_min is None
        assert wc_max is None

    def test_derives_range_from_competitors(self) -> None:
        response = {
            "competitors": [
                {"url": "a.com", "wordCount": 800},
                {"url": "b.com", "wordCount": 1500},
                {"url": "c.com", "wordCount": 1100},
            ]
        }
        wc_min, wc_max = _parse_word_count_range(response)
        assert wc_min == 800
        assert wc_max == 1500

    def test_derives_range_from_target(self) -> None:
        response = {"wordCount": {"target": 2000, "current": 0}}
        wc_min, wc_max = _parse_word_count_range(response)
        assert wc_min == 1600  # 2000 * 0.8
        assert wc_max == 2400  # 2000 * 1.2

    def test_competitors_take_priority_over_target(self) -> None:
        response = {
            "competitors": [
                {"url": "a.com", "wordCount": 500},
                {"url": "b.com", "wordCount": 900},
            ],
            "wordCount": {"target": 2000, "current": 0},
        }
        wc_min, wc_max = _parse_word_count_range(response)
        assert wc_min == 500
        assert wc_max == 900


class TestParsePageScore:
    """Tests for _parse_page_score helper."""

    def test_parses_valid_score(self) -> None:
        assert _parse_page_score({"pageScore": 85.5}) == 85.5

    def test_parses_int_score(self) -> None:
        assert _parse_page_score({"pageScore": 90}) == 90.0

    def test_returns_none_for_missing(self) -> None:
        assert _parse_page_score({}) is None

    def test_returns_none_for_invalid(self) -> None:
        assert _parse_page_score({"pageScore": "not a number"}) is None

    def test_falls_back_to_competitor_avg(self) -> None:
        response = {
            "pageScore": None,
            "competitors": [
                {"url": "a.com", "pageScore": 80},
                {"url": "b.com", "pageScore": 90},
            ],
        }
        assert _parse_page_score(response) == 85.0

    def test_returns_none_when_no_scores_anywhere(self) -> None:
        response = {
            "pageScore": None,
            "competitors": [{"url": "a.com", "pageScore": None}],
        }
        assert _parse_page_score(response) is None


# ---------------------------------------------------------------------------
# Mock mode tests
# ---------------------------------------------------------------------------


class TestFetchContentBriefMockMode:
    """Tests for fetch_content_brief with POPMockClient."""

    @pytest.mark.asyncio
    async def test_mock_returns_fixture_data(
        self, db_session: AsyncSession, crawled_page: CrawledPage
    ) -> None:
        """Mock mode returns fixture data with lsi_terms, related_searches, raw_response."""
        mock_client = POPMockClient()

        with patch("app.services.pop_content_brief.get_pop_client", return_value=mock_client):
            result = await fetch_content_brief(
                db=db_session,
                crawled_page=crawled_page,
                keyword="running shoes",
                target_url="https://brief-test.example.com/shoes",
            )

        assert result.success is True
        assert result.content_brief is not None
        assert result.cached is False

        brief = result.content_brief
        assert brief.keyword == "running shoes"
        assert brief.page_id == crawled_page.id
        assert len(brief.lsi_terms) >= 15  # Mock generates 15-25 terms
        assert len(brief.related_searches) >= 5  # Mock generates 5-10 variations
        assert brief.raw_response is not None
        assert "lsaPhrases" in brief.raw_response
        assert brief.pop_task_id is not None

    @pytest.mark.asyncio
    async def test_mock_returns_3step_data(
        self, db_session: AsyncSession, crawled_page: CrawledPage
    ) -> None:
        """Mock mode returns all 3-step fields populated."""
        mock_client = POPMockClient()

        with patch("app.services.pop_content_brief.get_pop_client", return_value=mock_client):
            result = await fetch_content_brief(
                db=db_session,
                crawled_page=crawled_page,
                keyword="running shoes",
                target_url="https://brief-test.example.com/shoes",
            )

        assert result.success is True
        brief = result.content_brief
        assert brief is not None

        # Step 2 data (create-report)
        assert len(brief.competitors) == 3
        assert len(brief.related_questions) >= 5
        assert brief.page_score_target is not None
        assert brief.page_score_target > 0
        assert brief.word_count_min is not None
        assert brief.word_count_max is not None
        assert brief.word_count_min < brief.word_count_max

        # Step 3 data (recommendations)
        assert len(brief.heading_targets) > 0
        assert len(brief.keyword_targets) > 0

        # Verify competitor structure
        comp = brief.competitors[0]
        assert "url" in comp
        assert "pageScore" in comp
        assert "wordCount" in comp

        # Verify heading targets have expected structure
        ht = brief.heading_targets[0]
        assert "tag" in ht
        assert "target" in ht


# ---------------------------------------------------------------------------
# Caching tests
# ---------------------------------------------------------------------------


class TestFetchContentBriefCaching:
    """Tests for caching behavior."""

    @pytest.mark.asyncio
    async def test_returns_cached_brief(
        self, db_session: AsyncSession, crawled_page: CrawledPage
    ) -> None:
        """Existing brief is returned without making API call."""
        # Pre-create a ContentBrief
        existing = ContentBrief(
            page_id=crawled_page.id,
            keyword="cached keyword",
            lsi_terms=[{"phrase": "cached term", "weight": 50}],
            related_searches=["cached search"],
            raw_response={"cached": True},
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        # Should not call POP client at all
        mock_client = POPMockClient()
        mock_client.get_terms = AsyncMock()  # type: ignore[method-assign]

        with patch("app.services.pop_content_brief.get_pop_client", return_value=mock_client):
            result = await fetch_content_brief(
                db=db_session,
                crawled_page=crawled_page,
                keyword="running shoes",
                target_url="https://brief-test.example.com/shoes",
            )

        assert result.success is True
        assert result.cached is True
        assert result.content_brief is not None
        assert result.content_brief.keyword == "cached keyword"
        mock_client.get_terms.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_refresh_bypasses_cache(
        self, db_session: AsyncSession, crawled_page: CrawledPage
    ) -> None:
        """force_refresh=True makes new API call and updates existing brief."""
        # Pre-create a ContentBrief
        existing = ContentBrief(
            page_id=crawled_page.id,
            keyword="old keyword",
            lsi_terms=[],
            related_searches=[],
            raw_response={},
        )
        db_session.add(existing)
        await db_session.commit()

        mock_client = POPMockClient()

        with patch("app.services.pop_content_brief.get_pop_client", return_value=mock_client):
            result = await fetch_content_brief(
                db=db_session,
                crawled_page=crawled_page,
                keyword="new keyword",
                target_url="https://brief-test.example.com/shoes",
                force_refresh=True,
            )

        assert result.success is True
        assert result.cached is False
        assert result.content_brief is not None
        # Brief should be updated with new keyword
        assert result.content_brief.keyword == "new keyword"
        assert len(result.content_brief.lsi_terms) > 0


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestFetchContentBriefErrorHandling:
    """Tests for error handling (returns failure result, does not raise)."""

    @pytest.mark.asyncio
    async def test_pop_timeout_returns_failure(
        self, db_session: AsyncSession, crawled_page: CrawledPage
    ) -> None:
        """POP timeout returns failure result, does not raise."""
        mock_client = AsyncMock()
        mock_client.__class__ = POPMockClient  # isinstance check

        # Make get_terms raise POPTimeoutError
        mock_client.get_terms = AsyncMock(side_effect=POPTimeoutError("Task timed out"))

        with patch("app.services.pop_content_brief.get_pop_client", return_value=mock_client):
            # Override isinstance check
            with patch("app.services.pop_content_brief.isinstance", return_value=True):
                result = await fetch_content_brief(
                    db=db_session,
                    crawled_page=crawled_page,
                    keyword="timeout test",
                    target_url="https://brief-test.example.com/shoes",
                )

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_failure(
        self, db_session: AsyncSession, crawled_page: CrawledPage
    ) -> None:
        """Unexpected exception returns failure result, does not raise."""
        mock_client = AsyncMock()

        # Make the mock raise a generic exception
        mock_client.get_terms = AsyncMock(side_effect=RuntimeError("unexpected"))

        with patch("app.services.pop_content_brief.get_pop_client", return_value=mock_client):
            with patch(
                "app.services.pop_content_brief.isinstance",
                side_effect=lambda obj, cls: cls is POPMockClient,
            ):
                result = await fetch_content_brief(
                    db=db_session,
                    crawled_page=crawled_page,
                    keyword="error test",
                    target_url="https://brief-test.example.com/shoes",
                )

        assert result.success is False
        assert result.error is not None
        assert "unexpected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_pop_task_failure_returns_failure(
        self, db_session: AsyncSession, crawled_page: CrawledPage
    ) -> None:
        """POP task returning failure status returns failure result."""
        mock_client = AsyncMock()
        mock_client.get_terms = AsyncMock(
            return_value=POPTaskResult(
                success=True,
                task_id="fail-task",
                status=POPTaskStatus.FAILURE,
                data={"error": "Bad keyword"},
            )
        )

        with patch("app.services.pop_content_brief.get_pop_client", return_value=mock_client):
            with patch(
                "app.services.pop_content_brief.isinstance",
                side_effect=lambda obj, cls: cls is POPMockClient,
            ):
                result = await fetch_content_brief(
                    db=db_session,
                    crawled_page=crawled_page,
                    keyword="fail test",
                    target_url="https://brief-test.example.com/shoes",
                )

        assert result.success is False
        assert result.error is not None
