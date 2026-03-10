## 1. Database & Models

- [x] 1.1 Create Alembic migration adding Shopify columns to `projects` table (`shopify_store_domain`, `shopify_access_token_encrypted`, `shopify_scopes`, `shopify_last_sync_at`, `shopify_sync_status`, `shopify_connected_at`)
- [x] 1.2 Create Alembic migration adding `shopify_pages` table with columns, unique constraint on `(project_id, shopify_id)`, composite index on `(project_id, page_type, is_deleted)`, and cascade delete FK to `projects`
- [x] 1.3 Add Shopify fields to the `Project` SQLAlchemy model and update Pydantic response schemas to include `shopify_connected` (bool) and `shopify_store_domain` (exclude encrypted token from responses)
- [x] 1.4 Create `ShopifyPage` SQLAlchemy model in `backend/app/models/shopify_page.py` and register in `models/__init__.py`

## 2. Configuration & Encryption

- [x] 2.1 Add env vars to `backend/app/core/config.py`: `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_TOKEN_ENCRYPTION_KEY` (all optional, feature disabled when absent)
- [x] 2.2 Create `backend/app/core/shopify_crypto.py` with `encrypt_token()` and `decrypt_token()` functions using Fernet symmetric encryption
- [x] 2.3 Add `cryptography` to `requirements.txt`

## 3. Shopify GraphQL Client

- [x] 3.1 Create `backend/app/integrations/shopify.py` with async `ShopifyGraphQLClient` class (httpx-based, authenticated POST to GraphQL endpoint, adaptive rate limiting via `extensions.cost.throttleStatus`)
- [x] 3.2 Add retry logic for transient errors (429, 502, 503, 504) with exponential backoff, and `ShopifyAuthError` for 401
- [x] 3.3 Add paginated query methods: `fetch_collections()`, `fetch_products()`, `fetch_articles()`, `fetch_pages()` — each returns all items using cursor pagination
- [x] 3.4 Add bulk operation methods: `start_bulk_query()`, `poll_bulk_operation()`, `download_jsonl()` for nightly sync

## 4. Sync Service

- [x] 4.1 Create `backend/app/services/shopify_sync.py` with `sync_immediate()` — calls all 4 paginated fetch methods, upserts to `shopify_pages`, constructs `full_url` per page type
- [x] 4.2 Add `sync_nightly()` — submits bulk operations sequentially, polls for completion, downloads JSONL, upserts to DB, soft-deletes pages not seen in results
- [x] 4.3 Add URL construction logic: `/collections/{handle}`, `/products/{handle}`, `/blogs/{blog_handle}/{handle}`, `/pages/{handle}`
- [x] 4.4 Add sync metadata updates: set `shopify_last_sync_at` and `shopify_sync_status` on project after sync completes/fails

## 5. OAuth & Webhook Routes

- [x] 5.1 Create `backend/app/api/v1/shopify.py` router with OAuth endpoints: `GET /shopify/auth/install` (constructs auth URL, redirects) and `GET /shopify/auth/callback` (validates HMAC + state, exchanges code for token, encrypts + stores)
- [x] 5.2 Add HMAC verification utility for OAuth callback and webhooks (`verify_shopify_hmac`)
- [x] 5.3 Add GDPR webhook endpoints: `POST /shopify/webhooks/customers/data_request`, `POST /shopify/webhooks/customers/redact`, `POST /shopify/webhooks/shop/redact` (all return 200)
- [x] 5.4 Add `app/uninstalled` webhook handler: verifies HMAC, clears Shopify fields on project, cancels sync job
- [x] 5.5 Register shopify router in `backend/app/api/v1/__init__.py`

## 6. API Endpoints (Pages, Sync, Status)

- [x] 6.1 Add `GET /projects/{id}/shopify/status` — returns connection state (connected bool, store domain, last sync, sync status)
- [x] 6.2 Add `GET /projects/{id}/shopify/pages` — paginated list with `type`, `search`, `page`, `per_page` query params
- [x] 6.3 Add `GET /projects/{id}/shopify/pages/counts` — returns count per page type (excluding soft-deleted)
- [x] 6.4 Add `POST /projects/{id}/shopify/sync` — triggers immediate sync as background task, returns 202
- [x] 6.5 Add `DELETE /projects/{id}/shopify` — disconnects Shopify, clears fields, cancels sync job

## 7. Scheduler Integration

- [x] 7.1 Add nightly sync job registration in `backend/app/core/scheduler.py`: register cron job on Shopify connect, remove on disconnect, stagger start times by project ID hash
- [x] 7.2 Add startup restoration: on backend start, ensure all projects with Shopify connections have active APScheduler jobs
- [x] 7.3 Ensure sync job function handles async correctly (APScheduler thread pool → `asyncio.run()` wrapper)

## 8. Blog Deduplication

- [x] 8.1 Create `backend/app/services/blog_dedup.py` with `check_duplicates()` function: normalizes titles (lowercase, strip punctuation, collapse whitespace), computes Levenshtein ratio
- [x] 8.2 Integrate dedup into blog topic generation pipeline: query `shopify_pages` where `page_type = 'article'`, compare each generated title, silently filter >90% matches, flag 70-90% matches with warning + live URL
- [x] 8.3 Add `python-Levenshtein` (or use `rapidfuzz`) to `requirements.txt`

## 9. Frontend — Tabbed Layout

- [x] 9.1 Add tab bar component to project detail page (`projects/[id]/page.tsx`): "Tools" and "Pages" tabs, URL query param `?tab=tools|pages`, palm-500 active indicator
- [x] 9.2 Extract existing dashboard content into a `ToolsTab` component (zero behavior changes, just wrapping)
- [x] 9.3 Create `PagesTab` component shell with conditional rendering based on Shopify connection status (not-connected, syncing, connected)

## 10. Frontend — Pages Tab (Connected State)

- [x] 10.1 Create category sidebar component with nav items: Collections, Products, Blog Posts, Pages — each with count badge from `/shopify/pages/counts`
- [x] 10.2 Create paginated table component with columns varying by category (Collections: title/handle/products, Products: title/type/status, Blog Posts: title/blog/published, Pages: title/handle/status)
- [x] 10.3 Add search input that filters the current category via `search` query param
- [x] 10.4 Add sync status header: store name, "Synced X ago" timestamp, "Sync Now" button wired to `POST /shopify/sync`
- [x] 10.5 Add row click behavior: opens `full_url` in new browser tab

## 11. Frontend — Empty & Syncing States

- [x] 11.1 Create not-connected empty state: link icon, heading, description, "Connect to Shopify" button that prompts for store domain then redirects to OAuth
- [x] 11.2 Create first-sync progress state: spinner with per-resource-type status (checkmark/spinner/circle for collections/products/blogs/pages)
- [x] 11.3 Add polling for sync status during initial sync (poll `/shopify/status` until `sync_status` returns to `"idle"`)

## 12. Frontend — Project Creation

- [x] 12.1 Add optional "Connect Shopify Store" section to `/projects/new` form: text input for `*.myshopify.com` domain with validation
- [x] 12.2 On form submit with Shopify domain: create project, then redirect to OAuth install endpoint with project ID + store domain

## 13. API Client & Hooks

- [x] 13.1 Add Shopify API functions to `frontend/src/lib/api.ts`: `getShopifyStatus()`, `getShopifyPages()`, `getShopifyPageCounts()`, `triggerShopifySync()`, `disconnectShopify()`
- [x] 13.2 Create TanStack Query hooks: `useShopifyStatus()`, `useShopifyPages()`, `useShopifyPageCounts()`, `useShopifySync()` with appropriate cache keys and invalidation

## 14. Testing & Verification

- [x] 14.1 Write backend tests for Shopify GraphQL client (mock httpx responses, test rate limiting, retry logic, auth error handling)
- [x] 14.2 Write backend tests for sync service (mock Shopify client, verify upsert logic, soft-delete detection, URL construction)
- [x] 14.3 Write backend tests for OAuth flow (mock Shopify token exchange, HMAC verification, state validation)
- [x] 14.4 Write backend tests for blog dedup (test similarity thresholds, normalization, edge cases)
- [x] 14.5 Manual verification: connect a test Shopify store, verify OAuth flow, verify immediate sync populates all categories, verify Pages tab displays data correctly
- [x] 14.6 Update V2_REBUILD_PLAN.md with Shopify integration phase status
