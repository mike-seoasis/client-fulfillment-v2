"""Brand config API router.

REST endpoints for managing brand configuration generation.
Supports triggering generation, monitoring progress, and managing config.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.integrations.claude import ClaudeClient, get_claude
from app.integrations.crawl4ai import Crawl4AIClient, get_crawl4ai
from app.integrations.perplexity import PerplexityClient, get_perplexity
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


async def run_generation(
    project_id: str,
    db: AsyncSession,
    perplexity: PerplexityClient,
    crawl4ai: Crawl4AIClient,
    claude: ClaudeClient,
) -> None:
    """Background task to run brand config generation.

    Executes the full generation pipeline:
    1. Research phase - parallel data gathering
    2. Synthesis phase - sequential section generation
    3. Storage phase - save to BrandConfig

    Args:
        project_id: UUID of the project.
        db: Database session.
        perplexity: Perplexity client for web research.
        crawl4ai: Crawl4AI client for website crawling.
        claude: Claude client for LLM generation.
    """
    try:
        logger.info(
            "Starting brand config generation",
            extra={"project_id": project_id},
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
    # Verify project exists
    await ProjectService.get_project(db, project_id)

    # Start generation (this sets status and checks for conflict)
    generation_status = await BrandConfigService.start_generation(db, project_id)
    await db.commit()

    # Queue background task
    background_tasks.add_task(
        run_generation,
        project_id=project_id,
        db=db,
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
