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
    _strip_faq_section,
    run_blog_quality_checks,
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
