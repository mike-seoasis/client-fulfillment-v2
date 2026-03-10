## ADDED Requirements

### Requirement: OAuth install endpoint initiates Shopify authorization
The system SHALL provide a GET endpoint at `/api/v1/shopify/auth/install` that accepts `shop` (store domain) and `project_id` query parameters, constructs a Shopify OAuth authorization URL with scopes `read_products,read_content`, and redirects the user to Shopify.

#### Scenario: Valid install request redirects to Shopify
- **WHEN** client sends GET to `/api/v1/shopify/auth/install?shop=acmestore.myshopify.com&project_id={id}`
- **THEN** system redirects (302) to `https://acmestore.myshopify.com/admin/oauth/authorize` with `client_id`, `scope=read_products,read_content`, `redirect_uri`, and a cryptographic `state` parameter

#### Scenario: Install request validates shop domain format
- **WHEN** client sends GET to `/api/v1/shopify/auth/install?shop=not-valid&project_id={id}`
- **THEN** system returns 400 with error "Invalid Shopify store domain"

#### Scenario: Install request validates project exists
- **WHEN** client sends GET to `/api/v1/shopify/auth/install?shop=store.myshopify.com&project_id={nonexistent}`
- **THEN** system returns 404 with error "Project not found"

### Requirement: OAuth callback exchanges code for access token
The system SHALL provide a GET endpoint at `/api/v1/shopify/auth/callback` that validates the HMAC signature, verifies the state parameter, exchanges the authorization code for an offline access token, encrypts the token, and stores it on the project.

#### Scenario: Valid callback stores encrypted token
- **WHEN** Shopify redirects to callback with valid `code`, `hmac`, `shop`, and `state` parameters
- **THEN** system exchanges code for offline access token, encrypts token with Fernet, stores encrypted token + shop domain + scopes on the project, and redirects user to the project's Pages tab

#### Scenario: Callback rejects invalid HMAC
- **WHEN** callback receives parameters with an invalid or missing `hmac` signature
- **THEN** system returns 401 with error "Invalid signature"

#### Scenario: Callback rejects invalid state parameter
- **WHEN** callback receives a `state` parameter that does not match any pending OAuth session
- **THEN** system returns 400 with error "Invalid or expired state"

#### Scenario: Callback rejects if project already has a different store connected
- **WHEN** callback completes for a project that already has a different Shopify store connected
- **THEN** system replaces the old connection with the new one (stores are 1:1 with projects)

### Requirement: Token encryption uses Fernet symmetric encryption
The system SHALL encrypt Shopify access tokens using Fernet (from the `cryptography` package) with a key stored in the `SHOPIFY_TOKEN_ENCRYPTION_KEY` environment variable.

#### Scenario: Token is encrypted before database storage
- **WHEN** a Shopify access token is received from the OAuth exchange
- **THEN** system encrypts the token using Fernet before writing to the `shopify_access_token_encrypted` column

#### Scenario: Token is decrypted for API calls
- **WHEN** the system needs to make a Shopify API call for a project
- **THEN** system decrypts the stored token using the same Fernet key

### Requirement: Shopify disconnect endpoint removes connection
The system SHALL provide a DELETE endpoint at `/api/v1/projects/{id}/shopify` that clears the Shopify connection fields and cancels any scheduled sync jobs.

#### Scenario: Disconnect clears Shopify fields
- **WHEN** client sends DELETE to `/api/v1/projects/{id}/shopify`
- **THEN** system clears `shopify_store_domain`, `shopify_access_token_encrypted`, `shopify_scopes`, `shopify_last_sync_at`, `shopify_sync_status`, `shopify_connected_at` from the project and returns 200

#### Scenario: Disconnect cancels scheduled sync job
- **WHEN** client disconnects Shopify from a project that has a nightly sync job registered
- **THEN** the APScheduler job for that project is removed

#### Scenario: Disconnect on project with no Shopify connection
- **WHEN** client sends DELETE to `/api/v1/projects/{id}/shopify` for a project with no Shopify connection
- **THEN** system returns 200 (idempotent, no error)

### Requirement: GDPR webhook endpoints exist
The system SHALL provide three POST endpoints for Shopify GDPR compliance that return 200 OK.

#### Scenario: Customer data request webhook returns 200
- **WHEN** Shopify sends POST to `/api/v1/shopify/webhooks/customers/data_request`
- **THEN** system returns 200 OK (no customer data is stored)

#### Scenario: Customer redact webhook returns 200
- **WHEN** Shopify sends POST to `/api/v1/shopify/webhooks/customers/redact`
- **THEN** system returns 200 OK

#### Scenario: Shop redact webhook returns 200
- **WHEN** Shopify sends POST to `/api/v1/shopify/webhooks/shop/redact`
- **THEN** system returns 200 OK

### Requirement: App uninstall webhook clears connection
The system SHALL handle the `app/uninstalled` webhook by clearing the Shopify connection for the affected store.

#### Scenario: Uninstall webhook clears project connection
- **WHEN** Shopify sends an `app/uninstalled` webhook for a connected store
- **THEN** system identifies the project by store domain, clears Shopify connection fields, cancels sync job, and sets `shopify_sync_status` to `"disconnected"`

#### Scenario: Uninstall webhook verifies HMAC
- **WHEN** Shopify sends an `app/uninstalled` webhook
- **THEN** system verifies the `X-Shopify-Hmac-SHA256` header using the app's client secret before processing

### Requirement: Shopify connection status endpoint
The system SHALL provide a GET endpoint at `/api/v1/projects/{id}/shopify/status` that returns the current Shopify connection state.

#### Scenario: Connected store returns status
- **WHEN** client sends GET to `/api/v1/projects/{id}/shopify/status` for a connected project
- **THEN** system returns 200 with `{ "connected": true, "store_domain": "...", "last_sync_at": "...", "sync_status": "idle", "connected_at": "..." }`

#### Scenario: Unconnected project returns status
- **WHEN** client sends GET to `/api/v1/projects/{id}/shopify/status` for a project with no Shopify connection
- **THEN** system returns 200 with `{ "connected": false }`
