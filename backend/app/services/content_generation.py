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
import json
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
from app.models.prompt_log import PromptLog
from app.services.content_quality import run_quality_checks
from app.services.content_writing import extract_competitor_brands, generate_content
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
    refresh_briefs: bool = False,
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
        refresh_briefs: If True, also re-fetch POP briefs (costs API credits).
            Only used when force_refresh is True.

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

    # Reset all page statuses to pending upfront when force-refreshing,
    # so the frontend immediately sees the pipeline indicators reset.
    if force_refresh:
        async with db_manager.session_factory() as reset_db:
            page_ids = [pd["page_id"] for pd in pages_data]
            reset_stmt = (
                select(PageContent).where(
                    PageContent.crawled_page_id.in_(page_ids)
                )
            )
            reset_result = await reset_db.execute(reset_stmt)
            for pc in reset_result.scalars().all():
                pc.status = ContentStatus.PENDING.value
                pc.generation_started_at = None
                pc.generation_completed_at = None
            await reset_db.commit()
            logger.info(
                "Reset page statuses to pending for regeneration",
                extra={"project_id": project_id, "pages_reset": len(page_ids)},
            )

    # --- Phase 1: Pre-fetch all POP briefs concurrently ---
    # POP briefs involve async polling loops that are mostly I/O wait.
    # Fetching all briefs upfront in parallel (ungated) eliminates the
    # per-page serial bottleneck where brief → write was sequential.
    await _prefetch_all_briefs(
        pages_data=pages_data,
        force_refresh=force_refresh,
        refresh_briefs=refresh_briefs,
    )

    # --- Phase 2: Write content + quality checks (briefs are now cached) ---
    semaphore = asyncio.Semaphore(concurrency)

    async def _process_with_semaphore(
        page_data: dict[str, Any],
    ) -> PipelinePageResult:
        async with semaphore:
            return await _process_single_page(
                page_data=page_data,
                brand_config=brand_config,
                force_refresh=force_refresh,
                refresh_briefs=False,  # Briefs already fetched in Phase 1
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


async def _prefetch_all_briefs(
    pages_data: list[dict[str, Any]],
    force_refresh: bool,
    refresh_briefs: bool,
) -> None:
    """Phase 1: Pre-fetch POP content briefs for all pages concurrently.

    POP briefs involve async polling loops (2s intervals) that are mostly I/O
    wait. Running all brief fetches in parallel — instead of gated behind the
    per-page content-writing semaphore — dramatically reduces wall-clock time.

    Brief results are stored in the database by fetch_content_brief and will be
    returned from cache when _process_single_page runs in Phase 2.
    """
    # Skip pages that will be skipped in Phase 2 (already complete)
    pages_needing_briefs = [
        pd
        for pd in pages_data
        if force_refresh
        or pd["existing_content_status"] != ContentStatus.COMPLETE.value
    ]

    if not pages_needing_briefs:
        logger.info("Phase 1: All pages already complete, skipping brief pre-fetch")
        return

    logger.info(
        "Phase 1: Pre-fetching POP briefs concurrently",
        extra={"page_count": len(pages_needing_briefs)},
    )

    # Batch-set all pages to GENERATING_BRIEF and commit so the frontend
    # polling endpoint can see the status immediately.
    async with db_manager.session_factory() as status_db:
        page_ids = [pd["page_id"] for pd in pages_needing_briefs]
        stmt = select(PageContent).where(
            PageContent.crawled_page_id.in_(page_ids)
        )
        result = await status_db.execute(stmt)
        existing = {pc.crawled_page_id: pc for pc in result.scalars().all()}

        for pd in pages_needing_briefs:
            pid = pd["page_id"]
            if pid in existing:
                existing[pid].status = ContentStatus.GENERATING_BRIEF.value
            else:
                status_db.add(
                    PageContent(
                        crawled_page_id=pid,
                        status=ContentStatus.GENERATING_BRIEF.value,
                    )
                )
        await status_db.commit()

    async def _fetch_one_brief(page_data: dict[str, Any]) -> None:
        page_id = page_data["page_id"]
        keyword = page_data["keyword"]
        url = page_data["url"]

        try:
            async with db_manager.session_factory() as db:
                stmt = select(CrawledPage).where(CrawledPage.id == page_id)
                result = await db.execute(stmt)
                crawled_page = result.scalar_one_or_none()

                if crawled_page is None:
                    return

                await fetch_content_brief(
                    db=db,
                    crawled_page=crawled_page,
                    keyword=keyword,
                    target_url=url,
                    force_refresh=refresh_briefs,
                )
        except Exception as exc:
            # Non-fatal: _process_single_page will retry in Phase 2
            logger.warning(
                "Brief pre-fetch failed (will retry in pipeline)",
                extra={"page_id": page_id, "error": str(exc)},
            )

    brief_tasks = [_fetch_one_brief(pd) for pd in pages_needing_briefs]
    await asyncio.gather(*brief_tasks)

    logger.info(
        "Phase 1: Brief pre-fetch complete",
        extra={"page_count": len(pages_needing_briefs)},
    )


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
    refresh_briefs: bool = False,
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
            await db.commit()

            # By default, use cached POP brief — force_refresh only controls
            # whether we re-run the Claude writing step. Re-fetching from POP
            # (which costs API credits) requires explicit refresh_briefs=True.
            brief_result = await fetch_content_brief(
                db=db,
                crawled_page=crawled_page,
                keyword=keyword,
                target_url=url,
                force_refresh=refresh_briefs,
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

            # Log the POP brief result to prompt_logs so it's visible in the inspector
            await _log_content_brief(
                db, page_content, keyword, content_brief, brief_result
            )

            # Auto-enrich vocabulary.competitors from POP competitor URLs
            if content_brief and content_brief.competitors:
                brand_config = await _enrich_competitors_from_pop(
                    db, brand_config, content_brief.competitors, crawled_page.project_id
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
            await db.commit()

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


async def _log_content_brief(
    db: AsyncSession,
    page_content: PageContent,
    keyword: str,
    content_brief: Any,
    brief_result: Any,
) -> None:
    """Create a PromptLog entry for the POP content brief step.

    Logs the keyword request as prompt_text and the POP API response (or error)
    as response_text so it's visible in the Prompt Inspector.
    """
    prompt_text = f"POP content brief (get-terms + create-report + recommendations) for keyword: {keyword}"

    if brief_result.success and content_brief is not None:
        # Show a readable summary of all POP response data
        raw = content_brief.raw_response or {}
        summary_parts: list[str] = []

        # LSI Terms
        lsi_terms = content_brief.lsi_terms or []
        if lsi_terms:
            summary_parts.append(f"LSI Terms ({len(lsi_terms)}):")
            for term in lsi_terms[:20]:  # Cap at 20 for readability
                phrase = term.get("phrase", "")
                weight = term.get("weight", 0)
                avg_count = term.get("averageCount", 0)
                summary_parts.append(f"  - {phrase} (weight: {weight}, target: {avg_count})")

        # Keyword Variations
        variations = content_brief.related_searches or []
        if variations:
            summary_parts.append(f"\nKeyword Variations ({len(variations)}):")
            for v in variations:
                summary_parts.append(f"  - {v}")

        # Competitors
        competitors = content_brief.competitors or []
        if competitors:
            summary_parts.append(f"\nCompetitors ({len(competitors)}):")
            for comp in competitors:
                url = comp.get("url", "")
                score = comp.get("pageScore") or 0
                wc = comp.get("wordCount") or 0
                summary_parts.append(f"  - {url} (score: {score}, words: {wc})")

        # Related Questions
        related_questions = content_brief.related_questions or []
        if related_questions:
            summary_parts.append(f"\nRelated Questions ({len(related_questions)}):")
            for q in related_questions:
                summary_parts.append(f"  - {q}")

        # Heading Structure Targets
        heading_targets = content_brief.heading_targets or []
        if heading_targets:
            summary_parts.append(f"\nHeading Structure Targets ({len(heading_targets)}):")
            for h in heading_targets:
                tag = h.get("tag", "")
                target = h.get("target", 0)
                summary_parts.append(f"  - {tag}: {target}")

        # Keyword Placement Targets
        keyword_targets = content_brief.keyword_targets or []
        if keyword_targets:
            summary_parts.append(f"\nKeyword Placement Targets ({len(keyword_targets)}):")
            for kt in keyword_targets:
                signal = kt.get("signal", "")
                kt_type = kt.get("type", "")
                target = kt.get("target", 0)
                phrase = kt.get("phrase", kt.get("comment", ""))
                label = f"{signal} ({kt_type}): target={target}"
                if phrase:
                    label += f" [{phrase}]"
                summary_parts.append(f"  - {label}")

        # Page Score Target
        page_score = content_brief.page_score_target
        if page_score is not None:
            summary_parts.append(f"\nPage Score Target: {page_score}")

        # Word Count Range
        wc_target = content_brief.word_count_target
        wc_min = content_brief.word_count_min
        wc_max = content_brief.word_count_max
        if wc_min and wc_max:
            wc_str = f"min={wc_min}, avg={wc_target or 'N/A'}, max={wc_max}"
        elif wc_target:
            wc_str = str(wc_target)
        else:
            wc_str = "N/A"
        summary_parts.append(f"\nWord Count Range: {wc_str}")

        response_text = "\n".join(summary_parts) if summary_parts else json.dumps(raw, indent=2)
    else:
        response_text = f"POP brief fetch failed: {brief_result.error or 'unknown error'}"

    log = PromptLog(
        page_content_id=page_content.id,
        step="content_brief",
        role="system",
        prompt_text=prompt_text,
        response_text=response_text,
    )
    db.add(log)
    await db.flush()


async def _enrich_competitors_from_pop(
    db: AsyncSession,
    brand_config: dict[str, Any],
    competitors: list[dict[str, Any]],
    project_id: str,
) -> dict[str, Any]:
    """Auto-enrich vocabulary.competitors from POP competitor URLs.

    Extracts brand names from competitor domains, merges them into the
    brand_config's vocabulary.competitors list (case-insensitive dedup),
    and persists changes back to the database if any new names were added.

    Returns the (potentially updated) brand_config dict for use in the
    current pipeline run.
    """
    new_brands = extract_competitor_brands(competitors)
    if not new_brands:
        return brand_config

    # Ensure vocabulary exists
    vocabulary = brand_config.get("vocabulary")
    if not isinstance(vocabulary, dict):
        vocabulary = {}
        brand_config["vocabulary"] = vocabulary

    existing: list[str] = vocabulary.get("competitors", []) or []
    existing_lower = {name.lower() for name in existing}

    added: list[str] = []
    for name in new_brands:
        if name.lower() not in existing_lower:
            existing.append(name)
            existing_lower.add(name.lower())
            added.append(name)

    if not added:
        return brand_config

    vocabulary["competitors"] = existing

    # Persist to database
    try:
        stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
        result = await db.execute(stmt)
        config_record = result.scalar_one_or_none()

        if config_record and config_record.v2_schema:
            updated_schema = dict(config_record.v2_schema)
            vocab = updated_schema.get("vocabulary")
            if not isinstance(vocab, dict):
                vocab = {}
                updated_schema["vocabulary"] = vocab
            vocab["competitors"] = existing
            config_record.v2_schema = updated_schema

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(config_record, "v2_schema")
            await db.flush()

            logger.info(
                "Enriched vocabulary.competitors from POP URLs",
                extra={
                    "project_id": project_id,
                    "added": added,
                    "total": len(existing),
                },
            )
    except Exception:
        logger.warning(
            "Failed to persist POP competitor enrichment",
            extra={"project_id": project_id},
            exc_info=True,
        )

    return brand_config
