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

