# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Model file pattern**: UUID(as_uuid=False) with `str` Mapped type, `text("gen_random_uuid()")` server_default, `lambda: str(uuid4())` Python default. DateTime(timezone=True) with `text("now()")` server_default. Boolean with `text("false")` server_default.
- **Model registration**: Add import to `backend/app/models/__init__.py` and include in `__all__` list (alphabetically sorted).
- **Relationships with back_populates**: Always define both sides. Use `TYPE_CHECKING` guard for imports to avoid circular deps. Parent side uses `cascade="all, delete-orphan"` with list type. Child FK uses `ondelete="CASCADE"` or `ondelete="SET NULL"` as appropriate.
- **Python env**: Use `.venv/bin/python` (not bare `python`) for running tools in backend.
- **Alembic env.py imports**: When adding new models, also add imports to `backend/alembic/env.py` so autogenerate can detect schema changes.
- **Migration naming**: Sequential `0NNN_description.py` with revision ID `"0NNN"`, `down_revision` pointing to previous. Named FK constraints: `fk_{table}_{column}`.

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

## 2026-02-08 - S8-004
- Created Alembic migration `0023_add_keyword_clusters_and_cluster_pages.py`
- Migration creates `keyword_clusters` table with all columns (id, project_id, seed_keyword, name, status, generation_metadata, created_at, updated_at) plus FK and indexes
- Migration creates `cluster_pages` table with all columns (id, cluster_id, keyword, role, url_slug, expansion_strategy, reasoning, search_volume, cpc, competition, competition_level, composite_score, is_approved, crawled_page_id, created_at, updated_at) plus FKs and indexes
- Migration adds `source` column to `crawled_pages` with server_default `'onboarding'` and backfills existing rows
- Migration is fully reversible (downgrade drops column/index, then both tables)
- Added `KeywordCluster` and `ClusterPage` imports to `alembic/env.py` for autogenerate support
- **Files changed:**
  - `backend/alembic/versions/0023_add_keyword_clusters_and_cluster_pages.py` (new)
  - `backend/alembic/env.py` (added model imports)
- **Learnings:**
  - `alembic upgrade head` cannot run locally due to space in project path (`Projects (1)`) — `version_locations = %(here)s/alembic/versions` splits on the space, producing two invalid paths. This is an environment-specific issue, not a migration issue.
  - Migration file loads and type-checks cleanly via direct Python import
  - Follow existing migration patterns: `postgresql.UUID(as_uuid=False)`, named FK constraints (`fk_{table}_{column}`), `op.f()` for index names
  - Always add new model imports to `alembic/env.py` so autogenerate can detect schema changes
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-005
- Created `backend/app/schemas/cluster.py` with 5 Pydantic v2 schemas: ClusterCreate, ClusterPageResponse, ClusterResponse, ClusterListResponse, ClusterPageUpdate
- Registered all schemas in `backend/app/schemas/__init__.py` with imports and `__all__` entries
- All response schemas use `model_config = ConfigDict(from_attributes=True)`
- ClusterCreate: seed_keyword (str, min_length=2), name (str | None = None)
- ClusterPageResponse: all ClusterPage model fields with proper types
- ClusterResponse: full cluster with nested list[ClusterPageResponse] pages
- ClusterListResponse: summary with page_count (int) and approved_count (int) for list views
- ClusterPageUpdate: all optional fields (is_approved, keyword, url_slug, role)
- **Files changed:**
  - `backend/app/schemas/cluster.py` (new)
  - `backend/app/schemas/__init__.py` (added imports + __all__ entries)
- **Learnings:**
  - Import order in `__init__.py` matters — ruff enforces alphabetical sorting of import blocks (I001)
  - `cluster` sorts after `categorize` but before `content_brief`
  - All quality checks (mypy, ruff) pass clean
---
