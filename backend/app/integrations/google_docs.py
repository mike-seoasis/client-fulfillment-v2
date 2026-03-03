"""Google Docs/Sheets/Drive integration using service account auth.

Thin wrapper around the Google API Python client for:
- Creating formatted Google Docs from outline JSON
- Managing a per-project Google Sheets tracking spreadsheet
- Sharing docs with "anyone with link" access

Uses a service account (no OAuth flow needed).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Scopes needed for creating Docs, Sheets, and managing Drive files
_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_credentials() -> Credentials:
    """Load service account credentials from the JSON key file."""
    settings = get_settings()
    key_path = Path(settings.google_service_account_path)
    if not key_path.is_absolute():
        # Resolve relative to backend/ directory
        key_path = Path(__file__).resolve().parents[2] / key_path
    if not key_path.exists():
        raise FileNotFoundError(
            f"Google service account key not found: {key_path}. "
            "Set GOOGLE_SERVICE_ACCOUNT_PATH to the correct path."
        )
    return Credentials.from_service_account_file(str(key_path), scopes=_SCOPES)


def _docs_service() -> Any:
    return build("docs", "v1", credentials=get_credentials(), cache_discovery=False)


def _sheets_service() -> Any:
    return build("sheets", "v4", credentials=get_credentials(), cache_discovery=False)


def _drive_service() -> Any:
    return build("drive", "v3", credentials=get_credentials(), cache_discovery=False)


# ---------------------------------------------------------------------------
# Google Docs
# ---------------------------------------------------------------------------


def create_google_doc(title: str, folder_id: str) -> tuple[str, str]:
    """Create an empty Google Doc inside the given Drive folder.

    Returns (doc_id, doc_url).
    """
    drive = _drive_service()
    file_metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id],
    }
    file = drive.files().create(
        body=file_metadata,
        fields="id,webViewLink",
        supportsAllDrives=True,
    ).execute()
    doc_id: str = file["id"]
    doc_url: str = file["webViewLink"]
    logger.info("Created Google Doc", extra={"doc_id": doc_id, "title": title})
    return doc_id, doc_url


def format_outline_doc(
    doc_id: str,
    outline_json: dict[str, Any],
    project_name: str,
) -> None:
    """Populate a Google Doc with a formatted outline using batchUpdate.

    Supports the actual outline_json structure produced by the generation
    pipeline, with fallbacks for alternate key names:
    - section_details (or sections): list of section objects
    - keyword_reference.keyword_variations / keyword_reference.lsi_terms
    - secondary_keywords (or keywords): flat keyword list
    - people_also_ask: PAA questions
    - top_ranked_results (or competitors): competitor pages
    """
    docs = _docs_service()

    page_name = outline_json.get("page_name", "Untitled")
    audience = outline_json.get("audience", "")
    # Support both "section_details" (actual) and "sections" (legacy)
    sections = outline_json.get("section_details") or outline_json.get("sections", [])
    paa = outline_json.get("people_also_ask", [])

    # Build keyword list from keyword_reference or flat "keywords" field
    keyword_ref = outline_json.get("keyword_reference", {})
    keywords: list[str] = []
    primary_kw = outline_json.get("primary_keyword")
    if primary_kw:
        keywords.append(primary_kw)
    keywords.extend(outline_json.get("secondary_keywords", []))
    for var in keyword_ref.get("keyword_variations", []):
        v = var.get("variation", var) if isinstance(var, dict) else var
        if v and v not in keywords:
            keywords.append(v)
    # Fallback to flat "keywords" list
    if not keywords:
        keywords = outline_json.get("keywords", [])

    # Build competitor list from top_ranked_results or flat "competitors"
    raw_competitors = outline_json.get("top_ranked_results") or outline_json.get("competitors", [])
    competitors: list[str] = []
    for c in raw_competitors:
        if isinstance(c, dict):
            url = c.get("url", "")
            title = c.get("title", "")
            competitors.append(f"{title} — {url}" if title else url)
        else:
            competitors.append(str(c))

    # Build requests list — insert from bottom up (index 1 = after title)
    # We'll build a list of text segments, then reverse them since
    # Docs API inserts shift indices. Easier: build full text and style later.

    requests: list[dict[str, Any]] = []
    # Track current insertion index (start at 1, after default empty paragraph)
    idx = 1

    def insert_text(text: str) -> int:
        nonlocal idx
        requests.append({
            "insertText": {"location": {"index": idx}, "text": text}
        })
        length = len(text)
        idx += length
        return length

    def style_range(start: int, end: int, style: dict[str, Any], fields: str) -> None:
        requests.append({
            "updateTextStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "textStyle": style,
                "fields": fields,
            }
        })

    def heading_style(start: int, end: int, heading: str) -> None:
        requests.append({
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": {"namedStyleType": heading},
                "fields": "namedStyleType",
            }
        })

    def bullet_style(start: int, end: int) -> None:
        requests.append({
            "createParagraphBullets": {
                "range": {"startIndex": start, "endIndex": end},
                "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
            }
        })

    # --- Title ---
    title_text = f"{project_name} — {page_name} Outline\n"
    title_start = idx
    insert_text(title_text)
    heading_style(title_start, idx, "HEADING_1")

    # --- Audience ---
    if audience:
        label_start = idx
        insert_text("Audience\n")
        heading_style(label_start, idx, "HEADING_2")
        insert_text(f"{audience}\n\n")

    # --- Sections ---
    for section in sections:
        headline = section.get("headline", "Section")
        purpose = section.get("purpose", "")
        key_points = section.get("key_points", [])
        client_notes = section.get("client_notes", "")

        # Section heading (H2)
        h2_start = idx
        insert_text(f"{headline}\n")
        heading_style(h2_start, idx, "HEADING_2")

        # Purpose
        if purpose:
            purpose_label_start = idx
            insert_text("Purpose: ")
            style_range(purpose_label_start, idx, {"bold": True}, "bold")
            insert_text(f"{purpose}\n")

        # Key points as bullets
        if key_points:
            bullets_start = idx
            for point in key_points:
                insert_text(f"{point}\n")
            bullet_style(bullets_start, idx)

        # Client notes (highlighted)
        if client_notes:
            insert_text("\n")
            note_start = idx
            insert_text(f"Client Notes: {client_notes}\n")
            style_range(
                note_start,
                idx,
                {"italic": True, "foregroundColor": {"color": {"rgbColor": {"red": 0.6, "green": 0.4, "blue": 0.0}}}},
                "italic,foregroundColor",
            )

        insert_text("\n")

    # --- Reference Section ---
    if keywords or paa or competitors:
        ref_start = idx
        insert_text("Reference\n")
        heading_style(ref_start, idx, "HEADING_1")

        if keywords:
            kw_start = idx
            insert_text("Target Keywords\n")
            heading_style(kw_start, idx, "HEADING_2")
            bullets_start = idx
            for kw in keywords:
                insert_text(f"{kw}\n")
            bullet_style(bullets_start, idx)
            insert_text("\n")

        if paa:
            paa_start = idx
            insert_text("People Also Ask\n")
            heading_style(paa_start, idx, "HEADING_2")
            bullets_start = idx
            for q in paa:
                insert_text(f"{q}\n")
            bullet_style(bullets_start, idx)
            insert_text("\n")

        if competitors:
            comp_start = idx
            insert_text("Competitor Pages\n")
            heading_style(comp_start, idx, "HEADING_2")
            bullets_start = idx
            for c in competitors:
                insert_text(f"{c}\n")
            bullet_style(bullets_start, idx)

    if requests:
        docs.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()
        logger.info(
            "Formatted Google Doc outline",
            extra={"doc_id": doc_id, "sections": len(sections)},
        )


def share_doc(doc_id: str, role: str = "reader", share_type: str = "anyone") -> None:
    """Make a doc viewable by anyone with the link."""
    drive = _drive_service()
    drive.permissions().create(
        fileId=doc_id,
        body={"role": role, "type": share_type},
        fields="id",
        supportsAllDrives=True,
    ).execute()
    logger.info("Shared Google Doc", extra={"doc_id": doc_id, "role": role})


# ---------------------------------------------------------------------------
# Google Sheets (Outline Tracker)
# ---------------------------------------------------------------------------


def find_or_create_sheet(
    project_name: str, folder_id: str
) -> tuple[str, str]:
    """Find or create a tracking spreadsheet for this project.

    Searches the folder for an existing sheet named
    "{project_name} — Outline Tracker". Creates one with a header row
    if not found.

    Returns (sheet_id, sheet_url).
    """
    drive = _drive_service()
    sheet_name = f"{project_name} — Outline Tracker"

    # Search for existing sheet in folder
    query = (
        f"name = '{sheet_name}' "
        f"and '{folder_id}' in parents "
        f"and mimeType = 'application/vnd.google-apps.spreadsheet' "
        f"and trashed = false"
    )
    results = drive.files().list(
        q=query,
        fields="files(id,webViewLink)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    files = results.get("files", [])

    if files:
        sheet_id = files[0]["id"]
        sheet_url = files[0]["webViewLink"]
        logger.info("Found existing tracker sheet", extra={"sheet_id": sheet_id})
        return sheet_id, sheet_url

    # Create new sheet in folder
    file_metadata = {
        "name": sheet_name,
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "parents": [folder_id],
    }
    file = drive.files().create(
        body=file_metadata,
        fields="id,webViewLink",
        supportsAllDrives=True,
    ).execute()
    sheet_id = file["id"]
    sheet_url = file["webViewLink"]

    # Add header row
    sheets = _sheets_service()
    sheets.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range="Sheet1!A1:E1",
        valueInputOption="RAW",
        body={
            "values": [["Page URL", "Keyword", "Outline Status", "Google Doc URL", "Export Date"]]
        },
    ).execute()

    # Bold the header row
    sheets.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": 0,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                        },
                        "cell": {
                            "userEnteredFormat": {"textFormat": {"bold": True}}
                        },
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                }
            ]
        },
    ).execute()

    logger.info("Created tracker sheet", extra={"sheet_id": sheet_id, "sheet_name": sheet_name})
    return sheet_id, sheet_url


def append_sheet_row(sheet_id: str, row_data: list[str]) -> None:
    """Append a single row to the tracking sheet."""
    sheets = _sheets_service()
    sheets.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range="Sheet1!A:E",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row_data]},
    ).execute()
    logger.info("Appended row to tracker sheet", extra={"sheet_id": sheet_id})
