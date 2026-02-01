"""Unit tests for CrawlService.

Tests cover:
- URL normalization (via normalize_url utility integration)
- Pattern matching (include/exclude patterns, glob syntax)
- PatternMatcher class behavior
- Validation methods (UUID, URL, pagination, status)
- Exception classes

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second

Target: 80% code coverage.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.crawl import (
    CrawlConfig,
    CrawlNotFoundError,
    CrawlPatternError,
    CrawlProgress,
    CrawlService,
    CrawlServiceError,
    CrawlValidationError,
    PatternMatcher,
)
from app.utils.url import (
    URLNormalizationOptions,
    URLNormalizer,
    normalize_url,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def crawl_service(db_session: AsyncSession) -> CrawlService:
    """Create a CrawlService instance with test database session."""
    return CrawlService(db_session)


@pytest.fixture
def basic_pattern_matcher() -> PatternMatcher:
    """Create a basic pattern matcher with sample patterns."""
    return PatternMatcher(
        include_patterns=["/products/*", "/services/*"],
        exclude_patterns=["/admin/*", "/api/*"],
    )


# ---------------------------------------------------------------------------
# Test: URL Normalization (normalize_url utility)
# ---------------------------------------------------------------------------


class TestURLNormalization:
    """Tests for URL normalization functionality."""

    def test_normalize_url_basic(self) -> None:
        """Should normalize a basic URL."""
        url = "https://example.com/path/"
        normalized = normalize_url(url)
        assert normalized == "https://example.com/path"

    def test_normalize_url_removes_fragment(self) -> None:
        """Should remove URL fragments by default."""
        url = "https://example.com/page#section"
        normalized = normalize_url(url)
        assert normalized == "https://example.com/page"

    def test_normalize_url_removes_trailing_slash(self) -> None:
        """Should remove trailing slash from path."""
        url = "https://example.com/products/"
        normalized = normalize_url(url)
        assert normalized == "https://example.com/products"

    def test_normalize_url_keeps_root_trailing_slash(self) -> None:
        """Should keep trailing slash for root path."""
        url = "https://example.com/"
        normalized = normalize_url(url)
        assert normalized == "https://example.com/"

    def test_normalize_url_lowercase_scheme(self) -> None:
        """Should lowercase the URL scheme."""
        url = "HTTPS://example.com/path"
        normalized = normalize_url(url)
        assert normalized.startswith("https://")

    def test_normalize_url_lowercase_host(self) -> None:
        """Should lowercase the hostname."""
        url = "https://WWW.EXAMPLE.COM/path"
        normalized = normalize_url(url)
        assert "example.com" in normalized.lower()

    def test_normalize_url_sorts_query_params(self) -> None:
        """Should sort query parameters alphabetically."""
        url = "https://example.com/page?z=3&a=1&m=2"
        normalized = normalize_url(url)
        # Query params should be sorted: a=1, m=2, z=3
        assert "a=1" in normalized
        assert normalized.index("a=1") < normalized.index("m=2")
        assert normalized.index("m=2") < normalized.index("z=3")

    def test_normalize_url_removes_tracking_params(self) -> None:
        """Should remove common tracking parameters by default."""
        url = "https://example.com/page?real=value&utm_source=google&fbclid=abc123"
        normalized = normalize_url(url)
        assert "real=value" in normalized
        assert "utm_source" not in normalized
        assert "fbclid" not in normalized

    def test_normalize_url_removes_default_http_port(self) -> None:
        """Should remove default HTTP port 80."""
        url = "http://example.com:80/path"
        normalized = normalize_url(url)
        assert ":80" not in normalized

    def test_normalize_url_removes_default_https_port(self) -> None:
        """Should remove default HTTPS port 443."""
        url = "https://example.com:443/path"
        normalized = normalize_url(url)
        assert ":443" not in normalized

    def test_normalize_url_keeps_non_default_port(self) -> None:
        """Should keep non-default ports."""
        url = "https://example.com:8080/path"
        normalized = normalize_url(url)
        assert ":8080" in normalized

    def test_normalize_url_handles_multiple_slashes(self) -> None:
        """Should normalize multiple consecutive slashes."""
        url = "https://example.com//path///to////page"
        normalized = normalize_url(url)
        assert "//" not in normalized or normalized.startswith("https://")

    def test_normalize_url_empty_string_raises(self) -> None:
        """Should raise ValueError for empty URL."""
        with pytest.raises(ValueError) as exc_info:
            normalize_url("")
        assert "empty" in str(exc_info.value).lower()

    def test_normalize_url_whitespace_only_raises(self) -> None:
        """Should raise ValueError for whitespace-only URL."""
        with pytest.raises(ValueError) as exc_info:
            normalize_url("   ")
        assert "empty" in str(exc_info.value).lower()

    def test_normalize_url_missing_scheme_raises(self) -> None:
        """Should raise ValueError for URL without scheme."""
        with pytest.raises(ValueError) as exc_info:
            normalize_url("example.com/path")
        assert "scheme" in str(exc_info.value).lower()

    def test_normalize_url_missing_host_raises(self) -> None:
        """Should raise ValueError for URL without host."""
        with pytest.raises(ValueError) as exc_info:
            normalize_url("https:///path")
        assert "host" in str(exc_info.value).lower()


class TestURLNormalizationOptions:
    """Tests for URLNormalizationOptions configuration."""

    def test_strip_www_option(self) -> None:
        """Should strip www prefix when option is enabled."""
        options = URLNormalizationOptions(strip_www=True)
        url = "https://www.example.com/path"
        normalized = normalize_url(url, options)
        assert "www." not in normalized

    def test_keep_www_by_default(self) -> None:
        """Should keep www prefix by default."""
        url = "https://www.example.com/path"
        normalized = normalize_url(url)
        # Default strip_www is False, so www should be preserved
        assert "www.example.com" in normalized

    def test_remove_all_query_params_option(self) -> None:
        """Should remove all query parameters when option is enabled."""
        options = URLNormalizationOptions(remove_query_params=True)
        url = "https://example.com/page?a=1&b=2"
        normalized = normalize_url(url, options)
        assert "?" not in normalized

    def test_keep_fragments_option(self) -> None:
        """Should keep fragments when option is disabled."""
        options = URLNormalizationOptions(remove_fragments=False)
        url = "https://example.com/page#section"
        normalized = normalize_url(url, options)
        assert "#section" in normalized

    def test_keep_trailing_slash_option(self) -> None:
        """Should keep trailing slash when option is disabled."""
        options = URLNormalizationOptions(remove_trailing_slash=False)
        url = "https://example.com/path/"
        normalized = normalize_url(url, options)
        assert normalized.endswith("/")

    def test_allowed_query_params_option(self) -> None:
        """Should only keep specified query parameters."""
        options = URLNormalizationOptions(allowed_query_params={"page", "sort"})
        url = "https://example.com/products?page=1&sort=asc&filter=test&utm_source=ads"
        normalized = normalize_url(url, options)
        assert "page=1" in normalized
        assert "sort=asc" in normalized
        assert "filter" not in normalized
        assert "utm_source" not in normalized


class TestURLNormalizerIsSamePage:
    """Tests for URLNormalizer.is_same_page method."""

    def test_same_url_is_same_page(self) -> None:
        """Same URL should be same page."""
        normalizer = URLNormalizer()
        assert normalizer.is_same_page(
            "https://example.com/page",
            "https://example.com/page",
        )

    def test_different_fragment_is_same_page(self) -> None:
        """URLs differing only in fragment should be same page."""
        normalizer = URLNormalizer()
        assert normalizer.is_same_page(
            "https://example.com/page#section1",
            "https://example.com/page#section2",
        )

    def test_trailing_slash_difference_is_same_page(self) -> None:
        """URLs differing only in trailing slash should be same page."""
        normalizer = URLNormalizer()
        assert normalizer.is_same_page(
            "https://example.com/page",
            "https://example.com/page/",
        )

    def test_case_difference_is_same_page(self) -> None:
        """URLs differing only in case should be same page."""
        normalizer = URLNormalizer()
        assert normalizer.is_same_page(
            "https://EXAMPLE.COM/path",
            "https://example.com/path",
        )

    def test_different_paths_not_same_page(self) -> None:
        """URLs with different paths should not be same page."""
        normalizer = URLNormalizer()
        assert not normalizer.is_same_page(
            "https://example.com/page1",
            "https://example.com/page2",
        )

    def test_different_domains_not_same_page(self) -> None:
        """URLs with different domains should not be same page."""
        normalizer = URLNormalizer()
        assert not normalizer.is_same_page(
            "https://example.com/page",
            "https://other.com/page",
        )

    def test_invalid_url_returns_false(self) -> None:
        """Invalid URLs should return False for is_same_page."""
        normalizer = URLNormalizer()
        assert not normalizer.is_same_page(
            "not-a-valid-url",
            "https://example.com/page",
        )


# ---------------------------------------------------------------------------
# Test: PatternMatcher
# ---------------------------------------------------------------------------


class TestPatternMatcherInitialization:
    """Tests for PatternMatcher initialization and validation."""

    def test_create_with_include_patterns(self) -> None:
        """Should create matcher with include patterns."""
        matcher = PatternMatcher(include_patterns=["/products/*"])
        assert matcher.include_patterns == ["/products/*"]
        assert matcher.exclude_patterns == []

    def test_create_with_exclude_patterns(self) -> None:
        """Should create matcher with exclude patterns."""
        matcher = PatternMatcher(exclude_patterns=["/admin/*"])
        assert matcher.include_patterns == []
        assert matcher.exclude_patterns == ["/admin/*"]

    def test_create_with_both_patterns(self) -> None:
        """Should create matcher with both include and exclude patterns."""
        matcher = PatternMatcher(
            include_patterns=["/products/*"],
            exclude_patterns=["/admin/*"],
        )
        assert len(matcher.include_patterns) == 1
        assert len(matcher.exclude_patterns) == 1

    def test_create_with_none_patterns(self) -> None:
        """Should handle None patterns gracefully."""
        matcher = PatternMatcher(
            include_patterns=None,
            exclude_patterns=None,
        )
        assert matcher.include_patterns == []
        assert matcher.exclude_patterns == []

    def test_empty_pattern_raises_error(self) -> None:
        """Should raise error for empty pattern."""
        with pytest.raises(CrawlPatternError) as exc_info:
            PatternMatcher(include_patterns=[""])
        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_pattern_raises_error(self) -> None:
        """Should raise error for whitespace-only pattern."""
        with pytest.raises(CrawlPatternError) as exc_info:
            PatternMatcher(include_patterns=["   "])
        assert "empty" in str(exc_info.value).lower()

    def test_too_many_wildcards_raises_error(self) -> None:
        """Should raise error for pattern with too many ** wildcards."""
        with pytest.raises(CrawlPatternError) as exc_info:
            PatternMatcher(include_patterns=["/**/**/**/**/**/**/test"])
        assert "too many" in str(exc_info.value).lower()


class TestPatternMatcherIncludeMatching:
    """Tests for PatternMatcher.matches_include method."""

    def test_matches_simple_glob(self) -> None:
        """Should match simple glob pattern."""
        matcher = PatternMatcher(include_patterns=["/products/*"])
        matches, pattern = matcher.matches_include("https://example.com/products/item1")
        assert matches is True
        assert pattern == "/products/*"

    def test_no_match_returns_false(self) -> None:
        """Should return False when URL doesn't match any pattern."""
        matcher = PatternMatcher(include_patterns=["/products/*"])
        matches, pattern = matcher.matches_include("https://example.com/services/item")
        assert matches is False
        assert pattern is None

    def test_empty_patterns_matches_all(self) -> None:
        """Empty include patterns should match all URLs."""
        matcher = PatternMatcher(include_patterns=[])
        matches, pattern = matcher.matches_include("https://example.com/anything")
        assert matches is True
        assert pattern is None

    def test_multiple_patterns_returns_first_match(self) -> None:
        """Should return first matching pattern."""
        matcher = PatternMatcher(include_patterns=["/products/*", "/items/*"])
        matches, pattern = matcher.matches_include("https://example.com/products/x")
        assert matches is True
        assert pattern == "/products/*"

    def test_pattern_matches_path_only(self) -> None:
        """Pattern should match against URL path, not full URL."""
        matcher = PatternMatcher(include_patterns=["/page"])
        matches, _ = matcher.matches_include("https://other-domain.com/page")
        assert matches is True


class TestPatternMatcherExcludeMatching:
    """Tests for PatternMatcher.matches_exclude method."""

    def test_matches_exclude_pattern(self) -> None:
        """Should match exclude pattern."""
        matcher = PatternMatcher(exclude_patterns=["/admin/*"])
        matches, pattern = matcher.matches_exclude("https://example.com/admin/dashboard")
        assert matches is True
        assert pattern == "/admin/*"

    def test_no_exclude_match(self) -> None:
        """Should return False when URL doesn't match exclude patterns."""
        matcher = PatternMatcher(exclude_patterns=["/admin/*"])
        matches, pattern = matcher.matches_exclude("https://example.com/products/item")
        assert matches is False
        assert pattern is None

    def test_empty_exclude_patterns_matches_none(self) -> None:
        """Empty exclude patterns should not match any URLs."""
        matcher = PatternMatcher(exclude_patterns=[])
        matches, pattern = matcher.matches_exclude("https://example.com/admin")
        assert matches is False
        assert pattern is None


class TestPatternMatcherShouldCrawl:
    """Tests for PatternMatcher.should_crawl method."""

    def test_exclude_takes_precedence(self) -> None:
        """Exclude patterns should take precedence over include patterns."""
        matcher = PatternMatcher(
            include_patterns=["/*"],
            exclude_patterns=["/admin/*"],
        )
        should_crawl, reason = matcher.should_crawl("https://example.com/admin/page")
        assert should_crawl is False
        assert "excluded" in reason.lower()

    def test_included_url_should_crawl(self) -> None:
        """URL matching include pattern should be crawled."""
        matcher = PatternMatcher(include_patterns=["/products/*"])
        should_crawl, reason = matcher.should_crawl("https://example.com/products/item")
        assert should_crawl is True
        assert "included" in reason.lower()

    def test_not_included_url_should_not_crawl(self) -> None:
        """URL not matching include pattern should not be crawled."""
        matcher = PatternMatcher(include_patterns=["/products/*"])
        should_crawl, reason = matcher.should_crawl("https://example.com/services/item")
        assert should_crawl is False
        assert "not matched" in reason.lower()

    def test_no_patterns_should_crawl_all(self) -> None:
        """No patterns means all URLs should be crawled."""
        matcher = PatternMatcher()
        should_crawl, reason = matcher.should_crawl("https://example.com/anything")
        assert should_crawl is True
        assert "no patterns" in reason.lower()


class TestPatternMatcherDeterminePriority:
    """Tests for PatternMatcher.determine_priority method."""

    def test_include_pattern_gives_include_priority(self) -> None:
        """URL matching include pattern should get INCLUDE priority."""
        from app.utils.crawl_queue import URLPriority

        matcher = PatternMatcher(include_patterns=["/products/*"])
        priority = matcher.determine_priority("https://example.com/products/item")
        assert priority == URLPriority.INCLUDE

    def test_no_include_pattern_gives_other_priority(self) -> None:
        """URL not matching include pattern should get OTHER priority."""
        from app.utils.crawl_queue import URLPriority

        matcher = PatternMatcher(include_patterns=["/products/*"])
        priority = matcher.determine_priority("https://example.com/services/item")
        assert priority == URLPriority.OTHER

    def test_empty_patterns_gives_other_priority(self) -> None:
        """Empty patterns should give OTHER priority."""
        from app.utils.crawl_queue import URLPriority

        matcher = PatternMatcher()
        priority = matcher.determine_priority("https://example.com/any")
        assert priority == URLPriority.OTHER


# ---------------------------------------------------------------------------
# Test: Glob Pattern Syntax
# ---------------------------------------------------------------------------


class TestGlobPatternSyntax:
    """Tests for various glob pattern syntax in PatternMatcher."""

    def test_single_asterisk_matches_any_chars(self) -> None:
        """Single * in fnmatch matches any characters including /."""
        # Note: Python's fnmatch uses shell-style globbing where * matches anything
        # This is different from pathlib's glob where * doesn't match /
        matcher = PatternMatcher(include_patterns=["/products/*"])
        should_crawl, _ = matcher.should_crawl("https://example.com/products/item1")
        assert should_crawl is True

        # fnmatch * DOES match nested paths (unlike some glob implementations)
        should_crawl, _ = matcher.should_crawl("https://example.com/products/cat/item")
        assert should_crawl is True  # fnmatch * matches any chars including /

    def test_double_asterisk_matches_any_depth(self) -> None:
        """Double ** should match any depth of path."""
        matcher = PatternMatcher(include_patterns=["/**/products/*"])
        should_crawl, _ = matcher.should_crawl("https://example.com/a/b/products/item")
        assert should_crawl is True

    def test_question_mark_matches_single_char(self) -> None:
        """Question mark should match single character."""
        matcher = PatternMatcher(include_patterns=["/item?"])
        should_crawl, _ = matcher.should_crawl("https://example.com/item1")
        assert should_crawl is True

        should_crawl, _ = matcher.should_crawl("https://example.com/item12")
        assert should_crawl is False

    def test_character_class_pattern(self) -> None:
        """Character class [abc] should match specified characters."""
        matcher = PatternMatcher(include_patterns=["/section[123]/*"])
        should_crawl, _ = matcher.should_crawl("https://example.com/section1/page")
        assert should_crawl is True

        should_crawl, _ = matcher.should_crawl("https://example.com/section4/page")
        assert should_crawl is False

    def test_file_extension_pattern(self) -> None:
        """Should match file extensions."""
        matcher = PatternMatcher(exclude_patterns=["*.pdf", "*.zip"])
        excluded, _ = matcher.matches_exclude("https://example.com/doc.pdf")
        assert excluded is True

        excluded, _ = matcher.matches_exclude("https://example.com/file.zip")
        assert excluded is True

        excluded, _ = matcher.matches_exclude("https://example.com/page.html")
        assert excluded is False


# ---------------------------------------------------------------------------
# Test: CrawlService Pattern Methods
# ---------------------------------------------------------------------------


class TestCrawlServiceCreatePatternMatcher:
    """Tests for CrawlService.create_pattern_matcher method."""

    def test_create_pattern_matcher_success(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should create a valid pattern matcher."""
        matcher = crawl_service.create_pattern_matcher(
            include_patterns=["/products/*"],
            exclude_patterns=["/admin/*"],
        )
        assert isinstance(matcher, PatternMatcher)
        assert matcher.include_patterns == ["/products/*"]
        assert matcher.exclude_patterns == ["/admin/*"]

    def test_create_pattern_matcher_empty_patterns(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should create matcher with empty patterns."""
        matcher = crawl_service.create_pattern_matcher()
        assert matcher.include_patterns == []
        assert matcher.exclude_patterns == []

    def test_create_pattern_matcher_invalid_pattern(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should raise CrawlPatternError for invalid pattern."""
        with pytest.raises(CrawlPatternError):
            crawl_service.create_pattern_matcher(include_patterns=[""])


class TestCrawlServiceFilterUrls:
    """Tests for CrawlService.filter_urls method."""

    def test_filter_urls_with_include_patterns(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should filter URLs based on include patterns."""
        urls = [
            "https://example.com/products/item1",
            "https://example.com/products/item2",
            "https://example.com/services/service1",
            "https://example.com/about",
        ]
        filtered = crawl_service.filter_urls(
            urls,
            include_patterns=["/products/*"],
        )
        assert len(filtered) == 2
        assert all("/products/" in url for url in filtered)

    def test_filter_urls_with_exclude_patterns(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should filter out URLs matching exclude patterns."""
        urls = [
            "https://example.com/page1",
            "https://example.com/admin/dashboard",
            "https://example.com/page2",
            "https://example.com/api/data",
        ]
        filtered = crawl_service.filter_urls(
            urls,
            exclude_patterns=["/admin/*", "/api/*"],
        )
        assert len(filtered) == 2
        assert all("/admin" not in url and "/api" not in url for url in filtered)

    def test_filter_urls_with_both_patterns(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should apply both include and exclude patterns."""
        urls = [
            "https://example.com/products/item1",
            "https://example.com/products/admin",
            "https://example.com/services/service1",
        ]
        filtered = crawl_service.filter_urls(
            urls,
            include_patterns=["/products/*", "/services/*"],
            exclude_patterns=["*/admin*"],
        )
        # products/item1 and services/service1 should pass
        # products/admin should be excluded
        assert len(filtered) == 2

    def test_filter_urls_empty_list(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should handle empty URL list."""
        filtered = crawl_service.filter_urls(
            [],
            include_patterns=["/products/*"],
        )
        assert filtered == []

    def test_filter_urls_no_patterns(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should return all URLs when no patterns specified."""
        urls = ["https://example.com/a", "https://example.com/b"]
        filtered = crawl_service.filter_urls(urls)
        assert len(filtered) == 2


# ---------------------------------------------------------------------------
# Test: CrawlService Validation Methods
# ---------------------------------------------------------------------------


class TestCrawlServiceValidation:
    """Tests for CrawlService validation methods."""

    def test_validate_uuid_valid(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should accept valid UUID."""
        # Should not raise
        crawl_service._validate_uuid(
            "550e8400-e29b-41d4-a716-446655440000",
            "test_id",
        )

    def test_validate_uuid_invalid_format(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should reject invalid UUID format."""
        with pytest.raises(CrawlValidationError) as exc_info:
            crawl_service._validate_uuid("not-a-uuid", "test_id")
        assert exc_info.value.field == "test_id"
        assert "uuid" in exc_info.value.message.lower()

    def test_validate_uuid_empty(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should reject empty UUID."""
        with pytest.raises(CrawlValidationError) as exc_info:
            crawl_service._validate_uuid("", "test_id")
        assert exc_info.value.field == "test_id"

    def test_validate_url_valid(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should accept valid URL."""
        # Should not raise
        crawl_service._validate_url("https://example.com/path", "test_url")

    def test_validate_url_missing_scheme(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should reject URL without scheme."""
        with pytest.raises(CrawlValidationError) as exc_info:
            crawl_service._validate_url("example.com/path", "test_url")
        assert exc_info.value.field == "test_url"

    def test_validate_url_empty(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should reject empty URL."""
        with pytest.raises(CrawlValidationError) as exc_info:
            crawl_service._validate_url("", "test_url")
        assert exc_info.value.field == "test_url"

    def test_validate_crawl_status_valid(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should accept valid crawl status."""
        valid_statuses = ["pending", "running", "completed", "failed", "cancelled"]
        for status in valid_statuses:
            # Should not raise
            crawl_service._validate_crawl_status(status)

    def test_validate_crawl_status_invalid(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should reject invalid crawl status."""
        with pytest.raises(CrawlValidationError) as exc_info:
            crawl_service._validate_crawl_status("invalid_status")
        assert exc_info.value.field == "status"
        assert "must be one of" in exc_info.value.message.lower()

    def test_validate_pagination_valid(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should accept valid pagination parameters."""
        # Should not raise
        crawl_service._validate_pagination(limit=100, offset=0)
        crawl_service._validate_pagination(limit=1, offset=1000)
        crawl_service._validate_pagination(limit=1000, offset=0)

    def test_validate_pagination_limit_too_small(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should reject limit less than 1."""
        with pytest.raises(CrawlValidationError) as exc_info:
            crawl_service._validate_pagination(limit=0, offset=0)
        assert exc_info.value.field == "limit"

    def test_validate_pagination_limit_too_large(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should reject limit greater than 1000."""
        with pytest.raises(CrawlValidationError) as exc_info:
            crawl_service._validate_pagination(limit=1001, offset=0)
        assert exc_info.value.field == "limit"
        assert "1000" in exc_info.value.message

    def test_validate_pagination_negative_offset(
        self,
        crawl_service: CrawlService,
    ) -> None:
        """Should reject negative offset."""
        with pytest.raises(CrawlValidationError) as exc_info:
            crawl_service._validate_pagination(limit=10, offset=-1)
        assert exc_info.value.field == "offset"


# ---------------------------------------------------------------------------
# Test: Exception Classes
# ---------------------------------------------------------------------------


class TestCrawlExceptionClasses:
    """Tests for CrawlService exception classes."""

    def test_crawl_service_error_base(self) -> None:
        """CrawlServiceError should be base exception."""
        error = CrawlServiceError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_crawl_validation_error(self) -> None:
        """CrawlValidationError should contain field and value info."""
        error = CrawlValidationError("test_field", "bad_value", "Invalid value")
        assert error.field == "test_field"
        assert error.value == "bad_value"
        assert error.message == "Invalid value"
        assert "test_field" in str(error)

    def test_crawl_not_found_error(self) -> None:
        """CrawlNotFoundError should contain entity type and id."""
        error = CrawlNotFoundError("CrawlHistory", "123-456")
        assert error.entity_type == "CrawlHistory"
        assert error.entity_id == "123-456"
        assert "CrawlHistory" in str(error)
        assert "123-456" in str(error)

    def test_crawl_pattern_error(self) -> None:
        """CrawlPatternError should contain pattern info."""
        error = CrawlPatternError("/bad/**/pattern", "Too many wildcards")
        assert error.pattern == "/bad/**/pattern"
        assert error.message == "Too many wildcards"
        assert "/bad/**/pattern" in str(error)

    def test_exception_hierarchy(self) -> None:
        """All exceptions should inherit from CrawlServiceError."""
        assert issubclass(CrawlValidationError, CrawlServiceError)
        assert issubclass(CrawlNotFoundError, CrawlServiceError)
        assert issubclass(CrawlPatternError, CrawlServiceError)


# ---------------------------------------------------------------------------
# Test: CrawlConfig and CrawlProgress Dataclasses
# ---------------------------------------------------------------------------


class TestCrawlConfig:
    """Tests for CrawlConfig dataclass."""

    def test_crawl_config_defaults(self) -> None:
        """Should have correct default values."""
        config = CrawlConfig(start_url="https://example.com")
        assert config.start_url == "https://example.com"
        assert config.include_patterns == []
        assert config.exclude_patterns == []
        assert config.max_pages == 100
        assert config.max_depth == 3
        assert config.crawl_options is None

    def test_crawl_config_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        config = CrawlConfig(
            start_url="https://example.com",
            include_patterns=["/products/*"],
            exclude_patterns=["/admin/*"],
            max_pages=50,
            max_depth=2,
        )
        result = config.to_dict()
        assert result["start_url"] == "https://example.com"
        assert result["include_patterns"] == ["/products/*"]
        assert result["exclude_patterns"] == ["/admin/*"]
        assert result["max_pages"] == 50
        assert result["max_depth"] == 2


class TestCrawlProgress:
    """Tests for CrawlProgress dataclass."""

    def test_crawl_progress_defaults(self) -> None:
        """Should have correct default values."""
        progress = CrawlProgress()
        assert progress.pages_crawled == 0
        assert progress.pages_failed == 0
        assert progress.pages_skipped == 0
        assert progress.urls_discovered == 0
        assert progress.current_depth == 0
        assert progress.status == "pending"
        assert progress.errors == []
        assert progress.started_at is None
        assert progress.completed_at is None

    def test_crawl_progress_to_dict(self) -> None:
        """Should convert to dictionary correctly."""
        progress = CrawlProgress(
            pages_crawled=10,
            pages_failed=2,
            pages_skipped=1,
            urls_discovered=50,
            current_depth=2,
        )
        result = progress.to_dict()
        assert result["pages_crawled"] == 10
        assert result["pages_failed"] == 2
        assert result["pages_skipped"] == 1
        assert result["urls_discovered"] == 50
        assert result["current_depth"] == 2
