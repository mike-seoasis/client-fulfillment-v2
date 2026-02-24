## Context

Phase 3 of the v2 rebuild. We have:
- Project model with `phase_status` JSONB for workflow tracking
- `CrawledPage` model already exists with `labels` JSONB field
- `Crawl4AIClient` integration ready with circuit breaker, retry logic, batch crawling
- Claude integration for AI operations
- FastAPI BackgroundTasks for async processing

Users need to upload collection page URLs and have them crawled before keyword generation (Phase 4).

## Goals / Non-Goals

**Goals:**
- Accept URLs via paste (one per line) or CSV upload
- Validate URLs and show preview before starting
- Crawl pages and extract structured data (title, meta, content, headings)
- Generate project-wide label taxonomy after all pages crawled
- Assign 2-5 labels from taxonomy to each page
- Show real-time progress and per-URL status
- Store crawl results for Phase 4 (keyword generation)

**Non-Goals:**
- Automatic re-crawling or scheduling (later feature)
- Deep site crawling/spidering (user provides explicit URLs)
- JavaScript rendering beyond what Crawl4AI provides
- Label suggestions during crawling (taxonomy comes after)

## Decisions

### 1. URL Validation Strategy

**Decision:** Client-side format validation + server-side accessibility check

- Frontend validates URL format (must be valid URL, must be HTTP/HTTPS)
- Frontend de-duplicates and normalizes URLs (lowercase, trailing slash handling)
- Backend validates URLs belong to project's `site_url` domain (optional, warn only)
- Accessibility checked during actual crawl (not pre-flight)
- No artificial URL count limits—process all URLs provided

**Alternatives considered:**
- Pre-flight HEAD requests: Adds latency, URLs might be accessible later
- No validation: Poor UX, wasted crawl attempts

### 2. Crawl Pipeline Architecture

**Decision:** FastAPI BackgroundTasks with polling

Per project decisions doc, we use BackgroundTasks + polling (2-3s) rather than WebSockets.

Flow:
1. POST `/projects/{id}/urls` → Creates `CrawledPage` records with status `pending`
2. Starts BackgroundTask that crawls pages sequentially
3. Frontend polls `GET /projects/{id}/crawl-status` every 2s
4. Each page: `pending` → `crawling` → `completed` or `failed`
5. After all crawled: trigger taxonomy generation

**Why parallel with concurrency limit:**
- Speed is critical for UX (don't make users wait)
- Use `asyncio.Semaphore` to limit concurrent requests (default: 5)
- Each page crawls independently, failures don't block others
- Crawl4AI's `crawl_many` can batch if supported, otherwise parallel single calls

**Concurrency strategy:**
```python
semaphore = asyncio.Semaphore(settings.crawl_concurrency)  # Default: 5
async def crawl_with_limit(url):
    async with semaphore:
        return await crawl4ai.crawl(url)

results = await asyncio.gather(*[crawl_with_limit(url) for url in urls])
```

Concurrency configurable via `CRAWL_CONCURRENCY` env var (default 5, can increase if Crawl4AI allows).

**Alternatives considered:**
- Sequential crawling: Too slow for 50+ URLs, poor UX
- Celery: Overkill for MVP, adds infrastructure complexity
- WebSockets: More complex, polling is sufficient UX
- Unlimited parallel: Would hit rate limits, overwhelm Crawl4AI

### 3. CrawledPage Model Extensions

**Decision:** Add fields to existing `CrawledPage` model

New fields needed:
- `status`: enum (`pending`, `crawling`, `completed`, `failed`)
- `meta_description`: extracted from page
- `body_content`: main content text (truncated if large)
- `headings`: JSONB `{h1: [...], h2: [...], h3: [...]}`
- `product_count`: integer (extracted from Shopify collection if applicable)
- `crawl_error`: error message if failed
- `word_count`: content word count

Existing fields we'll use:
- `normalized_url`, `raw_url`: URL tracking
- `title`: page title
- `labels`: assigned from taxonomy
- `content_hash`: for future re-crawl detection
- `last_crawled_at`: timestamp

### 4. Label Taxonomy Design

**Decision:** Two-phase labeling stored in Project `phase_status`

Phase 1: Taxonomy Generation (after all pages crawled)
- Claude analyzes all page titles/content together
- Generates 10-30 project-wide labels (e.g., "running", "women", "trail", "waterproof", "lightweight")
- Stored in `Project.phase_status.onboarding.taxonomy`

Phase 2: Label Assignment
- Claude assigns 2-5 labels per page from taxonomy
- Stored in `CrawledPage.labels` as array of strings
- User can edit assignments (frontend picks from taxonomy dropdown)

**Taxonomy storage:**
```json
{
  "onboarding": {
    "status": "labeling",
    "taxonomy": {
      "labels": ["running", "women", "men", "trail", "road", "waterproof", "lightweight"],
      "generated_at": "2024-02-04T10:00:00Z"
    },
    "crawl": {
      "total": 12,
      "completed": 12,
      "failed": 0
    }
  }
}
```

**Alternatives considered:**
- Separate `LabelTaxonomy` model: Over-engineering, taxonomy is project-scoped and simple
- Labels as separate table with FK: Complicates queries, JSONB array is simpler

### 5. Content Extraction Strategy

**Decision:** Use Crawl4AI markdown + custom extraction

- Crawl4AI returns `markdown` (cleaned content) and `html`
- Extract from HTML: `<title>`, `<meta name="description">`, heading structure
- Use markdown for `body_content` (already cleaned)
- Count products by parsing collection JSON or counting product cards

**Extraction targets:**
| Field | Source | Method |
|-------|--------|--------|
| title | `<title>` tag | BeautifulSoup |
| meta_description | `<meta name="description">` | BeautifulSoup |
| headings | H1/H2/H3 tags | BeautifulSoup |
| body_content | Crawl4AI markdown | Direct from API |
| product_count | Collection JSON or product grid | Regex/BeautifulSoup |

### 6. API Design

**Endpoints:**

```
POST /api/v1/projects/{project_id}/urls
  Body: { urls: string[] }
  → Creates CrawledPage records, starts background crawl
  → Returns: { task_id, pages_created: number }

GET /api/v1/projects/{project_id}/crawl-status
  → Returns: { status, progress: {total, completed, failed}, pages: [...] }

GET /api/v1/projects/{project_id}/pages
  → Returns: List of CrawledPage with labels

GET /api/v1/projects/{project_id}/taxonomy
  → Returns: { labels: string[], generated_at }

PUT /api/v1/projects/{project_id}/pages/{page_id}/labels
  Body: { labels: string[] }
  → Updates page labels (must be from taxonomy)
```

### 7. Frontend Routing

**Decision:** Nested routes under project onboarding

```
/projects/[id]/onboarding          → Redirects to appropriate step
/projects/[id]/onboarding/upload   → URL upload interface
/projects/[id]/onboarding/crawl    → Crawl progress + results
/projects/[id]/onboarding/labels   → Review/edit label assignments
```

Progress stepper shows: Upload → Crawl → Labels → Keywords → Content → Export

## Risks / Trade-offs

**Risk:** Crawl4AI rate limits or failures during batch crawl
→ Mitigation: Sequential crawling with per-page error handling, circuit breaker, retry logic already in client

**Risk:** Taxonomy generation produces inconsistent labels
→ Mitigation: Structured Claude prompt with examples, limit to 10-30 labels, user can edit taxonomy before assignment

**Risk:** Large pages exceed content storage limits
→ Mitigation: Truncate `body_content` to 50KB, store `word_count` for reference

**Risk:** User uploads hundreds of URLs
→ Mitigation: Parallel crawling with concurrency limit (5) keeps total time reasonable. Show progress clearly so user knows it's working.

**Trade-off:** Labels stored as strings in JSONB vs normalized table
→ Accepted: Simpler queries, label consistency enforced at application layer via taxonomy
