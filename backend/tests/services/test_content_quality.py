"""Tests for content quality checks service.

Tests cover each trope rule with positive (detected) and negative (passes) cases:
1. banned_word: detects banned words from brand config
2. em_dash: detects em dash character
3. ai_pattern: detects AI opener phrases
4. triplet_excess: flags >2 'X, Y, and Z' patterns
5. rhetorical_excess: flags >1 rhetorical question outside FAQ
Plus: structured result format validation
"""

from typing import Any

import pytest

from app.services.content_quality import (
    QualityIssue,
    QualityResult,
    _check_ai_openers,
    _check_banned_words,
    _check_em_dashes,
    _check_negation_contrast,
    _check_rhetorical_questions,
    _check_tier1_ai_words,
    _check_tier2_ai_words,
    _check_triplet_lists,
    _strip_faq_section,
    run_quality_checks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakePageContent:
    """Stand-in for PageContent to avoid SQLAlchemy session pollution.

    Creating real PageContent() instances in pure function tests registers
    them in the SQLAlchemy identity map. This pollutes the shared in-memory
    SQLite connection and breaks subsequent async tests that use db_session.
    """

    def __init__(self, **kwargs: Any) -> None:
        self.page_title: str | None = kwargs.get("page_title")
        self.meta_description: str | None = kwargs.get("meta_description")
        self.top_description: str | None = kwargs.get("top_description")
        self.bottom_description: str | None = kwargs.get("bottom_description")
        self.qa_results: dict[str, Any] | None = None


def _make_page_content(**kwargs: Any) -> Any:
    """Create a fake PageContent-like object with given fields."""
    return _FakePageContent(**kwargs)


# ---------------------------------------------------------------------------
# Check 1: Banned Words
# ---------------------------------------------------------------------------


class TestCheckBannedWords:
    """Tests for banned word detection."""

    def test_detects_banned_word(self) -> None:
        """Positive: banned word is detected in content."""
        fields = {"bottom_description": "This product is really cheap and affordable."}
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["cheap"]}}

        issues = _check_banned_words(fields, brand_config)
        assert len(issues) == 1
        assert issues[0].type == "banned_word"
        assert issues[0].field == "bottom_description"
        assert "cheap" in issues[0].description.lower()

    def test_passes_without_banned_words(self) -> None:
        """Negative: no banned words in content."""
        fields = {"bottom_description": "This product is affordable and well-made."}
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["cheap", "guarantee"]}}

        issues = _check_banned_words(fields, brand_config)
        assert len(issues) == 0

    def test_word_boundary_matching(self) -> None:
        """Banned word 'best' should not match 'bestseller'."""
        fields = {"page_title": "Our Bestseller Collection"}
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["best"]}}

        issues = _check_banned_words(fields, brand_config)
        # "best" does not appear as a standalone word in "bestseller"
        # But "best" appears as a word boundary match at the start of "bestseller"
        # Actually \bbest\b should NOT match "bestseller" since there's no word boundary after "best" in "bestseller"
        # Wait - \bbest\b: 'b' in "bestseller" has a word boundary before it, and after "best" there's "seller"
        # So \bbest\b would NOT match "bestseller" because there's no \b between t and s
        assert len(issues) == 0

    def test_case_insensitive(self) -> None:
        """Banned word detection is case-insensitive."""
        fields = {"page_title": "The BEST Running Shoes"}
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["best"]}}

        issues = _check_banned_words(fields, brand_config)
        assert len(issues) == 1

    def test_empty_banned_words_list(self) -> None:
        """Empty banned words list produces no issues."""
        fields = {"page_title": "Anything goes"}
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": []}}

        issues = _check_banned_words(fields, brand_config)
        assert len(issues) == 0

    def test_missing_vocabulary_key(self) -> None:
        """Missing vocabulary key produces no issues."""
        fields = {"page_title": "Content"}
        issues = _check_banned_words(fields, {})
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Check 2: Em Dashes
# ---------------------------------------------------------------------------


class TestCheckEmDashes:
    """Tests for em dash detection."""

    def test_detects_em_dash(self) -> None:
        """Positive: em dash character is detected."""
        fields = {"bottom_description": "Great quality—built to last."}

        issues = _check_em_dashes(fields)
        assert len(issues) == 1
        assert issues[0].type == "em_dash"
        assert issues[0].field == "bottom_description"

    def test_passes_without_em_dash(self) -> None:
        """Negative: content without em dashes passes."""
        fields = {"bottom_description": "Great quality - built to last."}

        issues = _check_em_dashes(fields)
        assert len(issues) == 0

    def test_en_dash_not_flagged(self) -> None:
        """En dash (–) should not be flagged as em dash."""
        fields = {"bottom_description": "Pages 10–20 describe the product."}

        issues = _check_em_dashes(fields)
        assert len(issues) == 0

    def test_multiple_em_dashes_multiple_issues(self) -> None:
        """Multiple em dashes produce multiple issues."""
        fields = {"bottom_description": "Quality—durability—comfort—style."}

        issues = _check_em_dashes(fields)
        assert len(issues) == 3


# ---------------------------------------------------------------------------
# Check 3: AI Opener Patterns
# ---------------------------------------------------------------------------


class TestCheckAiOpeners:
    """Tests for AI opener pattern detection."""

    def test_detects_in_todays(self) -> None:
        """Positive: 'In today's' opener detected."""
        fields = {"top_description": "In today's market, you need quality shoes."}

        issues = _check_ai_openers(fields)
        assert len(issues) == 1
        assert issues[0].type == "ai_pattern"

    def test_detects_whether_youre(self) -> None:
        """Positive: 'Whether you're' opener detected."""
        fields = {"bottom_description": "Whether you're a runner or a hiker, we've got you covered."}

        issues = _check_ai_openers(fields)
        assert len(issues) == 1

    def test_detects_look_no_further(self) -> None:
        """Positive: 'Look no further' opener detected."""
        fields = {"top_description": "Look no further for the best winter boots."}

        issues = _check_ai_openers(fields)
        assert len(issues) == 1

    def test_detects_in_the_world_of(self) -> None:
        """Positive: 'In the world of' opener detected."""
        fields = {"bottom_description": "In the world of outdoor footwear, quality matters."}

        issues = _check_ai_openers(fields)
        assert len(issues) == 1

    def test_detects_when_it_comes_to(self) -> None:
        """Positive: 'When it comes to' opener detected."""
        fields = {"bottom_description": "When it comes to winter boots, insulation is key."}

        issues = _check_ai_openers(fields)
        assert len(issues) == 1

    def test_passes_clean_content(self) -> None:
        """Negative: content without AI openers passes."""
        fields = {
            "top_description": "Our winter boots are built for the harshest conditions.",
            "bottom_description": "Featuring waterproof membranes and insulated linings.",
        }

        issues = _check_ai_openers(fields)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Check 4: Triplet Lists
# ---------------------------------------------------------------------------


class TestCheckTripletLists:
    """Tests for excessive triplet list detection."""

    def test_detects_excessive_triplets(self) -> None:
        """Positive: >2 triplet patterns flagged."""
        fields = {
            "bottom_description": (
                "Our boots offer warmth, comfort, and durability. "
                "Available in black, brown, and gray. "
                "Perfect for snow, ice, and rain."
            )
        }

        issues = _check_triplet_lists(fields)
        assert len(issues) == 1
        assert issues[0].type == "triplet_excess"
        assert "3 instances" in issues[0].description

    def test_passes_two_or_fewer_triplets(self) -> None:
        """Negative: exactly 2 triplet patterns is acceptable."""
        fields = {
            "bottom_description": (
                "Our boots offer warmth, comfort, and durability. "
                "Available in black, brown, and gray."
            )
        }

        issues = _check_triplet_lists(fields)
        assert len(issues) == 0

    def test_passes_no_triplets(self) -> None:
        """Negative: content without triplet patterns passes."""
        fields = {"bottom_description": "Our boots are warm and comfortable."}

        issues = _check_triplet_lists(fields)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Check 5: Rhetorical Questions
# ---------------------------------------------------------------------------


class TestCheckRhetoricalQuestions:
    """Tests for excessive rhetorical question detection."""

    def test_detects_excessive_questions(self) -> None:
        """Positive: >1 rhetorical question outside FAQ flagged."""
        fields = {
            "bottom_description": (
                "Looking for warm boots? Want something durable? "
                "Our collection has you covered."
            )
        }

        issues = _check_rhetorical_questions(fields)
        assert len(issues) == 1
        assert issues[0].type == "rhetorical_excess"
        assert "2 found" in issues[0].description

    def test_passes_single_question(self) -> None:
        """Negative: exactly 1 rhetorical question is acceptable."""
        fields = {
            "bottom_description": "Looking for warm boots? Our collection has you covered."
        }

        issues = _check_rhetorical_questions(fields)
        assert len(issues) == 0

    def test_faq_questions_excluded(self) -> None:
        """Questions inside FAQ section are not counted."""
        fields = {
            "bottom_description": (
                "Our boots are top quality. "
                "<h2>FAQ</h2>"
                "<p>What sizes are available? We carry sizes 6-14.</p>"
                "<p>Are they waterproof? Yes, all boots are waterproof.</p>"
            )
        }

        issues = _check_rhetorical_questions(fields)
        assert len(issues) == 0

    def test_passes_no_questions(self) -> None:
        """Negative: no questions at all passes."""
        fields = {"bottom_description": "Our boots are warm and durable."}

        issues = _check_rhetorical_questions(fields)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Check 6: Tier 1 AI Words
# ---------------------------------------------------------------------------


class TestCheckTier1AiWords:
    """Tests for Tier 1 AI word detection."""

    def test_detects_tier1_word(self) -> None:
        """Positive: Tier 1 AI word 'delve' is detected."""
        fields = {"bottom_description": "Let's delve into the details of these boots."}

        issues = _check_tier1_ai_words(fields)
        assert len(issues) == 1
        assert issues[0].type == "tier1_ai_word"
        assert "delve" in issues[0].description.lower()

    def test_passes_without_tier1_words(self) -> None:
        """Negative: clean content without Tier 1 words passes."""
        fields = {"bottom_description": "These boots are warm and waterproof."}

        issues = _check_tier1_ai_words(fields)
        assert len(issues) == 0

    def test_detects_multiple_tier1_words(self) -> None:
        """Multiple Tier 1 words produce multiple issues."""
        fields = {"bottom_description": "Unlock the crucial path to better footwear."}

        issues = _check_tier1_ai_words(fields)
        assert len(issues) == 2
        words_found = {i.description for i in issues}
        assert any("unlock" in d.lower() for d in words_found)
        assert any("crucial" in d.lower() for d in words_found)

    def test_case_insensitive(self) -> None:
        """Tier 1 detection is case-insensitive."""
        fields = {"page_title": "UNLEASH Your Potential"}

        issues = _check_tier1_ai_words(fields)
        assert len(issues) == 1
        assert "unleash" in issues[0].description.lower()

    def test_detects_multi_word_phrases(self) -> None:
        """Multi-word Tier 1 phrases like 'tap into' are detected."""
        fields = {"bottom_description": "Tap into the power of quality boots."}

        issues = _check_tier1_ai_words(fields)
        assert len(issues) >= 1
        assert any("tap into" in i.description.lower() for i in issues)


# ---------------------------------------------------------------------------
# Check 7: Tier 2 AI Words
# ---------------------------------------------------------------------------


class TestCheckTier2AiWords:
    """Tests for Tier 2 AI word excess detection."""

    def test_detects_excess_tier2_words(self) -> None:
        """Positive: 2+ Tier 2 words flagged."""
        fields = {"bottom_description": "Our robust and seamless collection enhances your wardrobe."}

        issues = _check_tier2_ai_words(fields)
        assert len(issues) == 1
        assert issues[0].type == "tier2_ai_excess"
        assert "robust" in issues[0].context.lower()
        assert "seamless" in issues[0].context.lower()

    def test_passes_single_tier2_word(self) -> None:
        """Negative: exactly 1 Tier 2 word is acceptable."""
        fields = {"bottom_description": "Our seamless checkout makes ordering easy."}

        issues = _check_tier2_ai_words(fields)
        assert len(issues) == 0

    def test_passes_no_tier2_words(self) -> None:
        """Negative: no Tier 2 words passes."""
        fields = {"bottom_description": "These boots are warm and waterproof."}

        issues = _check_tier2_ai_words(fields)
        assert len(issues) == 0

    def test_counts_across_fields(self) -> None:
        """Tier 2 words counted across all content fields."""
        fields = {
            "page_title": "Curated Winter Boots",
            "bottom_description": "Our comprehensive collection.",
        }

        issues = _check_tier2_ai_words(fields)
        assert len(issues) == 1
        assert issues[0].type == "tier2_ai_excess"


# ---------------------------------------------------------------------------
# Check 8: Negation/Contrast Pattern
# ---------------------------------------------------------------------------


class TestCheckNegationContrast:
    """Tests for negation/contrast pattern detection."""

    def test_detects_excess_negation(self) -> None:
        """Positive: 2+ negation patterns flagged."""
        fields = {
            "bottom_description": (
                "It's not just a boot, it's a statement. "
                "It's not about price, it's about value."
            )
        }

        issues = _check_negation_contrast(fields)
        assert len(issues) == 1
        assert issues[0].type == "negation_contrast"
        assert "2 found" in issues[0].description

    def test_passes_single_negation(self) -> None:
        """Negative: exactly 1 negation pattern is acceptable."""
        fields = {
            "bottom_description": "It's not just a boot, it's a statement. Great quality materials."
        }

        issues = _check_negation_contrast(fields)
        assert len(issues) == 0

    def test_passes_no_negation(self) -> None:
        """Negative: no negation patterns passes."""
        fields = {"bottom_description": "These boots are warm and durable."}

        issues = _check_negation_contrast(fields)
        assert len(issues) == 0

    def test_detects_contracted_form(self) -> None:
        """Detects both 'It's' and 'Its' forms (though 'Its' is grammatically different)."""
        fields = {
            "bottom_description": (
                "It's not just style, it's substance. "
                "Its not only warm, its also waterproof."
            )
        }

        issues = _check_negation_contrast(fields)
        assert len(issues) == 1  # 2 matches → flagged


class TestStripFaqSection:
    """Tests for FAQ section stripping."""

    def test_strips_faq_section(self) -> None:
        html = "Content before<h2>FAQ</h2><p>Question? Answer.</p>"
        result = _strip_faq_section(html)
        assert result == "Content before"

    def test_strips_frequently_asked_questions(self) -> None:
        html = "Before<h2>Frequently Asked Questions</h2><p>Q? A.</p>"
        result = _strip_faq_section(html)
        assert result == "Before"

    def test_no_faq_returns_unchanged(self) -> None:
        html = "<h2>About Us</h2><p>We sell boots.</p>"
        result = _strip_faq_section(html)
        assert result == html

    def test_case_insensitive(self) -> None:
        html = "Before<h3>faq</h3><p>Q? A.</p>"
        result = _strip_faq_section(html)
        assert result == "Before"


# ---------------------------------------------------------------------------
# Structured Result Format
# ---------------------------------------------------------------------------


class TestRunQualityChecks:
    """Tests for run_quality_checks orchestration and result format."""

    def test_passes_clean_content(self) -> None:
        """Clean content returns passed=True with no issues."""
        pc = _make_page_content(
            page_title="Winter Boots",
            meta_description="Shop winter boots online.",
            top_description="Browse our winter boots collection.",
            bottom_description="<h2>Quality Materials</h2><p>Built to last.</p>",
        )
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["cheap"]}}

        result = run_quality_checks(pc, brand_config)

        assert isinstance(result, QualityResult)
        assert result.passed is True
        assert len(result.issues) == 0
        assert result.checked_at != ""

    def test_fails_with_issues(self) -> None:
        """Content with problems returns passed=False and issues list."""
        pc = _make_page_content(
            page_title="The Best Winter Boots",
            meta_description="cheap boots",
            top_description="In today's market, everyone needs boots.",
            bottom_description="Quality—guaranteed.",
        )
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["cheap"]}}

        result = run_quality_checks(pc, brand_config)

        assert result.passed is False
        assert len(result.issues) > 0

        # Should detect: banned_word (cheap), em_dash, ai_pattern (In today's)
        issue_types = {issue.type for issue in result.issues}
        assert "banned_word" in issue_types
        assert "em_dash" in issue_types
        assert "ai_pattern" in issue_types

    def test_result_stored_in_qa_results(self) -> None:
        """Result is stored in PageContent.qa_results JSONB field."""
        pc = _make_page_content(
            page_title="Simple Title",
            bottom_description="Simple content.",
        )
        brand_config: dict[str, Any] = {}

        run_quality_checks(pc, brand_config)

        assert pc.qa_results is not None
        assert "passed" in pc.qa_results
        assert "issues" in pc.qa_results
        assert "checked_at" in pc.qa_results

    def test_result_to_dict_format(self) -> None:
        """QualityResult.to_dict() returns correct structure."""
        result = QualityResult(
            passed=False,
            issues=[
                QualityIssue(
                    type="banned_word",
                    field="page_title",
                    description='Banned word "cheap" detected',
                    context="...cheap boots...",
                ),
            ],
            checked_at="2026-02-06T12:00:00+00:00",
        )

        d = result.to_dict()
        assert d["passed"] is False
        assert len(d["issues"]) == 1
        assert d["issues"][0]["type"] == "banned_word"
        assert d["issues"][0]["field"] == "page_title"
        assert d["checked_at"] == "2026-02-06T12:00:00+00:00"

    def test_handles_none_fields(self) -> None:
        """Content with None fields is handled gracefully."""
        pc = _make_page_content(
            page_title=None,
            meta_description=None,
            top_description=None,
            bottom_description=None,
        )
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["test"]}}

        result = run_quality_checks(pc, brand_config)

        # Should pass since there's nothing to check
        assert result.passed is True
        assert len(result.issues) == 0
