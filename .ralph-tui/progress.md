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

