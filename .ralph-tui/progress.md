# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Neon Auth server singleton**: `import { auth } from '@/lib/auth/server'` — provides `.handler()`, `.middleware()`, `.getSession()`, and all Better Auth server methods (signIn, signUp, etc.).
- **Neon Auth client singleton**: `import { authClient } from '@/lib/auth/client'` — provides `signIn.social()`, `signOut()`, `useSession()`, and org management hooks for React components.
- **Neon Auth middleware**: `auth.middleware({ loginUrl: '/auth/sign-in' })` returns an `async (request: NextRequest) => NextResponse` function. SDK auto-skips `/api/auth`, `/auth/sign-in`, `/auth/sign-up`, `/auth/callback`, `/auth/magic-link`, `/auth/email-otp`, `/auth/forgot-password`. Session cookie name: `__Secure-neon-auth.session_token`.
- **Route group layout pattern**: Root layout (`app/layout.tsx`) has html/body/fonts/providers/bg only — NO Header. Authenticated routes live in `app/(authenticated)/layout.tsx` which adds `<Header />` + `<main>` wrapper. Auth pages live in `app/auth/layout.tsx` with no Header. Route groups don't affect URLs.
- **Backend auth dependency**: `from app.core.auth import get_current_user, UserInfo` — FastAPI dependency that validates Bearer tokens against `neon_auth.session`/`neon_auth."user"`. Returns `UserInfo(id, email, name)`. When `AUTH_REQUIRED=false`, returns dev user. Self-contained: `db` param has `Depends(get_session)` default so it works both as route-level `user: UserInfo = Depends(get_current_user)` and as router-level `dependencies=[Depends(get_current_user)]`.
- **Router-level auth**: `api_v1_router` in `backend/app/api/v1/__init__.py` has `dependencies=[Depends(get_current_user)]` — all `/api/v1/*` endpoints require auth by default. Health checks at `/health` are on `app` directly, unaffected.

---

## 2026-02-19 - S12-001
- Installed `@neondatabase/auth@^0.2.0-beta.1` in frontend/
- Files changed: `frontend/package.json`, `frontend/package-lock.json`
- **Learnings:**
  - All versions of `@neondatabase/auth` require Next.js 16+ as a peerOptional dependency. Project is on Next 14.2.35. Required `--legacy-peer-deps` flag to install. The peer dep is optional so this should work fine at runtime.
  - The SDK bundles `better-auth@1.4.6`, `@neondatabase/auth-ui`, `@supabase/auth-js`, `jose`, and `zod` internally.
  - Pre-existing typecheck errors exist in the codebase (unrelated to this change).
---

## 2026-02-19 - S12-002
- Created server-side auth instance at `frontend/src/lib/auth/server.ts`
- Exports `auth` singleton via `createNeonAuth` from `@neondatabase/auth/next/server`
- Configured with `process.env.NEON_AUTH_BASE_URL` and `process.env.NEON_AUTH_COOKIE_SECRET`
- Env vars already existed in `frontend/.env.local` with real values (not placeholders)
- Files changed: `frontend/src/lib/auth/server.ts` (new)
- **Learnings:**
  - The SDK's `next/server` export path is `@neondatabase/auth/next/server` (not `@neondatabase/auth/next`). The `@neondatabase/auth/next` path is the client-side Next.js export.
  - `createNeonAuth()` returns a unified object with: all Better Auth server methods + `.handler()` (for API route) + `.middleware()` (for route protection).
  - Config takes `{ baseUrl, cookies: { secret, sessionDataTtl?, domain? } }`. Cookie secret must be >= 32 chars.
  - No new typecheck errors introduced. Pre-existing test file errors remain.
---

## 2026-02-19 - S12-004
- Created catch-all auth API route at `frontend/src/app/api/auth/[...path]/route.ts`
- Imports `auth` from `@/lib/auth/server` and destructures `GET` and `POST` from `auth.handler()`
- Handles all Better Auth endpoints: `/api/auth/sign-in/social`, `/api/auth/get-session`, `/api/auth/callback/google`, etc.
- Files changed: `frontend/src/app/api/auth/[...path]/route.ts` (new)
- **Learnings:**
  - `auth.handler()` returns an object with `GET` and `POST` properties that can be directly destructured as Next.js route handler exports — very clean pattern.
  - The `[...path]` catch-all segment is required so Better Auth can handle its own sub-routing for all auth endpoints.
  - No new typecheck errors introduced. Pre-existing test file errors remain.
---

## 2026-02-19 - S12-003
- Created client-side auth instance at `frontend/src/lib/auth/client.ts`
- Exports `authClient` singleton via `createAuthClient` from `@neondatabase/auth/next`
- `createAuthClient()` takes no arguments — config is inferred from the server-side setup
- Exposes `signIn.social()`, `signOut()`, `useSession()`, plus org management hooks
- Files changed: `frontend/src/lib/auth/client.ts` (new)
- **Learnings:**
  - Client import path is `@neondatabase/auth/next` (not `/next/client` — the `/next` path IS the client export, while `/next/server` is the server export)
  - `createAuthClient()` takes zero arguments — no baseUrl or cookie config needed on the client side
  - The client instance also exposes `useActiveOrganization()`, `useListOrganizations()`, and other org-related hooks beyond the core auth methods
  - No new typecheck errors introduced. Pre-existing test file errors remain.
---

## 2026-02-19 - S12-005
- Created Next.js route protection middleware at `frontend/src/middleware.ts`
- Uses `auth.middleware()` from Neon Auth SDK for core route protection (unauthenticated → /auth/sign-in redirect, OAuth callback handling, session refresh)
- Added custom logic: authenticated users on `/auth/sign-in` are redirected to `/` by checking for session cookie (`__Secure-neon-auth.session_token`)
- Matcher regex excludes: `_next/static`, `_next/image`, `fonts`, `favicon.ico`, `api/auth`
- Files changed: `frontend/src/middleware.ts` (new)
- **Learnings:**
  - `auth.middleware({ loginUrl })` returns `async (request: NextRequest) => NextResponse` — can be called directly as a sub-middleware
  - The SDK middleware auto-skips these routes internally: `/api/auth`, `/auth/callback`, `/auth/sign-in`, `/auth/sign-up`, `/auth/magic-link`, `/auth/email-otp`, `/auth/forgot-password`
  - SDK middleware does NOT redirect authenticated users away from login pages — that must be handled manually
  - Session cookie name is `__Secure-neon-auth.session_token` (prefix `__Secure-neon-auth` + `.session_token`). Checking cookie presence is sufficient for the redirect-from-login case (no need for full session validation there)
  - No new typecheck errors introduced. Pre-existing test file errors remain.
---

## 2026-02-19 - S12-012
- Added `auth_required: bool = Field(default=True)` to Settings class in `backend/app/core/config.py`
- Placed in the `# Application` section alongside `app_name`, `debug`, `environment`
- Description: "Require authentication for API requests (disable for local development)"
- Defaults to `True` (production-safe); set `AUTH_REQUIRED=false` env var to bypass auth in local dev
- Files changed: `backend/app/core/config.py`
- **Learnings:**
  - Settings class uses `case_sensitive=False` so env var `AUTH_REQUIRED` maps to `auth_required` field automatically
  - `_env_file=None` can be passed to Settings constructor in tests to avoid loading `.env`
---

## 2026-02-19 - S12-006
- Created auth layout at `frontend/src/app/auth/layout.tsx` — renders children without Header, centered on screen
- Restructured app to use route groups: moved Header/main from root layout to `(authenticated)/layout.tsx`
- Root layout now only has html/body/fonts/QueryProvider/bg-cream-100 (shared by all routes)
- Moved all existing pages (`page.tsx`, `projects/`, `reddit/`, `tools/`, `design-test/`) into `(authenticated)/` route group
- Files changed:
  - `frontend/src/app/layout.tsx` (modified — removed Header import and rendering)
  - `frontend/src/app/(authenticated)/layout.tsx` (new — Header + main wrapper)
  - `frontend/src/app/auth/layout.tsx` (new — centered children, no Header)
  - Moved 5 items into `(authenticated)/`: `page.tsx`, `projects/`, `reddit/`, `tools/`, `design-test/`
- **Learnings:**
  - Next.js route groups `(name)` don't affect URL paths — `(authenticated)/projects/[id]` still serves `/projects/[id]`
  - After moving files, `.next/types/` cache has stale references — delete it to get clean typecheck results
  - Layouts in Next.js nest, they don't replace — the only way to avoid a parent layout's component is to use route groups so different children get different intermediate layouts
---

## 2026-02-19 - S12-008
- Verified all layout restructuring is already complete (done as part of S12-006)
- Root layout: html/body/fonts/QueryProvider only — NO Header ✅
- `(authenticated)/layout.tsx`: Header + main wrapper for all app routes ✅
- `auth/layout.tsx`: centered children, no Header ✅
- All pages (/, /projects/*, /reddit/*, /tools/*, /design-test/*) inside `(authenticated)/` ✅
- AuthTokenSync: component does not exist yet (created in S12-009), root layout is ready for it
- Files changed: none (already implemented)
- **Learnings:**
  - S12-006 already handled the full layout restructuring including route groups
  - AuthTokenSync mounting depends on S12-009 which creates the component
---

## 2026-02-19 - S12-007
- Created Google OAuth sign-in page at `frontend/src/app/auth/sign-in/page.tsx`
- 'use client' component with loading state management via useState
- Centered card with 'C' logo (matching Header), "Client Onboarding" title, "Sign in to continue" subtitle
- "Sign in with Google" button calls `authClient.signIn.social({ provider: 'google', callbackURL: window.location.origin })`
- Loading state: button disabled, spinner replaces Google icon, text changes to "Redirecting…"
- Styled with tropical oasis design: bg-white card, border-sand-500, palm-500 button, warm-gray text, rounded-sm
- Uses auth layout (no Header) — centered via parent `auth/layout.tsx`
- Files changed: `frontend/src/app/auth/sign-in/page.tsx` (new)
- **Learnings:**
  - `authClient.signIn.social()` is async but triggers a redirect — the loading state is mainly to give visual feedback during the brief window before the browser navigates away
  - Auth layout already handles centering (`flex min-h-screen items-center justify-center`), so the sign-in page just needs to constrain its width
  - No new typecheck or lint errors introduced. Pre-existing test file errors remain.
---

## 2026-02-19 - S12-009
- Updated Header component to use real auth session data instead of hardcoded placeholder
- `authClient.useSession()` provides `{ data: { user: { name, email } }, isPending }` for display
- User avatar shows first letter of name (or email as fallback) instead of hardcoded 'U'
- User name displayed next to avatar (hidden on small screens via `hidden sm:inline`)
- Dropdown menu with user name/email and "Sign out" button
- Sign out calls `authClient.signOut()` with `onSuccess` callback to redirect to `/auth/sign-in`
- Loading state: skeleton pulse animation on avatar and name while session loads
- Dropdown uses invisible backdrop overlay to close on outside click
- Files changed: `frontend/src/components/Header.tsx` (modified)
- **Learnings:**
  - `authClient.useSession()` returns `{ data, isPending }` — `data` is the session object with `user` and `session` properties, or `null` if not authenticated
  - `authClient.signOut()` accepts `{ fetchOptions: { onSuccess } }` for post-signout redirect — cleaner than chaining `.then()` since the SDK handles cookie cleanup internally
  - Dropdown pattern: invisible fixed backdrop `div` + `z-index` layering is a clean way to handle click-outside-to-close without `useRef`/`useEffect` event listeners
  - No new typecheck or lint errors introduced. Pre-existing test file errors remain.
---

## 2026-02-19 - S12-010
- Created auth token store at `frontend/src/lib/auth-token.ts` with `setSessionToken()` and `getSessionToken()` using a module-level variable
- Created `frontend/src/components/AuthTokenSync.tsx` ('use client') that syncs `authClient.useSession()` data into the token store via `useEffect`
- AuthTokenSync renders `null` (invisible component)
- Mounted AuthTokenSync in root layout (`frontend/src/app/layout.tsx`) inside QueryProvider
- Files changed:
  - `frontend/src/lib/auth-token.ts` (new)
  - `frontend/src/components/AuthTokenSync.tsx` (new)
  - `frontend/src/app/layout.tsx` (modified — added AuthTokenSync import and rendering)
- **Learnings:**
  - `authClient.useSession()` returns `{ data }` where `data?.session?.token` is the bearer token string needed for backend API calls
  - Module-level variable pattern works well for decoupling auth state from React context — any module can import `getSessionToken()` without needing hooks or providers
  - No new typecheck or lint errors introduced. Pre-existing test file errors remain.
---

## 2026-02-19 - S12-011
- Updated `api()` function to read token via `getSessionToken()` and add `Authorization: Bearer ${token}` header when token is available
- When token is null, Authorization header is omitted entirely (no empty Bearer)
- All `apiClient` methods (get, post, patch, put, delete) automatically inherit the header via `api()`
- Updated `exportProject()` raw `fetch()` call to include Authorization header
- Updated `downloadBlogPostHtml()` raw `fetch()` call to include Authorization header
- Files changed: `frontend/src/lib/api.ts` (modified — added import + 3 token injection points)
- **Learnings:**
  - The `api()` function is the single choke point for all `apiClient.*` methods, so adding the header there covers all JSON API calls automatically
  - The two raw `fetch()` calls (`exportProject`, `downloadBlogPostHtml`) are separate because they handle blob responses — these need individual token injection
  - Conditional spread `...(token ? { Authorization: \`Bearer ${token}\` } : {})` is a clean pattern for optional headers without sending empty values
  - No new typecheck or lint errors introduced. Pre-existing test file errors remain.
---

## 2026-02-19 - S12-013
- Created `backend/app/core/auth.py` with `get_current_user` FastAPI dependency and `UserInfo` dataclass
- `UserInfo` dataclass: `id` (str), `email` (str), `name` (str)
- When `AUTH_REQUIRED=false`: returns `UserInfo(id='dev-user', email='dev@localhost', name='Dev User')` without checking headers
- When `AUTH_REQUIRED=true`: extracts Bearer token from Authorization header, queries `neon_auth.session` joined with `neon_auth."user"` where token matches and `expiresAt > now()`
- Returns 401 `{'detail': 'Not authenticated'}` if no Authorization header or not Bearer format
- Returns 401 `{'detail': 'Invalid or expired session'}` if token not found or expired
- Uses `text()` for raw SQL since neon_auth tables are not in our SQLAlchemy models
- Files changed: `backend/app/core/auth.py` (new)
- **Learnings:**
  - Neon Auth uses camelCase column names (`userId`, `expiresAt`, `createdAt`, `updatedAt`) — must quote them in SQL
  - `"user"` is a reserved word in Postgres — must be double-quoted in SQL (`neon_auth."user"`)
  - Module-level `_DEV_USER` constant avoids creating a new object per request in dev mode
  - The dependency signature `(request: Request, db: AsyncSession = Depends(get_session))` lets FastAPI resolve the full dependency chain automatically — both at route-level and router-level usage
---

## 2026-02-19 - S12-014
- Applied `get_current_user` as a router-level dependency on `api_v1_router` using `dependencies=[Depends(get_current_user)]`
- All `/api/v1/*` endpoints now require a valid Bearer token (or bypass when `AUTH_REQUIRED=false`)
- Health check at `/health` is unaffected (mounted directly on `app` in `main.py`, not on the v1 router)
- Also updated `get_current_user` signature to declare `db: AsyncSession = Depends(get_session)` so FastAPI can resolve the dependency chain when used as a router-level dependency (previously had no default, relying on route-level `Depends(get_session)`)
- Files changed:
  - `backend/app/api/v1/__init__.py` (modified — added Depends import, get_current_user import, router-level dependency)
  - `backend/app/core/auth.py` (modified — added Depends/get_session imports, added `Depends(get_session)` default to db param)
- **Learnings:**
  - Router-level dependencies via `APIRouter(dependencies=[...])` apply to ALL routes on that router and all included sub-routers — clean way to enforce auth globally
  - When a dependency function is used as a router-level dependency, all its parameters must be self-resolving (either special types like `Request` or have `Depends(...)` defaults). A bare `db: AsyncSession` without `Depends(get_session)` works when the route also declares `db`, but fails as a router-level dependency since FastAPI can't resolve it
  - isort (via ruff) groups `app.api.*` and `app.core.*` together alphabetically — `app.api` imports must come before `app.core` imports
---

## 2026-02-19 - S12-015
- Moved CrowdReply webhook endpoint outside the authenticated `/api/v1` router
- Created `webhook_router` (APIRouter with `prefix="/webhooks"`) in `backend/app/api/v1/reddit.py`
- Moved `POST /webhooks/crowdreply` handler from `reddit_router` to `webhook_router`
- Mounted `webhook_router` directly on the app in `main.py` (no auth dependency)
- Webhook simulator endpoint (`POST /api/v1/reddit/webhooks/crowdreply/simulate`) stays inside authenticated router
- Old URL: `POST /api/v1/reddit/webhooks/crowdreply` → New URL: `POST /webhooks/crowdreply`
- Files changed:
  - `backend/app/api/v1/reddit.py` (modified — added `webhook_router`, moved webhook handler to it)
  - `backend/app/api/v1/__init__.py` (modified — re-export `webhook_router`)
  - `backend/app/main.py` (modified — import and mount `webhook_router` on app directly)
- **Learnings:**
  - When re-exporting a symbol from `__init__.py` that isn't used locally, ruff F401 requires explicit re-export syntax: `from module import thing as thing` (redundant alias signals intentional re-export)
  - Mounting a router directly on `app` via `app.include_router()` bypasses any router-level dependencies on `api_v1_router` — clean way to exempt specific routes from auth
---
