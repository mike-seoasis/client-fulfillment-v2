# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Approval fields pattern:** `is_approved` uses `Boolean, nullable=False, default=False, server_default=text("false"), index=True`. `approved_at` uses `DateTime(timezone=True), nullable=True`. See `PageKeywords` and `PageContent` models for reference. Import `Boolean` from sqlalchemy.
- **Approval migration pattern:** Reference `0020_add_page_keywords_approval_fields.py` and `0022_add_page_contents_approval_fields.py` for adding approval columns to existing tables. Pattern: `add_column` for each field + `create_index` on `is_approved`. Downgrade drops index first, then columns.

---

## 2026-02-07 - S6-001
- Added `is_approved` (Boolean, default=False, indexed) and `approved_at` (DateTime, nullable) fields to PageContent model
- Files changed: `backend/app/models/page_content.py`
- **Learnings:**
  - Pattern matches PageKeywords.is_approved exactly (lines 88-94 of page_keywords.py)
  - `Boolean` import was not previously in page_content.py — needed to add it to the sqlalchemy import line
  - mypy and ruff both pass clean
---

## 2026-02-07 - S6-002
- Created Alembic migration `0022_add_page_contents_approval_fields.py` adding `is_approved` and `approved_at` to `page_contents` table
- Files changed: `backend/alembic/versions/0022_add_page_contents_approval_fields.py` (new)
- **Learnings:**
  - Followed exact pattern from `0020_add_page_keywords_approval_fields.py` — `is_approved` with `server_default=sa.text("false")`, NOT NULL; `approved_at` as nullable `DateTime(timezone=True)`; index on `is_approved`
  - Downgrade drops index before columns (order matters)
  - Space in project path (`Projects (1)`) causes Alembic's `version_locations` config to split on space; workaround is to set `script_location` to absolute path and clear `version_locations`
  - Migration tested: upgrade, downgrade, re-upgrade all succeed
  - ruff and mypy pass clean
---

## 2026-02-07 - S6-003
- Added content review/editing schemas to `backend/app/schemas/content_generation.py`
- New schemas: `ContentUpdateRequest` (partial update with optional page_title, meta_description, top_description, bottom_description), `ContentBriefData` (keyword, lsi_terms, heading_targets, keyword_targets), `BulkApproveResponse` (approved_count)
- Updated `PageContentResponse` with `is_approved` (bool), `approved_at` (datetime|None), and `brief` (ContentBriefData|None)
- Updated `ContentGenerationStatus` with `pages_approved` (int, default 0)
- Files changed: `backend/app/schemas/content_generation.py`
- **Learnings:**
  - All schemas follow Pydantic v2 conventions (BaseModel, Field, ConfigDict)
  - ContentBriefData uses `list[Any]` for JSONB fields (lsi_terms, heading_targets, keyword_targets) to match the model's flexible JSON structure
  - Pre-existing mypy errors in brand_config.py and config.py are unrelated to this change
  - ruff passes clean
---

## 2026-02-07 - S6-011
- Installed Lexical packages: lexical, @lexical/react, @lexical/html, @lexical/rich-text, @lexical/list (all ^0.40.0)
- Updated frontend TypeScript types in `frontend/src/lib/api.ts` to match backend Pydantic schemas:
  - Added `pages_approved` (number) to `ContentGenerationStatus`
  - Added `is_approved` (boolean) and `approved_at` (string|null) to `PageContentResponse`
  - Added `brief` (ContentBriefData|null) to `PageContentResponse`
  - Added `ContentBriefData` type (keyword, lsi_terms, heading_targets, keyword_targets)
  - Added `ContentUpdateRequest` type (optional page_title, meta_description, top_description, bottom_description)
  - Added `ContentBulkApproveResponse` type (approved_count)
- Files changed: `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/lib/api.ts`
- **Learnings:**
  - Lexical packages all install at same version (0.40.0) — they're a monorepo
  - Backend uses `list[Any]` for JSONB brief fields; mapped to `unknown[]` on frontend for type safety
  - Pre-existing TS error in GenerationProgress.test.tsx (tuple index out of bounds) is unrelated
  - Named content bulk approve `ContentBulkApproveResponse` to avoid collision with existing keyword `BulkApproveResponse`
---

## 2026-02-07 - S6-004
- Added PUT /api/v1/projects/{project_id}/pages/{page_id}/content endpoint for partial content updates
- Accepts ContentUpdateRequest body; updates only provided fields (exclude_unset=True partial update)
- Recalculates word_count by stripping HTML tags from all 4 content fields (matches `_apply_parsed_content` pattern in content_writing.py)
- Clears approval on edit: sets is_approved=False, approved_at=None
- Returns updated PageContentResponse with brief_summary (same construction as GET endpoint)
- Returns 404 if page or PageContent not found
- Files changed: `backend/app/api/v1/content_generation.py`
- **Learnings:**
  - Word count pattern: `re.sub(r"<[^>]+>", " ", value)` then `len(text_only.split())` — used in content_writing.py line 824
  - Partial update via Pydantic: `body.model_dump(exclude_unset=True)` gives only the fields the client sent, so omitted fields stay unchanged
  - Brief summary construction is duplicated between GET and PUT — could be extracted to a helper in future
  - Pre-existing mypy errors in content_extraction.py, crawl4ai.py, crawling.py are unrelated; all router endpoints get "untyped decorator" warnings
  - ruff passes clean
---

## 2026-02-07 - S6-005
- Added POST /api/v1/projects/{project_id}/pages/{page_id}/approve-content endpoint
- When value=true (default): sets is_approved=True, approved_at=now(UTC)
- When value=false: sets is_approved=False, approved_at=None
- Returns 400 if content status is not 'complete'
- Returns 404 if page or PageContent not found
- Returns updated PageContentResponse with brief_summary
- Files changed: `backend/app/api/v1/content_generation.py`
- **Learnings:**
  - Ruff enforces `datetime.UTC` alias over `timezone.utc` (rule UP017)
  - Followed exact same pattern as approve-keyword in projects.py but adapted for content (added status check for 'complete', set approved_at timestamp)
  - Brief summary construction is duplicated across GET, PUT, and POST approve endpoints — candidate for helper extraction
  - Pre-existing mypy errors unchanged; ruff passes clean
---

## 2026-02-07 - S6-006
- Added POST /api/v1/projects/{project_id}/pages/{page_id}/recheck-content endpoint
- Loads BrandConfig.v2_schema for the project, calls run_quality_checks() with current content fields
- Stores updated qa_results in PageContent, returns full PageContentResponse
- Returns 404 if page or PageContent not found
- Files changed: `backend/app/api/v1/content_generation.py`
- **Learnings:**
  - run_quality_checks() mutates content.qa_results directly (side effect), so just need db.commit() after calling it
  - BrandConfig loading pattern: `select(BrandConfig).where(BrandConfig.project_id == project_id)` then `.v2_schema` — same as `_load_brand_config` in content_generation service
  - Pre-existing mypy errors unchanged; ruff passes clean
---
