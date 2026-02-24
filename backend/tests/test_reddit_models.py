"""Tests for Reddit models: enum values, default field values, unique constraints."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.reddit_account import AccountStatus, RedditAccount, WarmupStage
from app.models.reddit_config import RedditProjectConfig

# ---------------------------------------------------------------------------
# Enum value tests
# ---------------------------------------------------------------------------


class TestWarmupStageEnum:
    """Verify WarmupStage enum has all expected values."""

    def test_values(self):
        assert WarmupStage.OBSERVATION.value == "observation"
        assert WarmupStage.LIGHT_ENGAGEMENT.value == "light_engagement"
        assert WarmupStage.REGULAR_ACTIVITY.value == "regular_activity"
        assert WarmupStage.OPERATIONAL.value == "operational"

    def test_member_count(self):
        assert len(WarmupStage) == 4


class TestAccountStatusEnum:
    """Verify AccountStatus enum has all expected values."""

    def test_values(self):
        assert AccountStatus.ACTIVE.value == "active"
        assert AccountStatus.WARMING_UP.value == "warming_up"
        assert AccountStatus.COOLDOWN.value == "cooldown"
        assert AccountStatus.SUSPENDED.value == "suspended"
        assert AccountStatus.BANNED.value == "banned"

    def test_member_count(self):
        assert len(AccountStatus) == 5


# ---------------------------------------------------------------------------
# RedditAccount default field tests
# ---------------------------------------------------------------------------


class TestRedditAccountDefaults:
    """Verify Python-side defaults on RedditAccount model."""

    async def test_status_defaults_to_active(self, db_session: AsyncSession):
        account = RedditAccount(username=f"user_{uuid4().hex[:8]}")
        db_session.add(account)
        await db_session.flush()

        assert account.status == AccountStatus.ACTIVE.value

    async def test_warmup_stage_defaults_to_observation(self, db_session: AsyncSession):
        account = RedditAccount(username=f"user_{uuid4().hex[:8]}")
        db_session.add(account)
        await db_session.flush()

        assert account.warmup_stage == WarmupStage.OBSERVATION.value

    async def test_niche_tags_defaults_to_empty_list(self, db_session: AsyncSession):
        account = RedditAccount(username=f"user_{uuid4().hex[:8]}")
        db_session.add(account)
        await db_session.flush()

        assert account.niche_tags == []

    async def test_karma_defaults_to_zero(self, db_session: AsyncSession):
        account = RedditAccount(username=f"user_{uuid4().hex[:8]}")
        db_session.add(account)
        await db_session.flush()

        assert account.karma_post == 0
        assert account.karma_comment == 0

    async def test_nullable_fields_default_to_none(self, db_session: AsyncSession):
        account = RedditAccount(username=f"user_{uuid4().hex[:8]}")
        db_session.add(account)
        await db_session.flush()

        assert account.account_age_days is None
        assert account.cooldown_until is None
        assert account.last_used_at is None
        assert account.notes is None
        assert account.extra_metadata is None

    async def test_timestamps_are_set(self, db_session: AsyncSession):
        account = RedditAccount(username=f"user_{uuid4().hex[:8]}")
        db_session.add(account)
        await db_session.flush()

        assert account.created_at is not None
        assert account.updated_at is not None

    async def test_id_auto_generated(self, db_session: AsyncSession):
        account = RedditAccount(username=f"user_{uuid4().hex[:8]}")
        db_session.add(account)
        await db_session.flush()

        assert account.id is not None
        assert len(account.id) == 36  # UUID string length


# ---------------------------------------------------------------------------
# RedditAccount unique constraint tests
# ---------------------------------------------------------------------------


class TestRedditAccountUniqueConstraint:
    """Verify unique constraint on reddit_accounts.username."""

    async def test_duplicate_username_raises(self, db_session: AsyncSession):
        username = f"unique_user_{uuid4().hex[:8]}"

        account1 = RedditAccount(username=username)
        db_session.add(account1)
        await db_session.flush()

        account2 = RedditAccount(username=username)
        db_session.add(account2)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_different_usernames_ok(self, db_session: AsyncSession):
        account1 = RedditAccount(username=f"user_a_{uuid4().hex[:8]}")
        account2 = RedditAccount(username=f"user_b_{uuid4().hex[:8]}")
        db_session.add_all([account1, account2])
        await db_session.flush()

        stmt = select(RedditAccount).where(
            RedditAccount.id.in_([account1.id, account2.id])
        )
        result = await db_session.execute(stmt)
        assert len(result.scalars().all()) == 2


# ---------------------------------------------------------------------------
# RedditProjectConfig default field tests
# ---------------------------------------------------------------------------


class TestRedditProjectConfigDefaults:
    """Verify Python-side defaults on RedditProjectConfig model."""

    @pytest.fixture
    async def project(self, db_session: AsyncSession) -> Project:
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

    async def test_jsonb_arrays_default_to_empty(
        self, db_session: AsyncSession, project: Project
    ):
        config = RedditProjectConfig(project_id=project.id)
        db_session.add(config)
        await db_session.flush()

        assert config.search_keywords == []
        assert config.target_subreddits == []
        assert config.banned_subreddits == []
        assert config.competitors == []
        assert config.niche_tags == []

    async def test_is_active_defaults_to_true(
        self, db_session: AsyncSession, project: Project
    ):
        config = RedditProjectConfig(project_id=project.id)
        db_session.add(config)
        await db_session.flush()

        assert config.is_active is True

    async def test_nullable_fields_default_to_none(
        self, db_session: AsyncSession, project: Project
    ):
        config = RedditProjectConfig(project_id=project.id)
        db_session.add(config)
        await db_session.flush()

        assert config.comment_instructions is None
        assert config.discovery_settings is None
