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

## 2026-02-10 - S9-003
- Added `outbound_links` and `inbound_links` relationships to `CrawledPage` model
- Added `back_populates` to `InternalLink.source_page` and `InternalLink.target_page` relationships for bidirectional linking
- Added `InternalLink` to `TYPE_CHECKING` imports in `crawled_page.py`
- Models already registered in `__init__.py` from S9-001/S9-002
- **Files changed:**
  - `backend/app/models/crawled_page.py` (added TYPE_CHECKING import + two relationships)
  - `backend/app/models/internal_link.py` (added back_populates to source_page and target_page)
- **Learnings:**
  - When adding reverse relationships on a model with multi-FK ambiguity, use string-form `foreign_keys="[ClassName.column]"` on the parent side and `foreign_keys=[column]` on the child side
  - Both sides need `back_populates` for proper bidirectional behavior
  - `cascade="all, delete-orphan"` on the parent side ensures links are cleaned up when a page is deleted
---

## 2026-02-10 - S9-004
- Migrations already existed from S9-001 and S9-002 (0024 + 0025), so this was a verification task
- Verified `0024_create_internal_links_table.py` creates internal_links with all columns, FKs, and indexes
- Verified `0025_create_link_plan_snapshots_table.py` creates link_plan_snapshots with all columns, FKs, and indexes
- Ran `alembic upgrade head` successfully (0023 → 0024 → 0025)
- Verified reversibility: `alembic downgrade 0023` drops both tables cleanly, then re-upgraded to head
- **Files changed:** None (migrations already existed)
- **Learnings:**
  - When model creation stories (S9-001, S9-002) each create their own migration, the migration story (S9-004) becomes a verification task rather than a creation task
  - Always verify both upgrade AND downgrade paths when validating migrations
---

## 2026-02-10 - S9-005
- Created Pydantic v2 schemas for internal link management API
- 9 schema classes: LinkPlanRequest, LinkPlanStatusResponse, InternalLinkResponse, PageLinksResponse, LinkMapPageSummary, LinkMapResponse, AddLinkRequest, EditLinkRequest, AnchorSuggestionsResponse
- All use `Literal` types for constrained string fields (scope, anchor_type, status)
- `ConfigDict(from_attributes=True)` on InternalLinkResponse for ORM serialization
- Registered all schemas in `backend/app/schemas/__init__.py`
- **Files changed:**
  - `backend/app/schemas/internal_link.py` (new)
  - `backend/app/schemas/__init__.py` (added imports + __all__ entries)
- **Learnings:**
  - Pydantic v2 `Literal` types work well for constrained string enums in request schemas (cleaner than validator)
  - Ruff import sorter (isort) requires `internal_link` to sort alphabetically among other schema imports — placing it before `crawled_page` caused a re-sort
  - Response schemas that join data from relationships (e.g., InternalLinkResponse with target_url/target_title) don't need `from_attributes=True` if they'll be constructed manually rather than from ORM objects — but including it is harmless and future-proofs
---
