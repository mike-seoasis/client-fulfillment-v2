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

## 2026-02-03 - S2-002
- **What was implemented:** Alembic migration for project_files table
- **Files changed:**
  - `backend/alembic/versions/0017_create_project_files_table.py` (created)
- **Learnings:**
  - Pattern: Migrations follow format `0NNN_description.py` with sequential numbering
  - Pattern: Use `sa.ForeignKeyConstraint` with `name` param for explicit FK naming (e.g., `fk_table_column`)
  - Pattern: Use `sa.UniqueConstraint` with `name` param for explicit constraint naming (e.g., `uq_table_column`)
  - Pattern: Index naming convention uses `ix_table_column` via `op.f()` helper
  - Verified: Both upgrade and downgrade paths work correctly
---

## 2026-02-03 - S2-003
- **What was implemented:** Added additional_info column to Project model for user notes during project creation
- **Files changed:**
  - `backend/app/models/project.py` (added additional_info field with Text type, nullable)
  - `backend/alembic/versions/0018_add_additional_info_to_projects.py` (created)
- **Learnings:**
  - Pattern: Use `Text` (not `String`) for unbounded text fields like notes/descriptions
  - Pattern: Simple column additions don't need indexes unless they'll be queried directly
  - Verified: Both upgrade and downgrade paths work correctly
---

