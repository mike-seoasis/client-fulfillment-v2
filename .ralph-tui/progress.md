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
- **API tests**: Use pytest-asyncio with `async_client` fixture from conftest.py. Tests use httpx AsyncClient with ASGI transport. Validation errors return `{"error": ..., "code": ..., "request_id": ...}` format (not `detail`).
- **UI components**: Store in `frontend/src/components/ui/`. Use `forwardRef` for form elements. Export types and components from `index.ts`. Use warm palette classes: `gold-*` for primary, `cream-*` for secondary, `coral-*` for danger, `warm-gray-*` for text.
- **Two-step confirmation pattern**: Use `useState` for confirmation state, `useRef` for timeout cleanup, reset on blur with `onBlur` handler checking `relatedTarget`, and auto-reset with `useEffect` timeout.

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

## 2026-02-03 - S1-009
- Configured Tailwind with warm color palette matching brand guidelines
- Custom colors in `frontend/tailwind.config.ts`:
  - `gold` - Primary colors (amber/gold tones, 50-900 scale)
  - `cream` - Warm light neutrals for backgrounds
  - `coral` - Soft accent colors
  - `warm-gray` - Warm neutral grays for text/borders
- Updated `frontend/src/app/globals.css`:
  - Set `--background` to cream-100 (#FDFBF7)
  - Set `--foreground` to warm-gray-900 (#302D29)
  - Removed dark mode (light mode only per design spec)
- Created test page at `/design-test` to verify palette renders correctly
- Added `borderRadius` customizations for softer, more premium look
- Files changed: `frontend/tailwind.config.ts` (already existed), `frontend/src/app/globals.css`, `frontend/src/app/design-test/page.tsx`
- **Learnings:**
  - Tailwind custom colors use same 50-900 scale as built-in colors for consistency
  - CSS custom properties in globals.css integrate with Tailwind via `var(--name)` syntax in theme config
  - Remove dark mode media query when building light-mode-only interfaces
---

## 2026-02-03 - S1-006
- Created `backend/tests/api/test_projects.py` with comprehensive API tests
- Tests cover all CRUD operations: list, create, get, update, delete
- Test classes: `TestListProjects`, `TestCreateProject`, `TestGetProject`, `TestUpdateProject`, `TestDeleteProject`
- 21 total tests covering:
  - List projects (empty and with data)
  - Create project (valid data, minimal fields, missing name, missing site_url, invalid URL, empty name, whitespace name, custom status, invalid status)
  - Get project (exists, not found)
  - Update project (partial update, update site_url, update status, not found, invalid status, invalid URL)
  - Delete project (exists, not found)
- Fixed `conftest.py` to import models before table creation
- Fixed `projects.py` router to use `max(len(projects), 1)` for limit to satisfy schema constraint
- Files changed: `backend/tests/api/__init__.py`, `backend/tests/api/test_projects.py`, `backend/tests/conftest.py`, `backend/app/api/v1/projects.py`
- **Learnings:**
  - Models MUST be imported in conftest.py before `Base.metadata.create_all()` is called, otherwise SQLite tables won't be created
  - App uses custom error format `{"error": ..., "code": ..., "request_id": ...}` for validation errors, not FastAPI default `detail`
  - `ProjectListResponse` schema requires `limit >= 1`, so router must ensure minimum of 1 even when returning empty list
  - Use `uuid.uuid4()` for generating non-existent IDs in 404 tests
---

## 2026-02-03 - S1-010
- Created base UI components in `frontend/src/components/ui/`:
  - `Button.tsx` - Button with variants (primary, secondary, danger, ghost) and sizes (sm, md, lg)
  - `Input.tsx` - Input with label, error state, and ARIA attributes
  - `Card.tsx` - Card with hover state, onClick support, and keyboard accessibility
  - `EmptyState.tsx` - Empty state component with icon, title, description, and action slots
  - `index.ts` - Barrel export for all components and types
- All components use warm palette colors and forwardRef pattern for form elements
- Files changed: `frontend/src/components/ui/Button.tsx`, `frontend/src/components/ui/Input.tsx`, `frontend/src/components/ui/Card.tsx`, `frontend/src/components/ui/EmptyState.tsx`, `frontend/src/components/ui/index.ts`
- **Learnings:**
  - Use `forwardRef` for Button and Input to allow ref forwarding from form libraries
  - Clickable Cards need `role="button"`, `tabIndex={0}`, and keyboard event handlers for accessibility
  - EmptyState uses ReactNode for icon/action slots to maximize flexibility
  - Barrel exports (`index.ts`) allow clean imports: `import { Button, Card } from '@/components/ui'`
---

## 2026-02-03 - S1-011
- Created Header component at `frontend/src/components/Header.tsx`:
  - Sticky positioning at top with z-50 for proper stacking
  - Warm cream-100 background with cream-300 border
  - Logo placeholder (gold-500 square with "C" initial)
  - "Client Onboarding" title text
  - User dropdown placeholder with avatar and chevron icon
  - Uses warm palette classes consistent with design system
- Updated `frontend/src/app/layout.tsx`:
  - Added Header import and component
  - Set page title/description to "Client Onboarding"
  - Wrapped children in div with min-h-screen and cream-100 background
  - Main content area with max-w-7xl, horizontal padding (px-4/6/8), and py-8 vertical padding
- Files changed: `frontend/src/components/Header.tsx`, `frontend/src/app/layout.tsx`
- **Learnings:**
  - Header components at layout level (not page level) don't need `'use client'` unless they have interactivity, but it's safe to include for future dropdown functionality
  - Sticky headers need z-index (z-50) to stay above scrollable content
  - max-w-7xl with responsive padding (px-4 sm:px-6 lg:px-8) provides consistent container behavior
---

## 2026-02-03 - S1-012
- Created `frontend/src/components/ProjectCard.tsx` for displaying project cards on dashboard
- Card displays: project name (title), site_url, placeholder metrics (0 pages, 0 clusters, 0 pending), relative time for last activity
- Card is clickable and navigates to `/projects/{id}` using Next.js router
- Uses existing Card component from UI library which provides hover effects and keyboard accessibility
- Installed `date-fns` package for `formatDistanceToNow` relative time formatting
- Files changed: `frontend/src/components/ProjectCard.tsx`, `frontend/package.json`
- **Learnings:**
  - `date-fns` `formatDistanceToNow` with `addSuffix: true` gives natural output like "2 days ago"
  - Component-level cards (like ProjectCard) can compose UI primitives (Card) while adding domain-specific layout/content
  - `'use client'` required for components using `useRouter` from next/navigation
---

## 2026-02-03 - S1-013
- Built Dashboard page at `frontend/src/app/page.tsx` replacing Next.js boilerplate
- Dashboard features:
  - Page title "Your Projects" with "+ New Project" button linking to /projects/new
  - Responsive grid of ProjectCard components (1 col mobile, 2 col tablet, 3 col desktop)
  - Loading skeleton with animate-pulse while fetching projects
  - EmptyState with folder icon when no projects exist
  - Error state with coral-themed alert for fetch failures
  - Projects sorted by `updated_at` descending (most recent first)
- Files changed: `frontend/src/app/page.tsx`
- **Learnings:**
  - `'use client'` required for pages using hooks like `useProjects()` from TanStack Query
  - Use `Link` from `next/link` for client-side navigation without full page reload
  - Sort data in component (not API) when display order differs from API response
  - Skeleton loaders should mirror the layout/structure they replace for smooth transition
---

## 2026-02-03 - S1-014
- Created `frontend/src/components/ProjectForm.tsx` with React Hook Form and Zod validation
- Form features:
  - Name field: required, min 1 character with inline validation error
  - Site URL field: required, valid URL format with inline validation error
  - Submit button shows "Saving..." during submission, "Update Project" in edit mode, "Create Project" in create mode
  - Accepts `onSubmit` callback, optional `initialData` for edit mode, and `isSubmitting` for loading state
- Uses existing UI components (Input, Button) from design system
- Installed packages: `react-hook-form`, `@hookform/resolvers`, `zod`
- Files changed: `frontend/src/components/ProjectForm.tsx`, `frontend/package.json`
- **Learnings:**
  - React Hook Form's `register()` returns props compatible with forwardRef Input components
  - `zodResolver` from `@hookform/resolvers/zod` integrates Zod schemas with React Hook Form
  - Export the inferred form data type (`ProjectFormData`) for type-safe callbacks
  - Use `defaultValues` in `useForm` with nullish coalescing (`??`) for proper initial state
---

## 2026-02-03 - S1-015
- Created Create Project page at `frontend/src/app/projects/new/page.tsx`
- Page features:
  - Back link "← Back to Dashboard" at top with arrow icon
  - Page title "Create New Project"
  - Centered card with ProjectForm component
  - Cancel button (ghost variant) returns to dashboard
  - Error message display using coral error styling (matches dashboard pattern)
  - On successful creation, redirects to `/projects/{id}`
- Uses `useCreateProject` mutation hook with `mutateAsync` for promise handling
- Files changed: `frontend/src/app/projects/new/page.tsx`
- **Learnings:**
  - Next.js App Router: pages in `app/route/page.tsx` auto-map to `/route` URLs
  - Use `mutateAsync` instead of `mutate` when you need to await the result and handle success/error in the component
  - For pages without a toast system, inline error messages using the same styling as error states (coral-50 bg, coral-200 border, coral-700 text) maintain consistency
---

## 2026-02-03 - S1-016
- Created Project Detail page at `frontend/src/app/projects/[id]/page.tsx`
- Page features:
  - Back link "← All Projects" returns to dashboard
  - Header with project name and clickable site_url (opens in new tab)
  - "Edit Brand" button (disabled) with tooltip "Coming in Phase 2"
  - Onboarding section with clipboard icon, description, and disabled "Continue" button
  - New Content section with plus icon, description, and disabled "+ New Cluster" button
  - Loading skeleton state while fetching project data
  - 404 state with styled error icon and "Back to Dashboard" button for invalid IDs
- Uses `useProject(id)` hook for data fetching via TanStack Query
- Files changed: `frontend/src/app/projects/[id]/page.tsx`
- **Learnings:**
  - Next.js App Router dynamic routes: `[id]` folder with `page.tsx` maps to `/projects/:id`
  - Use `useParams()` from `next/navigation` to access dynamic route params in client components
  - Disabled buttons accept `disabled` prop - they get opacity and cursor styling automatically
  - CSS-only tooltips: use `group-hover:opacity-100` with `pointer-events-none` to show on parent hover
  - For 404-like states in client components, handle error state from hook rather than calling Next.js `notFound()`
---

## 2026-02-03 - S1-017
- Implemented project deletion with two-step confirmation on Project Detail page
- Created Toast component at `frontend/src/components/ui/Toast.tsx`:
  - Supports `success`, `error`, `info` variants with appropriate styling
  - Auto-dismisses after configurable duration (default 3s)
  - Fixed position bottom-right with fade-out animation
  - Includes close button and appropriate ARIA role
- Updated Project Detail page with delete functionality:
  - Added "Delete Project" button with danger variant next to "Edit Brand"
  - First click changes button text to "Confirm Delete"
  - Second click executes deletion via `useDeleteProject` mutation
  - Confirmation resets after 3 seconds timeout
  - Confirmation resets when button loses focus (clicking elsewhere)
  - Shows "Project deleted" toast on success
  - Redirects to dashboard after short delay
- Files changed: `frontend/src/components/ui/Toast.tsx`, `frontend/src/components/ui/index.ts`, `frontend/src/app/projects/[id]/page.tsx`
- **Learnings:**
  - Two-step confirmation: Use `useState` for confirmation state, `useRef<NodeJS.Timeout>` for timeout cleanup
  - Reset on blur: Check `e.relatedTarget` in `onBlur` handler to avoid resetting if focus stays within button
  - Use `useCallback` for event handlers to maintain stable references
  - For catch blocks where error variable is unused, use `catch { }` without variable (ES2019+)
  - Toast components need `role="alert"` for accessibility and `z-50` for stacking above other content
---

