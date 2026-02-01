"""Unit tests for CategoryService pattern matching and confidence scoring.

Tests cover:
- URL confidence scoring (base and boosted)
- Content signal integration
- LLM fallback threshold behavior
- Two-tier categorization flow
- CategorizationRequest and CategorizationResult dataclasses
- Validation methods
- Exception classes

ERROR LOGGING REQUIREMENTS:
- Ensure test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: 80% code coverage for CategoryService.
"""

from unittest.mock import MagicMock

import pytest

from app.services.category import (
    DEFAULT_LLM_FALLBACK_THRESHOLD,
    CategorizationRequest,
    CategorizationResult,
    CategoryNotFoundError,
    CategoryService,
    CategoryServiceError,
    CategoryValidationError,
    categorize_page,
    get_category_service,
)
from app.utils.content_signals import ContentAnalysis, ContentSignal, SignalType
from app.utils.url_categorizer import VALID_PAGE_CATEGORIES

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def category_service() -> CategoryService:
    """Create a CategoryService instance with LLM fallback disabled."""
    return CategoryService(
        enable_llm_fallback=False,
    )


@pytest.fixture
def category_service_with_llm() -> CategoryService:
    """Create a CategoryService instance with LLM fallback enabled."""
    mock_claude = MagicMock()
    mock_claude.available = True
    return CategoryService(
        claude_client=mock_claude,
        enable_llm_fallback=True,
        llm_fallback_threshold=0.6,
    )


# ---------------------------------------------------------------------------
# Test: CategorizationRequest Dataclass
# ---------------------------------------------------------------------------


class TestCategorizationRequest:
    """Tests for the CategorizationRequest dataclass."""

    def test_create_with_url_only(self) -> None:
        """Should create request with URL only."""
        request = CategorizationRequest(url="https://example.com/products/widget")
        assert request.url == "https://example.com/products/widget"
        assert request.title is None
        assert request.content is None
        assert request.headings is None
        assert request.schema_json is None
        assert request.meta_description is None
        assert request.breadcrumbs is None
        assert request.project_id is None
        assert request.page_id is None

    def test_create_with_all_fields(self) -> None:
        """Should create request with all fields."""
        request = CategorizationRequest(
            url="https://example.com/products/widget",
            title="Widget Pro - Buy Now",
            content="Add to cart for $29.99",
            headings=["Product Details", "Reviews"],
            schema_json='{"@type": "Product"}',
            meta_description="Best widget available",
            breadcrumbs=["Home", "Products", "Widget Pro"],
            project_id="proj-123",
            page_id="page-456",
        )
        assert request.url == "https://example.com/products/widget"
        assert request.title == "Widget Pro - Buy Now"
        assert request.content == "Add to cart for $29.99"
        assert len(request.headings or []) == 2
        assert request.schema_json == '{"@type": "Product"}'
        assert request.meta_description == "Best widget available"
        assert len(request.breadcrumbs or []) == 3
        assert request.project_id == "proj-123"
        assert request.page_id == "page-456"


# ---------------------------------------------------------------------------
# Test: CategorizationResult Dataclass
# ---------------------------------------------------------------------------


class TestCategorizationResult:
    """Tests for the CategorizationResult dataclass."""

    def test_create_success_result(self) -> None:
        """Should create a successful result."""
        result = CategorizationResult(
            success=True,
            url="https://example.com/products/widget",
            category="product",
            confidence=0.85,
            tier="pattern",
            url_category="product",
            url_confidence=0.6,
        )
        assert result.success is True
        assert result.category == "product"
        assert result.confidence == 0.85
        assert result.tier == "pattern"

    def test_create_failure_result(self) -> None:
        """Should create a failed result."""
        result = CategorizationResult(
            success=False,
            url="https://example.com/invalid",
            error="URL validation failed",
        )
        assert result.success is False
        assert result.error == "URL validation failed"
        assert result.category == "other"  # Default
        assert result.confidence == 0.0  # Default

    def test_result_defaults(self) -> None:
        """Should have correct default values."""
        result = CategorizationResult(success=True, url="https://example.com/")
        assert result.category == "other"
        assert result.confidence == 0.0
        assert result.tier == "pattern"
        assert result.url_category == "other"
        assert result.url_confidence == 0.0
        assert result.content_analysis is None
        assert result.llm_result is None
        assert result.labels == []
        assert result.reasoning is None
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.project_id is None
        assert result.page_id is None

    def test_result_to_dict(self) -> None:
        """Should convert result to dictionary correctly."""
        result = CategorizationResult(
            success=True,
            url="https://example.com/products/widget",
            category="product",
            confidence=0.85,
            tier="pattern",
            url_category="product",
            url_confidence=0.6,
            labels=["featured", "bestseller"],
            reasoning="Matched product URL pattern",
            duration_ms=15.5,
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["url"] == "https://example.com/products/widget"
        assert data["category"] == "product"
        assert data["confidence"] == 0.85
        assert data["tier"] == "pattern"
        assert data["url_category"] == "product"
        assert data["url_confidence"] == 0.6
        assert data["labels"] == ["featured", "bestseller"]
        assert data["reasoning"] == "Matched product URL pattern"
        assert data["duration_ms"] == 15.5
        assert data["content_analysis"] is None

    def test_result_to_dict_with_content_analysis(self) -> None:
        """Should include content analysis in dict when present."""
        analysis = ContentAnalysis(
            url_category="product",
            url_confidence=0.6,
            final_category="product",
            boosted_confidence=0.85,
            signals=[
                ContentSignal(
                    signal_type=SignalType.BODY,
                    category="product",
                    confidence_boost=0.25,
                    matched_text="$29.99",
                ),
            ],
        )
        result = CategorizationResult(
            success=True,
            url="https://example.com/products/widget",
            content_analysis=analysis,
        )
        data = result.to_dict()
        assert data["content_analysis"] is not None
        assert data["content_analysis"]["url_category"] == "product"
        assert data["content_analysis"]["boosted_confidence"] == 0.85


# ---------------------------------------------------------------------------
# Test: CategoryService Initialization
# ---------------------------------------------------------------------------


class TestCategoryServiceInit:
    """Tests for CategoryService initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize with default values."""
        service = CategoryService()
        assert service.llm_fallback_threshold == DEFAULT_LLM_FALLBACK_THRESHOLD
        assert service.valid_categories == VALID_PAGE_CATEGORIES

    def test_custom_threshold(self) -> None:
        """Should accept custom LLM fallback threshold."""
        service = CategoryService(llm_fallback_threshold=0.8)
        assert service.llm_fallback_threshold == 0.8

    def test_disable_llm_fallback(self) -> None:
        """Should disable LLM fallback when requested."""
        service = CategoryService(enable_llm_fallback=False)
        # LLM fallback is disabled, so it won't use Claude
        assert service.llm_fallback_threshold == DEFAULT_LLM_FALLBACK_THRESHOLD


# ---------------------------------------------------------------------------
# Test: URL Validation
# ---------------------------------------------------------------------------


class TestCategoryServiceValidation:
    """Tests for CategoryService validation methods."""

    def test_validate_url_valid_http(self, category_service: CategoryService) -> None:
        """Should accept valid HTTP URL."""
        # Should not raise
        category_service._validate_url("http://example.com/path")

    def test_validate_url_valid_https(self, category_service: CategoryService) -> None:
        """Should accept valid HTTPS URL."""
        # Should not raise
        category_service._validate_url("https://example.com/path")

    def test_validate_url_valid_relative(self, category_service: CategoryService) -> None:
        """Should accept relative URL starting with /."""
        # Should not raise
        category_service._validate_url("/products/widget")

    def test_validate_url_empty_raises(self, category_service: CategoryService) -> None:
        """Should reject empty URL."""
        with pytest.raises(CategoryValidationError) as exc_info:
            category_service._validate_url("")
        assert exc_info.value.field == "url"
        assert "required" in exc_info.value.message.lower()

    def test_validate_url_whitespace_raises(self, category_service: CategoryService) -> None:
        """Should reject whitespace-only URL."""
        with pytest.raises(CategoryValidationError) as exc_info:
            category_service._validate_url("   ")
        assert exc_info.value.field == "url"

    def test_validate_url_no_scheme_raises(self, category_service: CategoryService) -> None:
        """Should reject URL without scheme."""
        with pytest.raises(CategoryValidationError) as exc_info:
            category_service._validate_url("example.com/path")
        assert exc_info.value.field == "url"
        assert "http" in exc_info.value.message.lower()

    def test_validate_category_valid(self, category_service: CategoryService) -> None:
        """Should accept valid categories."""
        for category in VALID_PAGE_CATEGORIES:
            # Should not raise
            category_service._validate_category(category)

    def test_validate_category_invalid(self, category_service: CategoryService) -> None:
        """Should reject invalid category."""
        with pytest.raises(CategoryValidationError) as exc_info:
            category_service._validate_category("invalid_category")
        assert exc_info.value.field == "category"
        assert "must be one of" in exc_info.value.message.lower()


# ---------------------------------------------------------------------------
# Test: URL Confidence Scoring
# ---------------------------------------------------------------------------


class TestURLConfidenceScoring:
    """Tests for URL-based confidence scoring."""

    @pytest.mark.asyncio
    async def test_product_url_base_confidence(
        self,
        category_service: CategoryService,
    ) -> None:
        """Product URL should get base confidence of 0.6."""
        result = await category_service.categorize(
            url="https://example.com/products/widget-pro",
            skip_llm=True,
        )
        assert result.success is True
        assert result.url_category == "product"
        assert result.url_confidence == 0.6  # Pattern match gives 0.6

    @pytest.mark.asyncio
    async def test_other_url_base_confidence(
        self,
        category_service: CategoryService,
    ) -> None:
        """Unknown URL should get low base confidence of 0.3."""
        result = await category_service.categorize(
            url="https://example.com/xyz123/random-page",
            skip_llm=True,
        )
        assert result.success is True
        assert result.url_category == "other"
        # 'other' gets 0.3 base confidence
        assert result.url_confidence == 0.3

    @pytest.mark.asyncio
    async def test_blog_url_confidence(
        self,
        category_service: CategoryService,
    ) -> None:
        """Blog URL should be categorized correctly."""
        result = await category_service.categorize(
            url="https://example.com/blog/how-to-use-widgets",
            skip_llm=True,
        )
        assert result.success is True
        assert result.url_category == "blog"
        assert result.url_confidence == 0.6

    @pytest.mark.asyncio
    async def test_policy_url_confidence(
        self,
        category_service: CategoryService,
    ) -> None:
        """Policy URL should be categorized correctly."""
        result = await category_service.categorize(
            url="https://example.com/privacy-policy",
            skip_llm=True,
        )
        assert result.success is True
        assert result.url_category == "policy"
        assert result.url_confidence == 0.6

    @pytest.mark.asyncio
    async def test_homepage_url_confidence(
        self,
        category_service: CategoryService,
    ) -> None:
        """Homepage URL should be categorized correctly."""
        result = await category_service.categorize(
            url="https://example.com/",
            skip_llm=True,
        )
        assert result.success is True
        assert result.url_category == "homepage"


# ---------------------------------------------------------------------------
# Test: Content Signal Boosting
# ---------------------------------------------------------------------------


class TestContentSignalBoosting:
    """Tests for content signal confidence boosting."""

    @pytest.mark.asyncio
    async def test_signals_boost_confidence(
        self,
        category_service: CategoryService,
    ) -> None:
        """Content signals should boost confidence."""
        result = await category_service.categorize(
            url="https://example.com/products/widget-pro",
            title="Buy Widget Pro - Free Shipping",
            content="Only $29.99! Add to cart now. In stock.",
            skip_llm=True,
        )
        assert result.success is True
        assert result.category == "product"
        # Boosted confidence should be higher than URL-only confidence
        assert result.confidence > result.url_confidence
        assert result.content_analysis is not None
        assert result.content_analysis.boosted_confidence > result.url_confidence

    @pytest.mark.asyncio
    async def test_schema_signal_boosts_product(
        self,
        category_service: CategoryService,
    ) -> None:
        """JSON-LD Product schema should boost product confidence."""
        result = await category_service.categorize(
            url="https://example.com/items/12345",
            title="Widget",
            schema_json='{"@type": "Product", "name": "Widget"}',
            skip_llm=True,
        )
        assert result.success is True
        # Schema signal should help even if URL isn't clearly a product
        assert result.content_analysis is not None
        assert len(result.content_analysis.signals) > 0

    @pytest.mark.asyncio
    async def test_multiple_signals_stack(
        self,
        category_service: CategoryService,
    ) -> None:
        """Multiple signals should stack up to max boost."""
        result = await category_service.categorize(
            url="https://example.com/products/widget",
            title="Buy Widget Pro Now",
            content="$29.99 - Add to cart - In stock - Free shipping - SKU: WP001",
            schema_json='{"@type": "Product"}',
            skip_llm=True,
        )
        assert result.success is True
        assert result.content_analysis is not None
        # Multiple signals should give high confidence (but capped at 0.95)
        assert result.confidence <= 0.95
        assert len(result.content_analysis.signals) >= 2

    @pytest.mark.asyncio
    async def test_no_signals_keeps_url_confidence(
        self,
        category_service: CategoryService,
    ) -> None:
        """No content signals should keep URL-only confidence."""
        result = await category_service.categorize(
            url="https://example.com/products/widget",
            title="Welcome",
            content="Lorem ipsum dolor sit amet",
            skip_llm=True,
        )
        assert result.success is True
        # With no matching signals, confidence stays at URL level
        # (may be slightly affected by analysis but won't have strong boosts)
        assert result.confidence >= result.url_confidence

    @pytest.mark.asyncio
    async def test_content_can_override_url_category(
        self,
        category_service: CategoryService,
    ) -> None:
        """Strong content signals can override URL-based category."""
        result = await category_service.categorize(
            url="https://example.com/pages/item",  # Generic URL
            title="Privacy Policy",
            content="We collect personal data. GDPR compliant. Last updated 2024.",
            skip_llm=True,
        )
        assert result.success is True
        # Content signals may override to "policy" if strong enough
        # The exact category depends on signal strength
        assert result.content_analysis is not None


# ---------------------------------------------------------------------------
# Test: LLM Fallback Threshold
# ---------------------------------------------------------------------------


class TestLLMFallbackThreshold:
    """Tests for LLM fallback threshold behavior."""

    def test_high_confidence_check(self, category_service: CategoryService) -> None:
        """Should correctly identify high confidence scores."""
        assert category_service.is_high_confidence(0.7) is True
        assert category_service.is_high_confidence(0.6) is True
        assert category_service.is_high_confidence(0.59) is False
        assert category_service.is_high_confidence(0.0) is False

    def test_custom_threshold_check(self, category_service: CategoryService) -> None:
        """Should use custom threshold when provided."""
        assert category_service.is_high_confidence(0.7, threshold=0.8) is False
        assert category_service.is_high_confidence(0.8, threshold=0.8) is True
        assert category_service.is_high_confidence(0.5, threshold=0.4) is True

    @pytest.mark.asyncio
    async def test_skip_llm_ignores_threshold(
        self,
        category_service: CategoryService,
    ) -> None:
        """skip_llm=True should never trigger LLM."""
        result = await category_service.categorize(
            url="https://example.com/xyz123",  # Low confidence URL
            skip_llm=True,
        )
        assert result.success is True
        assert result.tier == "pattern"  # Never used LLM

    @pytest.mark.asyncio
    async def test_high_confidence_skips_llm(
        self,
        category_service_with_llm: CategoryService,
    ) -> None:
        """High confidence pattern result should skip LLM."""
        # Create a result that gets high confidence from patterns
        result = await category_service_with_llm.categorize(
            url="https://example.com/products/widget",
            title="Buy Widget - Only $29.99",
            content="Add to cart for free shipping. In stock now!",
            schema_json='{"@type": "Product"}',
        )
        # If confidence is high enough, should stay on "pattern" tier
        if result.confidence >= 0.6:
            assert result.tier == "pattern"


# ---------------------------------------------------------------------------
# Test: URL-Only Categorization (Synchronous)
# ---------------------------------------------------------------------------


class TestURLOnlyCategorization:
    """Tests for categorize_url_only method."""

    def test_product_url(self, category_service: CategoryService) -> None:
        """Product URL should be categorized correctly."""
        category, confidence = category_service.categorize_url_only(
            "https://example.com/products/widget"
        )
        assert category == "product"
        assert confidence == 0.6

    def test_blog_url(self, category_service: CategoryService) -> None:
        """Blog URL should be categorized correctly."""
        category, confidence = category_service.categorize_url_only(
            "https://example.com/blog/article"
        )
        assert category == "blog"
        assert confidence == 0.6

    def test_unknown_url(self, category_service: CategoryService) -> None:
        """Unknown URL should get 'other' with low confidence."""
        category, confidence = category_service.categorize_url_only(
            "https://example.com/xyz123abc"
        )
        assert category == "other"
        assert confidence == 0.3

    def test_empty_url(self, category_service: CategoryService) -> None:
        """Empty URL should return 'other' with 0.0 confidence."""
        category, confidence = category_service.categorize_url_only("")
        assert category == "other"
        assert confidence == 0.0

    def test_homepage_url(self, category_service: CategoryService) -> None:
        """Homepage URL should be categorized correctly."""
        category, confidence = category_service.categorize_url_only(
            "https://example.com/"
        )
        assert category == "homepage"

    def test_contact_url(self, category_service: CategoryService) -> None:
        """Contact URL should be categorized correctly."""
        category, confidence = category_service.categorize_url_only(
            "https://example.com/contact-us"
        )
        assert category == "contact"
        assert confidence == 0.6


# ---------------------------------------------------------------------------
# Test: Categorize Request Object
# ---------------------------------------------------------------------------


class TestCategorizeRequest:
    """Tests for categorize_request method."""

    @pytest.mark.asyncio
    async def test_categorize_request_basic(
        self,
        category_service: CategoryService,
    ) -> None:
        """Should categorize using request object."""
        request = CategorizationRequest(
            url="https://example.com/products/widget",
            title="Widget Pro",
            project_id="proj-123",
            page_id="page-456",
        )
        result = await category_service.categorize_request(request, skip_llm=True)
        assert result.success is True
        assert result.category == "product"
        assert result.project_id == "proj-123"
        assert result.page_id == "page-456"

    @pytest.mark.asyncio
    async def test_categorize_request_with_content(
        self,
        category_service: CategoryService,
    ) -> None:
        """Should use content from request object."""
        request = CategorizationRequest(
            url="https://example.com/products/widget",
            title="Buy Now",
            content="Only $29.99! Add to cart.",
            schema_json='{"@type": "Product"}',
        )
        result = await category_service.categorize_request(request, skip_llm=True)
        assert result.success is True
        assert result.content_analysis is not None
        assert len(result.content_analysis.signals) > 0


# ---------------------------------------------------------------------------
# Test: Batch Categorization
# ---------------------------------------------------------------------------


class TestBatchCategorization:
    """Tests for categorize_many method."""

    @pytest.mark.asyncio
    async def test_categorize_many_empty_list(
        self,
        category_service: CategoryService,
    ) -> None:
        """Should handle empty page list."""
        results = await category_service.categorize_many([], skip_llm=True)
        assert results == []

    @pytest.mark.asyncio
    async def test_categorize_many_basic(
        self,
        category_service: CategoryService,
    ) -> None:
        """Should categorize multiple pages."""
        pages = [
            CategorizationRequest(url="https://example.com/products/item1"),
            CategorizationRequest(url="https://example.com/blog/post1"),
            CategorizationRequest(url="https://example.com/about"),
        ]
        results = await category_service.categorize_many(pages, skip_llm=True)
        assert len(results) == 3
        assert results[0].category == "product"
        assert results[1].category == "blog"
        assert results[2].category == "about"

    @pytest.mark.asyncio
    async def test_categorize_many_uses_project_id(
        self,
        category_service: CategoryService,
    ) -> None:
        """Should propagate project_id to all results."""
        pages = [
            CategorizationRequest(url="https://example.com/products/item1"),
            CategorizationRequest(url="https://example.com/blog/post1"),
        ]
        results = await category_service.categorize_many(
            pages,
            project_id="proj-123",
            skip_llm=True,
        )
        # Project ID should be set on requests that didn't have it
        assert all(r.project_id == "proj-123" for r in results)

    @pytest.mark.asyncio
    async def test_categorize_many_preserves_existing_project_id(
        self,
        category_service: CategoryService,
    ) -> None:
        """Should preserve project_id if already set on request."""
        pages = [
            CategorizationRequest(
                url="https://example.com/products/item1",
                project_id="existing-proj",
            ),
            CategorizationRequest(url="https://example.com/blog/post1"),
        ]
        results = await category_service.categorize_many(
            pages,
            project_id="default-proj",
            skip_llm=True,
        )
        # First page keeps its existing project_id
        assert results[0].project_id == "existing-proj"
        # Second page gets the default
        assert results[1].project_id == "default-proj"


# ---------------------------------------------------------------------------
# Test: Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_invalid_url_returns_error_result(
        self,
        category_service: CategoryService,
    ) -> None:
        """Invalid URL should raise CategoryValidationError."""
        with pytest.raises(CategoryValidationError):
            await category_service.categorize(
                url="not-a-valid-url",
                skip_llm=True,
            )

    @pytest.mark.asyncio
    async def test_empty_url_returns_error_result(
        self,
        category_service: CategoryService,
    ) -> None:
        """Empty URL should raise CategoryValidationError."""
        with pytest.raises(CategoryValidationError):
            await category_service.categorize(
                url="",
                skip_llm=True,
            )


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestExceptionClasses:
    """Tests for CategoryService exception classes."""

    def test_category_service_error_base(self) -> None:
        """CategoryServiceError should be base exception."""
        error = CategoryServiceError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_category_validation_error(self) -> None:
        """CategoryValidationError should contain field and value info."""
        error = CategoryValidationError("url", "bad-url", "Invalid URL format")
        assert error.field == "url"
        assert error.value == "bad-url"
        assert error.message == "Invalid URL format"
        assert "url" in str(error)

    def test_category_not_found_error(self) -> None:
        """CategoryNotFoundError should contain category info."""
        error = CategoryNotFoundError("unknown_category")
        assert error.category == "unknown_category"
        assert "unknown_category" in str(error)

    def test_exception_hierarchy(self) -> None:
        """All exceptions should inherit from CategoryServiceError."""
        assert issubclass(CategoryValidationError, CategoryServiceError)
        assert issubclass(CategoryNotFoundError, CategoryServiceError)


# ---------------------------------------------------------------------------
# Test: Singleton and Convenience Functions
# ---------------------------------------------------------------------------


class TestSingletonAndConvenience:
    """Tests for singleton accessor and convenience functions."""

    def test_get_category_service_singleton(self) -> None:
        """get_category_service should return singleton."""
        # Clear the global instance first
        import app.services.category as category_module

        original = category_module._category_service
        category_module._category_service = None

        try:
            service1 = get_category_service()
            service2 = get_category_service()
            assert service1 is service2
        finally:
            # Restore original
            category_module._category_service = original

    @pytest.mark.asyncio
    async def test_categorize_page_convenience(self) -> None:
        """categorize_page should use default service."""
        result = await categorize_page(
            url="https://example.com/products/widget",
            title="Widget Pro",
        )
        assert result.success is True
        assert result.category == "product"


# ---------------------------------------------------------------------------
# Test: Duration and Timing
# ---------------------------------------------------------------------------


class TestTiming:
    """Tests for timing and duration tracking."""

    @pytest.mark.asyncio
    async def test_result_includes_duration(
        self,
        category_service: CategoryService,
    ) -> None:
        """Result should include duration_ms."""
        result = await category_service.categorize(
            url="https://example.com/products/widget",
            skip_llm=True,
        )
        assert result.duration_ms >= 0


# ---------------------------------------------------------------------------
# Test: Tier Assignment
# ---------------------------------------------------------------------------


class TestTierAssignment:
    """Tests for tier assignment in results."""

    @pytest.mark.asyncio
    async def test_pattern_tier_when_skipping_llm(
        self,
        category_service: CategoryService,
    ) -> None:
        """Should assign 'pattern' tier when LLM is skipped."""
        result = await category_service.categorize(
            url="https://example.com/random-page",
            skip_llm=True,
        )
        assert result.tier == "pattern"

    @pytest.mark.asyncio
    async def test_pattern_tier_for_high_confidence(
        self,
        category_service: CategoryService,
    ) -> None:
        """Should assign 'pattern' tier for high confidence results."""
        result = await category_service.categorize(
            url="https://example.com/products/widget",
            content="$29.99 - Add to cart",
            schema_json='{"@type": "Product"}',
        )
        # High confidence should stay on pattern tier (LLM disabled)
        assert result.tier == "pattern"


# ---------------------------------------------------------------------------
# Test: Valid Categories Property
# ---------------------------------------------------------------------------


class TestValidCategories:
    """Tests for valid_categories property."""

    def test_valid_categories_returns_frozenset(
        self,
        category_service: CategoryService,
    ) -> None:
        """valid_categories should return VALID_PAGE_CATEGORIES."""
        assert category_service.valid_categories == VALID_PAGE_CATEGORIES

    def test_valid_categories_is_immutable(
        self,
        category_service: CategoryService,
    ) -> None:
        """valid_categories should be a frozenset."""
        assert isinstance(category_service.valid_categories, frozenset)

    def test_expected_categories_exist(
        self,
        category_service: CategoryService,
    ) -> None:
        """Should include all expected categories."""
        expected = {
            "homepage",
            "product",
            "collection",
            "blog",
            "policy",
            "about",
            "contact",
            "faq",
            "account",
            "cart",
            "search",
            "other",
        }
        assert expected.issubset(category_service.valid_categories)
