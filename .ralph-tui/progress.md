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

## 2026-02-08 - S8-014
- Verified clusters router already registered in S8-012 — no additional changes needed
- Confirmed: `clusters_router` imported and included in `backend/app/api/v1/__init__.py`
- Confirmed: Router prefix `/projects` matches project path pattern (full path: `/api/v1/projects/{project_id}/clusters/...`)
- Confirmed: All 6 endpoints accessible (POST create, GET list, GET detail, PATCH update page, POST approve, DELETE)
- **Files changed:** None (already implemented in S8-012)
- **Learnings:**
  - S8-012 proactively completed S8-014's scope (router registration) as part of creating the router file
  - Always check progress.md first — previous stories may have already covered the work
  - All quality checks (ruff) pass clean
---

## 2026-02-08 - S8-017
- Added 6 TypeScript interfaces to `frontend/src/lib/api.ts`: ClusterCreate, ClusterPage, Cluster, ClusterListItem, ClusterPageUpdate, ClusterBulkApproveResponse
- Added 6 API client functions: createCluster, getClusters, getCluster, updateClusterPage, bulkApproveCluster, deleteCluster
- All functions follow existing apiClient pattern (get/post/patch/delete with typed generics)
- Types match backend Pydantic schemas exactly (ClusterResponse → Cluster, ClusterListResponse → ClusterListItem, ClusterPageResponse → ClusterPage)
- **Files changed:**
  - `frontend/src/lib/api.ts` (added cluster types + API functions)
- **Learnings:**
  - Frontend has no separate types.ts file — all types and API functions colocate in `frontend/src/lib/api.ts`
  - Pattern: types section with `// ===` banner, then functions section with same banner
  - DateTime fields from backend map to `string` in TS (ISO format), dict/JSONB maps to `Record<string, unknown> | null`
  - Pre-existing TS error in GenerationProgress.test.tsx (tuple index out of bounds) — unrelated to this change
  - All quality checks (tsc, eslint) pass clean
---

## 2026-02-08 - S8-018
- Created `frontend/src/hooks/useClusters.ts` with 6 TanStack Query hooks and query keys factory
- `clusterKeys` factory: `list(projectId)` and `detail(projectId, clusterId)` for consistent cache key management
- `useCreateCluster()`: useMutation calling `createCluster()`, invalidates cluster list on success
- `useClusters(projectId)`: useQuery fetching cluster list (ClusterListItem[])
- `useCluster(projectId, clusterId)`: useQuery fetching cluster detail with pages (Cluster)
- `useUpdateClusterPage()`: useMutation with optimistic update — cancels in-flight queries, patches page in cache, rolls back on error, invalidates on settle
- `useBulkApproveCluster()`: useMutation invalidating both cluster detail and list on success
- `useDeleteCluster()`: useMutation invalidating cluster list on success
- **Files changed:**
  - `frontend/src/hooks/useClusters.ts` (new)
- **Learnings:**
  - Optimistic update pattern: `onMutate` cancels queries + snapshots previous data + applies optimistic update; `onError` rolls back; `onSettled` invalidates for server truth
  - Query key convention: `['projects', projectId, 'clusters']` for list, `['projects', projectId, 'clusters', clusterId]` for detail — matches existing patterns (e.g., `pages-with-keywords`)
  - Mutation input types defined locally in the hooks file (not exported from api.ts) since they bundle projectId with the API params
  - Pre-existing TS error in GenerationProgress.test.tsx continues — unrelated to this change
  - All quality checks (tsc, eslint) pass clean
---

## 2026-02-08 - S8-020
- Created `frontend/src/app/projects/[id]/clusters/[clusterId]/page.tsx` — cluster suggestions and approval page
- Header shows cluster name, seed keyword, and 4-step stepper (Keywords → Content → Review → Export) with Keywords active
- Displays all ClusterPage suggestions in a sorted list (parent pinned to top, then by composite_score descending)
- Each row shows: editable keyword (click to edit), role badge (Parent in palm-500 green / Child in neutral), search volume, CPC, competition level, composite score, editable URL slug (click to edit), expansion strategy tag
- Parent page visually distinguished with `bg-palm-50/40` background and left border accent
- Approve/reject toggle per suggestion (checkbox) using `useUpdateClusterPage`
- Inline editing for keyword and URL slug — saves on blur or Enter key, cancels on Escape
- 'Make Parent' action on child rows — reassigns parent role via PATCH (backend handles demoting old parent)
- 'Approve All' button approves all unapproved suggestions
- 'Generate Content' button calls `useBulkApproveCluster`, navigates to content generation page on success. Disabled with tooltip when no pages approved.
- Warning banner when `volume_unavailable` flag is set in `generation_metadata`
- Back button navigates to project detail page
- **Files changed:**
  - `frontend/src/app/projects/[id]/clusters/[clusterId]/page.tsx` (new)
- **Learnings:**
  - `sortedPages` computed in render needs `useMemo` when used in `useCallback` dependencies, otherwise `react-hooks/exhaustive-deps` warns about conditional references creating new arrays each render
  - Stepper pattern from onboarding keywords page is reusable — just swap `ONBOARDING_STEPS` for `CLUSTER_STEPS` with different labels
  - InlineEditableCell component pattern: use `setTimeout` to focus input after state change (React batches updates), save on blur/Enter, cancel on Escape
  - `generation_metadata` is typed as `Record<string, unknown> | null` in frontend — needs cast when checking specific fields like `volume_unavailable`
  - Pre-existing TS error in GenerationProgress.test.tsx continues — unrelated to this change
  - All quality checks (tsc, eslint) pass clean
---

## 2026-02-08 - S8-019
- Created `frontend/src/app/projects/[id]/clusters/new/page.tsx` — seed keyword input page
- Form with Seed Keyword (required, min 2 chars) and Cluster Name (optional) fields
- Cancel button navigates back to project detail page
- Get Suggestions button triggers `useCreateCluster` mutation
- 3-step progress indicator during loading: Generating suggestions → Checking search volume → Finalizing results (timed at 3s/6s intervals to show activity during ~5-10s API call)
- On success, navigates to `/projects/{id}/clusters/{newClusterId}`
- On error, shows error message with Try Again button
- Follows design system: bg-white card with border-cream-500, palm-500 primary button, cream-200 secondary, rounded-sm, warm grays
- Reuses existing `Input` and `Button` UI components, `useProject` and `useCreateCluster` hooks
- **Files changed:**
  - `frontend/src/app/projects/[id]/clusters/new/page.tsx` (new)
- **Learnings:**
  - Progress step animation uses `setTimeout` timers that are cleared on success/error to avoid stale state updates
  - `useCreateCluster` returns the full `Cluster` object on success including `id` — used for navigation
  - Input component has built-in `error` prop for validation display — no need for custom error rendering
  - Pre-existing TS error in GenerationProgress.test.tsx continues — unrelated to this change
  - All quality checks (tsc, eslint) pass clean
---

## 2026-02-08 - S8-021
- Updated New Content section in `frontend/src/app/projects/[id]/page.tsx` to show live cluster list
- Added `useClusters` hook to fetch cluster data for the project
- Cluster cards display: cluster name (falls back to seed_keyword), page count, status badge
- Clicking a cluster card navigates to `/projects/{id}/clusters/{clusterId}`
- "+ New Cluster" button in header (when clusters exist) and in empty state navigates to `/projects/{id}/clusters/new`
- Empty state shows "No clusters yet" with prominent "+ New Cluster" button
- Added `ClusterStatusBadge` component mapping all 5 statuses: generating, suggestions_ready (Awaiting Approval), approved, content_generating (Generating Content), complete
- Cards follow design system: `border-sand-500`, `rounded-sm`, warm shadows, hover shadow transition
- **Files changed:**
  - `frontend/src/app/projects/[id]/page.tsx` (added useClusters import, cluster fetch, ClusterStatusBadge component, replaced placeholder with live cluster list)
- **Learnings:**
  - ClusterListItem has `name` and `seed_keyword` — display `name || seed_keyword` since name is optional
  - Reused existing icon components (CheckCircleIcon, CircleIcon, SpinnerIcon) for status badges — consistent with BrandConfigStatusBadge pattern
  - Pre-existing TS error in GenerationProgress.test.tsx continues — unrelated to this change
  - All quality checks (tsc, eslint) pass clean
---

## 2026-02-08 - S8-015
- Created `backend/tests/test_cluster_keyword_service.py` with 52 unit tests across 8 test classes
- **TestBuildBrandContext** (6 tests): full config, partial config, empty config, malformed data, empty personas, empty competitors
- **TestGenerateCandidates** (7 tests): success with brand context, 11 strategies in prompt, JSON markdown code block parsing, seed keyword first, seed deduplication, Claude failure, too few candidates
- **TestEnrichWithVolume** (5 tests): success with volume data, DataForSEO unavailable, API failure returns unchanged, unexpected exception, keyword not found in results
- **TestFilterAndAssignRoles** (6 tests): parent/child assignment, URL slug format, composite score calculation + sorting, seed role enforced in code, duplicate filtering, Claude failure
- **TestKeywordToSlug** (12 tests): basic conversion, special chars stripped, spaces collapsed, leading/trailing hyphens, long keyword truncation, no trailing hyphen after truncation, numbers preserved, mixed special chars, already clean slug, unicode stripped, empty result
- **TestCalculateCompositeScore** (5 tests): all values, null volume, null competition, competition normalization (0-100 vs 0-1), zero volume
- **TestGenerateCluster** (5 tests): full pipeline success, partial failure (DataForSEO down), total failure (Claude down Stage 1), Stage 3 failure, name defaults to seed
- **TestBulkApproveCluster** (6 tests): CrawledPage creation with source='cluster', PageKeywords with is_priority for parent, crawled_page_id backref, no approved pages error, already approved error, status update to 'approved'
- **Files changed:**
  - `backend/tests/test_cluster_keyword_service.py` (new)
- **Learnings:**
  - Mock pattern for ClaudeClient: `MagicMock()` with `available` property + `AsyncMock()` for `complete()`, return `CompletionResult` dataclass
  - Mock pattern for DataForSEOClient: `MagicMock()` with `available` property + `AsyncMock()` for `get_keyword_volume_batch()`, return `KeywordVolumeResult` with `KeywordVolumeData` list
  - Session-scoped SQLite DB persists data across tests — queries in bulk_approve tests need scoping (e.g., `crawled_page_id.in_(cp_ids)`) to avoid stale data from prior test runs
  - `claude.complete.side_effect = [result1, result2]` for mocking sequential calls (Stage 1 then Stage 3)
  - Project model uses `site_url` field, not `website_url`
  - All quality checks (ruff, mypy, pytest) pass clean — 52/52 tests pass
---

## 2026-02-08 - S8-016
- Created `backend/tests/test_cluster_api.py` with 20 integration tests in 1 test class (TestClusterAPI)
- **POST create cluster** (2 tests): success with mocked Claude + DataForSEO verifying response schema (seed_keyword, name, status, pages with parent role), 404 for invalid project
- **GET list clusters** (3 tests): page_count and approved_count computed correctly, empty project returns [], 404 for invalid project
- **GET cluster detail** (3 tests): all ClusterPage fields returned (13 fields verified), 404 for invalid cluster_id, 404 for invalid project_id
- **PATCH update page** (5 tests): approve toggle, edit keyword, edit slug, reassign parent (demotes old parent to child verified via GET detail), 404 for invalid page
- **POST bulk-approve** (3 tests): CrawledPage + PageKeywords created with correct counts, 400 for no approved pages, 409 for already-approved cluster
- **DELETE cluster** (4 tests): draft deletion returns 204 and removes from DB, 409 for approved cluster, 404 for invalid cluster, 404 for invalid project
- **Files changed:**
  - `backend/tests/test_cluster_api.py` (new)
- **Learnings:**
  - `KeywordVolumeResult` constructor uses `success` + `keywords` fields, not `data` + `errors` — always check dataclass field names
  - `AsyncSession.expire_all()` is synchronous (not awaitable) — but causes greenlet issues when test session differs from endpoint session
  - Integration tests use `async_client` fixture which creates its own DB session via `mock_db_manager` — the test's `db_session` fixture is a separate session. Verifying endpoint side-effects requires either: (a) a fresh session from `async_session_factory`, or (b) querying via the API endpoints themselves
  - Pattern for verifying parent reassignment: use GET detail endpoint to check all page roles after PATCH, avoids cross-session greenlet issues
  - `patch("app.api.v1.clusters.get_claude", return_value=mock_claude)` — patch the dependency getter at the module where it's imported, not at the source module
  - Pre-existing mypy errors in `crawl4ai.py` — unrelated to this change
  - All quality checks (ruff, mypy, pytest) pass clean — 20/20 tests pass
---

## 2026-02-08 - S8-022
- Created 3 frontend test files with 71 total tests using Vitest + React Testing Library
- **NewClusterPage tests** (22 tests): form rendering (seed keyword input, cluster name input, buttons, breadcrumb), validation (empty/short keyword disabled, 2+ chars enabled), loading state (skeleton, progress indicator, form hidden during pending), submission (mutate called with correct args, includes optional name), navigation (success redirects to cluster detail, cancel links back), error state (error message, Try Again/Cancel buttons), not found state (fetch failure, null project)
- **ClusterDetailPage tests** (33 tests): suggestion list rendering (all pages displayed, cluster name, seed keyword label, summary stats, search volume/CPC/composite score/expansion strategy), parent badge display (Parent/Child badges, Make Parent only on children), approval toggle (renders per page, toggle calls updateClusterPage for approve/reject), inline editing (editable buttons, click opens input, save on blur with changed value), Approve All (renders, calls update for unapproved pages, disabled when all approved), Generate Content button (renders, disabled/enabled based on approved count, calls bulkApproveCluster, disabled with correct label), step indicator (Keywords as step 1 of 4, all labels), volume unavailable warning (shows/hides based on metadata), loading/not found states, back navigation
- **ProjectDetailPage cluster section tests** (16 tests): empty state (no clusters message, New Cluster button with correct link), cluster cards rendering (names, page counts singular/plural, seed_keyword fallback, all 5 status badges), click navigation (cards link to cluster detail), New Cluster button in header (present when clusters exist, correct link), section header (New Content title, Keyword Clusters badge)
- **Files changed:**
  - `frontend/src/app/projects/[id]/clusters/new/__tests__/page.test.tsx` (new)
  - `frontend/src/app/projects/[id]/clusters/[clusterId]/__tests__/page.test.tsx` (new)
  - `frontend/src/app/projects/[id]/__tests__/clusters.test.tsx` (new)
- **Learnings:**
  - When a keyword appears both in seed keyword display and editable row, use `getAllByText` instead of `getByText` to avoid "found multiple elements" error
  - `userEvent.hover()` does not trigger `onMouseEnter` on disabled buttons in jsdom (browsers prevent pointer events on disabled elements) — use `fireEvent.mouseEnter` or test disabled state instead
  - Mocking multiple hooks from the same module (e.g., `useClusters`, `useUpdateClusterPage`, `useBulkApproveCluster`) works with a single `vi.mock` that returns all exports
  - For project detail page tests, 5 hooks need mocking: `use-projects`, `useBrandConfigGeneration`, `use-crawl-status`, `useClusters` — each with sensible defaults in `beforeEach`
  - Pre-existing test failures in GenerationProgress.test.tsx, KeywordPageRow.test.tsx, brand-config/page.test.tsx, content editor page.test.tsx — unrelated to this change
  - All quality checks (tsc, eslint, vitest) pass clean — 71/71 new tests pass
---
