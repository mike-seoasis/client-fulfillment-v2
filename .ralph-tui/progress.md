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

