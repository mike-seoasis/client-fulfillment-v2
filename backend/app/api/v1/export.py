"""Export endpoints for multi-site XLSX download."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.export_xlsx import generate_sites_xlsx

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/sites-xlsx")
async def export_sites_xlsx(
    project_ids: str | None = Query(
        None,
        description="Comma-separated project UUIDs to include. Omit for all projects.",
    ),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Export all projects as a multi-site XLSX workbook.

    Each project becomes a tab. Collection pages and blog posts
    are mapped to the sites-template format.
    """
    ids_list = None
    if project_ids:
        ids_list = [pid.strip() for pid in project_ids.split(",") if pid.strip()]

    try:
        buffer = await generate_sites_xlsx(db, project_ids=ids_list)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="sites-export.xlsx"',
        },
    )
