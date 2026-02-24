"""Tests for ClusterKeywordService: brand context, candidate generation,
volume enrichment, filtering, full pipeline, bulk approve, and URL slug edge cases."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.claude import CompletionResult
from app.integrations.dataforseo import KeywordVolumeData, KeywordVolumeResult
from app.models.crawled_page import CrawledPage
from app.models.keyword_cluster import ClusterPage, ClusterStatus, KeywordCluster
from app.models.page_keywords import PageKeywords
from app.models.project import Project
from app.services.cluster_keyword import ClusterKeywordService

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_claude_client(available: bool = True) -> MagicMock:
    """Create a mock ClaudeClient."""
    client = MagicMock()
    client.available = available
    client.complete = AsyncMock()
    return client


def _make_dataforseo_client(available: bool = True) -> MagicMock:
    """Create a mock DataForSEOClient."""
    client = MagicMock()
    client.available = available
    client.get_keyword_volume_batch = AsyncMock()
    return client


def _full_brand_config() -> dict[str, Any]:
    """Return a complete v2_schema brand config for testing."""
    return {
        "brand_foundation": {
            "company_overview": {"company_name": "TrailBlaze Co"},
            "what_they_sell": {
                "primary_products_services": "Hiking boots and outdoor gear",
                "price_point": "Premium ($150-$300)",
                "sales_channels": "DTC website, REI",
            },
        },
        "target_audience": {
            "personas": [
                {
                    "name": "Weekend Warrior",
                    "summary": "Active professional who hikes on weekends",
                }
            ]
        },
        "competitor_context": {
            "direct_competitors": [
                {"name": "Merrell"},
                {"name": "Salomon"},
            ]
        },
    }


def _partial_brand_config() -> dict[str, Any]:
    """Return a brand config with only company name."""
    return {
        "brand_foundation": {
            "company_overview": {"company_name": "TrailBlaze Co"},
        },
    }


def _candidates_json(count: int = 8, include_seed: bool = False) -> str:
    """Build a JSON string of candidate keywords for Claude mock responses."""
    strategies = [
        "demographic", "attribute", "price/value", "use-case",
        "comparison/intent", "seasonal/occasion", "material/type",
        "experience level",
    ]
    candidates = []
    for i in range(count):
        kw = f"hiking boots keyword {i + 1}" if not include_seed or i > 0 else "hiking boots"
        candidates.append({
            "keyword": kw,
            "expansion_strategy": strategies[i % len(strategies)],
            "rationale": f"Good for collection page {i + 1}",
            "estimated_intent": "commercial",
        })
    return json.dumps(candidates)


def _filter_json(seed: str = "hiking boots", child_count: int = 7) -> str:
    """Build a JSON string of filtered results for Claude mock responses."""
    results = [
        {
            "keyword": seed,
            "role": "parent",
            "url_slug": "hiking-boots",
            "reasoning": "High-volume seed keyword",
            "relevance": 0.95,
        }
    ]
    for i in range(child_count):
        results.append({
            "keyword": f"child keyword {i + 1}",
            "role": "child",
            "url_slug": f"child-keyword-{i + 1}",
            "reasoning": f"Good child keyword {i + 1}",
            "relevance": 0.8 - i * 0.05,
        })
    return json.dumps(results)


# ---------------------------------------------------------------------------
# Test _build_brand_context
# ---------------------------------------------------------------------------

class TestBuildBrandContext:
    """Tests for ClusterKeywordService._build_brand_context."""

    def test_full_brand_config(self):
        """Full brand config extracts all sections."""
        result = ClusterKeywordService._build_brand_context(_full_brand_config())

        assert "## Brand" in result
        assert "TrailBlaze Co" in result
        assert "Hiking boots and outdoor gear" in result
        assert "Premium ($150-$300)" in result
        assert "DTC website, REI" in result
        assert "## Target Audience" in result
        assert "Weekend Warrior" in result
        assert "Active professional who hikes on weekends" in result
        assert "## Competitors" in result
        assert "Merrell" in result
        assert "Salomon" in result

    def test_partial_brand_config(self):
        """Partial brand config only includes available sections."""
        result = ClusterKeywordService._build_brand_context(_partial_brand_config())

        assert "## Brand" in result
        assert "TrailBlaze Co" in result
        assert "## Target Audience" not in result
        assert "## Competitors" not in result

    def test_empty_brand_config(self):
        """Empty brand config returns empty string."""
        result = ClusterKeywordService._build_brand_context({})
        assert result == ""

    def test_malformed_brand_config(self):
        """Malformed data (wrong types) is handled gracefully."""
        config = {
            "brand_foundation": "not a dict",
            "target_audience": 42,
            "competitor_context": None,
        }
        result = ClusterKeywordService._build_brand_context(config)
        assert result == ""

    def test_empty_personas_list(self):
        """Empty personas list produces no target audience section."""
        config: dict[str, Any] = {"target_audience": {"personas": []}}
        result = ClusterKeywordService._build_brand_context(config)
        assert result == ""

    def test_empty_competitors_list(self):
        """Empty competitors list produces no competitors section."""
        config: dict[str, Any] = {"competitor_context": {"direct_competitors": []}}
        result = ClusterKeywordService._build_brand_context(config)
        assert result == ""


# ---------------------------------------------------------------------------
# Test _generate_candidates
# ---------------------------------------------------------------------------

class TestGenerateCandidates:
    """Tests for ClusterKeywordService._generate_candidates."""

    @pytest.mark.asyncio
    async def test_success_with_brand_context(self):
        """Generates candidates with brand context in prompt."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.return_value = CompletionResult(
            success=True,
            text=_candidates_json(10),
            input_tokens=500,
            output_tokens=300,
        )

        brand_context = "## Brand\nCompany: TestCo"
        result = await service._generate_candidates("hiking boots", brand_context)

        # Seed keyword should be prepended
        assert result[0]["keyword"] == "hiking boots"
        assert result[0]["role_hint"] == "parent"
        assert result[0]["expansion_strategy"] == "seed"

        # Total count: 1 seed + 10 generated
        assert len(result) == 11

        # Verify Claude was called with brand context
        call_args = claude.complete.call_args
        prompt = call_args.kwargs.get("user_prompt") or call_args[1].get("user_prompt") or call_args[0][0]
        assert "Brand Context" in prompt

    @pytest.mark.asyncio
    async def test_prompt_includes_11_strategies(self):
        """Prompt includes all 11 expansion strategies."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.return_value = CompletionResult(
            success=True,
            text=_candidates_json(10),
            input_tokens=500,
            output_tokens=300,
        )

        await service._generate_candidates("hiking boots", "")

        call_args = claude.complete.call_args
        prompt = call_args.kwargs.get("user_prompt") or call_args[0][0]
        strategies = [
            "Demographic", "Attribute", "Price/Value", "Use-Case",
            "Comparison/Intent", "Seasonal/Occasion", "Material/Type",
            "Experience Level", "Problem/Solution", "Terrain/Environment",
            "Values/Lifestyle",
        ]
        for strategy in strategies:
            assert strategy in prompt, f"Strategy '{strategy}' not found in prompt"

    @pytest.mark.asyncio
    async def test_json_parsing_with_markdown_code_blocks(self):
        """JSON wrapped in ```json code blocks is parsed correctly."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        raw_json = _candidates_json(8)
        claude.complete.return_value = CompletionResult(
            success=True,
            text=f"```json\n{raw_json}\n```",
            input_tokens=500,
            output_tokens=300,
        )

        result = await service._generate_candidates("hiking boots", "")
        # 1 seed + 8 generated
        assert len(result) == 9

    @pytest.mark.asyncio
    async def test_seed_keyword_included_first(self):
        """Seed keyword is always the first candidate with role_hint='parent'."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.return_value = CompletionResult(
            success=True,
            text=_candidates_json(6),
            input_tokens=500,
            output_tokens=300,
        )

        result = await service._generate_candidates("HIKING Boots ", "")
        assert result[0]["keyword"] == "hiking boots"
        assert result[0]["role_hint"] == "parent"

    @pytest.mark.asyncio
    async def test_seed_keyword_deduplication(self):
        """If Claude includes the seed keyword, it's deduplicated."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        # Generate candidates where one matches the seed
        candidates = [
            {"keyword": "hiking boots", "expansion_strategy": "seed-dup", "rationale": "Dup", "estimated_intent": "commercial"},
        ]
        for i in range(7):
            candidates.append({
                "keyword": f"variant {i}",
                "expansion_strategy": "attribute",
                "rationale": "test",
                "estimated_intent": "commercial",
            })

        claude.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps(candidates),
            input_tokens=500,
            output_tokens=300,
        )

        result = await service._generate_candidates("hiking boots", "")
        # Only 1 seed + 7 non-seed = 8 total (duplicate removed)
        seed_count = sum(1 for c in result if c["keyword"] == "hiking boots")
        assert seed_count == 1

    @pytest.mark.asyncio
    async def test_claude_failure_raises_valueerror(self):
        """Claude returning failure raises ValueError."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.return_value = CompletionResult(
            success=False,
            error="API error",
        )

        with pytest.raises(ValueError, match="Claude candidate generation failed"):
            await service._generate_candidates("hiking boots", "")

    @pytest.mark.asyncio
    async def test_too_few_candidates_raises_valueerror(self):
        """Fewer than 5 valid candidates raises ValueError."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        # Only 3 candidates (below min of 5)
        claude.complete.return_value = CompletionResult(
            success=True,
            text=_candidates_json(3),
            input_tokens=500,
            output_tokens=300,
        )

        with pytest.raises(ValueError, match="Too few valid candidates"):
            await service._generate_candidates("hiking boots", "")


# ---------------------------------------------------------------------------
# Test _enrich_with_volume
# ---------------------------------------------------------------------------

class TestEnrichWithVolume:
    """Tests for ClusterKeywordService._enrich_with_volume."""

    @pytest.mark.asyncio
    async def test_success_with_volume_data(self):
        """Successful enrichment merges volume data into candidates."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        candidates = [
            {"keyword": "hiking boots"},
            {"keyword": "waterproof hiking boots"},
        ]

        dataforseo.get_keyword_volume_batch.return_value = KeywordVolumeResult(
            success=True,
            keywords=[
                KeywordVolumeData(
                    keyword="hiking boots",
                    search_volume=12000,
                    cpc=1.50,
                    competition=0.65,
                    competition_level="HIGH",
                ),
                KeywordVolumeData(
                    keyword="waterproof hiking boots",
                    search_volume=3500,
                    cpc=1.20,
                    competition=0.45,
                    competition_level="MEDIUM",
                ),
            ],
            cost=0.05,
            duration_ms=200,
        )

        result = await service._enrich_with_volume(candidates)

        assert result[0]["search_volume"] == 12000
        assert result[0]["cpc"] == 1.50
        assert result[0]["competition"] == 0.65
        assert result[0]["competition_level"] == "HIGH"
        assert result[1]["search_volume"] == 3500
        assert "volume_unavailable" not in result[0]

    @pytest.mark.asyncio
    async def test_dataforseo_unavailable(self):
        """DataForSEO unavailable sets volume_unavailable flag."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client(available=False)
        service = ClusterKeywordService(claude, dataforseo)

        candidates = [{"keyword": "hiking boots"}]
        result = await service._enrich_with_volume(candidates)

        assert result[0]["volume_unavailable"] is True

    @pytest.mark.asyncio
    async def test_api_failure_returns_unchanged_with_warning(self):
        """API failure returns candidates unchanged with volume_unavailable flag."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        candidates = [{"keyword": "hiking boots"}]

        dataforseo.get_keyword_volume_batch.return_value = KeywordVolumeResult(
            success=False,
            error="API timeout",
        )

        result = await service._enrich_with_volume(candidates)

        assert result[0]["volume_unavailable"] is True
        assert result[0]["keyword"] == "hiking boots"

    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_unchanged(self):
        """Unexpected exception returns candidates with volume_unavailable."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        candidates = [{"keyword": "hiking boots"}]

        dataforseo.get_keyword_volume_batch.side_effect = RuntimeError("Connection lost")

        result = await service._enrich_with_volume(candidates)

        assert result[0]["volume_unavailable"] is True

    @pytest.mark.asyncio
    async def test_keyword_not_found_in_results(self):
        """Keyword not in volume results gets None values."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        candidates = [{"keyword": "rare obscure keyword"}]

        dataforseo.get_keyword_volume_batch.return_value = KeywordVolumeResult(
            success=True,
            keywords=[],  # No results returned
            cost=0.01,
            duration_ms=100,
        )

        result = await service._enrich_with_volume(candidates)

        assert result[0]["search_volume"] is None
        assert result[0]["cpc"] is None
        assert result[0]["competition"] is None
        assert result[0]["competition_level"] is None
        assert "volume_unavailable" not in result[0]


# ---------------------------------------------------------------------------
# Test _filter_and_assign_roles
# ---------------------------------------------------------------------------

class TestFilterAndAssignRoles:
    """Tests for ClusterKeywordService._filter_and_assign_roles."""

    @pytest.mark.asyncio
    async def test_parent_child_assignment(self):
        """Seed keyword gets role=parent, others get role=child."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.return_value = CompletionResult(
            success=True,
            text=_filter_json("hiking boots", child_count=5),
            input_tokens=500,
            output_tokens=300,
        )

        candidates = [
            {"keyword": "hiking boots", "search_volume": 12000, "cpc": 1.5, "competition": 0.65, "competition_level": "HIGH", "expansion_strategy": "seed"},
        ]
        for i in range(5):
            candidates.append({
                "keyword": f"child keyword {i + 1}",
                "search_volume": 3000 - i * 500,
                "cpc": 1.0,
                "competition": 0.4,
                "competition_level": "MEDIUM",
                "expansion_strategy": "attribute",
            })

        result = await service._filter_and_assign_roles(candidates, "hiking boots")

        # Parent is first
        assert result[0]["role"] == "parent"
        assert result[0]["keyword"] == "hiking boots"

        # Children follow
        for r in result[1:]:
            assert r["role"] == "child"

    @pytest.mark.asyncio
    async def test_url_slug_format(self):
        """URL slugs are in correct format."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.return_value = CompletionResult(
            success=True,
            text=_filter_json("hiking boots", child_count=3),
            input_tokens=500,
            output_tokens=300,
        )

        candidates = [
            {"keyword": "hiking boots", "search_volume": 12000, "expansion_strategy": "seed"},
            {"keyword": "child keyword 1", "search_volume": 3000, "expansion_strategy": "attribute"},
            {"keyword": "child keyword 2", "search_volume": 2000, "expansion_strategy": "demographic"},
            {"keyword": "child keyword 3", "search_volume": 1000, "expansion_strategy": "use-case"},
        ]

        result = await service._filter_and_assign_roles(candidates, "hiking boots")

        for r in result:
            slug = r["url_slug"]
            assert slug == slug.lower()
            assert " " not in slug
            # Only alphanumeric and hyphens
            assert all(c.isalnum() or c == "-" for c in slug)

    @pytest.mark.asyncio
    async def test_composite_score_calculation(self):
        """Composite scores are calculated and results sorted."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.return_value = CompletionResult(
            success=True,
            text=_filter_json("hiking boots", child_count=3),
            input_tokens=500,
            output_tokens=300,
        )

        candidates = [
            {"keyword": "hiking boots", "search_volume": 12000, "competition": 0.65, "expansion_strategy": "seed"},
            {"keyword": "child keyword 1", "search_volume": 3000, "competition": 0.4, "expansion_strategy": "attribute"},
            {"keyword": "child keyword 2", "search_volume": 2000, "competition": 0.3, "expansion_strategy": "demographic"},
            {"keyword": "child keyword 3", "search_volume": 1000, "competition": 0.2, "expansion_strategy": "use-case"},
        ]

        result = await service._filter_and_assign_roles(candidates, "hiking boots")

        for r in result:
            assert "composite_score" in r
            assert isinstance(r["composite_score"], float)
            assert r["composite_score"] >= 0

        # Children should be sorted by composite_score descending
        child_scores = [r["composite_score"] for r in result[1:]]
        assert child_scores == sorted(child_scores, reverse=True)

    @pytest.mark.asyncio
    async def test_seed_role_enforced_in_code(self):
        """Seed keyword always gets parent role even if Claude says child."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        # Claude incorrectly assigns child to seed
        filter_data = [
            {"keyword": "hiking boots", "role": "child", "url_slug": "hiking-boots", "reasoning": "test", "relevance": 0.9},
            {"keyword": "other kw 1", "role": "parent", "url_slug": "other-kw-1", "reasoning": "test", "relevance": 0.8},
            {"keyword": "other kw 2", "role": "child", "url_slug": "other-kw-2", "reasoning": "test", "relevance": 0.7},
            {"keyword": "other kw 3", "role": "child", "url_slug": "other-kw-3", "reasoning": "test", "relevance": 0.6},
        ]

        claude.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps(filter_data),
            input_tokens=500,
            output_tokens=300,
        )

        candidates = [
            {"keyword": "hiking boots", "search_volume": 12000, "expansion_strategy": "seed"},
            {"keyword": "other kw 1", "search_volume": 5000, "expansion_strategy": "attribute"},
            {"keyword": "other kw 2", "search_volume": 3000, "expansion_strategy": "demographic"},
            {"keyword": "other kw 3", "search_volume": 2000, "expansion_strategy": "use-case"},
        ]

        result = await service._filter_and_assign_roles(candidates, "hiking boots")

        # Seed should be parent regardless of LLM output
        seed_result = [r for r in result if r["keyword"] == "hiking boots"][0]
        assert seed_result["role"] == "parent"

        # Non-seed should be child
        for r in result:
            if r["keyword"] != "hiking boots":
                assert r["role"] == "child"

    @pytest.mark.asyncio
    async def test_duplicate_filtering(self):
        """Results are deduplicated based on keyword matching."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        # Claude returns duplicates
        filter_data = [
            {"keyword": "hiking boots", "role": "parent", "url_slug": "hiking-boots", "reasoning": "test", "relevance": 0.9},
            {"keyword": "waterproof boots", "role": "child", "url_slug": "waterproof-boots", "reasoning": "test", "relevance": 0.8},
            {"keyword": "waterproof boots", "role": "child", "url_slug": "waterproof-boots-2", "reasoning": "test dup", "relevance": 0.7},
            {"keyword": "leather boots", "role": "child", "url_slug": "leather-boots", "reasoning": "test", "relevance": 0.6},
        ]

        claude.complete.return_value = CompletionResult(
            success=True,
            text=json.dumps(filter_data),
            input_tokens=500,
            output_tokens=300,
        )

        candidates = [
            {"keyword": "hiking boots", "search_volume": 12000, "expansion_strategy": "seed"},
            {"keyword": "waterproof boots", "search_volume": 5000, "expansion_strategy": "attribute"},
            {"keyword": "leather boots", "search_volume": 3000, "expansion_strategy": "material/type"},
        ]

        result = await service._filter_and_assign_roles(candidates, "hiking boots")

        # The service processes all items from Claude but deduplication happens
        # via candidate_map lookup — each keyword maps to one original entry
        keywords = [r["keyword"] for r in result]
        assert "hiking boots" in keywords
        assert "waterproof boots" in keywords
        assert "leather boots" in keywords

    @pytest.mark.asyncio
    async def test_claude_failure_raises_valueerror(self):
        """Claude failure raises ValueError."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.return_value = CompletionResult(
            success=False,
            error="API down",
        )

        with pytest.raises(ValueError, match="Claude filtering failed"):
            await service._filter_and_assign_roles(
                [{"keyword": "hiking boots"}], "hiking boots"
            )


# ---------------------------------------------------------------------------
# Test _keyword_to_slug
# ---------------------------------------------------------------------------

class TestKeywordToSlug:
    """Tests for URL slug generation edge cases."""

    def test_basic_conversion(self):
        """Basic keyword converts to lowercase hyphenated slug."""
        assert ClusterKeywordService._keyword_to_slug("Hiking Boots") == "hiking-boots"

    def test_special_characters_stripped(self):
        """Special characters are stripped from slugs."""
        assert ClusterKeywordService._keyword_to_slug("women's hiking boots!") == "womens-hiking-boots"

    def test_multiple_spaces_collapsed(self):
        """Multiple spaces collapse into single hyphen."""
        assert ClusterKeywordService._keyword_to_slug("hiking   boots") == "hiking-boots"

    def test_leading_trailing_hyphens_stripped(self):
        """Leading and trailing hyphens are stripped."""
        assert ClusterKeywordService._keyword_to_slug("--hiking boots--") == "hiking-boots"

    def test_long_keyword_truncated(self):
        """Keywords longer than 60 chars are truncated."""
        long_keyword = "a" * 80
        slug = ClusterKeywordService._keyword_to_slug(long_keyword)
        assert len(slug) <= 60

    def test_truncation_no_trailing_hyphen(self):
        """Truncated slug doesn't end with a trailing hyphen."""
        # Create a keyword that would produce a hyphen at position 60
        keyword = "a" * 55 + " " + "b" * 10  # "aaaa...a bbbbb..." -> "aaaa...a-bbbbb..."
        slug = ClusterKeywordService._keyword_to_slug(keyword)
        assert len(slug) <= 60
        assert not slug.endswith("-")

    def test_spaces_become_hyphens(self):
        """Spaces convert to hyphens."""
        assert ClusterKeywordService._keyword_to_slug("best hiking boots for women") == "best-hiking-boots-for-women"

    def test_numbers_preserved(self):
        """Numbers are preserved in slugs."""
        assert ClusterKeywordService._keyword_to_slug("top 10 boots") == "top-10-boots"

    def test_mixed_special_chars(self):
        """Mix of special characters all stripped correctly."""
        assert ClusterKeywordService._keyword_to_slug("boots & shoes (2024)") == "boots-shoes-2024"

    def test_already_clean_slug(self):
        """Already clean slug passes through unchanged."""
        assert ClusterKeywordService._keyword_to_slug("hiking-boots") == "hiking-boots"

    def test_unicode_characters_stripped(self):
        """Unicode/non-ASCII characters are stripped."""
        assert ClusterKeywordService._keyword_to_slug("café boots") == "caf-boots"

    def test_empty_after_stripping(self):
        """All-special-char keyword produces empty slug."""
        result = ClusterKeywordService._keyword_to_slug("!@#$%^&*()")
        assert result == ""


# ---------------------------------------------------------------------------
# Test _calculate_composite_score
# ---------------------------------------------------------------------------

class TestCalculateCompositeScore:
    """Tests for composite score calculation."""

    def test_with_all_values(self):
        """Score calculated correctly with all values provided."""
        score = ClusterKeywordService._calculate_composite_score(
            volume=10000, competition=0.5, relevance=0.8
        )
        assert isinstance(score, float)
        assert score > 0

    def test_null_volume(self):
        """Null volume contributes 0 to volume component."""
        score = ClusterKeywordService._calculate_composite_score(
            volume=None, competition=0.5, relevance=0.8
        )
        assert score > 0  # Relevance and competition still contribute

    def test_null_competition(self):
        """Null competition defaults to mid-range (50)."""
        score = ClusterKeywordService._calculate_composite_score(
            volume=1000, competition=None, relevance=0.8
        )
        assert isinstance(score, float)
        assert score > 0

    def test_competition_normalization(self):
        """Competition > 1.0 is normalized by dividing by 100."""
        score_normalized = ClusterKeywordService._calculate_composite_score(
            volume=1000, competition=50.0, relevance=0.8
        )
        score_raw = ClusterKeywordService._calculate_composite_score(
            volume=1000, competition=0.5, relevance=0.8
        )
        assert score_normalized == score_raw

    def test_zero_volume(self):
        """Zero volume contributes 0 to volume component."""
        score = ClusterKeywordService._calculate_composite_score(
            volume=0, competition=0.5, relevance=0.8
        )
        # Only relevance (35%) and competition (15%) contribute
        assert score > 0


# ---------------------------------------------------------------------------
# Test generate_cluster (full pipeline)
# ---------------------------------------------------------------------------

class TestGenerateCluster:
    """Tests for generate_cluster() orchestrator with all mocks."""

    @pytest.fixture
    async def project(self, db_session: AsyncSession) -> Project:
        """Create a test project in the database."""
        project = Project(
            id=str(uuid4()),
            name="Test Project",
            site_url="https://example.com",
        )
        db_session.add(project)
        await db_session.flush()
        return project

    @pytest.mark.asyncio
    async def test_success_full_pipeline(self, db_session: AsyncSession, project: Project):
        """Full pipeline success: generate → enrich → filter → persist."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        # Generate 22 candidates so that with volume data for all,
        # the loop stops after 1 iteration (>= 20 with volume).
        claude.complete.side_effect = [
            # Stage 1 iteration 1: Generate candidates
            CompletionResult(
                success=True,
                text=_candidates_json(22),
                input_tokens=500,
                output_tokens=300,
            ),
            # Stage 3: Filter and assign roles
            CompletionResult(
                success=True,
                text=_filter_json("hiking boots", child_count=5),
                input_tokens=600,
                output_tokens=400,
            ),
        ]

        # Return volume data for all candidates so loop breaks after 1 iteration
        volume_keywords = [
            KeywordVolumeData(keyword=f"hiking boots keyword {i + 1}", search_volume=500 + i * 100, cpc=1.5, competition=0.65, competition_level="HIGH")
            for i in range(22)
        ] + [
            KeywordVolumeData(keyword="hiking boots", search_volume=12000, cpc=1.5, competition=0.65, competition_level="HIGH"),
        ]
        dataforseo.get_keyword_volume_batch.return_value = KeywordVolumeResult(
            success=True,
            keywords=volume_keywords,
            cost=0.05,
            duration_ms=200,
        )

        result = await service.generate_cluster(
            seed_keyword="hiking boots",
            project_id=project.id,
            brand_config=_full_brand_config(),
            db=db_session,
        )

        assert "cluster_id" in result
        assert "suggestions" in result
        assert "generation_metadata" in result
        assert "warnings" in result
        assert len(result["warnings"]) == 0
        assert len(result["suggestions"]) == 6  # 1 parent + 5 children

        # Verify metadata
        meta = result["generation_metadata"]
        assert meta["candidates_generated"] > 0
        assert meta["volume_unavailable"] is False
        assert meta["iterations"] == 1  # Stopped after 1 iteration
        assert "total_time_ms" in meta

        # Verify DB persistence
        cluster_result = await db_session.execute(
            select(KeywordCluster).where(KeywordCluster.id == result["cluster_id"])
        )
        cluster = cluster_result.scalar_one()
        assert cluster.status == ClusterStatus.SUGGESTIONS_READY.value
        assert cluster.seed_keyword == "hiking boots"

    @pytest.mark.asyncio
    async def test_partial_failure_dataforseo_down(self, db_session: AsyncSession, project: Project):
        """Pipeline succeeds with warning when DataForSEO is down."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client(available=False)
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.side_effect = [
            CompletionResult(
                success=True,
                text=_candidates_json(8),
                input_tokens=500,
                output_tokens=300,
            ),
            CompletionResult(
                success=True,
                text=_filter_json("hiking boots", child_count=5),
                input_tokens=600,
                output_tokens=400,
            ),
        ]

        result = await service.generate_cluster(
            seed_keyword="hiking boots",
            project_id=project.id,
            brand_config=_full_brand_config(),
            db=db_session,
        )

        assert len(result["warnings"]) > 0
        assert "volume" in result["warnings"][0].lower() or "unavailable" in result["warnings"][0].lower()
        assert result["generation_metadata"]["volume_unavailable"] is True
        assert "cluster_id" in result  # Still succeeds

    @pytest.mark.asyncio
    async def test_total_failure_claude_down(self, db_session: AsyncSession, project: Project):
        """Pipeline raises ValueError when Claude is down (Stage 1 failure)."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.return_value = CompletionResult(
            success=False,
            error="Claude API unavailable",
        )

        with pytest.raises(ValueError, match="Stage 1"):
            await service.generate_cluster(
                seed_keyword="hiking boots",
                project_id=project.id,
                brand_config=_full_brand_config(),
                db=db_session,
            )

    @pytest.mark.asyncio
    async def test_stage3_failure_raises_valueerror(self, db_session: AsyncSession, project: Project):
        """Pipeline raises ValueError when Stage 3 (filtering) fails."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.side_effect = [
            # Stage 1 succeeds (22 candidates so loop stops after 1 iteration)
            CompletionResult(
                success=True,
                text=_candidates_json(22),
                input_tokens=500,
                output_tokens=300,
            ),
            # Stage 3 fails
            CompletionResult(
                success=False,
                error="Claude API unavailable",
            ),
        ]

        volume_keywords = [
            KeywordVolumeData(keyword=f"hiking boots keyword {i + 1}", search_volume=500 + i * 100, cpc=1.5, competition=0.65, competition_level="HIGH")
            for i in range(22)
        ] + [
            KeywordVolumeData(keyword="hiking boots", search_volume=12000, cpc=1.5, competition=0.65, competition_level="HIGH"),
        ]
        dataforseo.get_keyword_volume_batch.return_value = KeywordVolumeResult(
            success=True,
            keywords=volume_keywords,
            cost=0.01,
            duration_ms=100,
        )

        with pytest.raises(ValueError, match="Stage 3"):
            await service.generate_cluster(
                seed_keyword="hiking boots",
                project_id=project.id,
                brand_config=_full_brand_config(),
                db=db_session,
            )

    @pytest.mark.asyncio
    async def test_name_defaults_to_seed_keyword(self, db_session: AsyncSession, project: Project):
        """Cluster name defaults to seed keyword when not provided."""
        claude = _make_claude_client()
        dataforseo = _make_dataforseo_client()
        service = ClusterKeywordService(claude, dataforseo)

        claude.complete.side_effect = [
            CompletionResult(success=True, text=_candidates_json(22), input_tokens=500, output_tokens=300),
            CompletionResult(success=True, text=_filter_json("hiking boots", child_count=3), input_tokens=600, output_tokens=400),
        ]
        volume_keywords = [
            KeywordVolumeData(keyword=f"hiking boots keyword {i + 1}", search_volume=500 + i * 100, cpc=1.5, competition=0.65, competition_level="HIGH")
            for i in range(22)
        ] + [
            KeywordVolumeData(keyword="hiking boots", search_volume=12000, cpc=1.5, competition=0.65, competition_level="HIGH"),
        ]
        dataforseo.get_keyword_volume_batch.return_value = KeywordVolumeResult(success=True, keywords=volume_keywords, cost=0.01, duration_ms=100)

        result = await service.generate_cluster(
            seed_keyword="hiking boots",
            project_id=project.id,
            brand_config={},
            db=db_session,
        )

        cluster_result = await db_session.execute(
            select(KeywordCluster).where(KeywordCluster.id == result["cluster_id"])
        )
        cluster = cluster_result.scalar_one()
        assert cluster.name == "hiking boots"


# ---------------------------------------------------------------------------
# Test bulk_approve_cluster
# ---------------------------------------------------------------------------

class TestBulkApproveCluster:
    """Tests for ClusterKeywordService.bulk_approve_cluster."""

    @pytest.fixture
    async def project(self, db_session: AsyncSession) -> Project:
        """Create a test project."""
        project = Project(
            id=str(uuid4()),
            name="Approve Test Project",
            site_url="https://example.com",
        )
        db_session.add(project)
        await db_session.flush()
        return project

    @pytest.fixture
    async def cluster_with_approved_pages(
        self, db_session: AsyncSession, project: Project
    ) -> KeywordCluster:
        """Create a cluster with approved pages."""
        cluster = KeywordCluster(
            id=str(uuid4()),
            project_id=project.id,
            seed_keyword="hiking boots",
            name="Hiking Boots Cluster",
            status=ClusterStatus.SUGGESTIONS_READY.value,
        )
        db_session.add(cluster)
        await db_session.flush()

        # Parent page (approved)
        parent = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="hiking boots",
            role="parent",
            url_slug="hiking-boots",
            is_approved=True,
            search_volume=12000,
            composite_score=85.5,
        )
        db_session.add(parent)

        # Child page (approved)
        child = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="waterproof hiking boots",
            role="child",
            url_slug="waterproof-hiking-boots",
            is_approved=True,
            search_volume=3500,
            composite_score=72.3,
        )
        db_session.add(child)

        # Child page (not approved)
        unapproved = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="cheap hiking boots",
            role="child",
            url_slug="cheap-hiking-boots",
            is_approved=False,
        )
        db_session.add(unapproved)

        await db_session.flush()
        return cluster

    @pytest.mark.asyncio
    async def test_creates_crawled_pages_with_source_cluster(
        self, db_session: AsyncSession, cluster_with_approved_pages: KeywordCluster
    ):
        """Approved pages create CrawledPage records with source='cluster'."""
        cluster = cluster_with_approved_pages

        result = await ClusterKeywordService.bulk_approve_cluster(cluster.id, db_session)

        assert result["bridged_count"] == 2
        assert len(result["crawled_page_ids"]) == 2

        # Verify CrawledPages created
        for cp_id in result["crawled_page_ids"]:
            cp_result = await db_session.execute(
                select(CrawledPage).where(CrawledPage.id == cp_id)
            )
            cp = cp_result.scalar_one()
            assert cp.source == "cluster"
            assert cp.status == "completed"
            assert cp.category == "collection"
            assert cp.project_id == cluster.project_id

    @pytest.mark.asyncio
    async def test_creates_page_keywords_with_priority_for_parent(
        self, db_session: AsyncSession, cluster_with_approved_pages: KeywordCluster
    ):
        """PageKeywords created with is_priority=True for parent role."""
        cluster = cluster_with_approved_pages

        result = await ClusterKeywordService.bulk_approve_cluster(cluster.id, db_session)

        # Scope queries to the crawled_page_ids created in this call
        cp_ids = result["crawled_page_ids"]

        # Find the PageKeywords for the parent (hiking boots)
        pk_result = await db_session.execute(
            select(PageKeywords).where(
                PageKeywords.primary_keyword == "hiking boots",
                PageKeywords.crawled_page_id.in_(cp_ids),
            )
        )
        parent_pk = pk_result.scalar_one()
        assert parent_pk.is_approved is True
        assert parent_pk.is_priority is True
        assert parent_pk.search_volume == 12000

        # Find the PageKeywords for the child
        pk_result = await db_session.execute(
            select(PageKeywords).where(
                PageKeywords.primary_keyword == "waterproof hiking boots",
                PageKeywords.crawled_page_id.in_(cp_ids),
            )
        )
        child_pk = pk_result.scalar_one()
        assert child_pk.is_approved is True
        assert child_pk.is_priority is False

    @pytest.mark.asyncio
    async def test_crawled_page_id_backref(
        self, db_session: AsyncSession, cluster_with_approved_pages: KeywordCluster
    ):
        """ClusterPage.crawled_page_id is set after approval."""
        cluster = cluster_with_approved_pages

        result = await ClusterKeywordService.bulk_approve_cluster(cluster.id, db_session)

        # Check that approved ClusterPages now have crawled_page_id
        pages_result = await db_session.execute(
            select(ClusterPage).where(
                ClusterPage.cluster_id == cluster.id,
                ClusterPage.is_approved == True,  # noqa: E712
            )
        )
        for page in pages_result.scalars().all():
            assert page.crawled_page_id is not None
            assert page.crawled_page_id in result["crawled_page_ids"]

    @pytest.mark.asyncio
    async def test_error_no_approved_pages(
        self, db_session: AsyncSession, project: Project
    ):
        """Raises ValueError when no approved pages exist."""
        cluster = KeywordCluster(
            id=str(uuid4()),
            project_id=project.id,
            seed_keyword="empty cluster",
            name="Empty Cluster",
            status=ClusterStatus.SUGGESTIONS_READY.value,
        )
        db_session.add(cluster)

        # Add one unapproved page
        page = ClusterPage(
            id=str(uuid4()),
            cluster_id=cluster.id,
            keyword="some keyword",
            role="child",
            url_slug="some-keyword",
            is_approved=False,
        )
        db_session.add(page)
        await db_session.flush()

        with pytest.raises(ValueError, match="No approved pages"):
            await ClusterKeywordService.bulk_approve_cluster(cluster.id, db_session)

    @pytest.mark.asyncio
    async def test_error_already_approved(
        self, db_session: AsyncSession, project: Project
    ):
        """Raises ValueError when cluster is already approved."""
        cluster = KeywordCluster(
            id=str(uuid4()),
            project_id=project.id,
            seed_keyword="approved cluster",
            name="Approved Cluster",
            status=ClusterStatus.APPROVED.value,
        )
        db_session.add(cluster)
        await db_session.flush()

        with pytest.raises(ValueError, match="already has status"):
            await ClusterKeywordService.bulk_approve_cluster(cluster.id, db_session)

    @pytest.mark.asyncio
    async def test_cluster_status_updated_to_approved(
        self, db_session: AsyncSession, cluster_with_approved_pages: KeywordCluster
    ):
        """Cluster status is updated to 'approved' on success."""
        cluster = cluster_with_approved_pages

        await ClusterKeywordService.bulk_approve_cluster(cluster.id, db_session)

        # Re-fetch cluster
        cluster_result = await db_session.execute(
            select(KeywordCluster).where(KeywordCluster.id == cluster.id)
        )
        updated_cluster = cluster_result.scalar_one()
        assert updated_cluster.status == ClusterStatus.APPROVED.value
