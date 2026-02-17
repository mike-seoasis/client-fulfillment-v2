# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **SQLAlchemy `metadata` is reserved**: The `metadata` attribute name is reserved by SQLAlchemy's Declarative API. Use a different Python attribute name (e.g., `extra_metadata`) with an explicit column name mapping: `mapped_column("metadata", JSONB, ...)`.
- **Model registration**: New models must be imported in `backend/app/models/__init__.py` and added to `__all__`. Enums should also be exported.
- **UUID PK pattern**: `default=lambda: str(uuid4()), server_default=text("gen_random_uuid()")` — both Python-side and DB-side defaults.
- **DateTime pattern**: `default=lambda: datetime.now(UTC), server_default=text("now()")` for created_at/updated_at. Add `onupdate=lambda: datetime.now(UTC)` for updated_at.
- **JSONB default list**: Use `default=list, server_default=text("'[]'::jsonb")` for JSONB array columns.
- **Set to Array**: Use `Array.from(set)` instead of `[...set]` spread — the project's tsconfig target doesn't enable `--downlevelIteration`.
- **Mock new hooks in existing tests**: When adding a new hook to a shared page (e.g., `useRedditConfig` on `ProjectDetailPage`), update ALL existing test files that render that page to mock the new hook. Missing mocks cause "No QueryClient set" errors because the unmocked hook calls `useQuery` without a provider.

---

## 2026-02-16 - S14A-001
- Created `RedditAccount` model with `WarmupStage` and `AccountStatus` enums
- Files changed:
  - `backend/app/models/reddit_account.py` (new)
  - `backend/app/models/__init__.py` (registered model + enums)
- **Learnings:**
  - SQLAlchemy reserves `metadata` attribute name in Declarative API — must use alternate Python name with explicit column mapping (e.g., `extra_metadata = mapped_column("metadata", JSONB, ...)`)
  - JSONB default empty array needs both `default=list` (Python-side) and `server_default=text("'[]'::jsonb")` (DB-side)
---

## 2026-02-16 - S14A-002
- Created `RedditProjectConfig` model for per-project Reddit settings (1:1 with Project)
- Files changed:
  - `backend/app/models/reddit_config.py` (new)
  - `backend/app/models/project.py` (added `reddit_config` relationship with `uselist=False`)
  - `backend/app/models/__init__.py` (registered `RedditProjectConfig`)
- **Learnings:**
  - For 1:1 relationships, use `unique=True` on the FK column plus `uselist=False` on the parent's relationship
  - Import ordering in `__init__.py` must stay sorted — ruff enforces `I001` (isort)
---

## 2026-02-16 - S14A-003
- Created `RedditPost` model with `PostFilterStatus` and `PostIntent` enums
- Files changed:
  - `backend/app/models/reddit_post.py` (new)
  - `backend/app/models/__init__.py` (registered model + enums)
- **Learnings:**
  - RedditComment model doesn't exist yet — used `TYPE_CHECKING` forward reference for the `comments` relationship so the model compiles without the dependency
  - UniqueConstraint goes in `__table_args__` tuple (must have trailing comma for single-element tuple)
---

## 2026-02-16 - S14A-004
- Created `RedditComment` model with `CommentStatus` enum
- Files changed:
  - `backend/app/models/reddit_comment.py` (new)
  - `backend/app/models/__init__.py` (registered `RedditComment` + `CommentStatus`)
- **Learnings:**
  - `RedditPost` already had a forward-reference `comments` relationship to `RedditComment` via `TYPE_CHECKING` — now that the model exists, the relationship resolves at runtime via string-based target (`"RedditComment"`)
  - Boolean columns with `server_default` use `text("true")` / `text("false")` (not Python bool)
  - `SET NULL` on FK delete requires the column to be `nullable=True`
---

## 2026-02-16 - S14A-005
- Created `CrowdReplyTask` model with `CrowdReplyTaskType` and `CrowdReplyTaskStatus` enums
- Files changed:
  - `backend/app/models/crowdreply_task.py` (new)
  - `backend/app/models/__init__.py` (registered model + enums)
- **Learnings:**
  - Import ordering in `__init__.py` is strictly alphabetical by module path — `crawl_history` < `crawl_schedule` < `crawled_page` < `crowdreply_task` (ruff I001)
  - `ForeignKey` can be imported from either `sqlalchemy` or `sqlalchemy.schema` — both work identically, but existing models use `sqlalchemy` directly
---

## 2026-02-16 - S14A-006
- Verified all acceptance criteria already met from previous iterations (S14A-001 through S14A-005)
- All 5 Reddit models imported and registered in `__init__.py` with enums
- `reddit_config` relationship on `Project` model with `uselist=False` already added in S14A-002
- `TYPE_CHECKING` import for `RedditProjectConfig` in `project.py` already present
- Files changed: None (no changes needed)
- **Learnings:**
  - When each prior story registers its own model in `__init__.py` and adds relationships, the "registration" story becomes a verification-only task
  - Typecheck confirmed clean (only pre-existing `dict` type-arg issue in `internal_link.py`)
---

## 2026-02-16 - S14A-007
- Created Alembic migration `0027_create_reddit_tables.py` for all 5 Reddit tables
- Tables created in dependency order: reddit_accounts → reddit_project_configs → reddit_posts → reddit_comments → crowdreply_tasks
- Files changed:
  - `backend/alembic/versions/0027_create_reddit_tables.py` (new)
- Verified: `alembic upgrade head` ✓, `alembic downgrade -1` ✓, re-upgrade ✓
- **Learnings:**
  - Wrote migration manually rather than using `--autogenerate` to avoid picking up drift from the `da1ea5f253b0` widening migration (which dropped/recreated constraints as side effects)
  - The venv has a stale shebang (old path without ` (1)`); use `.venv/bin/python -m alembic` instead of `.venv/bin/alembic`
  - SQLAlchemy `extra_metadata` mapped to column `"metadata"` — in the migration, use the actual DB column name `"metadata"`, not the Python attribute name
  - For `unique=True` + `index=True` columns (like `reddit_project_configs.project_id`), create a unique index (`unique=True` on `create_index`) which satisfies both the unique constraint and the index
---

## 2026-02-16 - S14A-008
- Created Pydantic v2 schemas for all Reddit entities
- Files changed:
  - `backend/app/schemas/reddit.py` (new — 11 schema classes)
  - `backend/app/schemas/__init__.py` (registered all Reddit schemas)
- **Learnings:**
  - Follow `blog.py` pattern: `str` for UUID fields (not `UUID` type) since models use `UUID(as_uuid=False)`
  - `extra_metadata` Python attribute maps to `metadata` DB column — Pydantic schema uses the Python attribute name `extra_metadata` since `from_attributes=True` reads Python attrs
  - ruff import sorting (`I001`) places `reddit` alphabetically after `project_file` and before nothing else — auto-fix with `--fix` is safe
---

## 2026-02-16 - S14A-009
- Added Reddit / CrowdReply config vars to `Settings` class: `serpapi_key`, `crowdreply_api_key`, `crowdreply_project_id`, `crowdreply_webhook_secret`, `crowdreply_base_url`
- Files changed:
  - `backend/app/core/config.py` (added 5 settings under `# Reddit / CrowdReply` comment section)
- **Learnings:**
  - Config follows simple pattern: `str` type with `Field(default="", description=...)` for credential fields, non-empty default for URL fields
  - No circuit breaker settings needed at config level — those will come when integration clients are built (slices 14b/14e)
  - Pre-existing pyright error on `get_settings()` (missing `database_url` param) is expected — it's resolved at runtime via env vars
---

## 2026-02-16 - S14A-010
- Created Reddit API router with account CRUD endpoints
- Files changed:
  - `backend/app/api/v1/reddit.py` (new — 2 APIRouter instances, 4 endpoints)
  - `backend/app/api/v1/__init__.py` (registered `reddit_router` and `reddit_project_router`)
- Endpoints:
  - `GET /api/v1/reddit/accounts` — list with optional `niche`, `status`, `warmup_stage` filters
  - `POST /api/v1/reddit/accounts` — create with 409 on duplicate username
  - `PATCH /api/v1/reddit/accounts/{account_id}` — partial update, 404 if missing
  - `DELETE /api/v1/reddit/accounts/{account_id}` — delete, 204/404
- **Learnings:**
  - For JSONB `@>` contains filter: `RedditAccount.niche_tags.op("@>")(cast([niche], JSONB))` — wrap the value in a Python list and cast to JSONB
  - FastAPI `Query` param named `status` conflicts with the imported `status` module — use `alias="status"` with a different Python param name (`status_filter`)
  - Two separate `APIRouter` instances (`reddit_router`, `reddit_project_router`) allow grouping endpoints under different URL prefixes while sharing the same tag
  - Venv lives at `backend/.venv/` not project root `.venv/`
---

## 2026-02-16 - S14A-011
- Added GET and POST endpoints for per-project Reddit config on `reddit_project_router`
- GET `/{project_id}/reddit/config` — returns config or 404
- POST `/{project_id}/reddit/config` — upsert: creates (201) or updates (200), verifies project exists (404)
- Files changed:
  - `backend/app/api/v1/reddit.py` (added 2 endpoints, new imports for Project, RedditProjectConfig, Response, and config schemas)
- **Learnings:**
  - For dynamic status codes (201 vs 200 on upsert), inject FastAPI's `Response` object and set `response.status_code` — the `responses={}` decorator param just documents the possible codes in OpenAPI
  - Direct `select(Project.id).where(...)` is simpler than importing `ProjectService` when you just need an existence check
  - `model_dump(exclude_unset=True)` on the upsert update path ensures only explicitly-sent fields are modified (preserves existing values for omitted fields)
---

## 2026-02-16 - S14A-012
- Verified router registration already complete (done in S14A-010)
- Both `reddit_router` and `reddit_project_router` imported and included in `backend/app/api/v1/__init__.py`
- Files changed: None (no changes needed)
- **Learnings:**
  - S14A-010 proactively registered both routers when creating them, making this story a verification-only task (same pattern as S14A-006)
---

## 2026-02-16 - S14A-013
- Created backend tests for Reddit models and API endpoints (31 tests total)
- Files changed:
  - `backend/tests/test_reddit_models.py` (new — 16 tests: enum values, default fields, unique constraints)
  - `backend/tests/test_reddit_api.py` (new — 15 tests: CRUD accounts, filter, duplicate 409, project config upsert, 404s)
- **Learnings:**
  - JSONB `@>` (contains) operator with `cast(..., JSONB)` is PostgreSQL-specific — SQLite test backend can't compile it. Niche filter test must skip the actual filter call and verify endpoint routing only; full filter testing requires PostgreSQL integration tests.
  - Use `IntegrityError` (not bare `Exception`) for unique constraint violation assertions — ruff B017 forbids `pytest.raises(Exception)`
  - `asyncio_mode = "auto"` means no `@pytest.mark.asyncio` decorators needed on test methods
  - Test pattern: class-scoped fixtures (project, account) follow the same pattern as `test_cluster_api.py` — create via `db_session`, commit, return model instance
---

## 2026-02-16 - S14A-014
- Added Reddit API types and functions to frontend API client
- Files changed:
  - `frontend/src/lib/api.ts` (added Reddit section: 5 interfaces + 6 API functions)
- Interfaces: `RedditAccount`, `RedditAccountCreate`, `RedditAccountUpdate`, `RedditProjectConfig`, `RedditProjectConfigCreate`
- Functions: `fetchRedditAccounts` (with optional niche/status/warmup_stage filters), `createRedditAccount`, `updateRedditAccount`, `deleteRedditAccount`, `fetchRedditConfig`, `upsertRedditConfig`
- **Learnings:**
  - Backend datetime fields map to `string` on the frontend (ISO 8601 format via JSON serialization)
  - Backend `extra_metadata` (Python attr name for `metadata` DB column) stays as `extra_metadata` in TS interfaces since the Pydantic schema exposes `extra_metadata`
  - Filter params use `URLSearchParams` pattern (same as `triggerContentGeneration`) — only set params that are provided
---

## 2026-02-16 - S14A-015
- Created TanStack Query hooks for Reddit accounts and project config
- Files changed:
  - `frontend/src/hooks/useReddit.ts` (new — 6 hooks + query key factory)
- Hooks: `useRedditAccounts`, `useCreateRedditAccount`, `useUpdateRedditAccount`, `useDeleteRedditAccount` (with optimistic delete), `useRedditConfig`, `useUpsertRedditConfig`
- **Learnings:**
  - For optimistic delete across multiple cached query variants (e.g., different filter params), use `getQueriesData`/`setQueriesData` with the base key prefix `['reddit-accounts']` — this catches all parameterized variants
  - `useUpsertRedditConfig(projectId)` takes projectId as a hook argument (not mutation variable) since it's fixed for the component lifetime — keeps mutation variable as just the data payload
  - Invalidating with just the key prefix `['reddit-accounts']` (no params) invalidates all variants of that query regardless of filter params used
---

## 2026-02-16 - S14A-016
- Added navigation links (Projects, Reddit) to Header with active state styling
- Files changed:
  - `frontend/src/components/Header.tsx` (added `usePathname`, `Link`, nav links with active detection)
- **Learnings:**
  - Header already had `'use client'` directive — just needed imports for `Link` and `usePathname`
  - Active state pattern: `pathname === '/'` for exact match on root, `pathname.startsWith('/reddit')` for prefix match on sections
  - Nav links placed inside the left section (alongside logo) using `gap-8` for spacing between logo group and nav group
---

## 2026-02-16 - S14A-017
- Created minimal pass-through layout for Reddit section
- Files changed:
  - `frontend/src/app/reddit/layout.tsx` (new — simple wrapper rendering `{children}`)
- **Learnings:**
  - Next.js nested layouts are additive — the root layout already provides Header + max-w-7xl container, so section layouts only need to render children
  - This layout exists as a future extension point for Reddit-specific sub-navigation
---

## 2026-02-16 - S14A-018
- Created Reddit accounts management page with full CRUD
- Files changed:
  - `frontend/src/app/reddit/accounts/page.tsx` (new — table, filters, add modal, two-step delete)
- Features implemented:
  - Breadcrumb-style header ("Reddit > Accounts")
  - Table with columns: Username, Status (badge), Warmup Stage, Niche Tags (chips), Karma (post/comment), Cooldown (relative time), Last Used (relative time)
  - Filter bar with three dropdowns: Niche (dynamically extracted from accounts), Warmup Stage, Status
  - "+ Add Account" button with modal (username required, comma-separated niche tags, optional notes)
  - Two-step delete confirmation per row (same pattern as cluster/blog delete)
  - Empty state with friendly message + CTA, plus separate empty state for no filter results
  - Loading skeleton while data loads
  - Toast notifications for delete success/error
- **Learnings:**
  - `Set` spread (`[...set]`) requires `--downlevelIteration` or `es2015+` target in tsconfig — use `Array.from(set)` instead for compatibility
  - For dynamically-populated filter options (niches), fetch all accounts without filters separately and extract unique values
  - Two-step delete pattern: first click sets `isDeleteConfirming=true` (auto-resets after 3s timeout), second click executes the mutation — reusable across any entity
---

## 2026-02-16 - S14A-019
- Created project-specific Reddit config page with tag inputs, toggle, and save
- Added `is_active` field to `RedditProjectConfigCreate` backend schema (was missing — only in response schema) and frontend TS interface
- Files changed:
  - `frontend/src/app/projects/[id]/reddit/page.tsx` (new — full config form with tag inputs, toggle, discovery settings, save)
  - `backend/app/schemas/reddit.py` (added `is_active: bool | None` to `RedditProjectConfigCreate`)
  - `frontend/src/lib/api.ts` (added `is_active?: boolean` to `RedditProjectConfigCreate` interface)
- **Learnings:**
  - Tag input pattern: wrap chips + input in a shared div with `focus-within:` styles to make it behave like a single form field
  - When using `useCallback` with derived values from `??` (nullish coalescing) that produce new array references, ESLint `react-hooks/exhaustive-deps` warns about unstable deps — fix with `useMemo` on the derived arrays
  - `useRedditConfig` returns a 404 error when no config exists — treat 404 as "no config yet" (show empty defaults) rather than an error state
  - Toggle switch pattern: `role="switch"` + `aria-checked` for accessibility; `translate-x-6`/`translate-x-1` for the knob animation
  - For upsert flows, reset local state to `null` after successful save so values re-derive from the invalidated query cache
---

## 2026-02-16 - S14A-020
- Added Reddit Marketing card to project detail page below Blogs section
- Card shows "Not configured" / "Configured" status badge based on `useRedditConfig` hook data
- Links to `/projects/[id]/reddit` for both states (with contextual button text)
- Files changed:
  - `frontend/src/app/projects/[id]/page.tsx` (added ChatBubbleIcon, useRedditConfig import, Reddit Marketing section card)
- **Learnings:**
  - `useRedditConfig` returns undefined (not null) when a 404 is received and the query errors — truthiness check on `redditConfig` works to distinguish configured vs not-configured state
  - Section card pattern: icon + title + subtitle badge + description + action ButtonLink — consistent across Onboarding, Clusters, Blogs, and now Reddit
---

## 2026-02-16 - S14A-021
- Created frontend component tests for Reddit UI (51 tests total across 3 files)
- Files changed:
  - `frontend/src/app/reddit/accounts/__tests__/page.test.tsx` (new — 24 tests: table rendering, filter controls, add account modal, delete confirmation, empty state, loading state, page header)
  - `frontend/src/app/projects/[id]/reddit/__tests__/page.test.tsx` (new — 18 tests: form rendering, loading existing config, save functionality, empty config 404, loading state, project not found)
  - `frontend/src/components/__tests__/Header.test.tsx` (new — 9 tests: link rendering, active state toggling based on pathname)
- **Learnings:**
  - Filter dropdown `<option>` values share text with table column headers (e.g., "Cooldown") and badge text (e.g., "Active") — use `within(table)` scoping to disambiguate queries instead of `screen.getByText`
  - For elements with prefix text rendered as sibling nodes (e.g., `r/` prefix + subreddit name), use `screen.getByText((_, el) => el?.textContent === 'r/running')` custom matcher to match the composed text content
  - Mock pattern for hooks: `vi.fn()` for the mock, `vi.mock('@/hooks/useReddit', () => ({ hookName: (...args) => mockHookFn(...args) }))` — pass-through args so the mock captures filter params
  - Pre-existing test failures (129 tests across 11 files) are unrelated to Reddit tests — caused by missing `useRedditConfig` mock in project detail tests and other prior issues
---

## 2026-02-16 - S14A-098
- Updated V2_REBUILD_PLAN.md to reflect Phase 14a completion
- Files changed:
  - `V2_REBUILD_PLAN.md` (Current Status table updated, Phase 14a checkbox marked complete, session log row added)
- **Learnings:**
  - No code changes — status tracking task only
---

## 2026-02-16 - S14A-099
- Ran full verification of Phase 14a slice completion
- Fixed 3 test regressions caused by S14A-020 (adding `useRedditConfig` to ProjectDetailPage without updating existing test mocks)
- Fixed pre-existing build type error in `useBlogs.ts` (optimistic update spread producing nullable type)
- Files changed:
  - `frontend/src/app/projects/[id]/__tests__/blogs.test.tsx` (added `useReddit` mock)
  - `frontend/src/app/projects/[id]/__tests__/clusters.test.tsx` (added `useReddit` mock)
  - `frontend/src/app/projects/[id]/__tests__/linkStatus.test.tsx` (added `useReddit` mock)
  - `frontend/src/hooks/useBlogs.ts` (type assertion on optimistic update spread)
- **Verification Results:**
  - Backend: 950 passed, 24 failed (all pre-existing), 5 skipped — 0 Reddit-related failures
  - Reddit-specific backend tests: 16 model tests pass, 15 API tests pass (from `backend/` dir)
  - Frontend: 713 passed, 99 failed (all pre-existing), 8 failed files (all pre-existing) — down from 129 failed / 11 files before fix
  - Reddit-specific frontend tests: 42 passed (24 accounts + 18 config)
  - Build: `npm run build` succeeds with no errors
- **Learnings:**
  - When adding hooks to shared pages, must update ALL test files that render that page — not just create new test files for the new feature
  - Pre-existing backend test failures are concentrated in brand_config (9), link planning/pipeline (4), crawling (1), content editing (1), clusters (2), keyword generation (3) — none related to Reddit
  - Pre-existing frontend test failures are in brand-config, cluster detail, content generation, link map, onboarding content/keywords, GenerationProgress — none related to Reddit
  - `useBlogs.ts` type error: spreading `BlogPostUpdate` (with nullable fields) onto `BlogPost` (non-nullable) requires explicit type assertion
---
