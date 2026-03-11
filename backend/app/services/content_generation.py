"""Content generation pipeline orchestrator.

Orchestrates the brief → write → check → link pipeline for each approved page
with concurrency control. Designed to be called from a FastAPI BackgroundTask.

Pipeline phases:
Phase 1: Pre-fetch POP content briefs concurrently
Phase 2: Write content + quality checks per page (concurrent with semaphore)
Phase 3: Auto-run link planning to inject/re-inject internal links

Error isolation: if one page fails, others continue. Failed pages get
status='failed' with error details in qa_results. Link planning failures
are non-fatal and logged but don't affect content generation results.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
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
from app.services.content_outline import (
    generate_content_from_outline,
    generate_outline,
)
from app.services.content_writing import extract_competitor_brands, generate_content
from app.services.pop_content_brief import fetch_content_brief
from app.services.quality_pipeline import PipelineResult as QualityPipelineResult
from app.services.quality_pipeline import run_quality_pipeline

logger = get_logger(__name__)


def _apply_rewrite_results(
    content: "PageContent",
    pipeline_result: QualityPipelineResult,
) -> None:
    """Apply auto-rewrite results back to content object if fixed version was kept.

    Updates content fields, recomputes word count, and flags modified attributes
    for SQLAlchemy change detection.
    """
    if not pipeline_result.final_fields:
        return
    if not pipeline_result.rewrite or pipeline_result.rewrite.get("kept_version") != "fixed":
        return

    import re

    from sqlalchemy.orm.attributes import flag_modified

    for field_name, value in pipeline_result.final_fields.items():
        if hasattr(content, field_name):
            setattr(content, field_name, value)
            flag_modified(content, field_name)

    # Recompute word count
    total_words = 0
    for value in pipeline_result.final_fields.values():
        text_only = re.sub(r"<[^>]+>", " ", value)
        total_words += len(text_only.split())
    content.word_count = total_words


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
    batch: int | None = None,
    outline_first: bool = False,
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

    # Load approved pages, brand config, and bibles in a read-only session
    async with db_manager.session_factory() as session:
        pages_data = await _load_approved_pages(session, project_id, batch=batch)
        brand_config = await _load_brand_config(session, project_id)
        project_bibles = await _load_project_bibles(session, project_id)

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
            reset_stmt = select(PageContent).where(
                PageContent.crawled_page_id.in_(page_ids)
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
                outline_first=outline_first,
                project_bibles=project_bibles,
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

    # --- Phase 3: Auto-run link planning to inject/re-inject internal links ---
    # Only run if at least 2 pages have complete content (link planning needs ≥2)
    # Skip link planning in outline_first mode (outlines don't have content yet)
    completed_count = result.succeeded + result.skipped  # skipped = already complete
    if completed_count >= 2 and not outline_first:
        await _auto_link_planning(project_id)

    return result


async def run_generate_from_outline(
    project_id: str,
    page_id: str,
) -> PipelinePageResult:
    """Generate content from an approved outline for a single page.

    Per-page pipeline:
    1. Load page with relationships, brand config
    2. Validate outline_status='approved' and outline_json exists
    3. Call generate_content_from_outline()
    4. Run quality checks
    5. Mark status='complete'
    6. Trigger link planning if >= 2 pages have complete content

    Designed to be called from a FastAPI BackgroundTask.

    Args:
        project_id: UUID of the project.
        page_id: UUID of the crawled page.

    Returns:
        PipelinePageResult with success status.
    """
    logger.info(
        "Starting generate-from-outline pipeline",
        extra={"project_id": project_id, "page_id": page_id},
    )

    try:
        async with db_manager.session_factory() as db:
            # Load page with relationships
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
            crawled_page = result.scalar_one_or_none()

            if crawled_page is None:
                return PipelinePageResult(
                    page_id=page_id,
                    url="",
                    success=False,
                    error="CrawledPage not found",
                )

            page_content = crawled_page.page_content
            if page_content is None:
                return PipelinePageResult(
                    page_id=page_id,
                    url=crawled_page.normalized_url,
                    success=False,
                    error="No PageContent record exists",
                )

            # Validate outline is approved
            if page_content.outline_status != "approved":
                return PipelinePageResult(
                    page_id=page_id,
                    url=crawled_page.normalized_url,
                    success=False,
                    error=f"Outline status is '{page_content.outline_status}', expected 'approved'",
                )

            if not page_content.outline_json:
                return PipelinePageResult(
                    page_id=page_id,
                    url=crawled_page.normalized_url,
                    success=False,
                    error="No outline_json found",
                )

            # Load brand config
            brand_config = await _load_brand_config(db, project_id)

            # Load and match bibles
            project_bibles = await _load_project_bibles(db, project_id)

            # Load keyword
            keyword_stmt = select(PageKeywords).where(
                PageKeywords.crawled_page_id == page_id
            )
            kw_result = await db.execute(keyword_stmt)
            page_keywords = kw_result.scalar_one_or_none()
            keyword = page_keywords.primary_keyword if page_keywords else ""

            matched_bibles = await _match_bibles_for_keyword(project_bibles, keyword)

            # Generate content from outline
            outline_headlines = [
                s.get("headline", "?") for s in (page_content.outline_json or {}).get("section_details", [])
            ]
            logger.info(
                "Generating from outline — headlines being sent to LLM",
                extra={
                    "page_id": page_id,
                    "keyword": keyword,
                    "outline_headlines": outline_headlines,
                    "section_count": len(outline_headlines),
                },
            )
            content_result = await generate_content_from_outline(
                db=db,
                crawled_page=crawled_page,
                content_brief=crawled_page.content_brief,
                brand_config=brand_config,
                keyword=keyword,
                outline_json=page_content.outline_json,
                matched_bibles=matched_bibles,
            )

            if not content_result.success:
                await db.commit()
                return PipelinePageResult(
                    page_id=page_id,
                    url=crawled_page.normalized_url,
                    success=False,
                    error=content_result.error,
                )

            # Run quality checks
            written_content = content_result.page_content
            if written_content is not None:
                written_content.status = ContentStatus.CHECKING.value
                await db.commit()

                pipeline_result = await run_quality_pipeline(
                    content=written_content,
                    brand_config=brand_config,
                    primary_keyword=keyword,
                    content_brief=crawled_page.content_brief,
                    matched_bibles=matched_bibles,
                )

                # Apply auto-rewrite results if fixed version was kept
                _apply_rewrite_results(written_content, pipeline_result)

                # flag_modified needed for in-place JSONB dict mutation
                from sqlalchemy.orm.attributes import flag_modified

                flag_modified(written_content, "qa_results")

                written_content.status = ContentStatus.COMPLETE.value
                written_content.generation_completed_at = datetime.now(UTC)
                # Mark outline as 'used' so the frontend can offer a
                # "Revise Outline" button instead of hiding it completely
                written_content.outline_status = "used"
                await db.commit()

            logger.info(
                "Generate-from-outline complete",
                extra={
                    "page_id": page_id,
                    "word_count": written_content.word_count if written_content else 0,
                },
            )

        # Check if link planning should run — only count pages with actual
        # generated content (not outline-only pages)
        async with db_manager.session_factory() as db2:
            complete_count_stmt = (
                select(func.count())
                .select_from(PageContent)
                .join(CrawledPage, PageContent.crawled_page_id == CrawledPage.id)
                .where(
                    CrawledPage.project_id == project_id,
                    PageContent.status == ContentStatus.COMPLETE.value,
                    PageContent.outline_status.in_([None, "used"]),
                    PageContent.bottom_description.isnot(None),
                )
            )
            count_result = await db2.execute(complete_count_stmt)
            complete_count = count_result.scalar_one() or 0

        if complete_count >= 2:
            await _auto_link_planning(project_id)

        return PipelinePageResult(
            page_id=page_id,
            url=crawled_page.normalized_url,
            success=True,
        )

    except Exception as exc:
        logger.error(
            "Generate-from-outline failed",
            extra={
                "page_id": page_id,
                "error": str(exc),
            },
            exc_info=True,
        )

        # Mark as failed
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
                "Failed to mark page as failed",
                extra={"page_id": page_id},
                exc_info=True,
            )

        return PipelinePageResult(
            page_id=page_id,
            url="",
            success=False,
            error=str(exc),
        )


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
        stmt = select(PageContent).where(PageContent.crawled_page_id.in_(page_ids))
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


async def _auto_link_planning(project_id: str) -> None:
    """Phase 3: Automatically run link planning after content generation.

    Checks if InternalLink records already exist for the project (onboarding
    scope). If they do, runs replan_links (snapshot → strip → delete → re-run).
    If none exist, runs the fresh link planning pipeline.

    Failures are non-fatal — logged but don't affect content generation results.
    """
    from sqlalchemy import func

    from app.models.internal_link import InternalLink
    from app.services.link_planning import replan_links, run_link_planning_pipeline

    logger.info(
        "Phase 3: Starting auto link planning",
        extra={"project_id": project_id},
    )

    try:
        async with db_manager.session_factory() as db:
            # Check for existing onboarding-scope links
            count_stmt = (
                select(func.count())
                .select_from(InternalLink)
                .where(
                    InternalLink.project_id == project_id,
                    InternalLink.scope == "onboarding",
                )
            )
            count_result = await db.execute(count_stmt)
            has_existing = (count_result.scalar_one() or 0) > 0

            if has_existing:
                logger.info(
                    "Phase 3: Existing links found, re-planning",
                    extra={"project_id": project_id},
                )
                await replan_links(project_id, "onboarding", None, db)
            else:
                logger.info(
                    "Phase 3: No existing links, running fresh link planning",
                    extra={"project_id": project_id},
                )
                await run_link_planning_pipeline(project_id, "onboarding", None, db)

        logger.info(
            "Phase 3: Auto link planning complete",
            extra={"project_id": project_id},
        )

    except Exception as e:
        # Non-fatal: content generation already succeeded, links can be
        # planned manually via the UI if auto-planning fails.
        logger.warning(
            "Phase 3: Auto link planning failed (non-fatal)",
            extra={
                "project_id": project_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )


async def _load_approved_pages(
    db: AsyncSession,
    project_id: str,
    batch: int | None = None,
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
    if batch is not None:
        stmt = stmt.where(CrawledPage.onboarding_batch == batch)
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


async def _load_project_bibles(
    db: AsyncSession,
    project_id: str,
) -> list[Any]:
    """Load active vertical bibles for a project, ordered by sort_order.

    Returns empty list if no bibles exist or if the table doesn't exist yet
    (graceful degradation for environments without the migration applied).
    """
    try:
        from app.models.vertical_bible import VerticalBible

        stmt = (
            select(VerticalBible)
            .where(
                VerticalBible.project_id == project_id,
                VerticalBible.is_active.is_(True),
            )
            .order_by(VerticalBible.sort_order)
        )
        result = await db.execute(stmt)
        bibles = list(result.scalars().all())
        logger.info(
            "Loaded vertical bibles for project",
            extra={
                "project_id": project_id,
                "bible_count": len(bibles),
                "bible_names": [b.name for b in bibles],
                "bible_triggers": {
                    b.name: (b.trigger_keywords or []) for b in bibles
                },
                "bible_content_lengths": {
                    b.name: len(b.content_md or "") for b in bibles
                },
            },
        )
        return bibles
    except (ImportError, Exception) as exc:
        from sqlalchemy.exc import OperationalError, ProgrammingError

        if isinstance(exc, (ImportError, OperationalError, ProgrammingError)):
            logger.debug(
                "Could not load vertical bibles (table may not exist)",
                extra={"project_id": project_id},
            )
            return []
        raise


BIBLE_MATCH_MODEL = "claude-haiku-4-5-20251001"


def _match_bibles_substring(
    project_bibles: list[Any],
    keyword: str,
) -> list[Any]:
    """Fast substring matching — used as first pass before LLM fallback."""
    keyword_lower = keyword.lower().strip()
    matched: list[Any] = []

    for bible in project_bibles:
        triggers = getattr(bible, "trigger_keywords", []) or []
        for trigger in triggers:
            trigger_lower = str(trigger).lower().strip()
            if not trigger_lower or len(trigger_lower) < 3:
                continue
            if trigger_lower in keyword_lower or keyword_lower in trigger_lower:
                matched.append(bible)
                break  # Don't add same bible twice

    return matched


async def _match_bibles_llm(
    project_bibles: list[Any],
    keyword: str,
) -> list[Any]:
    """Semantic matching via Haiku — cheap, fast fallback when substring fails.

    Sends bible names + trigger keywords to Haiku and asks which are relevant
    to the page keyword. Returns matched bibles preserving sort order.
    """
    from app.integrations.claude import ClaudeClient, get_api_key

    # Build a compact description of each bible for the prompt
    bible_descriptions: list[str] = []
    for i, bible in enumerate(project_bibles):
        name = getattr(bible, "name", f"Bible {i}")
        triggers = getattr(bible, "trigger_keywords", []) or []
        triggers_str = ", ".join(str(t) for t in triggers[:20])
        bible_descriptions.append(f'{i}. "{name}" — triggers: {triggers_str}')

    prompt = (
        f'Page keyword: "{keyword}"\n\n'
        "Knowledge bibles:\n"
        + "\n".join(bible_descriptions)
        + "\n\n"
        "Which bibles contain domain knowledge relevant to this page keyword? "
        "Return ONLY a JSON array of the bible numbers (0-indexed) that match. "
        "A bible is relevant if its topic area covers the page keyword, even if "
        "the exact keyword isn't in the trigger list. "
        "If none are relevant, return []."
    )

    try:
        client = ClaudeClient(
            api_key=get_api_key(),
            model=BIBLE_MATCH_MODEL,
            max_tokens=100,
            timeout=10,
        )
        result = await client.complete(
            user_prompt=prompt,
            system_prompt="You are a keyword matching assistant. Respond with ONLY a JSON array of integers.",
            max_tokens=100,
            temperature=0,
        )

        text = (result.text or "").strip()
        # Strip markdown fencing if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()

        indices = json.loads(text)
        if not isinstance(indices, list):
            return []

        matched = []
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(project_bibles):
                matched.append(project_bibles[idx])

        logger.info(
            "LLM bible matching result",
            extra={
                "keyword": keyword,
                "matched_indices": indices,
                "matched_names": [getattr(b, "name", "?") for b in matched],
                "model": BIBLE_MATCH_MODEL,
            },
        )
        return matched

    except Exception as exc:
        logger.warning(
            "LLM bible matching failed, returning empty",
            extra={"keyword": keyword, "error": str(exc)},
        )
        return []


async def _match_bibles_for_keyword(
    project_bibles: list[Any],
    keyword: str,
) -> list[Any]:
    """Match bibles for a keyword — substring first, LLM fallback.

    1. Try fast bidirectional substring matching
    2. If no matches, fall back to Haiku for semantic matching

    Returns matched bibles preserving sort order.
    """
    if not project_bibles or not keyword:
        logger.info(
            "Bible matching skipped (no bibles or no keyword)",
            extra={
                "bible_count": len(project_bibles) if project_bibles else 0,
                "keyword": keyword or "(empty)",
            },
        )
        return []

    # Fast path: substring matching
    matched = _match_bibles_substring(project_bibles, keyword)

    if matched:
        logger.info(
            "Bible matched via substring",
            extra={
                "keyword": keyword,
                "matched_count": len(matched),
                "matched_names": [getattr(b, "name", "?") for b in matched],
            },
        )
        return matched

    # Slow path: LLM semantic matching
    logger.info(
        "No substring match — falling back to LLM matching",
        extra={"keyword": keyword, "total_bibles": len(project_bibles)},
    )
    matched = await _match_bibles_llm(project_bibles, keyword)

    logger.info(
        "Bible keyword matching final result",
        extra={
            "keyword": keyword,
            "total_bibles": len(project_bibles),
            "matched_count": len(matched),
            "matched_names": [getattr(b, "name", "?") for b in matched],
            "method": "llm",
        },
    )
    return matched


async def _process_single_page(
    page_data: dict[str, Any],
    brand_config: dict[str, Any],
    force_refresh: bool,
    refresh_briefs: bool = False,
    outline_first: bool = False,
    project_bibles: list[Any] | None = None,
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

            # Match vertical bibles for this keyword
            matched_bibles = await _match_bibles_for_keyword(
                project_bibles or [], keyword
            )

            # --- Step 2: Write content (or outline) ---
            if outline_first:
                # Outline-first mode: generate outline, skip quality checks
                outline_result = await generate_outline(
                    db=db,
                    crawled_page=crawled_page,
                    content_brief=content_brief,
                    brand_config=brand_config,
                    keyword=keyword,
                    matched_bibles=matched_bibles,
                )

                if not outline_result.success:
                    await db.commit()
                    return PipelinePageResult(
                        page_id=page_id,
                        url=url,
                        success=False,
                        error=outline_result.error,
                    )

                logger.info(
                    "Page outline generation complete",
                    extra={
                        "page_id": page_id,
                        "url": url,
                        "sections": len(
                            (outline_result.outline_json or {}).get("section_details", [])
                        ),
                    },
                )

                return PipelinePageResult(
                    page_id=page_id,
                    url=url,
                    success=True,
                )

            # Standard mode: generate content
            writing_result = await generate_content(
                db=db,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword=keyword,
                matched_bibles=matched_bibles,
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

            pipeline_result = await run_quality_pipeline(
                content=written_content,
                brand_config=brand_config,
                primary_keyword=keyword,
                content_brief=content_brief,
                matched_bibles=matched_bibles,
            )

            # Apply auto-rewrite results if fixed version was kept
            _apply_rewrite_results(written_content, pipeline_result)

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
                summary_parts.append(
                    f"  - {phrase} (weight: {weight}, target: {avg_count})"
                )

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
            summary_parts.append(
                f"\nHeading Structure Targets ({len(heading_targets)}):"
            )
            for h in heading_targets:
                tag = h.get("tag", "")
                target = h.get("target", 0)
                summary_parts.append(f"  - {tag}: {target}")

        # Keyword Placement Targets
        keyword_targets = content_brief.keyword_targets or []
        if keyword_targets:
            summary_parts.append(
                f"\nKeyword Placement Targets ({len(keyword_targets)}):"
            )
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

        response_text = (
            "\n".join(summary_parts) if summary_parts else json.dumps(raw, indent=2)
        )
    else:
        response_text = (
            f"POP brief fetch failed: {brief_result.error or 'unknown error'}"
        )

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
