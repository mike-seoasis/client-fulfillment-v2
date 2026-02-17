## Context

Phase 14a is the data foundation for Reddit marketing integration. The existing V2 app has 11 completed phases with a consistent architecture: SQLAlchemy 2.0 models with UUID PKs and JSONB fields, Pydantic v2 schemas, FastAPI routers with dependency injection, TanStack Query hooks on the frontend. The blog phase (Phase 11) is the closest analog — it introduced 2 models, a new API router, and a new frontend section. Reddit introduces 5 models, a new API router, and a new top-level navigation section.

The app currently has no top-level navigation links — the header shows only a logo and user menu. Reddit is the first feature that needs its own section separate from the project context, so the header needs nav links added.

Current state:
- Latest migration: `0026_create_blog_tables.py` (plus a widening migration `da1ea5f253b0`)
- Router registration: `backend/app/api/v1/__init__.py` includes 8 routers
- Models registered in: `backend/app/models/__init__.py`
- Frontend API: single `frontend/src/lib/api.ts` file with all functions
- No `/reddit` directory in frontend yet

## Goals / Non-Goals

**Goals:**
- Create all 5 Reddit tables in a single Alembic migration
- Follow the exact model patterns from `blog.py` (UUID PKs, `Mapped[]` types, JSONB, `str(uuid4())` defaults, `server_default=text()`)
- Establish CRUD for the two entities needed before discovery/generation: accounts and project configs
- Add nav to the header so Reddit pages are reachable
- Build the account management and project config UI pages

**Non-Goals:**
- No SERP API integration (Slice 14b)
- No comment generation logic (Slice 14c)
- No comment queue UI (Slice 14d)
- No CrowdReply API client (Slice 14e)
- No dashboard stats (Slice 14f)
- No seeded conversations (Slice 14g)
- Posts, comments, and CrowdReply task tables are created in the migration but have no API endpoints yet — they exist only so the migration is complete and future slices don't need schema changes

## Decisions

### 1. Single migration for all 5 tables

**Choice:** One Alembic migration (`0027_create_reddit_tables.py`) creates all 5 tables.

**Rationale:** These tables form a cohesive unit. Creating them individually would generate unnecessary migration files and increase rollback complexity. The blog phase used a single migration for both `blog_campaigns` and `blog_posts` — same pattern here.

**Alternative considered:** Separate migrations per slice (e.g., accounts+configs in 14a, posts in 14b, comments in 14c). Rejected because it fragments the schema and makes rollback harder.

### 2. Separate model files per entity

**Choice:** 5 separate model files (`reddit_account.py`, `reddit_config.py`, `reddit_post.py`, `reddit_comment.py`, `crowdreply_task.py`).

**Rationale:** Each entity has its own enums, fields, and relationships. Blog used a single `blog.py` for 2 models because they're tightly coupled (campaign owns posts). Reddit's 5 entities are more independent — accounts are shared across projects, posts and comments have different lifecycles, CrowdReply tasks are an integration concern.

**Alternative considered:** Single `reddit.py` with all 5 models. Rejected because 400+ lines in one file is harder to navigate and the entities aren't as tightly coupled as blog campaign/post.

### 3. JSONB arrays for niche tags (not join tables)

**Choice:** `niche_tags` stored as `JSONB` arrays on both `reddit_accounts` and `reddit_project_configs`.

**Rationale:** Simple `["skincare", "supplements"]` arrays. Queryable with PostgreSQL `@>` operator (`WHERE niche_tags @> '["skincare"]'::jsonb`). Avoids the complexity of join tables for what are essentially free-form labels. The existing codebase uses JSONB arrays extensively (e.g., `labels` on `crawled_pages`, `search_keywords` on reddit configs).

**Alternative considered:** Normalized `niche_tags` table with `account_niche_tags` and `config_niche_tags` join tables. Rejected — overkill for tagging, adds 3 tables and complex joins for no benefit at this scale.

### 4. Reddit API router with dual prefix strategy

**Choice:** Single `reddit.py` router file with two logical groups:
- Global Reddit routes: `prefix="/reddit"` (accounts, cross-project queue, dashboard, webhooks)
- Per-project Reddit routes: `prefix="/projects"` (config, discovery, posts, comments)

**Implementation:** Two `APIRouter` instances in the same file, both registered in `__init__.py`. This mirrors how `blogs.py` uses `prefix="/projects"` for project-scoped endpoints.

**Rationale:** Keeps all Reddit endpoints in one file for discoverability. The global `/reddit/*` routes are new — no other router uses a non-project prefix, but accounts and the comment queue are inherently cross-project.

**Alternative considered:** Two separate files (`reddit_global.py` and `reddit_project.py`). Rejected — unnecessary file split when the endpoints are closely related and share the same schemas.

### 5. Frontend: Reddit API functions in existing `api.ts`

**Choice:** Add Reddit API functions directly to `frontend/src/lib/api.ts`, following the existing pattern.

**Rationale:** Every other feature's API functions live in this single file. Splitting Reddit into a separate file would be inconsistent. The file is already large but organized by feature sections.

**Alternative considered:** New `frontend/src/lib/api/reddit.ts`. Rejected — would be the only feature with a separate API file, breaking the established pattern.

### 6. Claude Sonnet for all AI operations

**Choice:** Use `claude-sonnet-4-5` (the model already configured in `config.py`) for all Reddit AI operations — intent filtering (14b) and comment generation (14c).

**Rationale:** User preference for quality over cost. The existing `claude_model` setting in config.py already defaults to Sonnet. No Haiku anywhere.

### 7. Header navigation with active states

**Choice:** Add "Projects" and "Reddit" links to the header, with active state based on current pathname.

**Rationale:** Reddit is the first feature that lives outside the project context. The header currently has no nav — the logo implicitly goes to the dashboard. Adding explicit nav links makes the two top-level sections discoverable.

**Implementation:** Use Next.js `usePathname()` hook. "Projects" active on `/` and `/projects/*`. "Reddit" active on `/reddit/*`.

### 8. Reddit layout wrapper

**Choice:** Create `frontend/src/app/reddit/layout.tsx` as a simple pass-through layout (no sidebar, no sub-navigation).

**Rationale:** Reddit pages share the same global layout (Header + max-w-7xl container) as the rest of the app. A dedicated layout allows future additions (e.g., Reddit-specific sub-nav) without modifying individual pages. For now it just renders `{children}`.

## Risks / Trade-offs

**[5 tables in one migration]** If any table definition has an error, the entire migration fails. **Mitigation:** Tables are well-defined in `REDDIT_INTEGRATION_PLAN.md` and follow established patterns. Test with `alembic upgrade head` on dev before staging.

**[No API for posts/comments/tasks yet]** Tables exist but are empty shells until slices 14b-14e. **Mitigation:** This is intentional — schema is stable, APIs are additive. No wasted work.

**[Global `/reddit` prefix is new pattern]** All existing routes are project-scoped. **Mitigation:** Clean separation — global routes for cross-project concerns (accounts, queue), project routes for per-project concerns. FastAPI handles multiple prefixes cleanly.

**[Header nav changes affect all pages]** Adding nav links to the header changes the global layout. **Mitigation:** Minimal change — just adding two links. Active state logic is simple pathname matching.

## Migration Plan

1. Create model files (5 files)
2. Register models in `models/__init__.py`
3. Add `reddit_config` relationship to `Project` model
4. Generate Alembic migration with `alembic revision --autogenerate`
5. Add config vars to `Settings` class
6. Create schemas, API router, register in `__init__.py`
7. Add frontend API functions, hooks, pages
8. Update Header component with nav links
9. Test: `alembic upgrade head`, `pytest`, `npm run build`

**Rollback:** `alembic downgrade -1` drops all 5 tables. Frontend changes are additive and can be reverted with git.

## Open Questions

None — all decisions are resolved for this slice.
