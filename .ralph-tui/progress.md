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
- **API routers**: Create routers in `backend/app/api/v1/`. Use `APIRouter(prefix="/resource", tags=["Resource"])`. Register in `__init__.py` with `router.include_router()`, then include v1 router in `main.py`.
- **Frontend providers**: Create providers in `frontend/src/components/providers/`. Use `'use client'` directive. Wrap app in `layout.tsx`. For TanStack Query, use SSR-safe singleton pattern from `frontend/src/lib/query-client.ts`.
- **API client**: Use `apiClient` from `frontend/src/lib/api.ts` for all API calls. Base URL from `NEXT_PUBLIC_API_URL` env var.
- **TanStack Query hooks**: Create hooks in `frontend/src/hooks/`. Use query key factories (`resourceKeys.all`, `resourceKeys.detail(id)`) for cache consistency. For mutations: invalidate list queries, use `setQueryData` for optimistic updates.

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

## 2026-02-03 - S1-005
- Created `backend/app/api/v1/projects.py` with REST endpoints:
  - `GET /api/v1/projects` - returns ProjectListResponse
  - `POST /api/v1/projects` - accepts ProjectCreate, returns ProjectResponse with 201
  - `GET /api/v1/projects/{id}` - returns ProjectResponse or 404
  - `PATCH /api/v1/projects/{id}` - accepts ProjectUpdate, returns ProjectResponse
  - `DELETE /api/v1/projects/{id}` - returns 204 No Content
- Updated `backend/app/api/v1/__init__.py` to include projects router with `/api/v1` prefix
- Updated `backend/app/main.py` to register the v1 router
- Files changed: `backend/app/api/v1/projects.py`, `backend/app/api/v1/__init__.py`, `backend/app/main.py`
- **Learnings:**
  - API routers use `APIRouter(prefix="/projects", tags=["Projects"])` for path prefix and OpenAPI grouping
  - Use `response_model=ProjectResponse` to auto-serialize SQLAlchemy models via `model_validate()`
  - Use `status_code=status.HTTP_201_CREATED` for POST and `status.HTTP_204_NO_CONTENT` for DELETE
  - `get_session` dependency handles commit/rollback automatically, routes just call service methods
  - Router registration: domain routers → v1 __init__.py → main.py `include_router()`
---

## 2026-02-03 - S1-007
- Set up TanStack Query in frontend for data fetching
- Created `frontend/src/lib/query-client.ts` with QueryClient factory functions:
  - `makeQueryClient()` - creates configured QueryClient with sensible defaults
  - `getQueryClient()` - SSR-safe singleton pattern (new client on server, reused on browser)
- Created `frontend/src/components/providers/QueryProvider.tsx` with 'use client' directive
- Updated `frontend/src/app/layout.tsx` to wrap app with QueryProvider
- Files changed: `frontend/src/lib/query-client.ts`, `frontend/src/components/providers/QueryProvider.tsx`, `frontend/src/app/layout.tsx`
- **Learnings:**
  - TanStack Query v5 requires SSR-aware setup for Next.js App Router
  - Use `'use client'` directive for provider components that use React context
  - Server-side rendering needs new QueryClient per request; browser should reuse singleton
  - Default staleTime of 60s and disabling refetchOnWindowFocus improves UX for admin tools
---

## 2026-02-03 - S1-008
- Created API client and project hooks for frontend data fetching
- Created `frontend/src/lib/api.ts` with:
  - `ApiError` class for typed error handling
  - `api<T>()` generic function with JSON handling
  - `apiClient` object with `get`, `post`, `patch`, `delete` convenience methods
  - Base URL configurable via `NEXT_PUBLIC_API_URL` env var
- Created `frontend/src/hooks/use-projects.ts` with:
  - `useProjects()` - fetches project list with query key `['projects']`
  - `useProject(id)` - fetches single project with query key `['projects', id]`
  - `useCreateProject()` - POST mutation, invalidates list on success
  - `useUpdateProject()` - PATCH mutation, invalidates list and updates detail cache
  - `useDeleteProject()` - DELETE mutation with optimistic update and rollback
  - `projectKeys` factory for consistent query key management
- TypeScript types mirror backend Pydantic schemas
- Files changed: `frontend/src/lib/api.ts`, `frontend/src/hooks/use-projects.ts`
- **Learnings:**
  - Use query key factories (`projectKeys.all`, `projectKeys.detail(id)`) for consistency
  - Optimistic updates: cancel queries, snapshot, update cache, return context for rollback
  - Use `enabled: !!id` to prevent queries with undefined/empty IDs
  - `setQueryData` for immediate cache updates; `invalidateQueries` for background refetch
---

