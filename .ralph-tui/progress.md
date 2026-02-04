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

