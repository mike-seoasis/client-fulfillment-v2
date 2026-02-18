"""Reddit API routers.

REST endpoints for Reddit account CRUD, per-project Reddit configuration,
post discovery, post management, and comment generation.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import cast

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.project import Project
from app.models.reddit_account import RedditAccount
from app.models.reddit_comment import RedditComment
from app.models.reddit_config import RedditProjectConfig
from app.models.reddit_post import RedditPost
from app.schemas.reddit import (
    BatchGenerateRequest,
    BulkCommentActionRequest,
    BulkCommentRejectRequest,
    BulkPostActionRequest,
    CommentApproveRequest,
    CommentQueueResponse,
    CommentQueueStatusCounts,
    CommentRejectRequest,
    DiscoveryStatusResponse,
    DiscoveryTriggerRequest,
    DiscoveryTriggerResponse,
    GenerateCommentRequest,
    GenerationStatusResponse,
    PostUpdateRequest,
    RedditCommentUpdateRequest,
    RedditAccountCreate,
    RedditAccountResponse,
    RedditAccountUpdate,
    RedditCommentResponse,
    RedditPostResponse,
    RedditProjectCardResponse,
    RedditProjectConfigCreate,
    RedditProjectConfigResponse,
    RedditProjectListResponse,
)
from app.services.reddit_comment_generation import (
    generate_batch,
    generate_comment,
    get_generation_progress,
    is_generation_active,
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
# Reddit projects dashboard (on reddit_router, no project scope)
# ---------------------------------------------------------------------------


@reddit_router.get(
    "/projects",
    response_model=RedditProjectListResponse,
)
async def list_reddit_projects(
    db: AsyncSession = Depends(get_session),
) -> RedditProjectListResponse:
    """List projects that have a RedditProjectConfig (for the Reddit dashboard).

    Returns project summary cards with post/comment counts, ordered by
    most recently updated config first.
    """
    # Get all projects with Reddit config via JOIN
    stmt = (
        select(
            Project.id,
            Project.name,
            Project.site_url,
            RedditProjectConfig.is_active,
            RedditProjectConfig.updated_at,
        )
        .join(RedditProjectConfig, RedditProjectConfig.project_id == Project.id)
        .order_by(RedditProjectConfig.updated_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return RedditProjectListResponse(items=[], total=0)

    project_ids = [r.id for r in rows]

    # Count posts per project
    post_counts_stmt = (
        select(RedditPost.project_id, func.count())
        .where(RedditPost.project_id.in_(project_ids))
        .group_by(RedditPost.project_id)
    )
    post_result = await db.execute(post_counts_stmt)
    post_counts = dict(post_result.all())

    # Count total comments per project
    comment_counts_stmt = (
        select(RedditComment.project_id, func.count())
        .where(RedditComment.project_id.in_(project_ids))
        .group_by(RedditComment.project_id)
    )
    comment_result = await db.execute(comment_counts_stmt)
    comment_counts = dict(comment_result.all())

    # Count draft comments per project
    draft_counts_stmt = (
        select(RedditComment.project_id, func.count())
        .where(
            RedditComment.project_id.in_(project_ids),
            RedditComment.status == "draft",
        )
        .group_by(RedditComment.project_id)
    )
    draft_result = await db.execute(draft_counts_stmt)
    draft_counts = dict(draft_result.all())

    items = [
        RedditProjectCardResponse(
            id=r.id,
            name=r.name,
            site_url=r.site_url,
            is_active=r.is_active,
            post_count=post_counts.get(r.id, 0),
            comment_count=comment_counts.get(r.id, 0),
            draft_count=draft_counts.get(r.id, 0),
            updated_at=r.updated_at,
        )
        for r in rows
    ]

    return RedditProjectListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Cross-project comment queue (on reddit_router, no project scope)
# ---------------------------------------------------------------------------


@reddit_router.get(
    "/comments",
    response_model=CommentQueueResponse,
)
async def list_all_comments(
    comment_status: str | None = Query(
        None, alias="status", description="Filter by comment status"
    ),
    project_id: str | None = Query(None, description="Filter by project ID"),
    search: str | None = Query(None, description="Search comment body (ILIKE)"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_session),
) -> CommentQueueResponse:
    """Cross-project comment review queue.

    Returns paginated comments with status counts for tab badges.
    Eager-loads the parent post for each comment.
    """
    # Base filters (project + search) shared by items query and count queries
    base_conditions = []
    if project_id is not None:
        base_conditions.append(RedditComment.project_id == project_id)
    if search is not None:
        escaped = search.replace("%", "\\%").replace("_", "\\_")
        base_conditions.append(RedditComment.body.ilike(f"%{escaped}%"))

    # Status counts (always unfiltered by status so tabs can show all counts)
    count_stmt = (
        select(RedditComment.status, func.count())
        .group_by(RedditComment.status)
    )
    for cond in base_conditions:
        count_stmt = count_stmt.where(cond)
    count_result = await db.execute(count_stmt)
    status_map = dict(count_result.all())

    counts = CommentQueueStatusCounts(
        draft=status_map.get("draft", 0),
        approved=status_map.get("approved", 0),
        rejected=status_map.get("rejected", 0),
        all=sum(status_map.values()),
    )

    # Items query with pagination
    items_stmt = (
        select(RedditComment)
        .options(selectinload(RedditComment.post))
        .order_by(RedditComment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    for cond in base_conditions:
        items_stmt = items_stmt.where(cond)
    if comment_status is not None:
        items_stmt = items_stmt.where(RedditComment.status == comment_status)

    # Total count for the filtered set (with status filter applied)
    total_stmt = select(func.count()).select_from(RedditComment)
    for cond in base_conditions:
        total_stmt = total_stmt.where(cond)
    if comment_status is not None:
        total_stmt = total_stmt.where(RedditComment.status == comment_status)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    result = await db.execute(items_stmt)
    comments = result.scalars().all()

    return CommentQueueResponse(
        items=[RedditCommentResponse.model_validate(c) for c in comments],
        total=total,
        counts=counts,
    )


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


# ---------------------------------------------------------------------------
# Comment generation endpoints (Phase 14c)
# ---------------------------------------------------------------------------


@reddit_project_router.post(
    "/{project_id}/reddit/posts/{post_id}/generate",
    response_model=RedditCommentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Post not found"},
    },
)
async def generate_single_comment(
    project_id: str,
    post_id: str,
    data: GenerateCommentRequest | None = None,
    db: AsyncSession = Depends(get_session),
) -> RedditCommentResponse:
    """Generate a single AI comment for a Reddit post.

    Creates a new comment each time (re-generation never overwrites).
    Returns 201 with the generated comment.
    """
    is_promotional = data.is_promotional if data else True

    # Load the post
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

    comment = await generate_comment(
        post=post,
        project_id=project_id,
        db=db,
        is_promotional=is_promotional,
    )
    await db.commit()

    # Reload with post relationship for response
    reload_stmt = (
        select(RedditComment)
        .options(selectinload(RedditComment.post))
        .where(RedditComment.id == comment.id)
    )
    reload_result = await db.execute(reload_stmt)
    comment = reload_result.scalar_one()

    return RedditCommentResponse.model_validate(comment)


async def _run_batch_generation(
    project_id: str, post_ids: list[str] | None
) -> None:
    """Background task wrapper for generate_batch."""
    try:
        await generate_batch(project_id=project_id, post_ids=post_ids)
    except Exception as e:
        logger.error(
            "Background batch generation failed",
            extra={
                "project_id": project_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )


@reddit_project_router.post(
    "/{project_id}/reddit/generate-batch",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        409: {"description": "Batch generation already in progress"},
    },
)
async def trigger_batch_generation(
    project_id: str,
    background_tasks: BackgroundTasks,
    data: BatchGenerateRequest | None = None,
) -> dict:
    """Trigger batch comment generation as a background task.

    If post_ids provided, generates for those posts only.
    Otherwise generates for all relevant posts without comments.
    Returns 202 immediately. Poll GET /generate/status for progress.
    """
    if is_generation_active(project_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Batch generation already in progress",
        )

    post_ids = data.post_ids if data else None
    background_tasks.add_task(_run_batch_generation, project_id, post_ids)

    return {"message": "Batch generation started"}


@reddit_project_router.get(
    "/{project_id}/reddit/generate/status",
    response_model=GenerationStatusResponse,
)
async def get_generation_status(
    project_id: str,
) -> GenerationStatusResponse:
    """Poll batch generation progress for a project.

    Returns current progress if generation is active, or "idle" if not.
    """
    progress = get_generation_progress(project_id)

    if progress is None:
        return GenerationStatusResponse(status="idle")

    return GenerationStatusResponse(
        status=progress.status,
        total_posts=progress.total_posts,
        posts_generated=progress.posts_generated,
        error=progress.error,
    )


@reddit_project_router.get(
    "/{project_id}/reddit/comments",
    response_model=list[RedditCommentResponse],
)
async def list_comments(
    project_id: str,
    comment_status: str | None = Query(
        None, alias="status", description="Filter by comment status"
    ),
    post_id: str | None = Query(None, description="Filter by post ID"),
    db: AsyncSession = Depends(get_session),
) -> list[RedditCommentResponse]:
    """List generated comments for a project with optional filters.

    Results are ordered by creation time descending (newest first).
    """
    stmt = (
        select(RedditComment)
        .options(selectinload(RedditComment.post))
        .where(RedditComment.project_id == project_id)
        .order_by(RedditComment.created_at.desc())
    )

    if comment_status is not None:
        stmt = stmt.where(RedditComment.status == comment_status)

    if post_id is not None:
        stmt = stmt.where(RedditComment.post_id == post_id)

    result = await db.execute(stmt)
    comments = result.scalars().all()

    return [RedditCommentResponse.model_validate(c) for c in comments]


# ---------------------------------------------------------------------------
# Bulk comment actions (Phase 14d) — must register before {comment_id} routes
# ---------------------------------------------------------------------------


@reddit_project_router.post(
    "/{project_id}/reddit/comments/bulk-approve",
)
async def bulk_approve_comments(
    project_id: str,
    data: BulkCommentActionRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Bulk approve draft comments. Non-draft comments are skipped."""
    if not data.comment_ids:
        return {"approved_count": 0}

    stmt = (
        update(RedditComment)
        .where(
            RedditComment.id.in_(data.comment_ids),
            RedditComment.project_id == project_id,
            RedditComment.status == "draft",
        )
        .values(status="approved")
    )

    result = await db.execute(stmt)
    await db.commit()

    return {"approved_count": result.rowcount}


@reddit_project_router.post(
    "/{project_id}/reddit/comments/bulk-reject",
)
async def bulk_reject_comments(
    project_id: str,
    data: BulkCommentRejectRequest,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Bulk reject draft comments with a shared reason. Non-draft comments are skipped."""
    if not data.comment_ids:
        return {"rejected_count": 0}

    stmt = (
        update(RedditComment)
        .where(
            RedditComment.id.in_(data.comment_ids),
            RedditComment.project_id == project_id,
            RedditComment.status == "draft",
        )
        .values(status="rejected", reject_reason=data.reason)
    )

    result = await db.execute(stmt)
    await db.commit()

    return {"rejected_count": result.rowcount}


# ---------------------------------------------------------------------------
# Single comment actions (delete, edit, approve, reject)
# ---------------------------------------------------------------------------


@reddit_project_router.delete(
    "/{project_id}/reddit/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment(
    project_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a comment regardless of status."""
    stmt = select(RedditComment).where(
        RedditComment.id == comment_id,
        RedditComment.project_id == project_id,
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment {comment_id} not found",
        )

    await db.delete(comment)
    await db.commit()


@reddit_project_router.patch(
    "/{project_id}/reddit/comments/{comment_id}",
    response_model=RedditCommentResponse,
)
async def update_comment(
    project_id: str,
    comment_id: str,
    data: RedditCommentUpdateRequest,
    db: AsyncSession = Depends(get_session),
) -> RedditCommentResponse:
    """Update a comment's body text. Only draft comments can be edited."""
    stmt = (
        select(RedditComment)
        .options(selectinload(RedditComment.post))
        .where(
            RedditComment.id == comment_id,
            RedditComment.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment {comment_id} not found",
        )

    if comment.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft comments can be edited",
        )

    comment.body = data.body
    await db.commit()
    await db.refresh(comment)

    return RedditCommentResponse.model_validate(comment)


@reddit_project_router.post(
    "/{project_id}/reddit/comments/{comment_id}/approve",
    response_model=RedditCommentResponse,
)
async def approve_comment(
    project_id: str,
    comment_id: str,
    data: CommentApproveRequest | None = None,
    db: AsyncSession = Depends(get_session),
) -> RedditCommentResponse:
    """Approve a draft comment, optionally updating its body text."""
    stmt = (
        select(RedditComment)
        .options(selectinload(RedditComment.post))
        .where(
            RedditComment.id == comment_id,
            RedditComment.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment {comment_id} not found",
        )

    if comment.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft comments can be approved",
        )

    if data and data.body is not None:
        comment.body = data.body

    comment.status = "approved"
    await db.commit()
    await db.refresh(comment)

    return RedditCommentResponse.model_validate(comment)


@reddit_project_router.post(
    "/{project_id}/reddit/comments/{comment_id}/reject",
    response_model=RedditCommentResponse,
)
async def reject_comment(
    project_id: str,
    comment_id: str,
    data: CommentRejectRequest,
    db: AsyncSession = Depends(get_session),
) -> RedditCommentResponse:
    """Reject a draft comment with a reason."""
    stmt = (
        select(RedditComment)
        .options(selectinload(RedditComment.post))
        .where(
            RedditComment.id == comment_id,
            RedditComment.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment {comment_id} not found",
        )

    if comment.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft comments can be rejected",
        )

    comment.status = "rejected"
    comment.reject_reason = data.reason
    await db.commit()
    await db.refresh(comment)

    return RedditCommentResponse.model_validate(comment)


@reddit_project_router.post(
    "/{project_id}/reddit/comments/{comment_id}/revert",
    response_model=RedditCommentResponse,
)
async def revert_comment_to_draft(
    project_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_session),
) -> RedditCommentResponse:
    """Revert an approved or rejected comment back to draft status."""
    stmt = (
        select(RedditComment)
        .options(selectinload(RedditComment.post))
        .where(
            RedditComment.id == comment_id,
            RedditComment.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    comment = result.scalar_one_or_none()

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comment {comment_id} not found",
        )

    if comment.status == "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Comment is already a draft",
        )

    comment.status = "draft"
    comment.reject_reason = None
    await db.commit()
    await db.refresh(comment)

    return RedditCommentResponse.model_validate(comment)
