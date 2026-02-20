## Context

The app has no authentication. Anyone with the URL can access all data and trigger operations (content generation, Reddit posting, etc.). The team is 1-5 internal users who all use Google Workspace.

Neon Auth was chosen in Phase 10 when we migrated the database to Neon. Auth data lives in the same Postgres instance in the `neon_auth` schema, managed automatically by Neon. Sessions are stored in the DB, making backend validation a simple SQL query.

The frontend (Next.js 14 / React 18) talks to a separate FastAPI backend via REST API. They run on different Railway services with different domains.

## Goals / Non-Goals

**Goals:**
- Gate the entire app behind Google OAuth sign-in
- Validate all backend API requests against session tokens
- Show authenticated user info in the Header with sign-out
- Future-proof: user IDs available in DB for per-user data isolation later

**Non-Goals:**
- Per-user data siloing (all users see all projects for now)
- `created_by` column on projects table
- Row Level Security policies
- Email/password or other OAuth providers
- User management UI or role-based access control
- Sign-up flow (Google account creation is automatic on first sign-in)

## Decisions

### 1. Neon Auth SDK (`@neondatabase/auth`) over raw Better Auth
**Choice:** Use the managed Neon Auth SDK.
**Rationale:** Auth tables are auto-managed in `neon_auth` schema. No Alembic migrations needed. Sessions already in our DB. Branches with database for testing.
**Alternative considered:** Self-hosted Better Auth — more control but requires managing auth tables ourselves.

### 2. Google OAuth only (no email/password)
**Choice:** Single provider — Google.
**Rationale:** The internal team uses Google Workspace. One button, no forms, no password management. Simpler implementation.
**Alternative considered:** Email/password + Google — adds complexity (forms, validation, password reset) for no benefit with an all-Google team.

### 3. Session token forwarding via Authorization header
**Choice:** Frontend extracts session token from `authClient.useSession()` and sends it as `Authorization: Bearer <token>` on all API calls.
**Rationale:** Frontend and backend are on different domains (different Railway services), so cookies aren't shared. The session token is available client-side via the auth hooks. The backend validates against `neon_auth.session` table in the same DB.
**Alternative considered:**
- Cookie forwarding — doesn't work cross-domain without same-site setup.
- Next.js API proxy — adds latency and complexity routing all calls through Next.js.
- Shared API key — doesn't identify users, can't future-proof for per-user data.

### 4. Backend validates against DB directly (no JWT verification)
**Choice:** FastAPI reads the Bearer token, queries `neon_auth.session` WHERE token matches and not expired.
**Rationale:** The session table is in the same database. One SQL query per request is cheap and always consistent. No JWT secret management or token format coupling.
**Alternative considered:** JWT verification — faster (no DB query) but requires sharing signing secrets between Neon Auth and FastAPI.

### 5. Auth applied at router level, not per-endpoint
**Choice:** Add `get_current_user` as a dependency on the top-level API router so all endpoints are protected by default.
**Rationale:** Simpler and safer — no risk of forgetting auth on a new endpoint. Health check endpoint is the only exception (mounted before the auth router).

### 6. React 18 compatibility approach
**Choice:** Use client-side `authClient.signIn.social()` for Google sign-in instead of React 19 server actions.
**Rationale:** Project is on React 18 / Next.js 14. `useActionState` (used in Neon Auth docs) is React 19 only. Client-side auth hooks work fine on React 18.

## Risks / Trade-offs

- **[Neon Auth is beta]** → Acceptable for internal tool with 1-5 users. Neon is our DB provider anyway. If it breaks, we can fall back to raw Better Auth with the same DB tables.
- **[Next.js 14 compatibility]** → The `@neondatabase/auth` SDK may target Next.js 15. If middleware or hooks don't work, fall back to Better Auth SDK directly with manual cookie handling.
- **[Session token in client memory]** → Token is exposed to client JavaScript. Acceptable for internal tool. The token is tied to a server-side session with expiry, not a long-lived secret.
- **[DB query per API request]** → One SELECT per request to validate session. With Neon connection pooling and a simple indexed lookup, this adds <5ms latency. Acceptable for an internal tool.
- **[Breaking change for API]** → All endpoints return 401 without auth. No gradual rollout — deploy frontend and backend together.

## Migration Plan

1. Enable Neon Auth in console (creates `neon_auth` schema)
2. Deploy backend with auth dependency (but `AUTH_REQUIRED=false` env var initially)
3. Deploy frontend with auth UI and token forwarding
4. Set `AUTH_REQUIRED=true` on backend
5. Verify end-to-end: sign in → use app → sign out → blocked

**Rollback:** Set `AUTH_REQUIRED=false` on backend to bypass auth. Frontend auth pages still work but aren't enforced.

## Open Questions

- None — all decisions made during planning conversation with user.
