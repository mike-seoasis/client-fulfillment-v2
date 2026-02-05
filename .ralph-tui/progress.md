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

