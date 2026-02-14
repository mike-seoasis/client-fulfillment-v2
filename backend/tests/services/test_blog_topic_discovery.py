"""Tests for blog topic discovery service.

Tests cover:
- POP seed extraction: query approved pages with briefs, deduplication, empty results
- Topic expansion (Stage 2): mock Claude, JSON parsing, source_page_id mapping,
  too-few-candidates error, markdown code fence stripping
- Volume enrichment (Stage 3): mock DataForSEO, zero-volume filtering, unavailable fallback
- Filter and rank (Stage 4): mock Claude, slug generation, sorting by relevance
- Slug generation: length truncation, special char removal
- Full discover_topics pipeline: orchestration, persistence, error handling
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.claude import CompletionResult
from app.models.blog import BlogCampaign, BlogPost
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.keyword_cluster import ClusterPage, KeywordCluster
from app.models.project import Project
from app.services.blog_topic_discovery import BlogTopicDiscoveryService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    """Create a test project."""
    project = Project(
        name="Blog Discovery Test",
        site_url="https://blog-test.example.com",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def cluster(db_session: AsyncSession, project: Project) -> KeywordCluster:
    """Create a test keyword cluster."""
    cluster = KeywordCluster(
        project_id=project.id,
        seed_keyword="winter boots",
        name="Winter Boots",
        status="approved",
    )
    db_session.add(cluster)
    await db_session.commit()
    await db_session.refresh(cluster)
    return cluster


@pytest.fixture
async def crawled_page(db_session: AsyncSession, project: Project) -> CrawledPage:
    """Create a test crawled page."""
    page = CrawledPage(
        project_id=project.id,
        normalized_url="https://blog-test.example.com/boots",
        status="completed",
        title="Winter Boots Collection",
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)
    return page


@pytest.fixture
async def cluster_page(
    db_session: AsyncSession,
    cluster: KeywordCluster,
    crawled_page: CrawledPage,
) -> ClusterPage:
    """Create an approved cluster page linked to a crawled page."""
    cp = ClusterPage(
        cluster_id=cluster.id,
        keyword="winter boots",
        role="parent",
        url_slug="winter-boots",
        is_approved=True,
        crawled_page_id=crawled_page.id,
    )
    db_session.add(cp)
    await db_session.commit()
    await db_session.refresh(cp)
    return cp


@pytest.fixture
async def content_brief(
    db_session: AsyncSession, crawled_page: CrawledPage
) -> ContentBrief:
    """Create a content brief with related searches and questions."""
    brief = ContentBrief(
        page_id=crawled_page.id,
        keyword="winter boots",
        related_searches=["best winter boots", "warm boots for snow"],
        related_questions=["how to choose winter boots?"],
    )
    db_session.add(brief)
    await db_session.commit()
    await db_session.refresh(brief)
    return brief


@pytest.fixture
def mock_claude() -> AsyncMock:
    """Create a mock Claude client."""
    client = AsyncMock()
    client.available = True
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_dataforseo() -> AsyncMock:
    """Create a mock DataForSEO client."""
    client = AsyncMock()
    client.available = True
    return client


@pytest.fixture
def service(mock_claude: AsyncMock, mock_dataforseo: AsyncMock) -> BlogTopicDiscoveryService:
    """Create a BlogTopicDiscoveryService with mock clients."""
    return BlogTopicDiscoveryService(mock_claude, mock_dataforseo)


# ---------------------------------------------------------------------------
# Stage 1: Extract POP Seeds
# ---------------------------------------------------------------------------


class TestExtractPopSeeds:
    """Tests for seed extraction from POP briefs."""

    @pytest.mark.asyncio
    async def test_extracts_seeds_from_briefs(
        self,
        service: BlogTopicDiscoveryService,
        db_session: AsyncSession,
        cluster: KeywordCluster,
        cluster_page: ClusterPage,
        content_brief: ContentBrief,
    ) -> None:
        """Extracts related_searches and related_questions from approved pages."""
        seeds = await service.extract_pop_seeds(cluster.id, db_session)

        assert len(seeds) == 3
        seed_texts = {s["seed"] for s in seeds}
        assert "best winter boots" in seed_texts
        assert "warm boots for snow" in seed_texts
        assert "how to choose winter boots?" in seed_texts

    @pytest.mark.asyncio
    async def test_deduplicates_seeds(
        self,
        service: BlogTopicDiscoveryService,
        db_session: AsyncSession,
        cluster: KeywordCluster,
        cluster_page: ClusterPage,
        crawled_page: CrawledPage,
    ) -> None:
        """Seeds are deduplicated by normalized text."""
        brief = ContentBrief(
            page_id=crawled_page.id,
            keyword="winter boots",
            related_searches=["Best Winter Boots", "best winter boots"],
            related_questions=[],
        )
        db_session.add(brief)
        await db_session.commit()

        seeds = await service.extract_pop_seeds(cluster.id, db_session)

        # Should deduplicate "Best Winter Boots" and "best winter boots"
        assert len(seeds) == 1

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_approved_pages(
        self,
        service: BlogTopicDiscoveryService,
        db_session: AsyncSession,
        cluster: KeywordCluster,
    ) -> None:
        """Returns empty list when no approved cluster pages exist."""
        seeds = await service.extract_pop_seeds(cluster.id, db_session)
        assert seeds == []

    @pytest.mark.asyncio
    async def test_seeds_include_source_page_id(
        self,
        service: BlogTopicDiscoveryService,
        db_session: AsyncSession,
        cluster: KeywordCluster,
        cluster_page: ClusterPage,
        content_brief: ContentBrief,
    ) -> None:
        """Each seed includes the source_page_id from the cluster page."""
        seeds = await service.extract_pop_seeds(cluster.id, db_session)

        for seed in seeds:
            assert seed["source_page_id"] == cluster_page.id


# ---------------------------------------------------------------------------
# Stage 2: Expand Topics
# ---------------------------------------------------------------------------


class TestExpandTopics:
    """Tests for topic expansion via Claude."""

    @pytest.mark.asyncio
    async def test_expands_seeds_into_candidates(
        self, service: BlogTopicDiscoveryService, mock_claude: AsyncMock
    ) -> None:
        """Expands seeds into blog topic candidates via Claude."""
        candidates_json = json.dumps([
            {"topic": "how to clean winter boots", "format_type": "how-to",
             "rationale": "Common question", "source_seed_index": 1},
            {"topic": "best winter boots for hiking", "format_type": "listicle",
             "rationale": "High intent", "source_seed_index": 2},
            {"topic": "winter boot care guide", "format_type": "guide",
             "rationale": "Evergreen topic", "source_seed_index": 1},
            {"topic": "compare hiking boots vs winter boots", "format_type": "comparison",
             "rationale": "Comparison query", "source_seed_index": 2},
            {"topic": "are winter boots waterproof", "format_type": "faq",
             "rationale": "FAQ topic", "source_seed_index": 1},
        ])
        mock_claude.complete.return_value = CompletionResult(
            success=True, text=candidates_json, input_tokens=500, output_tokens=300,
        )

        seeds = [
            {"seed": "winter boot care", "source_type": "related_search", "source_page_id": "pg1"},
            {"seed": "best hiking boots", "source_type": "related_question", "source_page_id": "pg2"},
        ]
        result = await service.expand_topics(seeds, "")

        assert len(result) == 5
        assert result[0]["topic"] == "how to clean winter boots"
        assert result[0]["source_page_id"] == "pg1"
        assert result[1]["source_page_id"] == "pg2"

    @pytest.mark.asyncio
    async def test_strips_markdown_code_fences(
        self, service: BlogTopicDiscoveryService, mock_claude: AsyncMock
    ) -> None:
        """Handles Claude responses wrapped in markdown code fences."""
        candidates = [
            {"topic": f"topic {i}", "format_type": "guide", "rationale": "r", "source_seed_index": 1}
            for i in range(6)
        ]
        wrapped = f"```json\n{json.dumps(candidates)}\n```"
        mock_claude.complete.return_value = CompletionResult(
            success=True, text=wrapped, input_tokens=100, output_tokens=200,
        )

        seeds = [{"seed": "test", "source_type": "related_search", "source_page_id": "pg1"}]
        result = await service.expand_topics(seeds, "")
        assert len(result) == 6

    @pytest.mark.asyncio
    async def test_raises_on_too_few_candidates(
        self, service: BlogTopicDiscoveryService, mock_claude: AsyncMock
    ) -> None:
        """Raises ValueError when Claude returns fewer than 5 valid candidates."""
        mock_claude.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps([
                {"topic": "only one", "format_type": "guide", "rationale": "r", "source_seed_index": 1}
            ]),
            input_tokens=100, output_tokens=50,
        )

        seeds = [{"seed": "test", "source_type": "related_search", "source_page_id": "pg1"}]
        with pytest.raises(ValueError, match="Too few valid candidates"):
            await service.expand_topics(seeds, "")

    @pytest.mark.asyncio
    async def test_raises_on_claude_api_failure(
        self, service: BlogTopicDiscoveryService, mock_claude: AsyncMock
    ) -> None:
        """Raises ValueError when Claude API call fails."""
        mock_claude.complete.return_value = CompletionResult(
            success=False, error="Rate limit exceeded",
        )

        seeds = [{"seed": "test", "source_type": "related_search", "source_page_id": "pg1"}]
        with pytest.raises(ValueError, match="Claude topic expansion failed"):
            await service.expand_topics(seeds, "")


# ---------------------------------------------------------------------------
# Stage 3: Enrich With Volume
# ---------------------------------------------------------------------------


class TestEnrichWithVolume:
    """Tests for search volume enrichment via DataForSEO."""

    @pytest.mark.asyncio
    async def test_enriches_candidates_with_volume(
        self, service: BlogTopicDiscoveryService, mock_dataforseo: AsyncMock
    ) -> None:
        """Enriches candidates with volume data from DataForSEO."""
        mock_kw1 = MagicMock()
        mock_kw1.keyword = "how to clean boots"
        mock_kw1.search_volume = 1200
        mock_kw1.cpc = 0.5
        mock_kw1.competition = 0.3
        mock_kw1.competition_level = "low"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.keywords = [mock_kw1]
        mock_result.cost = 0.001
        mock_result.duration_ms = 200

        mock_dataforseo.get_keyword_volume_batch.return_value = mock_result

        candidates = [
            {"topic": "how to clean boots", "format_type": "how-to"},
        ]
        result = await service.enrich_with_volume(candidates)

        assert result[0]["search_volume"] == 1200
        assert result[0]["cpc"] == 0.5

    @pytest.mark.asyncio
    async def test_filters_zero_volume_topics(
        self, service: BlogTopicDiscoveryService, mock_dataforseo: AsyncMock
    ) -> None:
        """Filters out candidates with zero search volume."""
        mock_kw1 = MagicMock()
        mock_kw1.keyword = "topic with volume"
        mock_kw1.search_volume = 500
        mock_kw1.cpc = 0.5
        mock_kw1.competition = 0.3
        mock_kw1.competition_level = "low"

        mock_kw2 = MagicMock()
        mock_kw2.keyword = "zero volume topic"
        mock_kw2.search_volume = 0
        mock_kw2.cpc = 0.0
        mock_kw2.competition = 0.0
        mock_kw2.competition_level = "low"

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.keywords = [mock_kw1, mock_kw2]
        mock_result.cost = 0.001
        mock_result.duration_ms = 200

        mock_dataforseo.get_keyword_volume_batch.return_value = mock_result

        candidates = [
            {"topic": "topic with volume", "format_type": "guide"},
            {"topic": "zero volume topic", "format_type": "guide"},
        ]
        result = await service.enrich_with_volume(candidates)

        assert len(result) == 1
        assert result[0]["topic"] == "topic with volume"

    @pytest.mark.asyncio
    async def test_marks_volume_unavailable_when_client_unavailable(
        self, service: BlogTopicDiscoveryService, mock_dataforseo: AsyncMock
    ) -> None:
        """Marks candidates with volume_unavailable when DataForSEO is not available."""
        mock_dataforseo.available = False

        candidates = [
            {"topic": "some topic", "format_type": "guide"},
        ]
        result = await service.enrich_with_volume(candidates)

        assert len(result) == 1
        assert result[0]["volume_unavailable"] is True

    @pytest.mark.asyncio
    async def test_handles_empty_candidates(
        self, service: BlogTopicDiscoveryService
    ) -> None:
        """Returns empty list for empty candidates."""
        result = await service.enrich_with_volume([])
        assert result == []


# ---------------------------------------------------------------------------
# Stage 4: Filter and Rank
# ---------------------------------------------------------------------------


class TestFilterAndRank:
    """Tests for topic filtering and ranking via Claude."""

    @pytest.mark.asyncio
    async def test_filters_and_sorts_by_relevance(
        self, service: BlogTopicDiscoveryService, mock_claude: AsyncMock
    ) -> None:
        """Filters candidates and sorts by relevance_score descending."""
        filtered_json = json.dumps([
            {"topic": "second topic", "format_type": "guide",
             "url_slug": "second-topic", "relevance_score": 0.8, "reasoning": "Good"},
            {"topic": "top topic", "format_type": "how-to",
             "url_slug": "top-topic", "relevance_score": 0.95, "reasoning": "Best"},
            {"topic": "third topic", "format_type": "listicle",
             "url_slug": "third-topic", "relevance_score": 0.7, "reasoning": "OK"},
        ])
        mock_claude.complete.return_value = CompletionResult(
            success=True, text=filtered_json, input_tokens=800, output_tokens=400,
        )

        candidates = [
            {"topic": "top topic", "format_type": "how-to", "search_volume": 1000, "source_page_id": "pg1"},
            {"topic": "second topic", "format_type": "guide", "search_volume": 500, "source_page_id": "pg2"},
            {"topic": "third topic", "format_type": "listicle", "search_volume": 200, "source_page_id": "pg1"},
        ]
        result = await service.filter_and_rank(candidates, "Winter Boots")

        assert len(result) == 3
        assert result[0]["topic"] == "top topic"
        assert result[0]["relevance_score"] == 0.95
        assert result[1]["relevance_score"] == 0.8

    @pytest.mark.asyncio
    async def test_preserves_source_page_id_from_candidates(
        self, service: BlogTopicDiscoveryService, mock_claude: AsyncMock
    ) -> None:
        """Preserves source_page_id and volume data from original candidates."""
        filtered_json = json.dumps([
            {"topic": "my topic", "format_type": "guide",
             "url_slug": "my-topic", "relevance_score": 0.9, "reasoning": "r"},
            {"topic": "another topic", "format_type": "how-to",
             "url_slug": "another-topic", "relevance_score": 0.85, "reasoning": "r"},
            {"topic": "third one", "format_type": "listicle",
             "url_slug": "third-one", "relevance_score": 0.8, "reasoning": "r"},
        ])
        mock_claude.complete.return_value = CompletionResult(
            success=True, text=filtered_json, input_tokens=100, output_tokens=200,
        )

        candidates = [
            {"topic": "my topic", "format_type": "guide", "search_volume": 750,
             "cpc": 0.8, "source_page_id": "page-abc"},
            {"topic": "another topic", "format_type": "how-to", "search_volume": 500,
             "cpc": 0.5, "source_page_id": "page-def"},
            {"topic": "third one", "format_type": "listicle", "search_volume": 300,
             "cpc": 0.3, "source_page_id": "page-abc"},
        ]
        result = await service.filter_and_rank(candidates, "Boots")

        assert result[0]["source_page_id"] == "page-abc"
        assert result[0]["search_volume"] == 750

    @pytest.mark.asyncio
    async def test_raises_on_too_few_results(
        self, service: BlogTopicDiscoveryService, mock_claude: AsyncMock
    ) -> None:
        """Raises ValueError when filter returns fewer than 3 results."""
        mock_claude.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps([
                {"topic": "one", "format_type": "guide",
                 "url_slug": "one", "relevance_score": 0.9, "reasoning": "r"},
            ]),
            input_tokens=100, output_tokens=50,
        )

        candidates = [{"topic": "one", "format_type": "guide", "search_volume": 100}]
        with pytest.raises(ValueError, match="Too few results after filtering"):
            await service.filter_and_rank(candidates, "Test")


# ---------------------------------------------------------------------------
# Slug Generation
# ---------------------------------------------------------------------------


class TestTopicToSlug:
    """Tests for _topic_to_slug static method."""

    def test_basic_slug(self) -> None:
        slug = BlogTopicDiscoveryService._topic_to_slug("how to clean white sneakers")
        assert slug == "how-to-clean-white-sneakers"

    def test_removes_special_characters(self) -> None:
        slug = BlogTopicDiscoveryService._topic_to_slug("what's the best boot?")
        assert "'" not in slug
        assert "?" not in slug

    def test_truncates_at_80_chars(self) -> None:
        long_topic = "a very long blog topic keyword that exceeds the eighty character limit by quite a significant margin"
        slug = BlogTopicDiscoveryService._topic_to_slug(long_topic)
        assert len(slug) <= 80

    def test_collapses_consecutive_hyphens(self) -> None:
        slug = BlogTopicDiscoveryService._topic_to_slug("boots  --  for  winter")
        assert "--" not in slug

    def test_strips_leading_trailing_hyphens(self) -> None:
        slug = BlogTopicDiscoveryService._topic_to_slug("-boots-")
        assert not slug.startswith("-")
        assert not slug.endswith("-")


# ---------------------------------------------------------------------------
# Brand Context Builder
# ---------------------------------------------------------------------------


class TestBuildBrandContext:
    """Tests for _build_brand_context static method."""

    def test_builds_context_from_full_config(self) -> None:
        config: dict[str, Any] = {
            "brand_foundation": {
                "company_overview": {"company_name": "BootCo"},
                "what_they_sell": {"primary_products_services": "boots"},
            },
            "target_audience": {
                "personas": [{"name": "Outdoor Enthusiast", "summary": "Loves hiking"}],
            },
        }
        context = BlogTopicDiscoveryService._build_brand_context(config)
        assert "BootCo" in context
        assert "boots" in context
        assert "Outdoor Enthusiast" in context

    def test_handles_empty_config(self) -> None:
        context = BlogTopicDiscoveryService._build_brand_context({})
        assert context == ""
