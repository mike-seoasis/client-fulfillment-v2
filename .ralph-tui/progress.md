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

