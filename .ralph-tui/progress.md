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

