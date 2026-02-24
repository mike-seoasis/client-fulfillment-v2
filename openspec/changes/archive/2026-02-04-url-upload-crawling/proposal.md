## Why

Phase 2 established brand configuration. Now users need to upload the collection page URLs they want to optimize. This is the entry point for the onboarding workflow—without URLs to crawl, there's nothing to generate content for.

## What Changes

- Add URL upload interface (paste URLs or upload CSV file)
- Build crawling pipeline to extract page data (title, meta, content, headings, products)
- Generate semantic labels per page (for internal linking in later phases)
- Display crawl progress and results with success/failure status
- Store crawled data for use in keyword generation (Phase 4)

## Capabilities

### New Capabilities

- `url-upload`: Interface for submitting URLs to process. Supports pasting URLs (one per line) and CSV file upload. Validates URL format, shows preview list, allows removal before starting crawl.

- `page-crawling`: Background service that crawls submitted URLs and extracts structured data. Extracts: page title, meta description, body content, H1/H2/H3 structure, product count.

- `label-taxonomy`: Two-step labeling system for consistent internal linking. Step 1: After all pages are crawled, analyze them together to generate a unified project-wide taxonomy (e.g., "running", "women", "trail", "waterproof"). Step 2: Assign 2-5 labels from that taxonomy to each page. This ensures label consistency across pages—critical for the internal linking algorithm in later phases.

- `crawl-results`: UI for viewing crawl progress and results. Shows real-time progress (X of Y), per-URL status (pending/crawling/complete/failed), extracted data summary. After crawling completes, shows taxonomy generation status and per-page label assignments (editable from taxonomy).

### Modified Capabilities

- `project-detail-view`: Add "Onboarding" section with URL upload entry point and crawl status display.

## Impact

**Backend:**
- New models: `CrawledPage`, `LabelTaxonomy`, `PageLabel`
- New services: `CrawlingService`, `LabelTaxonomyService` (uses existing `CircuitBreaker` pattern)
- New API endpoints: `POST /projects/{id}/urls`, `GET /projects/{id}/crawl-status`, `GET /projects/{id}/pages`, `GET /projects/{id}/taxonomy`, `PUT /projects/{id}/pages/{page_id}/labels`
- Integration: Web scraping (httpx + BeautifulSoup or similar), Claude for taxonomy generation

**Frontend:**
- New components: `UrlUploader`, `CrawlProgress`, `CrawlResults`
- New pages: `/projects/[id]/onboarding/upload`, `/projects/[id]/onboarding/crawl`
- Modified: Project detail page to show onboarding section

**Dependencies:**
- Web scraping library (httpx already available, need HTML parser)
- Background task processing (FastAPI BackgroundTasks)
