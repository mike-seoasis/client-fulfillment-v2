## Context

Phase 6 (Content Review + Editing) is complete. Users can generate, review, edit, and approve content for all crawled pages. The final step in the onboarding workflow is exporting that approved content so it can be bulk-imported into Shopify via Matrixify.

The frontend already has "Export" as Step 5 in the onboarding stepper across all pages, and the content list page already has a "Continue to Export" button that navigates to `/projects/{id}/onboarding/export` — the route just doesn't exist yet.

**Current data flow:** CrawledPage (URL) → PageKeywords (primary keyword) → PageContent (page_title, meta_description, top_description, bottom_description, is_approved).

## Goals / Non-Goals

**Goals:**
- Generate a Matrixify-compatible CSV for Shopify collection page imports
- Let users select which approved pages to include in the export
- Provide a clean download experience (browser file download)
- Complete the onboarding workflow (Step 5 of 5)

**Non-Goals:**
- XLSX format (user requested CSV)
- Exporting unapproved/incomplete content
- Matrixify product import (this is collection pages only)
- Direct Shopify API integration (Matrixify handles the upload)
- Export history or versioning

## Decisions

### 1. CSV generation: Python stdlib `csv` module
**Rationale:** No external dependencies needed. The export is a flat table with 5-6 columns and typically <100 rows. `csv.writer` with `StringIO` is simple and fast.
**Alternative considered:** `pandas.to_csv()` — overkill for this use case, adds a heavy dependency.

### 2. Handle extraction: Parse URL path for `/collections/` slug
**Rationale:** Matrixify uses the Shopify "Handle" field to match collections. For a URL like `https://store.com/collections/running-shoes`, the handle is `running-shoes`. We strip the `/collections/` prefix from the URL path. If the URL doesn't contain `/collections/`, use the last path segment.
**Alternative considered:** Storing handles as a separate field — unnecessary since we can derive them deterministically from the URL.

### 3. Top Description as custom metafield column
**Rationale:** Shopify collections have Title, Body HTML, and SEO Description natively, but no "Top Description" field. Matrixify supports custom metafield columns with the header format `Metafield: custom.top_description [single_line_text_field]`. This lets the Shopify theme reference `collection.metafields.custom.top_description`.
**Alternative considered:** Concatenating top + bottom description into Body HTML — loses the separation the user needs for above/below-fold placement.

### 4. API endpoint returns CSV as file download (not JSON)
**Rationale:** The endpoint sets `Content-Type: text/csv` and `Content-Disposition: attachment` headers so the browser triggers a native file download. No need to store the file server-side.
**Alternative considered:** Generate file server-side, return URL — adds complexity (storage, cleanup) for no benefit.

### 5. Frontend uses fetch + blob for download
**Rationale:** TanStack Query is designed for JSON data fetching, not file downloads. A direct `fetch()` call that creates a blob URL and clicks a hidden anchor is the standard pattern for browser file downloads. Simple, well-supported.
**Alternative considered:** TanStack Query mutation — awkward for binary responses.

### 6. Export page shows all pages, only approved are selectable
**Rationale:** Users should see the full picture of what's ready vs. not ready. Unapproved pages appear grayed out with a status indicator, so the user knows they need to go back and approve them if they want to include them.

## Risks / Trade-offs

- **[Risk] URL handle extraction fails for non-standard URLs** → Mitigation: Fallback to last path segment of any URL. Log a warning if `/collections/` prefix not found.
- **[Risk] Large exports (100+ pages) slow to generate** → Mitigation: CSV generation is string concatenation — even 1000 rows is <100ms. Not a real concern.
- **[Risk] HTML in Body column breaks CSV parsing** → Mitigation: Python `csv.writer` handles quoting/escaping automatically per RFC 4180.
- **[Trade-off] No export history** → Acceptable for MVP. Users can re-export anytime. History adds complexity without clear value.
