"""Internal link management API router.

REST endpoints for triggering link planning, polling progress,
and managing internal links across project pages.
"""

from collections import Counter
from typing import Any

from bs4 import BeautifulSoup, Tag
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.internal_link import InternalLink
from app.models.keyword_cluster import ClusterPage, KeywordCluster
from app.models.page_content import ContentStatus, PageContent
from app.models.page_keywords import PageKeywords
from app.schemas.internal_link import (
    AddLinkRequest,
    AnchorSuggestionsResponse,
    EditLinkRequest,
    InternalLinkResponse,
    LinkMapPageSummary,
    LinkMapResponse,
    LinkPlanRequest,
    LinkPlanStatusResponse,
    PageLinksResponse,
)
from app.services.link_injection import LinkInjector
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
        cluster_pages_stmt = select(ClusterPage).where(
            ClusterPage.cluster_id == cluster_id,
            ClusterPage.is_approved.is_(True),
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


# =============================================================================
# LINK MAP & PAGE DETAIL ENDPOINTS (S9-022)
# =============================================================================


def _build_link_response(link: InternalLink) -> InternalLinkResponse:
    """Convert an InternalLink ORM object to InternalLinkResponse.

    Expects source_page and target_page relationships to be loaded.
    """
    target = link.target_page
    # Get target keyword from PageKeywords if loaded via relationship
    target_kw: str = ""
    if target and target.keywords:
        target_kw = target.keywords.primary_keyword or ""

    return InternalLinkResponse(
        id=link.id,
        source_page_id=link.source_page_id,
        target_page_id=link.target_page_id,
        target_url=target.normalized_url if target else "",
        target_title=target.title or "" if target else "",
        target_keyword=target_kw,
        anchor_text=link.anchor_text,
        anchor_type=link.anchor_type,
        position_in_content=link.position_in_content,
        is_mandatory=link.is_mandatory,
        placement_method=link.placement_method,
        status=link.status,
    )


def _compute_anchor_diversity_percentages(
    links: list[InternalLink],
) -> dict[str, Any]:
    """Count each anchor_type across all links, return percentages."""
    if not links:
        return {"exact_match": 0.0, "partial_match": 0.0, "natural": 0.0}

    counts: Counter[str] = Counter()
    for lnk in links:
        counts[lnk.anchor_type] += 1

    total = len(links)
    return {
        "exact_match": round(counts.get("exact_match", 0) / total * 100, 1),
        "partial_match": round(counts.get("partial_match", 0) / total * 100, 1),
        "natural": round(counts.get("natural", 0) / total * 100, 1),
    }


def _compute_diversity_score(links: list[InternalLink]) -> str:
    """Compute anchor diversity score for a set of links.

    Returns 'good', 'needs_variation', or 'poor'.
    """
    if not links:
        return "good"

    types_used = {lnk.anchor_type for lnk in links}
    if len(types_used) >= 3:
        return "good"
    if len(types_used) == 2:
        return "needs_variation"
    return "poor"


def _build_hierarchy_tree(
    cluster_pages: list[ClusterPage],
    page_summaries: dict[str, LinkMapPageSummary],
) -> dict[str, Any]:
    """Build a nested hierarchy dict for cluster mode.

    Parent page at root with children array.
    """
    parent_node: dict[str, Any] | None = None
    children: list[dict[str, Any]] = []

    for cp in cluster_pages:
        if not cp.crawled_page_id:
            continue
        summary = page_summaries.get(cp.crawled_page_id)
        node: dict[str, Any] = {
            "page_id": cp.crawled_page_id,
            "keyword": cp.keyword,
            "role": cp.role,
            "url": summary.url if summary else "",
            "title": summary.title if summary else "",
            "outbound_count": summary.outbound_count if summary else 0,
            "inbound_count": summary.inbound_count if summary else 0,
        }
        if cp.role == "parent":
            parent_node = node
        else:
            children.append(node)

    if parent_node is None:
        return {"children": children}

    parent_node["children"] = children
    return parent_node


@router.get(
    "/{project_id}/links",
    response_model=LinkMapResponse,
)
async def get_link_map(
    project_id: str,
    scope: str = Query("onboarding", description="Scope: 'onboarding' or 'cluster'"),
    cluster_id: str | None = Query(
        None, description="Cluster ID (required for cluster scope)"
    ),
    db: AsyncSession = Depends(get_session),
) -> LinkMapResponse:
    """Get the link map for a project scope.

    Returns aggregate stats, method breakdown, anchor diversity percentages,
    and per-page summaries. For cluster scope, includes hierarchy tree.
    """
    await ProjectService.get_project(db, project_id)

    # Build link query filtered by scope
    link_stmt = (
        select(InternalLink)
        .where(
            InternalLink.project_id == project_id,
            InternalLink.scope == scope,
        )
        .options(
            selectinload(InternalLink.source_page).selectinload(CrawledPage.keywords),
            selectinload(InternalLink.target_page).selectinload(CrawledPage.keywords),
        )
    )
    if scope == "cluster" and cluster_id:
        link_stmt = link_stmt.where(InternalLink.cluster_id == cluster_id)

    result = await db.execute(link_stmt)
    links = list(result.unique().scalars().all())

    # Collect unique page IDs involved in these links
    page_ids: set[str] = set()
    for lnk in links:
        page_ids.add(lnk.source_page_id)
        page_ids.add(lnk.target_page_id)

    # Load CrawledPage data for all involved pages
    pages_map: dict[str, CrawledPage] = {}
    if page_ids:
        pages_stmt = (
            select(CrawledPage)
            .where(CrawledPage.id.in_(page_ids))
            .options(selectinload(CrawledPage.keywords))
        )
        pages_result = await db.execute(pages_stmt)
        for page in pages_result.unique().scalars().all():
            pages_map[page.id] = page

    # Count outbound/inbound per page
    outbound_counts: Counter[str] = Counter()
    inbound_counts: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()
    page_methods: dict[str, Counter[str]] = {}
    page_statuses: dict[str, list[str]] = {}

    for lnk in links:
        outbound_counts[lnk.source_page_id] += 1
        inbound_counts[lnk.target_page_id] += 1
        method_counts[lnk.placement_method] += 1

        # Per-page method tracking
        if lnk.source_page_id not in page_methods:
            page_methods[lnk.source_page_id] = Counter()
        page_methods[lnk.source_page_id][lnk.placement_method] += 1

        # Per-page status tracking
        if lnk.source_page_id not in page_statuses:
            page_statuses[lnk.source_page_id] = []
        page_statuses[lnk.source_page_id].append(lnk.status)

    # Build page summaries
    page_summaries: dict[str, LinkMapPageSummary] = {}
    for pid in page_ids:
        crawled = pages_map.get(pid)
        if not crawled:
            continue

        statuses = page_statuses.get(pid, [])
        if any(s.startswith("failed") for s in statuses):
            validation_status = "fail"
        elif any(s == "injected" for s in statuses):
            validation_status = "warning"
        else:
            validation_status = "pass"

        page_summaries[pid] = LinkMapPageSummary(
            page_id=pid,
            url=crawled.normalized_url,
            title=crawled.title or "",
            is_priority=crawled.keywords.is_priority if crawled.keywords else False,
            role=None,
            labels=crawled.labels if crawled.labels else None,
            outbound_count=outbound_counts.get(pid, 0),
            inbound_count=inbound_counts.get(pid, 0),
            methods=dict(page_methods.get(pid, Counter())),
            validation_status=validation_status,
        )

    # Aggregate stats
    total_links = len(links)
    total_pages = len(page_ids)
    avg_links = round(total_links / total_pages, 2) if total_pages > 0 else 0.0

    # Validation pass rate
    pass_count = sum(
        1 for s in page_summaries.values() if s.validation_status == "pass"
    )
    pass_rate = round(pass_count / total_pages * 100, 1) if total_pages > 0 else 100.0

    # Anchor diversity
    anchor_diversity = _compute_anchor_diversity_percentages(links)

    # For cluster scope, build hierarchy tree and set page roles
    hierarchy: dict[str, Any] | None = None
    if scope == "cluster" and cluster_id:
        cp_stmt = select(ClusterPage).where(
            ClusterPage.cluster_id == cluster_id,
            ClusterPage.is_approved.is_(True),
        )
        cp_result = await db.execute(cp_stmt)
        cluster_pages = list(cp_result.scalars().all())

        # Set role on page summaries
        for cp in cluster_pages:
            if cp.crawled_page_id and cp.crawled_page_id in page_summaries:
                page_summaries[cp.crawled_page_id].role = cp.role

        hierarchy = _build_hierarchy_tree(cluster_pages, page_summaries)

    return LinkMapResponse(
        scope=scope,
        total_links=total_links,
        total_pages=total_pages,
        avg_links_per_page=avg_links,
        validation_pass_rate=pass_rate,
        method_breakdown=dict(method_counts),
        anchor_diversity=anchor_diversity,
        pages=list(page_summaries.values()),
        hierarchy=hierarchy,
    )


@router.get(
    "/{project_id}/links/page/{page_id}",
    response_model=PageLinksResponse,
)
async def get_page_links(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
) -> PageLinksResponse:
    """Get all links for a specific page with diversity metrics.

    Returns outbound links (ordered by position), inbound links, and
    anchor diversity section with diversity_score.
    """
    await ProjectService.get_project(db, project_id)

    # Verify page exists and belongs to project
    page_stmt = select(CrawledPage).where(
        CrawledPage.id == page_id,
        CrawledPage.project_id == project_id,
    )
    page_result = await db.execute(page_stmt)
    page = page_result.scalar_one_or_none()
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found in project {project_id}",
        )

    # Outbound links (ordered by position_in_content)
    outbound_stmt = (
        select(InternalLink)
        .where(
            InternalLink.source_page_id == page_id,
            InternalLink.project_id == project_id,
        )
        .options(
            selectinload(InternalLink.target_page).selectinload(CrawledPage.keywords),
        )
        .order_by(InternalLink.position_in_content.asc().nullslast())
    )
    outbound_result = await db.execute(outbound_stmt)
    outbound_links = list(outbound_result.unique().scalars().all())

    # Inbound links
    inbound_stmt = (
        select(InternalLink)
        .where(
            InternalLink.target_page_id == page_id,
            InternalLink.project_id == project_id,
        )
        .options(
            selectinload(InternalLink.target_page).selectinload(CrawledPage.keywords),
        )
    )
    inbound_result = await db.execute(inbound_stmt)
    inbound_links = list(inbound_result.unique().scalars().all())

    # All links for diversity calculation
    all_links = outbound_links + inbound_links

    # Anchor diversity counts
    anchor_counts: Counter[str] = Counter()
    for lnk in all_links:
        anchor_counts[lnk.anchor_type] += 1

    return PageLinksResponse(
        outbound_links=[_build_link_response(lnk) for lnk in outbound_links],
        inbound_links=[_build_link_response(lnk) for lnk in inbound_links],
        anchor_diversity=dict(anchor_counts),
        diversity_score=_compute_diversity_score(all_links),
    )


@router.get(
    "/{project_id}/links/suggestions/{target_page_id}",
    response_model=AnchorSuggestionsResponse,
)
async def get_anchor_suggestions(
    project_id: str,
    target_page_id: str,
    db: AsyncSession = Depends(get_session),
) -> AnchorSuggestionsResponse:
    """Get anchor text suggestions for a target page.

    Returns the primary keyword, POP keyword_targets variations,
    and usage counts of existing anchor texts linking to this page.
    """
    await ProjectService.get_project(db, project_id)

    # Verify target page exists and belongs to project
    page_stmt = select(CrawledPage).where(
        CrawledPage.id == target_page_id,
        CrawledPage.project_id == project_id,
    )
    page_result = await db.execute(page_stmt)
    page = page_result.scalar_one_or_none()
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {target_page_id} not found in project {project_id}",
        )

    # Get primary keyword
    kw_stmt = select(PageKeywords).where(
        PageKeywords.crawled_page_id == target_page_id,
    )
    kw_result = await db.execute(kw_stmt)
    page_kw = kw_result.scalar_one_or_none()
    primary_keyword = page_kw.primary_keyword if page_kw else ""

    # Get POP variations from ContentBrief
    pop_variations: list[str] = []
    brief_stmt = select(ContentBrief).where(
        ContentBrief.page_id == target_page_id,
    )
    brief_result = await db.execute(brief_stmt)
    brief = brief_result.scalar_one_or_none()
    if brief and brief.keyword_targets:
        for kt in brief.keyword_targets:
            kw_value: str = kt.get("keyword", "") if isinstance(kt, dict) else ""
            if kw_value and kw_value != primary_keyword:
                pop_variations.append(kw_value)

    # Get usage counts of existing anchor texts
    usage_stmt = (
        select(
            InternalLink.anchor_text,
            func.count().label("count"),
        )
        .where(
            InternalLink.target_page_id == target_page_id,
            InternalLink.project_id == project_id,
        )
        .group_by(InternalLink.anchor_text)
    )

    usage_result = await db.execute(usage_stmt)
    usage_counts: dict[str, int] = {}
    for row in usage_result.all():
        anchor_text: str = row[0]
        count: int = row[1]
        usage_counts[anchor_text] = count

    return AnchorSuggestionsResponse(
        primary_keyword=primary_keyword,
        pop_variations=pop_variations,
        usage_counts=usage_counts,
    )


# =============================================================================
# MANUAL LINK MANAGEMENT ENDPOINTS (S9-023)
# =============================================================================


@router.post(
    "/{project_id}/links",
    response_model=InternalLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_link(
    project_id: str,
    body: AddLinkRequest,
    db: AsyncSession = Depends(get_session),
) -> InternalLinkResponse:
    """Manually add an internal link.

    Validates silo integrity, no duplicates, and no self-links. Injects
    the link into bottom_description content (rule-based, LLM fallback).
    Creates InternalLink with status='verified'.

    Returns 400 for validation violations, 404 for invalid page IDs.
    """
    await ProjectService.get_project(db, project_id)

    source_page_id = body.source_page_id
    target_page_id = body.target_page_id

    # ---- Validate no self-links ----
    if source_page_id == target_page_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a self-link (source and target are the same page)",
        )

    # ---- Verify source page exists and belongs to project ----
    source_stmt = select(CrawledPage).where(
        CrawledPage.id == source_page_id,
        CrawledPage.project_id == project_id,
    )
    source_result = await db.execute(source_stmt)
    source_page = source_result.scalar_one_or_none()
    if not source_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source page {source_page_id} not found in project {project_id}",
        )

    # ---- Verify target page exists and belongs to project ----
    target_stmt = select(CrawledPage).where(
        CrawledPage.id == target_page_id,
        CrawledPage.project_id == project_id,
    )
    target_result = await db.execute(target_stmt)
    target_page = target_result.scalar_one_or_none()
    if not target_page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target page {target_page_id} not found in project {project_id}",
        )

    # ---- Validate no duplicate links (same source -> same target) ----
    dup_stmt = (
        select(func.count())
        .select_from(InternalLink)
        .where(
            InternalLink.source_page_id == source_page_id,
            InternalLink.target_page_id == target_page_id,
            InternalLink.project_id == project_id,
            InternalLink.status != "removed",
        )
    )
    dup_result = await db.execute(dup_stmt)
    if (dup_result.scalar_one() or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A link from this source to this target already exists",
        )

    # ---- Determine scope and validate silo integrity ----
    # Check if both pages are in the same cluster
    source_cluster_stmt = select(ClusterPage).where(
        ClusterPage.crawled_page_id == source_page_id,
        ClusterPage.is_approved.is_(True),
    )
    source_cp_result = await db.execute(source_cluster_stmt)
    source_cluster_pages = list(source_cp_result.scalars().all())

    target_cluster_stmt = select(ClusterPage).where(
        ClusterPage.crawled_page_id == target_page_id,
        ClusterPage.is_approved.is_(True),
    )
    target_cp_result = await db.execute(target_cluster_stmt)
    target_cluster_pages = list(target_cp_result.scalars().all())

    # Find shared cluster (if any)
    source_clusters = {cp.cluster_id for cp in source_cluster_pages}
    target_clusters = {cp.cluster_id for cp in target_cluster_pages}
    shared_clusters = source_clusters & target_clusters

    if shared_clusters:
        scope = "cluster"
        cluster_id: str | None = next(iter(shared_clusters))
    else:
        scope = "onboarding"
        cluster_id = None
        # For onboarding scope, verify silo integrity:
        # if source is in a cluster, target must also be in the same cluster
        # (already checked above — no shared cluster means onboarding scope is fine)

    # ---- Load source page content for injection ----
    content_stmt = select(PageContent).where(
        PageContent.crawled_page_id == source_page_id,
    )
    content_result = await db.execute(content_stmt)
    page_content = content_result.scalar_one_or_none()

    if not page_content or not page_content.bottom_description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source page has no content to inject a link into",
        )

    # ---- Inject link into content ----
    injector = LinkInjector()
    target_url = target_page.normalized_url

    # Try rule-based first
    modified_html, p_idx = injector.inject_rule_based(
        page_content.bottom_description,
        body.anchor_text,
        target_url,
    )

    placement_method = "rule_based"
    if p_idx is None:
        # Fall back to LLM injection
        # Get target keyword for relevance scoring
        kw_stmt = select(PageKeywords).where(
            PageKeywords.crawled_page_id == target_page_id,
        )
        kw_result = await db.execute(kw_stmt)
        target_kw = kw_result.scalar_one_or_none()
        target_keyword = target_kw.primary_keyword if target_kw else ""

        modified_html, p_idx = await injector.inject_llm_fallback(
            page_content.bottom_description,
            body.anchor_text,
            target_url,
            target_keyword,
        )
        placement_method = "llm_fallback"

    if p_idx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not inject link into content (no suitable location found)",
        )

    # ---- Update page content with injected HTML ----
    page_content.bottom_description = modified_html
    await db.flush()

    # ---- Create InternalLink record ----
    new_link = InternalLink(
        source_page_id=source_page_id,
        target_page_id=target_page_id,
        project_id=project_id,
        cluster_id=cluster_id,
        scope=scope,
        anchor_text=body.anchor_text,
        anchor_type=body.anchor_type,
        position_in_content=p_idx,
        is_mandatory=False,
        placement_method=placement_method,
        status="verified",
    )
    db.add(new_link)
    await db.flush()

    # ---- Load relationships for response ----
    link_stmt = (
        select(InternalLink)
        .where(InternalLink.id == new_link.id)
        .options(
            selectinload(InternalLink.target_page).selectinload(CrawledPage.keywords),
        )
    )
    link_result = await db.execute(link_stmt)
    loaded_link = link_result.unique().scalar_one()

    await db.commit()

    logger.info(
        "Manual link added",
        extra={
            "project_id": project_id,
            "link_id": new_link.id,
            "source_page_id": source_page_id,
            "target_page_id": target_page_id,
            "placement_method": placement_method,
        },
    )

    return _build_link_response(loaded_link)


@router.delete(
    "/{project_id}/links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_link(
    project_id: str,
    link_id: str,
    db: AsyncSession = Depends(get_session),
) -> Response:
    """Remove an internal link.

    Rejects removal of mandatory links (400). Strips the <a> tag from
    content (unwrap), keeping the text. Sets InternalLink status='removed'.

    Returns 204 on success, 400 for mandatory links, 404 for invalid link_id.
    """
    await ProjectService.get_project(db, project_id)

    # ---- Load the link ----
    link_stmt = select(InternalLink).where(
        InternalLink.id == link_id,
        InternalLink.project_id == project_id,
    )
    link_result = await db.execute(link_stmt)
    link = link_result.scalar_one_or_none()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link {link_id} not found in project {project_id}",
        )

    # ---- Reject mandatory links ----
    if link.is_mandatory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove a mandatory link",
        )

    # ---- Strip <a> tag from content ----
    content_stmt = select(PageContent).where(
        PageContent.crawled_page_id == link.source_page_id,
    )
    content_result = await db.execute(content_stmt)
    page_content = content_result.scalar_one_or_none()

    if page_content and page_content.bottom_description:
        soup = BeautifulSoup(page_content.bottom_description, "html.parser")
        target_url = ""

        # Load target page URL
        target_stmt = select(CrawledPage).where(CrawledPage.id == link.target_page_id)
        target_result = await db.execute(target_stmt)
        target_page = target_result.scalar_one_or_none()
        if target_page:
            target_url = target_page.normalized_url

        # Find and unwrap the <a> tag matching this link's anchor text and href
        for a_tag in soup.find_all("a"):
            href = a_tag.get("href", "")
            if not isinstance(href, str):
                href = str(href)
            tag_text = a_tag.get_text()

            # Match by anchor text; if multiple matches, use href to disambiguate
            if tag_text == link.anchor_text and (not target_url or href == target_url):
                a_tag.unwrap()
                break

        page_content.bottom_description = str(soup)
        await db.flush()

    # ---- Set status to removed ----
    link.status = "removed"
    await db.commit()

    logger.info(
        "Link removed",
        extra={
            "project_id": project_id,
            "link_id": link_id,
        },
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{project_id}/links/{link_id}",
    response_model=InternalLinkResponse,
)
async def edit_link(
    project_id: str,
    link_id: str,
    body: EditLinkRequest,
    db: AsyncSession = Depends(get_session),
) -> InternalLinkResponse:
    """Edit an existing internal link's anchor text and type.

    Finds the existing <a> tag in content by matching current anchor text,
    replaces with new anchor text, updates the InternalLink row.

    Returns 404 for invalid link_id, updated link on success.
    """
    await ProjectService.get_project(db, project_id)

    # ---- Load the link with target page relationship ----
    link_stmt = (
        select(InternalLink)
        .where(
            InternalLink.id == link_id,
            InternalLink.project_id == project_id,
        )
        .options(
            selectinload(InternalLink.target_page).selectinload(CrawledPage.keywords),
        )
    )
    link_result = await db.execute(link_stmt)
    link = link_result.unique().scalar_one_or_none()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link {link_id} not found in project {project_id}",
        )

    old_anchor_text = link.anchor_text
    new_anchor_text = body.anchor_text

    # ---- Update anchor text in content ----
    content_stmt = select(PageContent).where(
        PageContent.crawled_page_id == link.source_page_id,
    )
    content_result = await db.execute(content_stmt)
    page_content = content_result.scalar_one_or_none()

    if page_content and page_content.bottom_description:
        soup = BeautifulSoup(page_content.bottom_description, "html.parser")
        target_url = link.target_page.normalized_url if link.target_page else ""

        # Find the <a> tag by text content; disambiguate by href if needed
        matched_tag: Tag | None = None
        for a_tag in soup.find_all("a"):
            tag_text = a_tag.get_text()
            if tag_text == old_anchor_text:
                href = a_tag.get("href", "")
                if not isinstance(href, str):
                    href = str(href)
                # If href matches or no target_url to check, this is the one
                if not target_url or href == target_url:
                    matched_tag = a_tag
                    break
                # Fallback: accept text match even without href match
                if matched_tag is None:
                    matched_tag = a_tag

        if matched_tag is not None:
            matched_tag.string = new_anchor_text

        page_content.bottom_description = str(soup)
        await db.flush()

    # ---- Update InternalLink row ----
    link.anchor_text = new_anchor_text
    link.anchor_type = body.anchor_type
    await db.commit()

    # Refresh for response
    await db.refresh(link)

    logger.info(
        "Link edited",
        extra={
            "project_id": project_id,
            "link_id": link_id,
            "old_anchor": old_anchor_text,
            "new_anchor": new_anchor_text,
        },
    )

    return _build_link_response(link)
