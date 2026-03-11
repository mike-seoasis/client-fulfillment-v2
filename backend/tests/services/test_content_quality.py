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
    _check_bible_banned_claims,
    _check_bible_preferred_terms,
    _check_bible_term_context,
    _check_bible_wrong_attribution,
    _check_business_jargon,
    _check_em_dashes,
    _check_empty_signposts,
    _check_missing_direct_answer,
    _check_negation_contrast,
    _check_rhetorical_questions,
    _check_tier1_ai_words,
    _check_tier2_ai_words,
    _check_tier3_phrases,
    _check_triplet_lists,
    _split_sentences,
    _strip_faq_section,
    _word_boundary_pattern,
    run_blog_quality_checks,
    run_quality_checks,
)
from app.services.content_generation import _match_bibles_for_keyword


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


class _FakeBible:
    """Stand-in for VerticalBible to avoid importing the model."""

    def __init__(
        self,
        name: str = "Test Bible",
        qa_rules: dict[str, Any] | None = None,
        content_md: str = "",
        sort_order: int = 0,
        trigger_keywords: list[str] | None = None,
    ) -> None:
        self.name = name
        self.qa_rules = qa_rules or {}
        self.content_md = content_md
        self.sort_order = sort_order
        self.trigger_keywords = trigger_keywords or []


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
        """Positive: >2 triplet patterns flagged (one issue per match)."""
        fields = {
            "bottom_description": (
                "Our boots offer warmth, comfort, and durability. "
                "Available in black, brown, and gray. "
                "Perfect for snow, ice, and rain."
            )
        }

        issues = _check_triplet_lists(fields)
        assert len(issues) == 3  # One issue per match
        assert issues[0].type == "triplet_excess"
        assert "3 total" in issues[0].description

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
        """Positive: >1 rhetorical question outside FAQ flagged (one issue per match)."""
        fields = {
            "bottom_description": (
                "Looking for warm boots? Want something durable? "
                "Our collection has you covered."
            )
        }

        issues = _check_rhetorical_questions(fields)
        assert len(issues) == 2  # One issue per match
        assert issues[0].type == "rhetorical_excess"
        assert "2 total" in issues[0].description

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
        """Positive: 2+ Tier 2 words flagged (one issue per word found)."""
        fields = {"bottom_description": "Our robust and seamless collection."}

        issues = _check_tier2_ai_words(fields)
        assert len(issues) == 2  # One issue per distinct Tier 2 word found
        assert issues[0].type == "tier2_ai_excess"
        words_in_descriptions = " ".join(i.description.lower() for i in issues)
        assert "robust" in words_in_descriptions
        assert "seamless" in words_in_descriptions

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
        """Tier 2 words counted across all content fields (one issue per word)."""
        fields = {
            "page_title": "Curated Winter Boots",
            "bottom_description": "Our comprehensive collection.",
        }

        issues = _check_tier2_ai_words(fields)
        assert len(issues) == 2  # One per distinct word found across fields
        assert issues[0].type == "tier2_ai_excess"


# ---------------------------------------------------------------------------
# Check 8: Negation/Contrast Pattern
# ---------------------------------------------------------------------------


class TestCheckNegationContrast:
    """Tests for negation/contrast pattern detection."""

    def test_detects_excess_negation(self) -> None:
        """Positive: 2+ negation patterns flagged (one issue per match)."""
        fields = {
            "bottom_description": (
                "It's not just a boot, it's a statement. "
                "It's not about price, it's about value."
            )
        }

        issues = _check_negation_contrast(fields)
        assert len(issues) == 2  # One issue per match
        assert issues[0].type == "negation_contrast"
        assert "2 total" in issues[0].description

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
        assert len(issues) == 2  # 2 matches → one issue per match


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


# ---------------------------------------------------------------------------
# Check 10: Tier 3 Banned Phrases
# ---------------------------------------------------------------------------


class TestCheckTier3Phrases:
    """Tests for Tier 3 banned phrase detection (opening, filler, closing, hype)."""

    def test_detects_opening_phrase(self) -> None:
        """Detects Tier 3 opening phrase."""
        fields = {"content": "In today's fast-paced world, boots matter."}
        issues = _check_tier3_phrases(fields)
        assert len(issues) == 1
        assert issues[0].type == "tier3_banned_phrase"

    def test_detects_filler_phrase(self) -> None:
        """Detects Tier 3 filler phrase."""
        fields = {"content": "It's important to note that leather is durable."}
        issues = _check_tier3_phrases(fields)
        assert len(issues) == 1
        assert issues[0].type == "tier3_banned_phrase"

    def test_detects_closing_phrase(self) -> None:
        """Detects Tier 3 closing phrase."""
        fields = {"content": "In conclusion, choose quality boots."}
        issues = _check_tier3_phrases(fields)
        assert len(issues) == 1
        assert issues[0].type == "tier3_banned_phrase"

    def test_detects_hype_phrase(self) -> None:
        """Detects Tier 3 hype phrase."""
        fields = {"content": "These boots unlock the potential of your wardrobe."}
        issues = _check_tier3_phrases(fields)
        assert len(issues) == 1
        assert issues[0].type == "tier3_banned_phrase"

    def test_passes_clean_content(self) -> None:
        """Clean content without Tier 3 phrases passes."""
        fields = {"content": "Our leather boots are built for comfort and warmth."}
        issues = _check_tier3_phrases(fields)
        assert len(issues) == 0

    def test_case_insensitive(self) -> None:
        """Tier 3 detection is case-insensitive."""
        fields = {"content": "LET'S DIVE IN to the world of boots."}
        issues = _check_tier3_phrases(fields)
        assert len(issues) == 1


# ---------------------------------------------------------------------------
# Check 11: Empty Signposts
# ---------------------------------------------------------------------------


class TestCheckEmptySignposts:
    """Tests for empty transition signpost detection."""

    def test_detects_signpost(self) -> None:
        """Detects empty signpost phrases."""
        fields = {"content": "Now, let's look at the sole construction."}
        issues = _check_empty_signposts(fields)
        assert len(issues) == 1
        assert issues[0].type == "empty_signpost"

    def test_detects_that_said(self) -> None:
        """Detects 'That said' signpost."""
        fields = {"content": "That said, you should consider fit first."}
        issues = _check_empty_signposts(fields)
        assert len(issues) == 1

    def test_passes_clean_content(self) -> None:
        """Clean content without signposts passes."""
        fields = {"content": "The sole is made from Vibram rubber."}
        issues = _check_empty_signposts(fields)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Check 12: Missing Direct Answer
# ---------------------------------------------------------------------------


class TestCheckMissingDirectAnswer:
    """Tests for missing direct answer check on blog content."""

    def test_flags_question_opener(self) -> None:
        """Flags content that opens with a question."""
        fields = {"content": "Have you ever wondered about boot care? Here's what you need to know."}
        issues = _check_missing_direct_answer(fields)
        assert len(issues) == 1
        assert issues[0].type == "missing_direct_answer"
        assert "question" in issues[0].description.lower()

    def test_flags_ai_opener(self) -> None:
        """Flags content that opens with AI pattern instead of direct answer."""
        fields = {"content": "In today's market, boot care is more important than ever."}
        issues = _check_missing_direct_answer(fields)
        assert len(issues) == 1
        assert issues[0].type == "missing_direct_answer"

    def test_passes_direct_answer(self) -> None:
        """Content that opens with a direct statement passes."""
        fields = {"content": "Leather boots last 10+ years with proper care. Here is how to maintain them."}
        issues = _check_missing_direct_answer(fields)
        assert len(issues) == 0

    def test_handles_html_content(self) -> None:
        """Strips HTML tags before checking."""
        fields = {"content": "<h2>Boot Care</h2><p>Leather boots need regular conditioning to stay supple.</p>"}
        issues = _check_missing_direct_answer(fields)
        assert len(issues) == 0

    def test_skips_empty_content(self) -> None:
        """No issues when content field is empty."""
        fields = {"content": ""}
        issues = _check_missing_direct_answer(fields)
        assert len(issues) == 0

    def test_skips_missing_content(self) -> None:
        """No issues when content key is missing."""
        fields = {"title": "Some Title"}
        issues = _check_missing_direct_answer(fields)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Check 13: Business Jargon
# ---------------------------------------------------------------------------


class TestCheckBusinessJargon:
    """Tests for business jargon detection."""

    def test_detects_jargon_word(self) -> None:
        """Detects business jargon word."""
        fields = {"content": "Our synergy-driven approach to boot design sets us apart."}
        issues = _check_business_jargon(fields)
        assert len(issues) == 1
        assert issues[0].type == "business_jargon"
        assert "synergy" in issues[0].description.lower()

    def test_detects_multi_word_jargon(self) -> None:
        """Detects multi-word business jargon like 'paradigm shift'."""
        fields = {"content": "This represents a paradigm shift in footwear technology."}
        issues = _check_business_jargon(fields)
        assert len(issues) == 1
        assert "paradigm shift" in issues[0].description.lower()

    def test_passes_clean_content(self) -> None:
        """Clean content without jargon passes."""
        fields = {"content": "Our boots are made with quality leather and strong stitching."}
        issues = _check_business_jargon(fields)
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# run_blog_quality_checks (combined: 13 checks)
# ---------------------------------------------------------------------------


class TestRunBlogQualityChecks:
    """Tests for run_blog_quality_checks with all 13 checks."""

    def test_passes_clean_content(self) -> None:
        """Clean content passes all 13 checks."""
        fields = {
            "title": "Winter Boots Guide",
            "content": "Leather boots last years with proper care. Regular conditioning keeps them supple.",
        }
        result = run_blog_quality_checks(fields, {})
        assert result.passed is True
        assert len(result.issues) == 0

    def test_catches_tier3_and_standard(self) -> None:
        """Catches both standard (em dash) and blog-specific (tier3) issues."""
        fields = {
            "content": "In conclusion, these boots are great\u2014quality matters.",
        }
        result = run_blog_quality_checks(fields, {})
        assert result.passed is False
        types = {i.type for i in result.issues}
        assert "tier3_banned_phrase" in types
        assert "em_dash" in types

    def test_includes_all_13_check_types(self) -> None:
        """Verifies all 13 checks run (each produces at least its type)."""
        # Content designed to trigger at least one issue from many checks
        fields = {
            "content": (
                "In today's fast-paced world, let's dive in. "
                "Now, let's look at synergy. "
                "It's crucial to utilize robust scalable tools\u2014"
                "indeed furthermore moreover. "
                "It's not just style, it's substance. "
                "It's not just X, it's Y. "
                "A, B, and C. D, E, and F. G, H, and I. "
                "Question? Another question? "
            ),
        }
        brand_config: dict[str, Any] = {"vocabulary": {"banned_words": ["tools"]}}
        result = run_blog_quality_checks(fields, brand_config)
        assert result.passed is False
        types = {i.type for i in result.issues}
        # Standard checks
        assert "banned_word" in types
        assert "em_dash" in types
        assert "ai_pattern" in types
        assert "tier1_ai_word" in types
        assert "tier2_ai_excess" in types
        # Blog-specific checks
        assert "tier3_banned_phrase" in types
        assert "empty_signpost" in types
        assert "business_jargon" in types


# ---------------------------------------------------------------------------
# _split_sentences helper
# ---------------------------------------------------------------------------


class TestSplitSentences:
    """Tests for the _split_sentences helper."""

    def test_splits_on_period(self) -> None:
        result = _split_sentences("First sentence. Second sentence.")
        assert len(result) == 2
        assert result[0] == "First sentence."
        assert result[1] == "Second sentence."

    def test_splits_on_exclamation_and_question(self) -> None:
        result = _split_sentences("Wow! Is that true? Yes.")
        assert len(result) == 3

    def test_strips_html(self) -> None:
        result = _split_sentences("<p>Hello world.</p> <p>Next one.</p>")
        assert len(result) == 2
        assert "<p>" not in result[0]

    def test_handles_empty_string(self) -> None:
        result = _split_sentences("")
        assert result == []


# ---------------------------------------------------------------------------
# Check 14: Bible Preferred Terms
# ---------------------------------------------------------------------------


class TestCheckBiblePreferredTerms:
    """Tests for bible preferred term detection."""

    def test_detects_deprecated_term(self) -> None:
        fields = {"bottom_description": "Our cartridge works great with any machine."}
        qa_rules = {
            "preferred_terms": [
                {"use": "needle cartridge", "instead_of": "cartridge"},
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Tattoo Bible")
        assert len(issues) == 1
        assert issues[0].type == "bible_preferred_term"
        assert "needle cartridge" in issues[0].description
        assert "Tattoo Bible" in issues[0].description

    def test_passes_when_preferred_term_used(self) -> None:
        fields = {"bottom_description": "Our needle cartridge works great."}
        qa_rules = {
            "preferred_terms": [
                {"use": "needle cartridge", "instead_of": "disposable tube"},
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Bible")
        assert len(issues) == 0

    def test_case_insensitive(self) -> None:
        fields = {"bottom_description": "Use our CARTRIDGE system."}
        qa_rules = {
            "preferred_terms": [
                {"use": "needle cartridge", "instead_of": "cartridge"},
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Bible")
        assert len(issues) == 1

    def test_word_boundary(self) -> None:
        fields = {"bottom_description": "The subcartridge unit is fine."}
        qa_rules = {
            "preferred_terms": [
                {"use": "needle cartridge", "instead_of": "cartridge"},
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Bible")
        # "cartridge" should not match inside "subcartridge"
        assert len(issues) == 0

    def test_empty_rules(self) -> None:
        fields = {"bottom_description": "Some content."}
        issues = _check_bible_preferred_terms(fields, {}, "Bible")
        assert len(issues) == 0

    def test_malformed_entry_skipped(self) -> None:
        fields = {"bottom_description": "Some content."}
        qa_rules = {"preferred_terms": [{"use": "x"}, "not a dict"]}
        issues = _check_bible_preferred_terms(fields, qa_rules, "Bible")
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Check 15: Bible Banned Claims
# ---------------------------------------------------------------------------


class TestCheckBibleBannedClaims:
    """Tests for bible banned claim detection."""

    def test_detects_claim_with_context_in_same_sentence(self) -> None:
        fields = {
            "bottom_description": "Our needles are FDA approved for tattoo use. Safe and reliable."
        }
        qa_rules = {
            "banned_claims": [
                {"claim": "FDA approved", "context": "needle", "reason": "Not FDA regulated"},
            ]
        }
        issues = _check_bible_banned_claims(fields, qa_rules, "Bible")
        assert len(issues) == 1
        assert issues[0].type == "bible_banned_claim"
        assert "FDA approved" in issues[0].description

    def test_no_flag_when_context_in_different_sentence(self) -> None:
        fields = {
            "bottom_description": "Our needles are top quality. This is FDA approved equipment."
        }
        qa_rules = {
            "banned_claims": [
                {"claim": "FDA approved", "context": "needle", "reason": "Not FDA regulated"},
            ]
        }
        issues = _check_bible_banned_claims(fields, qa_rules, "Bible")
        assert len(issues) == 0

    def test_flags_claim_without_context_anywhere(self) -> None:
        fields = {"bottom_description": "Our products are FDA approved."}
        qa_rules = {
            "banned_claims": [
                {"claim": "FDA approved", "context": "", "reason": "Never claim this"},
            ]
        }
        issues = _check_bible_banned_claims(fields, qa_rules, "Bible")
        assert len(issues) == 1

    def test_empty_claims(self) -> None:
        fields = {"bottom_description": "Content here."}
        issues = _check_bible_banned_claims(fields, {}, "Bible")
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Check 16: Bible Wrong Attribution
# ---------------------------------------------------------------------------


class TestCheckBibleWrongAttribution:
    """Tests for bible wrong attribution detection."""

    def test_detects_wrong_attribution(self) -> None:
        fields = {
            "bottom_description": "The motor drives the needle at high speed."
        }
        qa_rules = {
            "feature_attribution": [
                {
                    "feature": "drives the needle",
                    "correct_component": "cam mechanism",
                    "wrong_components": ["motor"],
                },
            ]
        }
        issues = _check_bible_wrong_attribution(fields, qa_rules, "Bible")
        assert len(issues) == 1
        assert issues[0].type == "bible_wrong_attribution"
        assert "cam mechanism" in issues[0].description
        assert "motor" in issues[0].description

    def test_passes_correct_attribution(self) -> None:
        fields = {
            "bottom_description": "The cam mechanism drives the needle smoothly."
        }
        qa_rules = {
            "feature_attribution": [
                {
                    "feature": "drives the needle",
                    "correct_component": "cam mechanism",
                    "wrong_components": ["motor"],
                },
            ]
        }
        issues = _check_bible_wrong_attribution(fields, qa_rules, "Bible")
        assert len(issues) == 0

    def test_different_sentences_no_flag(self) -> None:
        fields = {
            "bottom_description": "The motor is powerful. The cam drives the needle."
        }
        qa_rules = {
            "feature_attribution": [
                {
                    "feature": "drives the needle",
                    "correct_component": "cam mechanism",
                    "wrong_components": ["motor"],
                },
            ]
        }
        issues = _check_bible_wrong_attribution(fields, qa_rules, "Bible")
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# Check 17: Bible Term Context
# ---------------------------------------------------------------------------


class TestCheckBibleTermContext:
    """Tests for bible term context detection."""

    def test_detects_wrong_context(self) -> None:
        fields = {
            "bottom_description": "The voltage setting affects needle depth."
        }
        qa_rules = {
            "term_context_rules": [
                {
                    "term": "voltage",
                    "wrong_contexts": ["needle depth"],
                    "explanation": "Voltage controls motor speed, not depth",
                },
            ]
        }
        issues = _check_bible_term_context(fields, qa_rules, "Bible")
        assert len(issues) == 1
        assert issues[0].type == "bible_term_context"
        assert "voltage" in issues[0].description
        assert "needle depth" in issues[0].description

    def test_passes_correct_context(self) -> None:
        fields = {
            "bottom_description": "The voltage setting controls motor speed."
        }
        qa_rules = {
            "term_context_rules": [
                {
                    "term": "voltage",
                    "wrong_contexts": ["needle depth"],
                    "explanation": "Voltage controls motor speed, not depth",
                },
            ]
        }
        issues = _check_bible_term_context(fields, qa_rules, "Bible")
        assert len(issues) == 0

    def test_different_sentences_no_flag(self) -> None:
        fields = {
            "bottom_description": "Adjust the voltage carefully. Needle depth depends on other factors."
        }
        qa_rules = {
            "term_context_rules": [
                {
                    "term": "voltage",
                    "wrong_contexts": ["needle depth"],
                    "explanation": "Voltage controls motor speed, not depth",
                },
            ]
        }
        issues = _check_bible_term_context(fields, qa_rules, "Bible")
        assert len(issues) == 0


# ---------------------------------------------------------------------------
# run_quality_checks with bibles
# ---------------------------------------------------------------------------


class TestRunQualityChecksWithBibles:
    """Tests for run_quality_checks with matched_bibles parameter."""

    def test_backward_compatible_without_bibles(self) -> None:
        """Calling with 2 args still works (no bibles)."""
        pc = _make_page_content(
            page_title="Simple Title",
            bottom_description="Simple content.",
        )
        result = run_quality_checks(pc, {})
        assert result.passed is True
        assert result.bibles_matched == []
        # to_dict should NOT include bibles_matched when empty
        d = result.to_dict()
        assert "bibles_matched" not in d

    def test_bible_check_failure_causes_fail(self) -> None:
        """Bible check failures cause result.passed=False."""
        pc = _make_page_content(
            page_title="Cartridge Title",
            bottom_description="Use our cartridge system for best results.",
        )
        bible = _FakeBible(
            name="Tattoo Bible",
            qa_rules={
                "preferred_terms": [
                    {"use": "needle cartridge", "instead_of": "cartridge"},
                ]
            },
        )
        result = run_quality_checks(pc, {}, matched_bibles=[bible])
        assert result.passed is False
        assert "Tattoo Bible" in result.bibles_matched
        assert any(i.type == "bible_preferred_term" for i in result.issues)
        # to_dict should include bibles_matched when non-empty
        d = result.to_dict()
        assert "bibles_matched" in d
        assert "Tattoo Bible" in d["bibles_matched"]

    def test_multiple_bibles_accumulate(self) -> None:
        """Issues from multiple bibles are accumulated."""
        pc = _make_page_content(
            bottom_description="Use our cartridge. The motor drives the needle.",
        )
        bible1 = _FakeBible(
            name="Bible A",
            qa_rules={
                "preferred_terms": [
                    {"use": "needle cartridge", "instead_of": "cartridge"},
                ]
            },
        )
        bible2 = _FakeBible(
            name="Bible B",
            qa_rules={
                "feature_attribution": [
                    {
                        "feature": "drives the needle",
                        "correct_component": "cam",
                        "wrong_components": ["motor"],
                    },
                ]
            },
        )
        result = run_quality_checks(pc, {}, matched_bibles=[bible1, bible2])
        assert result.passed is False
        assert len(result.bibles_matched) == 2
        types = {i.type for i in result.issues}
        assert "bible_preferred_term" in types
        assert "bible_wrong_attribution" in types


# ---------------------------------------------------------------------------
# run_blog_quality_checks with bibles
# ---------------------------------------------------------------------------


class TestRunBlogQualityChecksWithBibles:
    """Tests for run_blog_quality_checks with matched_bibles parameter."""

    def test_backward_compatible_without_bibles(self) -> None:
        """Calling with 2 args still works (no bibles)."""
        fields = {"content": "Simple clean content here."}
        result = run_blog_quality_checks(fields, {})
        assert result.passed is True
        assert result.bibles_matched == []

    def test_bible_issues_alongside_blog_checks(self) -> None:
        """Bible issues combine with blog-specific checks."""
        fields = {
            "content": "In conclusion, use our cartridge system.",
        }
        bible = _FakeBible(
            name="Tattoo Bible",
            qa_rules={
                "preferred_terms": [
                    {"use": "needle cartridge", "instead_of": "cartridge"},
                ]
            },
        )
        result = run_blog_quality_checks(fields, {}, matched_bibles=[bible])
        assert result.passed is False
        types = {i.type for i in result.issues}
        assert "tier3_banned_phrase" in types  # "In conclusion"
        assert "bible_preferred_term" in types
        assert "Tattoo Bible" in result.bibles_matched


# ---------------------------------------------------------------------------
# Adversarial review fixes: additional tests
# ---------------------------------------------------------------------------


class TestWordBoundaryPattern:
    """Tests for _word_boundary_pattern with special-character terms."""

    def test_plain_word(self) -> None:
        import re

        p = re.compile(_word_boundary_pattern("cartridge"), re.IGNORECASE)
        assert p.search("our cartridge works")
        assert not p.search("subcartridge unit")

    def test_term_with_plus(self) -> None:
        import re

        p = re.compile(_word_boundary_pattern("C++"), re.IGNORECASE)
        assert p.search("learn C++ today")
        assert not p.search("learn C today")

    def test_term_starting_with_dot(self) -> None:
        import re

        p = re.compile(_word_boundary_pattern(".NET"), re.IGNORECASE)
        assert p.search("use .NET framework")
        assert not p.search("use DOTNET framework")

    def test_term_with_dot_inside(self) -> None:
        import re

        p = re.compile(_word_boundary_pattern("Node.js"), re.IGNORECASE)
        assert p.search("use Node.js for backend")


class TestSplitSentencesAbbreviations:
    """Tests for _split_sentences handling abbreviations correctly."""

    def test_dr_abbreviation(self) -> None:
        result = _split_sentences("Dr. Smith recommends this. He is an expert.")
        assert len(result) == 2
        assert "Dr. Smith" in result[0]

    def test_eg_abbreviation(self) -> None:
        result = _split_sentences("Use tools, e.g. hammers. They work well.")
        assert len(result) == 2
        assert "e.g." in result[0]

    def test_inc_abbreviation(self) -> None:
        result = _split_sentences("Acme Inc. makes great products. Buy them now.")
        assert len(result) == 2
        assert "Inc." in result[0]

    def test_normal_sentences_still_split(self) -> None:
        result = _split_sentences("First sentence. Second sentence. Third one.")
        assert len(result) == 3


class TestCheckBiblePreferredTermsSpecialChars:
    """Tests for bible preferred terms with special regex characters."""

    def test_term_with_plus_signs(self) -> None:
        fields = {"bottom_description": "We recommend C++ for performance."}
        qa_rules = {
            "preferred_terms": [
                {"use": "Rust", "instead_of": "C++"},
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Lang Bible")
        assert len(issues) == 1
        assert "Rust" in issues[0].description

    def test_nonstring_instead_of_skipped(self) -> None:
        """Non-string instead_of values should be skipped, not crash."""
        fields = {"bottom_description": "Some content here."}
        qa_rules = {
            "preferred_terms": [
                {"use": "foo", "instead_of": 42},
            ]
        }
        issues = _check_bible_preferred_terms(fields, qa_rules, "Bible")
        assert len(issues) == 0


class TestCheckBibleBannedClaimsContextMatching:
    """Test context_word matching behavior in banned claims."""

    def test_context_matches_plural_form(self) -> None:
        """'needle' should match 'needles' (plural) in context matching."""
        fields = {
            "bottom_description": "Our needles are FDA approved for tattoo use."
        }
        qa_rules = {
            "banned_claims": [
                {"claim": "FDA approved", "context": "needle", "reason": "test"},
            ]
        }
        issues = _check_bible_banned_claims(fields, qa_rules, "Bible")
        assert len(issues) == 1

    def test_nonstring_claim_skipped(self) -> None:
        """Non-string claim values should be skipped, not crash."""
        fields = {"bottom_description": "Some content here."}
        qa_rules = {
            "banned_claims": [
                {"claim": 42, "context": "needle"},
            ]
        }
        issues = _check_bible_banned_claims(fields, qa_rules, "Bible")
        assert len(issues) == 0


class TestMatchBiblesForKeyword:
    """Tests for _match_bibles_for_keyword matching logic."""

    def test_basic_match(self) -> None:
        bible = _FakeBible(name="Ink Bible", trigger_keywords=["tattoo ink"])
        result = _match_bibles_for_keyword([bible], "best tattoo ink brands")
        assert len(result) == 1

    def test_no_match(self) -> None:
        bible = _FakeBible(name="Ink Bible", trigger_keywords=["tattoo ink"])
        result = _match_bibles_for_keyword([bible], "running shoes")
        assert len(result) == 0

    def test_short_trigger_skipped(self) -> None:
        """Triggers shorter than 3 chars should be skipped to prevent false matches."""
        bible = _FakeBible(name="Bad Bible", trigger_keywords=["a", "in"])
        result = _match_bibles_for_keyword([bible], "tattoo ink brands")
        assert len(result) == 0

    def test_empty_keyword_returns_empty(self) -> None:
        bible = _FakeBible(name="Bible", trigger_keywords=["tattoo"])
        result = _match_bibles_for_keyword([bible], "")
        assert len(result) == 0

    def test_bidirectional_match(self) -> None:
        """Keyword can also be substring of trigger."""
        bible = _FakeBible(name="Ink Bible", trigger_keywords=["tattoo ink supplies"])
        result = _match_bibles_for_keyword([bible], "ink")
        assert len(result) == 1

    def test_preserves_sort_order(self) -> None:
        bible_a = _FakeBible(name="A", trigger_keywords=["tattoo"], sort_order=2)
        bible_b = _FakeBible(name="B", trigger_keywords=["tattoo"], sort_order=1)
        result = _match_bibles_for_keyword([bible_a, bible_b], "tattoo needles")
        assert len(result) == 2
        assert result[0].name == "A"  # Order from input list preserved


class TestEmptyQaRulesBible:
    """Test that a bible with empty qa_rules is NOT added to bibles_matched."""

    def test_empty_qa_rules_not_in_matched(self) -> None:
        pc = _make_page_content(bottom_description="Clean content.")
        bible = _FakeBible(name="Empty Bible", qa_rules={})
        result = run_quality_checks(pc, {}, matched_bibles=[bible])
        assert result.passed is True
        assert "Empty Bible" not in result.bibles_matched

    def test_nonempty_qa_rules_in_matched(self) -> None:
        pc = _make_page_content(bottom_description="Clean content.")
        bible = _FakeBible(
            name="Real Bible",
            qa_rules={"preferred_terms": [{"use": "X", "instead_of": "nonexistent_term_xyz"}]},
        )
        result = run_quality_checks(pc, {}, matched_bibles=[bible])
        assert "Real Bible" in result.bibles_matched


class TestQualityResultToDictDirect:
    """Direct tests for QualityResult.to_dict() bibles_matched behavior."""

    def test_empty_bibles_matched_excluded(self) -> None:
        result = QualityResult(passed=True, bibles_matched=[])
        d = result.to_dict()
        assert "bibles_matched" not in d

    def test_nonempty_bibles_matched_included(self) -> None:
        result = QualityResult(passed=True, bibles_matched=["Bible A"])
        d = result.to_dict()
        assert d["bibles_matched"] == ["Bible A"]
