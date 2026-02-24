## Why

Content generation and review are complete through Phase 6, but there's no way to get the approved content out of the tool and into Shopify. The export step is the final piece of the onboarding workflow — without it, users have to manually copy-paste content field by field. Matrixify CSV import is the standard bulk-update method for Shopify stores.

## What Changes

- New backend service to generate Matrixify-compatible CSV from approved page content
- New API endpoint that returns a CSV file download for selected pages
- New frontend export page (Step 5 of onboarding flow) with page selection and download
- CSV columns: `Handle`, `Title`, `Body (HTML)`, `SEO Description`, `Top Description (Metafield)` — using standard Matrixify collection import format plus a custom metafield for top description
- Only approved pages are exportable; user can uncheck individual pages before downloading

## Capabilities

### New Capabilities
- `matrixify-export`: Backend service for generating Matrixify-compatible CSV files from approved PageContent data. Covers CSV column mapping, handle extraction from URLs, content field formatting, and file download delivery.
- `export-ui`: Frontend export page (onboarding Step 5) with page selection checkboxes, export summary, download button, and finish onboarding flow.

### Modified Capabilities
_(none — this is a new leaf feature that reads existing data without changing any existing specs)_

## Impact

- **Backend**: New `export.py` service, new API endpoint in `projects.py` (or new `export.py` route file), new Pydantic schemas for export request/response
- **Frontend**: New route at `/projects/[id]/onboarding/export`, new API client method, new React components (page selection list, download button)
- **Dependencies**: Python `csv` stdlib module (no new packages needed)
- **Existing code**: The content list page already has a "Continue to Export" button that routes to the export page — just needs the destination to exist
