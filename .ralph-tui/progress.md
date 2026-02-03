# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **SQLAlchemy model fields**: Use `Mapped[T]` with `mapped_column()`. For optional fields, use `Mapped[T | None]` with `nullable=True`. Always specify `String(length)` explicitly.
- **Type checking**: Run `uv run mypy <file>` from the `backend/` directory
- **Linting**: Run `uv run ruff check <file>` from project root
- **Alembic migrations**: Follow `0NNN_description.py` naming pattern. Use `op.add_column()`, `op.alter_column()`, `op.create_index()`. For new required columns on existing tables, add `server_default` temporarily, then remove it after.
- **Alembic verification**: Use `alembic heads` to verify migration is detected (no DB required). Use `alembic history -r X:Y` to verify chain.
- **Pydantic URL fields**: Use `HttpUrl` in request schemas for automatic URL validation. Use `str` in response schemas (DB stores as string, `from_attributes=True` handles conversion).
- **Service layer**: Services live in `backend/app/services/`. Use `@staticmethod` methods, async patterns with `select()` + `db.execute()`, and `db.flush()` + `db.refresh()` for writes. Let the route dependency handle commit/rollback.

---

## 2026-02-03 - S1-001
- Added `site_url: Mapped[str]` field to Project model
- Made `client_id` field optional (nullable=True)
- Updated docstring to document new field
- Files changed: `backend/app/models/project.py`
- **Learnings:**
  - SQLAlchemy uses `Mapped[T | None]` for optional fields (not `Optional[T]`)
  - Model follows consistent pattern: mapped_column with explicit String length, nullable, and index params
---

## 2026-02-03 - S1-002
- Created Alembic migration `0016_add_site_url_to_projects.py`
- Migration adds `site_url` column (String 2048, NOT NULL, indexed)
- Migration makes `client_id` nullable (was required)
- Files changed: `backend/alembic/versions/0016_add_site_url_to_projects.py`
- **Learnings:**
  - `greenlet` package required for async SQLAlchemy Alembic - installed via `uv add greenlet`
  - For adding required columns to existing tables: use `server_default` temporarily, then `op.alter_column(..., server_default=None)` to remove it
  - `alembic heads` and `alembic history` don't require DB connection, useful for verification
---

## 2026-02-03 - S1-003
- Updated `backend/app/schemas/project.py` for v2 rebuild
- Added `site_url: HttpUrl` to `ProjectCreate` (required field)
- Added `site_url: HttpUrl | None` to `ProjectUpdate` (optional field)
- Added `site_url: str` to `ProjectResponse`
- Made `client_id` optional in both `ProjectCreate` and `ProjectResponse` to match model
- Files changed: `backend/app/schemas/project.py`
- **Learnings:**
  - Pydantic v2 `HttpUrl` type provides automatic URL validation
  - Use `HttpUrl` in request schemas for validation, but `str` in response schemas (since DB stores as string)
  - Schemas already exported in `__init__.py`, no changes needed there
---

## 2026-02-03 - S1-004
- Created `backend/app/services/` directory with service layer
- Created `ProjectService` class with all CRUD operations:
  - `list_projects(db)` - returns all projects ordered by `updated_at` DESC
  - `get_project(db, id)` - returns project or raises HTTPException 404
  - `create_project(db, data)` - creates and returns new project
  - `update_project(db, id, data)` - updates and returns project
  - `delete_project(db, id)` - deletes project or raises 404
- All methods are async and use SQLAlchemy 2.0 patterns (`select()`, `db.execute()`, `db.flush()`)
- Files changed: `backend/app/services/__init__.py`, `backend/app/services/project.py`
- **Learnings:**
  - Service layer uses `@staticmethod` for methods that don't need instance state
  - Use `db.flush()` + `db.refresh()` to get updated object state without committing (transaction handled by dependency)
  - Convert `HttpUrl` to `str()` when storing to database
  - Use `model_dump(exclude_unset=True)` to only update fields that were provided in the request
---

