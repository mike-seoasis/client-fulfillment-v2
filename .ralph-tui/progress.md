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

## 2026-02-08 - S7-006
- Added `exportProject(projectId, pageIds?)` function to `frontend/src/lib/api.ts`
- Uses raw `fetch()` (not apiClient) to get blob response from `GET /api/v1/projects/{projectId}/export`
- Optional `page_ids` query param as comma-separated string
- Extracts filename from `Content-Disposition` header with regex fallback to `"export.csv"`
- Triggers browser download via hidden anchor element + blob URL pattern
- Cleans up: removes anchor from DOM, revokes blob URL after download
- Error handling reuses `ApiError` class from existing api.ts for consistency
- Files changed: `frontend/src/lib/api.ts` (modified)
- **Learnings:**
  - Browser file download pattern: `fetch → response.blob() → URL.createObjectURL → anchor.click() → URL.revokeObjectURL` is the standard approach
  - Cannot use `apiClient` wrapper for blob downloads since `handleResponse` calls `response.json()` — need raw fetch for binary/blob responses
  - `Content-Disposition` filename regex `filename="?([^";\n]+)"?` handles both quoted and unquoted filenames
---

## 2026-02-08 - S7-007
- Created export page at `frontend/src/app/projects/[id]/onboarding/export/page.tsx`
- Page shows onboarding stepper with Export as active Step 5 (uses same `ONBOARDING_STEPS` config)
- Fetches project info via `useProject` and pages with approval status via `useContentGenerationStatus`
- Filters to approved+complete pages, shows checkboxes for page selection (all selected by default)
- "Export includes" info box listing Matrixify columns (Handle, Title, Body HTML, Meta description)
- Download button calls `exportProject()` from api.ts with selected page IDs
- Select all / deselect all with indeterminate checkbox state
- Navigation: Back to Content, Finish Onboarding
- Matches tropical oasis design system (palm, sand, coral palette, rounded-sm corners)
- Files changed: `frontend/src/app/projects/[id]/onboarding/export/page.tsx` (new)
- **Learnings:**
  - `useContentGenerationStatus` hook (not `useContentGeneration`) is the right hook for read-only page status — it's a simpler query-only hook without generation mutation logic
  - Checkbox indeterminate state requires a ref callback: `ref={(el) => { if (el) el.indeterminate = someSelected; }}` since React doesn't support `indeterminate` as a JSX prop
  - Initializing selection state from async data uses a `!initialized` guard pattern to set defaults once on first data load without re-triggering on re-renders
---

## 2026-02-08 - S7-008
- Updated export page to show ALL project pages (not just approved ones) in the page selection list
- Unapproved/incomplete pages now appear with disabled checkbox, muted opacity (opacity-50), cursor-not-allowed, and dimmed text colors
- Added "Not approved" label badge (bg-cream-200, text-warm-gray-500) for unapproved rows alongside existing "Approved" badge for approved rows
- Empty state updated from "No Approved Pages" to "No Pages Found" since we now show all pages
- Select all / deselect all toggle still only operates on approved pages (disabled checkboxes unaffected)
- Files changed: `frontend/src/app/projects/[id]/onboarding/export/page.tsx` (modified)
- **Learnings:**
  - S7-007 had already built most of the page selection component; S7-008 specifically required showing unapproved pages as disabled/muted rows rather than filtering them out
  - Using `opacity-50` on the row container plus `disabled` prop on checkbox provides clean visual distinction without extra CSS
  - The `allPages` vs `approvedPages` split keeps selection logic clean — `toggleAll` and `togglePage` only operate on approved page IDs while the list renders everything
---
