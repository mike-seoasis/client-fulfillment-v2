"""Tests for LinkInjector (rule-based + LLM fallback) and strip_internal_links.

Tests cover:
- inject_rule_based: anchor found in paragraph → wraps in <a> tag
- inject_rule_based: anchor not found → returns original HTML with None
- inject_rule_based: anchor inside existing <a> tag → treated as 'not found'
- inject_rule_based: case-insensitive match preserves original casing
- inject_rule_based: density limit (2 links/paragraph) → tries next paragraph
- inject_llm_fallback: rewrites paragraph with <a> tag (mock Haiku response)
- inject_llm_fallback: malformed LLM response → returns original HTML
- strip_internal_links: internal links unwrapped, external links preserved
- strip_internal_links: heading structure preserved after stripping
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from app.services.link_injection import LinkInjector, strip_internal_links

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SIMPLE_HTML = (
    "<h2>Heading</h2>"
    "<p>The best hiking boots are made for rugged terrain and long trails.</p>"
    "<p>Consider waterproof options when shopping for outdoor gear.</p>"
)

HTML_WITH_EXISTING_LINK = (
    "<p>Check our <a href='/shoes'>hiking boots</a> for the best selection.</p>"
    "<p>We also offer waterproof jackets for outdoor adventures.</p>"
)

HTML_AT_DENSITY_LIMIT = (
    "<p>Visit <a href='/a'>link one</a> and <a href='/b'>link two</a> in this paragraph.</p>"
    "<p>This second paragraph has no links and mentions hiking boots clearly.</p>"
)


@pytest.fixture
def injector() -> LinkInjector:
    return LinkInjector()


# ---------------------------------------------------------------------------
# inject_rule_based: anchor found → wraps in <a>
# ---------------------------------------------------------------------------


class TestInjectRuleBasedFound:
    def test_anchor_found_wraps_in_link(self, injector: LinkInjector) -> None:
        result_html, p_idx = injector.inject_rule_based(
            SIMPLE_HTML, "hiking boots", "/collections/boots"
        )
        assert p_idx == 0
        assert '<a href="/collections/boots">hiking boots</a>' in result_html

    def test_surrounding_text_preserved(self, injector: LinkInjector) -> None:
        result_html, _ = injector.inject_rule_based(
            SIMPLE_HTML, "hiking boots", "/collections/boots"
        )
        assert "The best" in result_html
        assert "are made for" in result_html

    def test_heading_not_modified(self, injector: LinkInjector) -> None:
        result_html, _ = injector.inject_rule_based(
            SIMPLE_HTML, "hiking boots", "/collections/boots"
        )
        assert "<h2>Heading</h2>" in result_html


# ---------------------------------------------------------------------------
# inject_rule_based: anchor not found → original HTML + None
# ---------------------------------------------------------------------------


class TestInjectRuleBasedNotFound:
    def test_no_match_returns_original(self, injector: LinkInjector) -> None:
        result_html, p_idx = injector.inject_rule_based(
            SIMPLE_HTML, "nonexistent phrase", "/collections/boots"
        )
        assert p_idx is None
        assert result_html == SIMPLE_HTML


# ---------------------------------------------------------------------------
# inject_rule_based: anchor inside existing <a> → treated as 'not found'
# ---------------------------------------------------------------------------


class TestInjectRuleBasedInsideExistingLink:
    def test_anchor_inside_link_skipped(self, injector: LinkInjector) -> None:
        """Anchor text that exists only inside an <a> tag should not be injected."""
        html = "<p>Check our <a href='/shoes'>hiking boots</a> for quality.</p>"
        result_html, p_idx = injector.inject_rule_based(
            html, "hiking boots", "/collections/boots"
        )
        assert p_idx is None
        assert result_html == html

    def test_anchor_inside_link_but_also_in_another_paragraph(
        self, injector: LinkInjector
    ) -> None:
        """If anchor is inside <a> in first paragraph but free in second, inject in second."""
        result_html, p_idx = injector.inject_rule_based(
            HTML_WITH_EXISTING_LINK, "waterproof", "/collections/waterproof"
        )
        assert p_idx == 1
        assert '<a href="/collections/waterproof">waterproof</a>' in result_html


# ---------------------------------------------------------------------------
# inject_rule_based: case-insensitive match preserves original casing
# ---------------------------------------------------------------------------


class TestInjectRuleBasedCaseInsensitive:
    def test_case_insensitive_match(self, injector: LinkInjector) -> None:
        html = "<p>The best Hiking Boots are essential for trails.</p>"
        result_html, p_idx = injector.inject_rule_based(
            html, "hiking boots", "/collections/boots"
        )
        assert p_idx == 0
        # Original casing "Hiking Boots" should be preserved in the link
        assert '<a href="/collections/boots">Hiking Boots</a>' in result_html

    def test_uppercase_anchor_matches_lowercase_content(
        self, injector: LinkInjector
    ) -> None:
        html = "<p>Great hiking boots for every adventurer.</p>"
        result_html, p_idx = injector.inject_rule_based(
            html, "HIKING BOOTS", "/collections/boots"
        )
        assert p_idx == 0
        # Original casing from content is preserved
        assert '<a href="/collections/boots">hiking boots</a>' in result_html


# ---------------------------------------------------------------------------
# inject_rule_based: density limit → tries next paragraph
# ---------------------------------------------------------------------------


class TestInjectRuleBasedDensityLimit:
    def test_skips_paragraph_at_density_limit(
        self, injector: LinkInjector
    ) -> None:
        """First paragraph has 2 links (at limit), injection should go to second."""
        result_html, p_idx = injector.inject_rule_based(
            HTML_AT_DENSITY_LIMIT, "hiking boots", "/collections/boots"
        )
        assert p_idx == 1
        assert '<a href="/collections/boots">hiking boots</a>' in result_html

    def test_all_paragraphs_at_limit_returns_none(
        self, injector: LinkInjector
    ) -> None:
        html = (
            "<p><a href='/a'>one</a> and <a href='/b'>two</a> with hiking boots here.</p>"
            "<p><a href='/c'>three</a> and <a href='/d'>four</a> also hiking boots.</p>"
        )
        result_html, p_idx = injector.inject_rule_based(
            html, "hiking boots", "/collections/boots"
        )
        assert p_idx is None
        assert result_html == html


# ---------------------------------------------------------------------------
# inject_llm_fallback: rewrites paragraph with <a> tag (mock Haiku response)
# ---------------------------------------------------------------------------


@dataclass
class MockCompletionResult:
    success: bool
    text: str | None = None
    error: str | None = None


class TestInjectLlmFallback:
    @pytest.mark.asyncio
    async def test_successful_rewrite(self, injector: LinkInjector) -> None:
        html = (
            "<p>Intro paragraph about outdoor gear.</p>"
            "<p>Hiking boots provide excellent ankle support on rough trails.</p>"
        )
        rewritten_p = (
            '<p>Hiking boots provide excellent '
            '<a href="/collections/boots">ankle support</a> on rough trails.</p>'
        )
        mock_result = MockCompletionResult(success=True, text=rewritten_p)

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with (
            patch(
                "app.services.link_injection.ClaudeClient",
                return_value=mock_client,
            ),
            patch(
                "app.services.link_injection.get_api_key",
                return_value="test-key",
            ),
        ):
            result_html, p_idx = await injector.inject_llm_fallback(
                html, "ankle support", "/collections/boots", "hiking boots"
            )

        assert p_idx is not None
        assert '<a href="/collections/boots">ankle support</a>' in result_html
        mock_client.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_strips_markdown_fences(self, injector: LinkInjector) -> None:
        html = "<p>Content about hiking gear and boots.</p>"
        rewritten = (
            "```html\n"
            '<p>Content about <a href="/boots">hiking gear</a> and boots.</p>\n'
            "```"
        )
        mock_result = MockCompletionResult(success=True, text=rewritten)

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with (
            patch(
                "app.services.link_injection.ClaudeClient",
                return_value=mock_client,
            ),
            patch(
                "app.services.link_injection.get_api_key",
                return_value="test-key",
            ),
        ):
            result_html, p_idx = await injector.inject_llm_fallback(
                html, "hiking gear", "/boots", "hiking gear"
            )

        assert p_idx is not None
        assert '<a href="/boots">hiking gear</a>' in result_html


# ---------------------------------------------------------------------------
# inject_llm_fallback: malformed LLM response → returns original HTML
# ---------------------------------------------------------------------------


class TestInjectLlmFallbackMalformed:
    @pytest.mark.asyncio
    async def test_llm_failure_returns_original(
        self, injector: LinkInjector
    ) -> None:
        html = "<p>Content about hiking gear.</p>"
        mock_result = MockCompletionResult(
            success=False, text=None, error="API error"
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with (
            patch(
                "app.services.link_injection.ClaudeClient",
                return_value=mock_client,
            ),
            patch(
                "app.services.link_injection.get_api_key",
                return_value="test-key",
            ),
        ):
            result_html, p_idx = await injector.inject_llm_fallback(
                html, "hiking gear", "/boots", "hiking gear"
            )

        assert p_idx is None
        assert result_html == html

    @pytest.mark.asyncio
    async def test_wrong_href_returns_original(
        self, injector: LinkInjector
    ) -> None:
        html = "<p>Content about hiking gear.</p>"
        # LLM returns wrong href
        rewritten = '<p>Content about <a href="/wrong-url">hiking gear</a>.</p>'
        mock_result = MockCompletionResult(success=True, text=rewritten)

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with (
            patch(
                "app.services.link_injection.ClaudeClient",
                return_value=mock_client,
            ),
            patch(
                "app.services.link_injection.get_api_key",
                return_value="test-key",
            ),
        ):
            result_html, p_idx = await injector.inject_llm_fallback(
                html, "hiking gear", "/boots", "hiking gear"
            )

        assert p_idx is None
        assert result_html == html

    @pytest.mark.asyncio
    async def test_multiple_links_returns_original(
        self, injector: LinkInjector
    ) -> None:
        html = "<p>Content about hiking gear.</p>"
        # LLM returns multiple links
        rewritten = (
            '<p><a href="/boots">Content</a> about '
            '<a href="/boots">hiking gear</a>.</p>'
        )
        mock_result = MockCompletionResult(success=True, text=rewritten)

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with (
            patch(
                "app.services.link_injection.ClaudeClient",
                return_value=mock_client,
            ),
            patch(
                "app.services.link_injection.get_api_key",
                return_value="test-key",
            ),
        ):
            result_html, p_idx = await injector.inject_llm_fallback(
                html, "hiking gear", "/boots", "hiking gear"
            )

        assert p_idx is None
        assert result_html == html

    @pytest.mark.asyncio
    async def test_no_paragraphs_returns_original(
        self, injector: LinkInjector
    ) -> None:
        html = "<div>No paragraphs here</div>"
        result_html, p_idx = await injector.inject_llm_fallback(
            html, "hiking gear", "/boots", "hiking gear"
        )
        assert p_idx is None
        assert result_html == html


# ---------------------------------------------------------------------------
# strip_internal_links: internal links unwrapped, external preserved
# ---------------------------------------------------------------------------


class TestStripInternalLinks:
    def test_relative_links_unwrapped(self) -> None:
        html = '<p>Check our <a href="/collections/boots">hiking boots</a> selection.</p>'
        result = strip_internal_links(html)
        assert "<a" not in result
        assert "hiking boots" in result
        assert "Check our" in result
        assert "selection." in result

    def test_same_domain_links_unwrapped(self) -> None:
        html = '<p>See <a href="https://example.com/boots">boots</a> here.</p>'
        result = strip_internal_links(html, site_domain="example.com")
        assert "<a" not in result
        assert "boots" in result

    def test_external_links_preserved(self) -> None:
        html = (
            '<p>Read <a href="https://external.com/article">this article</a> '
            'and <a href="/internal">internal page</a>.</p>'
        )
        result = strip_internal_links(html, site_domain="example.com")
        # External link preserved
        assert '<a href="https://external.com/article">this article</a>' in result
        # Internal link stripped
        assert 'href="/internal"' not in result
        assert "internal page" in result

    def test_mixed_links(self) -> None:
        html = (
            '<p><a href="/shoes">Shoes</a> and '
            '<a href="https://other.com">Other</a> and '
            '<a href="https://example.com/boots">Boots</a>.</p>'
        )
        result = strip_internal_links(html, site_domain="example.com")
        # /shoes (relative) → stripped
        assert 'href="/shoes"' not in result
        assert "Shoes" in result
        # example.com/boots (same domain) → stripped
        assert 'href="https://example.com/boots"' not in result
        assert "Boots" in result
        # other.com (external) → preserved
        assert '<a href="https://other.com">Other</a>' in result


# ---------------------------------------------------------------------------
# strip_internal_links: heading structure preserved
# ---------------------------------------------------------------------------


class TestStripInternalLinksStructure:
    def test_headings_preserved(self) -> None:
        html = (
            "<h2>Best Hiking Boots</h2>"
            '<p>Our <a href="/boots">hiking boots</a> are great.</p>'
            "<h3>Waterproof Options</h3>"
            '<p>Try <a href="/waterproof">waterproof boots</a> too.</p>'
        )
        result = strip_internal_links(html)
        assert "<h2>Best Hiking Boots</h2>" in result
        assert "<h3>Waterproof Options</h3>" in result
        assert "<a" not in result

    def test_paragraphs_preserved(self) -> None:
        html = (
            "<p>First paragraph with <a href='/a'>link</a>.</p>"
            "<p>Second paragraph with <a href='/b'>another link</a>.</p>"
        )
        result = strip_internal_links(html)
        # Both paragraphs still exist
        assert result.count("<p>") == 2
        assert result.count("</p>") == 2
        assert "<a" not in result

    def test_list_structure_preserved(self) -> None:
        html = (
            "<ul>"
            "<li><a href='/a'>Item one</a></li>"
            "<li><a href='/b'>Item two</a></li>"
            "</ul>"
        )
        result = strip_internal_links(html)
        assert "<ul>" in result
        assert "<li>" in result
        assert "Item one" in result
        assert "Item two" in result
        assert "<a" not in result

    def test_no_links_returns_unchanged(self) -> None:
        html = "<h2>Title</h2><p>No links here.</p>"
        result = strip_internal_links(html)
        assert result == html
