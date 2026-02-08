## 1. Database & Model Layer

- [ ] 1.1 Add `is_approved` (Boolean, default=false, indexed) and `approved_at` (DateTime, nullable) fields to PageContent model
- [ ] 1.2 Create Alembic migration for new columns with server defaults
- [ ] 1.3 Run migration and verify columns exist in dev database

## 2. Backend Schemas

- [ ] 2.1 Create `ContentUpdateRequest` schema (optional fields: page_title, meta_description, top_description, bottom_description)
- [ ] 2.2 Update `PageContentResponse` schema to include `is_approved`, `approved_at`, and `brief` object (keyword, lsi_terms, heading_targets, keyword_targets)
- [ ] 2.3 Update `ContentGenerationStatus` schema to include `pages_approved` count
- [ ] 2.4 Create `BulkApproveResponse` schema with `approved_count` field

## 3. Backend API Endpoints

- [ ] 3.1 Add `PUT /projects/{project_id}/pages/{page_id}/content` endpoint — update content fields, recalculate word_count, clear approval on edit
- [ ] 3.2 Add `POST /projects/{project_id}/pages/{page_id}/approve-content` endpoint — toggle is_approved/approved_at, validate status is "complete"
- [ ] 3.3 Add `POST /projects/{project_id}/pages/{page_id}/recheck-content` endpoint — re-run quality checks on current content, return updated qa_results
- [ ] 3.4 Add `POST /projects/{project_id}/bulk-approve-content` endpoint — approve all pages with status=complete and qa_results.passed=true
- [ ] 3.5 Update `GET /pages/{page_id}/content` to join ContentBrief and include lsi_terms, heading_targets, keyword_targets in response
- [ ] 3.6 Update `GET /content-generation-status` to include pages_approved count

## 4. Backend Tests

- [ ] 4.1 Unit tests for content update endpoint (partial update, word count recalc, approval cleared on edit)
- [ ] 4.2 Unit tests for approve/unapprove endpoint (approve, unapprove, reject when not complete)
- [ ] 4.3 Unit tests for recheck endpoint (re-run checks, return updated results)
- [ ] 4.4 Unit tests for bulk approve endpoint (approve eligible, skip already approved, zero eligible)
- [ ] 4.5 Unit tests for updated GET content endpoint (brief data included, null when no brief)
- [ ] 4.6 Integration test: edit content → re-run checks → approve flow

## 5. Frontend Dependencies & API Client

- [ ] 5.1 Install Lexical packages: `lexical`, `@lexical/react`, `@lexical/html`, `@lexical/rich-text`, `@lexical/list`
- [ ] 5.2 Add TypeScript types for updated PageContentResponse (is_approved, approved_at, brief object with lsi_terms/heading_targets/keyword_targets)
- [ ] 5.3 Add API functions: `updatePageContent()`, `approvePageContent()`, `recheckPageContent()`, `bulkApproveContent()`
- [ ] 5.4 Add TanStack Query hooks: `useUpdatePageContent()`, `useApprovePageContent()`, `useRecheckPageContent()`, `useBulkApproveContent()` with cache invalidation

## 6. Lexical Editor Setup

- [ ] 6.1 Create LexicalEditor wrapper component with theme config, initial HTML state from bottom_description, and onChange handler that serializes to HTML
- [ ] 6.2 Create HTML ↔ Lexical state serialization utils (import HTML to editor state, export editor state to HTML)
- [ ] 6.3 Create Rendered/HTML Source tab toggle — Rendered shows Lexical editor, HTML Source shows raw textarea, switching syncs content between them

## 7. Keyword Highlighting System

- [ ] 7.1 Create keyword variation generator utility — splits primary keyword into words, generates common variations (plural/singular: s, es, ing, er, ers), returns Set of variation strings
- [ ] 7.2 Create Lexical highlight plugin that scans text nodes for: exact primary keyword matches, keyword variations, LSI terms, and AI trope violation text ranges
- [ ] 7.3 Implement four highlight CSS styles: `.hl-keyword` (solid gold), `.hl-keyword-var` (lighter gold, dashed), `.hl-lsi` (lagoon tint + border), `.hl-trope` (coral wavy underline)
- [ ] 7.4 Create highlight toggle controls (3 buttons in page header) — "Keywords + Vars" / "LSI Terms" / "Issues" — each toggles visibility of its highlight class
- [ ] 7.5 Add debounced highlight recomputation (200ms after last edit) to avoid jank on rapid typing

## 8. Content Editor Page

- [ ] 8.1 Replace existing read-only `[pageId]/page.tsx` with the content editor page — two-column layout (editor left, sidebar right)
- [ ] 8.2 Build page title field: text input with live character counter (N/70, palm-600 under, coral-600 over)
- [ ] 8.3 Build meta description field: textarea with live character counter (N/160)
- [ ] 8.4 Build top description field: textarea with live word counter
- [ ] 8.5 Build bottom description section: Lexical editor with Rendered/HTML tabs, word count + heading count footer
- [ ] 8.6 Build header: breadcrumb, page URL, primary keyword badge, highlight toggle buttons
- [ ] 8.7 Build bottom action bar (sticky): auto-save indicator, "Re-run Checks" button, "Save Draft" button, "Approve"/"Approved" toggle button

## 9. Stats Sidebar

- [ ] 9.1 Build quality status card: overall pass/fail banner, individual check results list (8 checks with pass/fail per row)
- [ ] 9.2 Build flagged passages section: list violations from qa_results with red dot, description, context quote, and "Jump to" button that scrolls editor to flagged text
- [ ] 9.3 Build content stats section: word count, heading count vs brief targets, exact keyword match count with density bar, variation count with listed words
- [ ] 9.4 Build LSI term checklist: terms from brief with found (green dot + count on hover) vs not found (warm-600 text, "not found" label), clickable found terms scroll to first occurrence, summary "N of M used"
- [ ] 9.5 Build heading outline: mini TOC from H2/H3 headings in bottom description, H3 indented under parent H2

## 10. Auto-Save

- [ ] 10.1 Implement blur-based auto-save: on field blur, if content changed, call PUT update endpoint
- [ ] 10.2 Build auto-save indicator in bottom bar: "Saving..." during save, "Auto-saved {time}" on success, "Save failed — click to retry" on error
- [ ] 10.3 Track dirty state per field to avoid unnecessary saves when content hasn't changed

## 11. Content Review List Updates

- [ ] 11.1 Update content list page to show review columns after generation complete: QA Status (pass/fail icon), Approval Status (badge), "Review" link to editor
- [ ] 11.2 Add approved count summary: "Approved: N of M"
- [ ] 11.3 Add "Approve All Ready" button calling bulk-approve endpoint, disabled when no eligible pages
- [ ] 11.4 Add "Continue to Export" button, enabled only when at least one page is approved

## 12. Verification & Polish

- [ ] 12.1 Frontend component tests for editor page (field rendering, character counts, tab switching)
- [ ] 12.2 Frontend component tests for sidebar (quality display, LSI checklist, stats)
- [ ] 12.3 Manual verification: edit content → re-run checks → approve → verify list page updates
- [ ] 12.4 Update V2_REBUILD_PLAN.md: mark Phase 6 checkboxes, update status, add session log entry
