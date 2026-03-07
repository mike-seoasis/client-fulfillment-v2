"""Tests for LLM judge service (Tier 2 quality evaluation).

Covers:
- _parse_judge_response: JSON parsing, markdown fences, clamping, edge cases
- build_brief_summary: brief with/without fields
- score_naturalness: mocked OpenAI success, timeout, parse failure
- run_llm_judge_checks: no API key, threshold-based issue generation, cost tracking
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.content_quality import QualityIssue
from app.services.llm_judge import (
    JudgeResult,
    JudgeRunResult,
    _parse_judge_response,
    build_brief_summary,
    run_llm_judge_checks,
    score_naturalness,
    score_heading_structure,
)


# ---------------------------------------------------------------------------
# _parse_judge_response
# ---------------------------------------------------------------------------


class TestParseJudgeResponse:
    """Tests for parsing LLM judge JSON responses."""

    def test_valid_json(self) -> None:
        score, reasoning = _parse_judge_response('{"score": 0.85, "reasoning": "good"}')
        assert score == 0.85
        assert reasoning == "good"

    def test_markdown_fences(self) -> None:
        raw = '```json\n{"score": 0.7, "reasoning": "ok"}\n```'
        score, reasoning = _parse_judge_response(raw)
        assert score == 0.7
        assert reasoning == "ok"

    def test_score_clamped_above_1(self) -> None:
        score, reasoning = _parse_judge_response('{"score": 1.5, "reasoning": "over"}')
        assert score == 1.0

    def test_score_clamped_below_0(self) -> None:
        score, reasoning = _parse_judge_response('{"score": -0.3, "reasoning": "under"}')
        assert score == 0.0

    def test_non_numeric_score(self) -> None:
        score, reasoning = _parse_judge_response('{"score": "high", "reasoning": "oops"}')
        assert score is None
        assert "Failed to parse" in reasoning

    def test_invalid_json(self) -> None:
        score, reasoning = _parse_judge_response("this is not json at all")
        assert score is None
        assert "Failed to parse" in reasoning

    def test_embedded_json_in_text(self) -> None:
        raw = 'Here is my evaluation:\n{"score": 0.65, "reasoning": "decent"}\nEnd.'
        score, reasoning = _parse_judge_response(raw)
        assert score == 0.65
        assert reasoning == "decent"

    def test_empty_response(self) -> None:
        score, reasoning = _parse_judge_response("")
        assert score is None
        assert "Failed to parse" in reasoning

    def test_whitespace_only(self) -> None:
        score, reasoning = _parse_judge_response("   \n\n  ")
        assert score is None
        assert "Failed to parse" in reasoning

    def test_score_exactly_0(self) -> None:
        score, reasoning = _parse_judge_response('{"score": 0.0, "reasoning": "terrible"}')
        assert score == 0.0
        assert reasoning == "terrible"

    def test_score_exactly_1(self) -> None:
        score, reasoning = _parse_judge_response('{"score": 1.0, "reasoning": "perfect"}')
        assert score == 1.0
        assert reasoning == "perfect"

    def test_markdown_fences_no_language_tag(self) -> None:
        raw = '```\n{"score": 0.5, "reasoning": "mid"}\n```'
        score, reasoning = _parse_judge_response(raw)
        assert score == 0.5
        assert reasoning == "mid"


# ---------------------------------------------------------------------------
# build_brief_summary
# ---------------------------------------------------------------------------


class TestBuildBriefSummary:
    """Tests for building brief summary text for the judge."""

    def test_full_brief(self) -> None:
        brief = MagicMock()
        brief.lsi_terms = ["term1", "term2", "term3"]
        brief.word_count_min = 800
        brief.word_count_max = 1200
        brief.heading_structure = None

        result = build_brief_summary(brief, primary_keyword="best shoes")
        assert "Primary keyword: best shoes" in result
        assert "LSI terms: term1, term2, term3" in result
        assert "Target word count: 800-1200" in result

    def test_no_brief(self) -> None:
        result = build_brief_summary(None)
        assert result == "No content brief available."

    def test_keyword_only(self) -> None:
        result = build_brief_summary(None, primary_keyword="test keyword")
        assert result == "Primary keyword: test keyword"

    def test_brief_with_heading_structure(self) -> None:
        brief = MagicMock()
        brief.lsi_terms = []
        brief.word_count_min = None
        brief.word_count_max = None
        brief.heading_structure = [{"h2": "Section 1"}, {"h2": "Section 2"}]

        result = build_brief_summary(brief, primary_keyword="kw")
        assert "Primary keyword: kw" in result
        assert "Heading structure:" in result

    def test_no_brief_no_keyword(self) -> None:
        result = build_brief_summary(None, primary_keyword="")
        assert result == "No content brief available."


# ---------------------------------------------------------------------------
# score_naturalness (async, mocked OpenAI)
# ---------------------------------------------------------------------------


class TestScoreNaturalness:
    """Tests for the naturalness scoring function with mocked OpenAI."""

    async def test_successful_scoring(self, mocker: Any) -> None:
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"score": 0.85, "reasoning": "natural"}'))
        ]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=20)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        # Mock settings to avoid threshold lookup issues
        mock_settings = MagicMock()
        mock_settings.quality_naturalness_threshold = 0.6
        mocker.patch("app.services.llm_judge.get_settings", return_value=mock_settings)

        result = await score_naturalness(mock_client, "some content", "gpt-4.1", 30)

        assert isinstance(result, JudgeResult)
        assert result.dimension == "naturalness"
        assert result.score == 0.85
        assert result.reasoning == "natural"
        assert result.error is None
        assert result.issues == []
        assert result.cost_usd > 0  # cost should be tracked

    async def test_timeout_error(self, mocker: Any) -> None:
        import asyncio

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=asyncio.TimeoutError("timed out")
        )

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.quality_naturalness_threshold = 0.6
        mocker.patch("app.services.llm_judge.get_settings", return_value=mock_settings)

        result = await score_naturalness(mock_client, "some content", "gpt-4.1", 30)

        assert isinstance(result, JudgeResult)
        assert result.dimension == "naturalness"
        assert result.score == 0.0
        assert result.error is not None
        assert result.issues == []  # errors should NOT generate threshold issues

    async def test_low_score_generates_issue(self, mocker: Any) -> None:
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"score": 0.3, "reasoning": "robotic"}'))
        ]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=20)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_settings = MagicMock()
        mock_settings.quality_naturalness_threshold = 0.6
        mocker.patch("app.services.llm_judge.get_settings", return_value=mock_settings)

        result = await score_naturalness(mock_client, "some content", "gpt-4.1", 30)

        assert result.score == 0.3
        assert len(result.issues) == 1
        assert result.issues[0].type == "llm_naturalness"

    async def test_parse_failure_returns_error_not_issue(self, mocker: Any) -> None:
        """Parse failure should set error, not generate a threshold issue."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="this is not json"))
        ]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=20)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_settings = MagicMock()
        mock_settings.quality_naturalness_threshold = 0.6
        mocker.patch("app.services.llm_judge.get_settings", return_value=mock_settings)

        result = await score_naturalness(mock_client, "some content", "gpt-4.1", 30)

        assert result.score == 0.0
        assert result.error is not None
        assert "Failed to parse" in result.error
        assert result.issues == []  # no spurious threshold issue


# ---------------------------------------------------------------------------
# score_heading_structure (async, mocked OpenAI)
# ---------------------------------------------------------------------------


class TestScoreHeadingStructure:
    """Tests for heading structure scoring — verifies issue generation."""

    async def test_low_score_generates_issue(self, mocker: Any) -> None:
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"score": 0.3, "reasoning": "poor headings"}'))
        ]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=20)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_settings = MagicMock()
        mock_settings.quality_heading_structure_threshold = 0.6
        mocker.patch("app.services.llm_judge.get_settings", return_value=mock_settings)

        result = await score_heading_structure(mock_client, "content", "brief", "gpt-4.1", 30)

        assert result.score == 0.3
        assert len(result.issues) == 1
        assert result.issues[0].type == "llm_heading_structure"

    async def test_high_score_no_issue(self, mocker: Any) -> None:
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"score": 0.9, "reasoning": "great structure"}'))
        ]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=20)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_settings = MagicMock()
        mock_settings.quality_heading_structure_threshold = 0.6
        mocker.patch("app.services.llm_judge.get_settings", return_value=mock_settings)

        result = await score_heading_structure(mock_client, "content", "brief", "gpt-4.1", 30)

        assert result.score == 0.9
        assert result.issues == []
        assert result.error is None


# ---------------------------------------------------------------------------
# run_llm_judge_checks
# ---------------------------------------------------------------------------


class TestRunLlmJudgeChecks:
    """Tests for the main entry point that runs all 3 judge evaluations."""

    async def test_no_api_key(self, mocker: Any) -> None:
        mock_settings = MagicMock()
        mock_settings.openai_api_key = None
        mocker.patch("app.services.llm_judge.get_settings", return_value=mock_settings)

        result = await run_llm_judge_checks("some content")

        assert isinstance(result, JudgeRunResult)
        assert result.error == "No OpenAI API key configured"
        assert result.naturalness == 0.0

    async def test_scores_below_thresholds(self, mocker: Any) -> None:
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "sk-test-key"
        mock_settings.quality_judge_model = "gpt-4.1"
        mock_settings.quality_tier2_timeout = 30
        mock_settings.quality_naturalness_threshold = 0.6
        mock_settings.quality_brief_adherence_threshold = 0.7
        mock_settings.quality_heading_structure_threshold = 0.6
        mocker.patch("app.services.llm_judge.get_settings", return_value=mock_settings)

        # Mock OpenAI client creation
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"score": 0.3, "reasoning": "low"}'))
        ]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=20)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_openai_module = MagicMock()
        mock_openai_module.AsyncOpenAI.return_value = mock_client
        mocker.patch.dict("sys.modules", {"openai": mock_openai_module})

        result = await run_llm_judge_checks("some content")

        assert result.naturalness == 0.3
        assert result.brief_adherence == 0.3
        assert result.heading_structure == 0.3
        # All three below thresholds -> 3 issues
        issue_types = [i.type for i in result.issues]
        assert "llm_naturalness" in issue_types
        assert "llm_brief_adherence" in issue_types
        assert "llm_heading_structure" in issue_types
        # Cost should be tracked
        assert result.cost_usd > 0

    async def test_scores_above_thresholds(self, mocker: Any) -> None:
        mock_settings = MagicMock()
        mock_settings.openai_api_key = "sk-test-key"
        mock_settings.quality_judge_model = "gpt-4.1"
        mock_settings.quality_tier2_timeout = 30
        mock_settings.quality_naturalness_threshold = 0.6
        mock_settings.quality_brief_adherence_threshold = 0.7
        mock_settings.quality_heading_structure_threshold = 0.6
        mocker.patch("app.services.llm_judge.get_settings", return_value=mock_settings)

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"score": 0.9, "reasoning": "great"}'))
        ]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=20)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        mock_openai_module = MagicMock()
        mock_openai_module.AsyncOpenAI.return_value = mock_client
        mocker.patch.dict("sys.modules", {"openai": mock_openai_module})

        result = await run_llm_judge_checks("some content")

        assert result.naturalness == 0.9
        assert result.brief_adherence == 0.9
        assert result.heading_structure == 0.9
        assert result.issues == []
        assert result.error is None
        assert result.cost_usd > 0
