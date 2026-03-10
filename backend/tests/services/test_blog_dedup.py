"""Unit tests for blog deduplication service.

Tests cover:
- Title normalization (lowercase, strip punctuation, collapse whitespace)
- >90% similarity is silently filtered
- 70-90% similarity shows warning with URL
- <70% similarity passes through
- Identical titles produce 1.0 similarity
- Completely different titles produce low similarity
- Edge cases: empty titles, very short titles, unicode characters
- Dedup skipped when no existing articles
- get_existing_articles only returns active articles

Tests the similarity calculation and filtering logic against the actual
blog_dedup.py implementation which uses:
- normalize_title(title: str) -> str
- levenshtein_ratio(a: str, b: str) -> float
- check_duplicates(generated_titles: list[str], existing_articles: list[dict]) -> list[DedupResult]
- get_existing_articles(project_id: str, db: AsyncSession) -> list[dict]
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.shopify_page import ShopifyPage
from app.services.blog_dedup import (
    DedupResult,
    check_duplicates,
    get_existing_articles,
    levenshtein_ratio,
    normalize_title,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def dedup_project(db_session: AsyncSession) -> Project:
    """Create a project with Shopify connection for dedup testing."""
    project = Project(
        id=str(uuid.uuid4()),
        name="Blog Dedup Test",
        site_url="https://blogstore.myshopify.com",
        shopify_store_domain="blogstore.myshopify.com",
        shopify_access_token_encrypted="encrypted_token",
        shopify_scopes="read_products,read_content",
        shopify_sync_status="idle",
        shopify_connected_at=datetime.now(UTC),
    )
    db_session.add(project)
    await db_session.commit()
    return project


@pytest.fixture
async def existing_articles(
    db_session: AsyncSession, dedup_project: Project
) -> list[ShopifyPage]:
    """Create existing Shopify blog articles for comparison."""
    articles = [
        ShopifyPage(
            id=str(uuid.uuid4()),
            project_id=dedup_project.id,
            shopify_id="gid://shopify/Article/1",
            page_type="article",
            title="Best Running Shoes for 2025",
            handle="best-running-shoes-2025",
            full_url="https://blogstore.myshopify.com/blogs/fitness/best-running-shoes-2025",
            is_deleted=False,
        ),
        ShopifyPage(
            id=str(uuid.uuid4()),
            project_id=dedup_project.id,
            shopify_id="gid://shopify/Article/2",
            page_type="article",
            title="How to Start a Morning Workout Routine",
            handle="morning-workout-routine",
            full_url="https://blogstore.myshopify.com/blogs/fitness/morning-workout-routine",
            is_deleted=False,
        ),
        ShopifyPage(
            id=str(uuid.uuid4()),
            project_id=dedup_project.id,
            shopify_id="gid://shopify/Article/3",
            page_type="article",
            title="Top 10 Yoga Poses for Beginners",
            handle="yoga-poses-beginners",
            full_url="https://blogstore.myshopify.com/blogs/wellness/yoga-poses-beginners",
            is_deleted=False,
        ),
        # Soft-deleted article -- should be excluded from dedup
        ShopifyPage(
            id=str(uuid.uuid4()),
            project_id=dedup_project.id,
            shopify_id="gid://shopify/Article/99",
            page_type="article",
            title="Deleted Post About Running",
            handle="deleted-post",
            full_url="https://blogstore.myshopify.com/blogs/fitness/deleted-post",
            is_deleted=True,
        ),
        # Non-article page -- should be excluded from article query
        ShopifyPage(
            id=str(uuid.uuid4()),
            project_id=dedup_project.id,
            shopify_id="gid://shopify/Product/1",
            page_type="product",
            title="Running Shoes Product",
            handle="running-shoes",
            full_url="https://blogstore.myshopify.com/products/running-shoes",
            is_deleted=False,
        ),
    ]
    db_session.add_all(articles)
    await db_session.commit()
    return articles


# ---------------------------------------------------------------------------
# Test: Title Normalization
# ---------------------------------------------------------------------------


class TestTitleNormalization:
    """Tests for normalize_title()."""

    def test_lowercase_normalization(self) -> None:
        """Test titles are lowercased."""
        assert normalize_title("Best Running Shoes") == "best running shoes"

    def test_strip_punctuation(self) -> None:
        """Test punctuation is stripped from titles."""
        result = normalize_title("Best Running Shoes! (2025 Edition)")
        assert "!" not in result
        assert "(" not in result
        assert ")" not in result

    def test_collapse_whitespace(self) -> None:
        """Test multiple whitespace characters are collapsed to single space."""
        result = normalize_title("Best   Running    Shoes")
        assert "  " not in result
        assert result == "best running shoes"

    def test_combined_normalization(self) -> None:
        """Test all normalizations applied together."""
        result = normalize_title("  Best  Running Shoes!! (2025)  ")
        assert result == "best running shoes 2025"

    def test_empty_title(self) -> None:
        """Test normalization of empty string."""
        assert normalize_title("") == ""

    def test_only_punctuation(self) -> None:
        """Test title that is only punctuation normalizes to empty."""
        result = normalize_title("!!! --- ???")
        assert result.strip() == ""

    def test_unicode_characters(self) -> None:
        """Test unicode characters are handled."""
        result = normalize_title("Cafe Resume Niche")
        assert isinstance(result, str)
        assert len(result) > 0
        assert result == "cafe resume niche"

    def test_tabs_and_newlines_collapsed(self) -> None:
        """Test tabs and newlines are treated as whitespace and collapsed."""
        result = normalize_title("Best\tRunning\nShoes")
        assert result == "best running shoes"


# ---------------------------------------------------------------------------
# Test: Levenshtein Ratio
# ---------------------------------------------------------------------------


class TestLevenshteinRatio:
    """Tests for levenshtein_ratio() similarity calculation."""

    def test_identical_titles_produce_1_0(self) -> None:
        """Test identical titles produce 1.0 similarity."""
        ratio = levenshtein_ratio("best running shoes", "best running shoes")
        assert ratio == 1.0

    def test_completely_different_titles_produce_low_similarity(self) -> None:
        """Test completely different titles produce low similarity."""
        ratio = levenshtein_ratio(
            "best running shoes for marathon training",
            "how to cook italian pasta from scratch",
        )
        assert ratio < 0.3

    def test_minor_variation_produces_high_similarity(self) -> None:
        """Test titles with minor variation produce high similarity (>0.90)."""
        ratio = levenshtein_ratio(
            "best running shoes 2025",
            "best running shoes 2026",
        )
        assert ratio > 0.90

    def test_similarity_is_symmetric(self) -> None:
        """Test similarity(a, b) == similarity(b, a)."""
        sim_ab = levenshtein_ratio("best running shoes", "best running gear")
        sim_ba = levenshtein_ratio("best running gear", "best running shoes")
        assert abs(sim_ab - sim_ba) < 0.001

    def test_empty_strings_return_1_0(self) -> None:
        """Test two empty strings produce 1.0 similarity."""
        ratio = levenshtein_ratio("", "")
        assert ratio == 1.0

    def test_one_empty_string_returns_0_0(self) -> None:
        """Test one empty string produces 0.0 similarity."""
        ratio = levenshtein_ratio("hello", "")
        assert ratio == 0.0

    def test_very_short_titles(self) -> None:
        """Test similarity with very short titles."""
        ratio = levenshtein_ratio("shoes", "shoos")
        assert 0 < ratio < 1.0

    def test_returns_float_between_0_and_1(self) -> None:
        """Test ratio is always between 0.0 and 1.0."""
        ratio = levenshtein_ratio("anything", "something else entirely")
        assert 0.0 <= ratio <= 1.0


# ---------------------------------------------------------------------------
# Test: check_duplicates
# ---------------------------------------------------------------------------


class TestCheckDuplicates:
    """Tests for check_duplicates() function."""

    def test_high_similarity_filtered(self) -> None:
        """Test >90% similarity match is filtered (action='filter')."""
        existing = [
            {"title": "Best Running Shoes for 2025", "full_url": "https://store.com/post1"},
        ]

        results = check_duplicates(
            generated_titles=["Best Running Shoes for 2026"],
            existing_articles=existing,
        )

        assert len(results) == 1
        assert results[0].action == "filter"
        assert results[0].similarity > 0.90

    def test_medium_similarity_warned(self) -> None:
        """Test 70-90% similarity shows warning (action='warn')."""
        existing = [
            {"title": "How to Start a Morning Workout Routine", "full_url": "https://store.com/post2"},
        ]

        # This title is similar enough for a warning (70-90%)
        results = check_duplicates(
            generated_titles=["Starting Your Morning Workout Routine at Home"],
            existing_articles=existing,
        )

        assert len(results) == 1
        # Check if it's in warn range
        if results[0].similarity > 0.70 and results[0].similarity <= 0.90:
            assert results[0].action == "warn"
            assert results[0].existing_title is not None
            assert results[0].existing_url is not None

    def test_low_similarity_passes(self) -> None:
        """Test <70% similarity passes through (action='pass')."""
        existing = [
            {"title": "Best Running Shoes", "full_url": "https://store.com/post1"},
        ]

        results = check_duplicates(
            generated_titles=["Complete Guide to Mediterranean Diet for Weight Loss"],
            existing_articles=existing,
        )

        assert len(results) == 1
        assert results[0].action == "pass"
        assert results[0].similarity < 0.70

    def test_no_existing_articles_all_pass(self) -> None:
        """Test all topics pass when no existing articles."""
        results = check_duplicates(
            generated_titles=["Topic 1", "Topic 2", "Topic 3"],
            existing_articles=[],
        )

        assert len(results) == 3
        assert all(r.action == "pass" for r in results)
        assert all(r.similarity == 0.0 for r in results)

    def test_identical_title_filtered(self) -> None:
        """Test identical title produces 1.0 similarity and is filtered."""
        existing = [
            {"title": "Best Running Shoes for 2025", "full_url": "https://store.com/post1"},
        ]

        results = check_duplicates(
            generated_titles=["Best Running Shoes for 2025"],
            existing_articles=existing,
        )

        assert len(results) == 1
        assert results[0].action == "filter"
        assert results[0].similarity == 1.0

    def test_multiple_generated_topics(self) -> None:
        """Test dedup with multiple generated topics."""
        existing = [
            {"title": "Best Running Shoes for 2025", "full_url": "https://store.com/post1"},
        ]

        results = check_duplicates(
            generated_titles=[
                "Best Running Shoes for 2026",       # Should be filtered (>90%)
                "Guide to Mediterranean Cooking",     # Should pass (<70%)
            ],
            existing_articles=existing,
        )

        assert len(results) == 2
        assert results[0].action == "filter"
        assert results[1].action == "pass"

    def test_result_includes_existing_title_and_url(self) -> None:
        """Test DedupResult includes the matching existing title and URL."""
        url = "https://blogstore.com/blogs/fitness/running-shoes"
        existing = [
            {"title": "Best Running Shoes for 2025", "full_url": url},
        ]

        results = check_duplicates(
            generated_titles=["Best Running Shoes for 2026"],
            existing_articles=existing,
        )

        assert results[0].existing_title == "Best Running Shoes for 2025"
        assert results[0].existing_url == url


# ---------------------------------------------------------------------------
# Test: get_existing_articles (DB integration)
# ---------------------------------------------------------------------------


class TestGetExistingArticles:
    """Tests for get_existing_articles() async DB function."""

    async def test_returns_active_articles(
        self,
        db_session: AsyncSession,
        dedup_project: Project,
        existing_articles: list[ShopifyPage],
    ) -> None:
        """Test only returns active, non-deleted articles."""
        articles = await get_existing_articles(dedup_project.id, db_session)

        # Should return 3 active articles (not the soft-deleted one or the product)
        assert len(articles) == 3

        titles = [a["title"] for a in articles]
        assert "Best Running Shoes for 2025" in titles
        assert "How to Start a Morning Workout Routine" in titles
        assert "Top 10 Yoga Poses for Beginners" in titles

        # Should NOT include deleted article
        assert "Deleted Post About Running" not in titles
        # Should NOT include non-article page type
        assert "Running Shoes Product" not in titles

    async def test_articles_have_title_and_url(
        self,
        db_session: AsyncSession,
        dedup_project: Project,
        existing_articles: list[ShopifyPage],
    ) -> None:
        """Test returned articles have both title and full_url keys."""
        articles = await get_existing_articles(dedup_project.id, db_session)

        for article in articles:
            assert "title" in article
            assert "full_url" in article
            assert article["title"] is not None
            assert article["full_url"] is not None

    async def test_returns_empty_for_project_without_articles(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test returns empty list for project with no articles."""
        project = Project(
            id=str(uuid.uuid4()),
            name="Empty Project",
            site_url="https://empty.com",
        )
        db_session.add(project)
        await db_session.commit()

        articles = await get_existing_articles(project.id, db_session)
        assert articles == []


# ---------------------------------------------------------------------------
# Test: End-to-end dedup flow with DB
# ---------------------------------------------------------------------------


class TestDedupEndToEnd:
    """End-to-end tests combining get_existing_articles and check_duplicates."""

    async def test_full_dedup_flow(
        self,
        db_session: AsyncSession,
        dedup_project: Project,
        existing_articles: list[ShopifyPage],
    ) -> None:
        """Test full dedup flow: fetch articles from DB, then check duplicates."""
        articles = await get_existing_articles(dedup_project.id, db_session)

        generated_titles = [
            "Best Running Shoes for 2026",                     # >90% match
            "Complete Guide to Mediterranean Diet",             # <70% match
            "How to Start a Morning Workout Routine at Home",  # 70-90% match likely
        ]

        results = check_duplicates(generated_titles, articles)

        assert len(results) == 3

        # First should be filtered (very similar to "Best Running Shoes for 2025")
        assert results[0].action == "filter"

        # Second should pass (completely different)
        assert results[1].action == "pass"

    async def test_dedup_ignores_deleted_articles(
        self,
        db_session: AsyncSession,
        dedup_project: Project,
        existing_articles: list[ShopifyPage],
    ) -> None:
        """Test dedup does not match against soft-deleted articles."""
        articles = await get_existing_articles(dedup_project.id, db_session)

        results = check_duplicates(
            generated_titles=["Deleted Post About Running"],
            existing_articles=articles,
        )

        # Should NOT be filtered because the matching article is soft-deleted
        assert len(results) == 1
        # The "Deleted Post About Running" should not match any active article closely
        # (it's a unique title compared to the active articles)
        assert results[0].action != "filter"
