## 1. Backend: Export Service

- [ ] 1.1 Create `backend/app/services/export.py` with handle extraction utility (parse URL → Shopify handle, with `/collections/` prefix detection and fallback to last path segment)
- [ ] 1.2 Add CSV generation function: query approved PageContent + CrawledPage, build CSV with columns Handle, Title, Body (HTML), SEO Description, Metafield: custom.top_description [single_line_text_field]. Use Python stdlib `csv` + `StringIO`, include UTF-8 BOM
- [ ] 1.3 Add filename sanitization utility (project name → alphanumeric + hyphens)

## 2. Backend: API Endpoint

- [ ] 2.1 Create export endpoint `GET /api/v1/projects/{project_id}/export` with optional `page_ids` query parameter (comma-separated UUIDs)
- [ ] 2.2 Return CSV as file download with proper headers (`Content-Type: text/csv`, `Content-Disposition: attachment`)
- [ ] 2.3 Handle edge cases: no approved pages → 400, invalid project → 404, non-approved page_ids silently skipped

## 3. Backend: Tests

- [ ] 3.1 Unit tests for handle extraction (standard URL, no /collections/ prefix, query params, trailing slash, nested paths)
- [ ] 3.2 Unit tests for CSV generation (all fields populated, null fields → empty string, filename sanitization)
- [ ] 3.3 Integration test for export endpoint (with page_ids filter, without filter, no approved pages, mixed approved/unapproved)

## 4. Frontend: API Client

- [ ] 4.1 Add `exportProject(projectId: string, pageIds?: string[])` function to `frontend/src/lib/api.ts` that fetches the CSV endpoint and triggers a browser file download via blob URL

## 5. Frontend: Export Page

- [ ] 5.1 Create route at `frontend/src/app/projects/[id]/onboarding/export/page.tsx`
- [ ] 5.2 Fetch project pages with content approval status on page load
- [ ] 5.3 Build page selection list: checkboxes for each page (URL path displayed), approved pages checked by default, unapproved pages disabled and visually muted
- [ ] 5.4 Export summary section: selected page count, exported fields list, format indicator ("CSV - Matrixify compatible")
- [ ] 5.5 "Download Export" button: calls export API with selected page IDs, disabled when none selected, loading state during download
- [ ] 5.6 "Back" link to content list page, "Finish Onboarding" button navigates to project detail

## 6. Verification

- [ ] 6.1 Manual test: create project with approved content, navigate through onboarding to export, download CSV, verify columns and data are correct
- [ ] 6.2 Verify CSV imports correctly into a Matrixify test (or at minimum, opens correctly in Excel/Google Sheets with proper column separation)
- [ ] 6.3 Update V2_REBUILD_PLAN.md: mark Phase 7 checkboxes complete, update status and session log
