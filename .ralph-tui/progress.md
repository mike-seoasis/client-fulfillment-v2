# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Model UUID pattern**: `UUID(as_uuid=False)` with `default=lambda: str(uuid4())` and `server_default=text("gen_random_uuid()")`. Python type is `Mapped[str]`, not `Mapped[UUID]`.
- **DateTime pattern**: `DateTime(timezone=True)` with `default=lambda: datetime.now(UTC)` and `server_default=text("now()")`. Add `onupdate=lambda: datetime.now(UTC)` for `updated_at`.
- **Boolean defaults**: Use `server_default=text("false")` (lowercase string), not `server_default=False`.
- **FK pattern**: `ForeignKey("table.id", ondelete="CASCADE")` for required refs, `ondelete="SET NULL"` for optional refs.
- **Composite indexes**: Use `__table_args__` tuple with `Index(name, col1, col2)`. See `notification.py` and `internal_link.py`.
- **Multi-FK relationships**: When a model has multiple FKs to the same table, specify `foreign_keys=[column]` on each relationship to disambiguate.
- **Model registration**: Import in `backend/app/models/__init__.py` and add to `__all__`.
- **Migration numbering**: Sequential `0001`, `0002`, etc. in `backend/alembic/versions/`. Set `down_revision` to previous.
- **Virtual env**: Use `.venv/bin/python` (not `python`) in the backend directory.

---

## 2026-02-10 - S9-001
- Created `InternalLink` model (`backend/app/models/internal_link.py`) with all fields from acceptance criteria
- Created Alembic migration `0024_create_internal_links_table.py` with table, FKs, and indexes
- Registered model in `backend/app/models/__init__.py`
- **Files changed:**
  - `backend/app/models/internal_link.py` (new)
  - `backend/app/models/__init__.py` (updated import + __all__)
  - `backend/alembic/versions/0024_create_internal_links_table.py` (new)
- **Learnings:**
  - Models with multiple FKs to the same table (e.g., source_page_id and target_page_id both pointing to crawled_pages) require `foreign_keys=[column]` on each relationship to avoid SQLAlchemy ambiguity errors
  - Composite indexes go in `__table_args__` tuple — pattern already used in `notification.py`
  - Enums defined as `str, Enum` for JSON serialization compatibility
  - Virtual env is at `backend/.venv/bin/python`
---

## 2026-02-10 - S9-002
- Created `LinkPlanSnapshot` model in `backend/app/models/internal_link.py` (same file as InternalLink)
- Fields: id (UUID PK), project_id (FK CASCADE), cluster_id (FK SET NULL nullable), scope (String(20)), plan_data (JSONB), total_links (Integer), created_at (DateTime timezone)
- Composite index on (project_id, scope)
- Relationship to Project and KeywordCluster
- Created Alembic migration `0025_create_link_plan_snapshots_table.py`
- Registered `LinkPlanSnapshot` in `backend/app/models/__init__.py`
- **Files changed:**
  - `backend/app/models/internal_link.py` (added LinkPlanSnapshot class, added JSONB import)
  - `backend/app/models/__init__.py` (added LinkPlanSnapshot import + __all__ entry)
  - `backend/alembic/versions/0025_create_link_plan_snapshots_table.py` (new)
- **Learnings:**
  - JSONB column uses `from sqlalchemy.dialects.postgresql import JSONB` alongside `UUID`
  - Python type hint for JSONB column is `Mapped[dict]`
  - Multiple models in the same file sharing FKs to the same tables (e.g. both InternalLink and LinkPlanSnapshot referencing keyword_clusters) works fine without `foreign_keys=` disambiguation since each model only has one FK to that table
---
