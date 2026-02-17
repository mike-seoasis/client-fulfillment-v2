"""Reddit API routers.

REST endpoints for Reddit account CRUD, per-project Reddit configuration,
post discovery, and post management.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import cast

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.project import Project
from app.models.reddit_account import RedditAccount
from app.models.reddit_config import RedditProjectConfig
from app.models.reddit_post import RedditPost
from app.schemas.reddit import (
    BulkPostActionRequest,
    DiscoveryStatusResponse,
    DiscoveryTriggerRequest,
    DiscoveryTriggerResponse,
    PostUpdateRequest,
    RedditAccountCreate,
    RedditAccountResponse,
    RedditAccountUpdate,
    RedditPostResponse,
    RedditProjectConfigCreate,
    RedditProjectConfigResponse,
)
from app.services.reddit_discovery import (
    DiscoveryProgress,
    discover_posts,
    get_discovery_progress,
    is_discovery_active,
)

logger = get_logger(__name__)

reddit_router = APIRouter(prefix="/reddit", tags=["Reddit"])
reddit_project_router = APIRouter(prefix="/projects", tags=["Reddit"])


@reddit_router.get(
    "/accounts",
    response_model=list[RedditAccountResponse],
)
async def list_accounts(
    niche: str | None = Query(None, description="Filter by niche tag (JSONB contains)"),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by account status"
    ),
    warmup_stage: str | None = Query(None, description="Filter by warmup stage"),
    db: AsyncSession = Depends(get_session),
) -> list[RedditAccountResponse]:
    """List all Reddit accounts with optional filters."""
    stmt = select(RedditAccount).order_by(RedditAccount.created_at.desc())

    if niche is not None:
        stmt = stmt.where(
            RedditAccount.niche_tags.op("@>")(cast([niche], JSONB))
        )

    if status_filter is not None:
        stmt = stmt.where(RedditAccount.status == status_filter)

    if warmup_stage is not None:
        stmt = stmt.where(RedditAccount.warmup_stage == warmup_stage)

    result = await db.execute(stmt)
    accounts = result.scalars().all()

    return [RedditAccountResponse.model_validate(a) for a in accounts]


@reddit_router.post(
    "/accounts",
    response_model=RedditAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    data: RedditAccountCreate,
    db: AsyncSession = Depends(get_session),
) -> RedditAccountResponse:
    """Create a new Reddit account. Returns 409 if username already exists."""
    existing_stmt = select(RedditAccount).where(
        RedditAccount.username == data.username
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Reddit account with username '{data.username}' already exists",
        )

    account = RedditAccount(
        username=data.username,
        niche_tags=data.niche_tags,
        warmup_stage=data.warmup_stage,
        notes=data.notes,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    return RedditAccountResponse.model_validate(account)


@reddit_router.patch(
    "/accounts/{account_id}",
    response_model=RedditAccountResponse,
)
async def update_account(
    account_id: str,
    data: RedditAccountUpdate,
    db: AsyncSession = Depends(get_session),
) -> RedditAccountResponse:
    """Update a Reddit account. Returns 404 if not found."""
    stmt = select(RedditAccount).where(RedditAccount.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reddit account {account_id} not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)

    return RedditAccountResponse.model_validate(account)


@reddit_router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a Reddit account. Returns 404 if not found."""
    stmt = select(RedditAccount).where(RedditAccount.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reddit account {account_id} not found",
        )

    await db.delete(account)
    await db.commit()


# ---------------------------------------------------------------------------
# Project Reddit config endpoints (on reddit_project_router)
# ---------------------------------------------------------------------------


@reddit_project_router.get(
    "/{project_id}/reddit/config",
    response_model=RedditProjectConfigResponse,
)
async def get_project_reddit_config(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> RedditProjectConfigResponse:
    """Get Reddit config for a project. Returns 404 if none exists."""
    stmt = select(RedditProjectConfig).where(
        RedditProjectConfig.project_id == project_id
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reddit config for project {project_id} not found",
        )

    return RedditProjectConfigResponse.model_validate(config)


@reddit_project_router.post(
    "/{project_id}/reddit/config",
    response_model=RedditProjectConfigResponse,
    responses={
        200: {"description": "Config updated"},
        201: {"description": "Config created"},
        404: {"description": "Project not found"},
    },
)
async def upsert_project_reddit_config(
    project_id: str,
    data: RedditProjectConfigCreate,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> RedditProjectConfigResponse:
    """Create or update Reddit config for a project.

    Returns 201 if created, 200 if updated. Returns 404 if project doesn't exist.
    """
    # Verify project exists
    project_stmt = select(Project.id).where(Project.id == project_id)
    project_result = await db.execute(project_stmt)
    if project_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Check for existing config
    stmt = select(RedditProjectConfig).where(
        RedditProjectConfig.project_id == project_id
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        # Update existing config
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)
        await db.commit()
        await db.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return RedditProjectConfigResponse.model_validate(existing)

    # Create new config
    config = RedditProjectConfig(
        project_id=project_id,
        **data.model_dump(),
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    response.status_code = status.HTTP_201_CREATED
    return RedditProjectConfigResponse.model_validate(config)


# ---------------------------------------------------------------------------
# Discovery endpoints (Phase 14b)
# ---------------------------------------------------------------------------


async def _run_discovery_background(project_id: str, time_range: str) -> None:
    """Background task wrapper for discover_posts."""
    try:
        await discover_posts(project_id=project_id, time_range=time_range)
    except Exception as e:
        logger.error(
            "Background discovery failed",
            extra={
                "project_id": project_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )


@reddit_project_router.post(
    "/{project_id}/reddit/discover",
    response_model=DiscoveryTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"description": "No search keywords configured"},
        404: {"description": "Reddit config not found"},
        409: {"description": "Discovery already in progress"},
    },
)
async def trigger_discovery(
    project_id: str,
    background_tasks: BackgroundTasks,
    data: DiscoveryTriggerRequest | None = None,
    db: AsyncSession = Depends(get_session),
) -> DiscoveryTriggerResponse:
    """Trigger Reddit post discovery for a project.

    Starts the discovery pipeline as a background task and returns 202 immediately.
    Poll GET /discover/status for progress.
    """
    time_range = data.time_range if data else "7d"

    # Validate project has Reddit config
    config_stmt = select(RedditProjectConfig).where(
        RedditProjectConfig.project_id == project_id
    )
    config_result = await db.execute(config_stmt)
    config = config_result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reddit config not found for this project",
        )

    if not config.search_keywords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No search keywords configured",
        )

    # Check for duplicate runs
    if is_discovery_active(project_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Discovery already in progress",
        )

    # Start background task
    background_tasks.add_task(_run_discovery_background, project_id, time_range)

    return DiscoveryTriggerResponse(message="Discovery started")


@reddit_project_router.get(
    "/{project_id}/reddit/discover/status",
    response_model=DiscoveryStatusResponse,
)
async def get_discovery_status(
    project_id: str,
) -> DiscoveryStatusResponse:
    """Poll discovery progress for a project.

    Returns current progress if discovery is active, or "idle" if not.
    """
    progress = get_discovery_progress(project_id)

    if progress is None:
        return DiscoveryStatusResponse(status="idle")

    return DiscoveryStatusResponse(
        status=progress.status,
        total_keywords=progress.total_keywords,
        keywords_searched=progress.keywords_searched,
        total_posts_found=progress.total_posts_found,
        posts_scored=progress.posts_scored,
        posts_stored=progress.posts_stored,
        error=progress.error,
    )


# ---------------------------------------------------------------------------
# Post management endpoints (Phase 14b)
# ---------------------------------------------------------------------------


@reddit_project_router.get(
    "/{project_id}/reddit/posts",
    response_model=list[RedditPostResponse],
)
async def list_posts(
    project_id: str,
    filter_status: str | None = Query(None, description="Filter by status"),
    intent: str | None = Query(None, description="Filter by intent category"),
    subreddit: str | None = Query(None, description="Filter by subreddit"),
    db: AsyncSession = Depends(get_session),
) -> list[RedditPostResponse]:
    """List discovered Reddit posts for a project with optional filters.

    Results are ordered by relevance_score descending (most relevant first).
    """
    stmt = (
        select(RedditPost)
        .where(RedditPost.project_id == project_id)
        .order_by(RedditPost.relevance_score.desc().nulls_last())
    )

    if filter_status is not None:
        stmt = stmt.where(RedditPost.filter_status == filter_status)

    if intent is not None:
        # JSONB contains check: intent_categories @> '["research"]'
        stmt = stmt.where(
            RedditPost.intent_categories.op("@>")(cast([intent], JSONB))
        )

    if subreddit is not None:
        stmt = stmt.where(RedditPost.subreddit == subreddit)

    result = await db.execute(stmt)
    posts = result.scalars().all()

    return [RedditPostResponse.model_validate(p) for p in posts]


@reddit_project_router.patch(
    "/{project_id}/reddit/posts/{post_id}",
    response_model=RedditPostResponse,
)
async def update_post(
    project_id: str,
    post_id: str,
    data: PostUpdateRequest,
    db: AsyncSession = Depends(get_session),
) -> RedditPostResponse:
    """Update a Reddit post's filter status."""
    stmt = select(RedditPost).where(
        RedditPost.id == post_id,
        RedditPost.project_id == project_id,
    )
    result = await db.execute(stmt)
    post = result.scalar_one_or_none()

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reddit post {post_id} not found",
        )

    post.filter_status = data.filter_status
    await db.commit()
    await db.refresh(post)

    return RedditPostResponse.model_validate(post)


@reddit_project_router.post(
    "/{project_id}/reddit/posts/bulk-action",
    response_model=dict,
)
async def bulk_post_action(
    project_id: str,
    data: BulkPostActionRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Bulk update filter status for multiple posts."""
    if not data.post_ids:
        return {"updated": 0}

    stmt = (
        update(RedditPost)
        .where(
            RedditPost.id.in_(data.post_ids),
            RedditPost.project_id == project_id,
        )
        .values(filter_status=data.filter_status)
    )

    result = await db.execute(stmt)
    await db.commit()

    return {"updated": result.rowcount}
