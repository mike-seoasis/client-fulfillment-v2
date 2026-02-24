# Phase 12: Authentication (Neon Auth)

## Context

All 11 core phases are complete. The app has no auth — every user sees every project. Phase 12 adds authentication using Neon Auth (built on Better Auth) so we can protect routes, display the logged-in user, and isolate projects per user. This is an internal tool with 1-5 users.

**Key decisions:**
- Single package: `@neondatabase/auth` (NOT the old `better-auth` + `@better-auth/nextjs` from the spec)
- Backend validates JWTs via JWKS (NOT direct DB session reads — the session cookie is opaque/same-origin only)
- Application-level project filtering (NOT Postgres RLS)
- Email/password + Google OAuth
- No account management pages — just sign in, sign out, route protection, user in header

---

## Step 1: Neon Dashboard Setup (Manual — You Do This)

1. Go to https://console.neon.tech, open project `spring-fog-49733273`
2. Navigate to **Auth** tab, click **Enable Neon Auth**
3. Copy the **Auth URL** (format: `https://ep-xxx.neonauth.us-east-1.aws.neon.tech/neondb/auth`)
4. Enable **Email/Password** and **Google** OAuth providers
5. Generate a cookie secret: `openssl rand -base64 32`
6. Share the Auth URL and cookie secret with me

---

## Step 2: Backend — Auth Module + Migration

### 2a: Add `neon_auth_url` to config
**Modify:** `backend/app/core/config.py`
- Add `neon_auth_url: str | None = Field(default=None)` to Settings
- When `None`, auth is disabled (opt-in for dev)

### 2b: Create JWT validation dependency
**Create:** `backend/app/core/auth.py`
- `get_current_user(request) -> AuthenticatedUser | None` — extracts Bearer token, validates JWT against `{NEON_AUTH_URL}/.well-known/jwks.json`
- Returns `None` when `NEON_AUTH_URL` not set (dev mode — no auth)
- Raises 401 when auth is enabled but token missing/invalid
- JWKS cached for 5 minutes
- Uses `python-jose[cryptography]` for RS256 validation

### 2c: Database migration for `created_by`
**Create:** `backend/alembic/versions/0027_add_created_by_to_projects.py`
- Add `created_by` (String(255), nullable, indexed) to `projects` table
- Nullable so existing projects keep working (NULL = legacy/pre-auth)

**Modify:** `backend/app/models/project.py`
- Add `created_by: Mapped[str | None]` column

### 2d: Wire auth into service + endpoints
**Modify:** `backend/app/services/project.py`
- `list_projects(db, user_id=None)` — when user_id provided, filter `WHERE created_by = user_id OR created_by IS NULL`
- `create_project(db, data, user_id=None)` — stamp `created_by = user_id`
- `get_project(db, project_id, user_id=None)` — ownership check (returns 404, not 403)

**Modify:** `backend/app/api/v1/projects.py`
- Import and inject `get_current_user` dependency into list, create, get, update, delete endpoints
- Pass `user.id if user else None` to service methods

**NOT modified (this phase):** Other routers (`blogs.py`, `clusters.py`, etc.) — they all go through `ProjectService.get_project()` which will enforce ownership once wired. Full coverage comes from the ownership check in `get_project`.

**Health endpoints** (`/health/*`) remain public — they're on `app` directly, not behind any auth dependency.

### 2e: Install backend dependency
- Add `python-jose[cryptography]>=3.3.0` to `pyproject.toml`

---

## Step 3: Frontend — Auth SDK Setup

### 3a: Install package
```
cd frontend && npm install @neondatabase/auth@latest
```

### 3b: Create auth config files
**Create:** `frontend/src/lib/auth/server.ts`
- `createNeonAuth()` with `NEON_AUTH_BASE_URL` and `NEON_AUTH_COOKIE_SECRET`

**Create:** `frontend/src/lib/auth/client.ts`
- `createAuthClient()` for client components

### 3c: Create auth API route
**Create:** `frontend/src/app/api/auth/[...path]/route.ts`
- Export `{ GET, POST }` from `auth.handler()`

### 3d: Create sign-in page
**Create:** `frontend/src/app/auth/[path]/page.tsx`
- Uses `<AuthView path={path} />` from Neon Auth
- Wrapped in tropical oasis styled container (cream bg, palm green logo, centered card)

### 3e: Create middleware
**Create:** `frontend/src/middleware.ts`
- `auth.middleware({ loginUrl: '/auth/sign-in' })`
- Matcher excludes: `/auth/*`, `/api/auth/*`, `/_next/*`, static files

---

## Step 4: Frontend — Layout, Header, API Client

### 4a: Wrap layout with auth provider
**Modify:** `frontend/src/app/layout.tsx`
- Add `<NeonAuthUIProvider authClient={authClient}>` wrapping the existing tree
- Add `suppressHydrationWarning` to `<html>` tag

### 4b: Update header with real user
**Modify:** `frontend/src/components/Header.tsx`
- Replace hardcoded "U" avatar with `<UserButton />` from Neon Auth

### 4c: Inject JWT into API client
**Modify:** `frontend/src/lib/api.ts`
- Add `getAuthHeaders()` helper that gets JWT from `authClient.getSession()`
- Inject `Authorization: Bearer <token>` into all `api()` calls
- Also update `exportProject()` and `downloadBlogPostHtml()` direct fetch calls

### 4d: Import Neon Auth styles
**Modify:** `frontend/src/app/globals.css`
- Add `@import "@neondatabase/auth/ui/tailwind"` (or add to tailwind config content paths if CSS import causes issues with v3)

---

## Step 5: Environment Variables + Deploy

### Local dev (.env files)
```
# frontend/.env.local
NEON_AUTH_BASE_URL=https://ep-xxx.neonauth...
NEON_AUTH_COOKIE_SECRET=<secret>

# backend/.env
NEON_AUTH_URL=https://ep-xxx.neonauth...
```

### Railway (staging)
- Add `NEON_AUTH_URL` to backend service
- Add `NEON_AUTH_BASE_URL` and `NEON_AUTH_COOKIE_SECRET` to frontend service

---

## Step 6: Verification

1. **Backend without auth**: No `NEON_AUTH_URL` set — all endpoints work exactly as before
2. **Frontend without auth**: No `NEON_AUTH_BASE_URL` set — app works (may need graceful fallback)
3. **Full auth flow**: Sign in with email/password -> header shows UserButton -> create project -> `created_by` populated in DB -> list shows only user's projects + legacy projects -> sign out -> redirect to sign-in
4. **Health endpoints**: `/health`, `/health/db` still accessible without auth
5. **Google OAuth**: Sign in with Google account works
6. **Existing data**: Legacy projects (created_by=NULL) still visible to all users

---

## Files Summary

### New Files (8)
| File | Purpose |
|------|---------|
| `frontend/src/lib/auth/server.ts` | Server-side auth config |
| `frontend/src/lib/auth/client.ts` | Client-side auth instance |
| `frontend/src/app/api/auth/[...path]/route.ts` | Auth API catch-all route |
| `frontend/src/app/auth/[path]/page.tsx` | Sign-in/sign-up page |
| `frontend/src/middleware.ts` | Route protection |
| `backend/app/core/auth.py` | JWT validation dependency |
| `backend/alembic/versions/0027_*.py` | Migration: `created_by` column |
| `backend/tests/test_auth.py` | Auth unit tests |

### Modified Files (9)
| File | Change |
|------|--------|
| `frontend/package.json` | Add `@neondatabase/auth` |
| `frontend/src/app/layout.tsx` | Wrap with `NeonAuthUIProvider` |
| `frontend/src/components/Header.tsx` | `UserButton` replaces placeholder |
| `frontend/src/lib/api.ts` | JWT in all API requests |
| `frontend/src/app/globals.css` | Neon Auth UI styles |
| `backend/pyproject.toml` | Add `python-jose[cryptography]` |
| `backend/app/core/config.py` | Add `neon_auth_url` setting |
| `backend/app/models/project.py` | Add `created_by` column |
| `backend/app/services/project.py` | User filtering in list/create/get |
| `backend/app/api/v1/projects.py` | Inject auth dependency |

---

## Implementation Order

```
Step 1: Neon Dashboard (you, manual)
Step 2: Backend auth module + migration (independent of frontend)
Step 3: Frontend auth SDK setup (independent of backend)
Step 4: Frontend layout/header/API client changes
Step 5: Environment variables + deploy
Step 6: End-to-end verification
```

Steps 2 and 3 can be done in parallel. Step 4 depends on Step 3. Step 5 depends on Steps 1-4.

---

## Technical Notes

### JWT Flow
```
Browser → Neon Auth SDK (cookie) → Neon Auth API (managed)
                                        ↓
                                  neon_auth schema (in Neon DB)
Browser → Authorization: Bearer <JWT> → FastAPI backend
                                        ↓ validates via JWKS
                                  extract user_id from "sub" claim
```

### Why Not RLS
For 1-5 internal users, application-level filtering (`WHERE created_by = user_id`) is simpler than Row Level Security. RLS requires setting `app.current_user_id` on every DB connection, which adds middleware complexity. We can always add RLS later if the app goes multi-tenant.

### Why JWT (Not Direct DB Session Reads)
The Neon Auth session cookie (`__Secure-neonauth.session_token`) is opaque and HttpOnly — it's only sent to the Neon Auth API, not to our FastAPI backend on a different origin. The JWT (`session.access_token`) is explicitly designed to be passed to separate backend services via `Authorization: Bearer` header.

### Graceful Degradation
When `NEON_AUTH_URL` (backend) or `NEON_AUTH_BASE_URL` (frontend) are not set, auth is completely disabled. All existing functionality works unchanged. This allows development without auth configured.

### Legacy Project Handling
The `created_by` column is nullable. Existing projects (created_by=NULL) remain visible to all authenticated users via the filter: `WHERE created_by = user_id OR created_by IS NULL`. New projects are stamped with the authenticated user's ID.
