"""Brand config API router.

REST endpoints for managing brand configuration generation.
Supports triggering generation, monitoring progress, and managing config.
"""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_session
from app.integrations.claude import ClaudeClient, get_claude
from app.integrations.crawl4ai import Crawl4AIClient, get_crawl4ai
from app.integrations.perplexity import PerplexityClient, get_perplexity
from app.models.reddit_config import RedditProjectConfig
from app.schemas.brand_config import (
    BrandConfigResponse,
    RegenerateRequest,
    SectionUpdate,
)
from app.schemas.brand_config_generation import GenerationStatusResponse
from app.services.brand_config import BrandConfigService
from app.services.project import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/brand-config", tags=["Brand Config"])


async def _run_subreddit_research(
    db: AsyncSession,
    project_id: str,
    generated_sections: dict[str, Any],
    perplexity: PerplexityClient,
    update_status: Any,
) -> None:
    """Post-synthesis hook: research and auto-populate target subreddits.

    Only runs if the project has a RedditProjectConfig and target_subreddits
    is currently empty (doesn't overwrite manual entries).

    Args:
        db: AsyncSession for database operations.
        project_id: UUID of the project.
        generated_sections: Sections generated during synthesis phase.
        perplexity: Perplexity client for subreddit research.
        update_status: Async callback for progress updates.
    """
    from app.services.brand_config import GENERATION_STEPS

    step_index = GENERATION_STEPS.index("subreddit_research")
    await update_status("subreddit_research", step_index)

    # Check if project has a Reddit config
    stmt = select(RedditProjectConfig).where(
        RedditProjectConfig.project_id == project_id
    )
    result = await db.execute(stmt)
    reddit_config = result.scalar_one_or_none()

    if not reddit_config:
        logger.info(
            "Skipping subreddit research — no Reddit config",
            extra={"project_id": project_id},
        )
        return

    # Don't overwrite manually entered subreddits
    if reddit_config.target_subreddits and len(reddit_config.target_subreddits) > 0:
        logger.info(
            "Skipping subreddit research — target_subreddits already populated",
            extra={
                "project_id": project_id,
                "existing_count": len(reddit_config.target_subreddits),
            },
        )
        return

    if not perplexity.available:
        logger.warning(
            "Skipping subreddit research — Perplexity not available",
            extra={"project_id": project_id},
        )
        return

    # Build brand info from generated sections
    bf = generated_sections.get("brand_foundation", {})
    ta = generated_sections.get("target_audience", {})

    brand_name = bf.get("company_overview", {}).get("company_name", "")
    if not brand_name:
        logger.warning(
            "Skipping subreddit research — no brand name in generated sections",
            extra={"project_id": project_id},
        )
        return

    brand_info = f"""Industry: {bf.get("company_overview", {}).get("industry", "")}
Products: {bf.get("what_they_sell", {}).get("primary_products_services", "")}
Target audience: {ta.get("audience_overview", {}).get("primary_persona", "")}
USP: {bf.get("differentiators", {}).get("primary_usp", "")}"""

    try:
        subreddits = await perplexity.research_subreddits(brand_name, brand_info)

        if subreddits:
            reddit_config.target_subreddits = subreddits
            flag_modified(reddit_config, "target_subreddits")
            await db.flush()

            logger.info(
                "Auto-populated target_subreddits from research",
                extra={
                    "project_id": project_id,
                    "subreddit_count": len(subreddits),
                    "subreddits": subreddits,
                },
            )
        else:
            logger.warning(
                "Subreddit research returned no results",
                extra={"project_id": project_id},
            )

    except Exception as e:
        # Non-fatal — log and continue
        logger.warning(
            "Subreddit research failed (non-fatal)",
            extra={"project_id": project_id, "error": str(e)},
        )


async def run_generation(
    project_id: str,
    perplexity: PerplexityClient,
    crawl4ai: Crawl4AIClient,
    claude: ClaudeClient,
) -> None:
    """Background task to run brand config generation.

    Executes the full generation pipeline:
    1. Research phase - parallel data gathering
    2. Synthesis phase - sequential section generation
    3. Storage phase - save to BrandConfig

    Note: Creates its own database session to avoid issues with the
    request-scoped session being closed after the response is sent.

    Args:
        project_id: UUID of the project.
        perplexity: Perplexity client for web research.
        crawl4ai: Crawl4AI client for website crawling.
        claude: Claude client for LLM generation.
    """
    from app.core.database import db_manager

    # Create a fresh database session for the background task
    async with db_manager.session_factory() as db:
        try:
            logger.info(
                "Starting brand config generation - background task",
                extra={
                    "project_id": project_id,
                    "claude_available": claude.available,
                    "claude_model": claude.model,
                    "claude_id": id(claude),
                    "perplexity_available": perplexity.available,
                },
            )

            # Research phase
            research_context = await BrandConfigService._research_phase(
                db=db,
                project_id=project_id,
                perplexity=perplexity,
                crawl4ai=crawl4ai,
            )

            if not research_context.has_any_data():
                await BrandConfigService.fail_generation(
                    db=db,
                    project_id=project_id,
                    error="No research data available - all sources failed",
                )
                await db.commit()
                return

            # Create status update callback
            async def update_status(step_name: str, step_index: int) -> None:
                await BrandConfigService.update_progress(
                    db=db,
                    project_id=project_id,
                    current_step=step_name,
                    steps_completed=step_index,
                )
                await db.commit()

            # Synthesis phase
            generated_sections = await BrandConfigService._synthesis_phase(
                project_id=project_id,
                research_context=research_context,
                claude=claude,
                update_status_callback=update_status,
            )

            # Post-synthesis: subreddit research if Reddit is configured
            await _run_subreddit_research(
                db=db,
                project_id=project_id,
                generated_sections=generated_sections,
                perplexity=perplexity,
                update_status=update_status,
            )

            # Get source file IDs for metadata
            source_file_ids = await BrandConfigService.get_source_file_ids(db, project_id)

            # Store brand config
            await BrandConfigService.store_brand_config(
                db=db,
                project_id=project_id,
                generated_sections=generated_sections,
                source_file_ids=source_file_ids,
            )

            await db.commit()

            logger.info(
                "Brand config generation completed",
                extra={"project_id": project_id},
            )

        except Exception as e:
            logger.exception(
                "Brand config generation failed",
                extra={"project_id": project_id, "error": str(e)},
            )
            try:
                await BrandConfigService.fail_generation(
                    db=db,
                    project_id=project_id,
                    error=str(e),
                )
                await db.commit()
            except Exception:
                logger.exception(
                    "Failed to update generation status after error",
                    extra={"project_id": project_id},
                )


@router.post(
    "/generate",
    response_model=GenerationStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"description": "Project not found"},
        409: {"description": "Generation already in progress"},
    },
)
async def start_generation(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    perplexity: PerplexityClient = Depends(get_perplexity),
    crawl4ai: Crawl4AIClient = Depends(get_crawl4ai),
    claude: ClaudeClient = Depends(get_claude),
) -> GenerationStatusResponse:
    """Start brand config generation for a project.

    Initiates a background task to generate brand configuration
    based on project data, uploaded files, and web research.

    Args:
        project_id: UUID of the project.

    Returns:
        GenerationStatusResponse with initial generation state.

    Raises:
        HTTPException: 404 if project not found.
        HTTPException: 409 if generation is already in progress.
    """
    # Debug logging for client state at endpoint time
    logger.info(
        "start_generation endpoint - client states",
        extra={
            "project_id": project_id,
            "claude_available": claude.available,
            "claude_model": claude.model,
            "claude_id": id(claude),
            "perplexity_available": perplexity.available,
        },
    )

    # Verify project exists
    await ProjectService.get_project(db, project_id)

    # Start generation (this sets status and checks for conflict)
    generation_status = await BrandConfigService.start_generation(db, project_id)
    await db.commit()

    # Queue background task (creates its own db session)
    background_tasks.add_task(
        run_generation,
        project_id=project_id,
        perplexity=perplexity,
        crawl4ai=crawl4ai,
        claude=claude,
    )

    return GenerationStatusResponse(
        status=generation_status.status.value,
        current_step=generation_status.current_step,
        steps_completed=generation_status.steps_completed,
        steps_total=generation_status.steps_total,
        error=generation_status.error,
        started_at=generation_status.started_at,
        completed_at=generation_status.completed_at,
    )


@router.get(
    "/status",
    response_model=GenerationStatusResponse,
    responses={
        404: {"description": "Project not found"},
    },
)
async def get_generation_status(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> GenerationStatusResponse:
    """Get the current brand config generation status.

    Returns the current state of brand config generation including
    progress information and any errors.

    Args:
        project_id: UUID of the project.

    Returns:
        GenerationStatusResponse with current generation state.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists
    await ProjectService.get_project(db, project_id)

    # Get generation status
    generation_status = await BrandConfigService.get_status(db, project_id)

    return GenerationStatusResponse(
        status=generation_status.status.value,
        current_step=generation_status.current_step,
        steps_completed=generation_status.steps_completed,
        steps_total=generation_status.steps_total,
        error=generation_status.error,
        started_at=generation_status.started_at,
        completed_at=generation_status.completed_at,
    )


@router.get(
    "",
    response_model=BrandConfigResponse,
    responses={
        404: {"description": "Project not found or brand config not generated yet"},
    },
)
async def get_brand_config(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> BrandConfigResponse:
    """Get the full brand config for a project.

    Returns the complete brand configuration including all generated sections.

    Args:
        project_id: UUID of the project.

    Returns:
        BrandConfigResponse with the full brand config.

    Raises:
        HTTPException: 404 if project not found or brand config not generated yet.
    """
    brand_config = await BrandConfigService.get_brand_config(db, project_id)

    return BrandConfigResponse(
        id=brand_config.id,
        project_id=brand_config.project_id,
        brand_name=brand_config.brand_name,
        domain=brand_config.domain,
        v2_schema=brand_config.v2_schema,
        created_at=brand_config.created_at,
        updated_at=brand_config.updated_at,
    )


@router.patch(
    "",
    response_model=BrandConfigResponse,
    responses={
        404: {"description": "Project not found or brand config not generated yet"},
        422: {"description": "Invalid section names"},
    },
)
async def update_brand_config(
    project_id: str,
    request: SectionUpdate,
    db: AsyncSession = Depends(get_session),
) -> BrandConfigResponse:
    """Update specific sections of a brand config.

    Allows partial updates to individual sections without replacing
    the entire v2_schema.

    Args:
        project_id: UUID of the project.
        request: SectionUpdate with sections to update.

    Returns:
        BrandConfigResponse with the updated brand config.

    Raises:
        HTTPException: 404 if project not found or brand config not generated yet.
        HTTPException: 422 if invalid section names provided.
    """
    brand_config = await BrandConfigService.update_sections(
        db=db,
        project_id=project_id,
        sections=request.sections,
    )
    await db.commit()

    return BrandConfigResponse(
        id=brand_config.id,
        project_id=brand_config.project_id,
        brand_name=brand_config.brand_name,
        domain=brand_config.domain,
        v2_schema=brand_config.v2_schema,
        created_at=brand_config.created_at,
        updated_at=brand_config.updated_at,
    )


@router.post(
    "/regenerate",
    response_model=BrandConfigResponse,
    responses={
        404: {"description": "Project not found or brand config not generated yet"},
        422: {"description": "Invalid section names"},
        503: {"description": "Claude LLM not available"},
    },
)
async def regenerate_brand_config(
    project_id: str,
    request: RegenerateRequest,
    db: AsyncSession = Depends(get_session),
    perplexity: PerplexityClient = Depends(get_perplexity),
    crawl4ai: Crawl4AIClient = Depends(get_crawl4ai),
    claude: ClaudeClient = Depends(get_claude),
) -> BrandConfigResponse:
    """Regenerate all or specific sections of a brand config.

    Runs the research and synthesis phases again for the specified sections.
    If no sections are specified, regenerates all sections.

    Args:
        project_id: UUID of the project.
        request: RegenerateRequest with optional sections to regenerate.

    Returns:
        BrandConfigResponse with the regenerated brand config.

    Raises:
        HTTPException: 404 if project not found or brand config not generated yet.
        HTTPException: 422 if invalid section names provided.
        HTTPException: 503 if Claude LLM is not configured.
    """
    sections = request.get_sections_to_regenerate()

    brand_config = await BrandConfigService.regenerate_sections(
        db=db,
        project_id=project_id,
        sections=sections,
        perplexity=perplexity,
        crawl4ai=crawl4ai,
        claude=claude,
    )
    await db.commit()

    return BrandConfigResponse(
        id=brand_config.id,
        project_id=brand_config.project_id,
        brand_name=brand_config.brand_name,
        domain=brand_config.domain,
        v2_schema=brand_config.v2_schema,
        created_at=brand_config.created_at,
        updated_at=brand_config.updated_at,
    )
