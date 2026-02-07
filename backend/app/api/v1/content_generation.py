"""Content generation API router.

REST endpoints for triggering content generation, polling progress,
retrieving generated content, and fetching prompt logs.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.crawled_page import CrawledPage
from app.models.page_content import ContentStatus, PageContent
from app.models.page_keywords import PageKeywords
from app.models.prompt_log import PromptLog
from app.schemas.content_generation import (
    BriefSummary,
    ContentGenerationStatus,
    ContentGenerationTriggerResponse,
    PageContentResponse,
    PageGenerationStatusItem,
    PromptLogResponse,
)
from app.services.project import ProjectService

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["Content Generation"])

# Module-level set to track projects with active generation tasks.
# This is sufficient for single-process deployments. For multi-process,
# a shared store (Redis, DB flag) would be needed.
_active_generations: set[str] = set()


@router.post(
    "/{project_id}/generate-content",
    response_model=ContentGenerationTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_content(
    project_id: str,
    background_tasks: BackgroundTasks,
    force_refresh: bool = False,
    refresh_briefs: bool = False,
    db: AsyncSession = Depends(get_session),
) -> ContentGenerationTriggerResponse:
    """Trigger content generation for all pages with approved keywords.

    Starts a background task that processes each approved page through
    the brief -> write -> check pipeline.

    Args:
        force_refresh: If True, regenerate content even for completed pages.
        refresh_briefs: If True, also re-fetch POP briefs (costs API credits).
            Only used when force_refresh is True.

    Returns 400 if no approved keywords exist.
    Returns 409 if generation is already in progress for this project.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Check for duplicate runs
    if project_id in _active_generations:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Content generation is already in progress for this project",
        )

    # Check for approved keywords
    approved_count_stmt = (
        select(func.count())
        .select_from(PageKeywords)
        .join(CrawledPage, PageKeywords.crawled_page_id == CrawledPage.id)
        .where(
            CrawledPage.project_id == project_id,
            PageKeywords.is_approved.is_(True),
        )
    )
    result = await db.execute(approved_count_stmt)
    approved_count = result.scalar_one()

    if approved_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved keywords found. Approve keywords before generating content.",
        )

    # Mark as active and start background task
    _active_generations.add(project_id)

    background_tasks.add_task(
        _run_generation_background,
        project_id=project_id,
        force_refresh=force_refresh,
        refresh_briefs=refresh_briefs,
    )

    logger.info(
        "Content generation triggered",
        extra={
            "project_id": project_id,
            "approved_pages": approved_count,
        },
    )

    return ContentGenerationTriggerResponse(
        status="accepted",
        message=f"Content generation started for {approved_count} pages with approved keywords",
    )


async def _run_generation_background(
    project_id: str,
    force_refresh: bool = False,
    refresh_briefs: bool = False,
) -> None:
    """Background task wrapper for the content generation pipeline.

    Runs the pipeline and cleans up the active generation tracking.
    """
    from app.services.content_generation import run_content_pipeline

    try:
        result = await run_content_pipeline(
            project_id,
            force_refresh=force_refresh,
            refresh_briefs=refresh_briefs,
        )
        logger.info(
            "Content generation pipeline finished",
            extra={
                "project_id": project_id,
                "succeeded": result.succeeded,
                "failed": result.failed,
                "skipped": result.skipped,
            },
        )
    except Exception as e:
        logger.error(
            "Content generation pipeline failed",
            extra={
                "project_id": project_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
    finally:
        _active_generations.discard(project_id)


@router.get(
    "/{project_id}/content-generation-status",
    response_model=ContentGenerationStatus,
)
async def get_content_generation_status(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> ContentGenerationStatus:
    """Get content generation status for a project.

    Returns overall status, progress counts, and per-page status array.
    Designed to be polled by the frontend during generation.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Get all approved-keyword pages with their content status
    stmt = (
        select(CrawledPage)
        .join(PageKeywords, PageKeywords.crawled_page_id == CrawledPage.id)
        .where(
            CrawledPage.project_id == project_id,
            PageKeywords.is_approved.is_(True),
        )
        .options(
            selectinload(CrawledPage.keywords),
            selectinload(CrawledPage.page_content),
        )
    )
    result = await db.execute(stmt)
    pages = result.scalars().unique().all()

    # Build per-page status items
    page_items: list[PageGenerationStatusItem] = []
    pages_completed = 0
    pages_failed = 0

    for page in pages:
        keyword = page.keywords.primary_keyword if page.keywords else ""
        page_status = "pending"
        error = None

        if page.page_content:
            page_status = page.page_content.status
            if page_status == ContentStatus.FAILED.value:
                pages_failed += 1
                qa = page.page_content.qa_results
                if qa and "error" in qa:
                    error = qa["error"]
            elif page_status == ContentStatus.COMPLETE.value:
                pages_completed += 1

        page_items.append(
            PageGenerationStatusItem(
                page_id=page.id,
                url=page.normalized_url,
                keyword=keyword,
                status=page_status,
                error=error,
            )
        )

    # Determine overall status
    pages_total = len(pages)
    if pages_total == 0:
        overall_status = "idle"
    elif project_id in _active_generations:
        overall_status = "generating"
    elif pages_completed + pages_failed >= pages_total:
        overall_status = "complete" if pages_failed == 0 else "failed"
    else:
        # Has some content but generation not active — partial/idle
        has_any_content = any(p.page_content is not None for p in pages)
        overall_status = "idle" if not has_any_content else "complete"

    return ContentGenerationStatus(
        overall_status=overall_status,
        pages_total=pages_total,
        pages_completed=pages_completed,
        pages_failed=pages_failed,
        pages=page_items,
    )


@router.get(
    "/{project_id}/pages/{page_id}/content",
    response_model=PageContentResponse,
)
async def get_page_content(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
) -> PageContentResponse:
    """Get generated content for a specific page.

    Returns the PageContent fields including brief summary and QA results.
    Returns 404 if content has not been generated yet.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Get page with content and brief
    stmt = (
        select(CrawledPage)
        .where(
            CrawledPage.id == page_id,
            CrawledPage.project_id == project_id,
        )
        .options(
            selectinload(CrawledPage.page_content),
            selectinload(CrawledPage.content_brief),
        )
    )
    result = await db.execute(stmt)
    page = result.scalar_one_or_none()

    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found in project {project_id}",
        )

    if not page.page_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content has not been generated yet for this page",
        )

    # Build brief summary if content brief exists
    brief_summary = None
    if page.content_brief:
        brief = page.content_brief
        lsi_terms = brief.lsi_terms or []
        competitors = brief.competitors or []
        related_questions = brief.related_questions or []

        # Build word count range string
        word_count_range = None
        if brief.word_count_min and brief.word_count_max:
            word_count_range = f"{brief.word_count_min}-{brief.word_count_max}"

        brief_summary = BriefSummary(
            keyword=brief.keyword,
            lsi_terms_count=len(lsi_terms),
            competitors_count=len(competitors),
            related_questions_count=len(related_questions),
            page_score_target=brief.page_score_target,
            word_count_range=word_count_range,
        )

    content = page.page_content
    return PageContentResponse(
        page_title=content.page_title,
        meta_description=content.meta_description,
        top_description=content.top_description,
        bottom_description=content.bottom_description,
        word_count=content.word_count,
        status=content.status,
        qa_results=content.qa_results,
        brief_summary=brief_summary,
        generation_started_at=content.generation_started_at,
        generation_completed_at=content.generation_completed_at,
    )


@router.get(
    "/{project_id}/pages/{page_id}/prompts",
    response_model=list[PromptLogResponse],
)
async def get_page_prompts(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
) -> list[PromptLogResponse]:
    """Get all prompt logs for a specific page.

    Returns PromptLog records ordered by created_at.
    Returns an empty array if no prompts exist.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Verify page belongs to project
    page_stmt = select(CrawledPage.id).where(
        CrawledPage.id == page_id,
        CrawledPage.project_id == project_id,
    )
    page_result = await db.execute(page_stmt)
    if not page_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found in project {project_id}",
        )

    # Get PageContent for this page (needed to find prompt logs)
    content_stmt = select(PageContent.id).where(
        PageContent.crawled_page_id == page_id,
    )
    content_result = await db.execute(content_stmt)
    page_content_id = content_result.scalar_one_or_none()

    if not page_content_id:
        return []

    # Get prompt logs ordered by created_at
    logs_stmt = (
        select(PromptLog)
        .where(PromptLog.page_content_id == page_content_id)
        .order_by(PromptLog.created_at)
    )
    logs_result = await db.execute(logs_stmt)
    logs = logs_result.scalars().all()

    return [PromptLogResponse.model_validate(log) for log in logs]
