## Why

We want to run Kyle Roof's Lorem Ipsum SEO ranking experiment at scale using the same tooling we already have for client onboarding. The hypothesis: Google ranks pages based on keyword placement in critical SEO signals (title tags, H1s, meta descriptions, schema, URLs), not body copy. By reusing our existing cluster-building, POP brief, and internal linking workflows — but swapping real copy for lorem ipsum body text — we can generate full site content for 8+ exact-match domains from a single local instance, then export everything to an XLSX template for the static site generator.

This needs to be a fully isolated local instance to avoid any risk of contaminating the production database with test content.

## What Changes

- **New content generation mode**: "Lorem Ipsum mode" — follows POP briefs exactly (hitting every keyword target, headline target, LSI term, related question) but fills all body paragraph text with lorem ipsum. Keywords appear only in SEO-critical positions: H1s, H2s, H3s, title tags, meta descriptions, lead sentences, alt text.
- **New XLSX multi-site export**: Dashboard button that exports all projects into a single XLSX file matching the sites-template format — one tab per domain, rows for collection pages and blog posts, with columns for page_type, title, meta_description, h1, top/bottom descriptions, and blog content HTML.
- **Local-only instance configuration**: Separate `.env` profile and docker-compose configuration for running a fully isolated instance with its own PostgreSQL database, no auth requirement, and a visual indicator that this is the "SEO Test" instance (not production).

## Capabilities

### New Capabilities
- `lorem-ipsum-content`: Content generation mode that follows POP briefs for keyword/heading structure but uses lorem ipsum for all body text between SEO-critical elements. Modifies the content writing prompts, not the pipeline architecture.
- `xlsx-site-export`: Multi-site XLSX export that generates one workbook with an instructions tab and one tab per project/domain, mapping cluster pages to collection rows and blog posts to blog rows in the sites-template format.
- `local-seo-instance`: Docker-compose profile and environment configuration for running a fully isolated local instance with its own database, no auth, and visual "SEO Test" branding to distinguish from production.

### Modified Capabilities
- (none — all existing capabilities remain unchanged; new capabilities layer on top)

## Impact

- **Content writing service** (`content_writing.py`, `content_outline.py`): New prompt templates for lorem ipsum mode, toggled by environment variable or project-level setting
- **New API endpoint**: `GET /api/v1/export/xlsx` — generates multi-site XLSX workbook
- **Frontend**: New "Export All Sites (XLSX)" button on main dashboard
- **Docker**: New `docker-compose.seo-test.yml` or compose profile for isolated instance
- **Dependencies**: `openpyxl` added to backend requirements for XLSX generation
- **No database schema changes**: All existing models store the data needed; lorem ipsum content is just different text in the same fields
- **No changes to production instance**: This is additive — production app is completely unaffected
