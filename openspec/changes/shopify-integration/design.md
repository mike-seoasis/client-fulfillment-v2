## Context

The client onboarding platform currently relies on manual URL paste or AI crawling (Crawl4AI) to discover a client's Shopify pages. This works but is slow, incomplete, and creates a one-time snapshot rather than a living inventory. The platform already integrates with external services (WordPress, CrowdReply, DataForSEO) using a consistent pattern: an async client in `integrations/`, routes in `api/v1/`, and models in `models/`. The backend runs FastAPI with async SQLAlchemy on Neon PostgreSQL, deployed to Railway. APScheduler is already initialized with a SQLAlchemy job store but has no registered recurring jobs yet.

Shopify's REST Admin API is deprecated (Oct 2024). The GraphQL Admin API is the only path forward. API version 2024-10+ is required for Pages/Articles/Blogs support in GraphQL.

## Goals / Non-Goals

**Goals:**
- Read-only Shopify connection via OAuth that works for any Shopify store
- Immediate page import during onboarding (replaces manual URL paste for Shopify stores)
- Nightly sync that keeps the page inventory current without manual intervention
- Pages tab on the project dashboard showing categorized page inventory
- Blog deduplication that prevents generating content ideas that already exist as published posts

**Non-Goals:**
- Writing data back to Shopify (no product creation, no content publishing)
- Shopify App Store listing (unlisted distribution via direct install link)
- Real-time webhooks for page/article changes (no webhook topics exist for content; products/collections webhooks are a future enhancement)
- Storefront API integration (Admin API covers all needs with better auth flow)
- Multi-store per project (one Shopify store per project)

## Decisions

### 1. GraphQL Admin API only (no REST)

**Decision:** Use Shopify's GraphQL Admin API exclusively.

**Rationale:** REST is deprecated since Oct 2024. GraphQL has cost-based rate limiting (50 pts/sec vs 2 req/sec), supports bulk operations, and lets us fetch exactly the fields we need. API version `2024-10` adds GraphQL support for Pages, Articles, and Blogs.

**Alternative considered:** REST Admin API — rejected because it's legacy and less efficient for bulk reads.

### 2. Raw `httpx` over `basic_shopify_api`

**Decision:** Use `httpx.AsyncClient` directly for Shopify GraphQL calls rather than a third-party wrapper library.

**Rationale:** We only need read-only GraphQL queries and bulk operations. `httpx` is already a transitive dependency (used by FastAPI's test client). The Shopify GraphQL interface is simple (POST JSON, read response). Building our own thin client gives us full control over retry logic, rate limiting, and error handling without depending on a small community library. We implement adaptive throttling by reading `extensions.cost.throttleStatus` from each response.

**Alternative considered:** `basic_shopify_api` — async-native and feature-rich, but adds a dependency for functionality we can implement in ~100 lines. `ShopifyAPI` (official) — rejected, no async support.

### 3. Public App with unlisted distribution

**Decision:** Register a Public App on Shopify Partners (free) and distribute via direct install link.

**Rationale:** Public Apps are the only type that support OAuth installation on stores you don't own. Unlisted distribution means no App Store review required initially. The client experience is seamless: click "Connect Shopify" → authorize on Shopify → redirected back. Custom Apps would require each client to manually create API credentials in their store admin — terrible UX.

**Requirement:** Shopify requires 3 GDPR webhook endpoints even for unlisted apps. These can return 200 OK with no logic since we store no customer data.

### 4. Offline access tokens, encrypted at rest

**Decision:** Use offline access tokens (the OAuth default) and encrypt them with Fernet symmetric encryption before storing in PostgreSQL.

**Rationale:** Offline tokens don't expire — they persist until the merchant uninstalls the app. This is essential for nightly background syncs (online tokens expire in ~24h). Fernet encryption is simple, well-audited, and the `cryptography` package is already widely used. The encryption key lives in an environment variable, never in the database.

**Alternative considered:** Storing tokens in a secrets manager (Vault, AWS Secrets Manager) — overkill for our scale. We'd add this if we grow past ~50 connected stores.

### 5. Nightly sync via Bulk Operations API + APScheduler

**Decision:** Use Shopify's GraphQL Bulk Operations API for nightly full syncs, triggered by APScheduler cron jobs.

**Rationale:** Bulk Operations run server-side at Shopify — no pagination, no rate limit concerns, results delivered as a JSONL download. APScheduler is already initialized in our backend with a PostgreSQL job store. Each connected project gets a cron job (staggered start times to avoid thundering herd). For the initial onboarding sync, we use paginated GraphQL queries instead (faster for first-time import, doesn't require waiting for async bulk operation completion).

**Sync strategy:**
- **Onboarding (immediate):** Paginated GraphQL queries — `collections(first: 250)`, `products(first: 250)`, `articles(first: 250)`, `pages(first: 250)` with cursor pagination. Fast enough for initial import.
- **Nightly (bulk):** Submit 4 bulk operation mutations (one per resource type, run sequentially since only 1 bulk op allowed at a time per store). Poll for completion. Download JSONL. Diff against local DB. Upsert changes, soft-delete removed items.

### 6. New `shopify_pages` table (not reusing `crawled_pages`)

**Decision:** Create a dedicated `shopify_pages` table rather than inserting Shopify data into the existing `crawled_pages` table.

**Rationale:** `crawled_pages` is tightly coupled to the onboarding crawl workflow — it has fields like `crawl_error`, `content_hash`, `body_content` (markdown from crawling), and status values (`pending`/`crawling`/`completed`/`failed`) that don't apply to Shopify API imports. Shopify pages have their own fields (`shopify_id`, `page_type`, `product_type`, `product_count`, `blog_name`, `published_at`). A separate table keeps concerns clean and avoids polluting the crawl pipeline. The internal linking logic can query both tables when building link plans.

**Schema:**
```
shopify_pages (
  id UUID PK,
  project_id UUID FK → projects,
  shopify_id TEXT NOT NULL,         -- e.g., "gid://shopify/Product/123"
  page_type TEXT NOT NULL,          -- "collection", "product", "article", "page"
  title TEXT,
  handle TEXT,                      -- URL slug
  full_url TEXT,                    -- constructed: {store_url}/collections/{handle}
  status TEXT,                      -- "active", "draft", "archived"
  published_at TIMESTAMPTZ,
  -- Type-specific fields (nullable)
  product_type TEXT,                -- products only
  product_count INT,                -- collections only
  blog_name TEXT,                   -- articles only
  tags TEXT[],                      -- products + articles
  -- Sync metadata
  shopify_updated_at TIMESTAMPTZ,
  last_synced_at TIMESTAMPTZ,
  is_deleted BOOLEAN DEFAULT false, -- soft delete for items removed from Shopify
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ,
  UNIQUE(project_id, shopify_id)
)
```

**Index:** Composite index on `(project_id, page_type, is_deleted)` for the category sidebar queries.

### 7. Shopify connection fields on `projects` table

**Decision:** Add Shopify connection columns directly to the `projects` table rather than a separate `shopify_connections` table.

**Rationale:** One store per project. No need for a join table. Simple to query.

**New columns:**
```
shopify_store_domain TEXT,          -- e.g., "acmestore.myshopify.com"
shopify_access_token_encrypted TEXT, -- Fernet-encrypted offline token
shopify_scopes TEXT,                -- granted scopes for verification
shopify_last_sync_at TIMESTAMPTZ,
shopify_sync_status TEXT,           -- "idle", "syncing", "error"
shopify_connected_at TIMESTAMPTZ,
```

### 8. Blog deduplication via title similarity

**Decision:** Use normalized Levenshtein distance for title comparison. Silent filter at >90% similarity, warning at 70-90%.

**Rationale:** Blog titles are short strings where edit distance works well. No need for embedding-based similarity at this stage — titles are explicit enough. The comparison runs at content idea generation time, comparing each proposed title against all `shopify_pages` where `page_type = 'article'` for that project.

**Algorithm:**
1. Normalize both titles: lowercase, strip punctuation, collapse whitespace
2. Compute Levenshtein ratio: `1 - (edit_distance / max(len(a), len(b)))`
3. If ratio > 0.90: silently exclude from generated ideas
4. If ratio 0.70-0.90: include but flag with warning + link to live post
5. If ratio < 0.70: no match, include normally

### 9. Tabbed project dashboard layout

**Decision:** Add a tab bar (Tools | Pages) below the project header. "Tools" renders the existing dashboard. "Pages" renders the new inventory view.

**Rationale:** Keeps the existing dashboard intact while adding a new surface for the page inventory. The tab state is managed via URL search params (`?tab=tools` or `?tab=pages`) so it's bookmarkable and shareable. Default tab is "Tools" to preserve existing behavior.

**Frontend structure:**
- Tab bar component at project page level
- Tools tab: existing sections (onboarding, clusters, blogs, reddit) — zero changes
- Pages tab: new component with left sidebar (category nav) + right content (paginated table)

## Risks / Trade-offs

**[Shopify App Review] →** Unlisted public apps may require basic review for stores outside our Partners org. Mitigation: submit for review early; the review is lighter than App Store listing and our read-only scopes are low-risk.

**[Token Revocation] →** If a merchant uninstalls the app, the token is invalidated and nightly sync will fail with 401. Mitigation: subscribe to `app/uninstalled` webhook; on receipt, clear token and mark project as disconnected. Sync jobs check for valid token before executing.

**[Bulk Operation Limits] →** Only 1 bulk operation per store at a time (pre-2026-01 API). Since we need 4 resource types, they must run sequentially. Mitigation: stagger nightly syncs across projects; each project's sync takes ~2-5 minutes for typical store sizes.

**[Rate Limits During Onboarding] →** The immediate paginated sync during onboarding consumes rate limit budget (50 pts/sec). A store with 10K+ products could take several minutes. Mitigation: show progress indicator per resource type; use `first: 250` (max page size) to minimize requests; adaptive throttling based on `currentlyAvailable` in response.

**[No Webhooks for Content] →** Shopify has no webhook topics for Pages or Articles. Blog posts and pages can only be detected via polling. Mitigation: nightly sync catches all changes within 24h. For most SEO workflows, this latency is acceptable.

**[Separate Table vs Unified] →** Having `shopify_pages` separate from `crawled_pages` means internal linking must query both. Mitigation: the link planning service already accepts a list of URLs — we just union both sources when building the link plan.

## Migration Plan

1. **Database migration:** Add Shopify columns to `projects`, create `shopify_pages` table with indexes
2. **Backend deployment:** Deploy new routes + integration client. GDPR endpoints must be live before any OAuth installs.
3. **Environment variables:** Set `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_TOKEN_ENCRYPTION_KEY` on Railway
4. **Shopify Partners setup:** Register app, configure OAuth redirect URL, set GDPR webhook URLs
5. **Frontend deployment:** Deploy tabbed layout + Pages tab. "Connect Shopify" button will show but OAuth won't work until Partners app is configured.
6. **Rollback:** Drop `shopify_pages` table, remove Shopify columns from `projects`. No data dependencies — existing crawl workflow is completely unchanged.

## Open Questions

- Should we also pull Shopify metafields for pages (could be useful for SEO metadata)? Starting without, can add later.
- Should the "Connect Shopify" option fully replace the manual URL paste step, or always offer both? Decision: offer both — some clients may not use Shopify.
