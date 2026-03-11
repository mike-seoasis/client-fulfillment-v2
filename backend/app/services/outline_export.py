"""Export outline to Google Doc and log to tracking sheet.

Orchestrates the Google Docs integration to:
1. Create a formatted Google Doc from outline JSON
2. Share the doc (anyone with link can view)
3. Log a row in the per-project tracking spreadsheet
4. Save the doc URL back to the PageContent record
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.google_docs import (
    append_sheet_row,
    clear_google_doc,
    create_google_doc,
    extract_doc_id_from_url,
    find_or_create_sheet,
    format_outline_doc,
    share_doc,
)
from app.models.crawled_page import CrawledPage
from app.models.page_content import PageContent

logger = get_logger(__name__)


@dataclass
class ExportResult:
    success: bool
    google_doc_url: str | None = None
    error: str | None = None


async def export_outline_to_google(
    db: AsyncSession,
    project_name: str,
    crawled_page: CrawledPage,
    page_content: PageContent,
    keyword: str,
) -> ExportResult:
    """Export an outline to a Google Doc and log it in the tracking sheet.

    This is synchronous Google API work wrapped in an async function.
    The Google API client is synchronous, so the actual calls block.

    Args:
        db: Database session for saving the doc URL.
        project_name: Name of the project (for doc title / sheet name).
        crawled_page: The CrawledPage record (for URL).
        page_content: The PageContent record (has outline_json, gets google_doc_url set).
        keyword: Primary keyword for the page.

    Returns:
        ExportResult with success status and doc URL.
    """
    settings = get_settings()
    folder_id = settings.google_drive_folder_id
    outline = page_content.outline_json

    if not outline:
        return ExportResult(success=False, error="No outline data found")

    page_name = outline.get("page_name", keyword or "Untitled")
    doc_title = f"{project_name} — {page_name} Outline"

    try:
        # Check if we can update an existing doc (re-export)
        existing_doc_id = (
            extract_doc_id_from_url(page_content.google_doc_url)
            if page_content.google_doc_url
            else None
        )

        if existing_doc_id:
            # Re-export: clear existing doc and re-populate
            doc_id = existing_doc_id
            doc_url = str(page_content.google_doc_url)
            clear_google_doc(doc_id)
            format_outline_doc(doc_id, outline, project_name)
            logger.info(
                "Re-exported outline to existing Google Doc",
                extra={"doc_id": doc_id, "page_id": crawled_page.id},
            )
        else:
            # First export: create new doc
            doc_id, doc_url = create_google_doc(doc_title, folder_id)
            format_outline_doc(doc_id, outline, project_name)
            share_doc(doc_id)
            page_content.google_doc_url = doc_url

        # Log to tracking sheet
        sheet_id, _sheet_url = find_or_create_sheet(project_name, folder_id)
        action = (
            "re-exported" if existing_doc_id else page_content.outline_status or "draft"
        )
        append_sheet_row(
            sheet_id,
            [
                crawled_page.normalized_url,
                keyword,
                action,
                doc_url or "",
                datetime.now(UTC).strftime("%Y-%m-%d %H:%M"),
            ],
        )

        await db.commit()
        await db.refresh(page_content)

        logger.info(
            "Outline exported to Google Doc",
            extra={
                "doc_url": doc_url,
                "page_id": crawled_page.id,
                "keyword": keyword,
            },
        )

        return ExportResult(success=True, google_doc_url=doc_url)

    except FileNotFoundError as e:
        logger.error("Google service account key not found", extra={"error": str(e)})
        return ExportResult(success=False, error=str(e))
    except Exception as e:
        logger.error(
            "Failed to export outline to Google Doc",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        return ExportResult(success=False, error=f"Export failed: {e}")
