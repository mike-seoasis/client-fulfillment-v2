# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Model file pattern**: UUID(as_uuid=False) with `str` Mapped type, `text("gen_random_uuid()")` server_default, `lambda: str(uuid4())` Python default. DateTime(timezone=True) with `text("now()")` server_default. Boolean with `text("false")` server_default.
- **Model registration**: Add import to `backend/app/models/__init__.py` and include in `__all__` list (alphabetically sorted).
- **Relationships with back_populates**: Always define both sides. Use `TYPE_CHECKING` guard for imports to avoid circular deps. Parent side uses `cascade="all, delete-orphan"` with list type. Child FK uses `ondelete="CASCADE"` or `ondelete="SET NULL"` as appropriate.
- **Python env**: Use `.venv/bin/python` (not bare `python`) for running tools in backend.

---

## 2026-02-08 - S8-001
- Created `backend/app/models/keyword_cluster.py` with `KeywordCluster` and `ClusterPage` models
- Added `clusters` relationship to `backend/app/models/project.py` (back_populates with KeywordCluster)
- Updated `backend/app/models/__init__.py` to export both new models
- **Files changed:**
  - `backend/app/models/keyword_cluster.py` (new)
  - `backend/app/models/project.py` (added relationship + imports)
  - `backend/app/models/__init__.py` (added exports)
- **Learnings:**
  - Project model had no existing relationships - this is the first relationship added to it
  - Project model didn't import `relationship` from sqlalchemy.orm - needed to add it along with TYPE_CHECKING guard
  - ClusterPage FK to crawled_pages uses `ondelete="SET NULL"` since deleting a crawled page shouldn't cascade-delete cluster pages
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-002
- Added `source` column to `CrawledPage` model: `Mapped[str]` with `String(20)`, `default="onboarding"`, `server_default=text("'onboarding'")`, `index=True`
- Column supports values 'onboarding' or 'cluster' to distinguish page origins
- Updated model docstring to document the new attribute
- **Files changed:**
  - `backend/app/models/crawled_page.py` (added source column + docstring update)
- **Learnings:**
  - No venv found in project root or backend/ — system `python3` used for quality checks
  - Simple column additions follow the same pattern as existing String columns (e.g., `status`)
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-003
- Verified all work was already completed in S8-001: model registration and Project.clusters relationship
- Confirmed: `KeywordCluster` and `ClusterPage` imported in `__init__.py`, included in `__all__`
- Confirmed: `Project.clusters` relationship with `back_populates="project"` and `cascade="all, delete-orphan"`
- Confirmed: All models importable from `app.models`
- **Files changed:** None (already implemented)
- **Learnings:**
  - S8-001 proactively completed S8-003's scope (model registration + relationship)
  - Always check progress.md first — previous stories may have already covered the work
  - All quality checks (mypy, ruff) pass clean
---
