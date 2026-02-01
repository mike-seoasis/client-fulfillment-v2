# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Redis Caching Pattern
- Use `app/core/redis.py` RedisManager for all Redis operations - it handles circuit breaker, connection pooling, SSL/TLS
- Create domain-specific cache services (e.g., `serp_cache.py`, `keyword_cache.py`) that wrap RedisManager
- Cache services follow singleton pattern with `get_*_service()` factory functions
- Cache key format: `{prefix}:{dimension1}:{dimension2}:...:{identifier}`
- Always handle graceful degradation when Redis is unavailable
- Use dataclasses for cached data structures with `cached_at` timestamp

### DataForSEO Integration Pattern
- The client at `app/integrations/dataforseo.py` has its own circuit breaker
- Add `*_cached` methods to integrations that need caching (checks cache first, then API)
- Import cache services inside methods to avoid circular imports

### PAA Fan-Out Pattern
- Use `PAAEnrichmentService` for PAA discovery with optional fan-out
- Fan-out searches initial PAA questions for nested questions (controlled by `fanout_enabled`, `max_fanout_questions`)
- Rate-limit concurrent fan-out with `max_concurrent_fanout` (default 5)
- Use `enrich_keyword_paa_cached()` for cache-aware PAA enrichment (24h TTL)
- Questions are de-duplicated using normalized text (lowercase, stripped)
- Falls back to Related Searches (with LLM semantic filter) when PAA results are insufficient (`fallback_enabled`, `min_paa_for_fallback=3`)

### Related Searches Fallback Pattern
- Use `RelatedSearchesService` for extracting "related searches" from DataForSEO SERP response
- Related searches are extracted from items with `type="related_searches"`
- Apply LLM semantic filter via Claude to assess relevance and convert to question format
- Filter threshold: `min_relevance_score=0.6` (scale 0.0-1.0)
- Cache filtered results with 24h TTL (same as PAA/SERP caching)
- Gracefully degrades if LLM filter fails (returns raw results)
- Question conversion: uses LLM question_form or simple heuristic conversion

---

## 2026-02-01 - client-onboarding-v2-c3y.57
- What was implemented:
  - Created SERP result caching service (`app/services/serp_cache.py`)
  - Added `get_serp_cached()` method to DataForSEO client for cache-aware SERP lookups
  - 24-hour TTL for cached SERP results
  - Redis-based caching with graceful degradation when Redis is unavailable

- Files changed:
  - `backend/app/services/serp_cache.py` (new)
  - `backend/app/integrations/dataforseo.py` (modified)

- **Learnings:**
  - Pattern: Domain-specific caching services that wrap the core redis_manager
  - Cache key uses SHA256 hash of normalized keyword to handle long/special character keywords
  - Existing Redis infrastructure already has circuit breaker, SSL/TLS, and connection retry logic
  - Import cache services inside methods to avoid circular imports when cache depends on domain types
  - The mypy errors in core modules are pre-existing (config.py requires database_url, logging imports issue)
---

## 2026-02-01 - client-onboarding-v2-c3y.58
- What was implemented:
  - Created PAA enrichment service (`app/services/paa_enrichment.py`) with fan-out strategy
  - Created PAA cache service (`app/services/paa_cache.py`) with 24h TTL
  - Fan-out strategy: searches initial PAA questions for nested questions
  - Uses DataForSEO SERP Advanced endpoint with `people_also_ask_click_depth` parameter (1-4)
  - Supports rate-limited concurrent fan-out with configurable max_concurrent_fanout
  - De-duplicates questions using normalized question text
  - Comprehensive logging per error logging requirements

- Files changed:
  - `backend/app/services/paa_enrichment.py` (new)
  - `backend/app/services/paa_cache.py` (new)

- **Learnings:**
  - DataForSEO SERP Advanced endpoint (`/v3/serp/google/organic/live/advanced`) supports PAA click depth
  - `people_also_ask_click_depth` param (1-4) expands PAA questions, costs $0.00015 extra per click
  - PAA items in SERP response have type `people_also_ask` with nested `people_also_ask_element` items
  - Expanded elements can be `people_also_ask_expanded_element` (standard) or `people_also_ask_ai_overview_expanded_element` (AI-generated)
  - Fan-out strategy limits to first N questions to control API costs
  - Question deduplication uses normalized (lowercase, stripped, no trailing ?) comparison
---

## 2026-02-01 - client-onboarding-v2-c3y.59
- What was implemented:
  - Created Related Searches service (`app/services/related_searches.py`) with LLM semantic filter
  - Extracts `related_searches` items from DataForSEO SERP Advanced endpoint
  - Uses Claude LLM to evaluate semantic relevance of related searches (0.0-1.0 score)
  - LLM converts related searches to natural question format
  - Integrated as fallback in PAA enrichment when fewer than 3 PAA questions found
  - 24h TTL caching for related searches results
  - Comprehensive logging per error logging requirements

- Files changed:
  - `backend/app/services/related_searches.py` (new)
  - `backend/app/services/paa_enrichment.py` (modified - added fallback integration)

- **Learnings:**
  - Related searches in SERP have `type="related_searches"` with nested `items` array
  - Each item has a `title` field containing the search term
  - LLM semantic filter prompt should include: original keyword context, relevance score request, question conversion
  - Claude `complete()` method works well for structured JSON responses with `temperature=0.0`
  - Variable scoping in Python: must be careful when same variable name used in try/except blocks and conditional blocks (mypy catches this with `no-redef`)
  - Fallback triggers when `len(all_questions) < min_paa_for_fallback` (default 3)
  - Question conversion heuristic: detect existing question starters, else wrap with "What is/are"
---

