"""Tests for Reddit post discovery: SerpAPI client, intent classification,
discovery pipeline, and API endpoints.

Covers:
- SerpAPI client: query construction, time range mapping, URL filtering,
  subreddit extraction, rate limiting
- Intent classification: each keyword category, promotional exclusion,
  marketing subreddit exclusion, multiple intents
- Discovery pipeline: deduplication, banned subreddit filtering,
  progress tracking, filter_status determination
- API endpoints: trigger (202/409/404/400), poll status, list with filters,
  PATCH status, bulk action
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.serpapi import (
    SerpAPIClient,
    SerpResult,
    TIME_RANGE_MAP,
)
from app.models.project import Project
from app.models.reddit_config import RedditProjectConfig
from app.models.reddit_post import PostFilterStatus, PostIntent, RedditPost
from app.services.reddit_discovery import (
    DiscoveryProgress,
    IntentResult,
    ScoringResult,
    _deduplicate_posts,
    _determine_filter_status,
    classify_intent,
    get_discovery_progress,
    is_discovery_active,
    is_excluded_post,
    MARKETING_SUBREDDITS,
    PROMOTIONAL_KEYWORDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_serp_result(
    url: str = "https://www.reddit.com/r/TestSub/comments/abc123/some_post/",
    title: str = "Test post title",
    snippet: str = "Some snippet text",
    subreddit: str = "TestSub",
) -> SerpResult:
    """Create a SerpResult with sensible defaults."""
    return SerpResult(
        url=url,
        title=title,
        snippet=snippet,
        subreddit=subreddit,
        discovered_at=datetime.now(UTC),
    )


def _make_project_and_config(
    db_session: AsyncSession,
    search_keywords: list[str] | None = None,
    banned_subreddits: list[str] | None = None,
    target_subreddits: list[str] | None = None,
) -> tuple[Project, RedditProjectConfig]:
    """Create a project and Reddit config for testing."""
    project_id = str(uuid4())
    project = Project(
        id=project_id,
        name="Discovery Test Project",
        site_url="https://example.com",
        status="active",
        phase_status={},
        brand_wizard_state={},
    )
    config = RedditProjectConfig(
        project_id=project_id,
        search_keywords=search_keywords or ["test keyword"],
        banned_subreddits=banned_subreddits or [],
        target_subreddits=target_subreddits or [],
    )
    return project, config


# ===========================================================================
# SerpAPI Client Tests
# ===========================================================================


class TestSerpAPIQueryConstruction:
    """Test query building for SerpAPI search."""

    def test_keyword_only_query(self):
        """Query with keyword only should use site:reddit.com."""
        client = SerpAPIClient.__new__(SerpAPIClient)
        query = client._build_query("cbd for dogs")
        assert query == 'site:reddit.com "cbd for dogs"'

    def test_keyword_with_subreddit_query(self):
        """Query with subreddit should scope to that subreddit."""
        client = SerpAPIClient.__new__(SerpAPIClient)
        query = client._build_query("cbd for dogs", subreddit="dogs")
        assert query == 'site:reddit.com/r/dogs "cbd for dogs"'


class TestSerpAPITimeRangeMapping:
    """Test time range parameter mapping."""

    def test_24h_maps_to_qdr_d(self):
        assert TIME_RANGE_MAP["24h"] == "qdr:d"

    def test_7d_maps_to_qdr_w(self):
        assert TIME_RANGE_MAP["7d"] == "qdr:w"

    def test_30d_maps_to_qdr_m(self):
        assert TIME_RANGE_MAP["30d"] == "qdr:m"

    def test_all_time_ranges_present(self):
        assert set(TIME_RANGE_MAP.keys()) == {"24h", "7d", "30d"}


class TestSerpAPIURLFiltering:
    """Test URL filtering (only /comments/ URLs are Reddit posts)."""

    def test_post_url_accepted(self):
        """URL with /comments/ is a valid Reddit post."""
        assert SerpAPIClient._is_reddit_post(
            "https://www.reddit.com/r/dogs/comments/abc123/my_post/"
        )

    def test_subreddit_url_rejected(self):
        """Subreddit listing URL is NOT a post."""
        assert not SerpAPIClient._is_reddit_post(
            "https://www.reddit.com/r/dogs/"
        )

    def test_non_reddit_url_rejected(self):
        """Non-reddit URL is rejected."""
        assert not SerpAPIClient._is_reddit_post(
            "https://www.example.com/comments/abc123/"
        )

    def test_user_profile_url_rejected(self):
        """User profile URL without /comments/ is rejected."""
        assert not SerpAPIClient._is_reddit_post(
            "https://www.reddit.com/user/someuser/"
        )


class TestSerpAPISubredditExtraction:
    """Test subreddit name extraction from URLs."""

    def test_standard_post_url(self):
        """Extract subreddit from a standard Reddit post URL."""
        assert SerpAPIClient._extract_subreddit(
            "https://www.reddit.com/r/SkincareAddiction/comments/abc123/post_title/"
        ) == "SkincareAddiction"

    def test_short_subreddit(self):
        """Extract a short subreddit name."""
        assert SerpAPIClient._extract_subreddit(
            "https://www.reddit.com/r/dogs/comments/xyz/"
        ) == "dogs"

    def test_no_subreddit_returns_unknown(self):
        """URL without /r/ pattern returns 'unknown'."""
        assert SerpAPIClient._extract_subreddit(
            "https://www.reddit.com/comments/abc123/"
        ) == "unknown"

    def test_old_reddit_url(self):
        """Extract subreddit from old.reddit.com URL."""
        assert SerpAPIClient._extract_subreddit(
            "https://old.reddit.com/r/webdev/comments/abc/"
        ) == "webdev"


class TestSerpAPIRateLimiting:
    """Test rate limiting between consecutive requests."""

    @patch("app.integrations.serpapi.get_settings")
    async def test_rate_limit_enforces_delay(self, mock_settings):
        """Rate limiting should enforce minimum delay between requests."""
        mock_settings.return_value = MagicMock(serpapi_key="test-key")
        client = SerpAPIClient(api_key="test-key", rate_limit_delay=0.1)

        # Record time before first rate limit
        import time
        client._last_request_time = time.monotonic()

        # The rate limiter should wait before allowing next request
        start = time.monotonic()
        await client._rate_limit()
        elapsed = time.monotonic() - start

        # Should have waited approximately 0.1 seconds
        assert elapsed >= 0.05  # allow some tolerance
        await client.close()


# ===========================================================================
# Intent Classification Tests
# ===========================================================================


class TestIntentClassification:
    """Test keyword-based intent classification."""

    def test_research_intent(self):
        """Post with research keywords gets research intent."""
        post = _make_serp_result(
            title="Can anyone recommend a good moisturizer?",
            snippet="Looking for suggestions for dry skin products",
        )
        result = classify_intent(post)
        assert "research" in result.intents

    def test_pain_point_intent(self):
        """Post with pain point keywords gets pain_point intent."""
        post = _make_serp_result(
            title="Struggling with acne for years",
            snippet="I'm so frustrated, nothing seems to work",
        )
        result = classify_intent(post)
        assert "pain_point" in result.intents

    def test_question_intent(self):
        """Post with question patterns gets question intent."""
        post = _make_serp_result(
            title="How do I pick the right sunscreen?",
            snippet="Should I go with SPF 30 or 50?",
        )
        result = classify_intent(post)
        assert "question" in result.intents

    def test_competitor_intent(self):
        """Post mentioning a competitor gets competitor intent."""
        post = _make_serp_result(
            title="Thoughts on CeraVe moisturizer",
            snippet="Is CeraVe worth the hype?",
        )
        result = classify_intent(post, competitors=["CeraVe"])
        assert "competitor" in result.intents

    def test_general_intent_when_no_match(self):
        """Post with no keyword matches gets general intent."""
        post = _make_serp_result(
            title="Nice sunset photo today",
            snippet="Took this from my balcony",
        )
        result = classify_intent(post)
        assert result.intents == ["general"]

    def test_multiple_intents(self):
        """Post matching multiple categories gets all matching intents."""
        post = _make_serp_result(
            title="Best alternative to CeraVe? I'm struggling with acne",
            snippet="Looking for recommendations, my skin is getting worse",
        )
        result = classify_intent(post, competitors=["CeraVe"])
        assert "research" in result.intents
        assert "pain_point" in result.intents
        assert "competitor" in result.intents
        assert len(result.intents) >= 3

    def test_promotional_detection(self):
        """Post with promotional keywords is flagged as promotional."""
        post = _make_serp_result(
            title="Check out my new skincare brand!",
            snippet="We're launching my store with a discount code SAVE20",
        )
        result = classify_intent(post)
        assert result.is_promotional is True

    def test_non_promotional_post(self):
        """Normal post is not flagged as promotional."""
        post = _make_serp_result(
            title="Best moisturizer for winter?",
            snippet="Need help finding something affordable",
        )
        result = classify_intent(post)
        assert result.is_promotional is False


class TestExcludedPostFiltering:
    """Test post exclusion logic (banned subs, marketing subs, promotional)."""

    def test_banned_subreddit_excluded(self):
        """Post from a banned subreddit is excluded."""
        post = _make_serp_result(subreddit="SpamSub")
        assert is_excluded_post(post, banned_subreddits=["SpamSub"]) is True

    def test_banned_subreddit_case_insensitive(self):
        """Banned subreddit check is case-insensitive."""
        post = _make_serp_result(subreddit="spamsub")
        assert is_excluded_post(post, banned_subreddits=["SpamSub"]) is True

    def test_marketing_subreddit_excluded(self):
        """Post from a known marketing subreddit is excluded."""
        for sub in MARKETING_SUBREDDITS:
            post = _make_serp_result(subreddit=sub)
            assert is_excluded_post(post) is True, f"Should exclude r/{sub}"

    def test_promotional_content_excluded(self):
        """Post with promotional content is excluded."""
        post = _make_serp_result(
            title="Check out my new product launch!",
            snippet="Use discount code SAVE20 on my website",
        )
        assert is_excluded_post(post) is True

    def test_normal_post_not_excluded(self):
        """Normal post from a regular subreddit is not excluded."""
        post = _make_serp_result(
            subreddit="SkincareAddiction",
            title="Best sunscreen for daily use?",
            snippet="Looking for recommendations",
        )
        assert is_excluded_post(post) is False


# ===========================================================================
# Discovery Pipeline Helper Tests
# ===========================================================================


class TestDeduplication:
    """Test URL-based post deduplication."""

    def test_removes_exact_duplicates(self):
        """Identical URLs are deduplicated (first occurrence wins)."""
        posts = [
            _make_serp_result(url="https://reddit.com/r/a/comments/1/", title="First"),
            _make_serp_result(url="https://reddit.com/r/a/comments/1/", title="Second"),
        ]
        unique = _deduplicate_posts(posts)
        assert len(unique) == 1
        assert unique[0].title == "First"

    def test_trailing_slash_normalized(self):
        """URLs with and without trailing slash are treated as duplicates."""
        posts = [
            _make_serp_result(url="https://reddit.com/r/a/comments/1/"),
            _make_serp_result(url="https://reddit.com/r/a/comments/1"),
        ]
        unique = _deduplicate_posts(posts)
        assert len(unique) == 1

    def test_different_urls_preserved(self):
        """Different URLs are all preserved."""
        posts = [
            _make_serp_result(url="https://reddit.com/r/a/comments/1/"),
            _make_serp_result(url="https://reddit.com/r/a/comments/2/"),
            _make_serp_result(url="https://reddit.com/r/b/comments/3/"),
        ]
        unique = _deduplicate_posts(posts)
        assert len(unique) == 3


class TestFilterStatusDetermination:
    """Test score-to-filter-status mapping."""

    def test_low_score_discard(self):
        """Score < 5 returns None (discard)."""
        assert _determine_filter_status(0) is None
        assert _determine_filter_status(4.9) is None

    def test_mid_score_low_relevance(self):
        """Score 5-7 maps to 'low_relevance'."""
        assert _determine_filter_status(5) == "low_relevance"
        assert _determine_filter_status(6) == "low_relevance"
        assert _determine_filter_status(7) == "low_relevance"

    def test_high_score_relevant(self):
        """Score >= 8 maps to 'relevant'."""
        assert _determine_filter_status(8) == "relevant"
        assert _determine_filter_status(10) == "relevant"


class TestDiscoveryProgress:
    """Test in-memory progress tracking."""

    def test_is_discovery_active_searching(self):
        """Discovery is active during 'searching' status."""
        from app.services.reddit_discovery import _set_progress, _clear_progress

        project_id = f"test-{uuid4().hex[:8]}"
        progress = DiscoveryProgress(status="searching")
        _set_progress(project_id, progress)
        assert is_discovery_active(project_id) is True
        _clear_progress(project_id)

    def test_is_discovery_active_scoring(self):
        """Discovery is active during 'scoring' status."""
        from app.services.reddit_discovery import _set_progress, _clear_progress

        project_id = f"test-{uuid4().hex[:8]}"
        progress = DiscoveryProgress(status="scoring")
        _set_progress(project_id, progress)
        assert is_discovery_active(project_id) is True
        _clear_progress(project_id)

    def test_is_discovery_not_active_when_complete(self):
        """Discovery is NOT active when status is 'complete'."""
        from app.services.reddit_discovery import _set_progress, _clear_progress

        project_id = f"test-{uuid4().hex[:8]}"
        progress = DiscoveryProgress(status="complete")
        _set_progress(project_id, progress)
        assert is_discovery_active(project_id) is False
        _clear_progress(project_id)

    def test_is_discovery_not_active_when_no_entry(self):
        """Discovery is NOT active when no entry exists."""
        assert is_discovery_active(f"nonexistent-{uuid4().hex[:8]}") is False

    def test_get_progress_returns_none_when_no_entry(self):
        """get_discovery_progress returns None when no entry exists."""
        assert get_discovery_progress(f"nonexistent-{uuid4().hex[:8]}") is None

    def test_progress_fields_update(self):
        """Progress fields can be updated during discovery."""
        from app.services.reddit_discovery import _set_progress, _clear_progress

        project_id = f"test-{uuid4().hex[:8]}"
        progress = DiscoveryProgress(
            status="searching",
            total_keywords=3,
            keywords_searched=1,
        )
        _set_progress(project_id, progress)
        retrieved = get_discovery_progress(project_id)
        assert retrieved is not None
        assert retrieved.total_keywords == 3
        assert retrieved.keywords_searched == 1
        _clear_progress(project_id)


# ===========================================================================
# API Endpoint Integration Tests
# ===========================================================================


class TestDiscoveryTriggerAPI:
    """Integration tests for POST /projects/{id}/reddit/discover."""

    @pytest.fixture
    async def project_with_config(
        self, db_session: AsyncSession
    ) -> tuple[Project, RedditProjectConfig]:
        """Create a project with Reddit config for discovery tests."""
        project_id = str(uuid4())
        project = Project(
            id=project_id,
            name="Discovery API Test",
            site_url="https://test.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(project)
        await db_session.flush()

        config = RedditProjectConfig(
            project_id=project_id,
            search_keywords=["test keyword", "another keyword"],
            target_subreddits=[],
            banned_subreddits=[],
        )
        db_session.add(config)
        await db_session.commit()
        return project, config

    @pytest.fixture
    async def project_no_keywords(
        self, db_session: AsyncSession
    ) -> tuple[Project, RedditProjectConfig]:
        """Create a project with config but no search keywords."""
        project_id = str(uuid4())
        project = Project(
            id=project_id,
            name="No Keywords Project",
            site_url="https://test.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(project)
        await db_session.flush()

        config = RedditProjectConfig(
            project_id=project_id,
            search_keywords=[],
        )
        db_session.add(config)
        await db_session.commit()
        return project, config

    async def test_trigger_returns_202(
        self,
        async_client: AsyncClient,
        project_with_config: tuple[Project, RedditProjectConfig],
    ):
        """POST discover returns 202 Accepted when valid."""
        project, _ = project_with_config
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/reddit/discover"
        )
        assert resp.status_code == 202
        assert "started" in resp.json()["message"].lower()

    async def test_trigger_no_config_returns_404(
        self, async_client: AsyncClient
    ):
        """POST discover for project with no config returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.post(
            f"/api/v1/projects/{fake_id}/reddit/discover"
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_trigger_no_keywords_returns_400(
        self,
        async_client: AsyncClient,
        project_no_keywords: tuple[Project, RedditProjectConfig],
    ):
        """POST discover with empty keywords returns 400."""
        project, _ = project_no_keywords
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/reddit/discover"
        )
        assert resp.status_code == 400
        assert "keywords" in resp.json()["detail"].lower()

    async def test_trigger_duplicate_returns_409(
        self,
        async_client: AsyncClient,
        project_with_config: tuple[Project, RedditProjectConfig],
    ):
        """POST discover while already running returns 409."""
        from app.services.reddit_discovery import _set_progress, _clear_progress

        project, _ = project_with_config

        # Simulate an active discovery
        _set_progress(
            project.id,
            DiscoveryProgress(status="searching"),
        )

        try:
            resp = await async_client.post(
                f"/api/v1/projects/{project.id}/reddit/discover"
            )
            assert resp.status_code == 409
            assert "already in progress" in resp.json()["detail"].lower()
        finally:
            _clear_progress(project.id)


class TestDiscoveryStatusAPI:
    """Integration tests for GET /projects/{id}/reddit/discover/status."""

    async def test_poll_idle_when_no_discovery(
        self, async_client: AsyncClient
    ):
        """GET status with no active discovery returns 'idle'."""
        fake_id = str(uuid4())
        resp = await async_client.get(
            f"/api/v1/projects/{fake_id}/reddit/discover/status"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "idle"

    async def test_poll_returns_progress(
        self, async_client: AsyncClient
    ):
        """GET status during active discovery returns progress data."""
        from app.services.reddit_discovery import _set_progress, _clear_progress

        project_id = str(uuid4())
        _set_progress(
            project_id,
            DiscoveryProgress(
                status="scoring",
                total_keywords=5,
                keywords_searched=5,
                total_posts_found=20,
                posts_scored=10,
            ),
        )

        try:
            resp = await async_client.get(
                f"/api/v1/projects/{project_id}/reddit/discover/status"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "scoring"
            assert data["total_keywords"] == 5
            assert data["keywords_searched"] == 5
            assert data["total_posts_found"] == 20
            assert data["posts_scored"] == 10
        finally:
            _clear_progress(project_id)


class TestListPostsAPI:
    """Integration tests for GET /projects/{id}/reddit/posts."""

    @pytest.fixture
    async def project_with_posts(
        self, db_session: AsyncSession
    ) -> tuple[str, list[RedditPost]]:
        """Create a project with some discovered posts."""
        project_id = str(uuid4())
        project = Project(
            id=project_id,
            name="Posts Test Project",
            site_url="https://test.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(project)
        await db_session.flush()

        now = datetime.now(UTC)
        posts = [
            RedditPost(
                project_id=project_id,
                subreddit="SkincareAddiction",
                title="Best moisturizer for dry skin?",
                url=f"https://reddit.com/r/SkincareAddiction/comments/{uuid4().hex[:6]}/",
                snippet="Looking for recommendations",
                intent="research",
                intent_categories=["research", "question"],
                relevance_score=0.8,
                filter_status="relevant",
                discovered_at=now,
            ),
            RedditPost(
                project_id=project_id,
                subreddit="beauty",
                title="My skin is terrible",
                url=f"https://reddit.com/r/beauty/comments/{uuid4().hex[:6]}/",
                snippet="Struggling with acne",
                intent="pain_point",
                intent_categories=["pain_point"],
                relevance_score=0.6,
                filter_status="pending",
                discovered_at=now,
            ),
            RedditPost(
                project_id=project_id,
                subreddit="SkincareAddiction",
                title="CeraVe vs Cetaphil",
                url=f"https://reddit.com/r/SkincareAddiction/comments/{uuid4().hex[:6]}/",
                snippet="Comparing brands",
                intent="competitor",
                intent_categories=["competitor", "research"],
                relevance_score=0.3,
                filter_status="low_relevance",
                discovered_at=now,
            ),
        ]
        db_session.add_all(posts)
        await db_session.commit()
        return project_id, posts

    async def test_list_all_posts(
        self,
        async_client: AsyncClient,
        project_with_posts: tuple[str, list[RedditPost]],
    ):
        """GET posts returns all posts for the project."""
        project_id, posts = project_with_posts
        resp = await async_client.get(
            f"/api/v1/projects/{project_id}/reddit/posts"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    async def test_list_posts_ordered_by_score_desc(
        self,
        async_client: AsyncClient,
        project_with_posts: tuple[str, list[RedditPost]],
    ):
        """Posts are ordered by relevance_score descending."""
        project_id, _ = project_with_posts
        resp = await async_client.get(
            f"/api/v1/projects/{project_id}/reddit/posts"
        )
        data = resp.json()
        scores = [p["relevance_score"] for p in data]
        assert scores == sorted(scores, reverse=True)

    async def test_filter_by_status(
        self,
        async_client: AsyncClient,
        project_with_posts: tuple[str, list[RedditPost]],
    ):
        """Filter posts by filter_status returns only matching posts."""
        project_id, _ = project_with_posts
        resp = await async_client.get(
            f"/api/v1/projects/{project_id}/reddit/posts",
            params={"filter_status": "relevant"},
        )
        data = resp.json()
        assert len(data) == 1
        assert all(p["filter_status"] == "relevant" for p in data)

    async def test_filter_by_subreddit(
        self,
        async_client: AsyncClient,
        project_with_posts: tuple[str, list[RedditPost]],
    ):
        """Filter posts by subreddit returns only matching posts."""
        project_id, _ = project_with_posts
        resp = await async_client.get(
            f"/api/v1/projects/{project_id}/reddit/posts",
            params={"subreddit": "SkincareAddiction"},
        )
        data = resp.json()
        assert len(data) == 2
        assert all(p["subreddit"] == "SkincareAddiction" for p in data)

    async def test_empty_project_returns_empty_list(
        self, async_client: AsyncClient
    ):
        """GET posts for a project with no posts returns empty list."""
        fake_id = str(uuid4())
        resp = await async_client.get(
            f"/api/v1/projects/{fake_id}/reddit/posts"
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestUpdatePostAPI:
    """Integration tests for PATCH /projects/{id}/reddit/posts/{post_id}."""

    @pytest.fixture
    async def project_and_post(
        self, db_session: AsyncSession
    ) -> tuple[str, RedditPost]:
        """Create a project with one post."""
        project_id = str(uuid4())
        project = Project(
            id=project_id,
            name="Patch Test Project",
            site_url="https://test.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(project)
        await db_session.flush()

        post = RedditPost(
            project_id=project_id,
            subreddit="test",
            title="Test post",
            url=f"https://reddit.com/r/test/comments/{uuid4().hex[:6]}/",
            filter_status="pending",
            discovered_at=datetime.now(UTC),
        )
        db_session.add(post)
        await db_session.commit()
        return project_id, post

    async def test_approve_post(
        self,
        async_client: AsyncClient,
        project_and_post: tuple[str, RedditPost],
    ):
        """PATCH post with filter_status 'relevant' approves it."""
        project_id, post = project_and_post
        resp = await async_client.patch(
            f"/api/v1/projects/{project_id}/reddit/posts/{post.id}",
            json={"filter_status": "relevant"},
        )
        assert resp.status_code == 200
        assert resp.json()["filter_status"] == "relevant"

    async def test_reject_post(
        self,
        async_client: AsyncClient,
        project_and_post: tuple[str, RedditPost],
    ):
        """PATCH post with filter_status 'skipped' skips it."""
        project_id, post = project_and_post
        resp = await async_client.patch(
            f"/api/v1/projects/{project_id}/reddit/posts/{post.id}",
            json={"filter_status": "skipped"},
        )
        assert resp.status_code == 200
        assert resp.json()["filter_status"] == "skipped"

    async def test_update_nonexistent_post_returns_404(
        self, async_client: AsyncClient
    ):
        """PATCH non-existent post returns 404."""
        fake_project = str(uuid4())
        fake_post = str(uuid4())
        resp = await async_client.patch(
            f"/api/v1/projects/{fake_project}/reddit/posts/{fake_post}",
            json={"filter_status": "relevant"},
        )
        assert resp.status_code == 404


class TestBulkPostActionAPI:
    """Integration tests for POST /projects/{id}/reddit/posts/bulk-action."""

    @pytest.fixture
    async def project_and_posts(
        self, db_session: AsyncSession
    ) -> tuple[str, list[RedditPost]]:
        """Create a project with multiple posts for bulk testing."""
        project_id = str(uuid4())
        project = Project(
            id=project_id,
            name="Bulk Test Project",
            site_url="https://test.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(project)
        await db_session.flush()

        now = datetime.now(UTC)
        posts = []
        for i in range(3):
            post = RedditPost(
                project_id=project_id,
                subreddit="test",
                title=f"Post {i}",
                url=f"https://reddit.com/r/test/comments/{uuid4().hex[:6]}/",
                filter_status="pending",
                discovered_at=now,
            )
            posts.append(post)
        db_session.add_all(posts)
        await db_session.commit()
        return project_id, posts

    async def test_bulk_approve(
        self,
        async_client: AsyncClient,
        project_and_posts: tuple[str, list[RedditPost]],
    ):
        """Bulk approve updates all specified posts."""
        project_id, posts = project_and_posts
        post_ids = [p.id for p in posts[:2]]

        resp = await async_client.post(
            f"/api/v1/projects/{project_id}/reddit/posts/bulk-action",
            json={
                "post_ids": post_ids,
                "filter_status": "relevant",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 2

    async def test_bulk_reject(
        self,
        async_client: AsyncClient,
        project_and_posts: tuple[str, list[RedditPost]],
    ):
        """Bulk skip updates all specified posts."""
        project_id, posts = project_and_posts
        post_ids = [p.id for p in posts]

        resp = await async_client.post(
            f"/api/v1/projects/{project_id}/reddit/posts/bulk-action",
            json={
                "post_ids": post_ids,
                "filter_status": "skipped",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 3

    async def test_bulk_empty_ids_returns_zero(
        self,
        async_client: AsyncClient,
        project_and_posts: tuple[str, list[RedditPost]],
    ):
        """Bulk action with empty post_ids returns 0 updated."""
        project_id, _ = project_and_posts
        resp = await async_client.post(
            f"/api/v1/projects/{project_id}/reddit/posts/bulk-action",
            json={
                "post_ids": [],
                "filter_status": "relevant",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0


# ===========================================================================
# Model Enum Tests
# ===========================================================================


class TestPostFilterStatusEnum:
    """Verify PostFilterStatus enum has all expected values."""

    def test_values(self):
        assert PostFilterStatus.PENDING.value == "pending"
        assert PostFilterStatus.RELEVANT.value == "relevant"
        assert PostFilterStatus.LOW_RELEVANCE.value == "low_relevance"
        assert PostFilterStatus.SKIPPED.value == "skipped"

    def test_member_count(self):
        assert len(PostFilterStatus) == 4


class TestPostIntentEnum:
    """Verify PostIntent enum has all expected values."""

    def test_values(self):
        assert PostIntent.RESEARCH.value == "research"
        assert PostIntent.PAIN_POINT.value == "pain_point"
        assert PostIntent.COMPETITOR.value == "competitor"
        assert PostIntent.QUESTION.value == "question"
        assert PostIntent.GENERAL.value == "general"

    def test_member_count(self):
        assert len(PostIntent) == 5


# ===========================================================================
# RedditPost Model Default Tests
# ===========================================================================


class TestRedditPostDefaults:
    """Verify Python-side defaults on RedditPost model."""

    async def test_filter_status_defaults_to_pending(
        self, db_session: AsyncSession
    ):
        """New post defaults to 'pending' filter status."""
        project = Project(
            id=str(uuid4()),
            name="Defaults Test",
            site_url="https://test.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(project)
        await db_session.flush()

        post = RedditPost(
            project_id=project.id,
            subreddit="test",
            title="Test post",
            url="https://reddit.com/r/test/comments/abc123/",
            discovered_at=datetime.now(UTC),
        )
        db_session.add(post)
        await db_session.flush()

        assert post.filter_status == "pending"

    async def test_id_auto_generated(
        self, db_session: AsyncSession
    ):
        """RedditPost id is auto-generated UUID."""
        project = Project(
            id=str(uuid4()),
            name="ID Test",
            site_url="https://test.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(project)
        await db_session.flush()

        post = RedditPost(
            project_id=project.id,
            subreddit="test",
            title="Test",
            url="https://reddit.com/r/test/comments/xyz/",
            discovered_at=datetime.now(UTC),
        )
        db_session.add(post)
        await db_session.flush()

        assert post.id is not None
        assert len(post.id) == 36

    async def test_timestamps_set(
        self, db_session: AsyncSession
    ):
        """created_at and updated_at are set automatically."""
        project = Project(
            id=str(uuid4()),
            name="Timestamps Test",
            site_url="https://test.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(project)
        await db_session.flush()

        post = RedditPost(
            project_id=project.id,
            subreddit="test",
            title="Test",
            url="https://reddit.com/r/test/comments/ts/",
            discovered_at=datetime.now(UTC),
        )
        db_session.add(post)
        await db_session.flush()

        assert post.created_at is not None
        assert post.updated_at is not None
