## Why

Phase 5 generates content but the output is read-only. The operations team has no way to edit AI-generated copy, fix flagged AI trope violations, verify LSI term placement, or approve content for export. This phase closes the loop between generation and export by giving the team a rich editing + approval interface.

## What Changes

- **New: Content editor page** — Full editing page for a single page's content with Lexical rich text editor for bottom description, plain inputs for title/meta/top description, HTML/rendered toggle, and auto-save
- **New: Four-layer keyword highlighting** — Primary keyword exact match (solid gold), primary keyword variations (lighter gold, dashed underline), LSI terms from POP brief (lagoon), AI trope violations (coral wavy underline) all visible inline in the editor with toggle controls. Keywords + variations toggle together but are visually distinct so the reviewer can tell exact matches from partial ones at a glance.
- **New: Live stats sidebar** — Right-side panel showing word count, heading count vs targets, keyword density, keyword variation count, LSI term checklist (found/missing with occurrence counts), heading outline, and quality check results with jump-to-violation
- **New: Content approval workflow** — `is_approved` field on PageContent, approve/unapprove endpoints, approve button in editor, approval status on content list page
- **New: Content update API** — PUT endpoint to save edited content fields, POST endpoint to re-run quality checks after edits
- **New: Content review list** — Updated content list page showing approval status, QA pass/fail, and review links per row with bulk approve capability
- **New: Lexical editor integration** — Lexical rich text editor for the bottom description field with custom decorator nodes for keyword/LSI/trope highlighting, HTML serialization, and read-only mode toggle

## Capabilities

### New Capabilities
- `content-editing`: Backend API for updating content fields, approval workflow, re-running quality checks, and content field validation
- `content-editor-ui`: Frontend content editor page with Lexical rich text editor, keyword highlighting, stats sidebar, and approval controls
- `content-review-list`: Frontend content list page with approval status, QA results, and bulk approve

### Modified Capabilities
- `content-generation-api`: Add PUT endpoint for content updates, POST for approval, POST for re-run checks; add `is_approved` and `approved_at` fields to PageContent response schema
- `content-generation-ui`: Update content list page to show approval status column and link to editor instead of read-only view

## Impact

- **Database**: Alembic migration adding `is_approved` (boolean), `approved_at` (datetime) to `page_contents` table
- **Backend API**: 3 new endpoints (update content, approve/unapprove, re-run checks) in content_generation router
- **Backend schemas**: New `ContentUpdateRequest` schema, updated `PageContentResponse` with approval fields
- **Frontend dependencies**: New dependency on `lexical` + `@lexical/react` + `@lexical/html` packages
- **Frontend pages**: New content editor page, modified content list page
- **Frontend hooks**: New mutations for update, approve, re-run checks
- **Wireframe reference**: `wireframes/phase6-content-editor.html`
