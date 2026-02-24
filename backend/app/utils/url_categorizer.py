"""URL pattern rules for categorizing crawled pages.

Provides intelligent URL categorization based on common URL patterns:
- Collection pages (/collections/*, /category/*, /shop/*)
- Product pages (/products/*, /product/*, /p/*)
- Blog pages (/blog/*, /news/*, /articles/*)
- Policy pages (/policy/*, /policies/*, /legal/*, /terms/*, /privacy/*)
- Homepage (/)
- About pages (/about/*, /about-us/*)
- Contact pages (/contact/*, /contact-us/*)
- FAQ/Help pages (/faq/*, /help/*, /support/*)

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger("url_categorizer")

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000


@dataclass
class CategoryRule:
    """A single URL pattern rule for categorization.

    Attributes:
        category: The category name to assign (e.g., 'product', 'collection')
        patterns: List of regex patterns that match this category
        priority: Higher priority rules are evaluated first (default: 0)
        description: Human-readable description of the rule
    """

    category: str
    patterns: list[str]
    priority: int = 0
    description: str = ""

    def __post_init__(self) -> None:
        """Compile regex patterns for efficiency."""
        self._compiled_patterns: list[re.Pattern[str]] = []
        for pattern in self.patterns:
            try:
                self._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(
                    "Invalid regex pattern in category rule",
                    extra={
                        "category": self.category,
                        "pattern": pattern,
                        "error": str(e),
                    },
                )

    def matches(self, path: str) -> tuple[bool, str | None]:
        """Check if a URL path matches any of this rule's patterns.

        Args:
            path: The URL path to check

        Returns:
            Tuple of (matches, matched_pattern)
        """
        for i, compiled in enumerate(self._compiled_patterns):
            if compiled.search(path):
                return True, self.patterns[i]
        return False, None


# Default category rules for common website patterns
# Ordered by priority (higher = checked first)
DEFAULT_CATEGORY_RULES: list[CategoryRule] = [
    # Homepage - highest priority, exact match
    CategoryRule(
        category="homepage",
        patterns=[
            r"^/?$",  # Exact root
            r"^/index\.html?$",  # index.html or index.htm
            r"^/home/?$",  # /home or /home/
        ],
        priority=100,
        description="Homepage/landing page",
    ),
    # Product pages - common ecommerce patterns
    CategoryRule(
        category="product",
        patterns=[
            r"^/products?/[^/]+/?$",  # /product/item or /products/item
            r"^/p/[^/]+/?$",  # Short product URL /p/item
            r"^/shop/[^/]+/[^/]+/?$",  # /shop/category/item
            r"^/item/[^/]+/?$",  # /item/item-name
            r"^/merchandise/[^/]+/?$",  # /merchandise/item
            r"^/sku/[^/]+/?$",  # /sku/12345
        ],
        priority=80,
        description="Individual product pages",
    ),
    # Collection/category pages - lists of products
    CategoryRule(
        category="collection",
        patterns=[
            r"^/collections?/[^/]+/?$",  # /collection/summer or /collections/summer
            r"^/collections?/?$",  # /collections (listing all)
            r"^/categor(y|ies)/[^/]*/?$",  # /category/shoes or /categories/shoes
            r"^/shop/[^/]+/?$",  # /shop/category (but not /shop/category/item)
            r"^/shop/?$",  # /shop main page
            r"^/browse/[^/]*/?$",  # /browse/category
            r"^/catalog/[^/]*/?$",  # /catalog/category
            r"^/store/[^/]*/?$",  # /store/category
        ],
        priority=70,
        description="Collection/category listing pages",
    ),
    # Blog/content pages
    CategoryRule(
        category="blog",
        patterns=[
            r"^/blog/?$",  # Blog listing
            r"^/blog/[^/]+/?$",  # Individual blog post
            r"^/blog/category/[^/]+/?$",  # Blog category
            r"^/blog/tag/[^/]+/?$",  # Blog tag
            r"^/news/?$",  # News listing
            r"^/news/[^/]+/?$",  # Individual news article
            r"^/articles?/?$",  # Articles listing
            r"^/articles?/[^/]+/?$",  # Individual article
            r"^/posts?/[^/]+/?$",  # /post/slug or /posts/slug
            r"^/stories?/[^/]+/?$",  # /story/slug or /stories/slug
            r"^/insights?/[^/]*/?$",  # /insights or /insights/article
            r"^/resources?/[^/]*/?$",  # /resources or /resources/article
        ],
        priority=60,
        description="Blog and content pages",
    ),
    # Policy/legal pages - important for compliance
    CategoryRule(
        category="policy",
        patterns=[
            r"^/polic(y|ies)/[^/]*/?$",  # /policy/privacy or /policies/terms
            r"^/privacy-policy/?$",  # /privacy-policy
            r"^/privacy/?$",  # /privacy
            r"^/terms-of-service/?$",  # /terms-of-service
            r"^/terms-and-conditions/?$",  # /terms-and-conditions
            r"^/terms/?$",  # /terms
            r"^/tos/?$",  # /tos
            r"^/legal/?$",  # /legal
            r"^/legal/[^/]+/?$",  # /legal/privacy
            r"^/refund-policy/?$",  # /refund-policy
            r"^/refund/?$",  # /refund
            r"^/shipping-policy/?$",  # /shipping-policy
            r"^/shipping/?$",  # /shipping (if just info page)
            r"^/returns?(-policy)?/?$",  # /return or /returns or /return-policy
            r"^/cookie-policy/?$",  # /cookie-policy
            r"^/cookies?/?$",  # /cookie or /cookies
            r"^/gdpr/?$",  # /gdpr
            r"^/ccpa/?$",  # /ccpa
            r"^/accessibility/?$",  # /accessibility
            r"^/disclaimer/?$",  # /disclaimer
        ],
        priority=50,
        description="Policy and legal pages",
    ),
    # About pages
    CategoryRule(
        category="about",
        patterns=[
            r"^/about(-us)?/?$",  # /about or /about-us
            r"^/about/[^/]+/?$",  # /about/team
            r"^/company/?$",  # /company
            r"^/team/?$",  # /team
            r"^/our-story/?$",  # /our-story
            r"^/who-we-are/?$",  # /who-we-are
            r"^/mission/?$",  # /mission
            r"^/values/?$",  # /values
            r"^/history/?$",  # /history
        ],
        priority=40,
        description="About and company pages",
    ),
    # Contact pages
    CategoryRule(
        category="contact",
        patterns=[
            r"^/contact(-us)?/?$",  # /contact or /contact-us
            r"^/get-in-touch/?$",  # /get-in-touch
            r"^/reach-us/?$",  # /reach-us
            r"^/locations?/?$",  # /location or /locations
            r"^/store-locator/?$",  # /store-locator
            r"^/find-us/?$",  # /find-us
        ],
        priority=40,
        description="Contact and location pages",
    ),
    # FAQ/Help pages
    CategoryRule(
        category="faq",
        patterns=[
            r"^/faq/?$",  # /faq
            r"^/faqs?/[^/]*/?$",  # /faq/category or /faqs/
            r"^/help/?$",  # /help
            r"^/help/[^/]+/?$",  # /help/topic
            r"^/help-center/?$",  # /help-center
            r"^/support/?$",  # /support
            r"^/support/[^/]+/?$",  # /support/topic
            r"^/knowledge-base/?$",  # /knowledge-base
            r"^/kb/[^/]*/?$",  # /kb/article
            r"^/how-to/[^/]*/?$",  # /how-to/guide
            r"^/guides?/[^/]*/?$",  # /guide/topic or /guides/topic
            r"^/tutorials?/[^/]*/?$",  # /tutorial/topic or /tutorials/topic
        ],
        priority=35,
        description="FAQ and help pages",
    ),
    # Account/auth pages
    CategoryRule(
        category="account",
        patterns=[
            r"^/account/?$",  # /account
            r"^/account/[^/]+/?$",  # /account/settings
            r"^/my-account/?$",  # /my-account
            r"^/login/?$",  # /login
            r"^/signin/?$",  # /signin
            r"^/sign-in/?$",  # /sign-in
            r"^/register/?$",  # /register
            r"^/signup/?$",  # /signup
            r"^/sign-up/?$",  # /sign-up
            r"^/forgot-password/?$",  # /forgot-password
            r"^/reset-password/?$",  # /reset-password
            r"^/profile/?$",  # /profile
            r"^/dashboard/?$",  # /dashboard
            r"^/orders?/?$",  # /order or /orders
            r"^/wishlist/?$",  # /wishlist
        ],
        priority=30,
        description="Account and authentication pages",
    ),
    # Cart/checkout pages
    CategoryRule(
        category="cart",
        patterns=[
            r"^/cart/?$",  # /cart
            r"^/bag/?$",  # /bag
            r"^/basket/?$",  # /basket
            r"^/checkout/?$",  # /checkout
            r"^/checkout/[^/]+/?$",  # /checkout/step
        ],
        priority=30,
        description="Shopping cart and checkout pages",
    ),
    # Search pages
    CategoryRule(
        category="search",
        patterns=[
            r"^/search/?",  # /search or /search?q=...
            r"^/s\?",  # Short search /s?q=...
            r"^/find/?",  # /find?q=...
        ],
        priority=20,
        description="Search results pages",
    ),
]


class URLCategorizer:
    """Categorizes URLs based on configurable pattern rules.

    Uses a priority-based system where higher priority rules are evaluated first.
    Falls back to 'other' category if no rules match.

    Example usage:
        categorizer = URLCategorizer()

        # Categorize a URL
        category, matched_rule = categorizer.categorize("https://example.com/products/widget")
        # Returns: ("product", "/products?/[^/]+/?$")

        # Categorize with page context
        category = categorizer.categorize_page(
            url="https://example.com/",
            title="Welcome to Example Store",
        )
        # Returns: "homepage"
    """

    def __init__(
        self,
        rules: list[CategoryRule] | None = None,
        default_category: str = "other",
    ) -> None:
        """Initialize the categorizer with rules.

        Args:
            rules: List of CategoryRule objects. Uses DEFAULT_CATEGORY_RULES if None.
            default_category: Category to assign when no rules match.
        """
        logger.debug(
            "URLCategorizer.__init__ called",
            extra={
                "rule_count": len(rules) if rules else len(DEFAULT_CATEGORY_RULES),
                "default_category": default_category,
            },
        )

        self._rules = rules if rules is not None else DEFAULT_CATEGORY_RULES.copy()
        self._default_category = default_category

        # Sort rules by priority (highest first)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

        logger.debug(
            "URLCategorizer initialized",
            extra={
                "rule_count": len(self._rules),
                "categories": list({r.category for r in self._rules}),
            },
        )

    @property
    def rules(self) -> list[CategoryRule]:
        """Get the categorization rules (read-only copy)."""
        return self._rules.copy()

    @property
    def default_category(self) -> str:
        """Get the default category."""
        return self._default_category

    @property
    def categories(self) -> set[str]:
        """Get all available categories."""
        categories = {r.category for r in self._rules}
        categories.add(self._default_category)
        return categories

    def add_rule(self, rule: CategoryRule) -> None:
        """Add a new categorization rule.

        Args:
            rule: The CategoryRule to add.
        """
        logger.debug(
            "Adding category rule",
            extra={
                "category": rule.category,
                "pattern_count": len(rule.patterns),
                "priority": rule.priority,
            },
        )

        self._rules.append(rule)
        # Re-sort by priority
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def categorize(self, url: str) -> tuple[str, str | None]:
        """Categorize a URL based on its path pattern.

        Args:
            url: The URL to categorize (full URL or just path).

        Returns:
            Tuple of (category, matched_pattern or None)
        """
        start_time = time.monotonic()
        logger.debug(
            "categorize() called",
            extra={"url": url[:200] if url else ""},
        )

        if not url or not url.strip():
            logger.warning(
                "Categorization failed: empty URL",
                extra={"field": "url", "rejected_value": repr(url)},
            )
            return self._default_category, None

        try:
            # Extract path from URL
            parsed = urlparse(url.strip())
            path = parsed.path or "/"

            # Normalize path (remove trailing slash except for root)
            if len(path) > 1 and path.endswith("/"):
                path = path.rstrip("/")

            # Check each rule in priority order
            for rule in self._rules:
                matches, pattern = rule.matches(path)
                if matches:
                    duration_ms = (time.monotonic() - start_time) * 1000
                    logger.debug(
                        "URL categorized",
                        extra={
                            "url": url[:200],
                            "path": path,
                            "category": rule.category,
                            "matched_pattern": pattern,
                            "duration_ms": round(duration_ms, 2),
                        },
                    )

                    if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                        logger.warning(
                            "Slow URL categorization",
                            extra={
                                "url": url[:200],
                                "duration_ms": round(duration_ms, 2),
                            },
                        )

                    return rule.category, pattern

            # No rule matched
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "URL categorized as default",
                extra={
                    "url": url[:200],
                    "path": path,
                    "category": self._default_category,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return self._default_category, None

        except Exception as e:
            logger.error(
                "Categorization failed with exception",
                extra={
                    "url": url[:200] if url else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return self._default_category, None

    def categorize_page(
        self,
        url: str,
        title: str | None = None,
        content_hints: dict[str, Any] | None = None,
    ) -> str:
        """Categorize a page using URL and optional additional context.

        This method extends basic URL categorization with optional page context
        like title and content hints. Currently uses URL-based categorization
        with potential for future enhancements using title/content analysis.

        Args:
            url: The page URL to categorize.
            title: Optional page title (for future enhancement).
            content_hints: Optional content hints dict (for future enhancement).

        Returns:
            The category string.
        """
        logger.debug(
            "categorize_page() called",
            extra={
                "url": url[:200] if url else "",
                "has_title": title is not None,
                "has_content_hints": content_hints is not None,
            },
        )

        # Currently uses URL-based categorization
        # Future: could incorporate title/content analysis
        category, _ = self.categorize(url)

        # Log additional context for debugging
        if title:
            logger.debug(
                "Page categorized with context",
                extra={
                    "url": url[:200] if url else "",
                    "title": title[:100] if title else None,
                    "category": category,
                },
            )

        return category

    def categorize_many(
        self,
        urls: list[str],
    ) -> dict[str, str]:
        """Categorize multiple URLs efficiently.

        Args:
            urls: List of URLs to categorize.

        Returns:
            Dict mapping URL to category.
        """
        start_time = time.monotonic()
        logger.debug(
            "categorize_many() called",
            extra={"url_count": len(urls)},
        )

        results: dict[str, str] = {}
        category_counts: dict[str, int] = {}

        for url in urls:
            category, _ = self.categorize(url)
            results[url] = category
            category_counts[category] = category_counts.get(category, 0) + 1

        duration_ms = (time.monotonic() - start_time) * 1000
        logger.debug(
            "categorize_many() completed",
            extra={
                "url_count": len(urls),
                "category_counts": category_counts,
                "duration_ms": round(duration_ms, 2),
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch categorization",
                extra={
                    "url_count": len(urls),
                    "duration_ms": round(duration_ms, 2),
                },
            )

        return results

    def get_rule_for_category(self, category: str) -> CategoryRule | None:
        """Get the rule definition for a category.

        Args:
            category: The category to look up.

        Returns:
            CategoryRule or None if not found.
        """
        for rule in self._rules:
            if rule.category == category:
                return rule
        return None


# Default instance for convenience
_default_categorizer: URLCategorizer | None = None


def get_url_categorizer() -> URLCategorizer:
    """Get the default URLCategorizer instance (singleton).

    Returns:
        Default URLCategorizer instance.
    """
    global _default_categorizer
    if _default_categorizer is None:
        _default_categorizer = URLCategorizer()
    return _default_categorizer


def categorize_url(url: str) -> str:
    """Convenience function to categorize a URL.

    Args:
        url: The URL to categorize.

    Returns:
        The category string.

    Example:
        >>> categorize_url("https://example.com/products/widget")
        'product'
        >>> categorize_url("https://example.com/blog/my-post")
        'blog'
        >>> categorize_url("https://example.com/privacy-policy")
        'policy'
    """
    categorizer = get_url_categorizer()
    category, _ = categorizer.categorize(url)
    return category


# Valid categories constant for validation
VALID_PAGE_CATEGORIES = frozenset({
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
})
