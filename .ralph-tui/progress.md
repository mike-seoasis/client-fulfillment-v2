# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

- **Service pattern**: Services in `backend/app/services/` are classes with `@staticmethod` methods. No `__init__` needed for stateless utility services.

---

## 2026-02-08 - S7-001
- Created `ExportService` class with `extract_handle(url)` and `sanitize_filename(name)`
- `extract_handle`: Parses URL, strips query params and trailing slashes. If path contains `/collections/`, returns segment(s) after it; otherwise returns last non-empty path segment.
- `sanitize_filename`: Lowercases name, replaces non-alphanumeric chars with hyphens, collapses multiples, strips edges.
- Files changed: `backend/app/services/export.py` (new)
- **Learnings:**
  - `urlparse` handles query param stripping automatically via `.path` (no manual `?` splitting needed)
  - Ruff linting passes clean; mypy errors exist in other service files but not in new code
  - Run tests from `backend/` directory to get `app.` imports working
---

## 2026-02-08 - S7-002
- Added `generate_csv(db, project_id, page_ids=None)` async method to `ExportService`
- Queries `CrawledPage` joined with `PageContent` where `is_approved=True` and `status=complete`
- Optional `page_ids` filter silently skips non-approved pages
- CSV columns: Handle, Title, Body (HTML), SEO Description, Metafield: custom.top_description [single_line_text_field]
- Uses `csv.writer` with `StringIO`, UTF-8 BOM prefix (`\ufeff`) for Excel compatibility
- Null content fields render as empty string via `or ""`
- Returns `(csv_string, row_count)` tuple
- Files changed: `backend/app/services/export.py` (modified)
- **Learnings:**
  - `select(CrawledPage, PageContent).join(...)` returns tuples that can be unpacked as `(page, content)` in the result rows
  - UTF-8 BOM is `\ufeff` — write it before the csv.writer starts to ensure it's the very first bytes
  - Pre-existing mypy errors in other service files (content_extraction, crawling, content_writing, content_quality) — not related to export service
---

