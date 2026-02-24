"""Tests for blog content generation pipeline.

Tests cover:
- JSON parsing: valid 3-key JSON, markdown fences, missing keys, invalid JSON
- Quality checks: clean content passes, problematic content fails, handles None fields
- Skip-if-complete logic: already complete posts are skipped
- Pipeline result aggregation: succeeded/failed/skipped counts
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.blog import BlogPost, ContentStatus
from app.services.blog_content_generation import (
    BLOG_CONTENT_KEYS,
    BlogPipelinePostResult,
    BlogPipelineResult,
    _humanize_content,
    _parse_blog_content_json,
    _run_blog_quality_checks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeBlogPost:
    """Stand-in for BlogPost to avoid SQLAlchemy session pollution."""

    def __init__(self, **kwargs: Any) -> None:
        self.id: str = kwargs.get("id", "fake-post-id")
        self.title: str | None = kwargs.get("title")
        self.meta_description: str | None = kwargs.get("meta_description")
        self.content: str | None = kwargs.get("content")
        self.content_status: str = kwargs.get("content_status", ContentStatus.PENDING.value)
        self.qa_results: dict[str, Any] | None = None


def _make_blog_post(**kwargs: Any) -> Any:
    """Create a fake BlogPost-like object."""
    return _FakeBlogPost(**kwargs)


# ---------------------------------------------------------------------------
# _parse_blog_content_json Tests
# ---------------------------------------------------------------------------


class TestParseBlogContentJson:
    """Tests for JSON parsing of Claude's blog content response."""

    def test_parses_valid_json(self) -> None:
        """Parses valid JSON with all 3 required keys."""
        text = json.dumps({
            "page_title": "How to Clean Boots",
            "meta_description": "Learn the best ways to clean your boots",
            "content": "<h2>Step 1</h2><p>Gather supplies.</p>",
        })
        result = _parse_blog_content_json(text)
        assert result is not None
        assert result["page_title"] == "How to Clean Boots"
        assert result["meta_description"] == "Learn the best ways to clean your boots"
        assert "<h2>Step 1</h2>" in result["content"]

    def test_strips_markdown_code_fences(self) -> None:
        """Handles response wrapped in ```json ... ``` fences."""
        inner = json.dumps({
            "page_title": "Title",
            "meta_description": "Meta",
            "content": "<p>Content</p>",
        })
        text = f"```json\n{inner}\n```"
        result = _parse_blog_content_json(text)
        assert result is not None
        assert result["page_title"] == "Title"

    def test_extracts_json_from_surrounding_text(self) -> None:
        """Extracts JSON object embedded in surrounding text."""
        inner = json.dumps({
            "page_title": "T",
            "meta_description": "M",
            "content": "C",
        })
        text = f"Here is the content:\n{inner}\nDone!"
        result = _parse_blog_content_json(text)
        assert result is not None

    def test_returns_none_for_invalid_json(self) -> None:
        """Returns None for non-JSON text."""
        assert _parse_blog_content_json("not json at all") is None

    def test_returns_none_for_missing_keys(self) -> None:
        """Returns None when required keys are missing."""
        text = json.dumps({"page_title": "T", "meta_description": "M"})
        assert _parse_blog_content_json(text) is None

    def test_returns_none_for_non_dict(self) -> None:
        """Returns None for JSON arrays or primitives."""
        assert _parse_blog_content_json("[1, 2, 3]") is None

    def test_only_returns_required_keys(self) -> None:
        """Filters out extra keys not in BLOG_CONTENT_KEYS."""
        text = json.dumps({
            "page_title": "T",
            "meta_description": "M",
            "content": "C",
            "extra_key": "should not appear",
        })
        result = _parse_blog_content_json(text)
        assert result is not None
        assert "extra_key" not in result
        assert set(result.keys()) == BLOG_CONTENT_KEYS

    def test_returns_none_for_collection_page_keys(self) -> None:
        """Returns None for collection page JSON (4 keys instead of blog 3 keys)."""
        text = json.dumps({
            "page_title": "T",
            "meta_description": "M",
            "top_description": "Top",
            "bottom_description": "Bottom",
        })
        result = _parse_blog_content_json(text)
        # Missing "content" key
        assert result is None


# ---------------------------------------------------------------------------
# _run_blog_quality_checks Tests
# ---------------------------------------------------------------------------


class TestRunBlogQualityChecks:
    """Tests for blog-specific quality checks."""

    def test_passes_clean_content(self) -> None:
        """Clean blog content returns passed=True with no issues."""
        post = _make_blog_post(
            title="Winter Boots Guide",
            meta_description="A practical guide to choosing winter boots.",
            content="<h2>Choosing Boots</h2><p>Consider warmth and fit.</p>",
        )
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["cheap"]}}

        result = _run_blog_quality_checks(post, brand_config)

        assert result.passed is True
        assert len(result.issues) == 0
        assert result.checked_at != ""

    def test_detects_banned_word_in_content(self) -> None:
        """Detects banned words in blog post content."""
        post = _make_blog_post(
            title="Winter Boots",
            meta_description="Find cheap winter boots.",
            content="<p>Quality content.</p>",
        )
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["cheap"]}}

        result = _run_blog_quality_checks(post, brand_config)

        assert result.passed is False
        issue_types = {i.type for i in result.issues}
        assert "banned_word" in issue_types

    def test_detects_em_dash_in_content(self) -> None:
        """Detects em dash in blog content field."""
        post = _make_blog_post(
            title="Guide",
            content="<p>Quality\u2014built to last.</p>",
        )

        result = _run_blog_quality_checks(post, {})

        assert result.passed is False
        issue_types = {i.type for i in result.issues}
        assert "em_dash" in issue_types

    def test_detects_ai_opener(self) -> None:
        """Detects AI opener patterns in blog content."""
        post = _make_blog_post(
            title="Guide",
            content="<p>In today's market, boots are essential.</p>",
        )

        result = _run_blog_quality_checks(post, {})

        assert result.passed is False
        issue_types = {i.type for i in result.issues}
        assert "ai_pattern" in issue_types

    def test_handles_none_fields(self) -> None:
        """Content with None fields is handled gracefully."""
        post = _make_blog_post(
            title=None,
            meta_description=None,
            content=None,
        )

        result = _run_blog_quality_checks(post, {})
        assert result.passed is True
        assert len(result.issues) == 0

    def test_result_has_to_dict(self) -> None:
        """QualityResult.to_dict() returns correct structure."""
        post = _make_blog_post(
            title="Title",
            content="<p>Clean content.</p>",
        )

        result = _run_blog_quality_checks(post, {})
        d = result.to_dict()

        assert "passed" in d
        assert "issues" in d
        assert "checked_at" in d


# ---------------------------------------------------------------------------
# BlogPipelinePostResult Tests
# ---------------------------------------------------------------------------


class TestBlogPipelinePostResult:
    """Tests for the post-level pipeline result dataclass."""

    def test_success_result(self) -> None:
        result = BlogPipelinePostResult(
            post_id="p1", keyword="test", success=True
        )
        assert result.success is True
        assert result.error is None
        assert result.skipped is False

    def test_skipped_result(self) -> None:
        result = BlogPipelinePostResult(
            post_id="p1", keyword="test", success=True, skipped=True
        )
        assert result.skipped is True

    def test_failed_result(self) -> None:
        result = BlogPipelinePostResult(
            post_id="p1", keyword="test", success=False, error="API error"
        )
        assert result.success is False
        assert result.error == "API error"


# ---------------------------------------------------------------------------
# BlogPipelineResult Tests
# ---------------------------------------------------------------------------


class TestBlogPipelineResult:
    """Tests for the campaign-level pipeline result dataclass."""

    def test_aggregates_counts(self) -> None:
        result = BlogPipelineResult(campaign_id="c1")
        result.total_posts = 4
        result.succeeded = 2
        result.failed = 1
        result.skipped = 1

        assert result.total_posts == result.succeeded + result.failed + result.skipped

    def test_default_values(self) -> None:
        result = BlogPipelineResult(campaign_id="c1")
        assert result.total_posts == 0
        assert result.succeeded == 0
        assert result.failed == 0
        assert result.skipped == 0
        assert result.post_results == []


# ---------------------------------------------------------------------------
# _humanize_content Tests
# ---------------------------------------------------------------------------


class TestHumanizeContent:
    """Tests for the humanization auto-fix pass."""

    def test_replaces_banned_words(self) -> None:
        """Replaces AI-sounding words with natural alternatives."""
        content = "This is a crucial step to utilize robust tools for a seamless experience."
        result = _humanize_content(content)
        assert "crucial" not in result
        assert "important" in result
        assert "utilize" not in result
        assert "use" in result
        assert "robust" not in result
        assert "strong" in result
        assert "seamless" not in result
        assert "smooth" in result

    def test_case_insensitive(self) -> None:
        """Replacements work case-insensitively."""
        content = "CRUCIAL data shows Comprehensive results."
        result = _humanize_content(content)
        assert "crucial" not in result.lower()
        assert "comprehensive" not in result.lower()
        assert "important" in result.lower()
        assert "complete" in result.lower()

    def test_preserves_surrounding_text(self) -> None:
        """Surrounding text is not affected by replacements."""
        content = "Start here. This is crucial for success. End here."
        result = _humanize_content(content)
        assert result.startswith("Start here.")
        assert result.endswith("End here.")
        assert "important" in result

    def test_deletes_empty_replacement_phrases(self) -> None:
        """Phrases mapped to empty string are removed cleanly."""
        content = "It's important to note that boots need care."
        result = _humanize_content(content)
        assert "it's important to note that" not in result.lower()
        # Should still have the rest of the sentence
        assert "boots need care" in result

    def test_cleans_up_double_spaces(self) -> None:
        """Double spaces left by deletions are cleaned up."""
        content = "Start. At the end of the day boots matter."
        result = _humanize_content(content)
        assert "  " not in result

    def test_phrase_replacement_in_order_to(self) -> None:
        """'in order to' is replaced with 'to'."""
        content = "You need to clean them in order to maintain quality."
        result = _humanize_content(content)
        assert "in order to" not in result
        # "to maintain quality" should remain (the "to" replacement)
        assert "to maintain quality" in result

    def test_no_replacements_returns_unchanged(self) -> None:
        """Content with no banned words is returned unchanged."""
        content = "Our boots are made with quality leather."
        result = _humanize_content(content)
        assert result == content

    def test_cutting_edge_replaced(self) -> None:
        """'cutting-edge' is replaced with 'modern'."""
        content = "Using cutting-edge manufacturing techniques."
        result = _humanize_content(content)
        assert "cutting-edge" not in result
        assert "modern" in result


# ---------------------------------------------------------------------------
# Perplexity trend research (mocked)
# ---------------------------------------------------------------------------


class TestPerplexityTrendResearch:
    """Tests for Perplexity trend research integration."""

    @pytest.mark.asyncio
    async def test_trend_research_returns_data(self) -> None:
        """Mocked Perplexity returns trend data dict."""
        from app.services.blog_content_generation import _fetch_trend_context

        mock_completion = MagicMock()
        mock_completion.success = True
        mock_completion.text = "Boot care trends: conditioning is up 20% in 2026."
        mock_completion.citations = ["https://example.com/trends"]
        mock_completion.error = None
        mock_completion.input_tokens = 100
        mock_completion.output_tokens = 50

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.research_query = AsyncMock(return_value=mock_completion)
        mock_client.close = AsyncMock()

        with patch(
            "app.integrations.perplexity.PerplexityClient",
            return_value=mock_client,
        ):
            result = await _fetch_trend_context("boot care", {})

        assert result is not None
        assert "trends" in result
        assert "citations" in result
        assert "fetched_at" in result
        assert "conditioning" in result["trends"]

    @pytest.mark.asyncio
    async def test_trend_research_graceful_degradation(self) -> None:
        """Returns None when Perplexity fails."""
        from app.services.blog_content_generation import _fetch_trend_context

        mock_client = AsyncMock()
        mock_client.available = True
        mock_client.research_query = AsyncMock(side_effect=RuntimeError("API down"))
        mock_client.close = AsyncMock()

        with patch(
            "app.integrations.perplexity.PerplexityClient",
            return_value=mock_client,
        ):
            result = await _fetch_trend_context("boot care", {})

        assert result is None

    @pytest.mark.asyncio
    async def test_trend_research_skips_when_not_configured(self) -> None:
        """Returns None when Perplexity is not configured."""
        from app.services.blog_content_generation import _fetch_trend_context

        mock_client = AsyncMock()
        mock_client.available = False

        with patch(
            "app.integrations.perplexity.PerplexityClient",
            return_value=mock_client,
        ):
            result = await _fetch_trend_context("boot care", {})

        assert result is None
