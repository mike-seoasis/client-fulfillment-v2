"""Tests for blog export service.

Tests cover:
- HTML cleaning: highlight span stripping, data attribute removal, H1→H2 demotion,
  empty span cleanup, link preservation
- Export package generation: queries approved+complete posts, returns BlogExportItem list
- Word counting: strips HTML tags, handles empty content
"""

from typing import Any
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blog import BlogPost, ContentStatus
from app.models.project import Project
from app.models.blog import BlogCampaign, CampaignStatus
from app.services.blog_export import BlogExportService, _count_words


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeBlogPost:
    """Stand-in for BlogPost to avoid SQLAlchemy session pollution."""

    def __init__(self, **kwargs: Any) -> None:
        self.id: str = kwargs.get("id", "fake-post-id")
        self.primary_keyword: str = kwargs.get("primary_keyword", "test keyword")
        self.url_slug: str = kwargs.get("url_slug", "test-keyword")
        self.title: str | None = kwargs.get("title")
        self.meta_description: str | None = kwargs.get("meta_description")
        self.content: str | None = kwargs.get("content")
        self.content_status: str = kwargs.get("content_status", ContentStatus.COMPLETE.value)
        self.content_approved: bool = kwargs.get("content_approved", True)
        self.is_approved: bool = kwargs.get("is_approved", True)


def _make_fake_post(**kwargs: Any) -> Any:
    return _FakeBlogPost(**kwargs)


# ---------------------------------------------------------------------------
# generate_clean_html Tests
# ---------------------------------------------------------------------------


class TestGenerateCleanHtml:
    """Tests for HTML cleaning in BlogExportService."""

    def test_strips_highlight_spans(self) -> None:
        """Strips <span class='hl-keyword'> etc., keeping text content."""
        post = _make_fake_post(
            content='<p>Buy <span class="hl-keyword">winter boots</span> today.</p>'
        )
        result = BlogExportService.generate_clean_html(post)

        assert "hl-keyword" not in result
        assert "winter boots" in result
        assert "<span" not in result

    def test_strips_all_highlight_classes(self) -> None:
        """Strips all 4 highlight classes: hl-keyword, hl-keyword-var, hl-lsi, hl-trope."""
        post = _make_fake_post(
            content=(
                '<p><span class="hl-keyword">kw</span> '
                '<span class="hl-keyword-var">var</span> '
                '<span class="hl-lsi">lsi</span> '
                '<span class="hl-trope">trope</span></p>'
            )
        )
        result = BlogExportService.generate_clean_html(post)

        assert "hl-" not in result
        assert "kw" in result
        assert "var" in result
        assert "lsi" in result
        assert "trope" in result

    def test_removes_data_attributes(self) -> None:
        """Removes data-* attributes from all elements."""
        post = _make_fake_post(
            content='<p data-lexical-type="text" data-word-count="5">Hello world.</p>'
        )
        result = BlogExportService.generate_clean_html(post)

        assert "data-lexical-type" not in result
        assert "data-word-count" not in result
        assert "Hello world." in result

    def test_demotes_h1_to_h2(self) -> None:
        """Demotes H1 headings to H2 for proper heading hierarchy."""
        post = _make_fake_post(
            content="<h1>Main Heading</h1><p>Content.</p>"
        )
        result = BlogExportService.generate_clean_html(post)

        assert "<h1>" not in result
        assert "<h2>Main Heading</h2>" in result

    def test_preserves_internal_links(self) -> None:
        """Preserves <a href> links in cleaned HTML."""
        post = _make_fake_post(
            content='<p>See our <a href="/collections/boots">boots collection</a>.</p>'
        )
        result = BlogExportService.generate_clean_html(post)

        assert '<a href="/collections/boots">' in result
        assert "boots collection" in result

    def test_removes_empty_spans(self) -> None:
        """Removes spans left with no meaningful attributes after unwrapping."""
        post = _make_fake_post(
            content="<p><span>text inside plain span</span></p>"
        )
        result = BlogExportService.generate_clean_html(post)

        assert "<span>" not in result
        assert "text inside plain span" in result

    def test_preserves_spans_with_class(self) -> None:
        """Preserves spans that have non-highlight classes."""
        post = _make_fake_post(
            content='<p><span class="custom-style">styled text</span></p>'
        )
        result = BlogExportService.generate_clean_html(post)

        assert 'class="custom-style"' in result
        assert "styled text" in result

    def test_returns_empty_string_for_no_content(self) -> None:
        """Returns empty string when blog post has no content."""
        post = _make_fake_post(content=None)
        result = BlogExportService.generate_clean_html(post)
        assert result == ""

    def test_returns_empty_string_for_empty_content(self) -> None:
        """Returns empty string when content is empty."""
        post = _make_fake_post(content="")
        result = BlogExportService.generate_clean_html(post)
        assert result == ""


# ---------------------------------------------------------------------------
# _count_words Tests
# ---------------------------------------------------------------------------


class TestCountWords:
    """Tests for word counting utility."""

    def test_counts_words_in_html(self) -> None:
        """Counts words after stripping HTML tags."""
        html = "<h2>Heading</h2><p>Three words here.</p>"
        assert _count_words(html) == 4  # Heading + Three + words + here

    def test_returns_zero_for_empty(self) -> None:
        assert _count_words("") == 0

    def test_returns_zero_for_none_like(self) -> None:
        assert _count_words("") == 0

    def test_handles_nested_tags(self) -> None:
        html = "<p>A <strong>bold</strong> <em>word</em>.</p>"
        assert _count_words(html) == 4  # A + bold + word + .  — actually "." is attached to "word"
        # BeautifulSoup get_text strips=True gives "A bold word." → 4 words


# ---------------------------------------------------------------------------
# generate_export_package Tests (async, requires db)
# ---------------------------------------------------------------------------


class TestGenerateExportPackage:
    """Tests for export package generation (queries DB)."""

    @pytest.mark.asyncio
    async def test_exports_approved_complete_posts(
        self, db_session: AsyncSession
    ) -> None:
        """Exports only posts that are approved and content_complete."""
        project = Project(
            name="Export Test",
            site_url="https://export-test.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        # Need a KeywordCluster for the foreign key
        from app.models.keyword_cluster import KeywordCluster
        cluster = KeywordCluster(
            project_id=project.id,
            seed_keyword="test cluster",
            name="Test Cluster",
            status="approved",
        )
        db_session.add(cluster)
        await db_session.commit()
        await db_session.refresh(cluster)

        campaign = BlogCampaign(
            project_id=project.id,
            cluster_id=cluster.id,
            name="Export Test Campaign",
            status=CampaignStatus.REVIEW.value,
        )
        db_session.add(campaign)
        await db_session.commit()
        await db_session.refresh(campaign)

        # Approved + complete post → should be exported
        post1 = BlogPost(
            campaign_id=campaign.id,
            primary_keyword="export topic 1",
            url_slug="export-topic-1",
            title="Export Title 1",
            meta_description="Export meta 1",
            content="<h2>Export</h2><p>Content one.</p>",
            content_status=ContentStatus.COMPLETE.value,
            content_approved=True,
            is_approved=True,
        )
        # Not approved → should NOT be exported
        post2 = BlogPost(
            campaign_id=campaign.id,
            primary_keyword="export topic 2",
            url_slug="export-topic-2",
            title="Export Title 2",
            content="<p>Content two.</p>",
            content_status=ContentStatus.COMPLETE.value,
            content_approved=False,
            is_approved=True,
        )
        db_session.add_all([post1, post2])
        await db_session.commit()

        items = await BlogExportService.generate_export_package(campaign.id, db_session)

        assert len(items) == 1
        assert items[0].primary_keyword == "export topic 1"
        assert items[0].word_count > 0

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_approved_posts(
        self, db_session: AsyncSession
    ) -> None:
        """Returns empty list when no approved+complete posts exist."""
        project = Project(
            name="Empty Export Test",
            site_url="https://empty-export.example.com",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        from app.models.keyword_cluster import KeywordCluster
        cluster = KeywordCluster(
            project_id=project.id,
            seed_keyword="test cluster",
            name="Test Cluster",
            status="approved",
        )
        db_session.add(cluster)
        await db_session.commit()
        await db_session.refresh(cluster)

        campaign = BlogCampaign(
            project_id=project.id,
            cluster_id=cluster.id,
            name="Empty Export Campaign",
            status=CampaignStatus.PLANNING.value,
        )
        db_session.add(campaign)
        await db_session.commit()
        await db_session.refresh(campaign)

        items = await BlogExportService.generate_export_package(campaign.id, db_session)
        assert items == []
