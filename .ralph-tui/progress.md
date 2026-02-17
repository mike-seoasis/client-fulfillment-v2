# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **SQLAlchemy `metadata` is reserved**: The `metadata` attribute name is reserved by SQLAlchemy's Declarative API. Use a different Python attribute name (e.g., `extra_metadata`) with an explicit column name mapping: `mapped_column("metadata", JSONB, ...)`.
- **Model registration**: New models must be imported in `backend/app/models/__init__.py` and added to `__all__`. Enums should also be exported.
- **UUID PK pattern**: `default=lambda: str(uuid4()), server_default=text("gen_random_uuid()")` — both Python-side and DB-side defaults.
- **DateTime pattern**: `default=lambda: datetime.now(UTC), server_default=text("now()")` for created_at/updated_at. Add `onupdate=lambda: datetime.now(UTC)` for updated_at.
- **JSONB default list**: Use `default=list, server_default=text("'[]'::jsonb")` for JSONB array columns.

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
