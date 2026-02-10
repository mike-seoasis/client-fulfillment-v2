"""Internal link management API router.

REST endpoints for triggering link planning, polling progress,
and managing internal links across project pages.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.crawled_page import CrawledPage
from app.models.internal_link import InternalLink
from app.models.keyword_cluster import ClusterPage, KeywordCluster
from app.models.page_content import ContentStatus, PageContent
from app.models.page_keywords import PageKeywords
from app.schemas.internal_link import LinkPlanRequest, LinkPlanStatusResponse
from app.services.project import ProjectService

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["Internal Links"])

# Module-level set to track projects with active link planning tasks.
_active_plans: set[tuple[str, str, str | None]] = set()


@router.post(
    "/{project_id}/links/plan",
    response_model=LinkPlanStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def plan_links(
    project_id: str,
    body: LinkPlanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
) -> LinkPlanStatusResponse:
    """Trigger link planning for a project scope.

    Validates prerequisites (all content complete, all keywords approved),
    then starts the link planning pipeline as a background task.

    If existing links exist for the scope, triggers the re-plan flow
    (snapshot -> strip -> delete -> re-run).

    Returns 400 if prerequisites are not met.
    Returns 409 if planning is already in progress for this scope.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    scope = body.scope
    cluster_id = body.cluster_id

    # Check for duplicate runs
    plan_key = (project_id, scope, cluster_id)
    if plan_key in _active_plans:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Link planning is already in progress for this scope",
        )

    # ---- Scope-specific validation ----
    if scope == "cluster":
        # cluster_id is required for cluster scope
        if not cluster_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cluster_id is required when scope is 'cluster'",
            )

        # Verify cluster exists
        cluster_stmt = select(KeywordCluster).where(KeywordCluster.id == cluster_id)
        cluster_result = await db.execute(cluster_stmt)
        cluster = cluster_result.scalar_one_or_none()
        if not cluster:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cluster {cluster_id} not found",
            )

        # Cluster must have >= 2 approved pages
        approved_pages_stmt = (
            select(func.count())
            .select_from(ClusterPage)
            .where(
                ClusterPage.cluster_id == cluster_id,
                ClusterPage.is_approved.is_(True),
            )
        )
        approved_result = await db.execute(approved_pages_stmt)
        approved_count = approved_result.scalar_one()

        if approved_count < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cluster needs at least 2 approved pages, found {approved_count}",
            )

    # ---- Prerequisite validation (all content complete, all keywords approved) ----
    missing_content_ids: list[str] = []
    missing_keyword_ids: list[str] = []

    if scope == "onboarding":
        # Check all project pages have complete content and approved keywords
        pages_stmt = select(CrawledPage).where(CrawledPage.project_id == project_id)
        pages_result = await db.execute(pages_stmt)
        pages = pages_result.scalars().all()

        for page in pages:
            # Check content status
            content_stmt = select(PageContent).where(
                PageContent.crawled_page_id == page.id,
            )
            content_result = await db.execute(content_stmt)
            content = content_result.scalar_one_or_none()
            if not content or content.status != ContentStatus.COMPLETE.value:
                missing_content_ids.append(page.id)

            # Check keyword approval
            kw_stmt = select(PageKeywords).where(
                PageKeywords.crawled_page_id == page.id,
                PageKeywords.is_approved.is_(True),
            )
            kw_result = await db.execute(kw_stmt)
            kw = kw_result.scalar_one_or_none()
            if not kw:
                missing_keyword_ids.append(page.id)

    else:
        # For cluster scope, check the cluster's approved pages
        cluster_pages_stmt = (
            select(ClusterPage)
            .where(
                ClusterPage.cluster_id == cluster_id,
                ClusterPage.is_approved.is_(True),
            )
        )
        cp_result = await db.execute(cluster_pages_stmt)
        cluster_pages = cp_result.scalars().all()

        for cp in cluster_pages:
            if not cp.crawled_page_id:
                missing_content_ids.append(cp.id)
                continue

            # Check content status
            content_stmt = select(PageContent).where(
                PageContent.crawled_page_id == cp.crawled_page_id,
            )
            content_result = await db.execute(content_stmt)
            content = content_result.scalar_one_or_none()
            if not content or content.status != ContentStatus.COMPLETE.value:
                missing_content_ids.append(cp.crawled_page_id)

            # Check keyword approval
            kw_stmt = select(PageKeywords).where(
                PageKeywords.crawled_page_id == cp.crawled_page_id,
                PageKeywords.is_approved.is_(True),
            )
            kw_result = await db.execute(kw_stmt)
            kw = kw_result.scalar_one_or_none()
            if not kw:
                missing_keyword_ids.append(cp.crawled_page_id)

    if missing_content_ids or missing_keyword_ids:
        messages: list[str] = []
        if missing_content_ids:
            messages.append(
                f"Content not complete for page IDs: {', '.join(missing_content_ids)}"
            )
        if missing_keyword_ids:
            messages.append(
                f"Keywords not approved for page IDs: {', '.join(missing_keyword_ids)}"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(messages),
        )

    # ---- Check for existing links (triggers re-plan flow) ----
    existing_links_stmt = (
        select(func.count())
        .select_from(InternalLink)
        .where(
            InternalLink.project_id == project_id,
            InternalLink.scope == scope,
        )
    )
    if scope == "cluster" and cluster_id:
        existing_links_stmt = existing_links_stmt.where(
            InternalLink.cluster_id == cluster_id,
        )
    existing_result = await db.execute(existing_links_stmt)
    has_existing_links = (existing_result.scalar_one() or 0) > 0

    # Mark as active and start background task
    _active_plans.add(plan_key)

    background_tasks.add_task(
        _run_link_planning_background,
        project_id=project_id,
        scope=scope,
        cluster_id=cluster_id,
        replan=has_existing_links,
    )

    logger.info(
        "Link planning triggered",
        extra={
            "project_id": project_id,
            "scope": scope,
            "cluster_id": cluster_id,
            "replan": has_existing_links,
        },
    )

    return LinkPlanStatusResponse(
        status="planning",
        current_step=1,
        step_label="Starting link planning pipeline",
        pages_processed=0,
        total_pages=0,
    )


async def _run_link_planning_background(
    project_id: str,
    scope: str,
    cluster_id: str | None,
    replan: bool,
) -> None:
    """Background task wrapper for the link planning pipeline.

    Runs the pipeline (or re-plan flow) and cleans up active tracking.
    """
    from app.core.database import db_manager
    from app.services.link_planning import replan_links, run_link_planning_pipeline

    plan_key = (project_id, scope, cluster_id)

    try:
        async with db_manager.session_factory() as db:
            if replan:
                await replan_links(project_id, scope, cluster_id, db)  # type: ignore[arg-type]
            else:
                await run_link_planning_pipeline(project_id, scope, cluster_id, db)  # type: ignore[arg-type]

        logger.info(
            "Link planning pipeline finished",
            extra={
                "project_id": project_id,
                "scope": scope,
                "cluster_id": cluster_id,
                "replan": replan,
            },
        )
    except Exception as e:
        logger.error(
            "Link planning pipeline failed",
            extra={
                "project_id": project_id,
                "scope": scope,
                "cluster_id": cluster_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
    finally:
        _active_plans.discard(plan_key)


@router.get(
    "/{project_id}/links/plan/status",
    response_model=LinkPlanStatusResponse,
)
async def get_link_plan_status(
    project_id: str,
    scope: str = Query(..., description="Scope: 'onboarding' or 'cluster'"),
    cluster_id: str | None = Query(None, description="Required when scope='cluster'"),
    db: AsyncSession = Depends(get_session),
) -> LinkPlanStatusResponse:
    """Get current link planning status for a project scope.

    Returns the progress state from the pipeline's module-level dict.
    If no pipeline is running or has run, returns idle status.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    from app.services.link_planning import get_pipeline_progress

    progress = get_pipeline_progress(project_id, scope, cluster_id)

    if progress is None:
        return LinkPlanStatusResponse(
            status="idle",
            pages_processed=0,
            total_pages=0,
        )

    return LinkPlanStatusResponse(
        status=progress.get("status", "idle"),
        current_step=progress.get("current_step"),
        step_label=progress.get("step_label"),
        pages_processed=progress.get("pages_processed", 0),
        total_pages=progress.get("total_pages", 0),
        total_links=progress.get("total_links"),
        error=progress.get("error"),
    )
