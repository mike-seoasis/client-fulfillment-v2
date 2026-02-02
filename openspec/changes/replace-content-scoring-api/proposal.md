## Why

Our current `ContentScoreService` is a homegrown implementation that calculates content quality using basic heuristics (word count, TF-IDF-like semantic analysis, Flesch readability, keyword density patterns). While functional, it lacks the accuracy and depth that comes from real SERP data and competitor analysis. PageOptimizer Pro (POP) is an established SEO tool that analyzes actual search results, giving us competitor-informed targets rather than arbitrary thresholds.

## What Changes

- **BREAKING**: Replace `ContentScoreService` with a new `POPContentScoreService` that integrates with the PageOptimizer Pro API
- Add async task polling pattern (POP uses create-task → poll-for-results workflow)
- Store POP API credentials in environment configuration
- Update API endpoints to use new service while maintaining response contract
- Remove the old `ContentScoreService` implementation after migration
- `ContentQualityService` (AI trope detection) remains unchanged

## Capabilities

### New Capabilities
- `pop-content-scoring`: Integration with PageOptimizer Pro API for SERP-based content scoring, including competitor analysis, LSI term recommendations, keyword density targets, word count targets, and page structure analysis

### Modified Capabilities
- None (the external interface/contract of content scoring stays the same; this is an implementation swap)

## Impact

**Code changes:**
- `backend/app/services/content_score.py` — replace implementation with POP API client
- `backend/app/api/v1/endpoints/` — update any endpoints that use ContentScoreService
- `backend/app/core/config.py` — add POP API key configuration
- `backend/tests/services/test_content_score.py` — update tests for new implementation

**Dependencies:**
- New external dependency: PageOptimizer Pro API (`app.pageoptimizer.pro`)
- API key required: `POP_API_KEY` environment variable

**API considerations:**
- POP API is async (create task, poll for results) — may need to handle in background or implement webhook
- Rate limits and API costs need to be understood before production use
- Response data is much richer than current implementation — decide what to surface vs. store

**Risk:**
- External API dependency introduces potential for downtime/latency
- Need fallback strategy if POP API is unavailable
