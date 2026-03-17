## ADDED Requirements

### Requirement: SEO test docker-compose override
The system SHALL provide a `docker-compose.seo-test.yml` override file that configures an isolated local instance for SEO testing.

#### Scenario: Override file exists
- **WHEN** examining the project root
- **THEN** `docker-compose.seo-test.yml` SHALL exist alongside the base `docker-compose.yml`

#### Scenario: Separate database volume
- **WHEN** the SEO test compose is used
- **THEN** PostgreSQL SHALL use a separate named volume (`seo-test-pgdata`) that does not share data with the regular local dev volume

#### Scenario: Non-conflicting ports
- **WHEN** the SEO test compose is running
- **THEN** the backend SHALL be mapped to port 8001 and frontend to port 3001 (so it can coexist with a regular instance on 8000/3000)

#### Scenario: Content mode set to lorem
- **WHEN** the SEO test compose starts the backend
- **THEN** `CONTENT_MODE` SHALL be set to `lorem`

#### Scenario: Auth disabled
- **WHEN** the SEO test compose starts
- **THEN** `AUTH_REQUIRED` SHALL be set to `false`

#### Scenario: Start command
- **WHEN** the user runs `docker-compose -f docker-compose.yml -f docker-compose.seo-test.yml up -d`
- **THEN** all services SHALL start with the SEO test configuration applied

### Requirement: SEO test environment file
The system SHALL provide a `.env.seo-test` template file with all environment variables pre-configured for the SEO test instance.

#### Scenario: Environment file exists
- **WHEN** examining the project root
- **THEN** `.env.seo-test` SHALL exist with documented environment variables

#### Scenario: Database URL points to local PostgreSQL
- **WHEN** examining `.env.seo-test`
- **THEN** `DATABASE_URL` SHALL point to the local docker PostgreSQL service (not Neon)

#### Scenario: Content mode configured
- **WHEN** examining `.env.seo-test`
- **THEN** `CONTENT_MODE` SHALL be set to `lorem`

#### Scenario: API keys are placeholder
- **WHEN** examining `.env.seo-test`
- **THEN** API keys (`ANTHROPIC_API_KEY`, `POP_API_KEY`, `DATAFORSEO_API_LOGIN`, etc.) SHALL have placeholder values with comments instructing the user to fill them in

### Requirement: Visual SEO test mode indicator
When `CONTENT_MODE=lorem`, the frontend SHALL display a visual indicator distinguishing this instance from production.

#### Scenario: Mode badge in sidebar
- **WHEN** the frontend loads and the backend reports `content_mode=lorem`
- **THEN** the sidebar SHALL display a "SEO Test Mode" badge in coral color

#### Scenario: Badge not shown in real mode
- **WHEN** the backend reports `content_mode=real`
- **THEN** no mode badge SHALL be displayed

### Requirement: Config endpoint exposes content mode
The backend SHALL expose the current content mode so the frontend can display the appropriate indicator.

#### Scenario: Config endpoint returns content mode
- **WHEN** `GET /api/v1/config` is called
- **THEN** the response SHALL include `{"content_mode": "lorem"}` or `{"content_mode": "real"}`

#### Scenario: Health endpoint unaffected
- **WHEN** `GET /health` is called
- **THEN** it SHALL continue to return 200 OK regardless of content mode
