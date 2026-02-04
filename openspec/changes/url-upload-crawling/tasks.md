## 1. Database & Models

- [ ] 1.1 Add new fields to CrawledPage model (status, meta_description, body_content, headings, product_count, crawl_error, word_count)
- [ ] 1.2 Create Alembic migration for CrawledPage field additions
- [ ] 1.3 Add crawl_concurrency setting to config.py with CRAWL_CONCURRENCY env var (default 5)
- [ ] 1.4 Create Pydantic schemas for CrawledPage (create, response, status)

## 2. Crawling Service

- [ ] 2.1 Create CrawlingService class with parallel crawl method using asyncio.Semaphore
- [ ] 2.2 Implement content extraction (title, meta_description, headings from HTML)
- [ ] 2.3 Implement body_content extraction from Crawl4AI markdown with truncation
- [ ] 2.4 Implement product_count extraction for Shopify collection pages
- [ ] 2.5 Add word_count calculation
- [ ] 2.6 Write unit tests for CrawlingService

## 3. Label Taxonomy Service

- [ ] 3.1 Create LabelTaxonomyService class
- [ ] 3.2 Implement taxonomy generation prompt for Claude (analyze all pages, generate 10-30 labels)
- [ ] 3.3 Implement label assignment prompt for Claude (assign 2-5 labels per page from taxonomy)
- [ ] 3.4 Add taxonomy storage in Project.phase_status.onboarding.taxonomy
- [ ] 3.5 Implement label validation (must be from taxonomy, 2-5 per page)
- [ ] 3.6 Write unit tests for LabelTaxonomyService

## 4. API Endpoints

- [ ] 4.1 Create POST /projects/{id}/urls endpoint (accept URLs, create CrawledPage records, start background task)
- [ ] 4.2 Create GET /projects/{id}/crawl-status endpoint (return progress and per-page status)
- [ ] 4.3 Create GET /projects/{id}/pages endpoint (list pages with labels)
- [ ] 4.4 Create GET /projects/{id}/taxonomy endpoint (return taxonomy labels)
- [ ] 4.5 Create PUT /projects/{id}/pages/{page_id}/labels endpoint (update page labels with validation)
- [ ] 4.6 Create POST /projects/{id}/pages/{page_id}/retry endpoint (retry failed crawl)
- [ ] 4.7 Write API integration tests for all endpoints

## 5. Frontend - URL Upload Page

- [ ] 5.1 Create /projects/[id]/onboarding/upload route
- [ ] 5.2 Build UrlUploader component with textarea for pasting URLs
- [ ] 5.3 Add CSV file upload with drag-and-drop support
- [ ] 5.4 Implement URL parsing, validation, and normalization
- [ ] 5.5 Build URL preview list with remove buttons and validation status
- [ ] 5.6 Add domain warning for URLs not matching project site_url
- [ ] 5.7 Implement Start Crawl button that POSTs to API and navigates to crawl page
- [ ] 5.8 Write component tests for UrlUploader

## 6. Frontend - Crawl Progress Page

- [ ] 6.1 Create /projects/[id]/onboarding/crawl route
- [ ] 6.2 Build CrawlProgress component with overall progress bar
- [ ] 6.3 Build page list with per-page status (pending/crawling/completed/failed)
- [ ] 6.4 Add extracted data summary display (title, word count, headings, products)
- [ ] 6.5 Implement polling with 2-second interval that stops when complete
- [ ] 6.6 Add retry button for failed pages
- [ ] 6.7 Write component tests for CrawlProgress

## 7. Frontend - Label Management

- [ ] 7.1 Add taxonomy status display after crawl completes
- [ ] 7.2 Build label tag display for each page
- [ ] 7.3 Create label edit dropdown (multi-select from taxonomy)
- [ ] 7.4 Implement label save with validation feedback
- [ ] 7.5 Add Continue to Keywords button when labeling complete
- [ ] 7.6 Write component tests for label editing

## 8. Frontend - Project Detail Updates

- [ ] 8.1 Update Onboarding section to show crawl progress when pages exist
- [ ] 8.2 Add step indicators (URLs uploaded, Crawled, Labels assigned)
- [ ] 8.3 Update Continue/Start Onboarding button to navigate to correct step
- [ ] 8.4 Add quick stats display (page count, failed count, label status)

## 9. Integration & Polish

- [ ] 9.1 Wire up background task to trigger taxonomy generation after crawl completes
- [ ] 9.2 Update project phase_status through the workflow (crawling → labeling → labels_complete)
- [ ] 9.3 Add error handling and user-friendly error messages throughout
- [ ] 9.4 Manual end-to-end testing of full flow
- [ ] 9.5 Update V2_REBUILD_PLAN.md with Phase 3 completion
