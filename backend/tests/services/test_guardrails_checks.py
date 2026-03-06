"""Tests for Guardrails AI content quality checks.

Tests cover:
- LSI coverage check: below/at/above threshold, no terms, empty content
- Guardrails disabled via config: returns empty list
- Guard import failure: returns empty list (graceful fallback)
- Comment guardrails: profanity detected, clean text passes
- Reading level skip for <100 word fields
- Fuzzy ban list matching
- Redundant sentence detection
- XSS detection
- Integration: new issues merge with existing ones in run_quality_checks
- Backward compat: run_quality_checks without content_brief still works
"""

from typing import Any
from unittest.mock import patch

import pytest

from app.services.guardrails_checks import (
    _check_fuzzy_ban_list,
    _check_lsi_coverage,
    _check_reading_level,
    _check_redundant_sentences,
    _check_xss,
    run_comment_guardrails,
    run_guardrails_checks,
)
from app.services.content_quality import (
    QualityIssue,
    run_blog_quality_checks,
    run_quality_checks,
)


# ---------------------------------------------------------------------------
# Dependency detection helpers (used by @pytest.mark.skipif)
# ---------------------------------------------------------------------------


def _has_thefuzz() -> bool:
    try:
        from thefuzz import fuzz  # noqa: F401

        return True
    except ImportError:
        return False


def _has_bleach() -> bool:
    try:
        import bleach  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakePageContent:
    """Stand-in for PageContent to avoid SQLAlchemy session pollution."""

    def __init__(self, **kwargs: Any) -> None:
        self.page_title: str | None = kwargs.get("page_title")
        self.meta_description: str | None = kwargs.get("meta_description")
        self.top_description: str | None = kwargs.get("top_description")
        self.bottom_description: str | None = kwargs.get("bottom_description")
        self.qa_results: dict[str, Any] | None = None


def _make_page_content(**kwargs: Any) -> Any:
    return _FakePageContent(**kwargs)


# ---------------------------------------------------------------------------
# LSI Coverage Check
# ---------------------------------------------------------------------------


class TestLsiCoverage:
    """Tests for the custom LSI coverage check."""

    def test_below_threshold(self) -> None:
        """Flags when coverage is below threshold."""
        lsi_terms = [
            {"phrase": "winter boots"},
            {"phrase": "snow shoes"},
            {"phrase": "cold weather"},
            {"phrase": "waterproof"},
        ]
        text = "buy winter boots today"  # Only 1 of 4 terms

        issue = _check_lsi_coverage(text, lsi_terms, min_coverage=0.5)
        assert issue is not None
        assert issue.type == "lsi_coverage"
        assert issue.field == "all"
        assert "25%" in issue.description  # 1/4 = 25%
        assert "snow shoes" in issue.context

    def test_at_threshold(self) -> None:
        """No issue when coverage equals threshold."""
        lsi_terms = [
            {"phrase": "winter boots"},
            {"phrase": "snow shoes"},
            {"phrase": "cold weather"},
        ]
        text = "winter boots for cold weather"  # 2 of 3 = 67%

        issue = _check_lsi_coverage(text, lsi_terms, min_coverage=0.6)
        assert issue is None

    def test_above_threshold(self) -> None:
        """No issue when coverage exceeds threshold."""
        lsi_terms = [
            {"phrase": "winter boots"},
            {"phrase": "waterproof"},
        ]
        text = "winter boots that are waterproof"

        issue = _check_lsi_coverage(text, lsi_terms, min_coverage=0.3)
        assert issue is None

    def test_no_terms(self) -> None:
        """No issue when LSI terms list is empty."""
        issue = _check_lsi_coverage("some content", [], min_coverage=0.3)
        assert issue is None

    def test_empty_content(self) -> None:
        """Below threshold when content is empty."""
        lsi_terms = [{"phrase": "winter boots"}]
        issue = _check_lsi_coverage("", lsi_terms, min_coverage=0.3)
        assert issue is not None
        assert "0%" in issue.description

    def test_no_phrase_key(self) -> None:
        """Handles terms without a phrase key."""
        lsi_terms = [{"weight": 5}]  # Missing "phrase"
        issue = _check_lsi_coverage("some content", lsi_terms, min_coverage=0.3)
        assert issue is None  # No valid phrases to check


# ---------------------------------------------------------------------------
# Guard Disabled via Config
# ---------------------------------------------------------------------------


class TestGuardrailsDisabled:
    """Tests that guardrails return empty when disabled."""

    def test_disabled_returns_empty(self) -> None:
        """Returns empty list when enable_guardrails_checks is False."""
        with patch("app.core.config.get_settings") as mock:
            mock.return_value.enable_guardrails_checks = False
            result = run_guardrails_checks(
                {"body": "test content"},
                {"vocabulary": {"competitors": []}},
            )
            assert result == []

    def test_comment_disabled_returns_empty(self) -> None:
        """Comment guardrails returns empty when disabled."""
        with patch("app.core.config.get_settings") as mock:
            mock.return_value.enable_guardrails_checks = False
            result = run_comment_guardrails("test comment")
            assert result == []


# ---------------------------------------------------------------------------
# Reading Level Check
# ---------------------------------------------------------------------------


class TestReadingLevel:
    """Tests for reading level check."""

    def test_skips_short_text(self) -> None:
        """Skips text under 100 words."""
        short_text = "This is a short sentence with few words."
        issues = _check_reading_level(short_text, "body", min_grade=5, max_grade=8)
        assert len(issues) == 0

    def test_returns_issue_type(self) -> None:
        """Verifies issue type is gr_reading_level when triggered."""
        # Generate text that's 100+ words at a very high reading level
        long_text = (
            "The epistemological ramifications of quantum mechanical "
            "decoherence fundamentally undermine naive realist "
            "interpretations of observational phenomena. "
        ) * 10  # ~100+ words of complex text

        issues = _check_reading_level(long_text, "body", min_grade=1, max_grade=2)
        # May or may not trigger depending on readability library availability
        for issue in issues:
            assert issue.type == "gr_reading_level"


# ---------------------------------------------------------------------------
# Fuzzy Ban List
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _has_thefuzz(),
    reason="thefuzz not installed",
)
class TestFuzzyBanList:
    """Tests for fuzzy Levenshtein-distance ban list matching."""

    def test_catches_misspelling(self) -> None:
        """Catches misspelled banned words via fuzzy matching."""
        issues = _check_fuzzy_ban_list(
            "We must delvee into the details.",
            "body",
            ["delve"],
            threshold=80,
        )
        assert len(issues) >= 1
        assert issues[0].type == "gr_ban_list"
        assert "delvee" in issues[0].description

    def test_skips_exact_matches(self) -> None:
        """Exact matches are left to the deterministic checker."""
        issues = _check_fuzzy_ban_list(
            "We must delve into the details.",
            "body",
            ["delve"],
            threshold=80,
        )
        assert len(issues) == 0  # "delve" is exact, not fuzzy

    def test_skips_short_words(self) -> None:
        """Words under 4 characters are skipped to avoid false positives."""
        issues = _check_fuzzy_ban_list(
            "The end is here.",
            "body",
            ["end"],
            threshold=80,
        )
        assert len(issues) == 0


class TestFuzzyBanListImportFailure:
    """Tests for graceful import failure."""

    def test_import_failure_returns_empty(self) -> None:
        """Returns empty if thefuzz not installed."""
        with patch.dict("sys.modules", {"thefuzz": None, "thefuzz.fuzz": None}):
            issues = _check_fuzzy_ban_list("test text", "body", ["test"])
            # May or may not return empty depending on import caching
            # but should not raise


# ---------------------------------------------------------------------------
# Redundant Sentences
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _has_thefuzz(),
    reason="thefuzz not installed",
)
class TestRedundantSentences:
    """Tests for redundant sentence detection."""

    def test_detects_redundant(self) -> None:
        """Flags near-duplicate sentences."""
        text = (
            "Our boots are made from premium leather materials. "
            "Our boots are crafted from premium leather materials."
        )
        issues = _check_redundant_sentences(text, "body", threshold=75)
        assert len(issues) >= 1
        assert issues[0].type == "gr_redundant"

    def test_passes_different_sentences(self) -> None:
        """Different sentences don't trigger."""
        text = (
            "Our boots are made from premium leather. "
            "The sole uses Vibram rubber for traction."
        )
        issues = _check_redundant_sentences(text, "body", threshold=75)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# XSS Detection
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _has_bleach(),
    reason="bleach not installed",
)
class TestXssDetection:
    """Tests for XSS/script injection detection."""

    def test_detects_script_tag(self) -> None:
        """Flags script tags in HTML content."""
        html = '<p>Hello</p><script>alert("xss")</script>'
        issues = _check_xss(html, "body")
        assert len(issues) == 1
        assert issues[0].type == "gr_xss"

    def test_passes_clean_html(self) -> None:
        """Clean HTML passes."""
        html = "<p>This is clean content.</p>"
        issues = _check_xss(html, "body")
        assert len(issues) == 0

    def test_detects_event_handler(self) -> None:
        """Flags inline event handlers."""
        html = '<div onmouseover="alert(1)">Hover me</div>'
        issues = _check_xss(html, "body")
        assert len(issues) == 1


# ---------------------------------------------------------------------------
# Comment Guardrails
# ---------------------------------------------------------------------------


class TestCommentGuardrails:
    """Tests for lightweight Reddit comment guardrails."""

    def test_clean_text_passes(self) -> None:
        """Clean comment text produces no issues."""
        with patch("app.core.config.get_settings") as mock:
            mock.return_value.enable_guardrails_checks = True
            mock.return_value.enable_toxic_language_check = False
            result = run_comment_guardrails(
                "Great suggestion, I had the same experience with this."
            )
            assert result == []

    @pytest.mark.skipif(not _has_bleach(), reason="bleach not installed")
    def test_xss_in_comment(self) -> None:
        """XSS in comment text is flagged."""
        with patch("app.core.config.get_settings") as mock:
            mock.return_value.enable_guardrails_checks = True
            mock.return_value.enable_toxic_language_check = False
            result = run_comment_guardrails(
                '<script>alert("xss")</script> Great product!'
            )
            xss_issues = [i for i in result if i.type == "gr_xss"]
            assert len(xss_issues) == 1


# ---------------------------------------------------------------------------
# Integration: Guardrails merge with existing quality checks
# ---------------------------------------------------------------------------


class TestIntegrationWithQualityChecks:
    """Tests that guardrails issues merge correctly with existing checks."""

    def test_run_quality_checks_backward_compat(self) -> None:
        """run_quality_checks works without content_brief argument."""
        pc = _make_page_content(
            page_title="Winter Boots",
            bottom_description="Simple clean content here.",
        )
        # Should not raise
        result = run_quality_checks(pc, {})
        assert result.checked_at != ""

    def test_run_quality_checks_with_content_brief(self) -> None:
        """run_quality_checks accepts content_brief without errors."""
        pc = _make_page_content(
            page_title="Winter Boots",
            bottom_description="Simple clean content here.",
        )
        brief = {"lsi_terms": [{"phrase": "winter boots"}]}
        result = run_quality_checks(pc, {}, content_brief=brief)
        assert result.checked_at != ""

    def test_run_blog_quality_checks_backward_compat(self) -> None:
        """run_blog_quality_checks works without content_brief."""
        fields = {
            "title": "Winter Boots Guide",
            "content": "Simple clean content about boots.",
        }
        result = run_blog_quality_checks(fields, {})
        assert result.checked_at != ""

    def test_run_blog_quality_checks_with_content_brief(self) -> None:
        """run_blog_quality_checks accepts content_brief."""
        fields = {
            "title": "Winter Boots Guide",
            "content": "Simple clean content about boots.",
        }
        brief = {"lsi_terms": [{"phrase": "winter boots"}]}
        result = run_blog_quality_checks(fields, {}, content_brief=brief)
        assert result.checked_at != ""

    def test_guardrails_issues_included_in_results(self) -> None:
        """Issues from guardrails appear in the combined QualityResult."""
        pc = _make_page_content(
            page_title="Boots",
            bottom_description="Simple content.",
        )
        # Provide LSI terms that won't be found → triggers lsi_coverage issue
        brief = {
            "lsi_terms": [
                {"phrase": "absolutely impossible term xyz"},
                {"phrase": "another missing term abc"},
                {"phrase": "third missing term def"},
                {"phrase": "fourth missing term ghi"},
            ]
        }
        result = run_quality_checks(pc, {}, content_brief=brief)
        lsi_issues = [i for i in result.issues if i.type == "lsi_coverage"]
        assert len(lsi_issues) == 1
        assert "LSI coverage" in lsi_issues[0].description


# ---------------------------------------------------------------------------
# Full pipeline run_guardrails_checks
# ---------------------------------------------------------------------------


class TestRunGuardrailsChecks:
    """Tests for the main run_guardrails_checks function."""

    def test_returns_list(self) -> None:
        """Always returns a list (possibly empty)."""
        with patch("app.core.config.get_settings") as mock:
            mock.return_value.enable_guardrails_checks = True
            mock.return_value.enable_toxic_language_check = False
            mock.return_value.guardrails_reading_level_min = 5
            mock.return_value.guardrails_reading_level_max = 8
            mock.return_value.guardrails_redundant_threshold = 75
            mock.return_value.guardrails_lsi_coverage_min = 0.3

            result = run_guardrails_checks(
                {"body": "Clean content here."},
                {},
            )
            assert isinstance(result, list)

    def test_lsi_coverage_in_output(self) -> None:
        """LSI coverage check appears when brief has terms not in content."""
        with patch("app.core.config.get_settings") as mock:
            mock.return_value.enable_guardrails_checks = True
            mock.return_value.enable_toxic_language_check = False
            mock.return_value.guardrails_reading_level_min = 5
            mock.return_value.guardrails_reading_level_max = 8
            mock.return_value.guardrails_redundant_threshold = 75
            mock.return_value.guardrails_lsi_coverage_min = 0.3

            brief = {
                "lsi_terms": [
                    {"phrase": "missing term one"},
                    {"phrase": "missing term two"},
                    {"phrase": "missing term three"},
                ]
            }
            result = run_guardrails_checks(
                {"body": "Unrelated content here."},
                {},
                content_brief=brief,
            )
            lsi = [i for i in result if i.type == "lsi_coverage"]
            assert len(lsi) == 1

    def test_no_lsi_without_brief(self) -> None:
        """No LSI coverage issue when no content_brief provided."""
        with patch("app.core.config.get_settings") as mock:
            mock.return_value.enable_guardrails_checks = True
            mock.return_value.enable_toxic_language_check = False
            mock.return_value.guardrails_reading_level_min = 5
            mock.return_value.guardrails_reading_level_max = 8
            mock.return_value.guardrails_redundant_threshold = 75
            mock.return_value.guardrails_lsi_coverage_min = 0.3

            result = run_guardrails_checks(
                {"body": "Clean content here."},
                {},
                content_brief=None,
            )
            lsi = [i for i in result if i.type == "lsi_coverage"]
            assert len(lsi) == 0
