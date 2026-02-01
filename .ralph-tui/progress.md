# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### API Endpoint Pattern
- Endpoints use `_get_request_id(request)` helper to extract request ID from request state
- Use `_verify_project_exists()` helper to check project exists before processing
- Return structured error responses: `{"error": str, "code": str, "request_id": str}`
- Log at DEBUG for request details, INFO for completion, WARNING for 4xx, ERROR for 5xx
- All responses include `request_id` for debugging

### Page Data Access Pattern
For operations involving page data:
1. Query `CrawledPage` by ID and project_id
2. Query `PageKeywords` by crawled_page_id for keyword info
3. Page category maps to content_type (e.g., "collection", "product")
4. URL comes from `page.normalized_url`, keyword from `keywords.primary_keyword`

### Batch Operation Pattern
- Fetch all records in bulk with `select().where().in_(ids)`
- Build a dict mapping ID to record for O(1) lookups
- Track failed items separately from successful ones
- Return both individual results and aggregate statistics

---

## 2026-02-01 - client-onboarding-v2-c3y.86
- What was implemented:
  - Added regeneration endpoint for failed pages: `POST /regenerate` (single) and `POST /regenerate_batch` (batch)
  - Endpoints retrieve page and keyword data, then use existing content generation service
  - Follows same patterns as existing generate/batch endpoints
- Files changed:
  - `backend/app/schemas/content_generation.py` - Added Regenerate* request/response schemas
  - `backend/app/api/v1/endpoints/content_generation.py` - Added regenerate endpoints and `_get_page_data` helper
- **Learnings:**
  - Patterns discovered: Page data is split across CrawledPage (URL, category) and PageKeywords (primary_keyword)
  - Gotchas: mypy needs type assertions after conditional returns to narrow union types
  - Bulk queries should use `.in_()` for page IDs, then build dict for fast lookup
---

