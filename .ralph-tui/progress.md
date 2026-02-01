# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Redis Caching Pattern
- Use `redis_manager` singleton from `app.core.redis` for all Redis operations
- All Redis operations go through circuit breaker protection via `redis_manager.execute()`
- Check `redis_manager.available` before attempting cache operations
- Return graceful fallback when Redis unavailable (cache is optional)
- TTL in seconds via `ex` parameter on `redis_manager.set()`
- Use `redis_logger` from `app.core.logging` for Redis-specific logging

### Service Singleton Pattern
```python
_service_instance: ServiceClass | None = None

def get_service_instance() -> ServiceClass:
    global _service_instance
    if _service_instance is None:
        _service_instance = ServiceClass()
        logger.info("Service singleton created")
    return _service_instance
```

### Cache Key Pattern
```python
def _hash_keyword(self, keyword: str) -> str:
    normalized = keyword.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]

def _build_cache_key(self, keyword: str, **params) -> str:
    keyword_hash = self._hash_keyword(keyword)
    return f"{CACHE_KEY_PREFIX}{engine}:{location}:{language}:{keyword_hash}"
```

---

## 2026-02-01 - client-onboarding-v2-c3y.57
- What was implemented: SERP result caching in Redis with 24h TTL - **ALREADY COMPLETE**
- Files changed: None (implementation was already present)
- Existing implementation verified:
  - `backend/app/services/serp_cache.py` - SerpCacheService with get/set/delete/get_ttl methods
  - `backend/app/core/redis.py` - RedisManager with circuit breaker, SSL/TLS, retry logic
  - `backend/app/core/config.py` - Redis configuration via REDIS_URL env var
  - `backend/app/core/logging.py` - RedisLogger with all required logging methods
- **Learnings:**
  - SERP cache uses 24h TTL (DEFAULT_TTL_HOURS = 24, converted to seconds)
  - Cache key format: `serp:{search_engine}:{location_code}:{language_code}:{keyword_hash}`
  - Keywords hashed with SHA256 truncated to 16 chars for stable, compact keys
  - Redis operations return None on failure (graceful degradation)
  - SSL/TLS automatically enabled when URL starts with `rediss://`
  - Connection retry with exponential backoff for Railway cold starts
  - CacheStats dataclass tracks hits/misses/errors with hit_rate property
---

## 2026-02-01 - client-onboarding-v2-c3y.66
- What was implemented: On-site review platform detection (Yotpo, Judge.me) - **ALREADY COMPLETE**
- Files verified (implementation already existed from commit 3f68e8b):
  - `backend/app/integrations/review_platforms.py` - ReviewPlatformClient with Perplexity integration
  - `backend/app/services/review_platforms.py` - ReviewPlatformService orchestration layer
  - `backend/app/schemas/review_platforms.py` - Pydantic request/response schemas
  - `backend/app/api/v1/endpoints/review_platforms.py` - API endpoint at `/detect`
  - `backend/app/api/v1/__init__.py` - Router registered at `/projects/{project_id}/phases/review_platforms`
- **Learnings:**
  - Supports 9 platforms: Yotpo, Judge.me, Stamped.io, Loox, Okendo, Reviews.io, Trustpilot, Bazaarvoice, PowerReviews
  - Uses Perplexity API to analyze websites (avoids direct scraping)
  - Returns confidence scores (0.0-1.0), evidence, widget locations, and API hints
  - Comprehensive ERROR LOGGING REQUIREMENTS fully implemented:
    - DEBUG entry/exit logs with sanitized parameters
    - Exception logging with full stack traces via `logger.exception()`
    - project_id included in all log entries
    - Validation failures logged with field names and values
    - State transitions logged at INFO level
    - Slow operations (>1s) logged with timing
  - Graceful degradation when Perplexity unavailable
  - JSON response parsing handles markdown code blocks from LLM
---

## 2026-02-01 - client-onboarding-v2-c3y.99
- What was implemented: Schedule configuration CRUD - **ALREADY COMPLETE**
- Files verified (implementation already existed):
  - `backend/app/models/crawl_schedule.py` - CrawlSchedule SQLAlchemy model with all fields
  - `backend/app/schemas/schedule.py` - Pydantic schemas (Create, Update, Response, ListResponse)
  - `backend/app/repositories/schedule.py` - ScheduleRepository with CRUD + specialized queries
  - `backend/app/services/schedule.py` - ScheduleService with validation and business logic
  - `backend/app/api/v1/endpoints/schedule.py` - Full REST API (POST, GET, PUT, DELETE)
  - `backend/app/api/v1/__init__.py` - Router registered at `/projects/{project_id}/phases/schedule`
- ERROR LOGGING REQUIREMENTS fully implemented:
  - ✓ DEBUG entry/exit logs with sanitized parameters (URLs truncated to 50 chars)
  - ✓ Exception logging with full stack traces via `exc_info=True`
  - ✓ Entity IDs (project_id, schedule_id) included in all logs
  - ✓ Validation failures logged with field names and rejected values
  - ✓ State transitions (is_active changes) logged at INFO level
  - ✓ Slow operations (>1s) logged with WARNING level via `SLOW_OPERATION_THRESHOLD_MS`
- **Learnings:**
  - 4-layer architecture: API → Service → Repository → Model
  - Schedule types: manual, daily, weekly, monthly, cron
  - Cron validation: 5 fields (minute hour day month weekday)
  - URL validation: must start with http:// or https://
  - Pagination defaults: limit=100, max=1000, offset>=0
  - API verifies project exists before schedule operations
  - API verifies schedule belongs to project_id before returning/modifying
  - Custom exceptions: ScheduleNotFoundError, ScheduleValidationError
  - Structured error responses: {"error": str, "code": str, "request_id": str}
---

## 2026-02-01 - client-onboarding-v2-c3y.108
- What was implemented: React Router navigation with error handling - **ALREADY COMPLETE**
- Files verified (implementation already existed):
  - `frontend/src/App.tsx` - BrowserRouter with nested ErrorBoundary wrappers per route
  - `frontend/src/components/ErrorBoundary.tsx` - Class component with componentDidCatch, component stack logging
  - `frontend/src/lib/errorReporting.ts` - Centralized error reporting with Sentry stub integration
  - `frontend/src/lib/globalErrorHandlers.ts` - window.onerror and onunhandledrejection handlers
  - `frontend/src/lib/api.ts` - ApiClient with full error context logging (endpoint, status, responseBody)
  - `frontend/src/lib/env.ts` - VITE_API_URL and VITE_SENTRY_DSN environment config
  - `frontend/src/main.tsx` - Initializes global error handlers before React mounts
  - `frontend/vite.config.ts` - Build config for static assets, dev proxy
- ERROR LOGGING REQUIREMENTS fully implemented:
  - ✓ React Error Boundaries wrap all route components
  - ✓ componentDidCatch logs error.message, stack, and componentStack to console
  - ✓ window.onerror captures uncaught sync errors with source, line, column
  - ✓ onunhandledrejection captures unhandled promise rejections
  - ✓ API errors logged with endpoint, method, status, responseBody
  - ✓ userAction and component context included in all error reports
  - ✓ Sentry stub with commented integration code (VITE_SENTRY_DSN)
- RAILWAY DEPLOYMENT REQUIREMENTS fully implemented:
  - ✓ `npm run build` outputs static assets to `dist/`
  - ✓ VITE_API_URL env var for API base URL
  - ✓ NODE_ENV=production handled by Vite automatically
  - ✓ Relative URLs work when VITE_API_URL is empty
- **Learnings:**
  - ErrorBoundary is a class component (required for componentDidCatch lifecycle)
  - Routes get their own ErrorBoundary to isolate failures
  - Global handlers catch errors outside React (async code, event handlers)
  - ApiClient uses empty baseUrl for relative paths (proxied in dev, configurable in prod)
  - Sentry integration is a stub - uncomment and `npm install @sentry/react` to enable
  - withErrorBoundary HOC available for wrapping any component
---

