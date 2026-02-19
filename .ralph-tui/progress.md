# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Neon Auth server singleton**: `import { auth } from '@/lib/auth/server'` — provides `.handler()`, `.middleware()`, `.getSession()`, and all Better Auth server methods (signIn, signUp, etc.).
- **Neon Auth client singleton**: `import { authClient } from '@/lib/auth/client'` — provides `signIn.social()`, `signOut()`, `useSession()`, and org management hooks for React components.
- **Neon Auth middleware**: `auth.middleware({ loginUrl: '/auth/sign-in' })` returns an `async (request: NextRequest) => NextResponse` function. SDK auto-skips `/api/auth`, `/auth/sign-in`, `/auth/sign-up`, `/auth/callback`, `/auth/magic-link`, `/auth/email-otp`, `/auth/forgot-password`. Session cookie name: `__Secure-neon-auth.session_token`.

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
