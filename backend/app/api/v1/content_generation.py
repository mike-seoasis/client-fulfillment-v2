"""Content generation API router.

REST endpoints for triggering content generation, polling progress,
retrieving generated content, editing content, approving content,
and fetching prompt logs.
"""

import re
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.brand_config import BrandConfig
from app.models.crawled_page import CrawledPage
from app.models.page_content import ContentStatus, PageContent
from app.models.page_keywords import PageKeywords
from app.models.prompt_log import PromptLog
from app.schemas.content_generation import (
    BriefSummary,
    BulkApproveResponse,
    ContentBriefData,
    ContentGenerationStatus,
    ContentGenerationTriggerResponse,
    ContentUpdateRequest,
    ExportOutlineResponse,
    OutlineUpdateRequest,
    PageContentResponse,
    PageGenerationStatusItem,
    PromptLogResponse,
)
from app.services.project import ProjectService
from app.services.quality_pipeline import run_quality_pipeline

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
    outline_first: bool = False,
    batch: int | None = Query(None, description="Filter by onboarding batch number"),
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
    if batch is not None:
        approved_count_stmt = approved_count_stmt.where(
            CrawledPage.onboarding_batch == batch
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
        batch=batch,
        outline_first=outline_first,
    )

    logger.info(
        "Content generation triggered",
        extra={
            "project_id": project_id,
            "approved_pages": approved_count,
        },
    )

    mode = "outline generation" if outline_first else "content generation"
    return ContentGenerationTriggerResponse(
        status="accepted",
        message=f"{mode.capitalize()} started for {approved_count} pages with approved keywords",
    )


async def _run_generation_background(
    project_id: str,
    force_refresh: bool = False,
    refresh_briefs: bool = False,
    batch: int | None = None,
    outline_first: bool = False,
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
            batch=batch,
            outline_first=outline_first,
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
    batch: int | None = Query(None, description="Filter by onboarding batch number"),
    db: AsyncSession = Depends(get_session),
) -> ContentGenerationStatus:
    """Get content generation status for a project.

    Returns overall status, progress counts, and per-page status array.
    Designed to be polled by the frontend during generation.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Get all pages with approved keywords and their content status
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
    if batch is not None:
        stmt = stmt.where(CrawledPage.onboarding_batch == batch)
    result = await db.execute(stmt)
    pages = result.scalars().unique().all()

    # Build per-page status items
    page_items: list[PageGenerationStatusItem] = []
    pages_completed = 0
    pages_failed = 0
    pages_approved = 0

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
            if page.page_content.is_approved:
                pages_approved += 1

        # Extract QA status for review list
        qa_passed = None
        qa_issue_count = 0
        page_is_approved = False
        if page.page_content:
            qa = page.page_content.qa_results
            if qa and "passed" in qa:
                qa_passed = qa["passed"]
                qa_issue_count = len(qa.get("issues", []))
            page_is_approved = page.page_content.is_approved

        outline_status = None
        if page.page_content:
            outline_status = page.page_content.outline_status

        page_items.append(
            PageGenerationStatusItem(
                page_id=page.id,
                url=page.normalized_url,
                keyword=keyword,
                source=page.source or "onboarding",
                status=page_status,
                error=error,
                qa_passed=qa_passed,
                qa_issue_count=qa_issue_count,
                is_approved=page_is_approved,
                outline_status=outline_status,
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
        pages_approved=pages_approved,
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

    # Build full brief data for review sidebar
    brief_data = None
    if page.content_brief:
        brief_data = ContentBriefData(
            keyword=page.content_brief.keyword,
            lsi_terms=page.content_brief.lsi_terms or [],
            heading_targets=page.content_brief.heading_targets or [],
            keyword_targets=page.content_brief.keyword_targets or [],
        )

    content = page.page_content
    return PageContentResponse(
        page_title=content.page_title,
        meta_description=content.meta_description,
        top_description=content.top_description,
        bottom_description=content.bottom_description,
        word_count=content.word_count,
        status=content.status,
        outline_json=content.outline_json,
        outline_status=content.outline_status,
        google_doc_url=content.google_doc_url,
        qa_results=content.qa_results,
        brief_summary=brief_summary,
        brief=brief_data,
        generation_started_at=content.generation_started_at,
        generation_completed_at=content.generation_completed_at,
    )


@router.put(
    "/{project_id}/pages/{page_id}/content",
    response_model=PageContentResponse,
)
async def update_page_content(
    project_id: str,
    page_id: str,
    body: ContentUpdateRequest,
    db: AsyncSession = Depends(get_session),
) -> PageContentResponse:
    """Update content fields for a specific page.

    Partial update — only provided fields are changed. Recalculates word_count
    and clears approval status when content changes.
    Returns 404 if no PageContent exists for the page.
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

    content = page.page_content

    # Apply partial updates — only set fields that were provided
    update_data = body.model_dump(exclude_unset=True)
    content_fields = {
        "page_title",
        "meta_description",
        "top_description",
        "bottom_description",
    }
    has_content_change = False
    for field, value in update_data.items():
        if field in content_fields and getattr(content, field) != value:
            has_content_change = True
        setattr(content, field, value)

    # Recalculate word_count from all 4 fields (strip HTML tags, count words)
    total_words = 0
    for field_name in (
        "page_title",
        "meta_description",
        "top_description",
        "bottom_description",
    ):
        value = getattr(content, field_name)
        if value:
            text_only = re.sub(r"<[^>]+>", " ", value)
            total_words += len(text_only.split())
    content.word_count = total_words

    # Clear approval only when content actually changed
    if has_content_change:
        content.is_approved = False
        content.approved_at = None

    await db.commit()
    await db.refresh(content)

    # Build brief summary (same logic as get_page_content)
    brief_summary = None
    if page.content_brief:
        brief = page.content_brief
        lsi_terms = brief.lsi_terms or []
        competitors = brief.competitors or []
        related_questions = brief.related_questions or []

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

    return PageContentResponse(
        page_title=content.page_title,
        meta_description=content.meta_description,
        top_description=content.top_description,
        bottom_description=content.bottom_description,
        word_count=content.word_count,
        status=content.status,
        outline_json=content.outline_json,
        outline_status=content.outline_status,
        google_doc_url=content.google_doc_url,
        is_approved=content.is_approved,
        approved_at=content.approved_at,
        qa_results=content.qa_results,
        brief_summary=brief_summary,
        generation_started_at=content.generation_started_at,
        generation_completed_at=content.generation_completed_at,
    )


@router.post(
    "/{project_id}/pages/{page_id}/approve-content",
    response_model=PageContentResponse,
)
async def approve_content(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
    value: bool = True,
) -> PageContentResponse:
    """Approve or unapprove generated content for a page.

    By default, sets is_approved=true. Pass value=false to unapprove.

    Returns 400 if content status is not 'complete'.
    Returns 404 if page or PageContent not found.
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

    content = page.page_content

    # Set approval state
    content.is_approved = value
    content.approved_at = datetime.now(UTC) if value else None

    await db.commit()
    await db.refresh(content)

    logger.info(
        "Content approval updated",
        extra={
            "project_id": project_id,
            "page_id": page_id,
            "is_approved": value,
        },
    )

    # Build brief summary (same logic as get_page_content)
    brief_summary = None
    if page.content_brief:
        brief = page.content_brief
        lsi_terms = brief.lsi_terms or []
        competitors = brief.competitors or []
        related_questions = brief.related_questions or []

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

    return PageContentResponse(
        page_title=content.page_title,
        meta_description=content.meta_description,
        top_description=content.top_description,
        bottom_description=content.bottom_description,
        word_count=content.word_count,
        status=content.status,
        outline_json=content.outline_json,
        outline_status=content.outline_status,
        google_doc_url=content.google_doc_url,
        is_approved=content.is_approved,
        approved_at=content.approved_at,
        qa_results=content.qa_results,
        brief_summary=brief_summary,
        generation_started_at=content.generation_started_at,
        generation_completed_at=content.generation_completed_at,
    )


@router.post(
    "/{project_id}/bulk-approve-content",
    response_model=BulkApproveResponse,
)
async def bulk_approve_content(
    project_id: str,
    batch: int | None = Query(None, description="Filter by onboarding batch number"),
    db: AsyncSession = Depends(get_session),
) -> BulkApproveResponse:
    """Bulk-approve all eligible content pages for a project.

    Finds all PageContent records where status='complete', qa_results.passed=true,
    and is_approved=False. Sets each to is_approved=True with approved_at=now().

    Returns 200 with approved_count=0 if no pages are eligible.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    now = datetime.now(UTC)

    # Find all eligible PageContent records: complete, QA passed, not yet approved
    stmt = (
        select(PageContent)
        .join(CrawledPage, PageContent.crawled_page_id == CrawledPage.id)
        .where(
            CrawledPage.project_id == project_id,
            PageContent.status == ContentStatus.COMPLETE.value,
            PageContent.qa_results["passed"].as_boolean().is_(True),
            PageContent.is_approved.is_(False),
        )
    )
    if batch is not None:
        stmt = stmt.where(CrawledPage.onboarding_batch == batch)
    result = await db.execute(stmt)
    eligible = result.scalars().all()

    # Approve each
    for content in eligible:
        content.is_approved = True
        content.approved_at = now

    await db.commit()

    approved_count = len(eligible)

    logger.info(
        "Bulk content approval completed",
        extra={
            "project_id": project_id,
            "approved_count": approved_count,
        },
    )

    return BulkApproveResponse(approved_count=approved_count)


@router.post(
    "/{project_id}/pages/{page_id}/recheck-content",
    response_model=PageContentResponse,
)
async def recheck_content(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
) -> PageContentResponse:
    """Re-run AI trope quality checks on current content.

    Loads the project's brand config and re-runs all deterministic quality
    checks against the current content field values. Stores updated results
    in PageContent.qa_results.

    Returns 404 if page or PageContent not found.
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

    # Load brand config v2_schema
    brand_stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
    brand_result = await db.execute(brand_stmt)
    brand_config_row = brand_result.scalar_one_or_none()
    brand_config = brand_config_row.v2_schema if brand_config_row else {}

    # Load and match bibles for this page's keyword
    matched_bibles: list = []
    page_kw = None
    try:
        from app.services.content_generation import (
            _load_project_bibles,
            _match_bibles_for_keyword,
        )

        project_bibles = await _load_project_bibles(db, project_id)
        kw_stmt = select(PageKeywords).where(
            PageKeywords.crawled_page_id == page_id
        )
        kw_result = await db.execute(kw_stmt)
        page_kw = kw_result.scalar_one_or_none()
        if page_kw and page_kw.primary_keyword:
            matched_bibles = _match_bibles_for_keyword(
                project_bibles, page_kw.primary_keyword
            )
    except Exception:
        logger.warning(
            "Bible loading failed during recheck, continuing without bibles",
            extra={"project_id": project_id},
            exc_info=True,
        )

    # Re-run quality checks (mutates content.qa_results)
    content = page.page_content

    # Need keyword for Tier 2 brief adherence
    primary_keyword = ""
    if page_kw and page_kw.primary_keyword:
        primary_keyword = page_kw.primary_keyword

    pipeline_result = await run_quality_pipeline(
        content=content,
        brand_config=brand_config or {},
        primary_keyword=primary_keyword,
        content_brief=page.content_brief,
        matched_bibles=matched_bibles,
    )

    # Apply auto-rewrite results if fixed version was kept
    from app.services.content_generation import _apply_rewrite_results

    _apply_rewrite_results(content, pipeline_result)

    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(content, "qa_results")

    await db.commit()
    await db.refresh(content)

    logger.info(
        "Content quality recheck completed",
        extra={
            "project_id": project_id,
            "page_id": page_id,
            "qa_passed": content.qa_results.get("passed")
            if content.qa_results
            else None,
        },
    )

    # Build brief summary (same logic as get_page_content)
    brief_summary = None
    if page.content_brief:
        brief = page.content_brief
        lsi_terms = brief.lsi_terms or []
        competitors = brief.competitors or []
        related_questions = brief.related_questions or []

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

    return PageContentResponse(
        page_title=content.page_title,
        meta_description=content.meta_description,
        top_description=content.top_description,
        bottom_description=content.bottom_description,
        word_count=content.word_count,
        status=content.status,
        outline_json=content.outline_json,
        outline_status=content.outline_status,
        google_doc_url=content.google_doc_url,
        is_approved=content.is_approved,
        approved_at=content.approved_at,
        qa_results=content.qa_results,
        brief_summary=brief_summary,
        generation_started_at=content.generation_started_at,
        generation_completed_at=content.generation_completed_at,
    )


# Module-level set to track pages with active outline-to-content generation.
_active_outline_generations: set[str] = set()


@router.put(
    "/{project_id}/pages/{page_id}/outline",
    response_model=PageContentResponse,
)
async def update_outline(
    project_id: str,
    page_id: str,
    body: OutlineUpdateRequest,
    db: AsyncSession = Depends(get_session),
) -> PageContentResponse:
    """Save an edited outline for a page.

    Updates outline_json on the PageContent record.
    Returns 404 if page or PageContent not found.
    """
    await ProjectService.get_project(db, project_id)

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

    content = page.page_content
    content.outline_json = body.outline_json

    await db.commit()
    await db.refresh(content)

    logger.info(
        "Outline updated",
        extra={"project_id": project_id, "page_id": page_id},
    )

    return _build_page_content_response(page)


@router.post(
    "/{project_id}/pages/{page_id}/approve-outline",
    response_model=PageContentResponse,
)
async def approve_outline(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
) -> PageContentResponse:
    """Approve the outline for a page (set outline_status='approved').

    Returns 400 if outline_status is not 'draft'.
    Returns 404 if page or PageContent not found.
    """
    await ProjectService.get_project(db, project_id)

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

    content = page.page_content

    if content.outline_status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve outline with status '{content.outline_status}'. Expected 'draft'.",
        )

    content.outline_status = "approved"

    await db.commit()
    await db.refresh(content)

    logger.info(
        "Outline approved",
        extra={"project_id": project_id, "page_id": page_id},
    )

    return _build_page_content_response(page)


@router.post(
    "/{project_id}/pages/{page_id}/revise-outline",
    response_model=PageContentResponse,
)
async def revise_outline(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
) -> PageContentResponse:
    """Reset outline_status to 'draft' so the user can edit and regenerate.

    Requires: page has outline_json AND content has already been generated.
    Returns 400 if no outline exists or content hasn't been generated.
    Returns 404 if page or PageContent not found.
    """
    await ProjectService.get_project(db, project_id)

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

    content = page.page_content

    if not content.outline_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No outline exists for this page",
        )

    content.outline_status = "draft"

    await db.commit()
    await db.refresh(content)

    logger.info(
        "Outline revision started",
        extra={"project_id": project_id, "page_id": page_id},
    )

    return _build_page_content_response(page)


@router.post(
    "/{project_id}/pages/{page_id}/cancel-outline-revision",
    response_model=PageContentResponse,
)
async def cancel_outline_revision(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
) -> PageContentResponse:
    """Cancel an outline revision — reset outline_status back to null.

    Only valid when outline_status is 'draft' or 'approved' AND
    generated content already exists (top/bottom description).
    This lets the user go back to viewing their previously generated content
    without needing to regenerate.
    """
    await ProjectService.get_project(db, project_id)

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

    content = page.page_content

    if not (content.top_description or content.bottom_description):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No generated content exists to return to",
        )

    content.outline_status = None

    await db.commit()
    await db.refresh(content)

    logger.info(
        "Outline revision cancelled — returning to generated content",
        extra={"project_id": project_id, "page_id": page_id},
    )

    return _build_page_content_response(page)


@router.post(
    "/{project_id}/pages/{page_id}/export-outline",
    response_model=ExportOutlineResponse,
)
async def export_outline(
    project_id: str,
    page_id: str,
    force: bool = Query(False, description="Re-export even if a Google Doc already exists"),
    db: AsyncSession = Depends(get_session),
) -> ExportOutlineResponse:
    """Export a page outline to a formatted Google Doc.

    Creates a Google Doc in the shared Drive folder, populates it with
    the formatted outline, shares it (anyone with link), and logs a row
    in the per-project tracking spreadsheet.

    Idempotent: if a Google Doc URL already exists for this page, returns
    the existing URL without re-exporting.

    Returns 400 if no outline_json exists on the page content.
    Returns 404 if page or content not found.
    """
    from app.services.outline_export import export_outline_to_google

    project = await ProjectService.get_project(db, project_id)

    stmt = (
        select(CrawledPage)
        .where(
            CrawledPage.id == page_id,
            CrawledPage.project_id == project_id,
        )
        .options(
            selectinload(CrawledPage.page_content),
            selectinload(CrawledPage.keywords),
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

    content = page.page_content

    if not content.outline_json:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No outline exists for this page. Generate an outline first.",
        )

    # Idempotent: return existing doc if already exported (unless forced)
    if content.google_doc_url and not force:
        return ExportOutlineResponse(google_doc_url=content.google_doc_url)

    keyword = page.keywords.primary_keyword if page.keywords else ""

    export_result = await export_outline_to_google(
        db=db,
        project_name=project.name,
        crawled_page=page,
        page_content=content,
        keyword=keyword,
    )

    if not export_result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=export_result.error or "Failed to export outline to Google Doc",
        )

    return ExportOutlineResponse(google_doc_url=export_result.google_doc_url)  # type: ignore[arg-type]


@router.post(
    "/{project_id}/pages/{page_id}/generate-from-outline",
    response_model=ContentGenerationTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_from_outline(
    project_id: str,
    page_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
) -> ContentGenerationTriggerResponse:
    """Generate content from an approved outline.

    Starts a background task to generate content using the approved outline.
    Returns 400 if outline_status is not 'approved'.
    Returns 409 if generation is already in progress for this page.
    """
    await ProjectService.get_project(db, project_id)

    # Check for duplicate runs
    if page_id in _active_outline_generations:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Content generation from outline is already in progress for this page",
        )

    stmt = (
        select(CrawledPage)
        .where(
            CrawledPage.id == page_id,
            CrawledPage.project_id == project_id,
        )
        .options(selectinload(CrawledPage.page_content))
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

    if page.page_content.outline_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Outline must be approved before generating content. Current status: '{page.page_content.outline_status}'",
        )

    _active_outline_generations.add(page_id)
    _active_generations.add(project_id)

    background_tasks.add_task(
        _run_generate_from_outline_background,
        project_id=project_id,
        page_id=page_id,
    )

    logger.info(
        "Generate-from-outline triggered",
        extra={"project_id": project_id, "page_id": page_id},
    )

    return ContentGenerationTriggerResponse(
        status="accepted",
        message="Content generation from outline started",
    )


async def _run_generate_from_outline_background(
    project_id: str,
    page_id: str,
) -> None:
    """Background task wrapper for generate-from-outline."""
    from app.services.content_generation import run_generate_from_outline

    try:
        result = await run_generate_from_outline(project_id, page_id)
        logger.info(
            "Generate-from-outline background task finished",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "success": result.success,
            },
        )
    except Exception as e:
        logger.error(
            "Generate-from-outline background task failed",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "error": str(e),
            },
            exc_info=True,
        )
    finally:
        _active_outline_generations.discard(page_id)
        _active_generations.discard(project_id)


def _build_page_content_response(page: CrawledPage) -> PageContentResponse:
    """Helper to build PageContentResponse from a CrawledPage with loaded relations."""
    content = page.page_content

    brief_summary = None
    brief_data = None
    if page.content_brief:
        brief = page.content_brief
        lsi_terms = brief.lsi_terms or []
        competitors = brief.competitors or []
        related_questions = brief.related_questions or []

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

        brief_data = ContentBriefData(
            keyword=brief.keyword,
            lsi_terms=lsi_terms,
            heading_targets=brief.heading_targets or [],
            keyword_targets=brief.keyword_targets or [],
        )

    return PageContentResponse(
        page_title=content.page_title,
        meta_description=content.meta_description,
        top_description=content.top_description,
        bottom_description=content.bottom_description,
        word_count=content.word_count,
        status=content.status,
        outline_json=content.outline_json,
        outline_status=content.outline_status,
        google_doc_url=content.google_doc_url,
        is_approved=content.is_approved,
        approved_at=content.approved_at,
        qa_results=content.qa_results,
        brief_summary=brief_summary,
        brief=brief_data,
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
