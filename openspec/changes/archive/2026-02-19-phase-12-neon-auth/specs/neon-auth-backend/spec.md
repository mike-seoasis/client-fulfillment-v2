## ADDED Requirements

### Requirement: Session validation dependency
The system SHALL provide a FastAPI dependency `get_current_user()` in `app/core/auth.py` that validates the `Authorization: Bearer <token>` header against the `neon_auth.session` table. It MUST return user information (id, email, name) on success and raise HTTP 401 on failure.

#### Scenario: Valid session token
- **WHEN** a request includes `Authorization: Bearer <token>` with a valid, non-expired token
- **THEN** the dependency returns the authenticated user's id, email, and name from the joined `neon_auth.user` table

#### Scenario: Missing Authorization header
- **WHEN** a request has no Authorization header
- **THEN** the dependency raises HTTP 401 with body `{"detail": "Not authenticated"}`

#### Scenario: Invalid or expired token
- **WHEN** a request includes a Bearer token that does not match any session or the session has expired
- **THEN** the dependency raises HTTP 401 with body `{"detail": "Invalid or expired session"}`

#### Scenario: Malformed Authorization header
- **WHEN** a request includes an Authorization header that is not in `Bearer <token>` format
- **THEN** the dependency raises HTTP 401 with body `{"detail": "Not authenticated"}`

### Requirement: Auth applied to all API routes
The system SHALL apply the `get_current_user` dependency to the top-level API v1 router so all endpoints require authentication by default. The health check endpoint MUST remain unauthenticated.

#### Scenario: Protected endpoint without auth returns 401
- **WHEN** an unauthenticated request hits `/api/v1/projects`
- **THEN** the response is HTTP 401

#### Scenario: Protected endpoint with valid auth succeeds
- **WHEN** an authenticated request hits `/api/v1/projects`
- **THEN** the request proceeds normally and returns project data

#### Scenario: Health check bypasses auth
- **WHEN** an unauthenticated request hits `/health`
- **THEN** the response is HTTP 200 with health status

### Requirement: Auth toggle for development
The system SHALL support an `AUTH_REQUIRED` environment variable (default `true`). When set to `false`, the auth dependency MUST skip validation and return a placeholder user, allowing unauthenticated API access during development.

#### Scenario: Auth disabled in development
- **WHEN** `AUTH_REQUIRED=false` and a request has no Authorization header
- **THEN** the dependency returns a placeholder user (id="dev-user", email="dev@localhost", name="Dev User")

#### Scenario: Auth enabled in production
- **WHEN** `AUTH_REQUIRED=true` (or not set) and a request has no Authorization header
- **THEN** the dependency raises HTTP 401

### Requirement: CrowdReply webhook bypasses auth
The CrowdReply webhook endpoint MUST remain accessible without authentication since it receives callbacks from an external service with its own secret-based verification.

#### Scenario: Webhook receives callback without Bearer token
- **WHEN** CrowdReply sends a POST to the webhook endpoint without an Authorization header
- **THEN** the webhook processes normally using its own HMAC verification
