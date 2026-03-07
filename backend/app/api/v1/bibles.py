"""Bible CRUD API router.

REST endpoints for managing vertical knowledge bibles per project.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.schemas.vertical_bible import (
    TranscriptExtractionRequest,
    TranscriptExtractionResponse,
    VerticalBibleCreate,
    VerticalBibleExportResponse,
    VerticalBibleImportRequest,
    VerticalBibleListResponse,
    VerticalBibleResponse,
    VerticalBibleUpdate,
)
from app.services.project import ProjectService
from app.services.vertical_bible import VerticalBibleService, generate_bible_from_transcript

logger = get_logger(__name__)

router = APIRouter(prefix="/projects/{project_id}/bibles", tags=["Bibles"])


@router.post(
    "",
    response_model=VerticalBibleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Project not found"},
        409: {"description": "Slug collision"},
    },
)
async def create_bible(
    project_id: str,
    request: VerticalBibleCreate,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Create a new knowledge bible for a project."""
    await ProjectService.get_project(db, project_id)
    bible = await VerticalBibleService.create_bible(db, project_id, request)
    return VerticalBibleResponse.model_validate(bible)


@router.get(
    "",
    response_model=VerticalBibleListResponse,
    responses={404: {"description": "Project not found"}},
)
async def list_bibles(
    project_id: str,
    active_only: bool = False,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleListResponse:
    """List all bibles for a project."""
    await ProjectService.get_project(db, project_id)
    bibles = await VerticalBibleService.list_bibles(db, project_id, active_only)
    return VerticalBibleListResponse(
        items=[VerticalBibleResponse.model_validate(b) for b in bibles],
        total=len(bibles),
    )


@router.get(
    "/{bible_id}",
    response_model=VerticalBibleResponse,
    responses={404: {"description": "Bible not found"}},
)
async def get_bible(
    project_id: str,
    bible_id: str,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Get a single bible by ID."""
    bible = await VerticalBibleService.get_bible(db, project_id, bible_id)
    return VerticalBibleResponse.model_validate(bible)


@router.put(
    "/{bible_id}",
    response_model=VerticalBibleResponse,
    responses={
        404: {"description": "Bible not found"},
        409: {"description": "Slug collision"},
    },
)
async def update_bible(
    project_id: str,
    bible_id: str,
    request: VerticalBibleUpdate,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Update a bible (full or partial update)."""
    bible = await VerticalBibleService.update_bible(db, project_id, bible_id, request)
    return VerticalBibleResponse.model_validate(bible)


@router.patch(
    "/{bible_id}",
    response_model=VerticalBibleResponse,
    responses={
        404: {"description": "Bible not found"},
        409: {"description": "Slug collision"},
    },
)
async def patch_bible(
    project_id: str,
    bible_id: str,
    request: VerticalBibleUpdate,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Partially update a bible (same as PUT, only provided fields change)."""
    bible = await VerticalBibleService.update_bible(db, project_id, bible_id, request)
    return VerticalBibleResponse.model_validate(bible)


@router.delete(
    "/{bible_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Bible not found"}},
)
async def delete_bible(
    project_id: str,
    bible_id: str,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a bible."""
    await VerticalBibleService.delete_bible(db, project_id, bible_id)


@router.post(
    "/import",
    response_model=VerticalBibleResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid frontmatter"},
    },
)
async def import_bible(
    project_id: str,
    request: VerticalBibleImportRequest,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleResponse:
    """Import a bible from markdown with YAML frontmatter."""
    await ProjectService.get_project(db, project_id)
    bible = await VerticalBibleService.import_from_markdown(
        db, project_id, request.markdown, request.is_active
    )
    return VerticalBibleResponse.model_validate(bible)


@router.get(
    "/{bible_id}/export",
    response_model=VerticalBibleExportResponse,
    responses={404: {"description": "Bible not found"}},
)
async def export_bible(
    project_id: str,
    bible_id: str,
    db: AsyncSession = Depends(get_session),
) -> VerticalBibleExportResponse:
    """Export a bible as markdown with YAML frontmatter."""
    bible = await VerticalBibleService.get_bible(db, project_id, bible_id)
    markdown = VerticalBibleService.export_to_markdown(bible)
    return VerticalBibleExportResponse(
        markdown=markdown,
        filename=f"{bible.slug}.md",
    )


@router.post(
    "/generate-from-transcript",
    response_model=TranscriptExtractionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a bible draft from an expert transcript",
    responses={
        404: {"description": "Project not found"},
        422: {"description": "Invalid input"},
        502: {"description": "AI extraction failed"},
    },
)
async def generate_from_transcript(
    project_id: str,
    request: TranscriptExtractionRequest,
    db: AsyncSession = Depends(get_session),
) -> TranscriptExtractionResponse:
    """Extract a structured knowledge bible from a domain expert transcript.

    Uses Claude to analyze the transcript and extract domain knowledge,
    trigger keywords, and QA rules. The bible is created as a draft
    (is_active=False) for operator review.
    """
    await ProjectService.get_project(db, project_id)

    try:
        bible = await generate_bible_from_transcript(
            transcript=request.transcript,
            vertical_name=request.vertical_name,
            project_id=project_id,
            db=db,
        )

        return TranscriptExtractionResponse(
            id=str(bible.id),
            name=bible.name,
            slug=bible.slug,
            trigger_keywords=bible.trigger_keywords or [],
            content_md=bible.content_md or "",
            qa_rules=bible.qa_rules or {},
            is_active=bible.is_active,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
