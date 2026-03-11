## MODIFIED Requirements

### Requirement: Create a project
The system SHALL provide an API endpoint to create a new project with name, site URL, and an optional Shopify store domain. If a Shopify store domain is provided, the system SHALL initiate the OAuth flow after project creation.

#### Scenario: Create project with valid data
- **WHEN** client sends POST to `/api/v1/projects` with `{"name": "Acme Store", "site_url": "https://acme.com"}`
- **THEN** system returns 201 with created project object including server-generated `id` and timestamps

#### Scenario: Create project with missing name
- **WHEN** client sends POST to `/api/v1/projects` with `{"site_url": "https://acme.com"}` (missing name)
- **THEN** system returns 422 with validation error indicating name is required

#### Scenario: Create project with missing site_url
- **WHEN** client sends POST to `/api/v1/projects` with `{"name": "Acme Store"}` (missing site_url)
- **THEN** system returns 422 with validation error indicating site_url is required

#### Scenario: Create project with invalid URL format
- **WHEN** client sends POST to `/api/v1/projects` with `{"name": "Acme", "site_url": "not-a-url"}`
- **THEN** system returns 422 with validation error indicating site_url must be a valid URL

#### Scenario: Create project with Shopify store domain
- **WHEN** client sends POST to `/api/v1/projects` with `{"name": "Acme Store", "site_url": "https://acme.com", "shopify_store_domain": "acmestore.myshopify.com"}`
- **THEN** system returns 201 with created project object and the response includes `shopify_store_domain` field (token is not yet stored — OAuth must complete separately)

## ADDED Requirements

### Requirement: Project data model includes Shopify connection fields
The Project database model SHALL include fields for Shopify store connection: `shopify_store_domain` (TEXT, nullable), `shopify_access_token_encrypted` (TEXT, nullable), `shopify_scopes` (TEXT, nullable), `shopify_last_sync_at` (TIMESTAMPTZ, nullable), `shopify_sync_status` (TEXT, nullable, default null), `shopify_connected_at` (TIMESTAMPTZ, nullable).

#### Scenario: New projects have null Shopify fields
- **WHEN** a project is created without Shopify connection
- **THEN** all Shopify fields are null

#### Scenario: Shopify fields are populated after OAuth
- **WHEN** a project completes Shopify OAuth
- **THEN** `shopify_store_domain`, `shopify_access_token_encrypted`, `shopify_scopes`, and `shopify_connected_at` are populated

#### Scenario: Project API responses include Shopify connection status
- **WHEN** client sends GET to `/api/v1/projects/{id}`
- **THEN** the response includes `shopify_connected` (boolean derived from whether `shopify_store_domain` is non-null) and `shopify_store_domain` (the domain or null), but NEVER includes the encrypted access token

### Requirement: Shopify pages data model
The system SHALL provide a `shopify_pages` database table storing synced Shopify page data with columns: `id` (UUID PK), `project_id` (UUID FK), `shopify_id` (TEXT), `page_type` (TEXT: collection/product/article/page), `title` (TEXT), `handle` (TEXT), `full_url` (TEXT), `status` (TEXT), `published_at` (TIMESTAMPTZ), `product_type` (TEXT, nullable), `product_count` (INT, nullable), `blog_name` (TEXT, nullable), `tags` (TEXT[], nullable), `shopify_updated_at` (TIMESTAMPTZ), `last_synced_at` (TIMESTAMPTZ), `is_deleted` (BOOLEAN default false), `created_at` (TIMESTAMPTZ), `updated_at` (TIMESTAMPTZ).

#### Scenario: Unique constraint on project_id + shopify_id
- **WHEN** database schema is inspected
- **THEN** a unique constraint exists on `(project_id, shopify_id)` preventing duplicate Shopify pages per project

#### Scenario: Composite index for category queries
- **WHEN** database schema is inspected
- **THEN** an index exists on `(project_id, page_type, is_deleted)` for efficient filtered queries

#### Scenario: Deleting a project cascades to shopify_pages
- **WHEN** a project is deleted
- **THEN** all associated `shopify_pages` records are cascade-deleted
