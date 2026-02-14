## Context

Phase 8 adds the second core workflow: **Keyword Cluster Creation**. Phases 1-7 built the onboarding flow (crawl existing pages → keywords → content → export). This phase lets users create **new** collection pages from scratch by entering a seed keyword and getting cluster suggestions.

The existing downstream pipeline (content generation, review, export) is fully shared — the only new work is the *upstream* part: discovering what pages to build, getting user approval, and bridging approved pages into the existing `CrawledPage`/`PageKeywords` data model.

Research was conducted by 3 independent agents exploring POP-first, LLM-first, and hybrid approaches. All three converged: POP has no keyword discovery API and should only be used downstream for content briefs. The recommended approach is a 5-stage funnel pipeline using LLM + DataForSEO for discovery, with POP downstream.

Full research reports: `.tmp/cluster-research-*.md` and `.tmp/cluster-research-consensus.md`.

### Current state

- `CrawledPage` model stores all pages (onboarding creates these from crawled URLs)
- `PageKeywords` model stores primary keywords per page (1:1 with CrawledPage)
- `PrimaryKeywordService` generates keywords from page content (onboarding-specific)
- Content pipeline (`ContentBrief` → `PageContent`) operates on `CrawledPage` records
- Project detail view has a disabled "New Content" section placeholder
- POP integration (`pop.py`, `pop_content_brief_service.py`) already supports `page_not_built_yet=True`
- DataForSEO integration (`dataforseo.py`) has `get_keyword_volume_batch()` and `get_keyword_suggestions()`

## Goals / Non-Goals

**Goals:**
- Users can enter a seed keyword and get 8-12 validated cluster page suggestions in ~5-10 seconds
- Suggestions include real search volume data, parent/child roles, and URL slugs
- Users can approve/reject/edit suggestions, then approved pages flow into the existing content pipeline unchanged
- The project dashboard shows clusters with status and page counts
- Total API cost for cluster creation (Stages 1-3) stays under $0.10

**Non-Goals:**
- Internal link mapping between cluster pages (deferred — separate phase)
- POP cannibalization check (skip for v1, revisit if users report issues)
- Cluster re-generation (editing seed keyword and re-running) — v1 is create-once
- DataForSEO keyword suggestions as supplementary source (toggleable future enhancement)
- Cluster analytics (total volume, estimated traffic) — Phase 10 polish

## Decisions

### D1: 5-stage funnel pipeline

**Decision:** Stages 1-3 (LLM expand → DataForSEO enrich → LLM filter) run synchronously on cluster creation. Stage 4 is user approval. Stage 5 (POP briefs → content pipeline) runs on bulk-approve.

**Why over alternatives:**
- POP-first was rejected: no keyword discovery API, 30-60s per call, $21+ credits per cluster, 10-20 min wait
- Pure LLM-first (no Stage 3 filter) was simpler but doesn't assign parent/child roles or catch cannibalization
- The funnel shape ensures expensive POP credits are only spent on user-approved keywords

### D2: 11-strategy expansion prompt

**Decision:** Stage 1 uses a structured prompt with 11 modifier strategies: demographic, attribute, price/value, use-case, comparison/intent, seasonal/occasion, material/type, experience level, problem/solution, terrain/environment, values/lifestyle.

**Why:** Forces diverse coverage across all collection page dimensions. Without structure, LLM over-indexes on attribute variations and misses demographics, price tiers, and problem-based keywords. Brand config context is injected to keep suggestions relevant to the actual brand.

### D3: Claude Haiku for Stages 1 and 3

**Decision:** Use Haiku 4.5 for both LLM calls (~$0.008 total). Sonnet is available as a fallback if quality is insufficient.

**Why:** Stage 1 is structured expansion (formulaic), Stage 3 is filtering with data (volume numbers guide decisions). Neither requires Sonnet-level reasoning. Cost difference is negligible ($0.008 vs $0.02) but Haiku is faster (~0.5s vs ~1.5s per call).

### D4: Bridge to existing pipeline via CrawledPage + PageKeywords

**Decision:** On bulk-approve, create a `CrawledPage` record (with `status=completed`, `source=cluster`, minimal content fields) and a `PageKeywords` record (with `is_approved=True`) for each approved cluster page. This lets the entire downstream pipeline work unchanged.

**Why over alternative (new ClusterContent model):**
- Zero changes to content generation, review, or export code
- All existing API endpoints, frontend pages, and TanStack Query hooks work for cluster pages
- The `CrawledPage` model already has nullable content fields — cluster pages just have less data populated
- A `source` field on CrawledPage (or tracked via the cluster FK) distinguishes origin

**Trade-off:** CrawledPage has crawl-specific fields (crawl_error, last_crawled_at, body_content) that are irrelevant for cluster pages. This is acceptable — nullable fields cost nothing, and the alternative (parallel model hierarchy) would require duplicating the entire downstream pipeline.

### D5: New `KeywordCluster` and `ClusterPage` models

**Decision:** Two new tables rather than storing cluster data as JSON on an existing model.

```
keyword_clusters
├── id (UUID PK)
├── project_id (FK → projects)
├── seed_keyword (String, not null)
├── name (String, not null, defaults to seed keyword)
├── status (String: generating, suggestions_ready, approved, content_generating, complete)
├── generation_metadata (JSONB — stage timings, costs, candidate counts)
├── created_at, updated_at

cluster_pages
├── id (UUID PK)
├── cluster_id (FK → keyword_clusters, cascade delete)
├── keyword (String, not null)
├── role (String: parent | child)
├── url_slug (String, not null)
├── expansion_strategy (String, nullable — which of 11 strategies)
├── reasoning (String, nullable — why this suggestion)
├── search_volume (Integer, nullable)
├── cpc (Float, nullable)
├── competition (Float, nullable)
├── competition_level (String, nullable)
├── composite_score (Float, nullable)
├── is_approved (Boolean, default false)
├── crawled_page_id (FK → crawled_pages, nullable — set on bulk-approve)
├── created_at, updated_at
```

**Why:** Proper relational model enables querying clusters by project, pages by cluster, and tracking approval status independently from the downstream CrawledPage records. JSONB would make these queries painful.

### D6: Synchronous Stages 1-3 (no background task)

**Decision:** The cluster creation endpoint runs Stages 1-3 inline and returns results in the response (~5-10 seconds).

**Why over background task + polling:**
- 5-10 seconds is acceptable for a synchronous HTTP response (frontend shows a loading spinner)
- Avoids the complexity of background task management, polling endpoints, and status tracking
- The onboarding flow uses background tasks because content generation takes minutes; cluster suggestion takes seconds

**Trade-off:** If DataForSEO is slow or Claude is under load, the request could take 15-20s. Mitigated by a 30s timeout on the endpoint with a graceful error message.

### D7: Volume threshold default of 50

**Decision:** Suggestions with `search_volume < 50` are filtered out by default. Configurable per-project in the future.

**Why 50 over alternatives:**
- 10 (too permissive): includes ultra-niche terms not worth building a collection page for
- 100 (too aggressive): filters out legitimate long-tail collection pages for niche brands
- 50 is a reasonable floor for "worth building a standalone collection page"

### D8: Max 10 suggestions returned, 15-20 generated

**Decision:** Stage 1 generates 15-20 candidates, Stage 3 filters to the best 8-12, UI shows up to 10 by default.

**Why:** Over-generate and filter compensates for LLM hallucination (some candidates will have zero volume). The 15→10 ratio gives ~33% buffer for filtering losses.

## Risks / Trade-offs

**[LLM suggests zero-volume keywords]** → DataForSEO volume gate in Stage 2 filters these out. Over-generating (15-20 candidates) provides buffer. If DataForSEO is unavailable, suggestions are returned without volume data and a warning is shown.

**[DataForSEO unavailable/slow]** → Graceful degradation: return LLM suggestions without volume data. User can still approve based on their own judgment. Volume column shows "N/A" in UI.

**[Keyword cannibalization between cluster pages]** → Stage 3 LLM prompt explicitly instructs filtering of near-duplicate keywords. For v1 this is sufficient. POP variation overlap analysis is a future enhancement if needed.

**[CrawledPage model accumulates cluster-irrelevant fields]** → Accepted trade-off. Nullable fields have no storage cost. The benefit of pipeline reuse far outweighs model purity concerns.

**[5-10s synchronous response feels slow]** → Frontend shows a multi-step progress indicator (Generating suggestions → Checking search volume → Finalizing results) to make the wait feel purposeful.

## Migration Plan

1. **Alembic migration:** Add `keyword_clusters` and `cluster_pages` tables. Add optional `source` column to `crawled_pages` (default `'onboarding'`, new cluster pages get `'cluster'`).
2. **No data migration needed** — new tables start empty, existing CrawledPage records get default `source='onboarding'`.
3. **Rollback:** Drop the two new tables and the `source` column. No downstream impact since no existing code depends on them.
4. **Deployment order:** Backend first (new endpoints are additive), frontend second (new pages, modified project detail).
