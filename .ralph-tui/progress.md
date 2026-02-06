# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Model pattern**: Models use `UUID(as_uuid=False)` with `str` Mapped type, `server_default=text("gen_random_uuid()")`, timestamps use `DateTime(timezone=True)` with `default=lambda: datetime.now(UTC)` and `server_default=text("now()")`. Relationships use `TYPE_CHECKING` imports. Status fields use `String(20)` with str Enum classes.
- **One-to-one relationships**: Use `unique=True` on FK column + `uselist=False` on parent relationship. See PageKeywords and PageContent patterns.
- **Model registration**: Add import to `models/__init__.py` and add to `__all__` list (alphabetical order).

---

## 2026-02-06 - S5-001
- Created `PageContent` SQLAlchemy model with all 4 content fields, status tracking, QA results, and generation timestamps
- Files changed:
  - `backend/app/models/page_content.py` (new) — PageContent model with ContentStatus enum
  - `backend/app/models/crawled_page.py` — Added `page_content` one-to-one relationship and TYPE_CHECKING import
  - `backend/app/models/__init__.py` — Registered PageContent import and __all__ entry
- **Learnings:**
  - Pattern: One-to-one relationships use `unique=True` on FK + `uselist=False` on parent side
  - Pattern: ForeignKey uses `ondelete="CASCADE"` for child models tied to crawled_pages
  - All existing models follow the same UUID/timestamp/status pattern consistently
---

## 2026-02-06 - S5-002
- Created `PromptLog` SQLAlchemy model for persisting all Claude prompts/responses during content generation
- Files changed:
  - `backend/app/models/prompt_log.py` (new) — PromptLog model with all fields per acceptance criteria
  - `backend/app/models/page_content.py` — Added `prompt_logs` one-to-many relationship and TYPE_CHECKING import for PromptLog
  - `backend/app/models/__init__.py` — Registered PromptLog import and __all__ entry
- **Learnings:**
  - Ruff import sorting: `project` sorts before `prompt_log` alphabetically — need to maintain strict alphabetical order by module path
  - Many-to-one pattern: FK column without `unique=True` + `Mapped[list["Child"]]` on parent side for one-to-many
---

## 2026-02-06 - S5-003
- Verified ContentBrief model has all required fields (keyword, lsi_terms, related_searches, raw_response, pop_task_id)
- Changed CrawledPage.content_briefs (list) to CrawledPage.content_brief (one-to-one with uselist=False)
- Added unique=True to ContentBrief.page_id FK for proper one-to-one constraint
- Updated ContentBrief.page back_populates from "content_briefs" to "content_brief"
- Verified PageContent.prompt_logs one-to-many and CrawledPage.page_content one-to-one already existed from S5-001/S5-002
- Files changed:
  - `backend/app/models/crawled_page.py` — Changed content_briefs list relationship to content_brief one-to-one
  - `backend/app/models/content_brief.py` — Added unique=True to page_id FK, updated back_populates
- **Learnings:**
  - When converting list relationship to one-to-one: change Mapped type to Optional, add uselist=False, and add unique=True on FK column
  - Always grep for attribute references in app code before renaming relationship attributes
---

