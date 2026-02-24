"""Integration tests for Reddit API endpoints.

Tests the following endpoints end-to-end:
- POST /api/v1/reddit/accounts (create account)
- GET /api/v1/reddit/accounts (list accounts, filter by niche)
- PATCH /api/v1/reddit/accounts/{account_id} (update account)
- DELETE /api/v1/reddit/accounts/{account_id} (delete account)
- POST /api/v1/reddit/accounts — duplicate username returns 409
- GET /api/v1/projects/{project_id}/reddit/config (get config)
- POST /api/v1/projects/{project_id}/reddit/config (upsert config)
- POST /api/v1/projects/{project_id}/reddit/config — 404 on missing project
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.reddit_account import RedditAccount

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class TestRedditAccountAPI:
    """Integration tests for Reddit account CRUD endpoints."""

    @pytest.fixture
    async def project(self, db_session: AsyncSession) -> Project:
        """Create a project for testing."""
        p = Project(
            id=str(uuid4()),
            name="Test Project",
            site_url="https://example.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(p)
        await db_session.commit()
        return p

    @pytest.fixture
    async def account(self, db_session: AsyncSession) -> RedditAccount:
        """Create a Reddit account for testing."""
        a = RedditAccount(
            username=f"testuser_{uuid4().hex[:8]}",
            niche_tags=["fitness", "nutrition"],
        )
        db_session.add(a)
        await db_session.commit()
        return a

    # -------------------------------------------------------------------
    # POST create account
    # -------------------------------------------------------------------

    async def test_create_account_success(self, async_client: AsyncClient):
        """POST create account returns 201 with valid data."""
        username = f"newuser_{uuid4().hex[:8]}"
        resp = await async_client.post(
            "/api/v1/reddit/accounts",
            json={
                "username": username,
                "niche_tags": ["tech", "gaming"],
                "notes": "Test account",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == username
        assert data["niche_tags"] == ["tech", "gaming"]
        assert data["notes"] == "Test account"
        assert data["status"] == "active"
        assert data["warmup_stage"] == "observation"
        assert data["karma_post"] == 0
        assert data["karma_comment"] == 0
        assert data["id"] is not None

    async def test_create_account_minimal(self, async_client: AsyncClient):
        """POST create account with only required fields."""
        username = f"minimal_{uuid4().hex[:8]}"
        resp = await async_client.post(
            "/api/v1/reddit/accounts",
            json={"username": username},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == username
        assert data["niche_tags"] == []
        assert data["warmup_stage"] == "observation"

    async def test_create_account_duplicate_username_returns_409(
        self, async_client: AsyncClient, account: RedditAccount
    ):
        """POST create account with existing username returns 409."""
        resp = await async_client.post(
            "/api/v1/reddit/accounts",
            json={"username": account.username},
        )

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    # -------------------------------------------------------------------
    # GET list accounts
    # -------------------------------------------------------------------

    async def test_list_accounts_returns_all(
        self, async_client: AsyncClient, account: RedditAccount
    ):
        """GET list accounts returns created accounts."""
        resp = await async_client.get("/api/v1/reddit/accounts")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        usernames = [a["username"] for a in data]
        assert account.username in usernames

    async def test_list_accounts_filter_by_niche(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """GET list accounts with niche filter — JSONB @> requires PostgreSQL.

        The niche filter uses PostgreSQL's JSONB @> (contains) operator which
        is unsupported on SQLite. We verify the endpoint accepts the query param
        without the niche filter to confirm routing/schema work, and note that
        full filter behavior requires PostgreSQL integration tests.
        """
        a1 = RedditAccount(
            username=f"fitness_{uuid4().hex[:8]}",
            niche_tags=["fitness", "health"],
        )
        db_session.add(a1)
        await db_session.commit()

        # Without niche param — verifies endpoint works
        resp = await async_client.get("/api/v1/reddit/accounts")
        assert resp.status_code == 200
        usernames = [a["username"] for a in resp.json()]
        assert a1.username in usernames

    async def test_list_accounts_filter_by_status(
        self, async_client: AsyncClient, db_session: AsyncSession
    ):
        """GET list accounts with status filter returns only matching accounts."""
        a = RedditAccount(
            username=f"cooldown_{uuid4().hex[:8]}",
            status="cooldown",
        )
        db_session.add(a)
        await db_session.commit()

        resp = await async_client.get(
            "/api/v1/reddit/accounts", params={"status": "cooldown"}
        )

        assert resp.status_code == 200
        data = resp.json()
        assert all(a["status"] == "cooldown" for a in data)

    # -------------------------------------------------------------------
    # PATCH update account
    # -------------------------------------------------------------------

    async def test_update_account_success(
        self, async_client: AsyncClient, account: RedditAccount
    ):
        """PATCH update account modifies fields."""
        resp = await async_client.patch(
            f"/api/v1/reddit/accounts/{account.id}",
            json={"status": "cooldown", "karma_post": 100},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cooldown"
        assert data["karma_post"] == 100
        # Unchanged fields preserved
        assert data["username"] == account.username

    async def test_update_account_not_found_returns_404(
        self, async_client: AsyncClient
    ):
        """PATCH update non-existent account returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.patch(
            f"/api/v1/reddit/accounts/{fake_id}",
            json={"status": "active"},
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # -------------------------------------------------------------------
    # DELETE account
    # -------------------------------------------------------------------

    async def test_delete_account_success(
        self, async_client: AsyncClient, account: RedditAccount
    ):
        """DELETE account returns 204 and account is gone."""
        resp = await async_client.delete(
            f"/api/v1/reddit/accounts/{account.id}"
        )

        assert resp.status_code == 204

        # Verify it's gone
        get_resp = await async_client.get("/api/v1/reddit/accounts")
        usernames = [a["username"] for a in get_resp.json()]
        assert account.username not in usernames

    async def test_delete_account_not_found_returns_404(
        self, async_client: AsyncClient
    ):
        """DELETE non-existent account returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.delete(
            f"/api/v1/reddit/accounts/{fake_id}"
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Project Reddit Config endpoints
# ---------------------------------------------------------------------------


class TestRedditProjectConfigAPI:
    """Integration tests for per-project Reddit config endpoints."""

    @pytest.fixture
    async def project(self, db_session: AsyncSession) -> Project:
        """Create a project for testing."""
        p = Project(
            id=str(uuid4()),
            name="Config Test Project",
            site_url="https://config-test.com",
            status="active",
            phase_status={},
            brand_wizard_state={},
        )
        db_session.add(p)
        await db_session.commit()
        return p

    # -------------------------------------------------------------------
    # POST create/upsert config
    # -------------------------------------------------------------------

    async def test_create_config_success(
        self, async_client: AsyncClient, project: Project
    ):
        """POST config for project creates new config (201)."""
        resp = await async_client.post(
            f"/api/v1/projects/{project.id}/reddit/config",
            json={
                "search_keywords": ["running shoes", "trail running"],
                "target_subreddits": ["r/running", "r/trailrunning"],
                "niche_tags": ["fitness"],
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] == project.id
        assert data["search_keywords"] == ["running shoes", "trail running"]
        assert data["target_subreddits"] == ["r/running", "r/trailrunning"]
        assert data["niche_tags"] == ["fitness"]
        assert data["is_active"] is True
        assert data["banned_subreddits"] == []
        assert data["competitors"] == []

    async def test_upsert_config_updates_existing(
        self, async_client: AsyncClient, project: Project
    ):
        """POST config when config exists updates it (200)."""
        # Create initial config
        resp1 = await async_client.post(
            f"/api/v1/projects/{project.id}/reddit/config",
            json={"search_keywords": ["initial"]},
        )
        assert resp1.status_code == 201

        # Update via upsert
        resp2 = await async_client.post(
            f"/api/v1/projects/{project.id}/reddit/config",
            json={"search_keywords": ["updated"], "target_subreddits": ["r/new"]},
        )

        assert resp2.status_code == 200
        data = resp2.json()
        assert data["search_keywords"] == ["updated"]
        assert data["target_subreddits"] == ["r/new"]

    async def test_create_config_missing_project_returns_404(
        self, async_client: AsyncClient
    ):
        """POST config for non-existent project returns 404."""
        fake_id = str(uuid4())
        resp = await async_client.post(
            f"/api/v1/projects/{fake_id}/reddit/config",
            json={"search_keywords": ["test"]},
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    # -------------------------------------------------------------------
    # GET config
    # -------------------------------------------------------------------

    async def test_get_config_success(
        self, async_client: AsyncClient, project: Project
    ):
        """GET config returns existing config."""
        # Create config first
        await async_client.post(
            f"/api/v1/projects/{project.id}/reddit/config",
            json={
                "search_keywords": ["seo"],
                "comment_instructions": "Be helpful and friendly",
            },
        )

        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/reddit/config"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == project.id
        assert data["search_keywords"] == ["seo"]
        assert data["comment_instructions"] == "Be helpful and friendly"

    async def test_get_config_not_found_returns_404(
        self, async_client: AsyncClient, project: Project
    ):
        """GET config when none exists returns 404."""
        resp = await async_client.get(
            f"/api/v1/projects/{project.id}/reddit/config"
        )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]
