## Why

After crawling collection pages (Phase 3), we need to identify the optimal primary keyword for each page before content generation can begin. The primary keyword drives the POP API content brief in Phase 5, which provides LSI terms, related questions, and optimization targets. Without accurate primary keywords, content generation will target the wrong search intent.

## What Changes

**Keyword Generation Pipeline:**
- Generate 20-25 keyword candidates per page using Claude (analyzes URL, title, headings, content, product count)
- Enrich all candidates with DataForSEO data (search volume, CPC, competition score)
- Filter to page-specific keywords using second Claude call (removes generic category terms)
- Score and rank using weighted formula: 50% volume + 35% relevance + 15% competition
- Select best keyword as primary, store top 5 as alternatives for user selection

**Approval Interface:**
- New keywords page in onboarding flow (Step 3 of 5)
- Display primary keyword with score breakdown and search volume
- Dropdown to select from alternative keywords
- Priority toggle for pages that should receive more internal links
- Individual approve and bulk "Approve All" actions
- Inline editing to manually change keywords

**Data Model Updates:**
- Add approval status, priority flag, and alternative keywords to PageKeywords model
- Add composite score and relevance score fields
- Establish relationship between CrawledPage and PageKeywords

## Capabilities

### New Capabilities
- `primary-keyword-generation`: Service that generates, enriches, filters, and scores keyword candidates for crawled pages. Uses Claude for generation/filtering, DataForSEO for volume data, and scoring algorithm for ranking.
- `keyword-approval-ui`: Frontend interface for reviewing, selecting, and approving primary keywords. Includes alternative keyword selection, priority marking, and bulk approval.

### Modified Capabilities
- `page-keywords`: Add fields for `is_approved`, `is_priority`, `alternative_keywords` (JSON), `composite_score`, `relevance_score`, `ai_reasoning`. Add relationship from CrawledPage.

## Impact

**Backend:**
- New migration: Add fields to `page_keywords` table
- New service: `PrimaryKeywordService` in `backend/app/services/`
- New API endpoints in `backend/app/api/v1/projects.py`:
  - `POST /projects/{id}/generate-primary-keywords` (background task)
  - `GET /projects/{id}/primary-keywords-status` (polling)
  - `GET /projects/{id}/pages-with-keywords` (list view)
  - `PUT /projects/{id}/pages/{page_id}/primary-keyword` (edit)
  - `POST /projects/{id}/pages/{page_id}/approve-keyword` (approve single)
  - `POST /projects/{id}/approve-all-keywords` (bulk approve)
  - `PUT /projects/{id}/pages/{page_id}/priority` (toggle priority)
- Uses existing `DataForSEOClient` integration

**Frontend:**
- New page: `frontend/src/app/projects/[id]/onboarding/keywords/page.tsx`
- New components for keyword display, alternative selection, priority toggle
- TanStack Query hooks for polling and mutations
- Step indicator updates (Step 3 of 5: Keywords)

**Dependencies:**
- Requires Phase 3 complete (crawled pages with content)
- Unlocks Phase 5 (content generation with POP API)
- DataForSEO API credentials required (`DATAFORSEO_API_LOGIN`, `DATAFORSEO_API_PASSWORD`)

**Cost Implications:**
- Claude API: ~2 calls per page (generate + filter)
- DataForSEO: ~$0.05 per batch of 1000 keywords (20-25 keywords × pages)
