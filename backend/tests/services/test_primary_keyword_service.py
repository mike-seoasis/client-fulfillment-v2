"""Unit tests for PrimaryKeywordService.

Tests cover:
- Scoring formula calculation with various inputs
- Edge cases: zero volume, null values, negative values
- Formula weight verification (50% volume, 35% relevance, 15% competition)

Note: Tests do not require API calls - they test the synchronous calculate_score method.
"""

import pytest

from app.services.primary_keyword import (
    KeywordGenerationStats,
    PrimaryKeywordService,
)

# ---------------------------------------------------------------------------
# Mock clients for service initialization
# ---------------------------------------------------------------------------


class MockClaudeClient:
    """Minimal mock Claude client for service initialization."""

    available = True


class MockDataForSEOClient:
    """Minimal mock DataForSEO client for service initialization."""

    available = True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def primary_keyword_service() -> PrimaryKeywordService:
    """Create PrimaryKeywordService with mock clients."""
    return PrimaryKeywordService(
        claude_client=MockClaudeClient(),  # type: ignore[arg-type]
        dataforseo_client=MockDataForSEOClient(),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestCalculateScoreHighVolumeScenarios:
    """Tests for scoring high volume, low competition keywords."""

    def test_high_volume_low_competition_high_relevance(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test scoring with high volume (10,000), low competition (0.1), high relevance (0.9)."""
        result = primary_keyword_service.calculate_score(
            volume=10000,
            competition=0.1,
            relevance=0.9,
        )

        # Volume: log10(10000) * 10 = 4 * 10 = 40
        assert result["volume_score"] == 40.0

        # Competition: (1 - 0.1) * 100 = 90
        assert result["competition_score"] == 90.0

        # Relevance: 0.9 * 100 = 90
        assert result["relevance_score"] == 90.0

        # Composite: (40 * 0.50) + (90 * 0.35) + (90 * 0.15) = 20 + 31.5 + 13.5 = 65
        assert result["composite_score"] == 65.0

    def test_high_volume_zero_competition(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test scoring with high volume and zero competition (best case)."""
        result = primary_keyword_service.calculate_score(
            volume=100000,  # Max volume score
            competition=0.0,  # Best competition
            relevance=1.0,   # Perfect relevance
        )

        # Volume: log10(100000) * 10 = 5 * 10 = 50 (capped)
        assert result["volume_score"] == 50.0

        # Competition: (1 - 0) * 100 = 100
        assert result["competition_score"] == 100.0

        # Relevance: 1.0 * 100 = 100
        assert result["relevance_score"] == 100.0

        # Composite: (50 * 0.50) + (100 * 0.35) + (100 * 0.15) = 25 + 35 + 15 = 75
        assert result["composite_score"] == 75.0

    def test_very_high_volume_caps_at_50(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that volume score caps at 50 for very high volumes."""
        # 1 million searches - should cap at 50
        result = primary_keyword_service.calculate_score(
            volume=1000000,
            competition=0.5,
            relevance=0.5,
        )

        # log10(1000000) * 10 = 6 * 10 = 60, but capped at 50
        assert result["volume_score"] == 50.0


class TestCalculateScoreLowVolumeHighRelevance:
    """Tests for scoring low volume but high relevance keywords."""

    def test_low_volume_high_relevance(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test scoring with low volume (100), high competition (0.8), high relevance (0.95)."""
        result = primary_keyword_service.calculate_score(
            volume=100,
            competition=0.8,
            relevance=0.95,
        )

        # Volume: log10(100) * 10 = 2 * 10 = 20
        assert result["volume_score"] == 20.0

        # Competition: (1 - 0.8) * 100 = 20
        assert result["competition_score"] == 20.0

        # Relevance: 0.95 * 100 = 95
        assert result["relevance_score"] == 95.0

        # Composite: (20 * 0.50) + (95 * 0.35) + (20 * 0.15) = 10 + 33.25 + 3 = 46.25
        assert result["composite_score"] == 46.25

    def test_very_low_volume_still_scores(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test scoring with very low volume (10) still produces valid score."""
        result = primary_keyword_service.calculate_score(
            volume=10,
            competition=0.5,
            relevance=0.8,
        )

        # Volume: log10(10) * 10 = 1 * 10 = 10
        assert result["volume_score"] == 10.0

        # Should still have valid composite score
        assert result["composite_score"] > 0


class TestCalculateScoreZeroVolume:
    """Tests for zero volume handling (should not crash)."""

    def test_zero_volume_returns_zero_volume_score(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that zero volume returns 0 volume score without crashing."""
        result = primary_keyword_service.calculate_score(
            volume=0,
            competition=0.5,
            relevance=0.7,
        )

        # Zero volume should give 0 volume score
        assert result["volume_score"] == 0.0

        # Other scores should still work
        assert result["competition_score"] == 50.0  # (1 - 0.5) * 100
        assert result["relevance_score"] == 70.0    # 0.7 * 100

        # Composite: (0 * 0.50) + (70 * 0.35) + (50 * 0.15) = 0 + 24.5 + 7.5 = 32.0
        assert result["composite_score"] == 32.0

    def test_negative_volume_treated_as_zero(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that negative volume is treated as zero (edge case protection)."""
        result = primary_keyword_service.calculate_score(
            volume=-100,
            competition=0.5,
            relevance=0.5,
        )

        # Negative volume should be treated as 0
        assert result["volume_score"] == 0.0


class TestCalculateScoreNullValues:
    """Tests for null value handling."""

    def test_null_volume_returns_zero_volume_score(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that None volume returns 0 volume score."""
        result = primary_keyword_service.calculate_score(
            volume=None,
            competition=0.3,
            relevance=0.8,
        )

        # None volume should give 0 volume score
        assert result["volume_score"] == 0.0

        # Other scores should work
        assert result["competition_score"] == 70.0  # (1 - 0.3) * 100
        assert result["relevance_score"] == 80.0    # 0.8 * 100

    def test_null_competition_defaults_to_midrange(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that None competition defaults to 0.5 (midrange score of 50)."""
        result = primary_keyword_service.calculate_score(
            volume=1000,
            competition=None,
            relevance=0.7,
        )

        # Volume: log10(1000) * 10 = 3 * 10 = 30
        assert result["volume_score"] == 30.0

        # None competition should default to 50 (as if competition = 0.5)
        assert result["competition_score"] == 50.0

        # Relevance: 0.7 * 100 = 70
        assert result["relevance_score"] == 70.0

    def test_all_null_except_relevance(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test handling when volume and competition are both None."""
        result = primary_keyword_service.calculate_score(
            volume=None,
            competition=None,
            relevance=0.6,
        )

        # Volume score should be 0
        assert result["volume_score"] == 0.0

        # Competition should default to 50
        assert result["competition_score"] == 50.0

        # Relevance: 0.6 * 100 = 60
        assert result["relevance_score"] == 60.0

        # Composite: (0 * 0.50) + (60 * 0.35) + (50 * 0.15) = 0 + 21 + 7.5 = 28.5
        assert result["composite_score"] == 28.5


class TestCalculateScoreFormulaWeights:
    """Tests to verify formula weights are correct (50/35/15)."""

    def test_volume_weight_is_50_percent(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that volume contributes 50% of the composite score."""
        # Set relevance and competition to give 0 contribution
        result = primary_keyword_service.calculate_score(
            volume=10000,  # log10(10000) * 10 = 40
            competition=1.0,  # (1 - 1) * 100 = 0
            relevance=0.0,    # 0 * 100 = 0
        )

        # Only volume contributes: 40 * 0.50 = 20
        assert result["composite_score"] == 20.0

    def test_relevance_weight_is_35_percent(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that relevance contributes 35% of the composite score."""
        # Set volume and competition to give 0 contribution
        result = primary_keyword_service.calculate_score(
            volume=0,         # 0 volume score
            competition=1.0,  # (1 - 1) * 100 = 0
            relevance=1.0,    # 1.0 * 100 = 100
        )

        # Only relevance contributes: 100 * 0.35 = 35
        assert result["composite_score"] == 35.0

    def test_competition_weight_is_15_percent(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that competition contributes 15% of the composite score."""
        # Set volume and relevance to give 0 contribution
        result = primary_keyword_service.calculate_score(
            volume=0,         # 0 volume score
            competition=0.0,  # (1 - 0) * 100 = 100
            relevance=0.0,    # 0 * 100 = 0
        )

        # Only competition contributes: 100 * 0.15 = 15
        assert result["composite_score"] == 15.0

    def test_all_weights_sum_correctly(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that all weights (50 + 35 + 15 = 100) sum correctly."""
        # Use values that give nice round numbers
        result = primary_keyword_service.calculate_score(
            volume=100000,    # 50 (capped)
            competition=0.0,  # 100
            relevance=1.0,    # 100
        )

        # Composite: (50 * 0.50) + (100 * 0.35) + (100 * 0.15) = 25 + 35 + 15 = 75
        assert result["composite_score"] == 75.0

        # Verify individual components
        assert result["volume_score"] == 50.0
        assert result["competition_score"] == 100.0
        assert result["relevance_score"] == 100.0


class TestCalculateScoreEdgeCases:
    """Additional edge case tests."""

    def test_float_volume(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that float volume values are handled correctly."""
        result = primary_keyword_service.calculate_score(
            volume=1000.5,  # Float volume
            competition=0.5,
            relevance=0.5,
        )

        # log10(1000.5) * 10 ≈ 30.002 (very close to 30)
        assert 29.9 < result["volume_score"] < 30.1

    def test_boundary_volume_at_1(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test volume of 1 (log10(1) = 0)."""
        result = primary_keyword_service.calculate_score(
            volume=1,
            competition=0.5,
            relevance=0.5,
        )

        # log10(1) * 10 = 0 * 10 = 0
        assert result["volume_score"] == 0.0

    def test_competition_boundary_values(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test competition at boundary values 0.0 and 1.0."""
        # Competition = 0 (best)
        result_low = primary_keyword_service.calculate_score(
            volume=1000,
            competition=0.0,
            relevance=0.5,
        )
        assert result_low["competition_score"] == 100.0

        # Competition = 1.0 (worst)
        result_high = primary_keyword_service.calculate_score(
            volume=1000,
            competition=1.0,
            relevance=0.5,
        )
        assert result_high["competition_score"] == 0.0

    def test_relevance_boundary_values(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test relevance at boundary values 0.0 and 1.0."""
        # Relevance = 0 (worst)
        result_low = primary_keyword_service.calculate_score(
            volume=1000,
            competition=0.5,
            relevance=0.0,
        )
        assert result_low["relevance_score"] == 0.0

        # Relevance = 1.0 (best)
        result_high = primary_keyword_service.calculate_score(
            volume=1000,
            competition=0.5,
            relevance=1.0,
        )
        assert result_high["relevance_score"] == 100.0

    def test_scores_are_rounded_to_2_decimals(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that all scores are rounded to 2 decimal places."""
        result = primary_keyword_service.calculate_score(
            volume=123,       # log10(123) * 10 ≈ 20.899
            competition=0.333,
            relevance=0.777,
        )

        # All values should have at most 2 decimal places
        for key in ["volume_score", "competition_score", "relevance_score", "composite_score"]:
            # Check that rounding to 2 decimals gives the same value
            assert result[key] == round(result[key], 2)


class TestKeywordGenerationStatsDataclass:
    """Tests for the KeywordGenerationStats dataclass."""

    def test_stats_defaults(self) -> None:
        """Test that stats dataclass has correct defaults."""
        stats = KeywordGenerationStats()

        assert stats.pages_processed == 0
        assert stats.pages_succeeded == 0
        assert stats.pages_failed == 0
        assert stats.keywords_generated == 0
        assert stats.keywords_enriched == 0
        assert stats.claude_calls == 0
        assert stats.dataforseo_calls == 0
        assert stats.total_input_tokens == 0
        assert stats.total_output_tokens == 0
        assert stats.dataforseo_cost == 0.0
        assert stats.errors == []

    def test_stats_can_be_modified(self) -> None:
        """Test that stats can be modified."""
        stats = KeywordGenerationStats()
        stats.pages_processed = 10
        stats.keywords_generated = 100
        stats.errors.append({"error": "test"})

        assert stats.pages_processed == 10
        assert stats.keywords_generated == 100
        assert len(stats.errors) == 1


class TestPrimaryKeywordServiceInitialization:
    """Tests for service initialization and state management."""

    def test_service_initializes_with_empty_state(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that service initializes with empty state."""
        assert len(primary_keyword_service.used_primary_keywords) == 0
        assert primary_keyword_service.stats.pages_processed == 0
        assert primary_keyword_service.stats.claude_calls == 0

    def test_add_used_keyword(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test adding used keywords."""
        primary_keyword_service.add_used_keyword("test keyword")
        primary_keyword_service.add_used_keyword("ANOTHER Keyword")  # Should normalize

        assert "test keyword" in primary_keyword_service.used_primary_keywords
        assert "another keyword" in primary_keyword_service.used_primary_keywords  # Normalized

    def test_is_keyword_used(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test checking if keyword is used."""
        primary_keyword_service.add_used_keyword("used keyword")

        assert primary_keyword_service.is_keyword_used("used keyword") is True
        assert primary_keyword_service.is_keyword_used("USED KEYWORD") is True  # Case insensitive
        assert primary_keyword_service.is_keyword_used("unused keyword") is False

    def test_reset_stats(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test resetting stats."""
        # Modify stats
        primary_keyword_service._stats.pages_processed = 5
        primary_keyword_service._stats.claude_calls = 10

        # Reset
        primary_keyword_service.reset_stats()

        assert primary_keyword_service.stats.pages_processed == 0
        assert primary_keyword_service.stats.claude_calls == 0

    def test_reset_used_keywords(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test clearing used keywords."""
        primary_keyword_service.add_used_keyword("keyword1")
        primary_keyword_service.add_used_keyword("keyword2")

        primary_keyword_service.reset_used_keywords()

        assert len(primary_keyword_service.used_primary_keywords) == 0

    def test_get_stats_summary(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test getting stats summary dict."""
        primary_keyword_service._stats.pages_processed = 5
        primary_keyword_service._stats.pages_succeeded = 4
        primary_keyword_service._stats.pages_failed = 1
        primary_keyword_service.add_used_keyword("kw1")

        summary = primary_keyword_service.get_stats_summary()

        assert summary["pages_processed"] == 5
        assert summary["pages_succeeded"] == 4
        assert summary["pages_failed"] == 1
        assert summary["used_keywords_count"] == 1
        assert "error_count" in summary


# ---------------------------------------------------------------------------
# Duplicate Prevention Tests (S4-015)
# ---------------------------------------------------------------------------


class TestDuplicatePreventionUsedKeywordSkipped:
    """Tests for duplicate prevention: used keywords should be skipped."""

    def test_used_keyword_is_skipped_selects_second_best(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that a keyword already in used_primaries is skipped."""
        # Mark "best keyword" as already used
        primary_keyword_service.add_used_keyword("best keyword")

        scored_keywords = [
            {"keyword": "best keyword", "composite_score": 90.0, "volume": 5000},
            {"keyword": "second best", "composite_score": 85.0, "volume": 4000},
            {"keyword": "third option", "composite_score": 80.0, "volume": 3000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # "best keyword" should be skipped, "second best" should be selected
        assert result["primary"] is not None
        assert result["primary"]["keyword"] == "second best"
        assert result["primary"]["composite_score"] == 85.0

    def test_multiple_used_keywords_are_skipped(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that multiple used keywords are all skipped."""
        # Mark top 2 keywords as already used
        primary_keyword_service.add_used_keyword("first keyword")
        primary_keyword_service.add_used_keyword("second keyword")

        scored_keywords = [
            {"keyword": "first keyword", "composite_score": 95.0, "volume": 8000},
            {"keyword": "second keyword", "composite_score": 90.0, "volume": 6000},
            {"keyword": "third keyword", "composite_score": 85.0, "volume": 4000},
            {"keyword": "fourth keyword", "composite_score": 80.0, "volume": 3000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # First two should be skipped, third should be selected
        assert result["primary"] is not None
        assert result["primary"]["keyword"] == "third keyword"
        assert result["primary"]["composite_score"] == 85.0

    def test_case_insensitive_duplicate_check(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that duplicate checking is case-insensitive."""
        # Mark keyword with different case
        primary_keyword_service.add_used_keyword("BEST KEYWORD")

        scored_keywords = [
            {"keyword": "best keyword", "composite_score": 90.0, "volume": 5000},
            {"keyword": "second best", "composite_score": 85.0, "volume": 4000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # "best keyword" should be skipped (matches "BEST KEYWORD" case-insensitively)
        assert result["primary"] is not None
        assert result["primary"]["keyword"] == "second best"


class TestDuplicatePreventionNextBestSelection:
    """Tests for selecting next best keyword when first is used."""

    def test_next_best_selected_maintains_sort_order(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that keywords are still sorted by score when selecting next best."""
        primary_keyword_service.add_used_keyword("keyword a")

        # Keywords not in composite_score order initially
        scored_keywords = [
            {"keyword": "keyword c", "composite_score": 70.0, "volume": 2000},
            {"keyword": "keyword a", "composite_score": 90.0, "volume": 5000},
            {"keyword": "keyword b", "composite_score": 85.0, "volume": 4000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # Should select "keyword b" (second highest score) since "keyword a" is used
        assert result["primary"] is not None
        assert result["primary"]["keyword"] == "keyword b"

    def test_alternatives_exclude_used_keywords(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that alternatives also exclude already-used keywords."""
        # Mark a mid-ranking keyword as used
        primary_keyword_service.add_used_keyword("keyword c")

        scored_keywords = [
            {"keyword": "keyword a", "composite_score": 95.0, "volume": 8000},
            {"keyword": "keyword b", "composite_score": 90.0, "volume": 6000},
            {"keyword": "keyword c", "composite_score": 85.0, "volume": 5000},
            {"keyword": "keyword d", "composite_score": 80.0, "volume": 4000},
            {"keyword": "keyword e", "composite_score": 75.0, "volume": 3000},
            {"keyword": "keyword f", "composite_score": 70.0, "volume": 2000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # Primary should be "keyword a"
        assert result["primary"]["keyword"] == "keyword a"

        # Alternatives should not include "keyword c" (used)
        alternative_keywords = [alt["keyword"] for alt in result["alternatives"]]
        assert "keyword c" not in alternative_keywords
        assert alternative_keywords == ["keyword b", "keyword d", "keyword e", "keyword f"]


class TestDuplicatePreventionAllKeywordsUsed:
    """Tests for behavior when all top keywords are used."""

    def test_returns_none_primary_when_all_keywords_used(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that None is returned when all candidate keywords are already used."""
        # Mark all keywords as used
        primary_keyword_service.add_used_keyword("keyword 1")
        primary_keyword_service.add_used_keyword("keyword 2")
        primary_keyword_service.add_used_keyword("keyword 3")

        scored_keywords = [
            {"keyword": "keyword 1", "composite_score": 90.0, "volume": 5000},
            {"keyword": "keyword 2", "composite_score": 85.0, "volume": 4000},
            {"keyword": "keyword 3", "composite_score": 80.0, "volume": 3000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # Primary should be None
        assert result["primary"] is None
        # Alternatives should be empty
        assert result["alternatives"] == []
        # All keywords should still be in the all_keywords list
        assert len(result["all_keywords"]) == 3

    def test_returns_last_available_when_others_used(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test selecting the only remaining unused keyword."""
        # Mark all but the lowest-scoring keyword as used
        primary_keyword_service.add_used_keyword("high scorer")
        primary_keyword_service.add_used_keyword("mid scorer")

        scored_keywords = [
            {"keyword": "high scorer", "composite_score": 95.0, "volume": 8000},
            {"keyword": "mid scorer", "composite_score": 85.0, "volume": 5000},
            {"keyword": "low scorer", "composite_score": 50.0, "volume": 500},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # Should select the only available keyword
        assert result["primary"] is not None
        assert result["primary"]["keyword"] == "low scorer"
        assert result["primary"]["composite_score"] == 50.0
        # No alternatives available
        assert result["alternatives"] == []

    def test_empty_keywords_list_returns_none(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that empty keyword list returns None primary."""
        result = primary_keyword_service.select_primary_and_alternatives([])

        assert result["primary"] is None
        assert result["alternatives"] == []
        assert result["all_keywords"] == []


class TestDuplicatePreventionUsedPrimariesSetUpdated:
    """Tests for verifying used_primaries set is updated correctly."""

    def test_selected_primary_is_added_to_used_set(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that the selected primary keyword is added to used_primaries."""
        # Verify set is empty initially
        assert len(primary_keyword_service.used_primary_keywords) == 0

        scored_keywords = [
            {"keyword": "selected keyword", "composite_score": 90.0, "volume": 5000},
            {"keyword": "alternative", "composite_score": 80.0, "volume": 4000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # The selected primary should be in used set
        assert result["primary"]["keyword"] == "selected keyword"
        assert primary_keyword_service.is_keyword_used("selected keyword") is True
        assert len(primary_keyword_service.used_primary_keywords) == 1

    def test_alternatives_are_not_added_to_used_set(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that alternative keywords are NOT added to used_primaries set."""
        scored_keywords = [
            {"keyword": "primary", "composite_score": 95.0, "volume": 8000},
            {"keyword": "alt1", "composite_score": 85.0, "volume": 5000},
            {"keyword": "alt2", "composite_score": 80.0, "volume": 4000},
            {"keyword": "alt3", "composite_score": 75.0, "volume": 3000},
            {"keyword": "alt4", "composite_score": 70.0, "volume": 2000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # Verify primary was selected
        assert result["primary"]["keyword"] == "primary"

        # Only primary should be in used set
        assert len(primary_keyword_service.used_primary_keywords) == 1
        assert primary_keyword_service.is_keyword_used("primary") is True

        # Alternatives should NOT be in used set
        assert primary_keyword_service.is_keyword_used("alt1") is False
        assert primary_keyword_service.is_keyword_used("alt2") is False
        assert primary_keyword_service.is_keyword_used("alt3") is False
        assert primary_keyword_service.is_keyword_used("alt4") is False

    def test_used_set_accumulates_across_calls(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that used_primaries set accumulates across multiple calls."""
        # First call - select "keyword a"
        keywords_1 = [
            {"keyword": "keyword a", "composite_score": 90.0, "volume": 5000},
            {"keyword": "keyword b", "composite_score": 85.0, "volume": 4000},
        ]
        result_1 = primary_keyword_service.select_primary_and_alternatives(keywords_1)
        assert result_1["primary"]["keyword"] == "keyword a"

        # Second call - "keyword a" should be skipped, "keyword c" selected
        keywords_2 = [
            {"keyword": "keyword a", "composite_score": 95.0, "volume": 8000},
            {"keyword": "keyword c", "composite_score": 85.0, "volume": 4000},
        ]
        result_2 = primary_keyword_service.select_primary_and_alternatives(keywords_2)
        assert result_2["primary"]["keyword"] == "keyword c"

        # Third call - both "keyword a" and "keyword c" should be skipped
        keywords_3 = [
            {"keyword": "keyword a", "composite_score": 95.0, "volume": 8000},
            {"keyword": "keyword c", "composite_score": 90.0, "volume": 6000},
            {"keyword": "keyword d", "composite_score": 80.0, "volume": 3000},
        ]
        result_3 = primary_keyword_service.select_primary_and_alternatives(keywords_3)
        assert result_3["primary"]["keyword"] == "keyword d"

        # Used set should have 3 keywords
        assert len(primary_keyword_service.used_primary_keywords) == 3
        assert primary_keyword_service.is_keyword_used("keyword a") is True
        assert primary_keyword_service.is_keyword_used("keyword c") is True
        assert primary_keyword_service.is_keyword_used("keyword d") is True

    def test_no_primary_selected_does_not_modify_used_set(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that used_primaries set is not modified when no primary can be selected."""
        # Pre-add a keyword to track count
        primary_keyword_service.add_used_keyword("existing keyword")
        initial_count = len(primary_keyword_service.used_primary_keywords)

        # All candidates are already used
        primary_keyword_service.add_used_keyword("candidate 1")
        primary_keyword_service.add_used_keyword("candidate 2")

        scored_keywords = [
            {"keyword": "candidate 1", "composite_score": 90.0, "volume": 5000},
            {"keyword": "candidate 2", "composite_score": 85.0, "volume": 4000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords
        )

        # No primary selected
        assert result["primary"] is None

        # Set should only have the existing + 2 candidates we marked
        # (no new additions from this call since no primary could be selected)
        expected_count = initial_count + 2
        assert len(primary_keyword_service.used_primary_keywords) == expected_count

    def test_custom_used_primaries_set_is_respected(
        self,
        primary_keyword_service: PrimaryKeywordService,
    ) -> None:
        """Test that a custom used_primaries set passed to the method is respected."""
        # Instance's used set is empty
        assert len(primary_keyword_service.used_primary_keywords) == 0

        # Pass a custom used set
        custom_used = {"best keyword", "second best"}

        scored_keywords = [
            {"keyword": "best keyword", "composite_score": 95.0, "volume": 8000},
            {"keyword": "second best", "composite_score": 90.0, "volume": 6000},
            {"keyword": "third best", "composite_score": 85.0, "volume": 4000},
        ]

        result = primary_keyword_service.select_primary_and_alternatives(
            scored_keywords, used_primaries=custom_used
        )

        # Should skip keywords in custom set
        assert result["primary"]["keyword"] == "third best"

        # Instance's used set should now have "third best" added
        assert primary_keyword_service.is_keyword_used("third best") is True
        # The custom set keywords are NOT in instance's set (they were only in custom set)
        assert "best keyword" not in primary_keyword_service.used_primary_keywords
        assert "second best" not in primary_keyword_service.used_primary_keywords
