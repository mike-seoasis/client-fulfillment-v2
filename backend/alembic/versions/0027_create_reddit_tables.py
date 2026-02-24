"""Create Reddit tables: reddit_accounts, reddit_project_configs, reddit_posts, reddit_comments, crowdreply_tasks.

Phase 14 - Reddit Data Foundation:
- reddit_accounts: Shared Reddit accounts (no project FK)
- reddit_project_configs: Per-project Reddit settings (1:1 with projects)
- reddit_posts: Discovered Reddit threads via SERP
- reddit_comments: AI-generated comments with approval workflow
- crowdreply_tasks: CrowdReply API submission tracking

Revision ID: 0027
Revises: 0026
Create Date: 2026-02-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: str | tuple[str, ...] | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all Reddit tables."""
    # --- 1. reddit_accounts (no FKs) ---
    op.create_table(
        "reddit_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "warmup_stage",
            sa.String(length=50),
            server_default=sa.text("'observation'"),
            nullable=False,
        ),
        sa.Column(
            "niche_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "karma_post",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "karma_comment",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("account_age_days", sa.Integer(), nullable=True),
        sa.Column(
            "cooldown_until", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_reddit_accounts_username"),
    )
    op.create_index(
        op.f("ix_reddit_accounts_username"),
        "reddit_accounts",
        ["username"],
        unique=True,
    )
    op.create_index(
        op.f("ix_reddit_accounts_status"),
        "reddit_accounts",
        ["status"],
        unique=False,
    )

    # --- 2. reddit_project_configs (FK → projects) ---
    op.create_table(
        "reddit_project_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "search_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "target_subreddits",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "banned_subreddits",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "competitors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("comment_instructions", sa.Text(), nullable=True),
        sa.Column(
            "niche_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "discovery_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_reddit_project_configs_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "project_id", name="uq_reddit_project_configs_project_id"
        ),
    )
    op.create_index(
        op.f("ix_reddit_project_configs_project_id"),
        "reddit_project_configs",
        ["project_id"],
        unique=True,
    )

    # --- 3. reddit_posts (FK → projects) ---
    op.create_table(
        "reddit_posts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("reddit_post_id", sa.String(length=50), nullable=True),
        sa.Column("subreddit", sa.String(length=100), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("keyword", sa.String(length=500), nullable=True),
        sa.Column("intent", sa.String(length=50), nullable=True),
        sa.Column(
            "intent_categories",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column(
            "matched_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "ai_evaluation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "filter_status",
            sa.String(length=50),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("serp_position", sa.Integer(), nullable=True),
        sa.Column(
            "discovered_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_reddit_posts_project_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "project_id", "url", name="uq_reddit_posts_project_url"
        ),
    )
    op.create_index(
        op.f("ix_reddit_posts_project_id"),
        "reddit_posts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reddit_posts_subreddit"),
        "reddit_posts",
        ["subreddit"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reddit_posts_filter_status"),
        "reddit_posts",
        ["filter_status"],
        unique=False,
    )

    # --- 4. reddit_comments (FK → reddit_posts, projects, reddit_accounts) ---
    op.create_table(
        "reddit_comments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "post_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("original_body", sa.Text(), nullable=False),
        sa.Column(
            "is_promotional",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("approach_type", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column(
            "crowdreply_task_id", sa.String(length=255), nullable=True
        ),
        sa.Column("posted_url", sa.String(length=2048), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "generation_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["reddit_posts.id"],
            name="fk_reddit_comments_post_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_reddit_comments_project_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["reddit_accounts.id"],
            name="fk_reddit_comments_account_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        op.f("ix_reddit_comments_post_id"),
        "reddit_comments",
        ["post_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reddit_comments_project_id"),
        "reddit_comments",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reddit_comments_account_id"),
        "reddit_comments",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reddit_comments_status"),
        "reddit_comments",
        ["status"],
        unique=False,
    )

    # --- 5. crowdreply_tasks (FK → reddit_comments) ---
    op.create_table(
        "crowdreply_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "comment_id",
            postgresql.UUID(as_uuid=False),
            nullable=True,
        ),
        sa.Column(
            "external_task_id", sa.String(length=255), nullable=True
        ),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "crowdreply_project_id", sa.String(length=255), nullable=True
        ),
        sa.Column(
            "request_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "response_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("upvotes_requested", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "published_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["comment_id"],
            ["reddit_comments.id"],
            name="fk_crowdreply_tasks_comment_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        op.f("ix_crowdreply_tasks_comment_id"),
        "crowdreply_tasks",
        ["comment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crowdreply_tasks_external_task_id"),
        "crowdreply_tasks",
        ["external_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_crowdreply_tasks_status"),
        "crowdreply_tasks",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop all Reddit tables in reverse dependency order."""
    # --- 5. crowdreply_tasks ---
    op.drop_index(
        op.f("ix_crowdreply_tasks_status"), table_name="crowdreply_tasks"
    )
    op.drop_index(
        op.f("ix_crowdreply_tasks_external_task_id"),
        table_name="crowdreply_tasks",
    )
    op.drop_index(
        op.f("ix_crowdreply_tasks_comment_id"),
        table_name="crowdreply_tasks",
    )
    op.drop_table("crowdreply_tasks")

    # --- 4. reddit_comments ---
    op.drop_index(
        op.f("ix_reddit_comments_status"), table_name="reddit_comments"
    )
    op.drop_index(
        op.f("ix_reddit_comments_account_id"), table_name="reddit_comments"
    )
    op.drop_index(
        op.f("ix_reddit_comments_project_id"), table_name="reddit_comments"
    )
    op.drop_index(
        op.f("ix_reddit_comments_post_id"), table_name="reddit_comments"
    )
    op.drop_table("reddit_comments")

    # --- 3. reddit_posts ---
    op.drop_index(
        op.f("ix_reddit_posts_filter_status"), table_name="reddit_posts"
    )
    op.drop_index(
        op.f("ix_reddit_posts_subreddit"), table_name="reddit_posts"
    )
    op.drop_index(
        op.f("ix_reddit_posts_project_id"), table_name="reddit_posts"
    )
    op.drop_table("reddit_posts")

    # --- 2. reddit_project_configs ---
    op.drop_index(
        op.f("ix_reddit_project_configs_project_id"),
        table_name="reddit_project_configs",
    )
    op.drop_table("reddit_project_configs")

    # --- 1. reddit_accounts ---
    op.drop_index(
        op.f("ix_reddit_accounts_status"), table_name="reddit_accounts"
    )
    op.drop_index(
        op.f("ix_reddit_accounts_username"), table_name="reddit_accounts"
    )
    op.drop_table("reddit_accounts")
