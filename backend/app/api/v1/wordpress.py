"""WordPress blog internal linking API router.

REST endpoints for the 7-step WordPress linking wizard:
Connect → Import → Analyze → Label → Plan → Review → Export.
"""

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import db_manager, get_session
from app.core.logging import get_logger
from app.schemas.wordpress import (
    WPAnalyzeRequest,
    WPConnectRequest,
    WPConnectResponse,
    WPExportRequest,
    WPImportRequest,
    WPImportResponse,
    WPLabelRequest,
    WPLabelReviewResponse,
    WPPlanRequest,
    WPProgressResponse,
    WPReviewResponse,
    WPReviewGroup,
    WPTaxonomyLabel,
    WPLabelAssignment,
)
from app.services.wordpress_linker import (
    get_wp_progress,
    step1_connect,
    step2_import,
    step3_analyze,
    step4_label,
    step5_plan_links,
    step6_get_review,
    step7_export,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/wordpress", tags=["WordPress Linker"])


# =============================================================================
# STEP 1: CONNECT
# =============================================================================


@router.post("/connect", response_model=WPConnectResponse)
async def connect(body: WPConnectRequest) -> WPConnectResponse:
    """Validate WordPress credentials and return site info."""
    try:
        info = await step1_connect(body.site_url, body.username, body.app_password)
        return WPConnectResponse(
            site_name=info.name,
            site_url=info.url,
            total_posts=info.total_posts,
            valid=True,
        )
    except Exception as e:
        logger.warning("WP connect failed", extra={"error": str(e)})
        return WPConnectResponse(
            site_name="",
            site_url=body.site_url,
            total_posts=0,
            valid=False,
        )


# =============================================================================
# STEP 2: IMPORT
# =============================================================================


@router.post(
    "/import",
    response_model=WPImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_posts(
    body: WPImportRequest,
    background_tasks: BackgroundTasks,
) -> WPImportResponse:
    """Import WordPress posts as a background task."""
    job_id = str(uuid4())

    async def _run_import() -> None:
        async with db_manager.session_factory() as db:
            await step2_import(
                db=db,
                site_url=body.site_url,
                username=body.username,
                app_password=body.app_password,
                job_id=job_id,
                title_filter=body.title_filter,
                post_status=body.post_status,
            )

    background_tasks.add_task(_run_import)

    return WPImportResponse(
        project_id="",  # Will be set in progress result
        posts_imported=0,
        job_id=job_id,
    )


# =============================================================================
# PROGRESS POLLING (shared)
# =============================================================================


@router.get("/progress/{job_id}", response_model=WPProgressResponse)
async def get_progress(job_id: str) -> WPProgressResponse:
    """Poll progress for any background operation."""
    progress = get_wp_progress(job_id)
    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return WPProgressResponse(
        job_id=job_id,
        step=progress.get("step", "unknown"),
        step_label=progress.get("step_label", ""),
        status=progress.get("status", "unknown"),
        current=progress.get("current", 0),
        total=progress.get("total", 0),
        error=progress.get("error"),
        result=progress.get("result"),
    )


# =============================================================================
# STEP 3: ANALYZE
# =============================================================================


@router.post(
    "/analyze",
    response_model=WPProgressResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze_posts(
    body: WPAnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> WPProgressResponse:
    """Run POP analysis on imported posts (background task)."""
    job_id = str(uuid4())

    async def _run_analyze() -> None:
        async with db_manager.session_factory() as db:
            await step3_analyze(db=db, project_id=body.project_id, job_id=job_id)

    background_tasks.add_task(_run_analyze)

    return WPProgressResponse(
        job_id=job_id,
        step="analyze",
        step_label="Starting POP analysis",
        status="running",
        current=0,
        total=0,
    )


# =============================================================================
# STEP 4: LABEL
# =============================================================================


@router.post(
    "/label",
    response_model=WPProgressResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def label_posts(
    body: WPLabelRequest,
    background_tasks: BackgroundTasks,
) -> WPProgressResponse:
    """Generate taxonomy and assign labels (background task)."""
    job_id = str(uuid4())

    async def _run_label() -> None:
        async with db_manager.session_factory() as db:
            await step4_label(db=db, project_id=body.project_id, job_id=job_id)

    background_tasks.add_task(_run_label)

    return WPProgressResponse(
        job_id=job_id,
        step="label",
        step_label="Starting blog labeling",
        status="running",
        current=0,
        total=3,
    )


@router.get("/labels/{project_id}", response_model=WPLabelReviewResponse)
async def get_labels(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> WPLabelReviewResponse:
    """Get taxonomy and label assignments for review."""
    from sqlalchemy import select

    from app.models.crawled_page import CrawledPage
    from app.models.project import Project

    # Load project taxonomy
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    taxonomy_data = project.phase_status.get("wordpress", {}).get("taxonomy", {})
    taxonomy_labels_raw = taxonomy_data.get("labels", [])

    # Load pages with their labels
    stmt = select(CrawledPage).where(
        CrawledPage.project_id == project_id,
        CrawledPage.source == "wordpress",
    )
    result = await db.execute(stmt)
    pages = list(result.scalars().all())

    # Count posts per label
    label_counts: dict[str, int] = {}
    for page in pages:
        if page.labels:
            for label in page.labels:
                label_counts[label] = label_counts.get(label, 0) + 1

    # Build taxonomy response
    taxonomy = [
        WPTaxonomyLabel(
            name=l.get("name", ""),
            description=l.get("description", ""),
            post_count=label_counts.get(l.get("name", ""), 0),
        )
        for l in taxonomy_labels_raw
    ]

    # Build assignments
    assignments = [
        WPLabelAssignment(
            page_id=page.id,
            title=page.title or "",
            url=page.normalized_url,
            labels=page.labels or [],
            primary_label=page.labels[0] if page.labels else "",
        )
        for page in pages
    ]

    # Count unique primary labels
    primary_labels = {page.labels[0] for page in pages if page.labels}

    return WPLabelReviewResponse(
        taxonomy=taxonomy,
        assignments=assignments,
        total_groups=len(primary_labels),
    )


# =============================================================================
# STEP 5: PLAN
# =============================================================================


@router.post(
    "/plan",
    response_model=WPProgressResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def plan_links(
    body: WPPlanRequest,
    background_tasks: BackgroundTasks,
) -> WPProgressResponse:
    """Plan internal links per silo (background task)."""
    job_id = str(uuid4())

    async def _run_plan() -> None:
        async with db_manager.session_factory() as db:
            await step5_plan_links(db=db, project_id=body.project_id, job_id=job_id)

    background_tasks.add_task(_run_plan)

    return WPProgressResponse(
        job_id=job_id,
        step="plan",
        step_label="Starting link planning",
        status="running",
        current=0,
        total=0,
    )


# =============================================================================
# STEP 6: REVIEW
# =============================================================================


@router.get("/review/{project_id}", response_model=WPReviewResponse)
async def get_review(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> WPReviewResponse:
    """Get link review stats grouped by silo."""
    review_data = await step6_get_review(db, project_id)

    return WPReviewResponse(
        total_posts=review_data["total_posts"],
        total_links=review_data["total_links"],
        avg_links_per_post=review_data["avg_links_per_post"],
        groups=[
            WPReviewGroup(**g) for g in review_data["groups"]
        ],
        validation_pass_rate=review_data["validation_pass_rate"],
    )


# =============================================================================
# STEP 7: EXPORT
# =============================================================================


@router.post(
    "/export",
    response_model=WPProgressResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def export_posts(
    body: WPExportRequest,
    background_tasks: BackgroundTasks,
) -> WPProgressResponse:
    """Push modified content back to WordPress (background task)."""
    job_id = str(uuid4())

    async def _run_export() -> None:
        async with db_manager.session_factory() as db:
            await step7_export(
                db=db,
                project_id=body.project_id,
                site_url=body.site_url,
                username=body.username,
                app_password=body.app_password,
                job_id=job_id,
                title_filter=body.title_filter,
            )

    background_tasks.add_task(_run_export)

    return WPProgressResponse(
        job_id=job_id,
        step="export",
        step_label="Starting WordPress export",
        status="running",
        current=0,
        total=0,
    )
