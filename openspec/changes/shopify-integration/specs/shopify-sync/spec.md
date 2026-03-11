## ADDED Requirements

### Requirement: Shopify GraphQL client fetches store data
The system SHALL provide an async Shopify GraphQL client at `backend/app/integrations/shopify.py` that sends authenticated queries to the Shopify Admin GraphQL API (version 2024-10+).

#### Scenario: Client sends authenticated GraphQL query
- **WHEN** the client executes a GraphQL query for a connected store
- **THEN** the request includes the `X-Shopify-Access-Token` header with the decrypted access token and targets `https://{store}/admin/api/2024-10/graphql.json`

#### Scenario: Client handles rate limiting adaptively
- **WHEN** a GraphQL response indicates `currentlyAvailable` points below 100
- **THEN** the client pauses execution for `(100 - currentlyAvailable) / restoreRate` seconds before the next request

#### Scenario: Client retries on transient errors
- **WHEN** the Shopify API returns 429, 502, 503, or 504
- **THEN** the client retries up to 3 times with exponential backoff

#### Scenario: Client detects revoked tokens
- **WHEN** the Shopify API returns 401 Unauthorized
- **THEN** the client raises a `ShopifyAuthError` and does NOT retry

### Requirement: Immediate sync fetches all page types via paginated GraphQL
The system SHALL provide a `sync_immediate` function that fetches all collections, products, articles, and pages from a Shopify store using cursor-paginated GraphQL queries.

#### Scenario: Immediate sync fetches collections
- **WHEN** immediate sync runs for a connected store
- **THEN** system queries `collections(first: 250)` with cursor pagination, extracting `id`, `title`, `handle`, `productsCount`, `updatedAt`, and `ruleSet` for each collection

#### Scenario: Immediate sync fetches products
- **WHEN** immediate sync runs for a connected store
- **THEN** system queries `products(first: 250)` with cursor pagination, extracting `id`, `title`, `handle`, `status`, `productType`, `tags`, `publishedAt`, and `updatedAt` for each product

#### Scenario: Immediate sync fetches blog articles
- **WHEN** immediate sync runs for a connected store
- **THEN** system queries `articles(first: 250)` with cursor pagination, extracting `id`, `title`, `handle`, `publishedAt`, `tags`, `blog.title`, `blog.handle`, and `updatedAt` for each article

#### Scenario: Immediate sync fetches pages
- **WHEN** immediate sync runs for a connected store
- **THEN** system queries `pages(first: 250)` with cursor pagination, extracting `id`, `title`, `handle`, `publishedAt`, `isPublished`, and `updatedAt` for each page

#### Scenario: Immediate sync upserts results to shopify_pages table
- **WHEN** immediate sync completes fetching all resource types
- **THEN** system upserts all records into the `shopify_pages` table using `ON CONFLICT (project_id, shopify_id) DO UPDATE`, updates `last_synced_at`, and sets `is_deleted = false` for all synced records

#### Scenario: Immediate sync constructs full URLs
- **WHEN** a Shopify page is upserted
- **THEN** the `full_url` field is constructed as `{store_url}/collections/{handle}` for collections, `{store_url}/products/{handle}` for products, `{store_url}/blogs/{blog_handle}/{handle}` for articles, and `{store_url}/pages/{handle}` for pages

### Requirement: Nightly sync uses Bulk Operations API
The system SHALL provide a `sync_nightly` function that submits bulk operation queries to Shopify for each resource type, polls for completion, downloads JSONL results, and upserts to the database.

#### Scenario: Nightly sync submits bulk queries sequentially
- **WHEN** nightly sync runs for a connected store
- **THEN** system submits bulk operation mutations for collections, products, articles, and pages sequentially (one at a time, since only one bulk operation per store is allowed)

#### Scenario: Nightly sync polls for bulk operation completion
- **WHEN** a bulk operation is submitted
- **THEN** system polls the operation status every 10 seconds until status is `COMPLETED`, `FAILED`, or `CANCELED`

#### Scenario: Nightly sync downloads and processes JSONL
- **WHEN** a bulk operation completes with status `COMPLETED` and a non-null `url`
- **THEN** system downloads the JSONL file, parses each line as JSON, reassembles parent-child relationships via `__parentId`, and upserts records to `shopify_pages`

#### Scenario: Nightly sync detects deleted pages
- **WHEN** nightly sync completes for all resource types
- **THEN** system sets `is_deleted = true` for any `shopify_pages` records whose `shopify_id` was not seen in the current sync results (soft delete)

#### Scenario: Nightly sync updates project sync metadata
- **WHEN** nightly sync completes successfully
- **THEN** system updates the project's `shopify_last_sync_at` to current timestamp and `shopify_sync_status` to `"idle"`

#### Scenario: Nightly sync handles errors gracefully
- **WHEN** nightly sync fails (API error, timeout, token revoked)
- **THEN** system sets `shopify_sync_status` to `"error"`, logs the error, and does NOT modify existing `shopify_pages` data

### Requirement: APScheduler registers nightly sync jobs
The system SHALL register an APScheduler cron job for each project with a Shopify connection, running at 3:00 AM UTC with staggered offsets.

#### Scenario: Sync job is created on Shopify connect
- **WHEN** a project completes Shopify OAuth and stores an access token
- **THEN** system registers an APScheduler cron job with ID `shopify_sync_{project_id}` that runs `sync_nightly` daily

#### Scenario: Sync jobs are staggered across projects
- **WHEN** multiple projects have Shopify connections
- **THEN** each project's cron job runs at a different minute offset (based on project ID hash) to avoid thundering herd

#### Scenario: Sync job is removed on disconnect
- **WHEN** a project's Shopify connection is removed
- **THEN** the APScheduler job `shopify_sync_{project_id}` is removed

#### Scenario: Existing sync jobs are restored on backend startup
- **WHEN** the backend starts up
- **THEN** system queries all projects with non-null `shopify_store_domain` and ensures each has an APScheduler job registered (the SQLAlchemy job store persists jobs, but this handles edge cases)

### Requirement: Manual sync trigger endpoint
The system SHALL provide a POST endpoint at `/api/v1/projects/{id}/shopify/sync` that triggers an immediate sync.

#### Scenario: Manual sync triggers immediate sync
- **WHEN** client sends POST to `/api/v1/projects/{id}/shopify/sync`
- **THEN** system launches `sync_immediate` as a background task and returns 202 with `{ "status": "syncing" }`

#### Scenario: Manual sync rejects if already syncing
- **WHEN** client sends POST to `/api/v1/projects/{id}/shopify/sync` while `shopify_sync_status` is `"syncing"`
- **THEN** system returns 409 with error "Sync already in progress"

#### Scenario: Manual sync rejects if not connected
- **WHEN** client sends POST to `/api/v1/projects/{id}/shopify/sync` for a project with no Shopify connection
- **THEN** system returns 400 with error "Shopify not connected"

### Requirement: Shopify pages list endpoint
The system SHALL provide a GET endpoint at `/api/v1/projects/{id}/shopify/pages` that returns paginated Shopify pages filtered by type.

#### Scenario: List pages by type
- **WHEN** client sends GET to `/api/v1/projects/{id}/shopify/pages?type=collection&page=1&per_page=25`
- **THEN** system returns 200 with `{ "items": [...], "total": N, "page": 1, "per_page": 25 }` containing only non-deleted pages of the specified type

#### Scenario: Search pages by title
- **WHEN** client sends GET to `/api/v1/projects/{id}/shopify/pages?type=product&search=running`
- **THEN** system returns pages where title contains "running" (case-insensitive)

#### Scenario: List pages with counts per type
- **WHEN** client sends GET to `/api/v1/projects/{id}/shopify/pages/counts`
- **THEN** system returns 200 with `{ "collection": N, "product": N, "article": N, "page": N }` counting only non-deleted pages
