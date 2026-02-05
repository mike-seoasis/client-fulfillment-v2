# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Alembic Migration Patterns
- Migration files use sequential numbering: `0001_`, `0002_`, etc.
- Use `server_default=sa.text("false")` for Boolean defaults (not Python `False`)
- Use `server_default=sa.text("'[]'::jsonb")` for empty JSONB array defaults
- Use `server_default=sa.text("'{}'::jsonb")` for empty JSONB object defaults
- Always include proper downgrade() that reverses all upgrade() operations
- Drop indexes before dropping columns in downgrade
- Import `from sqlalchemy.dialects import postgresql` for JSONB types

---

## 2026-02-05 - S4-001
- **What was implemented:** Created Alembic migration to add approval and scoring fields to page_keywords table
- **Files changed:**
  - `backend/alembic/versions/0020_add_page_keywords_approval_fields.py` (new file)
- **Fields added:**
  - `is_approved` - Boolean with server_default=false
  - `is_priority` - Boolean with server_default=false
  - `alternative_keywords` - JSONB with server_default='[]'::jsonb
  - `composite_score` - Float (nullable)
  - `relevance_score` - Float (nullable)
  - `ai_reasoning` - Text (nullable)
- **Indexes added:**
  - `ix_page_keywords_is_approved` - for filtering approved keywords
  - `ix_page_keywords_is_priority` - for filtering priority keywords
- **Learnings:**
  - Pattern documented above for Alembic migrations
---

## 2026-02-05 - S4-002
- **What was implemented:** Added bidirectional relationship between CrawledPage and PageKeywords models
- **Files changed:**
  - `backend/app/models/crawled_page.py` - Added `keywords` relationship with one-to-one config
  - `backend/app/models/page_keywords.py` - Added ForeignKey constraint and `page` relationship
- **Changes:**
  - Added `ForeignKey("crawled_pages.id", ondelete="CASCADE")` to `crawled_page_id` column
  - Added `page` relationship in PageKeywords with `back_populates="keywords"`
  - Added `keywords` relationship in CrawledPage with `uselist=False` for one-to-one, `cascade="all, delete-orphan"`
- **Learnings:**
  - One-to-one relationships in SQLAlchemy use `uselist=False` on the parent side
  - Follow TYPE_CHECKING pattern with forward references to avoid circular imports
  - ForeignKey with `ondelete="CASCADE"` ensures database-level cascade
  - `cascade="all, delete-orphan"` on relationship ensures ORM-level cascade
---

## 2026-02-05 - S4-003
- **What was implemented:** Updated PageKeywords model with new fields for approval and scoring
- **Files changed:**
  - `backend/app/models/page_keywords.py` - Added 6 new fields matching migration 0020
- **Fields added:**
  - `is_approved: Mapped[bool]` - Boolean with default=False, indexed
  - `is_priority: Mapped[bool]` - Boolean with default=False, indexed
  - `alternative_keywords: Mapped[list[Any]]` - JSONB with default=[]
  - `composite_score: Mapped[float | None]` - Float, nullable
  - `relevance_score: Mapped[float | None]` - Float, nullable
  - `ai_reasoning: Mapped[str | None]` - Text, nullable
- **Learnings:**
  - Import `Boolean` and `Float` from sqlalchemy for explicit type declarations
  - Boolean fields with `server_default=text("false")` match Alembic pattern
  - JSONB fields need both `default=list` (Python) and `server_default=text("'[]'::jsonb")` (DB)
  - Add `index=True` on columns that have corresponding indexes in migration
---

## 2026-02-05 - S4-004
- **What was implemented:** Ran Alembic migration and verified schema changes
- **Files changed:**
  - None (database schema update only)
- **Verification results:**
  - Migration 0019 -> 0020 ran successfully
  - All 6 new columns exist: is_approved, is_priority, alternative_keywords, composite_score, relevance_score, ai_reasoning
  - Indexes created: ix_page_keywords_is_approved, ix_page_keywords_is_priority
  - Default values verified: is_approved=False, is_priority=False, alternative_keywords=[]
- **Learnings:**
  - Can run alembic migrations from host machine using `source .venv/bin/activate && alembic upgrade head`
  - Database accessible at localhost:5432 when docker compose db service is running
  - Use `sqlalchemy.inspect()` to verify table columns and indexes programmatically
---

## 2026-02-05 - S4-005
- **What was implemented:** Created Pydantic schemas for keyword generation API
- **Files changed:**
  - `backend/app/schemas/keyword_research.py` - Added 6 new schemas
- **Schemas added:**
  - `KeywordCandidate` - keyword with volume metrics and AI scoring (keyword, volume, cpc, competition, relevance_score, composite_score)
  - `PrimaryKeywordGenerationStatus` - tracks generation progress (status, total, completed, failed, current_page)
  - `PageKeywordsData` - keyword data matching PageKeywords model fields, with `from_attributes=True` for ORM support
  - `PageWithKeywords` - combines CrawledPage summary data with PageKeywords data for approval interface
  - `UpdatePrimaryKeywordRequest` - request to update primary keyword with validation
  - `BulkApproveResponse` - response for bulk approval operations (approved_count)
- **Learnings:**
  - Use `ConfigDict(from_attributes=True)` for schemas that need to be created from SQLAlchemy models
  - Nested schemas work well for combining related data (PageWithKeywords contains PageKeywordsData)
  - Follow existing pattern in keyword_research.py for Field descriptions and validators
---

## 2026-02-05 - S4-006
- **What was implemented:** Created PrimaryKeywordService class for orchestrating keyword generation
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - New service class
  - `backend/app/services/__init__.py` - Added exports for PrimaryKeywordService and KeywordGenerationStats
- **Class features:**
  - Accepts ClaudeClient and DataForSEOClient in __init__
  - `_used_primary_keywords: set[str]` - Tracks keywords already assigned to prevent duplicates
  - `_stats: KeywordGenerationStats` - Dataclass tracking generation metrics (pages processed, tokens, costs, errors)
  - Helper methods: `add_used_keyword()`, `is_keyword_used()`, `reset_stats()`, `get_stats_summary()`
- **Learnings:**
  - Follow LabelTaxonomyService pattern for service class structure
  - Use dataclass for stats to make it easy to track multiple metrics
  - Normalize keywords (lowercase, strip) when checking for duplicates
  - Export both the service class and any related dataclasses from __init__.py
---

## 2026-02-05 - S4-007
- **What was implemented:** Implemented `generate_candidates` async method for generating keyword candidates from page content
- **Files changed:**
  - `backend/app/services/primary_keyword.py` - Added `generate_candidates` method
- **Method features:**
  - Takes CrawledPage data as input: url, title, h1, headings, content_excerpt, product_count, category
  - Builds category-specific prompts with guidelines for product, collection, blog, homepage, other page types
  - Collection pages get e-commerce-focused guidelines with product count context
  - Calls Claude API via `self._claude.complete()` with temperature=0.3 for keyword diversity
  - Parses JSON array response, handles markdown code blocks
  - Returns 20-25 keyword strings (lowercase, stripped)
  - Handles API failures with fallback to title/H1
  - Updates stats: claude_calls, total_input_tokens, total_output_tokens, keywords_generated, errors
- **Learnings:**
  - Reference Old KW research logic/keyword_research.py for prompt structure (generate_keywords_with_llm)
  - Use temperature=0.3 for slight variation in keyword generation (vs 0.0 for deterministic)
  - Category-specific guidelines improve keyword relevance (product=buyer intent, collection=category terms, blog=informational)
  - Always handle markdown code blocks in LLM JSON responses (```json...```)
  - Normalize keywords immediately (lowercase, strip) for consistency
  - Fallback strategy: title first, then H1 if different from title
---

