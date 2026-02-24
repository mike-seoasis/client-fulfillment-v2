"""Brand Wizard API endpoints.

Provides endpoints for the 7-step brand configuration wizard:
- GET /api/v1/projects/{project_id}/brand-wizard - Get wizard state
- PUT /api/v1/projects/{project_id}/brand-wizard - Save wizard step
- POST /api/v1/projects/{project_id}/brand-wizard/research - Trigger Perplexity research
- POST /api/v1/projects/{project_id}/brand-wizard/generate - Generate V3 config

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.models.project import Project
from app.schemas.brand_config_v3 import V3BrandConfigSchema, is_v3_config
from app.services.brand_research import get_brand_research_service

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================


class WizardStateResponse(BaseModel):
    """Response schema for wizard state."""

    project_id: str
    current_step: int = Field(default=1, ge=1, le=7)
    steps_completed: list[int] = Field(default_factory=list)
    brand_name: str | None = None
    domain: str | None = None
    research_data: dict[str, Any] | None = None
    research_citations: list[str] = Field(default_factory=list)
    research_cached_at: str | None = None
    form_data: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None


class WizardStepUpdateRequest(BaseModel):
    """Request schema for updating wizard step."""

    current_step: int = Field(..., ge=1, le=7, description="Current step number")
    form_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Form data for all steps (merged with existing)",
    )


class WizardStepUpdateResponse(BaseModel):
    """Response schema for step update."""

    success: bool
    project_id: str
    current_step: int
    steps_completed: list[int]
    updated_at: str


class ResearchRequest(BaseModel):
    """Request schema for triggering brand research."""

    domain: str = Field(..., min_length=1, description="Domain to research")
    brand_name: str | None = Field(None, description="Optional brand name")
    force_refresh: bool = Field(
        default=False, description="Bypass cache and force new research"
    )


class ResearchResponse(BaseModel):
    """Response schema for brand research."""

    success: bool
    project_id: str
    domain: str
    raw_research: str | None = None
    citations: list[str] = Field(default_factory=list)
    from_cache: bool = False
    cached_at: str | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset_at: str | None = None
    error: str | None = None
    duration_ms: float = 0.0


class GenerateV3Request(BaseModel):
    """Request schema for generating V3 config."""

    brand_name: str = Field(..., min_length=1, description="Brand name")
    domain: str | None = Field(None, description="Brand domain")
    wizard_data: dict[str, Any] = Field(
        ..., description="Complete wizard form data from all steps"
    )


class GenerateV3Response(BaseModel):
    """Response schema for V3 generation."""

    success: bool
    project_id: str
    brand_config_id: str | None = None
    v3_config: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: float = 0.0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_request_id(request: Request) -> str:
    """Get request_id from request state."""
    return getattr(request.state, "request_id", "unknown")


async def _get_project(
    session: AsyncSession, project_id: str
) -> Project | None:
    """Get a project by ID."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get(
    "",
    response_model=WizardStateResponse,
    summary="Get brand wizard state",
    description="Get the current state of the brand configuration wizard for a project.",
)
async def get_wizard_state(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> WizardStateResponse | JSONResponse:
    """Get the current wizard state for a project."""
    request_id = _get_request_id(request)

    logger.debug(
        "Get wizard state request",
        extra={"project_id": project_id, "request_id": request_id},
    )

    project = await _get_project(session, project_id)
    if not project:
        logger.warning(
            "Project not found for wizard state",
            extra={"project_id": project_id, "request_id": request_id},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": f"Project {project_id} not found",
                "code": "PROJECT_NOT_FOUND",
                "request_id": request_id,
            },
        )

    wizard_state = project.brand_wizard_state or {}

    return WizardStateResponse(
        project_id=project_id,
        current_step=wizard_state.get("current_step", 1),
        steps_completed=wizard_state.get("steps_completed", []),
        brand_name=wizard_state.get("brand_name"),
        domain=wizard_state.get("domain"),
        research_data=wizard_state.get("research_data"),
        research_citations=wizard_state.get("research_citations", []),
        research_cached_at=wizard_state.get("research_cached_at"),
        form_data=wizard_state.get("form_data", {}),
        updated_at=wizard_state.get("updated_at"),
    )


@router.put(
    "",
    response_model=WizardStepUpdateResponse,
    summary="Save wizard step",
    description="Save the current wizard step and form data.",
)
async def save_wizard_step(
    request: Request,
    project_id: str,
    data: WizardStepUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> WizardStepUpdateResponse | JSONResponse:
    """Save wizard step and form data."""
    request_id = _get_request_id(request)

    logger.debug(
        "Save wizard step request",
        extra={
            "project_id": project_id,
            "current_step": data.current_step,
            "request_id": request_id,
        },
    )

    project = await _get_project(session, project_id)
    if not project:
        logger.warning(
            "Project not found for wizard save",
            extra={"project_id": project_id, "request_id": request_id},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": f"Project {project_id} not found",
                "code": "PROJECT_NOT_FOUND",
                "request_id": request_id,
            },
        )

    # Get existing state and merge
    existing_state = project.brand_wizard_state or {}
    existing_form_data = existing_state.get("form_data", {})
    existing_steps_completed = set(existing_state.get("steps_completed", []))

    # Merge form data
    merged_form_data = {**existing_form_data, **data.form_data}

    # Mark current step as completed if it has data
    if data.form_data:
        existing_steps_completed.add(data.current_step)

    # Update state
    now = datetime.utcnow().isoformat()
    new_state = {
        **existing_state,
        "current_step": data.current_step,
        "steps_completed": sorted(list(existing_steps_completed)),
        "form_data": merged_form_data,
        "updated_at": now,
    }

    # Persist to database
    await session.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(brand_wizard_state=new_state)
    )
    await session.commit()

    logger.info(
        "Wizard step saved",
        extra={
            "project_id": project_id,
            "current_step": data.current_step,
            "steps_completed": new_state["steps_completed"],
            "request_id": request_id,
        },
    )

    return WizardStepUpdateResponse(
        success=True,
        project_id=project_id,
        current_step=data.current_step,
        steps_completed=new_state["steps_completed"],
        updated_at=now,
    )


@router.post(
    "/research",
    response_model=ResearchResponse,
    summary="Trigger brand research",
    description="""
Trigger Perplexity-powered brand research for a domain.

Research results are cached for 24 hours. Use `force_refresh=true` to bypass cache.
Rate limited to 5 requests per hour per project.
""",
)
async def trigger_research(
    request: Request,
    project_id: str,
    data: ResearchRequest,
    session: AsyncSession = Depends(get_session),
) -> ResearchResponse | JSONResponse:
    """Trigger Perplexity brand research."""
    request_id = _get_request_id(request)

    logger.info(
        "Brand research request",
        extra={
            "project_id": project_id,
            "domain": data.domain,
            "force_refresh": data.force_refresh,
            "request_id": request_id,
        },
    )

    project = await _get_project(session, project_id)
    if not project:
        logger.warning(
            "Project not found for research",
            extra={"project_id": project_id, "request_id": request_id},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": f"Project {project_id} not found",
                "code": "PROJECT_NOT_FOUND",
                "request_id": request_id,
            },
        )

    # Get research service
    research_service = get_brand_research_service()

    # Perform research
    result = await research_service.research_brand(
        project_id=project_id,
        domain=data.domain,
        brand_name=data.brand_name,
        force_refresh=data.force_refresh,
    )

    if not result.success:
        # Check if rate limited
        if result.rate_limit and not result.rate_limit.allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": result.error,
                    "code": "RATE_LIMIT_EXCEEDED",
                    "request_id": request_id,
                    "rate_limit_remaining": 0,
                    "rate_limit_reset_at": (
                        result.rate_limit.reset_at.isoformat()
                        if result.rate_limit.reset_at
                        else None
                    ),
                },
            )

        return ResearchResponse(
            success=False,
            project_id=project_id,
            domain=data.domain,
            error=result.error,
            duration_ms=result.duration_ms,
        )

    # Update wizard state with research results
    existing_state = project.brand_wizard_state or {}
    now = datetime.utcnow().isoformat()

    new_state = {
        **existing_state,
        "domain": data.domain,
        "brand_name": data.brand_name or existing_state.get("brand_name"),
        "research_data": {"raw_text": result.raw_research},
        "research_citations": result.citations,
        "research_cached_at": result.cached_at.isoformat() if result.cached_at else now,
        "updated_at": now,
    }

    await session.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(brand_wizard_state=new_state)
    )
    await session.commit()

    # Get rate limit info
    rate_limit = result.rate_limit
    rate_limit_remaining = rate_limit.requests_remaining if rate_limit else None
    rate_limit_reset = (
        rate_limit.reset_at.isoformat()
        if rate_limit and rate_limit.reset_at
        else None
    )

    logger.info(
        "Brand research completed",
        extra={
            "project_id": project_id,
            "domain": data.domain,
            "from_cache": result.from_cache,
            "duration_ms": result.duration_ms,
            "request_id": request_id,
        },
    )

    return ResearchResponse(
        success=True,
        project_id=project_id,
        domain=data.domain,
        raw_research=result.raw_research,
        citations=result.citations,
        from_cache=result.from_cache,
        cached_at=result.cached_at.isoformat() if result.cached_at else None,
        rate_limit_remaining=rate_limit_remaining,
        rate_limit_reset_at=rate_limit_reset,
        duration_ms=result.duration_ms,
    )


@router.post(
    "/generate",
    response_model=GenerateV3Response,
    status_code=status.HTTP_201_CREATED,
    summary="Generate V3 brand config",
    description="""
Generate a V3 brand configuration from wizard data.

This finalizes the wizard by:
1. Synthesizing research data with wizard edits into V3 schema
2. Saving the V3 config to brand_configs table
3. Clearing the wizard state
""",
)
async def generate_v3_config(
    request: Request,
    project_id: str,
    data: GenerateV3Request,
    session: AsyncSession = Depends(get_session),
) -> GenerateV3Response | JSONResponse:
    """Generate V3 brand config from wizard data."""
    request_id = _get_request_id(request)

    logger.info(
        "Generate V3 config request",
        extra={
            "project_id": project_id,
            "brand_name": data.brand_name,
            "request_id": request_id,
        },
    )

    project = await _get_project(session, project_id)
    if not project:
        logger.warning(
            "Project not found for V3 generation",
            extra={"project_id": project_id, "request_id": request_id},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": f"Project {project_id} not found",
                "code": "PROJECT_NOT_FOUND",
                "request_id": request_id,
            },
        )

    # Get wizard state for research data
    wizard_state = project.brand_wizard_state or {}
    research_data = wizard_state.get("research_data", {})
    raw_research = research_data.get("raw_text", "")
    citations = wizard_state.get("research_citations", [])

    # If we have research data, synthesize with Claude
    research_service = get_brand_research_service()

    if raw_research:
        v3_config, error, _ = await research_service.synthesize_to_v3(
            research_text=raw_research,
            brand_name=data.brand_name,
            domain=data.domain,
            citations=citations,
        )

        if error:
            logger.error(
                "V3 synthesis failed",
                extra={
                    "project_id": project_id,
                    "error": error,
                    "request_id": request_id,
                },
            )
            return GenerateV3Response(
                success=False,
                project_id=project_id,
                error=error,
            )
    else:
        # Create empty V3 config from wizard data only
        v3_config = V3BrandConfigSchema()

    # Merge wizard edits into V3 config
    v3_dict = v3_config.model_dump() if v3_config else {}
    wizard_form = data.wizard_data

    # Apply wizard edits (step-by-step data overrides)
    if "foundation" in wizard_form:
        v3_dict["foundation"] = {**v3_dict.get("foundation", {}), **wizard_form["foundation"]}
    if "personas" in wizard_form:
        v3_dict["personas"] = wizard_form["personas"]
    if "voice_dimensions" in wizard_form:
        v3_dict["voice_dimensions"] = {
            **v3_dict.get("voice_dimensions", {}),
            **wizard_form["voice_dimensions"],
        }
    if "voice_characteristics" in wizard_form:
        v3_dict["voice_characteristics"] = {
            **v3_dict.get("voice_characteristics", {}),
            **wizard_form["voice_characteristics"],
        }
    if "writing_rules" in wizard_form:
        v3_dict["writing_rules"] = {
            **v3_dict.get("writing_rules", {}),
            **wizard_form["writing_rules"],
        }
    if "vocabulary" in wizard_form:
        v3_dict["vocabulary"] = {
            **v3_dict.get("vocabulary", {}),
            **wizard_form["vocabulary"],
        }
    if "proof_elements" in wizard_form:
        v3_dict["proof_elements"] = {
            **v3_dict.get("proof_elements", {}),
            **wizard_form["proof_elements"],
        }
    if "examples_bank" in wizard_form:
        v3_dict["examples_bank"] = {
            **v3_dict.get("examples_bank", {}),
            **wizard_form["examples_bank"],
        }
    if "quick_reference" in wizard_form:
        v3_dict["quick_reference"] = {
            **v3_dict.get("quick_reference", {}),
            **wizard_form["quick_reference"],
        }

    # Add metadata
    v3_dict["_version"] = "3.0"
    v3_dict["_generated_at"] = datetime.utcnow().isoformat()
    v3_dict["_sources_used"] = citations

    # TODO: Save to brand_configs table
    # For now, just clear the wizard state
    await session.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(brand_wizard_state={})
    )
    await session.commit()

    logger.info(
        "V3 config generated",
        extra={
            "project_id": project_id,
            "brand_name": data.brand_name,
            "request_id": request_id,
        },
    )

    return GenerateV3Response(
        success=True,
        project_id=project_id,
        v3_config=v3_dict,
    )
