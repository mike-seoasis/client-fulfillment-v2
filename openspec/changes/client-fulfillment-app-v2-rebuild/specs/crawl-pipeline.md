# Spec: crawl-pipeline

## Overview

Site crawling with configurable patterns, URL discovery, and metadata extraction. Uses crawl4ai for async crawling with priority queue management, concurrent request handling, and intelligent URL normalization.

## Key Logic from Existing Implementation

The existing crawler uses sophisticated logic that MUST be preserved:

1. **Priority Queue**: Homepage gets priority 0, URLs matching include patterns get priority 1, all others get priority 2
2. **URL Normalization**: Strips fragments, normalizes trailing slashes, handles query params consistently
3. **Deduplication**: By normalized path to avoid crawling same page with different query params
4. **Concurrent Crawling**: Default 5 concurrent requests with configurable delay between requests
5. **Include/Exclude Patterns**: Regex-based URL filtering (e.g., `/collections/`, exclude `/products/`)

## Data Model

### CrawledPage Entity

```
CrawledPage:
  id: UUID (primary key)
  project_id: UUID (foreign key)
  url: string (normalized, unique per project)
  title: string (from <title> tag)
  h1: string (from first <h1>)
  meta_description: string
  content_text: string (extracted body text)
  word_count: integer
  links_found: JSON array of discovered URLs
  crawled_at: datetime
  status: "success" | "failed" | "skipped"
  error_message: string | null
```

## Behaviors

### WHEN starting a crawl
- THEN validate project exists
- AND set phase status to "in_progress"
- AND initialize priority queue with homepage at priority 0
- AND begin async crawl loop

### WHEN processing URL queue
- THEN pop highest priority URL (lowest number)
- AND skip if URL already crawled (by normalized path)
- AND skip if URL matches exclude patterns
- AND fetch page content via crawl4ai
- AND extract metadata (title, h1, meta description, body text)
- AND discover new URLs from page links
- AND add new URLs to queue with appropriate priority

### WHEN normalizing URLs
- THEN strip URL fragments (#section)
- AND normalize trailing slashes (remove from non-root paths)
- AND preserve meaningful query params only
- AND convert to lowercase for comparison
- AND resolve relative URLs to absolute

### WHEN applying include/exclude patterns
- THEN include patterns are regex patterns (e.g., `collections`, `pages`)
- AND exclude patterns are regex patterns (e.g., `products`, `account`, `cart`)
- AND a URL is crawled only if it matches at least one include pattern
- AND a URL is skipped if it matches any exclude pattern
- AND exclude patterns take precedence over include patterns

### WHEN assigning URL priority
- THEN homepage (exact match to website_url) gets priority 0
- AND URLs matching include patterns get priority 1
- AND all other discovered URLs get priority 2
- AND within same priority, process in discovery order (FIFO)

### WHEN crawl completes
- THEN set phase status to "completed" with page count
- AND calculate and store crawl statistics
- AND broadcast completion via WebSocket

### WHEN crawl fails
- THEN set phase status to "failed" with error message
- AND preserve any pages successfully crawled
- AND log detailed error for debugging

### WHEN running in fetch-only mode
- THEN accept a list of specific URLs to crawl
- AND skip URL discovery (no following links)
- AND process only the provided URLs
- AND useful for re-crawling specific pages

## Configuration Options

```
CrawlConfig:
  max_pages: integer (default 200, max 1000)
  include_patterns: string (comma-separated regex patterns)
  exclude_patterns: string (comma-separated regex patterns)
  max_concurrent: integer (default 5)
  delay_seconds: float (default 0.5)
  fetch_only_urls: string[] | null (for fetch-only mode)
  respect_robots_txt: boolean (default true)
```

## Default Patterns

### Include (Shopify sites)
```
/collections/
/pages/
```

### Exclude (common non-content pages)
```
/products/
/account/
/cart/
/checkout/
/policies/
/apps/
```

## API Endpoints

```
POST /api/v1/projects/{id}/phases/crawl/run     - Start crawl
GET  /api/v1/projects/{id}/phases/crawl/status  - Get crawl status
GET  /api/v1/projects/{id}/pages                - List crawled pages
GET  /api/v1/projects/{id}/pages/{pageId}       - Get single page
```

## Progress Tracking

Progress percentage calculation:
```
progress = (pages_crawled / estimated_total) * 100
```

Where estimated_total starts at max_pages and adjusts based on queue size.

## Error Handling

- Connection timeout: Retry up to 3 times with exponential backoff
- 404 response: Mark page as "skipped", continue crawling
- 500 response: Mark page as "failed", continue crawling
- Rate limiting (429): Pause crawl, increase delay, retry
- Robot.txt blocked: Skip URL, log as "skipped"

## Database Schema

```sql
CREATE TABLE crawled_pages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  url VARCHAR(2000) NOT NULL,
  normalized_url VARCHAR(2000) NOT NULL,
  title VARCHAR(500),
  h1 VARCHAR(500),
  meta_description TEXT,
  content_text TEXT,
  word_count INTEGER,
  links_found JSONB DEFAULT '[]',
  crawled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  status VARCHAR(20) DEFAULT 'success',
  error_message TEXT,
  UNIQUE(project_id, normalized_url)
);

CREATE INDEX idx_crawled_pages_project ON crawled_pages(project_id);
CREATE INDEX idx_crawled_pages_status ON crawled_pages(project_id, status);
```
