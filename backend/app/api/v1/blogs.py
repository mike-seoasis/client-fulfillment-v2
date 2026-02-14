"""Blog campaigns API router.

REST endpoints for creating, listing, updating, approving, and deleting blog campaigns,
plus content generation trigger/poll, content CRUD, approval, and quality recheck.
"""

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_claude
from app.integrations.dataforseo import DataForSEOClient, get_dataforseo
from app.models.blog import BlogCampaign, BlogPost, CampaignStatus, ContentStatus
from app.models.brand_config import BrandConfig
from app.models.keyword_cluster import ClusterStatus, KeywordCluster
from app.schemas.blog import (
    BlogBulkApproveResponse,
    BlogCampaignCreate,
    BlogCampaignListItem,
    BlogCampaignResponse,
    BlogContentGenerationStatus,
    BlogContentTriggerResponse,
    BlogContentUpdateRequest,
    BlogPostGenerationStatusItem,
    BlogPostResponse,
    BlogPostUpdate,
)
from app.services.blog_topic_discovery import BlogTopicDiscoveryService
from app.services.project import ProjectService

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["Blogs"])

BLOG_DISCOVERY_TIMEOUT_SECONDS = 90

# Module-level set to track campaigns with active generation tasks.
# Sufficient for single-process deployments.
_active_blog_generations: set[str] = set()

# Cluster statuses that indicate completed content (has POP briefs)
_CLUSTER_COMPLETED_STATUSES = {
    ClusterStatus.APPROVED.value,
    ClusterStatus.CONTENT_GENERATING.value,
    ClusterStatus.COMPLETE.value,
}


@router.post(
    "/{project_id}/blogs",
    response_model=BlogCampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_blog_campaign(
    project_id: str,
    data: BlogCampaignCreate,
    db: AsyncSession = Depends(get_session),
    claude: ClaudeClient = Depends(get_claude),
    dataforseo: DataForSEOClient = Depends(get_dataforseo),
) -> BlogCampaignResponse:
    """Create a new blog campaign from a keyword cluster.

    Runs the 4-stage topic discovery pipeline synchronously:
    1. Extract POP seeds from approved cluster pages
    2. Expand seeds into blog topic candidates (Claude Haiku)
    3. Enrich with search volume (DataForSEO)
    4. Filter and rank candidates (Claude Haiku)

    Args:
        project_id: UUID of the project.
        data: BlogCampaignCreate with cluster_id and optional name.
        db: AsyncSession for database operations.
        claude: Claude client for LLM calls.
        dataforseo: DataForSEO client for volume data.

    Returns:
        BlogCampaignResponse with the created campaign and its posts.

    Raises:
        HTTPException: 404 if project or cluster not found.
        HTTPException: 409 if campaign already exists for this cluster.
        HTTPException: 422 if cluster doesn't have completed content.
        HTTPException: 504 if discovery exceeds timeout.
        HTTPException: 500 if discovery fails.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Verify cluster exists and belongs to this project
    cluster_stmt = select(KeywordCluster).where(
        KeywordCluster.id == data.cluster_id,
        KeywordCluster.project_id == project_id,
    )
    cluster_result = await db.execute(cluster_stmt)
    cluster = cluster_result.scalar_one_or_none()

    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {data.cluster_id} not found",
        )

    # Validate cluster has completed content
    if cluster.status not in _CLUSTER_COMPLETED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cluster must be approved with completed content before creating a blog campaign. "
                f"Current status: {cluster.status}"
            ),
        )

    # Check for existing campaign on this cluster (1:1 relationship)
    existing_stmt = select(BlogCampaign).where(
        BlogCampaign.cluster_id == data.cluster_id,
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A blog campaign already exists for cluster {data.cluster_id}",
        )

    # Fetch brand config for the project
    bc_stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
    bc_result = await db.execute(bc_stmt)
    brand_config_row = bc_result.scalar_one_or_none()
    brand_config: dict = brand_config_row.v2_schema if brand_config_row else {}

    # Run discovery with timeout
    service = BlogTopicDiscoveryService(claude, dataforseo)
    try:
        result = await asyncio.wait_for(
            service.discover_topics(
                cluster_id=data.cluster_id,
                project_id=project_id,
                brand_config=brand_config,
                db=db,
                name=data.name,
            ),
            timeout=BLOG_DISCOVERY_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Blog topic discovery timed out (>90s). Please try again.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Load the created campaign with posts for response
    campaign_id = result["campaign_id"]
    stmt = (
        select(BlogCampaign)
        .options(selectinload(BlogCampaign.posts))
        .where(BlogCampaign.id == campaign_id)
    )
    campaign_result = await db.execute(stmt)
    campaign = campaign_result.scalar_one()

    return BlogCampaignResponse.model_validate(campaign)


@router.get(
    "/{project_id}/blogs",
    response_model=list[BlogCampaignListItem],
)
async def list_blog_campaigns(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> list[BlogCampaignListItem]:
    """List all blog campaigns for a project.

    Returns campaigns with post counts and cluster name, ordered by created_at desc.

    Args:
        project_id: UUID of the project.
        db: AsyncSession for database operations.

    Returns:
        List of BlogCampaignListItem summaries.

    Raises:
        HTTPException: 404 if project not found.
    """
    await ProjectService.get_project(db, project_id)

    stmt = (
        select(
            BlogCampaign,
            KeywordCluster.name.label("cluster_name"),
            func.count(BlogPost.id).label("post_count"),
            func.count(
                func.nullif(BlogPost.is_approved, False)  # noqa: E712
            ).label("approved_count"),
            func.count(
                func.nullif(BlogPost.content_status, ContentStatus.PENDING.value)
            ).label("content_started_count"),
        )
        .outerjoin(BlogPost, BlogPost.campaign_id == BlogCampaign.id)
        .join(KeywordCluster, KeywordCluster.id == BlogCampaign.cluster_id)
        .where(BlogCampaign.project_id == project_id)
        .group_by(BlogCampaign.id, KeywordCluster.name)
        .order_by(BlogCampaign.created_at.desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    # For content_complete_count, count posts with content_status='complete'
    # We need a separate count since nullif only negates one value
    campaign_ids = [row[0].id for row in rows]
    complete_counts: dict[str, int] = {}
    if campaign_ids:
        complete_stmt = (
            select(
                BlogPost.campaign_id,
                func.count(BlogPost.id),
            )
            .where(
                BlogPost.campaign_id.in_(campaign_ids),
                BlogPost.content_status == ContentStatus.COMPLETE.value,
            )
            .group_by(BlogPost.campaign_id)
        )
        complete_result = await db.execute(complete_stmt)
        for cid, cnt in complete_result.all():
            complete_counts[cid] = cnt

    return [
        BlogCampaignListItem(
            id=campaign.id,
            name=campaign.name,
            status=campaign.status,
            cluster_name=cluster_name,
            post_count=post_count,
            approved_count=approved_count,
            content_complete_count=complete_counts.get(campaign.id, 0),
            created_at=campaign.created_at,
        )
        for campaign, cluster_name, post_count, approved_count, _ in rows
    ]


@router.get(
    "/{project_id}/blogs/{blog_id}",
    response_model=BlogCampaignResponse,
)
async def get_blog_campaign(
    project_id: str,
    blog_id: str,
    db: AsyncSession = Depends(get_session),
) -> BlogCampaignResponse:
    """Get a single blog campaign with all its posts.

    Args:
        project_id: UUID of the project.
        blog_id: UUID of the blog campaign.
        db: AsyncSession for database operations.

    Returns:
        BlogCampaignResponse with nested BlogPostResponse records.

    Raises:
        HTTPException: 404 if project or campaign not found.
    """
    await ProjectService.get_project(db, project_id)

    stmt = (
        select(BlogCampaign)
        .options(selectinload(BlogCampaign.posts))
        .where(
            BlogCampaign.id == blog_id,
            BlogCampaign.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()

    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog campaign {blog_id} not found",
        )

    return BlogCampaignResponse.model_validate(campaign)


@router.patch(
    "/{project_id}/blogs/{blog_id}/posts/{post_id}",
    response_model=BlogPostResponse,
)
async def update_blog_post(
    project_id: str,
    blog_id: str,
    post_id: str,
    data: BlogPostUpdate,
    db: AsyncSession = Depends(get_session),
) -> BlogPostResponse:
    """Update keyword-level fields on a blog post.

    Args:
        project_id: UUID of the project.
        blog_id: UUID of the blog campaign.
        post_id: UUID of the blog post.
        data: BlogPostUpdate with optional fields to update.
        db: AsyncSession for database operations.

    Returns:
        Updated BlogPostResponse.

    Raises:
        HTTPException: 404 if project, campaign, or post not found.
    """
    await ProjectService.get_project(db, project_id)

    # Verify campaign belongs to project
    campaign_stmt = select(BlogCampaign).where(
        BlogCampaign.id == blog_id,
        BlogCampaign.project_id == project_id,
    )
    campaign_result = await db.execute(campaign_stmt)
    campaign = campaign_result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog campaign {blog_id} not found",
        )

    # Load the target post
    post_stmt = select(BlogPost).where(
        BlogPost.id == post_id,
        BlogPost.campaign_id == blog_id,
    )
    post_result = await db.execute(post_stmt)
    post = post_result.scalar_one_or_none()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog post {post_id} not found",
        )

    # Apply updates
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value)

    await db.commit()
    await db.refresh(post)

    return BlogPostResponse.model_validate(post)


@router.post(
    "/{project_id}/blogs/{blog_id}/approve",
    status_code=status.HTTP_200_OK,
)
async def approve_blog_posts(
    project_id: str,
    blog_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Bulk approve all unapproved posts in a blog campaign.

    Sets is_approved=True on all unapproved posts. If all posts are now
    approved, updates the campaign status to 'writing'.

    Args:
        project_id: UUID of the project.
        blog_id: UUID of the blog campaign.
        db: AsyncSession for database operations.

    Returns:
        Dict with approved_count and campaign_status.

    Raises:
        HTTPException: 404 if project or campaign not found.
    """
    await ProjectService.get_project(db, project_id)

    # Verify campaign belongs to project and load posts
    stmt = (
        select(BlogCampaign)
        .options(selectinload(BlogCampaign.posts))
        .where(
            BlogCampaign.id == blog_id,
            BlogCampaign.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()

    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog campaign {blog_id} not found",
        )

    # Approve all unapproved posts
    approved_count = 0
    for post in campaign.posts:
        if not post.is_approved:
            post.is_approved = True
            approved_count += 1

    # Check if all posts are now approved → transition to 'writing'
    all_approved = all(post.is_approved for post in campaign.posts)
    if all_approved and campaign.status == CampaignStatus.PLANNING.value:
        campaign.status = CampaignStatus.WRITING.value

    await db.commit()

    return {
        "approved_count": approved_count,
        "campaign_status": campaign.status,
    }


@router.delete(
    "/{project_id}/blogs/{blog_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_blog_campaign(
    project_id: str,
    blog_id: str,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a blog campaign and all its posts (cascade).

    Args:
        project_id: UUID of the project.
        blog_id: UUID of the blog campaign.
        db: AsyncSession for database operations.

    Raises:
        HTTPException: 404 if project or campaign not found.
    """
    await ProjectService.get_project(db, project_id)

    stmt = select(BlogCampaign).where(
        BlogCampaign.id == blog_id,
        BlogCampaign.project_id == project_id,
    )
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()

    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog campaign {blog_id} not found",
        )

    await db.delete(campaign)
    await db.commit()


# =============================================================================
# Content Generation Endpoints
# =============================================================================


@router.post(
    "/{project_id}/blogs/{blog_id}/generate-content",
    response_model=BlogContentTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_blog_content(
    project_id: str,
    blog_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
) -> BlogContentTriggerResponse:
    """Trigger blog content generation for all approved posts in a campaign.

    Starts a background task that processes each approved post through
    the brief -> write -> check pipeline.

    Returns 400 if campaign status is not 'writing' or has no approved posts.
    Returns 409 if generation is already in progress for this campaign.
    """
    await ProjectService.get_project(db, project_id)

    # Load campaign with posts
    stmt = (
        select(BlogCampaign)
        .options(selectinload(BlogCampaign.posts))
        .where(
            BlogCampaign.id == blog_id,
            BlogCampaign.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()

    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog campaign {blog_id} not found",
        )

    # Validate campaign is in 'writing' status
    if campaign.status != CampaignStatus.WRITING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Campaign must be in 'writing' status to generate content. Current status: {campaign.status}",
        )

    # Validate has approved posts
    approved_posts = [p for p in campaign.posts if p.is_approved]
    if not approved_posts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved posts found. Approve posts before generating content.",
        )

    # Check for duplicate runs
    if blog_id in _active_blog_generations:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Content generation is already in progress for this campaign",
        )

    # Mark as active and start background task
    _active_blog_generations.add(blog_id)

    background_tasks.add_task(
        _run_blog_generation_background,
        campaign_id=blog_id,
    )

    logger.info(
        "Blog content generation triggered",
        extra={
            "project_id": project_id,
            "campaign_id": blog_id,
            "approved_posts": len(approved_posts),
        },
    )

    return BlogContentTriggerResponse(
        status="accepted",
        message=f"Blog content generation started for {len(approved_posts)} approved posts",
    )


async def _run_blog_generation_background(campaign_id: str) -> None:
    """Background task wrapper for the blog content generation pipeline."""
    from app.services.blog_content_generation import run_blog_content_pipeline

    try:
        result = await run_blog_content_pipeline(
            campaign_id=campaign_id,
            db=None,  # type: ignore[arg-type]  # pipeline creates its own sessions
        )
        logger.info(
            "Blog content generation pipeline finished",
            extra={
                "campaign_id": campaign_id,
                "succeeded": result.succeeded,
                "failed": result.failed,
                "skipped": result.skipped,
            },
        )
    except Exception as e:
        logger.error(
            "Blog content generation pipeline failed",
            extra={
                "campaign_id": campaign_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
    finally:
        _active_blog_generations.discard(campaign_id)


@router.get(
    "/{project_id}/blogs/{blog_id}/content-status",
    response_model=BlogContentGenerationStatus,
)
async def get_blog_content_status(
    project_id: str,
    blog_id: str,
    db: AsyncSession = Depends(get_session),
) -> BlogContentGenerationStatus:
    """Get content generation status for a blog campaign.

    Returns overall status, progress counts, and per-post status breakdown.
    Designed to be polled by the frontend during generation.
    """
    await ProjectService.get_project(db, project_id)

    # Load campaign with posts
    stmt = (
        select(BlogCampaign)
        .options(selectinload(BlogCampaign.posts))
        .where(
            BlogCampaign.id == blog_id,
            BlogCampaign.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    campaign = result.scalar_one_or_none()

    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog campaign {blog_id} not found",
        )

    # Build per-post status items
    post_items: list[BlogPostGenerationStatusItem] = []
    posts_completed = 0
    posts_failed = 0

    for post in campaign.posts:
        if post.content_status == ContentStatus.COMPLETE.value:
            posts_completed += 1
        elif post.content_status == ContentStatus.FAILED.value:
            posts_failed += 1

        post_items.append(
            BlogPostGenerationStatusItem(
                post_id=post.id,
                primary_keyword=post.primary_keyword,
                content_status=post.content_status,
            )
        )

    # Determine overall status
    posts_total = len(campaign.posts)
    if posts_total == 0:
        overall_status = "idle"
    elif blog_id in _active_blog_generations:
        overall_status = "generating"
    elif posts_completed + posts_failed >= posts_total:
        overall_status = "complete" if posts_failed == 0 else "failed"
    else:
        has_any_content = any(
            p.content_status != ContentStatus.PENDING.value for p in campaign.posts
        )
        overall_status = "idle" if not has_any_content else "complete"

    return BlogContentGenerationStatus(
        overall_status=overall_status,
        posts_total=posts_total,
        posts_completed=posts_completed,
        posts_failed=posts_failed,
        posts=post_items,
    )


@router.get(
    "/{project_id}/blogs/{blog_id}/posts/{post_id}/content",
    response_model=BlogPostResponse,
)
async def get_blog_post_content(
    project_id: str,
    blog_id: str,
    post_id: str,
    db: AsyncSession = Depends(get_session),
) -> BlogPostResponse:
    """Get full content for a specific blog post.

    Returns the BlogPost with all content fields, qa_results, and pop_brief summary.
    Returns 404 if content has not been generated yet.
    """
    await ProjectService.get_project(db, project_id)

    post = await _get_blog_post(db, project_id, blog_id, post_id)

    if post.content is None and post.content_status == ContentStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content has not been generated yet for this post",
        )

    return BlogPostResponse.model_validate(post)


@router.put(
    "/{project_id}/blogs/{blog_id}/posts/{post_id}/content",
    response_model=BlogPostResponse,
)
async def update_blog_post_content(
    project_id: str,
    blog_id: str,
    post_id: str,
    body: BlogContentUpdateRequest,
    db: AsyncSession = Depends(get_session),
) -> BlogPostResponse:
    """Update content fields on a blog post.

    Partial update — only provided fields are changed. Clears content_approved
    when content actually changes.
    """
    await ProjectService.get_project(db, project_id)

    post = await _get_blog_post(db, project_id, blog_id, post_id)

    # Apply partial updates
    update_data = body.model_dump(exclude_unset=True)
    content_fields = {"title", "meta_description", "content"}
    has_content_change = False
    for field, value in update_data.items():
        if field in content_fields and getattr(post, field) != value:
            has_content_change = True
        setattr(post, field, value)

    # Clear content approval when content actually changed
    if has_content_change:
        post.content_approved = False

    await db.commit()
    await db.refresh(post)

    return BlogPostResponse.model_validate(post)


@router.post(
    "/{project_id}/blogs/{blog_id}/posts/{post_id}/approve-content",
    response_model=BlogPostResponse,
)
async def approve_blog_post_content(
    project_id: str,
    blog_id: str,
    post_id: str,
    value: bool = True,
    db: AsyncSession = Depends(get_session),
) -> BlogPostResponse:
    """Approve or unapprove content for a blog post.

    By default, sets content_approved=True. Pass value=false to unapprove.
    """
    await ProjectService.get_project(db, project_id)

    post = await _get_blog_post(db, project_id, blog_id, post_id)

    post.content_approved = value

    await db.commit()
    await db.refresh(post)

    logger.info(
        "Blog post content approval updated",
        extra={
            "post_id": post_id,
            "campaign_id": blog_id,
            "content_approved": value,
        },
    )

    return BlogPostResponse.model_validate(post)


@router.post(
    "/{project_id}/blogs/{blog_id}/posts/{post_id}/recheck",
    response_model=BlogPostResponse,
)
async def recheck_blog_post_content(
    project_id: str,
    blog_id: str,
    post_id: str,
    db: AsyncSession = Depends(get_session),
) -> BlogPostResponse:
    """Re-run quality checks on current blog post content.

    Returns updated BlogPostResponse with fresh qa_results.
    Returns 404 if content has not been generated yet.
    """
    await ProjectService.get_project(db, project_id)

    post = await _get_blog_post(db, project_id, blog_id, post_id)

    if post.content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content has not been generated yet for this post",
        )

    # Load brand config
    campaign_stmt = select(BlogCampaign.project_id).where(BlogCampaign.id == blog_id)
    campaign_result = await db.execute(campaign_stmt)
    proj_id = campaign_result.scalar_one()

    brand_stmt = select(BrandConfig).where(BrandConfig.project_id == proj_id)
    brand_result = await db.execute(brand_stmt)
    brand_config_row = brand_result.scalar_one_or_none()
    brand_config = brand_config_row.v2_schema if brand_config_row else {}

    # Re-run quality checks
    from app.services.blog_content_generation import _run_blog_quality_checks

    qa_result = _run_blog_quality_checks(post, brand_config or {})
    post.qa_results = qa_result.to_dict()

    await db.commit()
    await db.refresh(post)

    logger.info(
        "Blog post quality recheck completed",
        extra={
            "post_id": post_id,
            "campaign_id": blog_id,
            "qa_passed": post.qa_results.get("passed") if post.qa_results else None,
        },
    )

    return BlogPostResponse.model_validate(post)


@router.post(
    "/{project_id}/blogs/{blog_id}/bulk-approve-content",
    response_model=BlogBulkApproveResponse,
)
async def bulk_approve_blog_content(
    project_id: str,
    blog_id: str,
    db: AsyncSession = Depends(get_session),
) -> BlogBulkApproveResponse:
    """Bulk-approve all eligible blog posts in a campaign.

    Finds posts where content_status='complete', qa_results.passed=true,
    and content_approved=False. Sets content_approved=True on each.
    """
    await ProjectService.get_project(db, project_id)

    # Verify campaign belongs to project
    campaign_stmt = select(BlogCampaign).where(
        BlogCampaign.id == blog_id,
        BlogCampaign.project_id == project_id,
    )
    campaign_result = await db.execute(campaign_stmt)
    campaign = campaign_result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog campaign {blog_id} not found",
        )

    # Find eligible posts: complete content, QA passed, not yet content-approved
    stmt = select(BlogPost).where(
        BlogPost.campaign_id == blog_id,
        BlogPost.content_status == ContentStatus.COMPLETE.value,
        BlogPost.content_approved.is_(False),
        BlogPost.qa_results["passed"].as_boolean().is_(True),
    )
    result = await db.execute(stmt)
    eligible = result.scalars().all()

    for post in eligible:
        post.content_approved = True

    await db.commit()

    approved_count = len(eligible)

    logger.info(
        "Bulk blog content approval completed",
        extra={
            "campaign_id": blog_id,
            "approved_count": approved_count,
        },
    )

    return BlogBulkApproveResponse(approved_count=approved_count)


# =============================================================================
# Helpers
# =============================================================================


async def _get_blog_post(
    db: AsyncSession,
    project_id: str,
    blog_id: str,
    post_id: str,
) -> BlogPost:
    """Load a blog post after verifying campaign ownership. Raises 404 if not found."""
    campaign_stmt = select(BlogCampaign).where(
        BlogCampaign.id == blog_id,
        BlogCampaign.project_id == project_id,
    )
    campaign_result = await db.execute(campaign_stmt)
    campaign = campaign_result.scalar_one_or_none()
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog campaign {blog_id} not found",
        )

    post_stmt = select(BlogPost).where(
        BlogPost.id == post_id,
        BlogPost.campaign_id == blog_id,
    )
    post_result = await db.execute(post_stmt)
    post = post_result.scalar_one_or_none()
    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blog post {post_id} not found",
        )

    return post
