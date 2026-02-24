## Why

The app is currently open to anyone with the URL. As we move toward production use, the internal ops team needs authentication to prevent unauthorized access. Neon Auth (built on Better Auth, managed by Neon) keeps auth in the same provider as the database, with sessions stored in the `neon_auth` schema — future-proofing for per-user data isolation via Row Level Security.

## What Changes

- Add Neon Auth SDK to the Next.js frontend for Google OAuth sign-in
- Add Next.js middleware to protect all app routes (redirect unauthenticated users to sign-in page)
- Add a sign-in page with "Sign in with Google" button
- Update the Header component with user display and sign-out
- Modify the frontend API client to include session tokens in backend requests
- Add FastAPI auth dependency that validates session tokens against the `neon_auth.session` table
- Apply auth dependency to all backend API routes

## Capabilities

### New Capabilities
- `neon-auth-frontend`: Frontend authentication with Neon Auth SDK — Google OAuth sign-in, route protection middleware, session management, auth token forwarding to backend API
- `neon-auth-backend`: Backend session validation — FastAPI dependency that reads Bearer tokens and validates against `neon_auth.session` table, applied to all API routes

### Modified Capabilities
- `dashboard`: Header component updated with user display (name/avatar from Google) and sign-out button

## Impact

- **Frontend**: New dependency `@neondatabase/auth`, new middleware file, new auth pages, modified Header and API client
- **Backend**: New `app/core/auth.py` module, all existing routes gain auth dependency
- **Database**: Neon Auth creates `neon_auth` schema automatically (no Alembic migration needed)
- **Environment**: Two new env vars for frontend (`NEON_AUTH_BASE_URL`, `NEON_AUTH_COOKIE_SECRET`), Railway config updates
- **Breaking**: All API endpoints will return 401 without a valid session token
