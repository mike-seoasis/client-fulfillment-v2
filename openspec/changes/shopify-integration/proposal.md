## Why

Client onboarding currently requires manually pasting collection page URLs or using an AI crawler to discover them. This is slow, error-prone, and doesn't maintain a live inventory of the client's Shopify store. We also have no way to detect duplicate blog topics before generating content, leading to wasted effort and potential conflicts with existing posts. A direct Shopify API connection solves both problems — auto-importing pages during onboarding and keeping a running inventory that feeds into deduplication and internal linking.

## What Changes

- Add Shopify OAuth flow so clients can connect their store during project setup (read-only: `read_products` + `read_content` scopes)
- Auto-import all collection pages, product pages, blog posts, and static pages from the connected Shopify store
- Add a **Pages tab** to the project dashboard with a sidebar-categorized view (Collections, Products, Blog Posts, Pages) showing the full live page inventory
- Add nightly sync via APScheduler to keep the page inventory current (using Shopify's GraphQL Bulk Operations API)
- Add blog deduplication logic: silently filter >90% title similarity matches, show warnings for lower-confidence matches with links to the live post
- Add a "Connect Shopify" step to the new project creation flow, replacing manual URL paste for Shopify stores
- Store Shopify access tokens (encrypted) and sync metadata per project

## Capabilities

### New Capabilities
- `shopify-oauth`: Shopify OAuth install flow — redirect to Shopify, exchange code for offline access token, store encrypted token per project, handle uninstalls via webhook
- `shopify-sync`: Read-only data sync from Shopify Admin GraphQL API — fetch collections, products, articles, pages; incremental sync via `updated_at` filter; nightly bulk operations; manual "Sync Now" trigger
- `shopify-pages-ui`: Pages tab on project dashboard — tabbed layout (Tools | Pages), left sidebar category nav with counts, paginated table per category, search, sync status display, empty/connecting/syncing states
- `blog-dedup`: Blog topic deduplication — compare generated blog ideas against existing Shopify blog posts by title similarity; silent filter at >90% match; warning with link to live post at lower confidence

### Modified Capabilities
- `project-management`: Projects gain optional Shopify connection fields (store domain, encrypted access token, sync config, last sync timestamp)
- `project-detail-view`: Project dashboard adds a tab bar (Tools | Pages) wrapping the existing content; existing dashboard becomes the "Tools" tab

## Impact

- **Backend**: New `integrations/shopify.py` client, new `api/v1/shopify.py` router, new DB migration for Shopify fields on projects + `shopify_page_type` on crawled_pages, new APScheduler job registration
- **Frontend**: New tabbed layout on project detail page, new Pages tab components (sidebar, tables, search, pagination), new "Connect Shopify" step in project creation
- **Dependencies**: `basic-shopify-api` or `httpx` for async Shopify GraphQL calls, `cryptography` (Fernet) for token encryption
- **External**: Requires a Shopify Partners account (free) and a registered public app (unlisted distribution)
- **Environment**: New env vars: `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_TOKEN_ENCRYPTION_KEY`
- **Deployment**: GDPR webhook endpoints required by Shopify (3 minimal endpoints), OAuth callback URL must be HTTPS (Railway provides this)
