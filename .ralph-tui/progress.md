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
