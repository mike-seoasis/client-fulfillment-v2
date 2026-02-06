"""Content generation pipeline orchestrator.

Orchestrates the brief → write → check pipeline for each approved page with
concurrency control. Designed to be called from a FastAPI BackgroundTask.

Pipeline per page:
1. Update status to generating_brief → fetch POP brief
2. Update status to writing → call Claude content writing
3. Update status to checking → run quality checks
4. Update status to complete

Error isolation: if one page fails, others continue. Failed pages get
status='failed' with error details in qa_results.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import db_manager
from app.core.logging import get_logger
from app.models.brand_config import BrandConfig
from app.models.crawled_page import CrawledPage
from app.models.page_content import ContentStatus, PageContent
from app.models.page_keywords import PageKeywords
from app.services.content_quality import run_quality_checks
from app.services.content_writing import generate_content
from app.services.pop_content_brief import fetch_content_brief

logger = get_logger(__name__)


@dataclass
class PipelinePageResult:
    """Result of processing a single page through the pipeline."""

    page_id: str
    url: str
    success: bool
    error: str | None = None
    skipped: bool = False


@dataclass
class PipelineResult:
    """Result of running the content generation pipeline for a project."""

    project_id: str
    total_pages: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    page_results: list[PipelinePageResult] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""


async def run_content_pipeline(
    project_id: str,
    force_refresh: bool = False,
) -> PipelineResult:
    """Run the content generation pipeline for all approved pages in a project.

    Processes each page through: brief → write → check. Uses asyncio.Semaphore
    for concurrency control (CONTENT_GENERATION_CONCURRENCY env var, default 1).

    Designed to be called from a FastAPI BackgroundTask — creates its own
    database sessions per-page for isolation.

    Args:
        project_id: UUID of the project to generate content for.
        force_refresh: If True, regenerate content even for pages with
            status='complete'.

    Returns:
        PipelineResult with per-page results and aggregate counts.
    """
    settings = get_settings()
    concurrency = settings.content_generation_concurrency

    result = PipelineResult(
        project_id=project_id,
        started_at=datetime.now(UTC).isoformat(),
    )

    logger.info(
        "Starting content generation pipeline",
        extra={
            "project_id": project_id,
            "concurrency": concurrency,
            "force_refresh": force_refresh,
        },
    )

    # Load approved pages and brand config in a read-only session
    async with db_manager.session_factory() as session:
        pages_data = await _load_approved_pages(session, project_id)
        brand_config = await _load_brand_config(session, project_id)

    if not pages_data:
        logger.info(
            "No approved pages found for content generation",
            extra={"project_id": project_id},
        )
        result.completed_at = datetime.now(UTC).isoformat()
        return result

    result.total_pages = len(pages_data)

    logger.info(
        "Found approved pages for content generation",
        extra={
            "project_id": project_id,
            "total_pages": result.total_pages,
        },
    )

    # Process pages with concurrency control
    semaphore = asyncio.Semaphore(concurrency)

    async def _process_with_semaphore(
        page_data: dict[str, Any],
    ) -> PipelinePageResult:
        async with semaphore:
            return await _process_single_page(
                page_data=page_data,
                brand_config=brand_config,
                force_refresh=force_refresh,
            )

    tasks = [_process_with_semaphore(pd) for pd in pages_data]
    page_results = await asyncio.gather(*tasks)

    # Aggregate results
    for pr in page_results:
        result.page_results.append(pr)
        if pr.skipped:
            result.skipped += 1
        elif pr.success:
            result.succeeded += 1
        else:
            result.failed += 1

    result.completed_at = datetime.now(UTC).isoformat()

    logger.info(
        "Content generation pipeline complete",
        extra={
            "project_id": project_id,
            "total": result.total_pages,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "skipped": result.skipped,
        },
    )

    return result


async def _load_approved_pages(
    db: AsyncSession,
    project_id: str,
) -> list[dict[str, Any]]:
    """Load all approved-keyword pages for a project.

    Returns lightweight dicts with page_id, url, and keyword so we can
    process each page in its own session without holding the read session open.
    """
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
    pages = result.scalars().all()

    pages_data: list[dict[str, Any]] = []
    for page in pages:
        keyword = page.keywords.primary_keyword if page.keywords else None
        if not keyword:
            continue

        # Track existing content status for skip logic
        existing_status = None
        if page.page_content:
            existing_status = page.page_content.status

        pages_data.append(
            {
                "page_id": page.id,
                "url": page.normalized_url,
                "keyword": keyword,
                "existing_content_status": existing_status,
            }
        )

    return pages_data


async def _load_brand_config(
    db: AsyncSession,
    project_id: str,
) -> dict[str, Any]:
    """Load brand config v2_schema for a project.

    Returns empty dict if no brand config exists (services degrade gracefully).
    """
    stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config is None:
        logger.warning(
            "No brand config found for project",
            extra={"project_id": project_id},
        )
        return {}

    return config.v2_schema or {}


async def _process_single_page(
    page_data: dict[str, Any],
    brand_config: dict[str, Any],
    force_refresh: bool,
) -> PipelinePageResult:
    """Process a single page through the brief → write → check pipeline.

    Creates its own database session for error isolation — if this page fails,
    the session is rolled back without affecting other pages.
    """
    page_id: str = page_data["page_id"]
    url: str = page_data["url"]
    keyword: str = page_data["keyword"]
    existing_status: str | None = page_data["existing_content_status"]

    # Skip pages that already have complete content (unless force_refresh)
    if not force_refresh and existing_status == ContentStatus.COMPLETE.value:
        logger.info(
            "Skipping page with complete content",
            extra={"page_id": page_id, "url": url},
        )
        return PipelinePageResult(
            page_id=page_id,
            url=url,
            success=True,
            skipped=True,
        )

    logger.info(
        "Processing page through content pipeline",
        extra={"page_id": page_id, "url": url, "keyword": keyword[:50]},
    )

    try:
        async with db_manager.session_factory() as db:
            # Re-load the CrawledPage in this session with relationships
            stmt = (
                select(CrawledPage)
                .where(CrawledPage.id == page_id)
                .options(
                    selectinload(CrawledPage.page_content),
                    selectinload(CrawledPage.content_brief),
                )
            )
            result = await db.execute(stmt)
            crawled_page = result.scalar_one_or_none()

            if crawled_page is None:
                return PipelinePageResult(
                    page_id=page_id,
                    url=url,
                    success=False,
                    error="CrawledPage not found",
                )

            # --- Step 1: Fetch POP brief ---
            page_content = await _ensure_page_content(db, crawled_page)
            page_content.status = ContentStatus.GENERATING_BRIEF.value
            page_content.generation_started_at = datetime.now(UTC)
            await db.flush()

            brief_result = await fetch_content_brief(
                db=db,
                crawled_page=crawled_page,
                keyword=keyword,
                target_url=url,
                force_refresh=force_refresh,
            )

            content_brief = brief_result.content_brief
            if not brief_result.success:
                logger.warning(
                    "Content brief fetch failed, continuing without brief",
                    extra={
                        "page_id": page_id,
                        "error": brief_result.error,
                    },
                )

            # --- Step 2: Write content ---
            # generate_content sets status to WRITING internally
            writing_result = await generate_content(
                db=db,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword=keyword,
            )

            if not writing_result.success:
                # generate_content already marks PageContent as failed
                await db.commit()
                return PipelinePageResult(
                    page_id=page_id,
                    url=url,
                    success=False,
                    error=writing_result.error,
                )

            # --- Step 3: Run quality checks ---
            written_content = writing_result.page_content
            if written_content is None:
                await db.commit()
                return PipelinePageResult(
                    page_id=page_id,
                    url=url,
                    success=False,
                    error="No PageContent after writing",
                )

            written_content.status = ContentStatus.CHECKING.value
            await db.flush()

            run_quality_checks(written_content, brand_config)

            # --- Step 4: Mark complete ---
            written_content.status = ContentStatus.COMPLETE.value
            written_content.generation_completed_at = datetime.now(UTC)
            await db.commit()

            logger.info(
                "Page content generation complete",
                extra={
                    "page_id": page_id,
                    "url": url,
                    "word_count": written_content.word_count,
                    "qa_passed": (written_content.qa_results or {}).get("passed"),
                },
            )

            return PipelinePageResult(
                page_id=page_id,
                url=url,
                success=True,
            )

    except Exception as exc:
        logger.error(
            "Content pipeline failed for page",
            extra={
                "page_id": page_id,
                "url": url,
                "error": str(exc),
            },
            exc_info=True,
        )

        # Mark as failed in a new session (previous may be broken)
        try:
            async with db_manager.session_factory() as err_db:
                err_stmt = select(PageContent).where(
                    PageContent.crawled_page_id == page_id
                )
                err_result = await err_db.execute(err_stmt)
                pc = err_result.scalar_one_or_none()
                if pc is not None:
                    pc.status = ContentStatus.FAILED.value
                    pc.generation_completed_at = datetime.now(UTC)
                    pc.qa_results = {"error": str(exc)}
                    await err_db.commit()
        except Exception:
            logger.error(
                "Failed to mark page as failed after pipeline error",
                extra={"page_id": page_id},
                exc_info=True,
            )

        return PipelinePageResult(
            page_id=page_id,
            url=url,
            success=False,
            error=str(exc),
        )


async def _ensure_page_content(
    db: AsyncSession,
    crawled_page: CrawledPage,
) -> PageContent:
    """Get or create PageContent record for a CrawledPage."""
    if crawled_page.page_content is not None:
        return crawled_page.page_content

    page_content = PageContent(crawled_page_id=crawled_page.id)
    db.add(page_content)
    await db.flush()
    # Attach to relationship so subsequent code can access it
    crawled_page.page_content = page_content
    return page_content
