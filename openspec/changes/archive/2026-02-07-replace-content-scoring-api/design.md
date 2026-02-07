## Context

**Current state:**
- `ContentScoreService` calculates content quality using homegrown heuristics (word count, TF-IDF semantic analysis, Flesch readability, keyword density, entity patterns)
- PAA enrichment uses DataForSEO SERP API with fan-out strategy and LLM intent categorization
- These are separate systems with different data sources and no competitor awareness

**Target state:**
- Integrate PageOptimizer Pro (POP) API for SERP-based content guidance
- Two API calls per content piece: (1) content brief before writing, (2) scoring after generation
- POP provides competitor-derived targets rather than arbitrary thresholds
- Potential consolidation: POP's `relatedQuestions` could replace DataForSEO PAA fetch

**Constraints:**
- POP API is async (create task → poll for results)
- External dependency introduces latency and failure modes
- Must maintain backwards compatibility during migration
- API costs need monitoring

## Goals / Non-Goals

**Goals:**
- Replace `ContentScoreService` with POP-based scoring
- Add new Content Brief phase that fetches SERP-based targets before content generation
- Create reusable POP API client following existing integration patterns
- Handle async task polling gracefully
- Provide fallback when POP is unavailable

**Non-Goals:**
- Replacing `ContentQualityService` (AI trope detection) — out of scope
- Building a POP dashboard/UI — just API integration
- Real-time POP data sync — batch/on-demand only
- Fully replacing DataForSEO PAA in this change — evaluate feasibility only

## Decisions

### 1. Integration architecture

**Decision:** Create `app/integrations/pop.py` following the DataForSEO client pattern.

**Rationale:** Existing integrations (DataForSEO, Claude, Crawl4AI) use a consistent pattern:
- Async httpx client
- Circuit breaker for fault tolerance
- Retry with exponential backoff
- Credential masking in logs
- Factory function for dependency injection

**Alternatives considered:**
- Inline API calls in services → rejected (violates separation of concerns)
- Third-party SDK → rejected (none exists, and direct HTTP is simpler)

### 2. Async task polling strategy

**Decision:** Implement polling loop in the integration client with configurable timeout and interval.

```
create_task() → task_id
poll_task(task_id) → result | pending
```

Poll every 2-3 seconds, timeout after 5 minutes (matching Railway's request limit).

**Rationale:** POP API requires polling; we can't change that. Encapsulating polling in the client keeps services simple.

**Alternatives considered:**
- Webhooks → POP doesn't support them
- Background job with callback → adds complexity, polling is simpler for MVP

### 3. Service structure

**Decision:** Two new services, one deprecated:

| Service | Purpose |
|---------|---------|
| `POPContentBriefService` | Fetch content targets (word count, headings, keywords, LSI terms, entities, PAA) |
| `POPContentScoreService` | Score generated content against targets |
| `ContentScoreService` | **Deprecated** — keep during migration, remove after validation |

**Rationale:** Separating brief and scoring follows single responsibility. The old service stays for A/B comparison during rollout.

### 4. Data model for content brief

**Decision:** Store POP brief response in a new `content_briefs` table, linked to the page/keyword.

Fields:
- `id`, `page_id`, `keyword`, `created_at`
- `pop_task_id` — for reference/debugging
- `word_count_target`, `word_count_min`, `word_count_max`
- `heading_targets` — JSON (H1, H2, H3, H4 counts)
- `keyword_targets` — JSON (by section: title, headings, paragraphs)
- `lsi_terms` — JSON array with weights and target counts
- `entities` — JSON array from Google NLP analysis
- `related_questions` — JSON array (PAA data)
- `related_searches` — JSON array
- `competitors` — JSON array (URLs, scores)
- `page_score_target` — target score to achieve
- `raw_response` — full POP response for debugging

**Rationale:** Structured fields for frequently accessed data, JSON for complex nested structures. Keeps raw response for debugging without parsing everything upfront.

### 5. PAA enrichment strategy

**Decision:** Keep DataForSEO PAA for now, but extract POP's `relatedQuestions` into the content brief for comparison.

**Rationale:**
- POP's PAA data comes "for free" with the content brief call
- Intent categorization (LLM) still needs to run regardless of source
- Can compare quality/coverage before deciding to deprecate DataForSEO
- Lower risk — don't break existing PAA workflow

**Migration path:**
1. Store POP PAA alongside DataForSEO PAA
2. Compare coverage and quality in production
3. If POP is sufficient, deprecate DataForSEO PAA fetch in future change

### 6. Fallback strategy

**Decision:** If POP API fails, fall back to `ContentScoreService` (homegrown) with a warning flag.

**Rationale:** Better to score with lower-quality data than to block the workflow entirely. UI can show "scored with fallback" indicator.

**Implementation:**
- Circuit breaker opens after N failures
- When open, automatically use fallback
- Log all fallbacks for monitoring

### 7. Configuration

**Decision:** Add to `app/core/config.py`:

```python
# PageOptimizer Pro
pop_api_key: str | None = Field(default=None, description="POP API key")
pop_api_url: str = Field(default="https://app.pageoptimizer.pro/api", description="POP API base URL")
pop_task_poll_interval: float = Field(default=3.0, description="Seconds between poll attempts")
pop_task_timeout: float = Field(default=300.0, description="Max seconds to wait for task completion")
pop_circuit_failure_threshold: int = Field(default=5, description="Failures before circuit opens")
pop_circuit_recovery_timeout: float = Field(default=60.0, description="Seconds before recovery attempt")
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| POP API downtime blocks content workflow | Fallback to `ContentScoreService`; circuit breaker prevents cascading failures |
| Polling adds latency (could be 30-60s for POP to analyze) | Run brief fetch as background task after keyword approval; content generation waits for brief |
| API costs unpredictable | Add cost logging per request; set up alerts; consider caching briefs |
| POP response schema changes | Store `raw_response`; version the parser; graceful degradation on parse errors |
| Two API calls per content piece doubles cost | Brief call is mandatory; scoring call could be optional (run only on final review) |

## Migration Plan

**Phase 1: Integration client (no production impact)**
- Create `app/integrations/pop.py`
- Add config settings
- Write integration tests with mocked responses

**Phase 2: Content Brief service**
- Create `POPContentBriefService`
- Create `content_briefs` table and model
- Add API endpoint (not wired into workflow yet)
- Test in isolation

**Phase 3: Wire into workflow**
- Add Content Brief phase after keyword approval
- Modify content generation to consume brief data
- Feature flag for gradual rollout

**Phase 4: Content Scoring service**
- Create `POPContentScoreService`
- Run in parallel with `ContentScoreService` (shadow mode)
- Compare results, tune thresholds

**Phase 5: Cutover**
- Switch to POP scoring as primary
- Keep fallback to old service
- Monitor for regressions

**Rollback:** Feature flags allow instant rollback to previous behavior at each phase.

## Open Questions

1. **POP API rate limits and pricing** — Need to confirm with POP; impacts batch processing strategy
2. **Brief caching duration** — How long is a brief valid? SERP data changes; should we refresh daily/weekly?
3. **Minimum page score threshold** — What score should content achieve to "pass"? Need to calibrate against current thresholds
4. **PAA quality comparison** — Need production data to compare POP vs DataForSEO PAA before deprecating
