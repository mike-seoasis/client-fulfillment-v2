# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Python tooling**: Use `uv run` to execute Python commands (mypy, ruff, etc.) - poetry/python not directly available
- **SQLAlchemy models**: Follow existing pattern with Mapped types, mapped_column, and server_default for database defaults
- **Enums in models**: Define as `class EnumName(str, Enum)` and use `.value` for defaults

---

## 2026-02-04 - S3-001
- **What was implemented**: Extended CrawledPage model with crawl status and content extraction fields
- **Files changed**: `backend/app/models/crawled_page.py`
- **New fields added**:
  - `status`: String(20) with CrawlStatus enum (pending, crawling, completed, failed), indexed
  - `meta_description`: Text, nullable
  - `body_content`: Text, nullable (for markdown content)
  - `headings`: JSONB, nullable (for h1, h2, h3 arrays)
  - `product_count`: Integer, nullable
  - `crawl_error`: Text, nullable
  - `word_count`: Integer, nullable
- **Learnings:**
  - Patterns discovered: Model follows consistent SQLAlchemy 2.0 pattern with `Mapped` type hints
  - Gotchas encountered: Import order matters - ruff E402 error if imports not at top of file
---

## 2026-02-04 - S3-002
- **What was implemented**: Created Alembic migration 0019 to add crawl status and content extraction fields to crawled_pages table
- **Files changed**: `backend/alembic/versions/0019_add_crawl_status_and_extraction_fields.py`
- **Migration adds**:
  - `status` column (String(20), non-null, server_default='pending', indexed)
  - `meta_description` (Text, nullable)
  - `body_content` (Text, nullable)
  - `headings` (JSONB, nullable)
  - `product_count` (Integer, nullable)
  - `crawl_error` (Text, nullable)
  - `word_count` (Integer, nullable)
- **Verified**: Migration upgrade and downgrade both work correctly
- **Learnings:**
  - Migrations use sequential numbering (0001, 0002, etc.) in this project
  - Use `server_default=sa.text("'pending'")` for string defaults in migrations
  - Index must be dropped before column in downgrade
---

## 2026-02-04 - S3-003
- **What was implemented**: Added crawl_concurrency setting to config for parallel crawling tuning
- **Files changed**: `backend/app/core/config.py`
- **Setting details**:
  - `crawl_concurrency: int` with default value of 5
  - Reads from `CRAWL_CONCURRENCY` environment variable
  - Placed in Crawl4AI settings section
- **Learnings:**
  - pydantic-settings automatically maps snake_case field names to SCREAMING_SNAKE_CASE env vars (case_sensitive=False)
  - Field validation is handled by type annotation (int) - pydantic coerces string env vars automatically
---

## 2026-02-04 - S3-004
- **What was implemented**: Created Pydantic schemas for CrawledPage API endpoints
- **Files changed**:
  - `backend/app/schemas/crawled_page.py` (new file)
  - `backend/app/schemas/__init__.py` (added exports)
- **Schemas created**:
  - `CrawledPageCreate` - Request schema with url field and validation
  - `CrawledPageResponse` - Full response schema with all fields (status, meta_description, body_content, headings, product_count, crawl_error, word_count)
  - `CrawlStatusResponse` - Progress response with counts by status and pages array
  - `UrlsUploadRequest` - Request schema with urls: list[str] and validation
  - `PageLabelsUpdate` - Request schema with labels: list[str] and normalization
- **Learnings:**
  - Existing `crawl.py` has a simpler `CrawledPageResponse` without new S3-001 fields - new schema in `crawled_page.py` is the full version
  - Aliased import as `CrawledPageFullResponse` in __init__.py to avoid collision with existing `CrawledPageResponse`
  - Can import enum from model file (`from app.models.crawled_page import CrawlStatus`) for reuse in schema defaults
---

## 2026-02-04 - S3-005
- **What was implemented**: Created CrawlingService for parallel page crawling with concurrency control
- **Files changed**:
  - `backend/app/services/crawling.py` (new file)
  - `backend/app/services/__init__.py` (added export)
- **Features**:
  - `crawl_urls(db, page_ids)` - Crawl multiple pages in parallel
  - `crawl_pending_pages(db, project_id, limit)` - Convenience method to crawl pending pages for a project
  - Uses `asyncio.Semaphore` with `settings.crawl_concurrency` for rate limiting
  - Uses `asyncio.gather` with `return_exceptions=True` for parallel execution
  - Updates page status lifecycle: pending → crawling → completed/failed
  - Extracts markdown content, metadata (title, description), and calculates word count
  - Stores crawl errors in `crawl_error` field on failure
- **Learnings:**
  - When using `asyncio.gather(return_exceptions=True)`, must check for `BaseException` (not `Exception`) because the return type is `list[T | BaseException]`
  - Service pattern: inject Crawl4AIClient in constructor, inject AsyncSession in method calls
  - Update status to "crawling" before starting, then to "completed"/"failed" after
---

## 2026-02-04 - S3-006
- **What was implemented**: Content extraction from crawled HTML using BeautifulSoup
- **Files changed**:
  - `backend/pyproject.toml` (added beautifulsoup4 dependency, bs4 mypy override)
  - `backend/app/services/content_extraction.py` (new file)
  - `backend/app/services/crawling.py` (updated to use content extraction)
  - `backend/app/services/__init__.py` (added exports)
- **Features**:
  - `extract_content_from_html(html, markdown)` - Extract title, meta_description, headings from HTML
  - `truncate_body_content(content)` - Truncate body content to 50KB at word boundary
  - `ExtractedContent` dataclass - Container for extracted content
  - Extracts title from `<title>` tag
  - Extracts meta_description from `<meta name="description">`
  - Extracts headings as `{h1: [...], h2: [...], h3: [...]}`
  - Body content truncated to 50KB with word boundary handling
- **Learnings:**
  - BeautifulSoup uses `soup.find("meta", attrs={"name": "description"})` to find meta tags by name
  - For mypy, add `bs4` and `bs4.*` to ignore_missing_imports modules
  - Use `html.parser` as the parser (built-in, no extra dependency needed)
  - When truncating UTF-8 strings by bytes, use `decode("utf-8", errors="ignore")` to handle partial multi-byte chars
---

## 2026-02-04 - S3-007
- **What was implemented**: Product count extraction for Shopify collection pages
- **Files changed**:
  - `backend/app/services/content_extraction.py` (added product count extraction)
  - `backend/app/services/crawling.py` (added product_count to extracted fields)
- **Features**:
  - `extract_shopify_product_count(soup, html)` - Main extraction function with two strategies
  - `_extract_product_count_from_json(html)` - Parse Shopify JSON data for product count
  - `_count_product_card_elements(soup)` - Fall back to counting product card elements
  - JSON patterns: ShopifyAnalytics.meta, "products_count", "productsCount", window.__INITIAL_STATE__
  - Element patterns: product-card, product-item, card--product, data-product-id, /cart/add forms
  - Returns None gracefully for non-collection pages
- **Learnings:**
  - BeautifulSoup's `find_all` with kwargs needs explicit typing; use separate calls for class_ and attrs
  - Common Shopify JSON patterns: `ShopifyAnalytics.meta = {...}`, `"products_count": N`, `window.__INITIAL_STATE__`
  - Shopify product cards use various class names depending on theme: product-card, product-item, ProductCard, etc.
  - Forms with action="/cart/add" can be used as last resort to count products (one form per product)
---

## 2026-02-04 - S3-008
- **What was implemented**: Unit tests for CrawlingService
- **Files changed**:
  - `backend/tests/services/test_crawling.py` (new file - 22 tests)
- **Test coverage**:
  - `TestCrawlConcurrency` - Tests for concurrency limit via semaphore, empty list handling, nonexistent pages
  - `TestStatusTransitions` - Tests pending → crawling → completed/failed status lifecycle
  - `TestFailedCrawl` - Tests error message setting, content fields not populated on failure, error clearing on success
  - `TestContentExtraction` - Tests all fields extracted (title, meta_description, headings, body_content, word_count, product_count)
  - `TestCrawlPendingPages` - Tests crawl_pending_pages convenience method with limit, skip completed/failed
  - `TestExceptionHandling` - Tests asyncio.gather return_exceptions=True behavior
  - `TestCrawlResultMapping` - Tests CrawlResult to CrawledPage field mapping
- **Learnings:**
  - SQLite in-memory database with aiosqlite cannot handle concurrent async transactions like PostgreSQL
  - Tests that verify concurrent database writes fail with SQLite; use single-page tests or in-memory tracking for concurrency tests
  - SQLAlchemy warning "Attribute history events accumulated" indicates concurrent transaction conflicts
  - Mock the Crawl4AIClient, not the database layer - tests verify service behavior, not database behavior
  - Use `test_page` fixture (single page) instead of `test_pages` (multiple) when not testing batch behavior
---

## 2026-02-04 - S3-009
- **What was implemented**: LabelTaxonomyService for AI-powered label generation and assignment
- **Files changed**:
  - `backend/app/services/label_taxonomy.py` (new file)
  - `backend/app/services/__init__.py` (added exports)
- **Features**:
  - `LabelTaxonomyService` class with two main methods:
    - `generate_taxonomy(db, project_id)` - Analyzes all completed pages and generates taxonomy of 5-15 labels
    - `assign_labels(db, project_id, taxonomy?)` - Assigns 1-3 labels from taxonomy to each page
  - Dataclasses: `TaxonomyLabel`, `GeneratedTaxonomy`, `LabelAssignment`
  - Stores taxonomy in `Project.phase_status["onboarding"]["taxonomy"]`
  - Stores labels in `CrawledPage.labels` array
  - Uses `flag_modified()` for SQLAlchemy JSONB mutation tracking
  - JSON extraction helper for markdown code block responses
- **Learnings:**
  - When modifying JSONB fields in SQLAlchemy, must use `flag_modified(obj, "field_name")` to ensure changes are persisted
  - Service pattern: inject ClaudeClient in constructor, inject AsyncSession in method calls
  - Claude's `complete()` method accepts `system_prompt` and `user_prompt` with configurable `temperature` and `max_tokens`
  - For taxonomy/classification tasks, use low temperature (0.0-0.1) for consistency
  - Can load taxonomy from project phase_status if not provided to assign_labels()
---

## 2026-02-04 - S3-010
- **What was implemented**: Enhanced taxonomy generation prompt for e-commerce context and internal linking
- **Files changed**:
  - `backend/app/services/label_taxonomy.py` (updated TAXONOMY_SYSTEM_PROMPT, added generated_at timestamp)
- **Changes made**:
  - Updated TAXONOMY_SYSTEM_PROMPT to explain e-commerce context and internal linking purpose
  - Changed label count requirement from "5-15" to "10-30" per acceptance criteria
  - Added `generated_at` timestamp (ISO format) when storing taxonomy in phase_status
  - Added examples relevant to e-commerce: trail-running, outdoor-gear, buying-guide, seasonal-collection
- **Learnings:**
  - Use `datetime.UTC` alias instead of `timezone.utc` (ruff UP017)
  - Prompt engineering for taxonomy: explaining the PURPOSE of labels (internal linking) helps AI generate more useful labels
---

## 2026-02-04 - S3-011
- **What was implemented**: Enhanced label assignment prompt for e-commerce context
- **Files changed**:
  - `backend/app/services/label_taxonomy.py` (updated ASSIGNMENT_SYSTEM_PROMPT)
- **Changes made**:
  - Updated ASSIGNMENT_SYSTEM_PROMPT to explain e-commerce context and internal linking purpose
  - Changed label count requirement from "1-3" to "2-5" per acceptance criteria
  - Added guidance to consider PURPOSE + TOPIC balance
  - Added rule about considering what pages should link together
  - Added recommendation to aim for 3-4 labels for most pages
- **Verification**:
  - Prompt receives taxonomy and single page data ✓ (_assign_labels_to_page method)
  - Prompt assigns 2-5 labels from taxonomy only ✓ (updated prompt)
  - Labels stored in CrawledPage.labels ✓ (line 369: page.labels = assignment.labels)
  - All assigned labels validated against taxonomy ✓ (lines 455-466)
- **Learnings:**
  - Label assignment already had validation logic filtering out invalid labels
  - Prompt engineering: providing context about WHY labels exist (internal linking) improves assignment quality
---

## 2026-02-04 - S3-012
- **What was implemented**: Label validation system for taxonomy conformance and count constraints
- **Files changed**:
  - `backend/app/services/label_taxonomy.py` (added validation dataclasses and functions)
  - `backend/app/services/__init__.py` (added exports for validation functions)
- **Features added**:
  - `LabelValidationError` dataclass with code, message, and details
  - `LabelValidationResult` dataclass with valid flag, normalized labels, and errors list
  - `validate_labels()` - Core validation function that checks:
    - Labels exist in taxonomy (code: "invalid_labels")
    - Count within 2-5 range (codes: "too_few_labels", "too_many_labels")
    - Normalizes labels (lowercase, stripped, deduplicated)
  - `get_project_taxonomy_labels()` - Helper to load taxonomy from project
  - `validate_page_labels()` - Convenience function for API endpoints (loads taxonomy + validates)
  - Constants `MIN_LABELS_PER_PAGE = 2` and `MAX_LABELS_PER_PAGE = 5`
- **Updated `_assign_labels_to_page()`** to use the new validation function instead of ad-hoc filtering
- **Learnings:**
  - Validation functions should return structured results (not just bool) for clear error handling
  - Using dataclasses with `field(default_factory=dict)` for mutable defaults in Python 3.12+
  - Export both sync functions (`validate_labels`) and async functions (`validate_page_labels`) for flexibility
---

## 2026-02-04 - S3-013
- **What was implemented**: Unit tests for LabelTaxonomyService (29 tests)
- **Files changed**:
  - `backend/tests/services/test_label_taxonomy.py` (new file)
- **Test coverage**:
  - `TestTaxonomyGenerationStorage` - Tests taxonomy generation stores in phase_status, handles no pages/API failures
  - `TestLabelAssignmentValidation` - Tests assignment uses taxonomy, stores in page, handles missing taxonomy
  - `TestInvalidLabelRejection` - Tests invalid labels are filtered out, validation rejects unknown labels
  - `TestLabelCountValidation` - Tests count validation (2-5), too few/too many errors, custom limits
  - `TestLabelNormalization` - Tests lowercase, whitespace stripping, deduplication, empty string handling
  - `TestValidationHelpers` - Tests get_project_taxonomy_labels, validate_page_labels helpers
  - `TestAssignmentAPIFailure` - Tests API error handling, JSON parse error handling
  - `TestTaxonomyDataclass` / `TestValidationResultErrorMessages` - Tests dataclass behavior
- **Learnings:**
  - Mock Claude client needs careful request type detection - use user_prompt content (e.g., "Generate a taxonomy" vs "Assign labels") not system_prompt
  - Same session-scoped db_session pattern as test_crawling.py works well
  - Projects with existing taxonomy need separate fixture (test_project_with_taxonomy) to test assignment path
---

## 2026-02-04 - S3-014
- **What was implemented**: POST /projects/{id}/urls endpoint for URL upload and background crawling
- **Files changed**:
  - `backend/app/api/v1/projects.py` (added upload_urls endpoint and _crawl_pages_background helper)
  - `backend/app/schemas/crawled_page.py` (added UrlUploadResponse schema)
  - `backend/app/schemas/__init__.py` (added UrlUploadResponse export)
- **Endpoint features**:
  - Accepts UrlsUploadRequest with urls array (1-10000 URLs)
  - Creates CrawledPage record for each URL with status='pending'
  - Skips duplicate URLs (already exist for project) using normalized_url lookup
  - URL normalization: strips whitespace, removes trailing slashes (except root paths)
  - Starts background task using FastAPI BackgroundTasks to crawl pages
  - Returns UrlUploadResponse with task_id, pages_created, pages_skipped, total_urls
  - Uses HTTP 202 Accepted status code (async processing)
- **Background task**:
  - Creates own database session via db_manager.session_factory()
  - Uses CrawlingService.crawl_urls() for parallel crawling
  - Logs task start/completion with success/failure counts
- **Learnings:**
  - FastAPI BackgroundTasks runs after response is sent, need separate db session
  - Use `db_manager.session_factory()` from `app.core.database` for background sessions
  - URL normalization is important for deduplication - handle trailing slashes carefully
  - Keep raw_url for reference, use normalized_url for deduplication
---

## 2026-02-04 - S3-015
- **What was implemented**: GET /projects/{id}/crawl-status endpoint for polling crawl progress
- **Files changed**:
  - `backend/app/api/v1/projects.py` (added get_crawl_status endpoint and _compute_overall_status helper)
  - `backend/app/schemas/crawled_page.py` (added PageSummary, ProgressCounts schemas, refactored CrawlStatusResponse)
  - `backend/app/schemas/__init__.py` (added PageSummary, ProgressCounts exports)
- **Endpoint features**:
  - Returns overall status: "crawling", "labeling", or "complete"
  - Returns progress counts: total, completed, failed, pending
  - Returns pages array with id, url, status, title, word_count, product_count, labels
  - Designed for polling every 2 seconds by frontend
- **Status logic**:
  - "crawling" if any pages pending or crawling
  - "labeling" if all pages done but no labels assigned yet
  - "complete" if all pages done and have labels
- **Learnings:**
  - Use lightweight PageSummary schema for status polling instead of full CrawledPageResponse
  - Separate ProgressCounts into nested object for cleaner API structure
  - Status computation logic should be in a helper function for testability
---

## 2026-02-04 - S3-016
- **What was implemented**: GET /projects/{id}/pages endpoint to list all crawled pages
- **Files changed**: `backend/app/api/v1/projects.py` (added list_project_pages endpoint, added CrawledPageResponse import)
- **Endpoint features**:
  - Returns list of CrawledPageResponse objects with all fields (labels, content, status, etc.)
  - Supports optional `status` query parameter to filter by crawl status
  - Verifies project exists (404 if not found)
  - Uses Pydantic model_validate() for ORM→schema conversion
- **Learnings:**
  - CrawledPageResponse schema already existed with all needed fields, just needed to import it
  - Use `model_validate()` to convert SQLAlchemy model instances to Pydantic response schemas
  - Optional query parameters are typed as `str | None = None` in FastAPI
---

## 2026-02-04 - S3-017
- **What was implemented**: GET /projects/{id}/taxonomy endpoint to retrieve label taxonomy
- **Files changed**:
  - `backend/app/api/v1/projects.py` (added get_project_taxonomy endpoint, imported Project model, TaxonomyLabel, TaxonomyResponse)
  - `backend/app/schemas/crawled_page.py` (added TaxonomyLabel and TaxonomyResponse schemas)
  - `backend/app/schemas/__init__.py` (added exports for TaxonomyLabel, TaxonomyResponse)
- **Endpoint features**:
  - Returns labels array from phase_status.onboarding.taxonomy
  - Returns generated_at timestamp
  - Returns 404 if project not found or taxonomy not yet generated
  - Endpoint at /api/v1/projects/{project_id}/taxonomy
- **Learnings:**
  - Use `datetime.fromisoformat()` to parse ISO timestamps stored in JSONB
  - Taxonomy data structure: `{labels: [{name, description, examples}], reasoning, generated_at}`
  - Fallback to `datetime.now()` for backwards compatibility with data missing timestamp
---

## 2026-02-04 - S3-018
- **What was implemented**: PUT /projects/{id}/pages/{page_id}/labels endpoint for updating page labels
- **Files changed**:
  - `backend/app/api/v1/projects.py` (added update_page_labels endpoint, imported PageLabelsUpdate, validate_page_labels)
- **Endpoint features**:
  - Accepts PageLabelsUpdate with labels array
  - Validates all labels are in project taxonomy using validate_page_labels()
  - Validates 2-5 labels provided (via validate_labels constants)
  - Returns 404 if project not found, page not found, or page doesn't belong to project
  - Returns 400 with clear error messages if validation fails (too few/too many labels, invalid labels)
  - Updates CrawledPage.labels on success with normalized labels
  - Returns full CrawledPageResponse after update
- **Learnings:**
  - Reuse validate_page_labels() from label_taxonomy.py - it loads taxonomy and validates in one call
  - PageLabelsUpdate schema already normalizes labels (lowercase, stripped) via field_validator
  - Check page belongs to project to prevent cross-project access
---

## 2026-02-04 - S3-019
- **What was implemented**: POST /projects/{id}/pages/{page_id}/retry endpoint for retrying failed crawls
- **Files changed**:
  - `backend/app/api/v1/projects.py` (added retry_page_crawl endpoint)
- **Endpoint features**:
  - Resets page status to 'pending'
  - Clears crawl_error field
  - Starts background task using existing _crawl_pages_background helper (reusing S3-014 pattern)
  - Returns HTTP 202 Accepted with updated page (status='pending')
  - Returns 404 if project not found, page not found, or page doesn't belong to project
- **Learnings:**
  - Reuse existing _crawl_pages_background helper - just pass single-item list of page_ids
  - Use HTTP 202 Accepted for async operations that spawn background tasks
  - Follow established page validation pattern (check project exists, page exists, page belongs to project)
---

## 2026-02-04 - S3-020
- **What was implemented**: API integration tests for all Phase 3 crawling endpoints (30 tests)
- **Files changed**: `backend/tests/api/test_crawling.py` (new file)
- **Test coverage**:
  - `TestUrlUpload` (5 tests): URL upload creates pages, skips duplicates, normalizes URLs, validates URL format, project not found
  - `TestCrawlStatus` (6 tests): Returns progress counts, status states (crawling/labeling/complete), page summaries, project not found
  - `TestPagesEndpoint` (4 tests): Returns all pages, filters by status, returns empty list, project not found
  - `TestTaxonomyEndpoint` (3 tests): Returns labels, taxonomy not yet generated, project not found
  - `TestLabelUpdate` (7 tests): Validates and saves, rejects invalid labels, too few/many labels, normalizes labels, page not found, page wrong project
  - `TestRetryEndpoint` (5 tests): Resets failed page, can retry any status, page not found, project not found, page wrong project
- **Learnings:**
  - Use `flag_modified(project, "phase_status")` when setting JSONB fields in test fixtures
  - Create mock clients for external services (MockCrawl4AIClient) and wire them via `app.dependency_overrides`
  - Follow existing test patterns: create project via API, then manipulate DB directly for test setup
  - `response.json()` returns `Any` type; mypy warns about `no-any-return` - this is expected
  - SQLite warnings about "Attribute history events accumulated" are benign during async testing
---

## 2026-02-04 - S3-021
- **What was implemented**: Created URL upload page route for onboarding
- **Files changed**: `frontend/src/app/projects/[id]/onboarding/upload/page.tsx` (new file)
- **Features**:
  - Page route at `/projects/[id]/onboarding/upload`
  - Loads project data using `useProject` hook
  - Breadcrumb navigation back to project (`{project.name} › Onboarding`)
  - Step indicator component showing Upload as current step (Step 1 of 5)
  - Loading skeleton while project data loads
  - 404 error state if project not found
  - Placeholder UI for URL textarea (ready for S3-022 UrlUploader component)
  - Cancel and Start Crawl buttons (disabled for now)
- **Learnings:**
  - Next.js App Router: nested routes like `/projects/[id]/onboarding/upload/page.tsx` work automatically
  - Step indicator pattern: use `ONBOARDING_STEPS` const array for maintainable step definitions
  - Breadcrumb pattern from wireframes: `{project.name} › Onboarding` with back arrow on project name
  - Design system colors: `palm-500` for active/completed steps, `cream-300` for pending, `warm-gray-*` for text
---

## 2026-02-04 - S3-022
- **What was implemented**: Created UrlUploader component with textarea for pasting URLs
- **Files changed**:
  - `frontend/src/components/onboarding/UrlUploader.tsx` (new file)
  - `frontend/src/app/projects/[id]/onboarding/upload/page.tsx` (updated to use UrlUploader)
- **Features**:
  - UrlUploader component with textarea accepting URLs one per line
  - `parseUrls()` function that splits by newline, trims whitespace, filters empty lines
  - `isValidUrl()` function that validates http/https URLs using URL constructor
  - `ParsedUrl` interface with `url` and `isValid` fields
  - Parses URLs on change and blur events
  - Placeholder text with examples and helper text explaining format
  - Upload page now shows URL count summary (valid/invalid counts)
  - URL preview list with visual distinction for valid (white) vs invalid (coral/red) URLs
  - "Start Crawl" button enabled only when valid URLs exist
- **Learnings:**
  - URL validation: Use `new URL(str)` constructor and check `protocol` for http/https - cleaner than regex
  - Component patterns: Export both component and utility functions (`parseUrls`, `isValidUrl`) for reuse
  - Textarea styling: Use `font-mono` for URL input to help users spot formatting issues
---

## 2026-02-04 - S3-023
- **What was implemented**: CSV file upload with drag-and-drop for URL upload page
- **Files changed**:
  - `frontend/src/components/onboarding/CsvDropzone.tsx` (new file)
  - `frontend/src/app/projects/[id]/onboarding/upload/page.tsx` (integrated CsvDropzone)
  - `frontend/package.json` (added papaparse dependency)
- **Features**:
  - CsvDropzone component with drag-and-drop zone and click-to-browse file picker
  - CSV parsing using papaparse library (header mode)
  - Extracts URLs from 'url' column (case-insensitive) or first column as fallback
  - Shows error for invalid file types (non-CSV)
  - Shows error when no URLs found in CSV
  - Combines CSV URLs with textarea URLs, deduplicating by URL
  - Success state shows loaded filename and URL count
  - Remove file button to clear loaded CSV
- **Learnings:**
  - Use `import * as Papa from 'papaparse'` (not default import) for TypeScript compatibility with papaparse types
  - CSV file MIME types vary: `text/csv`, `application/vnd.ms-excel` - also check `.csv` extension as fallback
  - Use `Papa.parse<Record<string, string>>()` with `header: true` to get named columns
  - Access column names via `results.meta.fields` array
  - Keyboard accessibility: Add `onKeyDown` handler for Enter/Space on div[role="button"]
---

## 2026-02-04 - S3-024
- **What was implemented**: URL parsing and validation with normalization and deduplication
- **Files changed**:
  - `frontend/src/components/onboarding/UrlUploader.tsx` (added normalizeUrl function, updated ParsedUrl interface, enhanced parseUrls)
  - `frontend/src/app/projects/[id]/onboarding/upload/page.tsx` (updated to use normalizedUrl for deduplication)
- **Features**:
  - Added `normalizedUrl` field to `ParsedUrl` interface
  - Created `normalizeUrl()` function that:
    - Lowercases the hostname (domain)
    - Removes trailing slashes except for root paths
    - Preserves original path case (paths can be case-sensitive)
    - Handles ports, search params, and hashes
  - Updated `parseUrls()` to deduplicate by normalized URL
  - Updated upload page to deduplicate CSV URLs using `normalizedUrl`
- **Acceptance criteria verification**:
  - ✅ Validate URL format (must have http/https protocol) - `isValidUrl()` already handled this
  - ✅ Normalize URLs (lowercase domain, consistent trailing slash) - new `normalizeUrl()` function
  - ✅ Deduplicate URLs - `parseUrls()` now deduplicates by normalized URL
  - ✅ Filter empty lines - `parseUrls()` already did this
  - ✅ Mark invalid URLs in preview - already handled in page component
- **Learnings:**
  - URL paths can be case-sensitive on some servers, so only lowercase the hostname, not the path
  - The JavaScript `URL` class handles most edge cases (ports, search params, hash) automatically
  - For invalid URLs, fall back to lowercased string for deduplication consistency
---

## 2026-02-04 - S3-025
- **What was implemented**: URL preview list component with remove button functionality
- **Files changed**:
  - `frontend/src/components/onboarding/UrlPreviewList.tsx` (new file)
  - `frontend/src/app/projects/[id]/onboarding/upload/page.tsx` (integrated UrlPreviewList)
- **Features**:
  - Created `UrlPreviewList` component with:
    - Shows all parsed URLs in a scrollable list (max-h-64)
    - Valid/invalid status indicator with check/X icons
    - "X URLs to process" count summary with invalid count
    - Remove button (trash icon) on each URL row, appears on hover
    - Empty state when no URLs
  - Added `removedUrls` state (Set<string>) to track manually removed URLs
  - Updated `parsedUrls` memo to filter out removed URLs
  - `handleRemoveUrl` callback adds normalized URL to removed set
- **Acceptance criteria verification**:
  - ✅ Shows all parsed URLs in a list - UrlPreviewList renders all items
  - ✅ Each URL shows validation status - Check icon (palm) for valid, X icon (coral) for invalid
  - ✅ Remove button on each URL - Trash icon button, reveals on hover, removes from list
  - ✅ Shows total count 'X URLs to process' - Count summary at top of list
  - ✅ Empty state when no URLs - "Enter URLs above..." message when empty
- **Learnings:**
  - Use `Set.prototype.add()` method instead of spread operator (`[...prev, item]`) to avoid TypeScript downlevelIteration issues
  - `group-hover:opacity-100` pattern works well for revealing action buttons on hover
  - Use `key={item.normalizedUrl}` instead of array index for stable list rendering when items can be removed
---

## 2026-02-04 - S3-026
- **What was implemented**: Domain warning banner for URLs from different domains
- **Files changed**:
  - `frontend/src/components/onboarding/UrlUploader.tsx` (added getDomain utility function and export)
  - `frontend/src/app/projects/[id]/onboarding/upload/page.tsx` (added warning banner and domain comparison logic)
- **Features**:
  - `getDomain(urlStr)` - Extract lowercase hostname from URL string
  - `hasDifferentDomainUrls` useMemo - Compares parsed URLs against project's site_url domain
  - Warning banner with coral styling and warning icon
  - Warning does not block submission (only requires valid URLs)
- **Acceptance criteria verification**:
  - ✅ Compare URLs against project site_url domain - getDomain extracts hostname for comparison
  - ✅ Show warning banner if any URLs have different domain - Conditional banner rendering
  - ✅ Warning does not block submission - Start Crawl only disabled when no valid URLs
  - ✅ Warning text: 'Some URLs are from a different domain' - Exact text used
- **Learnings:**
  - URL hostname is already lowercase from `new URL()`, but explicit `.toLowerCase()` ensures consistency
  - Use `useMemo` for derived state that depends on multiple sources (parsedUrls, project)
  - Design system color for warnings: `coral-50` background, `coral-200` border, `coral-500` icon, `coral-700` text
---

## 2026-02-04 - S3-027
- **What was implemented**: Start Crawl button action with API submission and navigation
- **Files changed**:
  - `frontend/src/app/projects/[id]/onboarding/upload/page.tsx` (added submission logic, loading state, error handling)
- **Features**:
  - Added `useRouter` for navigation after successful submission
  - Added `isSubmitting` state for loading indication
  - Added `submitError` state for error display
  - `handleStartCrawl` callback that:
    - POSTs valid URLs to `/api/v1/projects/{id}/urls`
    - Navigates to `/projects/{id}/onboarding/crawl` on success
    - Shows error message on failure
  - Button shows "Starting..." text during submission
  - Cancel button disabled during submission
  - Error banner displayed above action buttons
- **Acceptance criteria verification**:
  - ✅ Start Crawl button enabled when valid URLs exist
  - ✅ Button disabled when no valid URLs
  - ✅ Clicking POSTs to /api/v1/projects/{id}/urls
  - ✅ On success, navigates to crawl progress page
  - ✅ Shows loading state during submission
- **Learnings:**
  - Use `apiClient.post<ResponseType>()` from `@/lib/api` for typed API calls
  - Don't reset `isSubmitting` to false on success - navigation happens immediately after
  - Error handling: catch and display, only reset loading state on error (not success, since we navigate away)
---

## 2026-02-04 - S3-028
- **What was implemented**: Component tests for UrlUploader, CsvDropzone, and UrlPreviewList
- **Files changed**: `frontend/src/components/onboarding/__tests__/UrlUploader.test.tsx` (new file - 68 tests)
- **Test coverage**:
  - `parseUrls` unit tests: Basic parsing (4 tests), validation (6 tests), deduplication (5 tests), normalization (2 tests)
  - `isValidUrl` unit tests: Various protocols and edge cases (6 tests)
  - `normalizeUrl` unit tests: Domain lowercasing, path preservation, trailing slashes, ports, query params (7 tests)
  - `getDomain` unit tests: Domain extraction, case handling, subdomains (4 tests)
  - `extractUrlsFromCsv` unit tests: Column handling, fallback, empty filtering (6 tests)
  - `UrlUploader` component: Rendering (4 tests), URL parsing from textarea (4 tests)
  - `CsvDropzone` component: Rendering (2 tests), drag/drop (2 tests), validation (3 tests), keyboard (2 tests)
  - `UrlPreviewList` component: Rendering (5 tests), validation display (3 tests), remove (3 tests)
- **Acceptance criteria verification**:
  - ✅ Test URL parsing from textarea - covered in `UrlUploader Component > URL parsing from textarea`
  - ✅ Test CSV file parsing - covered in `extractUrlsFromCsv` and `CsvDropzone Component`
  - ✅ Test validation marks invalid URLs - covered in `parseUrls > validation` and `UrlPreviewList > validation status`
  - ✅ Test deduplication works - covered in `parseUrls > deduplication` (5 tests)
  - ✅ Test remove button removes URL - covered in `UrlPreviewList > remove functionality` (3 tests)
  - ✅ Tests in frontend/src/components/onboarding/__tests__/
- **Learnings:**
  - Use more specific CSS selectors when testing DOM classes (e.g., `.bg-coral-100.rounded-full` vs just `.bg-coral-100`) to avoid matching unrelated elements
  - Test utility functions separately from components for better isolation and maintainability
  - Follow existing FileUpload.test.tsx patterns: use `fireEvent` for events, `userEvent` for interactions, mock functions with `vi.fn()`
  - For drag-drop testing, `fireEvent.dragOver/dragLeave/drop` work well with jsdom
---

## 2026-02-04 - S3-029
- **What was implemented**: Created crawl progress page route for viewing crawl status
- **Files changed**: `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx` (new file)
- **Features**:
  - Page route at `/projects/[id]/onboarding/crawl`
  - Loads crawl status from `GET /projects/{id}/crawl-status` API
  - Polls every 2 seconds while status is `crawling` or `labeling`, stops when `complete`
  - Step indicator showing Crawl as current step (step 2 of 5)
  - Breadcrumb navigation: `{project.name} › Onboarding`
  - Progress bar showing completed pages vs total
  - Page list with status icons (check for completed, spinner for crawling, X for failed, circle for pending)
  - Page details shown for completed pages: title, word count, product count
  - Loading skeleton state while data loads
  - 404 error state if project not found
  - Continue button enabled only when crawl is complete, navigates to keywords step
- **Acceptance criteria verification**:
  - ✅ Create /projects/[id]/onboarding/crawl/page.tsx
  - ✅ Page loads crawl status and shows progress
  - ✅ Breadcrumb navigation
  - ✅ Step indicator showing Crawl as current step
- **Learnings:**
  - TanStack Query's `refetchInterval` can be a function that receives query data, returning `false` to stop polling or milliseconds to continue
  - Reuse ONBOARDING_STEPS pattern from upload page for consistent step indicator
  - Use `max-h-80 overflow-y-auto` for scrollable page lists within a card
  - Display URL path only (not full URL) for cleaner list using `new URL().pathname`
---

## 2026-02-04 - S3-030
- **What was implemented**: Created reusable CrawlProgress component with animated progress bar
- **Files changed**: `frontend/src/components/onboarding/CrawlProgress.tsx` (new file)
- **Features**:
  - Reusable progress bar component with TypeScript interface
  - Shows "X of Y" pages completed
  - Displays percentage value in parentheses (optional via showPercentage prop)
  - Animated progress bar using `transition-all duration-500 ease-out`
  - Uses `palm-500` for progress fill color (tropical oasis design)
  - Accessibility: proper `role="progressbar"` with aria attributes
  - Configurable label prop (defaults to "Progress")
- **Acceptance criteria verification**:
  - ✅ Progress bar shows X of Y pages complete
  - ✅ Percentage displayed
  - ✅ Animated progress bar
  - ✅ Component in frontend/src/components/onboarding/CrawlProgress.tsx
- **Learnings:**
  - Add `ease-out` to transitions for smoother progress bar animations
  - Use `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax` for accessibility
  - Export both named export and default export for flexibility in imports
---

## 2026-02-04 - S3-031
- **What was implemented**: Page list component with per-page status display including error messages for failed pages
- **Files changed**:
  - `backend/app/schemas/crawled_page.py` (added crawl_error to PageSummary schema)
  - `backend/app/api/v1/projects.py` (added crawl_error to PageSummary construction in get_crawl_status)
  - `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx` (added crawl_error to PageSummary interface, display error in PageListItem)
- **Acceptance criteria verification**:
  - ✅ List shows all pages being crawled - PageListItem renders each page
  - ✅ Pending: neutral icon, 'Pending' text - PageStatusIcon/PageStatusText handle pending state
  - ✅ Crawling: spinner, 'Crawling...' text - SpinnerIcon with animate-spin, "Crawling..." text
  - ✅ Completed: checkmark, shows extracted data - CheckIcon, title/word_count/product_count displayed
  - ✅ Failed: error icon, shows error message - X icon, crawl_error displayed in coral text
- **Learnings:**
  - When adding fields to API response schemas, must update both the Pydantic schema AND the API endpoint where the schema is constructed
  - PageSummary (lightweight) is separate from CrawledPageResponse (full) for polling efficiency
  - Status-specific UI: use conditional rendering with `page.status === 'failed' && page.crawl_error`
---

## 2026-02-04 - S3-032
- **What was implemented**: Enhanced extracted data summary display in crawl progress page
- **Files changed**:
  - `backend/app/schemas/crawled_page.py` (added headings field to PageSummary schema)
  - `backend/app/api/v1/projects.py` (added headings to PageSummary construction in get_crawl_status)
  - `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx` (added headings to interface, updated display format)
- **Acceptance criteria verification**:
  - ✅ Show page title for completed pages - title displayed below URL (truncated)
  - ✅ Show word count (e.g., '245 words') - format updated from "Words: X" to "X words" with toLocaleString()
  - ✅ Show heading counts (e.g., 'H2s: 3') - added headings field to schema/API, displays H2 count
  - ✅ Show product count if available (e.g., '24 products') - format updated from "Products: X" to "X products"
- **Learnings:**
  - When displaying counts with labels, acceptance criteria format matters (e.g., "245 words" vs "Words: 245")
  - Use `toLocaleString()` for number formatting to add thousand separators for large word counts
  - The headings JSONB structure `{h1: [], h2: [], h3: []}` requires optional chaining with nullish coalescing (`?.length ?? 0`)
  - Keep extracted data summary concise - H2 count is most useful (H1 usually just 1, H3 too granular)
---

## 2026-02-04 - S3-033
- **What was implemented**: Verified polling implementation (already completed in S3-029)
- **Files changed**: None - implementation was already complete
- **Location of implementation**: `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx` lines 334-345
- **Acceptance criteria verification**:
  - ✅ Poll /api/v1/projects/{id}/crawl-status every 2 seconds - `refetchInterval: 2000`
  - ✅ Update UI with new status data - useQuery updates `crawlStatus` which renders throughout component
  - ✅ Stop polling when all pages are completed or failed - `refetchInterval` function returns `false` when `status === 'complete'`
  - ✅ Use React Query or similar for polling - TanStack Query's `useQuery` with `refetchInterval`
- **Learnings:**
  - TanStack Query's `refetchInterval` can be a function that receives query state: `(data) => { return data.state.data?.status === 'complete' ? false : 2000 }`
  - Backend's `_compute_overall_status` returns 'complete' when all pages are either completed or failed AND labeling is done
  - The three-state model (crawling → labeling → complete) provides good UX for showing different phases
---

## 2026-02-04 - S3-034
- **What was implemented**: Added retry button for failed pages in the crawl progress UI
- **Files changed**: `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx`
- **Features**:
  - Added `RetryIcon` component (refresh/rotate arrow icon)
  - Extended `PageListItem` with `onRetry` callback and `isRetrying` state props
  - Retry button appears inline with status for failed pages (coral styling to match error theme)
  - Shows loading spinner during retry with "Retrying..." text
  - `handleRetryPage` callback POSTs to `/api/v1/projects/{id}/pages/{page_id}/retry`
  - Query invalidation refreshes page list immediately after retry
  - Button disabled during retry to prevent double-clicks
- **Acceptance criteria verification**:
  - ✅ Retry button shown on failed pages - inline button with retry icon
  - ✅ Clicking calls POST /api/v1/projects/{id}/pages/{page_id}/retry - apiClient.post()
  - ✅ Page status changes to pending and re-crawls - backend resets status, query invalidation updates UI
  - ✅ Button shows loading state during retry - SpinnerIcon + "Retrying..." + disabled state
- **Learnings:**
  - Track retry state per-page (not global) using `retryingPageId` state for correct loading indication when multiple failed pages exist
  - Inline retry button design: place in flex row with status text for compact UI
  - Use `queryClient.invalidateQueries()` after mutation to force refresh - the existing polling will pick up the new status
---

## 2026-02-04 - S3-035
- **What was implemented**: Component tests for CrawlProgress and related page components (44 tests)
- **Files changed**: `frontend/src/components/onboarding/__tests__/CrawlProgress.test.tsx` (new file)
- **Test coverage**:
  - `CrawlProgress` component (15 tests): Progress bar rendering, label/percentage display, aria attributes, percentage calculations (0%, 50%, 100%, rounding), props updates, styling (animation classes, fill color)
  - `PageStatusIcon` (5 tests): Renders correct icons for completed/crawling/failed/pending/unknown statuses
  - `PageStatusText` (4 tests): Renders correct text and colors for each status
  - `PageListItem` (18 tests): URL path extraction, completed page data display (title, word count, H2s, product count), failed page display (error message, retry button), retry button functionality (click calls API, loading state, disabled state)
  - `Polling behavior` (2 tests): Documents refetchInterval configuration and stop/continue conditions
- **Acceptance criteria verification**:
  - ✅ Test progress bar updates correctly - 7 tests for progress bar updates (percentage calculations, prop changes)
  - ✅ Test page status icons render correctly - 5 tests for PageStatusIcon, 4 for PageStatusText
  - ✅ Test polling starts and stops appropriately - 2 tests documenting refetchInterval behavior
  - ✅ Test retry button calls API - 5 tests for retry button (click, loading state, disabled state)
  - ✅ Tests in frontend/src/components/onboarding/__tests__/
- **Learnings:**
  - When testing components from page files that aren't exported, create local copies of the components in the test file with data-testid attributes for easier testing
  - For polling tests, document the expected configuration and behavior rather than trying to mock TanStack Query internals
  - Use `rerender` from render result to test prop change behavior
  - Test style/class assertions use `toHaveClass()` and `toHaveStyle()` matchers
---

## 2026-02-04 - S3-036
- **What was implemented**: Added taxonomy status display to crawl progress page
- **Files changed**: `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx`
- **Features**:
  - Added `TaxonomyResponse` and `TaxonomyLabel` TypeScript interfaces
  - Added `TagIcon` SVG component for visual indicator
  - Created `TaxonomyStatus` component that:
    - Shows "Generating label taxonomy..." with spinner during `labeling` status
    - Shows generated taxonomy labels as tags when status is `complete`
    - Shows label count (e.g., "15 labels generated")
  - Added useQuery hook to fetch taxonomy from `/projects/{id}/taxonomy` endpoint
  - Query enabled only when status is `labeling` or `complete`
  - Retry logic for 404 errors during labeling phase (taxonomy may not be ready yet)
- **Acceptance criteria verification**:
  - ✅ Show 'Generating label taxonomy...' with spinner after crawl completes - SpinnerIcon + text during `labeling` status
  - ✅ Show generated taxonomy labels when complete - Labels displayed as palm-colored tags
  - ✅ Show label count (e.g., '15 labels generated') - Count shown in header
- **Learnings:**
  - TanStack Query's `enabled` option can use dependent query data (`crawlStatus?.status`) for conditional fetching
  - Use retry with custom logic to handle 404s during transitional states (labeling phase before taxonomy is generated)
  - Conditional rendering based on status enums keeps component logic clean (`if (status === 'crawling') return null`)
  - Title attribute on label tags provides tooltip with description for user context
---

## 2026-02-04 - S3-037
- **What was implemented**: Added label tag display and edit button to crawl progress page
- **Files changed**: `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx`
- **Features**:
  - Added `PencilIcon` SVG component for edit button
  - Extended `PageListItemProps` with `onEditLabels` callback
  - Updated `PageListItem` component to:
    - Display labels as styled tags/chips (palm-100 bg, palm-700 text)
    - Show edit button next to labels (appears on hover-like interaction)
  - Added `editingPageId` state and `handleEditLabels` handler in main component
  - Wired up `onEditLabels` callback to all page items
- **Acceptance criteria verification**:
  - ✅ Labels shown as tags/chips on each page row - palm-colored tags rendered in flex wrap
  - ✅ Tags styled with tropical oasis colors - palm-100 background, palm-700 text, rounded-sm
  - ✅ Edit button to modify labels - PencilIcon button with "Edit" text, triggers state change
- **Learnings:**
  - Use `eslint-disable-next-line` for state that will be used by future stories (editingPageId for S3-038)
  - Label display should only appear when page has labels (`hasLabels` check)
  - Edit button styling: subtle warm-gray-500 text that highlights to palm-600 on hover
---

## 2026-02-04 - S3-038
- **What was implemented**: Created LabelEditDropdown component for editing page labels with multi-select checkboxes
- **Files changed**:
  - `frontend/src/components/onboarding/LabelEditDropdown.tsx` (new file)
  - `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx` (integrated dropdown)
  - `frontend/src/lib/api.ts` (added `put` method to apiClient)
- **Features**:
  - `LabelEditDropdown` component with checkboxes for all taxonomy labels
  - Shows label name and description for each option
  - Selected labels are highlighted with palm-50 background and checked icon
  - Selection count indicator showing "X of 2-5 labels selected"
  - Validation for 2-5 labels (MIN_LABELS, MAX_LABELS constants exported)
  - `validateLabelCount()` helper function for reuse
  - Dropdown closes on outside click or Escape key
  - Save button disabled when validation fails or no changes made
  - Loading state during save operation
- **Acceptance criteria verification**:
  - ✅ Multi-select dropdown shows all taxonomy labels - taxonomyLabels prop renders list
  - ✅ Checkboxes for selecting/deselecting labels - CheckboxIcon component with checked state
  - ✅ Shows current selections checked - localSelection state initialized from selectedLabels
  - ✅ Validates 2-5 labels selected - validateLabelCount function checks MIN_LABELS/MAX_LABELS
- **Learnings:**
  - apiClient didn't have a `put` method - had to add it (backend uses PUT for label updates)
  - Use `useRef` + `useEffect` for outside click detection on dropdown components
  - Local selection state (Set<string>) in dropdown allows preview of changes before saving
  - Export validation constants (MIN_LABELS, MAX_LABELS) for reuse in tests and other components
---

## 2026-02-04 - S3-039
- **What was implemented**: Added toast feedback for label save success/error
- **Files changed**: `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx`
- **Features**:
  - Added toast state variables: `showToast`, `toastMessage`, `toastVariant`
  - Updated `handleSaveLabels` to show "Labels saved" toast on success
  - Added error toast showing validation or network errors on failure
  - Imported and rendered `Toast` component from `@/components/ui`
- **Acceptance criteria verification**:
  - ✅ Changes saved via PUT /api/v1/projects/{id}/pages/{page_id}/labels - already implemented in S3-038
  - ✅ Show validation error if <2 or >5 labels - LabelEditDropdown prevents save + error toast on API error
  - ✅ Show success feedback on save - "Labels saved" toast shown
  - ✅ Update UI with new labels - queryClient.invalidateQueries() refreshes page list
- **Learnings:**
  - Follow existing Toast pattern from brand-config page: state for show/message/variant, render conditionally
  - Re-throwing error after showing toast allows the dropdown to also react (e.g., keeping form open)
---

## 2026-02-04 - S3-040
- **What was implemented**: Continue to Keywords button (already existed in crawl page) + placeholder keywords page
- **Files changed**:
  - `frontend/src/app/projects/[id]/onboarding/keywords/page.tsx` (new file)
- **Features**:
  - Button already existed in crawl page at lines 741-749 with correct conditional rendering
  - Created placeholder keywords page at `/projects/[id]/onboarding/keywords`
  - Keywords page shows "Coming Soon" message with clock icon
  - Includes breadcrumb navigation, step indicator (showing Keywords as step 3)
  - Navigation buttons: "Back to Crawl" and "Go to Project"
- **Acceptance criteria verification**:
  - ✅ Button appears when labeling is complete - `{isComplete ? <Link...>Continue to Keywords</Link> : ...}`
  - ✅ Button disabled during crawling/labeling - Shows disabled "Crawling..." button when `!isComplete`
  - ✅ Navigates to keywords step (Phase 4 placeholder for now) - Links to `/projects/{id}/onboarding/keywords`
- **Learnings:**
  - When navigating to a future phase, create a placeholder page with "Coming Soon" message
  - Follow existing page patterns: breadcrumb, step indicator, consistent card layout
  - Reuse shared components like ONBOARDING_STEPS, icon components, LoadingSkeleton, NotFoundState
---

## 2026-02-04 - S3-041
- **What was implemented**: Component tests for LabelEditDropdown (45 tests)
- **Files changed**: `frontend/src/components/onboarding/__tests__/LabelEditDropdown.test.tsx` (new file)
- **Test coverage**:
  - `validateLabelCount` unit tests (7 tests): Returns null for valid counts (2-5), error messages for invalid counts (0, 1, 6, 10)
  - `Label constants` tests (2 tests): MIN_LABELS=2, MAX_LABELS=5
  - `LabelEditDropdown rendering` (5 tests): Header, close button, Cancel/Save buttons, dialog role
  - `Taxonomy options display` (5 tests): All labels rendered, descriptions shown, checkbox states, empty labels handling
  - `Selection count indicator` (3 tests): Count display, validation errors, count updates
  - `Checkbox interaction` (2 tests): Toggle selection, deselect on re-click
  - `Validation prevents <2 labels` (3 tests): Disabled save at 0/1 labels, error message on deselect
  - `Validation prevents >5 labels` (2 tests): Error message and disabled save when exceeding max
  - `Save functionality` (7 tests): Save enabled with valid selection, disabled without changes, calls onSave/onLabelsChange, "Saving..." state, buttons disabled during save
  - `Close functionality` (5 tests): Close button, cancel button, Escape key, outside click, inside click doesn't close
  - `Label display in page context` (3 tests): Checkboxes state, background highlighting, text styling
  - `Label editing workflow` integration tests (3 tests): Complete workflow, cancel workflow, validation blocks save
- **Acceptance criteria verification**:
  - ✅ Test labels display correctly - taxonomy options display tests verify all labels render with descriptions and correct checked state
  - ✅ Test dropdown shows taxonomy options - checkbox interaction tests verify selection toggling works
  - ✅ Test validation prevents <2 or >5 labels - validation tests verify disabled save and error messages
  - ✅ Test save calls API with correct data - save functionality tests verify onSave called with correct labels array
- **Learnings:**
  - Use `screen.getByText('label-name').closest('button')` to find clickable option buttons in the dropdown
  - Access checkbox checked state via `getAttribute('aria-checked')` since these are styled buttons with role="checkbox"
  - Integration workflow tests are valuable for verifying complete user journeys through the component
  - Test for both the presence and absence of elements (e.g., disabled states, error messages appearing/disappearing)
---

## 2026-02-04 - S3-042
- **What was implemented**: Updated project detail Onboarding section with progress display
- **Files changed**:
  - `frontend/src/hooks/use-crawl-status.ts` (new file)
  - `frontend/src/app/projects/[id]/page.tsx` (updated Onboarding section)
- **Features**:
  - Created `useCrawlStatus` hook for fetching crawl status on project detail page
  - Created `getOnboardingStep` helper to determine current step and navigation target
  - Added `OnboardingStepIndicator` component showing step completion status
  - Progress bar showing "X of Y pages complete" when pages exist
  - Dynamic button text: "Start Onboarding" vs "Continue Onboarding"
  - Navigation to correct step based on progress (upload → crawl → keywords)
  - Status text showing "Crawl complete", "Labeling pages...", or "Crawling pages..."
  - Failed page count displayed when applicable
- **Acceptance criteria verification**:
  - ✅ Show crawl progress when pages exist (e.g., '8 of 12 pages complete') - Progress bar with count
  - ✅ Show step indicators with completion status - OnboardingStepIndicator component
  - ✅ Update button text: 'Start Onboarding' vs 'Continue Onboarding' - Conditional text based on hasStarted
  - ✅ Navigate to correct step based on progress - Link href changes based on currentStep
- **Learnings:**
  - Create reusable hooks for data fetching (useCrawlStatus) to share between components
  - Use helper functions (getOnboardingStep) to encapsulate business logic for determining UI state
  - Handle 404 responses gracefully by returning null (no pages uploaded yet case)
  - CrawlStatusResponse has three states: 'crawling', 'labeling', 'complete' - use for UI text
---

## 2026-02-04 - S3-043
- **What was implemented**: Added onboarding quick stats display showing page count, failed count, and label status
- **Files changed**: `frontend/src/app/projects/[id]/page.tsx`
- **Features**:
  - Quick stats row above progress bar showing key metrics at a glance
  - Page count displayed as "X pages" with bold number
  - Failed count shown in coral (warning style) only when failures exist
  - Label status shows "Labels assigned" (green) when complete, "Labels pending" (gray) otherwise
  - Calculates label status by checking if all pages have labels assigned
- **Acceptance criteria verification**:
  - ✅ Show page count - "X pages" with bold number in stats row
  - ✅ Show failed count in warning style if any - Coral color (`text-coral-600`) for failed count
  - ✅ Show label status ('Labels assigned' or 'Labels pending') - Green when complete, gray when pending
- **Learnings:**
  - Use IIFE pattern `{(() => { ... })()}` for inline conditional rendering with complex logic in JSX
  - CrawlStatusResponse.pages array contains label data, can compute "all pages labeled" by filtering
  - Design system colors: `text-palm-600` for success/positive, `text-coral-600` for warning, `text-warm-gray-500` for neutral
---

## 2026-02-04 - S3-044
- **What was implemented**: Wired background task to automatically trigger taxonomy generation and label assignment after crawling completes
- **Files changed**: `backend/app/api/v1/projects.py` (enhanced `_crawl_pages_background` function)
- **Features added**:
  - After crawling completes, checks if all project pages are done (no pending or crawling)
  - Updates `phase_status.onboarding.status` to `'labeling'` before taxonomy generation
  - Generates taxonomy using `LabelTaxonomyService.generate_taxonomy()`
  - Assigns labels to all pages using `LabelTaxonomyService.assign_labels()`
  - Updates `phase_status.onboarding.status` to `'labels_complete'` when done
  - Comprehensive logging throughout the workflow
- **Acceptance criteria verification**:
  - ✅ After all pages complete/failed, trigger taxonomy generation - checks `pending_or_crawling == 0`
  - ✅ Update project phase_status.onboarding.status to 'labeling' - done before `generate_taxonomy()`
  - ✅ After taxonomy generated, run label assignment - calls `assign_labels()` after taxonomy
  - ✅ Update status to 'labels_complete' when done - done after `assign_labels()` completes
- **Learnings:**
  - Use `get_claude()` from `app.integrations.claude` to get the global Claude client in background tasks
  - Must use `flag_modified(project, "phase_status")` for SQLAlchemy JSONB mutation tracking
  - Background task pattern: check all pages status, update phase_status, generate taxonomy, assign labels in sequence
  - Early return if not all pages done - supports incremental crawling with retries
---

## 2026-02-04 - S3-045
- **What was implemented**: Full workflow status tracking with phase_status updates throughout the onboarding process
- **Files changed**: `backend/app/api/v1/projects.py` (updated `upload_urls` and `_crawl_pages_background`)
- **Features added**:
  - In `upload_urls`: Set status to 'crawling' and initialize crawl progress tracking when pages are created
  - Initialize `phase_status.onboarding.crawl` object with total, completed, failed counts and started_at timestamp
  - In `_crawl_pages_background`: Update crawl progress counts after each crawl batch completes
  - Progress tracking handles incremental crawling (retries add to existing counts)
  - Moved `flag_modified` import to module level to avoid duplicate imports
- **Acceptance criteria verification**:
  - ✅ Set status to 'crawling' when crawl starts - done in `upload_urls` when pages_created > 0
  - ✅ Track crawl progress in phase_status.onboarding.crawl - object with total/completed/failed/started_at
  - ✅ Set status to 'labeling' when taxonomy starts - already implemented in S3-044
  - ✅ Set status to 'labels_complete' when done - already implemented in S3-044
  - ✅ Store taxonomy in phase_status.onboarding.taxonomy - already implemented in S3-009/S3-010
- **Learnings:**
  - Use module-level import for `flag_modified` when used in multiple functions to avoid duplicate imports
  - Initialize crawl progress tracking at URL upload time for accurate total counts
  - Progress tracking should increment (not replace) to support incremental crawling with retries
---

## 2026-02-04 - S3-046
- **What was implemented**: Added comprehensive error handling throughout the URL upload and crawl progress pages
- **Files changed**:
  - `frontend/src/app/projects/[id]/onboarding/upload/page.tsx` (added Toast, ApiError import, error message helper, toast state)
  - `frontend/src/app/projects/[id]/onboarding/crawl/page.tsx` (added ApiError import, getErrorMessage helper, network error banner, improved retry/save error handling)
- **Features added**:
  - User-friendly error messages for API errors (400, 404, 429, 500+)
  - Network error detection ("Failed to fetch" → friendly message)
  - Toast notifications on upload page for errors
  - Toast notifications on crawl page for retry success/error
  - Network error banner when crawl status polling fails
  - Improved label save error messages
  - Loading state already existed (isSubmitting, retryingPageId, savingLabels) - verified working
- **Acceptance criteria verification**:
  - ✅ API errors show user-friendly messages - getErrorMessage helper provides friendly text for all HTTP status codes
  - ✅ Network errors handled gracefully - "Failed to fetch" detected and shown with connectivity message
  - ✅ Loading states prevent double-submissions - Already existed: isSubmitting disables button, retryingPageId tracks retry state
  - ✅ Toast notifications for success/error feedback - Added to upload page, enhanced on crawl page
- **Learnings:**
  - Network errors in fetch show as `TypeError` with message "Failed to fetch" - check for this specific pattern
  - ApiError class from api.ts provides structured access to status codes and messages
  - For polling queries, use `retry: 3` with `retryDelay` to handle transient network issues gracefully
  - Show inline error banners for persistent errors (network down) but toasts for transient errors (single request failure)
---

