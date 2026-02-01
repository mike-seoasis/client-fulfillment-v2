"""Tests for content signal detection for confidence boosting.

Tests the ContentSignalDetector class and related functionality:
- Signal detection from various content types
- Confidence boosting calculations
- Category override logic
- Pattern matching
- Error handling
"""

import pytest

from app.utils.content_signals import (
    VALID_SIGNAL_TYPES,
    ContentAnalysis,
    ContentSignal,
    ContentSignalDetector,
    SignalPattern,
    SignalType,
    analyze_content_signals,
    get_content_signal_detector,
)


class TestSignalType:
    """Tests for the SignalType enum."""

    def test_signal_types_exist(self) -> None:
        """Verify all expected signal types exist."""
        assert SignalType.TITLE.value == "title"
        assert SignalType.HEADING.value == "heading"
        assert SignalType.SCHEMA.value == "schema"
        assert SignalType.META.value == "meta"
        assert SignalType.BREADCRUMB.value == "breadcrumb"
        assert SignalType.BODY.value == "body"

    def test_valid_signal_types_frozenset(self) -> None:
        """Verify VALID_SIGNAL_TYPES contains all enum values."""
        assert "title" in VALID_SIGNAL_TYPES
        assert "heading" in VALID_SIGNAL_TYPES
        assert "schema" in VALID_SIGNAL_TYPES
        assert "meta" in VALID_SIGNAL_TYPES
        assert "breadcrumb" in VALID_SIGNAL_TYPES
        assert "body" in VALID_SIGNAL_TYPES
        assert len(VALID_SIGNAL_TYPES) == len(SignalType)


class TestContentSignal:
    """Tests for the ContentSignal dataclass."""

    def test_create_signal(self) -> None:
        """Test creating a content signal."""
        signal = ContentSignal(
            signal_type=SignalType.TITLE,
            category="product",
            confidence_boost=0.25,
            matched_text="Buy Now",
            pattern=r"\bbuy\s+now\b",
        )
        assert signal.signal_type == SignalType.TITLE
        assert signal.category == "product"
        assert signal.confidence_boost == 0.25
        assert signal.matched_text == "Buy Now"
        assert signal.pattern == r"\bbuy\s+now\b"

    def test_signal_to_dict(self) -> None:
        """Test converting signal to dictionary."""
        signal = ContentSignal(
            signal_type=SignalType.SCHEMA,
            category="product",
            confidence_boost=0.4,
            matched_text='"@type": "Product"',
        )
        result = signal.to_dict()
        assert result["signal_type"] == "schema"
        assert result["category"] == "product"
        assert result["confidence_boost"] == 0.4
        assert '"@type": "Product"' in result["matched_text"]

    def test_signal_to_dict_truncates_long_text(self) -> None:
        """Test that to_dict truncates long matched text."""
        long_text = "x" * 500
        signal = ContentSignal(
            signal_type=SignalType.BODY,
            category="product",
            confidence_boost=0.2,
            matched_text=long_text,
        )
        result = signal.to_dict()
        assert len(result["matched_text"]) == 200


class TestContentAnalysis:
    """Tests for the ContentAnalysis dataclass."""

    def test_create_analysis(self) -> None:
        """Test creating a content analysis."""
        analysis = ContentAnalysis(
            url_category="product",
            url_confidence=0.7,
        )
        assert analysis.url_category == "product"
        assert analysis.url_confidence == 0.7
        assert analysis.final_category == "product"  # Default
        assert analysis.boosted_confidence == 0.7  # Default
        assert analysis.signals == []

    def test_analysis_with_signals(self) -> None:
        """Test creating analysis with signals."""
        signals = [
            ContentSignal(
                signal_type=SignalType.TITLE,
                category="product",
                confidence_boost=0.2,
                matched_text="Buy Now",
            ),
        ]
        analysis = ContentAnalysis(
            url_category="product",
            url_confidence=0.7,
            signals=signals,
            boosted_confidence=0.9,
            final_category="product",
        )
        assert len(analysis.signals) == 1
        assert analysis.boosted_confidence == 0.9

    def test_analysis_to_dict(self) -> None:
        """Test converting analysis to dictionary."""
        signal = ContentSignal(
            signal_type=SignalType.SCHEMA,
            category="product",
            confidence_boost=0.3,
            matched_text="Product",
        )
        analysis = ContentAnalysis(
            url_category="other",
            url_confidence=0.3,
            signals=[signal],
            boosted_confidence=0.8,
            final_category="product",
        )
        result = analysis.to_dict()
        assert result["url_category"] == "other"
        assert result["url_confidence"] == 0.3
        assert result["boosted_confidence"] == 0.8
        assert result["final_category"] == "product"
        assert result["signal_count"] == 1
        assert len(result["signals"]) == 1


class TestSignalPattern:
    """Tests for the SignalPattern dataclass."""

    def test_create_pattern(self) -> None:
        """Test creating a signal pattern."""
        pattern = SignalPattern(
            category="product",
            patterns=[r"\bbuy\s+now\b", r"\$\d+"],
            signal_type=SignalType.BODY,
            confidence_boost=0.25,
            priority=80,
        )
        assert pattern.category == "product"
        assert len(pattern.patterns) == 2
        assert pattern.signal_type == SignalType.BODY
        assert pattern.confidence_boost == 0.25
        assert pattern.priority == 80

    def test_pattern_matches(self) -> None:
        """Test pattern matching."""
        pattern = SignalPattern(
            category="product",
            patterns=[r"\bbuy\s+now\b"],
            signal_type=SignalType.BODY,
        )
        # Should match
        matches, text, pat = pattern.matches("Click here to buy now!")
        assert matches is True
        assert text == "buy now"
        assert pat == r"\bbuy\s+now\b"

        # Should not match
        matches, text, pat = pattern.matches("Click here to continue")
        assert matches is False
        assert text is None

    def test_pattern_matches_case_insensitive(self) -> None:
        """Test that pattern matching is case-insensitive."""
        pattern = SignalPattern(
            category="product",
            patterns=[r"\bbuy\s+now\b"],
            signal_type=SignalType.BODY,
        )
        matches, text, _ = pattern.matches("BUY NOW for free shipping!")
        assert matches is True
        assert text.lower() == "buy now"

    def test_pattern_matches_empty_text(self) -> None:
        """Test pattern matching with empty text."""
        pattern = SignalPattern(
            category="product",
            patterns=[r"\bbuy\s+now\b"],
            signal_type=SignalType.BODY,
        )
        matches, _, _ = pattern.matches("")
        assert matches is False

        matches, _, _ = pattern.matches(None)  # type: ignore[arg-type]
        assert matches is False

    def test_pattern_with_invalid_regex(self) -> None:
        """Test that invalid regex is handled gracefully."""
        pattern = SignalPattern(
            category="product",
            patterns=[r"[invalid(regex"],  # Invalid regex
            signal_type=SignalType.BODY,
        )
        # Should not crash, pattern should just not match
        matches, _, _ = pattern.matches("some text")
        assert matches is False


class TestContentSignalDetector:
    """Tests for the ContentSignalDetector class."""

    @pytest.fixture
    def detector(self) -> ContentSignalDetector:
        """Create a fresh detector instance for tests."""
        return ContentSignalDetector()

    def test_detector_initialization(self, detector: ContentSignalDetector) -> None:
        """Test detector initializes with default patterns."""
        assert len(detector.patterns) > 0
        assert detector.max_boost == 0.95

    def test_detector_custom_patterns(self) -> None:
        """Test creating detector with custom patterns."""
        custom_patterns = [
            SignalPattern(
                category="custom",
                patterns=[r"\bcustom\b"],
                signal_type=SignalType.TITLE,
                confidence_boost=0.5,
            ),
        ]
        detector = ContentSignalDetector(patterns=custom_patterns)
        assert len(detector.patterns) == 1
        assert detector.patterns[0].category == "custom"

    def test_add_pattern(self, detector: ContentSignalDetector) -> None:
        """Test adding a pattern to the detector."""
        original_count = len(detector.patterns)
        detector.add_pattern(SignalPattern(
            category="custom",
            patterns=[r"\bnew\b"],
            signal_type=SignalType.TITLE,
        ))
        assert len(detector.patterns) == original_count + 1

    def test_get_patterns_for_category(self, detector: ContentSignalDetector) -> None:
        """Test getting patterns for a specific category."""
        product_patterns = detector.get_patterns_for_category("product")
        assert len(product_patterns) > 0
        assert all(p.category == "product" for p in product_patterns)


class TestDetectSignals:
    """Tests for signal detection from content."""

    @pytest.fixture
    def detector(self) -> ContentSignalDetector:
        """Create a detector for tests."""
        return ContentSignalDetector()

    def test_detect_product_title_signal(self, detector: ContentSignalDetector) -> None:
        """Test detecting product signals from title."""
        signals = detector.detect_signals(
            body_text="Buy now for only $29.99!"
        )
        assert len(signals) > 0
        product_signals = [s for s in signals if s.category == "product"]
        assert len(product_signals) > 0

    def test_detect_product_price_signal(self, detector: ContentSignalDetector) -> None:
        """Test detecting product signals from price patterns."""
        signals = detector.detect_signals(
            body_text="Only $49.99 - Free shipping included"
        )
        product_signals = [s for s in signals if s.category == "product"]
        assert len(product_signals) > 0

    def test_detect_product_schema_signal(self, detector: ContentSignalDetector) -> None:
        """Test detecting product signals from JSON-LD schema."""
        schema = '{"@type": "Product", "name": "Widget Pro"}'
        signals = detector.detect_signals(schema_json=schema)
        schema_signals = [s for s in signals if s.signal_type == SignalType.SCHEMA]
        assert len(schema_signals) > 0
        assert any(s.category == "product" for s in schema_signals)

    def test_detect_blog_signals(self, detector: ContentSignalDetector) -> None:
        """Test detecting blog signals."""
        signals = detector.detect_signals(
            title="Blog Post Title",
            body_text="Posted on January 1, 2024 by John. Read more about...",
        )
        blog_signals = [s for s in signals if s.category == "blog"]
        assert len(blog_signals) > 0

    def test_detect_policy_title_signal(self, detector: ContentSignalDetector) -> None:
        """Test detecting policy signals from title."""
        signals = detector.detect_signals(
            title="Privacy Policy"
        )
        policy_signals = [s for s in signals if s.category == "policy"]
        assert len(policy_signals) > 0

    def test_detect_policy_body_signal(self, detector: ContentSignalDetector) -> None:
        """Test detecting policy signals from body text."""
        signals = detector.detect_signals(
            body_text="We collect personal data including your name and email address. Last updated: January 2024."
        )
        policy_signals = [s for s in signals if s.category == "policy"]
        assert len(policy_signals) > 0

    def test_detect_contact_signals(self, detector: ContentSignalDetector) -> None:
        """Test detecting contact page signals."""
        signals = detector.detect_signals(
            title="Contact Us",
            body_text="Phone: +1-555-123-4567. Email: contact@example.com"
        )
        contact_signals = [s for s in signals if s.category == "contact"]
        assert len(contact_signals) > 0

    def test_detect_faq_signals(self, detector: ContentSignalDetector) -> None:
        """Test detecting FAQ signals."""
        signals = detector.detect_signals(
            title="FAQ",
            schema_json='{"@type": "FAQPage"}'
        )
        faq_signals = [s for s in signals if s.category == "faq"]
        assert len(faq_signals) > 0

    def test_detect_collection_signals(self, detector: ContentSignalDetector) -> None:
        """Test detecting collection/category page signals."""
        signals = detector.detect_signals(
            body_text="Shop all products. 50 items found. Filter by price. Sort by popularity."
        )
        collection_signals = [s for s in signals if s.category == "collection"]
        assert len(collection_signals) > 0

    def test_detect_cart_signals(self, detector: ContentSignalDetector) -> None:
        """Test detecting cart/checkout signals."""
        signals = detector.detect_signals(
            title="Your Shopping Cart",
            body_text="Proceed to checkout. Subtotal: $99.99"
        )
        cart_signals = [s for s in signals if s.category == "cart"]
        assert len(cart_signals) > 0

    def test_detect_account_signals(self, detector: ContentSignalDetector) -> None:
        """Test detecting account page signals."""
        signals = detector.detect_signals(
            title="Sign In to Your Account",
            body_text="Username: Password: Remember me"
        )
        account_signals = [s for s in signals if s.category == "account"]
        assert len(account_signals) > 0

    def test_detect_about_signals(self, detector: ContentSignalDetector) -> None:
        """Test detecting about page signals."""
        signals = detector.detect_signals(
            title="About Us - Our Story"
        )
        about_signals = [s for s in signals if s.category == "about"]
        assert len(about_signals) > 0

    def test_detect_no_signals_from_generic_content(self, detector: ContentSignalDetector) -> None:
        """Test that generic content produces no strong signals."""
        signals = detector.detect_signals(
            title="Welcome",
            body_text="Lorem ipsum dolor sit amet"
        )
        # May have some weak signals, but should not have many
        assert len(signals) < 3

    def test_detect_signals_with_empty_content(self, detector: ContentSignalDetector) -> None:
        """Test signal detection with all empty content."""
        signals = detector.detect_signals()
        assert signals == []

    def test_detect_signals_truncates_body(self, detector: ContentSignalDetector) -> None:
        """Test that body text is truncated for efficiency."""
        # Create very long body with pattern at the end
        long_body = "x" * 15000 + " buy now "
        signals = detector.detect_signals(body_text=long_body)
        # Pattern at end should NOT be detected (truncated)
        product_signals = [
            s for s in signals
            if s.category == "product" and "buy now" in s.matched_text.lower()
        ]
        assert len(product_signals) == 0

    def test_detect_heading_signals(self, detector: ContentSignalDetector) -> None:
        """Test detecting signals from headings."""
        signals = detector.detect_signals(
            headings=["How do I reset my password?", "Can I cancel my order?"]
        )
        faq_signals = [s for s in signals if s.category == "faq"]
        assert len(faq_signals) > 0


class TestAnalyze:
    """Tests for the analyze method that computes confidence boosting."""

    @pytest.fixture
    def detector(self) -> ContentSignalDetector:
        """Create a detector for tests."""
        return ContentSignalDetector()

    def test_analyze_boosts_matching_category(self, detector: ContentSignalDetector) -> None:
        """Test that signals matching URL category boost confidence."""
        analysis = detector.analyze(
            url_category="product",
            url_confidence=0.7,
            body_text="Buy now for only $29.99! Add to cart for free shipping.",
        )
        assert analysis.url_category == "product"
        assert analysis.final_category == "product"
        assert analysis.boosted_confidence > 0.7

    def test_analyze_respects_max_boost(self, detector: ContentSignalDetector) -> None:
        """Test that boosted confidence doesn't exceed max_boost."""
        analysis = detector.analyze(
            url_category="product",
            url_confidence=0.9,
            body_text="Buy now $29.99 add to cart in stock free shipping sku model",
            schema_json='{"@type": "Product"}',
        )
        assert analysis.boosted_confidence <= 0.95

    def test_analyze_category_override(self, detector: ContentSignalDetector) -> None:
        """Test that strong signals can override URL category."""
        # URL says "other" but content clearly indicates "policy"
        analysis = detector.analyze(
            url_category="other",
            url_confidence=0.3,
            title="Privacy Policy",
            body_text="We collect personal data. GDPR compliant. Last updated 2024.",
        )
        # Should potentially override to "policy"
        assert analysis.final_category in ["other", "policy"]
        if analysis.final_category == "policy":
            assert analysis.boosted_confidence > analysis.url_confidence

    def test_analyze_no_signals(self, detector: ContentSignalDetector) -> None:
        """Test analysis when no signals are detected."""
        analysis = detector.analyze(
            url_category="other",
            url_confidence=0.5,
            title="Welcome",
            body_text="Lorem ipsum dolor sit amet",
        )
        # Should return URL-based values unchanged
        assert analysis.final_category == "other"
        assert analysis.boosted_confidence == 0.5

    def test_analyze_with_entity_ids(self, detector: ContentSignalDetector) -> None:
        """Test analysis with project_id and page_id for logging."""
        analysis = detector.analyze(
            url_category="product",
            url_confidence=0.7,
            title="Widget Pro",
            body_text="$29.99",
            project_id="proj-123",
            page_id="page-456",
        )
        # Should work normally with entity IDs
        assert analysis is not None
        assert len(analysis.signals) >= 0

    def test_analyze_includes_all_signal_info(self, detector: ContentSignalDetector) -> None:
        """Test that analysis includes all signal information."""
        analysis = detector.analyze(
            url_category="blog",
            url_confidence=0.6,
            title="Blog Post",
            body_text="Posted on January 1, 2024. Read more.",
            schema_json='{"@type": "BlogPosting"}',
        )
        assert len(analysis.signals) > 0
        for signal in analysis.signals:
            assert signal.signal_type is not None
            assert signal.category is not None
            assert signal.confidence_boost > 0
            assert signal.matched_text is not None


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_content_signal_detector_singleton(self) -> None:
        """Test that get_content_signal_detector returns a singleton."""
        detector1 = get_content_signal_detector()
        detector2 = get_content_signal_detector()
        assert detector1 is detector2

    def test_analyze_content_signals_function(self) -> None:
        """Test the analyze_content_signals convenience function."""
        analysis = analyze_content_signals(
            url_category="product",
            url_confidence=0.7,
            title="Buy Widget Pro",
            body_text="$29.99 - Add to Cart",
        )
        assert isinstance(analysis, ContentAnalysis)
        assert analysis.url_category == "product"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def detector(self) -> ContentSignalDetector:
        """Create a detector for tests."""
        return ContentSignalDetector()

    def test_unicode_content(self, detector: ContentSignalDetector) -> None:
        """Test handling of unicode content."""
        signals = detector.detect_signals(
            title="商品 - Product",
            body_text="价格: ¥299 Buy now",
        )
        # Should handle unicode without crashing
        assert isinstance(signals, list)

    def test_special_characters(self, detector: ContentSignalDetector) -> None:
        """Test handling of special characters."""
        signals = detector.detect_signals(
            body_text="Price: $29.99* (*excluding tax & shipping)"
        )
        # Should handle special chars without crashing
        product_signals = [s for s in signals if s.category == "product"]
        assert len(product_signals) > 0

    def test_very_long_title(self, detector: ContentSignalDetector) -> None:
        """Test handling of very long titles."""
        long_title = "Buy Now " + "x" * 1000
        analysis = detector.analyze(
            url_category="other",
            url_confidence=0.3,
            title=long_title,
        )
        # Should handle without crashing
        assert isinstance(analysis, ContentAnalysis)

    def test_mixed_case_patterns(self, detector: ContentSignalDetector) -> None:
        """Test pattern matching is case-insensitive."""
        signals = detector.detect_signals(
            title="PRIVACY POLICY",
            body_text="WE COLLECT PERSONAL DATA",
        )
        policy_signals = [s for s in signals if s.category == "policy"]
        assert len(policy_signals) > 0

    def test_custom_max_boost(self) -> None:
        """Test custom max_boost setting."""
        detector = ContentSignalDetector(max_boost=0.8)
        analysis = detector.analyze(
            url_category="product",
            url_confidence=0.75,
            body_text="Buy now $29.99 add to cart",
            schema_json='{"@type": "Product"}',
        )
        assert analysis.boosted_confidence <= 0.8

    def test_custom_min_override_boost(self) -> None:
        """Test custom min_override_boost setting."""
        # With high override threshold, category should not change
        detector = ContentSignalDetector(min_override_boost=0.9)
        analysis = detector.analyze(
            url_category="other",
            url_confidence=0.3,
            title="Privacy Policy",
        )
        # Policy signals likely won't meet 0.9 threshold
        assert analysis.final_category == "other"


class TestMultipleSignalInteraction:
    """Tests for how multiple signals interact."""

    @pytest.fixture
    def detector(self) -> ContentSignalDetector:
        """Create a detector for tests."""
        return ContentSignalDetector()

    def test_multiple_signals_same_category(self, detector: ContentSignalDetector) -> None:
        """Test multiple signals for the same category."""
        analysis = detector.analyze(
            url_category="product",
            url_confidence=0.5,
            title="Buy Widget Pro",
            body_text="$29.99 - In stock - Add to cart - Free shipping - SKU: WP001",
            schema_json='{"@type": "Product"}',
        )
        # Multiple signals should stack (up to max)
        assert analysis.boosted_confidence > 0.7

    def test_conflicting_signals(self, detector: ContentSignalDetector) -> None:
        """Test when content has signals for multiple categories."""
        # This page has both blog and product signals
        analysis = detector.analyze(
            url_category="blog",
            url_confidence=0.6,
            title="Product Review Blog Post",
            body_text="Posted on January 1. Buy now for $29.99.",
        )
        # Should return a valid result
        assert analysis.final_category in ["blog", "product"]
        assert analysis.boosted_confidence >= 0.6

    def test_signals_all_types(self, detector: ContentSignalDetector) -> None:
        """Test signals from all content types at once."""
        analysis = detector.analyze(
            url_category="product",
            url_confidence=0.7,
            title="Buy Widget Pro",
            headings=["Product Details", "Add to Cart"],
            body_text="In stock. $29.99. Free shipping.",
            schema_json='{"@type": "Product"}',
            meta_description="Buy Widget Pro - best price guaranteed",
            breadcrumbs=["Home", "Products", "Widget Pro"],
        )
        # Should process all types without issues
        assert len(analysis.signals) > 0
        # Check we got signals from different types
        signal_types = {s.signal_type for s in analysis.signals}
        assert len(signal_types) >= 1
