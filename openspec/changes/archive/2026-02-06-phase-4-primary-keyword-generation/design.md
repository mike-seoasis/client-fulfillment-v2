## Context

**Current State (after Phase 3):**
- CrawledPage records exist with: URL, title, headings, body_content, product_count, labels
- PageKeywords model exists but is not populated (has primary_keyword, secondary_keywords, search_volume, difficulty_score)
- DataForSEOClient integration is fully built with batch processing, circuit breaker, retry logic
- ClaudeClient integration exists for AI generation tasks
- Frontend has crawl progress page pattern with polling, inline editing, step indicators

**Constraints:**
- DataForSEO API: $0.05 per batch of up to 1000 keywords, ~7 second response time
- Claude API: Rate limits on concurrent requests, ~2-3 seconds per call
- Must not duplicate primary keywords across pages in same project
- User must approve all keywords before proceeding to Phase 5

**Stakeholders:**
- Operations team: Need efficient approval workflow, ability to override AI suggestions
- SEO strategy: Need accurate keyword targeting based on volume + relevance balance

## Goals / Non-Goals

**Goals:**
- Generate high-quality primary keyword candidates using AI analysis of page content
- Enrich candidates with real search volume and competition data
- Provide intelligent ranking that balances volume, relevance, and competition
- Enable users to quickly review, adjust, and approve keywords
- Track priority pages for internal linking in Phase 5
- Prevent duplicate primary keywords across pages

**Non-Goals:**
- Secondary keyword generation (POP API provides LSI terms in Phase 5)
- Keyword clustering or grouping (out of scope for MVP)
- Historical keyword tracking or rank monitoring
- Integration with Google Search Console (was in old code, not needed now)
- Automatic approval without human review

## Decisions

### 1. Scoring Formula: 50% Volume / 35% Relevance / 15% Competition

**Decision:** Use weighted composite score with volume as primary factor, relevance as strong secondary.

**Rationale:**
- Volume indicates search demand (most important for traffic potential)
- Relevance ensures we're targeting keywords that match the page (prevents generic terms)
- Competition is less important because we're optimizing existing pages (already have some authority)

**Alternatives Considered:**
- Pure volume ranking: Rejected - would select generic high-volume terms that don't match page
- Equal weighting: Rejected - relevance and competition aren't equally important
- Competition-first: Rejected - would select low-competition long-tails with no volume

**Formula:**
```python
score = (volume_score × 0.50) + (relevance_score × 0.35) + (competition_score × 0.15)

volume_score = min(50, max(0, log10(volume) × 10))  # 0-50 scale
relevance_score = llm_confidence × 100              # 0-100 from filter step
competition_score = (1 - competition) × 100         # 0-100, lower competition = higher score
```

### 2. Two-Step LLM Process: Generate Then Filter

**Decision:** Use two separate Claude calls - one to generate candidates, one to filter to specific keywords.

**Rationale:**
- Generation benefits from creativity (brainstorming many options)
- Filtering benefits from precision (strict specificity criteria)
- Separating allows different prompts optimized for each task
- Proven pattern from old keyword_research.py that produced good results

**Alternatives Considered:**
- Single LLM call for both: Rejected - conflicting objectives degrade quality
- LLM for generation only, rule-based filter: Rejected - specificity requires semantic understanding
- No LLM, use DataForSEO suggestions only: Rejected - suggestions don't account for page content

### 3. Store Top 5 Alternatives for User Selection

**Decision:** Save ranked alternatives in `alternative_keywords` JSON field, display as dropdown.

**Rationale:**
- Users may prefer a different keyword than the algorithm's top pick
- Avoids re-running expensive generation if user wants different option
- Provides transparency into what candidates were considered
- Quick selection without manual typing

**Alternatives Considered:**
- Store all 20 candidates: Rejected - UI clutter, most are filtered out anyway
- Store only primary: Rejected - no recourse if user disagrees with selection
- Re-generate on demand: Rejected - slow, expensive, inconsistent results

### 4. Background Task with Polling for Generation

**Decision:** Use FastAPI BackgroundTasks with 2-second polling interval, same pattern as crawling.

**Rationale:**
- Generation takes 5-15 seconds per page (LLM + API calls)
- Blocking request would timeout for large page sets
- Polling pattern already proven in Phase 3 crawl flow
- Enables progress tracking and cancellation

**Alternatives Considered:**
- WebSockets: Rejected - more complex, polling works fine for MVP
- Celery/Redis: Rejected - over-engineered for current scale
- Synchronous with long timeout: Rejected - poor UX, connection issues

### 5. Duplicate Prevention with Project-Scoped Lock

**Decision:** Track used primary keywords per project, skip duplicates during selection.

**Rationale:**
- Same keyword targeting multiple pages dilutes ranking potential
- Each page should have unique primary keyword
- Lock must be project-scoped (different projects can share keywords)

**Implementation:**
```python
# In PrimaryKeywordService
used_primaries: set[str] = set()  # Populated at start of batch

# During selection, skip if already used
candidates = [kw for kw in ranked if kw not in used_primaries]
primary = candidates[0]
used_primaries.add(primary)
```

### 6. Priority Flag on PageKeywords (Not CrawledPage)

**Decision:** Add `is_priority` boolean to PageKeywords model.

**Rationale:**
- Priority is a keyword/SEO concept, not a crawl concept
- Keeps CrawledPage focused on content extraction
- PageKeywords already has the primary keyword context
- Internal linking (Phase 5) queries PageKeywords anyway

### 7. Use Existing DataForSEOClient, No New Integration

**Decision:** Reuse `backend/app/integrations/dataforseo.py` as-is.

**Rationale:**
- Already has `get_keyword_volume_batch()` with all features needed
- Circuit breaker, retry logic, logging already implemented
- Returns `competition` field (0-1 scale) perfect for scoring
- Tested and production-ready

## Risks / Trade-offs

**[Risk] DataForSEO API unavailable or rate limited**
→ Mitigation: Circuit breaker prevents cascade failures. Fallback: Skip volume enrichment, use relevance-only scoring, flag for retry.

**[Risk] Claude generates low-quality or off-topic keywords**
→ Mitigation: Category-specific prompts (collection pages get e-commerce guidance). Fallback: Use title/H1 as candidates if generation fails.

**[Risk] Scoring formula produces unexpected rankings**
→ Mitigation: Store all scores in DB for debugging. Show score breakdown in UI. User can override via alternative selection.

**[Risk] Large projects (100+ pages) take too long**
→ Mitigation: Parallel LLM calls (max 8 concurrent). Batch DataForSEO requests (1000 keywords per call). Show per-page progress.

**[Trade-off] Two LLM calls per page increases cost**
→ Accepted: Quality improvement justifies ~$0.002/page additional cost. Could optimize later by caching common patterns.

**[Trade-off] Storing only top 5 alternatives limits options**
→ Accepted: 5 covers vast majority of cases. User can manually edit for edge cases.

## Migration Plan

**Database Migration:**
1. Add columns to `page_keywords` table:
   - `is_approved: Boolean, default=False`
   - `is_priority: Boolean, default=False`
   - `alternative_keywords: JSONB, default=[]`
   - `composite_score: Float, nullable`
   - `relevance_score: Float, nullable`
   - `ai_reasoning: Text, nullable`

2. Add foreign key relationship from `crawled_pages` to `page_keywords` if not exists

**Rollback Strategy:**
- Migration is additive (new columns only), no data loss on rollback
- Feature flag not needed - new endpoints only used by new UI
- If issues: Simply don't navigate to keywords step in UI

## Open Questions

1. **Volume threshold for filtering?** Should we exclude keywords with <10 monthly searches, or let scoring handle it naturally?
   - *Tentative answer:* Let scoring handle it. Zero-volume keywords will score low anyway.

2. **Confidence threshold for LLM filter?** If Claude is <50% confident a keyword is specific, should we exclude it?
   - *Tentative answer:* Include but lower its relevance_score. Let composite score decide.

3. **What if all candidates are filtered out?** Fall back to highest volume unfiltered keyword?
   - *Tentative answer:* Yes, use title-based keyword as ultimate fallback.
