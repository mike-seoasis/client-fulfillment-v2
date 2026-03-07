"""Tests for quality fixer module.

Covers:
- filter_fixable_issues: filtering to FIXABLE_ISSUE_TYPES
- group_issues_by_field: grouping issues by field name
- _build_fix_prompt: prompt construction
- _parse_fix_response: JSON parsing with edge cases
- Bible issue types: all bible types are fixable
- fix_content: async fix flow with mocked Claude
- Blog content fixes: field-specific fixes for blog posts
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.claude import CompletionResult
from app.services.quality_fixer import (
    FIXABLE_ISSUE_TYPES,
    FixResult,
    _build_fix_prompt,
    _parse_fix_response,
    filter_fixable_issues,
    fix_content,
    group_issues_by_field,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _issue(
    type: str,
    field: str = "content",
    description: str = "",
    context: str = "",
) -> dict[str, Any]:
    """Create a minimal issue dict for testing."""
    return {
        "type": type,
        "field": field,
        "description": description or f"test {type}",
        "context": context,
    }


def _valid_fix_response(
    content: str = "<p>Fixed content</p>",
    changes: list[str] | None = None,
) -> str:
    """Build a valid JSON fix response string."""
    return json.dumps({
        "fixed_content": content,
        "changes_made": changes or ["Replaced word X with Y"],
    })


# ---------------------------------------------------------------------------
# TestFilterFixableIssues
# ---------------------------------------------------------------------------


class TestFilterFixableIssues:
    """Tests for filter_fixable_issues()."""

    def test_filters_to_fixable_types(self) -> None:
        issues = [
            _issue("banned_word"),
            _issue("llm_naturalness"),
            _issue("em_dash"),
            _issue("rhetorical_excess"),
        ]
        result = filter_fixable_issues(issues)
        types = {i["type"] for i in result}
        assert types == {"banned_word", "em_dash"}
        assert len(result) == 2

    def test_empty_issues_returns_empty(self) -> None:
        assert filter_fixable_issues([]) == []

    def test_all_non_fixable_returns_empty(self) -> None:
        issues = [
            _issue("llm_naturalness"),
            _issue("rhetorical_excess"),
            _issue("missing_direct_answer"),
        ]
        assert filter_fixable_issues(issues) == []


# ---------------------------------------------------------------------------
# TestGroupIssuesByField
# ---------------------------------------------------------------------------


class TestGroupIssuesByField:
    """Tests for group_issues_by_field()."""

    def test_groups_by_field_name(self) -> None:
        issues = [
            _issue("banned_word", field="title"),
            _issue("em_dash", field="content"),
            _issue("ai_pattern", field="title"),
        ]
        grouped = group_issues_by_field(issues)
        assert set(grouped.keys()) == {"title", "content"}
        assert len(grouped["title"]) == 2
        assert len(grouped["content"]) == 1

    def test_empty_returns_empty(self) -> None:
        assert group_issues_by_field([]) == {}


# ---------------------------------------------------------------------------
# TestBuildFixPrompt
# ---------------------------------------------------------------------------


class TestBuildFixPrompt:
    """Tests for _build_fix_prompt()."""

    def test_prompt_includes_field_content(self) -> None:
        prompt = _build_fix_prompt(
            field_name="top_description",
            field_content="<p>Hello world</p>",
            issues=[_issue("banned_word", description="Found banned word 'synergy'")],
        )
        assert "top_description" in prompt
        assert "<p>Hello world</p>" in prompt
        assert "Found banned word 'synergy'" in prompt

    def test_multiple_issues_numbered(self) -> None:
        issues = [
            _issue("banned_word", description="Issue A"),
            _issue("em_dash", description="Issue B"),
            _issue("ai_pattern", description="Issue C"),
        ]
        prompt = _build_fix_prompt("content", "<p>text</p>", issues)
        assert "1. " in prompt
        assert "2. " in prompt
        assert "3. " in prompt


# ---------------------------------------------------------------------------
# TestParseFixResponse
# ---------------------------------------------------------------------------


class TestParseFixResponse:
    """Tests for _parse_fix_response()."""

    def test_parses_valid_json(self) -> None:
        response = _valid_fix_response("<p>Fixed</p>", ["Changed X to Y"])
        content, changes = _parse_fix_response(response)
        assert content == "<p>Fixed</p>"
        assert changes == ["Changed X to Y"]

    def test_handles_markdown_fences(self) -> None:
        inner = _valid_fix_response("<p>Fenced</p>", ["Removed em dash"])
        response = f"```json\n{inner}\n```"
        content, changes = _parse_fix_response(response)
        assert content == "<p>Fenced</p>"
        assert changes == ["Removed em dash"]

    def test_returns_none_on_invalid_json(self) -> None:
        content, changes = _parse_fix_response("this is not json at all")
        assert content is None
        assert changes == []

    def test_handles_missing_changes_made(self) -> None:
        response = json.dumps({"fixed_content": "<p>OK</p>"})
        content, changes = _parse_fix_response(response)
        assert content == "<p>OK</p>"
        assert changes == []

    def test_non_string_fixed_content_returns_none(self) -> None:
        """Non-string fixed_content (int, dict, bool) should be treated as None."""
        for bad_value in [42, {"nested": "object"}, True, []]:
            response = json.dumps({"fixed_content": bad_value, "changes_made": ["test"]})
            content, changes = _parse_fix_response(response)
            assert content is None, f"Expected None for fixed_content={bad_value!r}"

    def test_null_fixed_content_returns_none(self) -> None:
        response = json.dumps({"fixed_content": None})
        content, changes = _parse_fix_response(response)
        assert content is None


# ---------------------------------------------------------------------------
# TestBibleIssuesFixable
# ---------------------------------------------------------------------------


class TestBibleIssuesFixable:
    """Verify all bible issue types are in FIXABLE_ISSUE_TYPES."""

    def test_all_bible_types_fixable(self) -> None:
        bible_types = {
            "bible_preferred_term",
            "bible_banned_claim",
            "bible_wrong_attribution",
            "bible_term_context",
        }
        assert bible_types.issubset(FIXABLE_ISSUE_TYPES)


# ---------------------------------------------------------------------------
# TestFixContent
# ---------------------------------------------------------------------------


class TestFixContent:
    """Tests for fix_content() with mocked Claude client."""

    async def test_successful_fix(self, mocker: Any) -> None:
        original = "<p>This content has a synergy moment and delves deep.</p>"
        fixed = "<p>This content has a collaborative moment and explores deep.</p>"
        response_json = _valid_fix_response(fixed, ["Replaced synergy", "Replaced delves"])

        mock_client = AsyncMock()
        mock_client.complete.return_value = CompletionResult(
            success=True,
            text=response_json,
            input_tokens=500,
            output_tokens=200,
        )

        result = await fix_content(
            fields={"content": original},
            issues=[_issue("banned_word", field="content", description="Found 'synergy'")],
            claude_client=mock_client,
        )

        assert result.success is True
        assert "content" in result.fixed_fields
        assert result.fixed_fields["content"] == fixed
        assert len(result.changes_made) == 2
        assert result.issues_sent == 1
        assert result.cost_usd > 0

    async def test_no_fixable_issues_returns_early(self, mocker: Any) -> None:
        result = await fix_content(
            fields={"content": "<p>Some text</p>"},
            issues=[_issue("llm_naturalness"), _issue("rhetorical_excess")],
        )

        assert result.success is True
        assert result.fixed_fields == {}
        assert result.issues_sent == 0

    async def test_claude_failure_returns_error(self, mocker: Any) -> None:
        mock_client = AsyncMock()
        mock_client.complete.return_value = CompletionResult(
            success=False,
            error="API rate limit exceeded",
        )

        result = await fix_content(
            fields={"content": "<p>Some text</p>"},
            issues=[_issue("banned_word", field="content")],
            claude_client=mock_client,
        )

        assert result.success is False
        assert "content" in result.error

    async def test_suspiciously_short_response_rejected(self, mocker: Any) -> None:
        original = "<p>This is a fairly long piece of content that should not be shortened dramatically by the fixer.</p>"
        short_fixed = "<p>Short.</p>"
        response_json = _valid_fix_response(short_fixed, ["Trimmed"])

        mock_client = AsyncMock()
        mock_client.complete.return_value = CompletionResult(
            success=True,
            text=response_json,
            input_tokens=500,
            output_tokens=50,
        )

        result = await fix_content(
            fields={"content": original},
            issues=[_issue("banned_word", field="content")],
            claude_client=mock_client,
        )

        assert result.success is False
        assert "suspiciously short" in result.error

    async def test_partial_field_fix(self, mocker: Any) -> None:
        """Two fields with issues: one fix succeeds, the other fails to parse."""
        good_response = _valid_fix_response(
            "<p>Fixed title content here for length</p>",
            ["Fixed title"],
        )
        bad_response = "NOT VALID JSON"

        mock_client = AsyncMock()
        mock_client.complete.side_effect = [
            CompletionResult(success=True, text=good_response, input_tokens=100, output_tokens=50),
            CompletionResult(success=True, text=bad_response, input_tokens=100, output_tokens=50),
        ]

        result = await fix_content(
            fields={
                "title": "<p>Title with issues needs fixing</p>",
                "content": "<p>Content with issues needs fixing</p>",
            },
            issues=[
                _issue("banned_word", field="title"),
                _issue("em_dash", field="content"),
            ],
            claude_client=mock_client,
        )

        # One field fixed, one failed — overall marked as failed
        assert result.success is False
        assert "title" in result.fixed_fields
        assert "content" not in result.fixed_fields

    async def test_no_api_key_returns_error(self, mocker: Any) -> None:
        mocker.patch("app.services.quality_fixer.get_api_key", return_value=None)

        result = await fix_content(
            fields={"content": "<p>Text</p>"},
            issues=[_issue("banned_word", field="content")],
            claude_client=None,
        )

        assert result.success is False
        assert "API key" in result.error


# ---------------------------------------------------------------------------
# TestBlogContentFix
# ---------------------------------------------------------------------------


class TestBlogContentFix:
    """Tests for fixing blog-specific fields."""

    async def test_fixes_blog_content_field(self, mocker: Any) -> None:
        original = "<p>In today's fast-paced world, we delve into the synergies of modern business.</p>"
        fixed = "<p>In the modern landscape, we explore the connections of current business.</p>"
        response_json = _valid_fix_response(fixed, ["Removed banned phrases"])

        mock_client = AsyncMock()
        mock_client.complete.return_value = CompletionResult(
            success=True,
            text=response_json,
            input_tokens=400,
            output_tokens=150,
        )

        result = await fix_content(
            fields={"content": original},
            issues=[
                _issue("tier3_banned_phrase", field="content", description="'fast-paced world'"),
                _issue("tier1_ai_word", field="content", description="'delve'"),
            ],
            claude_client=mock_client,
        )

        assert result.success is True
        assert result.fixed_fields["content"] == fixed
        assert result.issues_sent == 2

    async def test_fixes_blog_title_field(self, mocker: Any) -> None:
        original = "Unlocking the Secrets — A Comprehensive Guide"
        fixed = "Understanding the Basics: A Practical Guide"
        response_json = _valid_fix_response(fixed, ["Replaced AI pattern", "Removed em dash"])

        mock_client = AsyncMock()
        mock_client.complete.return_value = CompletionResult(
            success=True,
            text=response_json,
            input_tokens=200,
            output_tokens=100,
        )

        result = await fix_content(
            fields={"title": original},
            issues=[
                _issue("ai_pattern", field="title", description="'Unlocking the Secrets'"),
                _issue("em_dash", field="title", description="Em dash found"),
            ],
            claude_client=mock_client,
        )

        assert result.success is True
        assert result.fixed_fields["title"] == fixed
        assert len(result.changes_made) == 2
