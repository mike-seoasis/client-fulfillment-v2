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

