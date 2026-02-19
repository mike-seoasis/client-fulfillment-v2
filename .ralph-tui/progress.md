# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Neon Auth server singleton**: `import { auth } from '@/lib/auth/server'` — provides `.handler()`, `.middleware()`, `.getSession()`, and all Better Auth server methods (signIn, signUp, etc.).

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

