"""Unit tests for URLCategorizer.

Tests URL pattern rules for categorizing crawled pages into common categories:
- homepage, product, collection, blog, policy, about, contact, faq, account, cart, search, other
"""

import pytest

from app.utils.url_categorizer import (
    VALID_PAGE_CATEGORIES,
    CategoryRule,
    URLCategorizer,
    categorize_url,
    get_url_categorizer,
)

# =============================================================================
# CategoryRule Tests
# =============================================================================


class TestCategoryRule:
    """Tests for CategoryRule dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic CategoryRule creation."""
        rule = CategoryRule(
            category="product",
            patterns=[r"^/products?/[^/]+/?$"],
        )
        assert rule.category == "product"
        assert len(rule.patterns) == 1
        assert rule.priority == 0
        assert rule.description == ""

    def test_creation_with_all_fields(self) -> None:
        """Test CategoryRule with all fields."""
        rule = CategoryRule(
            category="product",
            patterns=[r"^/products?/[^/]+/?$", r"^/p/[^/]+/?$"],
            priority=80,
            description="Product pages",
        )
        assert rule.category == "product"
        assert len(rule.patterns) == 2
        assert rule.priority == 80
        assert rule.description == "Product pages"

    def test_matches_simple_pattern(self) -> None:
        """Test matching a simple pattern."""
        rule = CategoryRule(
            category="product",
            patterns=[r"^/products?/[^/]+/?$"],
        )
        matches, pattern = rule.matches("/products/widget")
        assert matches is True
        assert pattern == r"^/products?/[^/]+/?$"

    def test_matches_no_match(self) -> None:
        """Test non-matching path."""
        rule = CategoryRule(
            category="product",
            patterns=[r"^/products?/[^/]+/?$"],
        )
        matches, pattern = rule.matches("/about")
        assert matches is False
        assert pattern is None

    def test_matches_case_insensitive(self) -> None:
        """Test that matching is case-insensitive."""
        rule = CategoryRule(
            category="product",
            patterns=[r"^/products?/[^/]+/?$"],
        )
        matches, _ = rule.matches("/PRODUCTS/Widget")
        assert matches is True

    def test_invalid_regex_pattern(self) -> None:
        """Test handling of invalid regex pattern."""
        # This should not raise, but should log warning
        rule = CategoryRule(
            category="test",
            patterns=[r"[invalid(regex"],
        )
        # The invalid pattern should not be compiled
        assert len(rule._compiled_patterns) == 0

    def test_multiple_patterns(self) -> None:
        """Test rule with multiple patterns."""
        rule = CategoryRule(
            category="product",
            patterns=[
                r"^/products?/[^/]+/?$",
                r"^/p/[^/]+/?$",
                r"^/item/[^/]+/?$",
            ],
        )

        # Test each pattern
        matches1, _ = rule.matches("/products/widget")
        assert matches1 is True

        matches2, _ = rule.matches("/p/12345")
        assert matches2 is True

        matches3, _ = rule.matches("/item/cool-item")
        assert matches3 is True


# =============================================================================
# URLCategorizer Basic Tests
# =============================================================================


class TestURLCategorizerBasic:
    """Basic tests for URLCategorizer."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        categorizer = URLCategorizer()
        assert len(categorizer.rules) > 0
        assert categorizer.default_category == "other"
        assert "homepage" in categorizer.categories
        assert "product" in categorizer.categories
        assert "other" in categorizer.categories

    def test_custom_initialization(self) -> None:
        """Test initialization with custom rules."""
        custom_rules = [
            CategoryRule(category="custom", patterns=[r"^/custom/.*"]),
        ]
        categorizer = URLCategorizer(rules=custom_rules, default_category="unknown")
        assert len(categorizer.rules) == 1
        assert categorizer.default_category == "unknown"
        assert "custom" in categorizer.categories
        assert "unknown" in categorizer.categories

    def test_add_rule(self) -> None:
        """Test adding a rule."""
        categorizer = URLCategorizer(rules=[])
        rule = CategoryRule(
            category="custom",
            patterns=[r"^/custom/.*"],
            priority=100,
        )
        categorizer.add_rule(rule)
        assert len(categorizer.rules) == 1
        assert categorizer.rules[0].category == "custom"

    def test_rules_sorted_by_priority(self) -> None:
        """Test that rules are sorted by priority (highest first)."""
        rules = [
            CategoryRule(category="low", patterns=[r"^/low/.*"], priority=10),
            CategoryRule(category="high", patterns=[r"^/high/.*"], priority=100),
            CategoryRule(category="medium", patterns=[r"^/medium/.*"], priority=50),
        ]
        categorizer = URLCategorizer(rules=rules)

        assert categorizer.rules[0].category == "high"
        assert categorizer.rules[1].category == "medium"
        assert categorizer.rules[2].category == "low"

    def test_get_rule_for_category(self) -> None:
        """Test getting rule for a category."""
        categorizer = URLCategorizer()
        rule = categorizer.get_rule_for_category("product")
        assert rule is not None
        assert rule.category == "product"

    def test_get_rule_for_nonexistent_category(self) -> None:
        """Test getting rule for non-existent category."""
        categorizer = URLCategorizer()
        rule = categorizer.get_rule_for_category("nonexistent")
        assert rule is None


# =============================================================================
# Homepage Categorization Tests
# =============================================================================


class TestHomepageCategorization:
    """Tests for homepage URL categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_root_url(self, categorizer: URLCategorizer) -> None:
        """Test root URL is categorized as homepage."""
        category, _ = categorizer.categorize("https://example.com/")
        assert category == "homepage"

    def test_root_no_trailing_slash(self, categorizer: URLCategorizer) -> None:
        """Test root URL without trailing slash."""
        category, _ = categorizer.categorize("https://example.com")
        assert category == "homepage"

    def test_index_html(self, categorizer: URLCategorizer) -> None:
        """Test index.html is categorized as homepage."""
        category, _ = categorizer.categorize("https://example.com/index.html")
        assert category == "homepage"

    def test_home_path(self, categorizer: URLCategorizer) -> None:
        """Test /home path is categorized as homepage."""
        category, _ = categorizer.categorize("https://example.com/home")
        assert category == "homepage"


# =============================================================================
# Product Page Categorization Tests
# =============================================================================


class TestProductCategorization:
    """Tests for product page URL categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_products_path(self, categorizer: URLCategorizer) -> None:
        """Test /products/item path."""
        category, _ = categorizer.categorize("https://example.com/products/widget")
        assert category == "product"

    def test_product_singular(self, categorizer: URLCategorizer) -> None:
        """Test /product/item path (singular)."""
        category, _ = categorizer.categorize("https://example.com/product/widget")
        assert category == "product"

    def test_short_product_url(self, categorizer: URLCategorizer) -> None:
        """Test /p/item short product URL."""
        category, _ = categorizer.categorize("https://example.com/p/12345")
        assert category == "product"

    def test_shop_nested_product(self, categorizer: URLCategorizer) -> None:
        """Test /shop/category/item nested product URL."""
        category, _ = categorizer.categorize("https://example.com/shop/electronics/laptop")
        assert category == "product"

    def test_item_path(self, categorizer: URLCategorizer) -> None:
        """Test /item/name path."""
        category, _ = categorizer.categorize("https://example.com/item/cool-widget")
        assert category == "product"


# =============================================================================
# Collection/Category Page Tests
# =============================================================================


class TestCollectionCategorization:
    """Tests for collection/category page categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_collections_path(self, categorizer: URLCategorizer) -> None:
        """Test /collections/name path."""
        category, _ = categorizer.categorize("https://example.com/collections/summer")
        assert category == "collection"

    def test_collection_singular(self, categorizer: URLCategorizer) -> None:
        """Test /collection/name path."""
        category, _ = categorizer.categorize("https://example.com/collection/winter")
        assert category == "collection"

    def test_category_path(self, categorizer: URLCategorizer) -> None:
        """Test /category/name path."""
        category, _ = categorizer.categorize("https://example.com/category/shoes")
        assert category == "collection"

    def test_shop_root(self, categorizer: URLCategorizer) -> None:
        """Test /shop root path."""
        category, _ = categorizer.categorize("https://example.com/shop")
        assert category == "collection"

    def test_shop_category(self, categorizer: URLCategorizer) -> None:
        """Test /shop/category path (not nested item)."""
        category, _ = categorizer.categorize("https://example.com/shop/electronics")
        assert category == "collection"

    def test_browse_path(self, categorizer: URLCategorizer) -> None:
        """Test /browse/category path."""
        category, _ = categorizer.categorize("https://example.com/browse/new-arrivals")
        assert category == "collection"


# =============================================================================
# Blog Page Categorization Tests
# =============================================================================


class TestBlogCategorization:
    """Tests for blog page categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_blog_listing(self, categorizer: URLCategorizer) -> None:
        """Test /blog listing page."""
        category, _ = categorizer.categorize("https://example.com/blog")
        assert category == "blog"

    def test_blog_post(self, categorizer: URLCategorizer) -> None:
        """Test individual blog post."""
        category, _ = categorizer.categorize("https://example.com/blog/my-awesome-post")
        assert category == "blog"

    def test_news_article(self, categorizer: URLCategorizer) -> None:
        """Test /news article."""
        category, _ = categorizer.categorize("https://example.com/news/company-update")
        assert category == "blog"

    def test_articles_path(self, categorizer: URLCategorizer) -> None:
        """Test /articles path."""
        category, _ = categorizer.categorize("https://example.com/articles/how-to-guide")
        assert category == "blog"

    def test_posts_path(self, categorizer: URLCategorizer) -> None:
        """Test /posts path."""
        category, _ = categorizer.categorize("https://example.com/posts/post-slug")
        assert category == "blog"


# =============================================================================
# Policy Page Categorization Tests
# =============================================================================


class TestPolicyCategorization:
    """Tests for policy/legal page categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_privacy_policy(self, categorizer: URLCategorizer) -> None:
        """Test /privacy-policy path."""
        category, _ = categorizer.categorize("https://example.com/privacy-policy")
        assert category == "policy"

    def test_terms_of_service(self, categorizer: URLCategorizer) -> None:
        """Test /terms-of-service path."""
        category, _ = categorizer.categorize("https://example.com/terms-of-service")
        assert category == "policy"

    def test_terms_and_conditions(self, categorizer: URLCategorizer) -> None:
        """Test /terms-and-conditions path."""
        category, _ = categorizer.categorize("https://example.com/terms-and-conditions")
        assert category == "policy"

    def test_legal_path(self, categorizer: URLCategorizer) -> None:
        """Test /legal path."""
        category, _ = categorizer.categorize("https://example.com/legal")
        assert category == "policy"

    def test_refund_policy(self, categorizer: URLCategorizer) -> None:
        """Test /refund-policy path."""
        category, _ = categorizer.categorize("https://example.com/refund-policy")
        assert category == "policy"

    def test_shipping_policy(self, categorizer: URLCategorizer) -> None:
        """Test /shipping-policy path."""
        category, _ = categorizer.categorize("https://example.com/shipping-policy")
        assert category == "policy"

    def test_cookie_policy(self, categorizer: URLCategorizer) -> None:
        """Test /cookie-policy path."""
        category, _ = categorizer.categorize("https://example.com/cookie-policy")
        assert category == "policy"

    def test_gdpr(self, categorizer: URLCategorizer) -> None:
        """Test /gdpr path."""
        category, _ = categorizer.categorize("https://example.com/gdpr")
        assert category == "policy"

    def test_policies_nested(self, categorizer: URLCategorizer) -> None:
        """Test /policies/privacy nested path."""
        category, _ = categorizer.categorize("https://example.com/policies/privacy")
        assert category == "policy"


# =============================================================================
# About Page Categorization Tests
# =============================================================================


class TestAboutCategorization:
    """Tests for about page categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_about_page(self, categorizer: URLCategorizer) -> None:
        """Test /about path."""
        category, _ = categorizer.categorize("https://example.com/about")
        assert category == "about"

    def test_about_us(self, categorizer: URLCategorizer) -> None:
        """Test /about-us path."""
        category, _ = categorizer.categorize("https://example.com/about-us")
        assert category == "about"

    def test_company_page(self, categorizer: URLCategorizer) -> None:
        """Test /company path."""
        category, _ = categorizer.categorize("https://example.com/company")
        assert category == "about"

    def test_team_page(self, categorizer: URLCategorizer) -> None:
        """Test /team path."""
        category, _ = categorizer.categorize("https://example.com/team")
        assert category == "about"

    def test_our_story(self, categorizer: URLCategorizer) -> None:
        """Test /our-story path."""
        category, _ = categorizer.categorize("https://example.com/our-story")
        assert category == "about"


# =============================================================================
# Contact Page Categorization Tests
# =============================================================================


class TestContactCategorization:
    """Tests for contact page categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_contact_page(self, categorizer: URLCategorizer) -> None:
        """Test /contact path."""
        category, _ = categorizer.categorize("https://example.com/contact")
        assert category == "contact"

    def test_contact_us(self, categorizer: URLCategorizer) -> None:
        """Test /contact-us path."""
        category, _ = categorizer.categorize("https://example.com/contact-us")
        assert category == "contact"

    def test_locations(self, categorizer: URLCategorizer) -> None:
        """Test /locations path."""
        category, _ = categorizer.categorize("https://example.com/locations")
        assert category == "contact"

    def test_store_locator(self, categorizer: URLCategorizer) -> None:
        """Test /store-locator path."""
        category, _ = categorizer.categorize("https://example.com/store-locator")
        assert category == "contact"


# =============================================================================
# FAQ/Help Page Categorization Tests
# =============================================================================


class TestFAQCategorization:
    """Tests for FAQ/help page categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_faq_page(self, categorizer: URLCategorizer) -> None:
        """Test /faq path."""
        category, _ = categorizer.categorize("https://example.com/faq")
        assert category == "faq"

    def test_help_page(self, categorizer: URLCategorizer) -> None:
        """Test /help path."""
        category, _ = categorizer.categorize("https://example.com/help")
        assert category == "faq"

    def test_support_page(self, categorizer: URLCategorizer) -> None:
        """Test /support path."""
        category, _ = categorizer.categorize("https://example.com/support")
        assert category == "faq"

    def test_help_topic(self, categorizer: URLCategorizer) -> None:
        """Test /help/topic path."""
        category, _ = categorizer.categorize("https://example.com/help/shipping-questions")
        assert category == "faq"


# =============================================================================
# Account/Cart Page Categorization Tests
# =============================================================================


class TestAccountCartCategorization:
    """Tests for account and cart page categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_account_page(self, categorizer: URLCategorizer) -> None:
        """Test /account path."""
        category, _ = categorizer.categorize("https://example.com/account")
        assert category == "account"

    def test_login_page(self, categorizer: URLCategorizer) -> None:
        """Test /login path."""
        category, _ = categorizer.categorize("https://example.com/login")
        assert category == "account"

    def test_signup_page(self, categorizer: URLCategorizer) -> None:
        """Test /signup path."""
        category, _ = categorizer.categorize("https://example.com/signup")
        assert category == "account"

    def test_cart_page(self, categorizer: URLCategorizer) -> None:
        """Test /cart path."""
        category, _ = categorizer.categorize("https://example.com/cart")
        assert category == "cart"

    def test_checkout_page(self, categorizer: URLCategorizer) -> None:
        """Test /checkout path."""
        category, _ = categorizer.categorize("https://example.com/checkout")
        assert category == "cart"


# =============================================================================
# Search Page Categorization Tests
# =============================================================================


class TestSearchCategorization:
    """Tests for search page categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_search_page(self, categorizer: URLCategorizer) -> None:
        """Test /search path."""
        category, _ = categorizer.categorize("https://example.com/search")
        assert category == "search"

    def test_search_with_query(self, categorizer: URLCategorizer) -> None:
        """Test /search?q=... path."""
        category, _ = categorizer.categorize("https://example.com/search?q=widgets")
        assert category == "search"


# =============================================================================
# Default/Other Category Tests
# =============================================================================


class TestDefaultCategorization:
    """Tests for default/other category."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_unknown_path(self, categorizer: URLCategorizer) -> None:
        """Test unknown path gets default category."""
        category, pattern = categorizer.categorize("https://example.com/random/unknown/path")
        assert category == "other"
        assert pattern is None

    def test_empty_url(self, categorizer: URLCategorizer) -> None:
        """Test empty URL gets default category."""
        category, pattern = categorizer.categorize("")
        assert category == "other"
        assert pattern is None

    def test_whitespace_url(self, categorizer: URLCategorizer) -> None:
        """Test whitespace URL gets default category."""
        category, pattern = categorizer.categorize("   ")
        assert category == "other"
        assert pattern is None


# =============================================================================
# Batch Categorization Tests
# =============================================================================


class TestBatchCategorization:
    """Tests for batch URL categorization."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_categorize_many(self, categorizer: URLCategorizer) -> None:
        """Test categorizing multiple URLs."""
        urls = [
            "https://example.com/",
            "https://example.com/products/widget",
            "https://example.com/blog/post",
            "https://example.com/privacy-policy",
        ]
        results = categorizer.categorize_many(urls)

        assert results["https://example.com/"] == "homepage"
        assert results["https://example.com/products/widget"] == "product"
        assert results["https://example.com/blog/post"] == "blog"
        assert results["https://example.com/privacy-policy"] == "policy"

    def test_categorize_many_empty_list(self, categorizer: URLCategorizer) -> None:
        """Test categorizing empty list."""
        results = categorizer.categorize_many([])
        assert results == {}


# =============================================================================
# Categorize Page Tests
# =============================================================================


class TestCategorizePage:
    """Tests for categorize_page method with additional context."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_categorize_page_basic(self, categorizer: URLCategorizer) -> None:
        """Test basic page categorization."""
        category = categorizer.categorize_page("https://example.com/products/widget")
        assert category == "product"

    def test_categorize_page_with_title(self, categorizer: URLCategorizer) -> None:
        """Test categorization with title context."""
        category = categorizer.categorize_page(
            url="https://example.com/",
            title="Welcome to Example Store",
        )
        assert category == "homepage"


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_categorize_url_function(self) -> None:
        """Test categorize_url convenience function."""
        assert categorize_url("https://example.com/products/widget") == "product"
        assert categorize_url("https://example.com/blog/post") == "blog"
        assert categorize_url("https://example.com/privacy-policy") == "policy"

    def test_get_url_categorizer_singleton(self) -> None:
        """Test get_url_categorizer returns singleton."""
        cat1 = get_url_categorizer()
        cat2 = get_url_categorizer()
        assert cat1 is cat2


# =============================================================================
# Valid Categories Constant Tests
# =============================================================================


class TestValidCategories:
    """Tests for VALID_PAGE_CATEGORIES constant."""

    def test_contains_expected_categories(self) -> None:
        """Test that all expected categories are present."""
        expected = {
            "homepage", "product", "collection", "blog", "policy",
            "about", "contact", "faq", "account", "cart", "search", "other",
        }
        assert expected == VALID_PAGE_CATEGORIES

    def test_is_frozenset(self) -> None:
        """Test that VALID_PAGE_CATEGORIES is immutable."""
        assert isinstance(VALID_PAGE_CATEGORIES, frozenset)


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for URLCategorizer."""

    @pytest.fixture
    def categorizer(self) -> URLCategorizer:
        return URLCategorizer()

    def test_url_with_query_params(self, categorizer: URLCategorizer) -> None:
        """Test URL with query parameters."""
        category, _ = categorizer.categorize(
            "https://example.com/products/widget?color=red&size=large"
        )
        assert category == "product"

    def test_url_with_fragment(self, categorizer: URLCategorizer) -> None:
        """Test URL with fragment."""
        category, _ = categorizer.categorize(
            "https://example.com/blog/post#comments"
        )
        assert category == "blog"

    def test_url_with_trailing_slash(self, categorizer: URLCategorizer) -> None:
        """Test URL with trailing slash."""
        category, _ = categorizer.categorize("https://example.com/products/widget/")
        assert category == "product"

    def test_url_uppercase_path(self, categorizer: URLCategorizer) -> None:
        """Test URL with uppercase path (case-insensitive matching)."""
        category, _ = categorizer.categorize("https://example.com/PRODUCTS/WIDGET")
        assert category == "product"

    def test_just_path(self, categorizer: URLCategorizer) -> None:
        """Test categorizing just a path (not full URL)."""
        category, _ = categorizer.categorize("/products/widget")
        assert category == "product"

    def test_relative_path_without_leading_slash(self, categorizer: URLCategorizer) -> None:
        """Test that relative paths without leading / fall back to default.

        Note: urlparse treats paths without leading / ambiguously, so these
        are categorized as 'other'. Paths should start with / for correct
        categorization.
        """
        category, _ = categorizer.categorize("products/widget")
        # Without leading /, urlparse interprets this ambiguously
        assert category == "other"

    def test_product_collection_priority(self, categorizer: URLCategorizer) -> None:
        """Test that product has higher priority than collection for nested shop paths."""
        # /shop/category/item should be product (more specific)
        category, _ = categorizer.categorize("https://example.com/shop/electronics/laptop")
        assert category == "product"

        # /shop/category should be collection (less specific)
        category, _ = categorizer.categorize("https://example.com/shop/electronics")
        assert category == "collection"
