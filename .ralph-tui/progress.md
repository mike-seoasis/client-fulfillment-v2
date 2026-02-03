# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### SQLAlchemy Model Pattern
- All models inherit from `app.core.database.Base`
- UUID primary keys use `UUID(as_uuid=False)` with `str(uuid4())` default
- Server defaults: `text("gen_random_uuid()")` for UUIDs, `text("now()")` for timestamps
- Foreign keys with cascade: `ForeignKey("table.id", ondelete="CASCADE")`
- Timestamps use `DateTime(timezone=True)` with `datetime.now(UTC)`
- New models must be added to `app/models/__init__.py` (import + `__all__` list)

---

## 2026-02-03 - S2-001
- **What was implemented:** ProjectFile model for storing uploaded brand documents
- **Files changed:**
  - `backend/app/models/project_file.py` (created)
  - `backend/app/models/__init__.py` (added import/export)
- **Learnings:**
  - Pattern: Use `BigInteger` for file_size to handle large files (>2GB)
  - Pattern: `s3_key` should be unique to prevent duplicate storage references
  - Gotcha: Must use `uv run` prefix for python/mypy/ruff commands in this project
---

