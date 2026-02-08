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
- **ClaudeClient per-call model override**: `complete()` accepts optional `model` param to override `self._model` for a single call (e.g., `model="claude-haiku-4-5-20251001"`). Uses `effective_model = model or self._model`.

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

## 2026-02-08 - S8-006
- Created `backend/app/services/cluster_keyword.py` with `ClusterKeywordService` class
- Constructor takes `ClaudeClient` and `DataForSEOClient` (same pattern as `PrimaryKeywordService`)
- Implemented `_build_brand_context(brand_config: dict) -> str` static method
- Extracts: company name, primary products, price point, sales channels from `brand_foundation`; primary persona name and summary from `target_audience`; competitor names from `competitor_context`
- Returns formatted string with `## Brand`, `## Target Audience`, `## Competitors` sections
- Handles missing/incomplete/malformed brand config gracefully (skips missing sections, returns empty string if no data)
- **Files changed:**
  - `backend/app/services/cluster_keyword.py` (new)
- **Learnings:**
  - `_build_brand_context` is a `@staticmethod` since it doesn't need instance state — makes it easy to test independently
  - Brand config v2_schema structure: `brand_foundation.company_overview.company_name`, `brand_foundation.what_they_sell.primary_products_services`, etc.
  - Target audience primary persona is always `personas[0]` in the array
  - Competitor names live at `competitor_context.direct_competitors[].name`
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-007
- Implemented `_generate_candidates(seed_keyword, brand_context) -> list[dict]` on `ClusterKeywordService`
- 11-strategy expansion prompt: demographic, attribute, price/value, use-case, comparison/intent, seasonal/occasion, material/type, experience level, problem/solution, terrain/environment, values/lifestyle
- Prompt includes brand context section (from `_build_brand_context()`) when available
- Constrains output to collection-level keywords (not blog posts), each viable as standalone collection page
- Seed keyword always prepended as first candidate with `role_hint='parent'`
- Uses Claude Haiku (`claude-haiku-4-5-20251001`) via model override, `temperature=0.4`, `max_tokens=1500`
- Returns structured JSON: list of `{keyword, expansion_strategy, rationale, estimated_intent}`
- JSON parsing with markdown code block stripping (same pattern as `primary_keyword.py`)
- Validates minimum 5 candidates, deduplicates seed keyword from LLM output
- Added optional `model` parameter to `ClaudeClient.complete()` for per-call model override
- **Files changed:**
  - `backend/app/services/cluster_keyword.py` (added `_generate_candidates` method + `json` import + `HAIKU_MODEL` constant)
  - `backend/app/integrations/claude.py` (added optional `model` param to `complete()` + `effective_model` in request body)
- **Learnings:**
  - `ClaudeClient.complete()` didn't support per-call model override — added optional `model` parameter with backward-compatible default
  - The `complete()` method builds request body with `self._model` — needed to introduce `effective_model = model or self._model`
  - Prompt instructs "no markdown code blocks" but JSON parsing still handles them defensively (LLMs don't always follow instructions)
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-008
- Implemented `_enrich_with_volume(candidates: list[dict]) -> list[dict]` on `ClusterKeywordService`
- Extracts keyword strings from candidates and calls `DataForSEOClient.get_keyword_volume_batch()` in a single batch call
- Merges `search_volume`, `cpc`, `competition`, `competition_level` back into each candidate dict
- Three graceful fallback paths (all set `volume_unavailable=True`): DataForSEO not configured, API call fails, unexpected exception
- Keywords not found in volume results get `None` for all volume fields (no `volume_unavailable` flag since the lookup itself succeeded)
- **Files changed:**
  - `backend/app/services/cluster_keyword.py` (added `_enrich_with_volume` method)
- **Learnings:**
  - Pattern closely mirrors `PrimaryKeywordService.enrich_with_volume()` but adapted: takes/returns `list[dict]` instead of returning `dict[str, KeywordVolumeData]`
  - `get_keyword_volume_batch()` handles batching internally (splits into 1000-keyword chunks) so caller doesn't need to worry about limits
  - `KeywordVolumeData` dataclass fields map directly to the four fields needed: `search_volume`, `cpc`, `competition`, `competition_level`
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-009
- Implemented `_filter_and_assign_roles(candidates, seed_keyword) -> list[dict]` on `ClusterKeywordService`
- Implemented `_keyword_to_slug(keyword) -> str` static method for URL slug generation (lowercase, hyphens, no special chars, max 60 chars)
- Implemented `_calculate_composite_score(volume, competition, relevance) -> float` static method reusing PrimaryKeywordService formula
- Filtering prompt includes all candidates with volume/CPC/competition data, instructs Claude to filter to 8-12 best, remove near-duplicates, remove < 50 volume (unless < 5 remain), assign parent/child roles
- Each result includes: keyword, role, url_slug, expansion_strategy, reasoning, search_volume, cpc, competition, competition_level, composite_score
- Uses Claude Haiku with temperature=0.0 for deterministic filtering
- Results sorted by composite_score descending with parent always first
- Role assignment enforced in code (not just LLM output): seed keyword always gets role='parent' regardless of LLM response
- **Files changed:**
  - `backend/app/services/cluster_keyword.py` (added `_keyword_to_slug`, `_calculate_composite_score`, `_filter_and_assign_roles` methods + `math`, `re` imports)
- **Learnings:**
  - Composite score formula: 50% volume (log10 * 10, cap 50) + 35% relevance (*100) + 15% competition ((1-comp)*100). Null volume=0, null competition=50 (mid-range)
  - Competition normalization: DataForSEO can return 0-100 or 0-1 range, so normalize with `/ 100.0 if > 1.0`
  - Role assignment should be enforced in code, not trusted from LLM — seed keyword comparison uses normalized lowercase
  - URL slug generation: regex `[^a-z0-9\s-]` strips special chars, then `[\s-]+` collapses whitespace/hyphens, truncate at 60 chars with trailing hyphen strip
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-010
- Implemented `generate_cluster()` orchestrator method on `ClusterKeywordService`
- Runs Stage 1 → Stage 2 → Stage 3 sequentially with `time.perf_counter()` timing
- Creates `KeywordCluster` record with `status='suggestions_ready'` and `ClusterPage` records for each filtered candidate
- Stores `generation_metadata` JSONB with all timing and count fields (stage1/2/3_time_ms, total_time_ms, candidates_generated/enriched/filtered, volume_unavailable)
- Returns dict with `cluster_id`, `suggestions`, `generation_metadata`, `warnings`
- Partial failure handling: Stage 2 (DataForSEO) failure adds warning and continues to Stage 3
- Total failure handling: Stage 1 or Stage 3 failure raises `ValueError`, DB rollback on persistence failure
- **Files changed:**
  - `backend/app/services/cluster_keyword.py` (added `generate_cluster` method + `time`, `AsyncSession`, model imports)
- **Learnings:**
  - `_enrich_with_volume` already handles its own failure gracefully (sets `volume_unavailable` flag on candidates), so the orchestrator's Stage 2 error handling wraps the outer exception path plus checks the flag
  - `db.flush()` after adding the cluster gets the `cluster.id` for FK references in `ClusterPage` records
  - `db.rollback()` in the persistence except block ensures no partial cluster data is saved
  - Pattern for orchestrators: timing with `time.perf_counter()`, try/except per stage, metadata dict for observability
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-011
- Implemented `bulk_approve_cluster(cluster_id, db)` static method on `ClusterKeywordService`
- Bridges approved ClusterPage records into the content pipeline by creating CrawledPage + PageKeywords records
- Validation: 409 if cluster status already 'approved' or later; 400 if no approved pages
- For each approved ClusterPage: creates CrawledPage (source='cluster', status='completed', category='collection'), PageKeywords (is_approved=True, is_priority=True for parent role), and links ClusterPage.crawled_page_id
- Updates KeywordCluster.status to 'approved' on success
- Returns dict with bridged_count and crawled_page_ids
- Added imports: `select` from sqlalchemy, `CrawledPage`/`CrawlStatus`, `PageKeywords`
- **Files changed:**
  - `backend/app/services/cluster_keyword.py` (added `bulk_approve_cluster` method + new imports)
- **Learnings:**
  - Method is `@staticmethod` since it only needs db session, no ClaudeClient/DataForSEO — keeps it callable without service instantiation
  - SQLAlchemy Boolean comparison needs `== True` with `# noqa: E712` to suppress ruff's "use `is`" warning (SA doesn't support `is True`)
  - `db.flush()` inside the loop to get each CrawledPage.id before creating the dependent PageKeywords and updating ClusterPage.crawled_page_id
  - Pattern for status guards: set of valid statuses from enum values, check membership
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-012
- Created `backend/app/api/v1/clusters.py` with two endpoints:
  - `POST /api/v1/projects/{project_id}/clusters` — validates project, fetches BrandConfig, runs `generate_cluster()` with 30s timeout, returns `ClusterResponse`
  - `GET /api/v1/projects/{project_id}/clusters` — returns `list[ClusterListResponse]` with `page_count` and `approved_count` computed via SQL aggregation
- Registered clusters router in `backend/app/api/v1/__init__.py`
- POST endpoint uses `asyncio.wait_for()` for 30s timeout, returns 504 on timeout
- GET endpoint uses `outerjoin` + `func.count` + `func.nullif` to compute page_count/approved_count in a single query
- **Files changed:**
  - `backend/app/api/v1/clusters.py` (new)
  - `backend/app/api/v1/__init__.py` (added clusters router import + include)
- **Learnings:**
  - Ruff UP041: use builtin `TimeoutError` instead of `asyncio.TimeoutError` (alias deprecated)
  - `func.nullif(ClusterPage.is_approved, False)` makes `func.count` skip non-approved rows (count only non-NULL values)
  - Dependency injection pattern: `get_claude` and `get_dataforseo` from integrations for request-scoped clients
  - `selectinload(KeywordCluster.pages)` for eager loading relationship after creation
  - All quality checks (mypy, ruff) pass clean
---

## 2026-02-08 - S8-013
- Added 4 new endpoints to `backend/app/api/v1/clusters.py`:
  - `GET /{project_id}/clusters/{cluster_id}` — returns full ClusterResponse with all ClusterPage records via `selectinload`, 404 if not found
  - `PATCH /{project_id}/clusters/{cluster_id}/pages/{page_id}` — updates is_approved, keyword, url_slug, and/or role fields using `model_dump(exclude_unset=True)`. Parent reassignment: when setting role='parent', finds current parent in same cluster and demotes to 'child'. 404 if not found.
  - `POST /{project_id}/clusters/{cluster_id}/approve` — calls `bulk_approve_cluster()`, returns `{"bridged_count": N}`. Maps ValueError messages to 400 (no approved pages) or 409 (already approved).
  - `DELETE /{project_id}/clusters/{cluster_id}` — deletes cluster if status < 'approved' (generating or suggestions_ready), returns 204. Returns 409 if status >= 'approved'. Uses `db.delete()` with cascade from model relationship.
- Added imports: `ClusterStatus`, `ClusterPageResponse`, `ClusterPageUpdate`
- **Files changed:**
  - `backend/app/api/v1/clusters.py` (added 4 endpoints + updated imports)
- **Learnings:**
  - Parent reassignment pattern: query for existing parent first, demote to child, then apply the update — all in one transaction before `db.commit()`
  - `model_dump(exclude_unset=True)` correctly handles partial PATCH updates — only fields explicitly sent in the request body are applied
  - `bulk_approve_cluster` raises ValueError with distinct messages for 400 vs 409 cases — router maps these via substring matching on error message
  - Delete uses `db.delete(cluster)` which cascades to ClusterPages via model's `cascade="all, delete-orphan"`
  - All quality checks (mypy, ruff) pass clean
---
