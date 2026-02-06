"""Tests for POP content brief service.

Tests cover:
- Mock mode returns fixture data (lsi_terms, related_searches, raw_response)
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
    _parse_lsi_terms,
    _parse_related_searches,
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
# Parse helper tests
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
