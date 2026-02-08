# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

- **Service pattern**: Services in `backend/app/services/` are classes with `@staticmethod` methods. No `__init__` needed for stateless utility services.
- **Test DB fixtures**: Use `db_session` fixture from conftest, create model instances with `db_session.add()` + `await db_session.flush()`. Session auto-rollbacks between tests. SQLite in-memory via `aiosqlite`.
- **Integration test fixtures**: When using `async_client` (HTTP endpoint tests), fixtures must call `await db_session.commit()` (not just `flush()`) so data is visible to the endpoint's separate DB session. Unit tests that pass `db_session` directly can use `flush()`.

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

## 2026-02-08 - S7-003
- Added `GET /api/v1/projects/{project_id}/export` endpoint to `backend/app/api/v1/projects.py`
- Accepts optional `page_ids` query parameter (comma-separated UUIDs)
- Returns CSV with `Content-Type: text/csv; charset=utf-8` and `Content-Disposition: attachment; filename="{sanitized}-matrixify-export.csv"`
- Returns HTTP 400 if no approved pages available, HTTP 404 if project not found
- Uses `ExportService.generate_csv()` from S7-002 and `ExportService.sanitize_filename()` from S7-001
- Files changed: `backend/app/api/v1/projects.py` (modified — added `Response` import + export endpoint)
- **Learnings:**
  - FastAPI `Response` with `media_type` and `headers` dict is the simplest way to return file downloads (no need for `StreamingResponse` for small CSV payloads)
  - Inline imports for service classes work well in endpoint functions (follows existing pattern in the codebase, e.g. `regenerate_taxonomy`)
  - `page_ids` as comma-separated string query param is simpler than using FastAPI's `Query(...)` list parsing for optional UUID lists
---

## 2026-02-08 - S7-004
- Created unit tests for export service: 14 tests across 3 test classes
- `TestExtractHandle` (7 tests): standard /collections/ URL, URL without /collections/, query params stripped, trailing slash stripped, nested path after /collections/, empty path, combined trailing slash + query params
- `TestSanitizeFilename` (4 tests): special characters, spaces, consecutive special chars collapsed, leading/trailing stripped
- `TestGenerateCSV` (3 tests): all fields populated with correct columns/values, null fields render as empty strings (not 'None'), UTF-8 BOM present
- Files changed: `backend/tests/test_export.py` (new)
- **Learnings:**
  - `asyncio_mode = "auto"` in pyproject.toml means no `@pytest.mark.asyncio` needed on async test methods
  - CSV BOM can be stripped with `csv_string.lstrip("\ufeff")` for clean parsing in assertions
  - CrawledPage requires `labels=[]` explicitly when creating test fixtures (non-nullable JSONB column)
---

## 2026-02-08 - S7-005
- Created integration tests for the export CSV endpoint (GET /api/v1/projects/{project_id}/export)
- 7 tests in `TestExportEndpoint` class covering all acceptance criteria:
  - `test_export_with_page_ids_filter` — page_ids filter returns only selected pages
  - `test_export_without_page_ids_returns_all_approved` — no filter returns all approved pages
  - `test_export_no_approved_pages_returns_400` — HTTP 400 when no approved pages
  - `test_export_mixed_approved_unapproved_page_ids` — mix of approved/unapproved returns only approved
  - `test_export_invalid_project_id_returns_404` — HTTP 404 for non-existent project
  - `test_export_csv_headers_are_matrixify_columns` — correct Matrixify column names
  - `test_export_content_disposition_header` — sanitized filename in Content-Disposition
- Files changed: `backend/tests/test_export_api.py` (new)
- **Learnings:**
  - Integration tests using `async_client` fixture need `db_session.commit()` (not just `flush()`) in fixtures so data is visible to the endpoint's separate session
  - `StaticPool` with SQLite in-memory means all sessions share the same connection, so committed data is visible across sessions within the same test
  - `_parse_csv()` helper with BOM stripping keeps test assertions clean and DRY
  - Project model requires `phase_status={}` and `brand_wizard_state={}` explicitly in test fixtures (non-nullable JSONB columns)
---
