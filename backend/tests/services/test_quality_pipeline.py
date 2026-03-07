"""Tests for quality pipeline orchestrator.

Covers:
- _compute_score: deduction logic, PER_PIECE_TYPES, floor at 0
- _get_score_tier: boundary values for each tier
- run_quality_pipeline: tier2 disabled, short-circuit, tier2 failure, blog mode
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services.content_quality import QualityIssue, QualityResult
from app.services.quality_pipeline import (
    PipelineResult,
    _compute_score,
    _get_score_tier,
    run_quality_pipeline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakePageContent:
    """Stand-in for PageContent to avoid SQLAlchemy session issues."""

    def __init__(self, **kwargs: Any) -> None:
        self.page_title: str | None = kwargs.get("page_title", "Test Page Title")
        self.meta_description: str | None = kwargs.get("meta_description", "Test meta description")
        self.top_description: str | None = kwargs.get("top_description", "Test top description")
        self.bottom_description: str | None = kwargs.get("bottom_description", "Test bottom content")
        self.qa_results: dict[str, Any] | None = None


def _issue(type: str, field: str = "all") -> QualityIssue:
    """Create a minimal QualityIssue for testing."""
    return QualityIssue(type=type, field=field, description=f"test {type}", context="...")


def _mock_settings(**overrides: Any) -> MagicMock:
    """Create mock settings with required quality pipeline attributes."""
    settings = MagicMock()
    settings.quality_tier2_enabled = overrides.get("quality_tier2_enabled", False)
    settings.quality_auto_rewrite_enabled = overrides.get("quality_auto_rewrite_enabled", False)
    settings.quality_auto_rewrite_threshold = overrides.get("quality_auto_rewrite_threshold", 70)
    return settings


# ---------------------------------------------------------------------------
# _compute_score
# ---------------------------------------------------------------------------


class TestComputeScore:
    """Tests for the score computation function."""

    def test_no_issues(self) -> None:
        assert _compute_score([]) == 100

    def test_single_tier1_ai_word(self) -> None:
        issues = [_issue("tier1_ai_word")]
        assert _compute_score(issues) == 95

    def test_single_em_dash(self) -> None:
        issues = [_issue("em_dash")]
        assert _compute_score(issues) == 98

    def test_per_piece_deducted_once(self) -> None:
        """PER_PIECE_TYPES should only deduct once even with multiple issues."""
        issues = [_issue("triplet_excess"), _issue("triplet_excess"), _issue("triplet_excess")]
        # triplet_excess = 2pt deduction, only once = 98
        assert _compute_score(issues) == 98

    def test_llm_judge_deductions(self) -> None:
        issues = [_issue("llm_naturalness")]
        # llm_naturalness = 5pt deduction, PER_PIECE so only once
        assert _compute_score(issues) == 95

    def test_combined_issues(self) -> None:
        issues = [
            _issue("tier1_ai_word"),  # 5
            _issue("em_dash"),  # 2
            _issue("ai_pattern"),  # 3
        ]
        assert _compute_score(issues) == 90

    def test_floor_at_zero(self) -> None:
        # Create enough issues to exceed 100 points of deductions
        issues = [_issue("tier1_ai_word") for _ in range(25)]  # 25 * 5 = 125
        assert _compute_score(issues) == 0

    def test_multiple_per_piece_types(self) -> None:
        """Different PER_PIECE_TYPES each deducted once."""
        issues = [
            _issue("triplet_excess"),  # 2 (once)
            _issue("triplet_excess"),  # skip
            _issue("rhetorical_excess"),  # 2 (once)
            _issue("rhetorical_excess"),  # skip
            _issue("llm_naturalness"),  # 5 (once)
            _issue("llm_naturalness"),  # skip
        ]
        assert _compute_score(issues) == 91  # 100 - 2 - 2 - 5

    def test_unknown_issue_type_defaults_to_2(self) -> None:
        issues = [_issue("unknown_type")]
        assert _compute_score(issues) == 98


# ---------------------------------------------------------------------------
# _get_score_tier
# ---------------------------------------------------------------------------


class TestGetScoreTier:
    """Tests for mapping scores to tier labels."""

    def test_score_95_publish_ready(self) -> None:
        assert _get_score_tier(95) == "publish_ready"

    def test_score_90_boundary_publish_ready(self) -> None:
        assert _get_score_tier(90) == "publish_ready"

    def test_score_89_minor_issues(self) -> None:
        assert _get_score_tier(89) == "minor_issues"

    def test_score_70_boundary_minor_issues(self) -> None:
        assert _get_score_tier(70) == "minor_issues"

    def test_score_69_needs_attention(self) -> None:
        assert _get_score_tier(69) == "needs_attention"

    def test_score_50_boundary_needs_attention(self) -> None:
        assert _get_score_tier(50) == "needs_attention"

    def test_score_49_needs_rewrite(self) -> None:
        assert _get_score_tier(49) == "needs_rewrite"

    def test_score_0_needs_rewrite(self) -> None:
        assert _get_score_tier(0) == "needs_rewrite"

    def test_score_100(self) -> None:
        assert _get_score_tier(100) == "publish_ready"


# ---------------------------------------------------------------------------
# run_quality_pipeline
# ---------------------------------------------------------------------------


class TestRunQualityPipeline:
    """Tests for the full quality pipeline orchestrator."""

    async def test_tier2_disabled(self, mocker: Any) -> None:
        """When tier2 is disabled, only tier1 runs."""
        mocker.patch("app.services.quality_pipeline.get_settings", return_value=_mock_settings())

        # Mock tier1 returning no issues
        mock_tier1 = QualityResult(passed=True, issues=[], checked_at="2026-01-01T00:00:00", bibles_matched=[])
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        content = _FakePageContent()
        result = await run_quality_pipeline(content=content, brand_config={})

        assert isinstance(result, PipelineResult)
        assert result.score == 100
        assert result.score_tier == "publish_ready"
        assert result.tier2 is None
        assert result.short_circuited is False

    async def test_short_circuit_on_critical_issues(self, mocker: Any) -> None:
        """Critical tier1 issues should short-circuit tier2."""
        mocker.patch("app.services.quality_pipeline.get_settings", return_value=_mock_settings(quality_tier2_enabled=True))

        critical_issue = QualityIssue(
            type="tier1_ai_word",
            field="bottom_description",
            description='Tier 1 AI word "delve" detected',
            context="...delve into...",
        )
        mock_tier1 = QualityResult(
            passed=False,
            issues=[critical_issue],
            checked_at="2026-01-01T00:00:00",
            bibles_matched=[],
        )
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        content = _FakePageContent()
        result = await run_quality_pipeline(content=content, brand_config={})

        assert result.short_circuited is True
        assert result.tier2 is None
        assert len(result.issues) == 1
        assert result.issues[0].type == "tier1_ai_word"

    async def test_tier2_failure_returns_tier1_with_error(self, mocker: Any) -> None:
        """If tier2 LLM judge throws, return tier1 results with tier2 error."""
        mocker.patch("app.services.quality_pipeline.get_settings", return_value=_mock_settings(quality_tier2_enabled=True))

        mock_tier1 = QualityResult(passed=True, issues=[], checked_at="2026-01-01T00:00:00", bibles_matched=[])
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        mocker.patch(
            "app.services.quality_pipeline.run_llm_judge_checks",
            side_effect=RuntimeError("OpenAI is down"),
        )

        content = _FakePageContent()
        result = await run_quality_pipeline(content=content, brand_config={})

        assert result.tier2 is not None
        assert "error" in result.tier2
        assert "RuntimeError" in result.tier2["error"]
        # Score is still computed from tier1 (no issues)
        assert result.score == 100

    async def test_blog_mode_uses_blog_checks(self, mocker: Any) -> None:
        """When is_blog=True, run_blog_quality_checks is used."""
        mocker.patch("app.services.quality_pipeline.get_settings", return_value=_mock_settings())

        mock_blog_result = QualityResult(
            passed=False,
            issues=[
                QualityIssue(
                    type="tier3_banned_phrase",
                    field="content",
                    description='Tier 3 banned phrase detected',
                    context="...in today's fast-paced world...",
                )
            ],
            checked_at="2026-01-01T00:00:00",
            bibles_matched=[],
        )
        mock_blog_fn = mocker.patch(
            "app.services.quality_pipeline.run_blog_quality_checks",
            return_value=mock_blog_result,
        )

        fields = {"content": "In today's fast-paced world, things are changing."}
        result = await run_quality_pipeline(
            fields=fields, brand_config={}, is_blog=True
        )

        mock_blog_fn.assert_called_once()
        assert result.score == 97  # 100 - 3 (tier3_banned_phrase)
        assert len(result.issues) == 1

    async def test_tier2_success_includes_data(self, mocker: Any) -> None:
        """When tier2 succeeds, tier2 data is included in result."""
        mocker.patch("app.services.quality_pipeline.get_settings", return_value=_mock_settings(quality_tier2_enabled=True))

        mock_tier1 = QualityResult(passed=True, issues=[], checked_at="2026-01-01T00:00:00", bibles_matched=[])
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        # Mock llm_judge to return good scores
        from app.services.llm_judge import JudgeRunResult

        mock_judge_result = JudgeRunResult(
            naturalness=0.9,
            brief_adherence=0.85,
            heading_structure=0.8,
            issues=[],
            model="gpt-4.1",
            cost_usd=0.01,
            latency_ms=500,
            error=None,
        )
        mocker.patch(
            "app.services.quality_pipeline.run_llm_judge_checks",
            return_value=mock_judge_result,
        )

        content = _FakePageContent()
        result = await run_quality_pipeline(content=content, brand_config={})

        assert result.tier2 is not None
        assert result.tier2["naturalness"] == 0.9
        assert result.tier2["brief_adherence"] == 0.85
        assert result.tier2["heading_structure"] == 0.8
        assert result.tier2["model"] == "gpt-4.1"
        assert "error" not in result.tier2
        assert result.score == 100

    async def test_no_content_no_fields_fallback(self, mocker: Any) -> None:
        """When neither content nor fields provided, fallback to empty result."""
        mocker.patch("app.services.quality_pipeline.get_settings", return_value=_mock_settings())

        result = await run_quality_pipeline()

        assert result.score == 100
        assert result.issues == []

    async def test_qa_results_stored_on_content(self, mocker: Any) -> None:
        """Pipeline stores results in content.qa_results when content is provided."""
        mocker.patch("app.services.quality_pipeline.get_settings", return_value=_mock_settings())

        mock_tier1 = QualityResult(passed=True, issues=[], checked_at="2026-01-01T00:00:00", bibles_matched=[])
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        content = _FakePageContent()
        assert content.qa_results is None

        result = await run_quality_pipeline(content=content, brand_config={})

        assert content.qa_results is not None
        assert content.qa_results["score"] == 100

    async def test_pipeline_result_to_dict(self, mocker: Any) -> None:
        """PipelineResult.to_dict includes expected fields."""
        result = PipelineResult(
            passed=True,
            score=95,
            score_tier="publish_ready",
            issues=[],
            checked_at="2026-01-01T00:00:00",
            bibles_matched=["Test Bible"],
            tier2={"naturalness": 0.9},
            short_circuited=False,
        )
        d = result.to_dict()
        assert d["passed"] is True
        assert d["score"] == 95
        assert d["score_tier"] == "publish_ready"
        assert d["bibles_matched"] == ["Test Bible"]
        assert d["tier2"]["naturalness"] == 0.9
        assert "short_circuited" not in d  # Only included when True

    async def test_content_and_fields_mutually_exclusive(self) -> None:
        """Providing both content and fields should raise ValueError."""
        with pytest.raises(ValueError, match="either"):
            await run_quality_pipeline(
                content=_FakePageContent(),
                fields={"body": "text"},
                brand_config={},
            )

    async def test_pipeline_result_to_dict_short_circuited(self) -> None:
        result = PipelineResult(
            passed=False,
            score=80,
            score_tier="minor_issues",
            issues=[],
            checked_at="2026-01-01T00:00:00",
            short_circuited=True,
        )
        d = result.to_dict()
        assert d["short_circuited"] is True

    async def test_pipeline_result_to_dict_with_rewrite(self) -> None:
        """PipelineResult.to_dict includes rewrite and versions when set."""
        result = PipelineResult(
            passed=True,
            score=88,
            score_tier="minor_issues",
            issues=[],
            checked_at="2026-01-01T00:00:00",
            rewrite={
                "triggered": True,
                "original_score": 52,
                "fixed_score": 88,
                "kept_version": "fixed",
            },
            versions={
                "original": {"score": 52, "content_snapshot": {}},
                "fixed": {"score": 88, "changes_made": ["change 1"]},
            },
            final_fields={"top_description": "<p>Fixed</p>"},
        )
        d = result.to_dict()
        assert d["rewrite"]["triggered"] is True
        assert d["rewrite"]["kept_version"] == "fixed"
        assert d["versions"]["original"]["score"] == 52
        assert d["versions"]["fixed"]["score"] == 88
        # final_fields is transient, should NOT be in to_dict
        assert "final_fields" not in d

    async def test_pipeline_result_to_dict_without_rewrite(self) -> None:
        """Rewrite and versions absent when not set (backward compatible)."""
        result = PipelineResult(
            passed=True,
            score=95,
            score_tier="publish_ready",
            issues=[],
            checked_at="2026-01-01T00:00:00",
        )
        d = result.to_dict()
        assert "rewrite" not in d
        assert "versions" not in d

    async def test_auto_rewrite_disabled_no_rewrite(self, mocker: Any) -> None:
        """When auto-rewrite is disabled, no rewrite happens even with low score."""
        mocker.patch("app.services.quality_pipeline.get_settings", return_value=_mock_settings())

        # Create issues that will produce a low score
        issues = [
            QualityIssue(type="tier1_ai_word", field="top_description", description="test", context="..."),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test2", context="..."),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test3", context="..."),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test4", context="..."),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test5", context="..."),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test6", context="..."),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test7", context="..."),
        ]  # 7 * 5 = 35 deduction, score = 65
        mock_tier1 = QualityResult(
            passed=False, issues=issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        content = _FakePageContent()
        result = await run_quality_pipeline(content=content, brand_config={})

        assert result.score == 65
        assert result.rewrite is None
        assert result.versions is None
        assert result.final_fields is None

    async def test_auto_rewrite_enabled_improves_score(self, mocker: Any) -> None:
        """When auto-rewrite is enabled and fixer improves score, fixed version is kept."""
        mocker.patch(
            "app.services.quality_pipeline.get_settings",
            return_value=_mock_settings(
                quality_auto_rewrite_enabled=True,
                quality_auto_rewrite_threshold=70,
            ),
        )

        # Original tier1 with fixable issues (score = 65)
        original_issues = [
            QualityIssue(type="tier1_ai_word", field="top_description", description="test", context="delve"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test2", context="utilize"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test3", context="leverage"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test4", context="facilitate"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test5", context="robust"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test6", context="seamless"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test7", context="journey"),
        ]
        mock_tier1 = QualityResult(
            passed=False, issues=original_issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        # Mock fix_content to return a "fixed" version
        from app.services.quality_fixer import FixResult

        mock_fix = FixResult(
            success=True,
            fixed_fields={"top_description": "<p>Fixed content without AI words</p>"},
            changes_made=["Replaced AI words"],
            issues_sent=7,
            cost_usd=0.01,
            latency_ms=500,
        )
        mocker.patch("app.services.quality_fixer.fix_content", return_value=mock_fix)

        # Mock recheck: fixed version has fewer issues (score = 95)
        fixed_issues = [
            QualityIssue(type="tier1_ai_word", field="top_description", description="remaining", context="optimal"),
        ]
        mock_recheck = QualityResult(
            passed=False, issues=fixed_issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )
        mocker.patch("app.services.quality_pipeline.run_fields_quality_checks", return_value=mock_recheck)

        content = _FakePageContent()
        result = await run_quality_pipeline(content=content, brand_config={})

        assert result.rewrite is not None
        assert result.rewrite["kept_version"] == "fixed"
        assert result.rewrite["original_score"] == 65
        assert result.rewrite["fixed_score"] == 95
        assert result.score == 95
        assert result.score_tier == "publish_ready"
        # Issues should be updated to the fixed version's issues
        assert len(result.issues) == 1
        assert result.issues[0].context == "optimal"
        assert result.final_fields is not None
        assert "top_description" in result.final_fields

    async def test_auto_rewrite_no_improvement_keeps_original(self, mocker: Any) -> None:
        """When fixer doesn't improve score, original is kept."""
        mocker.patch(
            "app.services.quality_pipeline.get_settings",
            return_value=_mock_settings(
                quality_auto_rewrite_enabled=True,
                quality_auto_rewrite_threshold=70,
            ),
        )

        original_issues = [
            QualityIssue(type="tier1_ai_word", field="top_description", description="test", context="delve"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test2", context="utilize"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test3", context="leverage"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test4", context="facilitate"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test5", context="robust"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test6", context="seamless"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test7", context="journey"),
        ]
        mock_tier1 = QualityResult(
            passed=False, issues=original_issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        from app.services.quality_fixer import FixResult

        mock_fix = FixResult(
            success=True,
            fixed_fields={"top_description": "<p>Made it worse</p>"},
            changes_made=["Bad rewrite"],
            issues_sent=7,
            cost_usd=0.01,
            latency_ms=500,
        )
        mocker.patch("app.services.quality_fixer.fix_content", return_value=mock_fix)

        # Recheck shows more issues (score = 55) — worse than original (65)
        fixed_issues = [
            QualityIssue(type="tier1_ai_word", field="top_description", description=f"new{i}", context="...")
            for i in range(9)
        ]
        mock_recheck = QualityResult(
            passed=False, issues=fixed_issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )
        mocker.patch("app.services.quality_pipeline.run_fields_quality_checks", return_value=mock_recheck)

        content = _FakePageContent()
        result = await run_quality_pipeline(content=content, brand_config={})

        assert result.rewrite is not None
        assert result.rewrite["kept_version"] == "original"
        assert result.score == 65  # Original score preserved
        # Issues should be the ORIGINAL issues (not updated)
        assert len(result.issues) == 7

    async def test_auto_rewrite_uses_blog_checks_for_blog(self, mocker: Any) -> None:
        """When is_blog=True, recheck uses run_blog_quality_checks (not run_fields_quality_checks)."""
        mocker.patch(
            "app.services.quality_pipeline.get_settings",
            return_value=_mock_settings(
                quality_auto_rewrite_enabled=True,
                quality_auto_rewrite_threshold=70,
            ),
        )

        original_issues = [
            QualityIssue(type="tier1_ai_word", field="content", description=f"test{i}", context=f"word{i}")
            for i in range(7)
        ]
        mock_tier1 = QualityResult(
            passed=False, issues=original_issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )

        from app.services.quality_fixer import FixResult

        mock_fix = FixResult(
            success=True,
            fixed_fields={"content": "<p>Fixed blog</p>"},
            changes_made=["Fixed"],
            issues_sent=7,
            cost_usd=0.01,
            latency_ms=500,
        )
        mocker.patch("app.services.quality_fixer.fix_content", return_value=mock_fix)

        mock_recheck = QualityResult(
            passed=True, issues=[], checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )

        # Use side_effect to return tier1 result first call, recheck result second call
        blog_mock = mocker.patch(
            "app.services.quality_pipeline.run_blog_quality_checks",
            side_effect=[mock_tier1, mock_recheck],
        )
        # fields_quality_checks should NOT be called for blogs
        fields_mock = mocker.patch(
            "app.services.quality_pipeline.run_fields_quality_checks",
            return_value=mock_recheck,
        )

        fields = {"content": "Blog content with AI words delve utilize leverage"}
        result = await run_quality_pipeline(fields=fields, brand_config={}, is_blog=True)

        # blog_quality_checks called twice: initial + recheck
        assert blog_mock.call_count == 2
        # fields_quality_checks should NOT have been called for blog content
        assert fields_mock.call_count == 0

    async def test_auto_rewrite_partial_fix_accepted(self, mocker: Any) -> None:
        """Partial fix (success=False but fixed_fields present) is evaluated."""
        mocker.patch(
            "app.services.quality_pipeline.get_settings",
            return_value=_mock_settings(
                quality_auto_rewrite_enabled=True,
                quality_auto_rewrite_threshold=70,
            ),
        )

        original_issues = [
            QualityIssue(type="tier1_ai_word", field="top_description", description="test", context="delve"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test2", context="utilize"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test3", context="leverage"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test4", context="facilitate"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test5", context="robust"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test6", context="seamless"),
            QualityIssue(type="tier1_ai_word", field="top_description", description="test7", context="journey"),
        ]
        mock_tier1 = QualityResult(
            passed=False, issues=original_issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        from app.services.quality_fixer import FixResult

        # Partial fix: success=False but some fields were fixed
        mock_fix = FixResult(
            success=False,
            fixed_fields={"top_description": "<p>Partially fixed</p>"},
            changes_made=["Fixed some issues"],
            issues_sent=7,
            cost_usd=0.01,
            latency_ms=500,
            error="Fix failed for bottom_description",
        )
        mocker.patch("app.services.quality_fixer.fix_content", return_value=mock_fix)

        # Recheck shows improvement
        fixed_issues = [
            QualityIssue(type="tier1_ai_word", field="top_description", description="remaining", context="optimal"),
        ]
        mock_recheck = QualityResult(
            passed=False, issues=fixed_issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )
        mocker.patch("app.services.quality_pipeline.run_fields_quality_checks", return_value=mock_recheck)

        content = _FakePageContent()
        result = await run_quality_pipeline(content=content, brand_config={})

        # Partial fix should still be evaluated and kept if better
        assert result.rewrite is not None
        assert result.rewrite["kept_version"] == "fixed"
        assert result.score == 95  # 100 - 5 (one remaining issue)

    async def test_auto_rewrite_issues_updated_in_qa_results(self, mocker: Any) -> None:
        """qa_results.issues reflects the fixed version when rewrite kept."""
        mocker.patch(
            "app.services.quality_pipeline.get_settings",
            return_value=_mock_settings(
                quality_auto_rewrite_enabled=True,
                quality_auto_rewrite_threshold=70,
            ),
        )

        original_issues = [
            QualityIssue(type="tier1_ai_word", field="top_description", description=f"issue{i}", context=f"word{i}")
            for i in range(7)
        ]
        mock_tier1 = QualityResult(
            passed=False, issues=original_issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )
        mocker.patch("app.services.quality_pipeline.run_quality_checks", return_value=mock_tier1)

        from app.services.quality_fixer import FixResult

        mock_fix = FixResult(
            success=True,
            fixed_fields={"top_description": "<p>Fixed</p>"},
            changes_made=["Fixed all AI words"],
            issues_sent=7,
            cost_usd=0.01,
            latency_ms=500,
        )
        mocker.patch("app.services.quality_fixer.fix_content", return_value=mock_fix)

        # Recheck: only 1 issue remains
        fixed_issues = [
            QualityIssue(type="em_dash", field="top_description", description="em dash found", context="—"),
        ]
        mock_recheck = QualityResult(
            passed=False, issues=fixed_issues, checked_at="2026-01-01T00:00:00", bibles_matched=[]
        )
        mocker.patch("app.services.quality_pipeline.run_fields_quality_checks", return_value=mock_recheck)

        content = _FakePageContent()
        result = await run_quality_pipeline(content=content, brand_config={})

        # Score and issues should both reflect the fixed version
        assert result.score == 98  # 100 - 2 (em_dash)
        assert len(result.issues) == 1
        assert result.issues[0].type == "em_dash"

        # qa_results on the content object should also be consistent
        assert content.qa_results is not None
        assert content.qa_results["score"] == 98
        assert len(content.qa_results["issues"]) == 1
        assert content.qa_results["issues"][0]["type"] == "em_dash"
