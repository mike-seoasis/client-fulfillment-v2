## ADDED Requirements

### Requirement: Auth server configuration
The system SHALL configure a Neon Auth server instance at `src/lib/auth/server.ts` using `createNeonAuth()` with the `NEON_AUTH_BASE_URL` and `NEON_AUTH_COOKIE_SECRET` environment variables.

#### Scenario: Server auth instance created
- **WHEN** the Next.js server starts
- **THEN** a Neon Auth server instance is available for middleware, API routes, and server-side session access

### Requirement: Auth client configuration
The system SHALL configure a Neon Auth client instance at `src/lib/auth/client.ts` using `createAuthClient()` for browser-side auth operations.

#### Scenario: Client auth instance created
- **WHEN** a client component imports the auth client
- **THEN** it can call `authClient.signIn.social()`, `authClient.signOut()`, and `authClient.useSession()`

### Requirement: Auth API route handler
The system SHALL expose auth API routes at `app/api/auth/[...path]/route.ts` using the server auth instance's `.handler()` method, handling GET and POST requests.

#### Scenario: Auth API handles sign-in
- **WHEN** the auth client initiates a sign-in flow
- **THEN** the API route proxies the request to Neon Auth and returns the response

### Requirement: Route protection middleware
The system SHALL protect all app routes via Next.js middleware. Unauthenticated users MUST be redirected to `/auth/sign-in`. Auth pages (`/auth/*`) and auth API routes (`/api/auth/*`) MUST be accessible without authentication.

#### Scenario: Unauthenticated user redirected to sign-in
- **WHEN** an unauthenticated user navigates to any app route (e.g., `/`, `/projects/123`, `/reddit`)
- **THEN** they are redirected to `/auth/sign-in`

#### Scenario: Auth pages accessible without session
- **WHEN** an unauthenticated user navigates to `/auth/sign-in`
- **THEN** the page loads without redirect

#### Scenario: Authenticated user accessing auth pages redirected to app
- **WHEN** an authenticated user navigates to `/auth/sign-in`
- **THEN** they are redirected to `/`

#### Scenario: Static assets and API auth routes bypass middleware
- **WHEN** a request targets `/_next/*`, `/fonts/*`, `/favicon.ico`, or `/api/auth/*`
- **THEN** the middleware does not intercept the request

### Requirement: Google OAuth sign-in page
The system SHALL provide a sign-in page at `/auth/sign-in` with a "Sign in with Google" button. The page MUST use a clean layout without the app Header. The page MUST match the tropical oasis design aesthetic.

#### Scenario: User signs in with Google
- **WHEN** user clicks "Sign in with Google" on the sign-in page
- **THEN** the browser redirects to Google OAuth consent screen
- **AND** after Google authentication, the user is redirected back to the app root (`/`)

#### Scenario: Sign-in page renders without Header
- **WHEN** the sign-in page loads
- **THEN** no app Header or navigation is displayed

### Requirement: Auth layout for sign-in pages
The system SHALL provide a dedicated layout at `app/auth/layout.tsx` that renders auth pages without the app Header component.

#### Scenario: Auth layout excludes Header
- **WHEN** any page under `/auth/*` is rendered
- **THEN** the page uses the auth layout which does not include the Header

### Requirement: Session token forwarded to backend API
The system SHALL include the authenticated user's session token as an `Authorization: Bearer <token>` header on all API requests to the FastAPI backend. The token MUST be obtained from the auth client's session data.

#### Scenario: API request includes auth header
- **WHEN** an authenticated user triggers an API call (e.g., list projects)
- **THEN** the request includes `Authorization: Bearer <session-token>` header

#### Scenario: API request without session omits auth header
- **WHEN** no session is active (e.g., during sign-in flow)
- **THEN** the request does not include an Authorization header

### Requirement: Auth token synchronization
The system SHALL synchronize the session token from `authClient.useSession()` into the API client module so that all fetch calls include the current token. The token MUST update when the session changes (sign-in, sign-out, refresh).

#### Scenario: Token updates on sign-in
- **WHEN** user completes Google OAuth sign-in
- **THEN** the API client's stored token updates to the new session token

#### Scenario: Token clears on sign-out
- **WHEN** user signs out
- **THEN** the API client's stored token is cleared to null
