## 1. Frontend Auth Setup

- [ ] 1.1 Install `@neondatabase/auth@latest` in frontend
- [ ] 1.2 Add `NEON_AUTH_BASE_URL` and `NEON_AUTH_COOKIE_SECRET` to `.env.local`
- [ ] 1.3 Create `src/lib/auth/server.ts` — Neon Auth server instance with `createNeonAuth()`
- [ ] 1.4 Create `src/lib/auth/client.ts` — Neon Auth client instance with `createAuthClient()`
- [ ] 1.5 Create `src/app/api/auth/[...path]/route.ts` — Auth API route handler (GET + POST)

## 2. Route Protection

- [ ] 2.1 Create `src/middleware.ts` — Protect all routes, redirect unauthenticated to `/auth/sign-in`, allow `/auth/*`, `/api/auth/*`, static assets
- [ ] 2.2 Verify middleware redirects unauthenticated users
- [ ] 2.3 Verify authenticated users are redirected away from `/auth/sign-in` to `/`

## 3. Sign-In UI

- [ ] 3.1 Create `src/app/auth/layout.tsx` — Clean layout without Header for auth pages
- [ ] 3.2 Create `src/app/auth/sign-in/page.tsx` — "Sign in with Google" button, tropical oasis styled, calls `authClient.signIn.social({ provider: "google" })`

## 4. Header Auth Integration

- [ ] 4.1 Update `src/components/Header.tsx` — Display user name/email from session, add sign-out button using `authClient.signOut()`
- [ ] 4.2 Move Header rendering into a layout that only renders for authenticated routes (not auth pages)

## 5. API Client Token Forwarding

- [ ] 5.1 Create `src/lib/auth-token.ts` — Module-level token store with `setSessionToken()` / `getSessionToken()`
- [ ] 5.2 Create `src/components/AuthTokenSync.tsx` — Component that syncs `authClient.useSession()` token into the token store
- [ ] 5.3 Add `AuthTokenSync` to the root layout (inside QueryProvider)
- [ ] 5.4 Update `src/lib/api.ts` — Add `Authorization: Bearer <token>` header to all requests when token is available

## 6. Backend Auth

- [ ] 6.1 Add `AUTH_REQUIRED` setting to `backend/app/core/config.py` (default `true`)
- [ ] 6.2 Create `backend/app/core/auth.py` — `get_current_user()` dependency that reads Bearer token, queries `neon_auth.session` + `neon_auth.user`, returns user info or 401
- [ ] 6.3 Apply `get_current_user` dependency to the top-level API v1 router in `main.py`
- [ ] 6.4 Ensure health check endpoint remains unauthenticated
- [ ] 6.5 Ensure CrowdReply webhook endpoint remains unauthenticated

## 7. Environment & Deployment

- [ ] 7.1 Add `NEON_AUTH_BASE_URL` and `NEON_AUTH_COOKIE_SECRET` to Railway frontend service
- [ ] 7.2 Set `AUTH_REQUIRED=false` on Railway backend initially for safe rollout
- [ ] 7.3 Deploy and verify end-to-end: sign in with Google → use app → sign out → redirected to sign-in
- [ ] 7.4 Set `AUTH_REQUIRED=true` on Railway backend after frontend is confirmed working

## 8. Verification

- [ ] 8.1 Verify: unauthenticated user is redirected to sign-in page
- [ ] 8.2 Verify: Google OAuth sign-in completes and redirects to dashboard
- [ ] 8.3 Verify: Header shows user name and sign-out button after sign-in
- [ ] 8.4 Verify: API calls include Authorization header and succeed
- [ ] 8.5 Verify: API calls without auth return 401 (when AUTH_REQUIRED=true)
- [ ] 8.6 Verify: Sign-out clears session and redirects to sign-in page
- [ ] 8.7 Verify: Health check endpoint works without auth
- [ ] 8.8 Update V2_REBUILD_PLAN.md with Phase 12 completion status
