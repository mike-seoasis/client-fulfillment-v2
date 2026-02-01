# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Layer Structure
- Services go in `backend/app/services/` with corresponding exports in `__init__.py`
- Use dataclasses for request/result objects (e.g., `Collection`, `RelatedCollectionMatch`, `RelatedCollectionsResult`)
- Global singleton pattern via `get_*_service()` functions
- Convenience module-level functions that use singleton (e.g., `find_related_collections()`)

### Error Logging Pattern (ERROR LOGGING REQUIREMENTS)
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace using `exc_info=True`
- Include entity IDs (project_id, page_id) in all service logs via `extra={}` dict
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second using `SLOW_OPERATION_THRESHOLD_MS = 1000`

### Exception Hierarchy
- Base exception: `*ServiceError(Exception)`
- Validation: `*ValidationError(*ServiceError)` with field, value, message
- Not found: `*NotFoundError(*ServiceError)` with ID

### Logging Import
```python
from app.core.logging import get_logger
logger = get_logger(__name__)
```

### Frontend Structure (React 18 + TypeScript + Vite)
- Frontend lives in `frontend/` with standard Vite structure
- Path alias `@/*` maps to `src/*` (configured in tsconfig.json and vite.config.ts)
- Error boundaries wrap route components: `<ErrorBoundary componentName="..."><Component /></ErrorBoundary>`
- Global error handlers in `lib/globalErrorHandlers.ts` (window.onerror, onunhandledrejection)
- Error reporting stub in `lib/errorReporting.ts` with Sentry integration points
- API client in `lib/api.ts` with automatic error logging (endpoint, status, response body)
- Environment config in `lib/env.ts` for type-safe access to VITE_* vars

---

## 2026-02-01 - client-onboarding-v2-c3y.42
- **What was implemented**: RelatedCollectionsService with label overlap scoring (Jaccard similarity algorithm)
- **Files changed**:
  - `backend/app/services/related_collections.py` (new)
  - `backend/app/services/__init__.py` (exports added)
- **Learnings:**
  - Jaccard similarity is ideal for set overlap: `J(A,B) = |A∩B| / |A∪B|`
  - Collections in this codebase are represented by groups of CrawledPage entries sharing labels
  - Labels are stored as JSONB arrays in the crawled_pages table
  - The codebase uses strict mypy with Python 3.11+ features
  - Some existing mypy errors in config.py, logging.py, redis.py are pre-existing
---

## 2026-02-01 - client-onboarding-v2-c3y.64
- **What was implemented**: Perplexity API integration client for website analysis
- **Files changed**:
  - `backend/app/integrations/perplexity.py` (new) - Full async client with circuit breaker, retry logic, logging
  - `backend/app/integrations/__init__.py` - Added Perplexity exports
  - `backend/app/core/logging.py` - Added PerplexityLogger class
  - `backend/app/core/config.py` - Added Perplexity settings (API key, model, timeouts, circuit breaker)
- **Learnings:**
  - Perplexity API uses OpenAI-compatible format (`/chat/completions` endpoint)
  - Response includes `citations` array for web sources
  - Uses Bearer token auth (not x-api-key like Anthropic)
  - Model names: `sonar` for web-connected queries
  - Integration pattern: global singleton + `get_*()` dependency function
  - Logger pattern: service-specific logger class in core/logging.py with singleton instance
---

## 2026-02-01 - client-onboarding-v2-c3y.98
- **What was implemented**: APScheduler with SQLAlchemy job store for background task scheduling
- **Files changed**:
  - `backend/pyproject.toml` - Added apscheduler>=3.10.0 dependency
  - `backend/app/core/config.py` - Added scheduler settings (enabled, coalesce, max_instances, misfire_grace_time)
  - `backend/app/core/logging.py` - Added SchedulerLogger class with comprehensive job logging
  - `backend/app/core/scheduler.py` (new) - Full scheduler manager with SQLAlchemy job store
  - `backend/app/main.py` - Integrated scheduler with app lifespan (start/stop) and health check endpoint
- **Learnings:**
  - APScheduler uses synchronous SQLAlchemy, so must convert `postgresql+asyncpg://` to `postgresql://` for job store
  - APScheduler doesn't have type stubs, needs `apscheduler.*` in mypy ignore_missing_imports
  - Job store table is `apscheduler_jobs` (auto-created by SQLAlchemyJobStore)
  - Scheduler events: EVENT_JOB_ADDED, EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
  - Pattern: singleton `scheduler_manager` with `get_scheduler()` getter following other services
  - CronTrigger.from_crontab() for cron expressions, IntervalTrigger for intervals
  - Health check returns: status, running, state, job_count, pending_jobs
---

## 2026-02-01 - client-onboarding-v2-c3y.106
- **What was implemented**: React 18 + TypeScript + Vite frontend with error handling infrastructure
- **Files changed**:
  - `frontend/package.json` - Project config with React 18, react-router-dom, TypeScript, Vite
  - `frontend/tsconfig.json`, `frontend/tsconfig.node.json` - Strict TypeScript config with path aliases
  - `frontend/vite.config.ts` - Vite config with path alias and API proxy
  - `frontend/src/main.tsx` - Entry point with error handler initialization
  - `frontend/src/App.tsx` - Router with error boundary-wrapped routes
  - `frontend/src/components/ErrorBoundary.tsx` - React error boundary with component stack logging
  - `frontend/src/lib/globalErrorHandlers.ts` - window.onerror and onunhandledrejection handlers
  - `frontend/src/lib/errorReporting.ts` - Sentry stub with reportError, reportApiError
  - `frontend/src/lib/api.ts` - API client with full error context logging
  - `frontend/src/lib/env.ts` - Type-safe environment config
  - `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/railway.json` - Railway deployment config
- **Learnings:**
  - Vite build uses `tsc -b` which requires node types for vite.config.ts (add @types/node)
  - React router v6 uses `<Routes>` and `<Route>` pattern (not Switch)
  - ErrorBoundary componentDidCatch provides componentStack in errorInfo
  - window.onerror signature: (message, source, lineno, colno, error)
  - VITE_* env vars accessed via import.meta.env (typed in vite-env.d.ts)
  - Railway deployment: Dockerfile builds static assets, nginx serves with SPA routing
---

## 2026-02-01 - client-onboarding-v2-c3y.43
- **What was implemented**: Parallel processing for label generation with max 5 concurrent operations
- **Files changed**:
  - `backend/app/services/label.py` - Added `generate_labels_batch()` method and `BatchLabelResult` dataclass
  - `backend/app/services/__init__.py` - Added exports for `BatchLabelResult` and `generate_labels_batch`
- **Learnings:**
  - `asyncio.Semaphore` is the idiomatic way to limit concurrent async operations in Python
  - Use `asyncio.gather()` with semaphore-wrapped coroutines for parallel execution with concurrency control
  - Pattern: return `(index, result)` tuples from parallel tasks, then sort by index to preserve input order
  - Constants like `DEFAULT_MAX_CONCURRENT = 5` and `MAX_CONCURRENT_LIMIT = 10` should be module-level for configurability
  - Comprehensive logging for batch operations: entry/exit, per-item progress, and final statistics
---

## 2026-02-01 - client-onboarding-v2-c3y.44
- **What was implemented**: Label phase API endpoints at /api/v1/projects/{id}/phases/label
- **Files changed**:
  - `backend/app/schemas/label.py` (new) - Pydantic schemas for label requests/responses
  - `backend/app/schemas/__init__.py` - Added label schema exports
  - `backend/app/api/v1/endpoints/label.py` (new) - Full label phase API endpoints
  - `backend/app/api/v1/__init__.py` - Added label router registration
- **Endpoints created**:
  - POST `/phases/label` - Generate labels for a collection of URLs
  - POST `/phases/label/batch` - Batch generate labels for multiple collections in parallel
  - POST `/phases/label/pages` - Generate labels for existing crawled pages by IDs
  - POST `/phases/label/all` - Generate labels for all pages in project (background task)
  - GET `/phases/label/stats` - Get label statistics (total, labeled, unlabeled, counts)
- **Learnings:**
  - Phase endpoints follow pattern: router at `endpoints/<phase>.py`, registered with prefix `/projects/{project_id}/phases/<phase>`
  - Use `_verify_project_exists()` helper to check project before processing (reused pattern from categorize)
  - Background tasks use `BackgroundTasks.add_task()` for async work, return 202 Accepted immediately
  - For checking empty JSONB arrays: `(CrawledPage.labels.is_(None)) | (CrawledPage.labels == [])`
  - Use `zip(..., strict=True)` to satisfy ruff B905 linting rule for explicit strict parameter
  - Schemas mirror service dataclasses but use Pydantic BaseModel with Field() for API validation
---

## 2026-02-01 - client-onboarding-v2-c3y.45
- **What was implemented**: Unit tests for RelatedCollectionsService with 95% code coverage (71 tests)
- **Files changed**:
  - `backend/tests/services/test_related_collections.py` (new) - Comprehensive test suite
- **Test coverage**:
  - Collection, RelatedCollectionMatch, RelatedCollectionsResult dataclasses
  - Jaccard similarity coefficient calculation (identical, disjoint, partial overlap, edge cases)
  - find_related() method (thresholds, exclusions, sorting, filtering)
  - find_related_by_collection() convenience method
  - rank_by_similarity() method
  - find_clusters() greedy clustering algorithm
  - Singleton pattern and convenience functions
  - Exception classes and validation
  - Edge cases: unicode labels, large sets, empty inputs, case sensitivity
- **Learnings:**
  - Test patterns follow existing codebase: pytest fixtures, class-based test organization
  - Use `pytest.approx()` for floating-point comparisons in Jaccard tests
  - Import module directly to reset singleton state: `import app.services.module as mod; mod._singleton = None`
  - Pre-existing mypy errors in config.py, logging.py, redis.py are known issues (not from this change)
  - Ruff catches f-strings without placeholders (F541) - use regular strings instead
---

## 2026-02-01 - client-onboarding-v2-c3y.46
- **What was implemented**: Keywords Everywhere API integration client for keyword data lookup
- **Files changed**:
  - `backend/app/integrations/keywords_everywhere.py` (new) - Full async client with circuit breaker, retry logic, logging
  - `backend/app/integrations/__init__.py` - Added Keywords Everywhere exports
  - `backend/app/core/logging.py` - Added KeywordsEverywhereLogger class
  - `backend/app/core/config.py` - Added Keywords Everywhere settings (API key, timeouts, default country/currency/data_source, circuit breaker)
- **API details**:
  - Endpoint: `POST /v1/get_keyword_data`
  - Auth: Bearer token in Authorization header
  - Parameters: `country`, `currency`, `dataSource` (gkp/cli), `kw[]` (array, max 100)
  - Response fields: `keyword`, `vol`, `cpc` (nested `value`), `competition`, `trend`
- **Learnings:**
  - Keywords Everywhere API uses form data format (not JSON) for POST requests
  - Max 100 keywords per request (API limit) - implemented batch processing for larger lists
  - API uses credit-based billing (each keyword = 1 credit)
  - Data sources: `gkp` (Google Keyword Planner) or `cli` (clickstream data)
  - CPC is returned as nested object `{"value": float}`, not direct float
  - Integration pattern follows Perplexity: global singleton + `get_*()` dependency function
  - Logger pattern: service-specific logger class in core/logging.py with singleton instance
---

## 2026-02-01 - client-onboarding-v2-c3y.47
- **What was implemented**: Keyword volume caching service using Redis with 30-day TTL
- **Files changed**:
  - `backend/app/services/keyword_cache.py` (new) - Full caching service with graceful degradation
  - `backend/app/services/__init__.py` - Added keyword cache exports
  - `backend/app/core/config.py` - Added `keyword_cache_ttl_days` setting (default: 30)
- **Features**:
  - Cache key format: `kw_vol:{country}:{data_source}:{keyword_normalized}`
  - Single and batch get/set operations
  - Graceful degradation when Redis unavailable
  - Cache statistics tracking (hits, misses, errors, hit_rate)
  - TTL checking and cache deletion
  - Comprehensive logging per error logging requirements
- **Learnings:**
  - Service layer caching uses inline logging via `get_logger(__name__)`, not dedicated logger classes
  - Dedicated logger classes (like `KeywordsEverywhereLogger`) are for integrations layer, not services
  - Redis `ttl()` returns -2 if key doesn't exist, -1 if no TTL set
  - Cache keys should be normalized (lowercase, stripped) to avoid duplicates
  - `CachedKeywordData` dataclass includes metadata like `cached_at` timestamp and `country`/`data_source`
  - JSON serialization for complex objects stored in Redis
  - Pre-existing mypy errors in config.py, logging.py, redis.py are known issues
---

## 2026-02-01 - client-onboarding-v2-c3y.48
- **What was implemented**: KeywordIdeaService for LLM-based keyword idea generation (Step 1 of keyword research)
- **Files changed**:
  - `backend/app/services/keyword_ideas.py` (new) - Full service with Claude LLM integration
  - `backend/app/services/__init__.py` - Added keyword idea exports
- **Features**:
  - Generates 20-30 keyword ideas per collection page using Claude LLM
  - Prompt templates for keyword generation (system + user prompts)
  - Includes long-tail variations (3-5 words)
  - Includes question-based keywords ("best X for Y", "how to choose X")
  - Includes comparison keywords ("X vs Y")
  - Keyword validation and normalization
  - Comprehensive error logging per requirements
- **API**:
  - `KeywordIdeaService.generate_ideas(collection_title, url, content_excerpt, project_id, page_id)`
  - `KeywordIdeaRequest` dataclass for structured requests
  - `KeywordIdeaResult` dataclass with keywords, timing, token usage
  - `get_keyword_idea_service()` singleton getter
  - `generate_keyword_ideas()` convenience function
- **Learnings:**
  - Temperature 0.7 used for LLM to encourage creative keyword diversity (vs 0.0 for deterministic categorization)
  - Content excerpt truncated to 1500 chars for token efficiency
  - LLM may wrap JSON in code fences - need to handle `\`\`\`json` extraction
  - Service pattern: dataclasses for request/result, singleton with `get_*()` getter
  - Pre-existing mypy errors in config.py, logging.py, redis.py are known issues
---

## 2026-02-01 - client-onboarding-v2-c3y.49
- **What was implemented**: KeywordVolumeService for batch volume lookup with Redis caching (Step 2 of keyword research)
- **Files changed**:
  - `backend/app/services/keyword_volume.py` (new) - Full batch volume lookup service
  - `backend/app/services/__init__.py` - Added keyword volume exports
- **Features**:
  - Cache-first approach: check Redis before API calls
  - Batch volume lookup via Keywords Everywhere API (uses existing `get_keyword_data_batch`)
  - Automatic caching of API results for future lookups (30-day TTL)
  - `VolumeStats` dataclass with cache_hits, cache_misses, api_lookups, api_errors, cache_hit_rate
  - Graceful degradation when cache or API unavailable
  - Keyword normalization and deduplication
  - Comprehensive logging per error logging requirements
- **API**:
  - `KeywordVolumeService.lookup_volumes(keywords, country, data_source, project_id, page_id)`
  - `KeywordVolumeService.lookup_single(keyword, ...)` - convenience for single keyword
  - `KeywordVolumeData` dataclass with volume, cpc, competition, trend, from_cache flag
  - `KeywordVolumeResult` with keywords list, stats, credits_used
  - `get_keyword_volume_service()` singleton getter
  - `lookup_keyword_volumes()` convenience function
- **Learnings:**
  - Cache-first pattern: check cache → batch lookup misses → cache results
  - Use `from_cache` flag on results to indicate data source for debugging/analytics
  - Keyword normalization (lowercase, strip, single spaces) ensures cache key consistency
  - `VolumeStats` tracks complete operation statistics for monitoring
  - Composing services: KeywordVolumeService uses KeywordCacheService + KeywordsEverywhereClient
  - Pre-existing mypy errors in config.py, logging.py, redis.py are known issues
---

## 2026-02-01 - client-onboarding-v2-c3y.50
- **What was implemented**: KeywordSpecificityService for LLM-based keyword specificity filtering (Step 4 of keyword research)
- **Files changed**:
  - `backend/app/services/keyword_specificity.py` (new) - Full service with LLM specificity filter
  - `backend/app/services/__init__.py` - Added keyword specificity exports
- **Features**:
  - LLM-based specificity analysis via Claude
  - Filters keywords to only SPECIFIC ones (vs generic/broad keywords)
  - Preserves volume data for filtered keywords via keyword_map lookup
  - System + user prompt templates for specificity determination
  - Comprehensive error logging per requirements
- **API**:
  - `KeywordSpecificityService.filter_keywords(collection_title, url, content_excerpt, keywords, project_id, page_id)`
  - `SpecificityFilterRequest` dataclass for structured requests
  - `SpecificityFilterResult` with specific_keywords, filter_rate, token usage
  - `get_keyword_specificity_service()` singleton getter
  - `filter_keywords_by_specificity()` convenience function
- **Learnings:**
  - SPECIFIC vs GENERIC keywords: specific keywords reference exact product types, generic are too broad
  - Temperature 0.0 for deterministic filtering (vs 0.7 for creative keyword generation)
  - Keyword normalization (lowercase, strip, single spaces) is essential for matching LLM output to input keywords
  - filter_rate metric = (original - filtered) / original, useful for monitoring filter quality
  - Composing services: KeywordSpecificityService uses KeywordVolumeData from keyword_volume service
  - Pre-existing mypy errors in config.py, logging.py, redis.py are known issues
---

## 2026-02-01 - client-onboarding-v2-c3y.51
- **What was implemented**: PrimaryKeywordService for selecting the primary keyword (Step 5 of keyword research)
- **Files changed**:
  - `backend/app/services/primary_keyword.py` (new) - Full service with highest-volume selection logic
  - `backend/app/services/__init__.py` - Added primary keyword exports
- **Features**:
  - Selects highest-volume keyword from SPECIFIC keywords (output of Step 4)
  - Tie-breaker: prefers shorter keywords (more concise)
  - Fallback to first keyword if no volume data available
  - Comprehensive error logging per requirements
- **API**:
  - `PrimaryKeywordService.select_primary(collection_title, specific_keywords, project_id, page_id)`
  - `PrimaryKeywordRequest` dataclass for structured requests
  - `PrimaryKeywordResult` with primary_keyword, primary_volume, candidate_count
  - `get_primary_keyword_service()` singleton getter
  - `select_primary_keyword()` convenience function
- **Learnings:**
  - Primary keyword = highest-volume SPECIFIC keyword (not generic)
  - Selection is deterministic (no LLM needed) - just sorting by volume
  - Tie-breaker by keyword length ensures concise primary keywords
  - Fallback strategy: if all keywords lack volume data, use first keyword
  - Service follows established pattern: dataclasses for request/result, singleton with `get_*()` getter
  - Pre-existing mypy errors in config.py, logging.py, redis.py are known issues
---

## 2026-02-01 - client-onboarding-v2-c3y.52
- **What was implemented**: SecondaryKeywordService for selecting secondary keywords (Step 6 of keyword research)
- **Files changed**:
  - `backend/app/services/secondary_keywords.py` (new) - Full service with specific + broader keyword selection
  - `backend/app/services/__init__.py` - Added secondary keyword exports
- **Features**:
  - Selects 3-5 secondary keywords as a mix of SPECIFIC + BROADER terms
  - 2-3 specific keywords (lower volume than primary, from Step 4 output)
  - 1-2 broader terms with volume > 1000 (from all keywords)
  - Excludes primary keyword from selection
  - Excludes keywords already used as primary elsewhere (via used_primaries set)
  - Configurable thresholds (min/max specific, min/max broader, volume threshold)
  - Comprehensive error logging per requirements
- **API**:
  - `SecondaryKeywordService.select_secondary(collection_title, primary_keyword, specific_keywords, all_keywords, used_primaries, ...)`
  - `SecondaryKeywordRequest` dataclass for structured requests
  - `SecondaryKeywordResult` with secondary_keywords, specific_count, broader_count, total_count
  - `get_secondary_keyword_service()` singleton getter
  - `select_secondary_keywords()` convenience function
- **Learnings:**
  - Secondary keywords require two input lists: specific keywords (from Step 4) AND all keywords (for broader terms)
  - Broader terms are non-specific keywords with volume > 1000 - they capture related, higher-volume searches
  - used_primaries set prevents cross-collection duplicate primary keywords (important for multi-page projects)
  - Selection is deterministic (no LLM needed) - just filtering and sorting by volume
  - Fallback: if not enough broader terms, fill remaining slots with more specific keywords
  - Service follows established pattern: dataclasses for request/result, singleton with `get_*()` getter
---

## 2026-02-01 - client-onboarding-v2-c3y.53
- **What was implemented**: Duplicate primary prevention across project in PrimaryKeywordService
- **Files changed**:
  - `backend/app/services/primary_keyword.py` - Added `used_primaries` parameter to prevent duplicate primaries
- **Features**:
  - Added `used_primaries` set parameter to `select_primary()` method and `PrimaryKeywordRequest` dataclass
  - Filters out keywords already used as primary elsewhere during selection
  - Logs skipped keywords at DEBUG level for debugging/auditing
  - Handles edge case where all keywords are already used as primaries (returns success=False with error message)
  - Fallback selection also respects `used_primaries` exclusion
  - Keyword normalization (lowercase, stripped, single spaces) ensures case-insensitive comparison
  - Updated convenience function `select_primary_keyword()` with `used_primaries` parameter
- **API**:
  - `select_primary(..., used_primaries: set[str] | None = None)` - excludes keywords in set from selection
  - `PrimaryKeywordRequest.used_primaries: set[str]` - default empty set via `field(default_factory=set)`
- **Learnings:**
  - Duplicate primary prevention is critical for multi-page projects to avoid SEO keyword cannibalization
  - Same normalization pattern `_normalize_keyword()` should be used consistently across services (primary + secondary)
  - Fallback case (no volume data) also needs to respect `used_primaries` exclusion
  - Edge case: when all keywords are used elsewhere, return success=False with clear error message
  - Pre-existing mypy errors in config.py, logging.py, redis.py are known issues
---

## 2026-02-01 - client-onboarding-v2-c3y.54
- **What was implemented**: Keyword research phase API endpoints at /api/v1/projects/{id}/phases/keyword_research
- **Files changed**:
  - `backend/app/schemas/keyword_research.py` (new) - Pydantic schemas for all keyword research operations
  - `backend/app/schemas/__init__.py` - Added keyword research schema exports
  - `backend/app/api/v1/endpoints/keyword_research.py` (new) - Full keyword research API endpoints
  - `backend/app/api/v1/__init__.py` - Added keyword research router registration
- **Endpoints created**:
  - POST `/phases/keyword_research/ideas` - Generate 20-30 keyword ideas (Step 1, LLM)
  - POST `/phases/keyword_research/volumes` - Look up keyword volumes (Step 2, API + cache)
  - POST `/phases/keyword_research/specificity` - Filter by specificity (Step 4, LLM)
  - POST `/phases/keyword_research/primary` - Select primary keyword (Step 5)
  - POST `/phases/keyword_research/secondary` - Select secondary keywords (Step 6)
  - POST `/phases/keyword_research/full` - Run full pipeline (Steps 1-6)
  - GET `/phases/keyword_research/stats` - Get keyword research statistics
- **Learnings:**
  - Phase endpoints follow established pattern: router at `endpoints/<phase>.py`, registered with prefix `/projects/{project_id}/phases/<phase>`
  - Service objects (dataclasses) need explicit conversion to/from Pydantic schemas for API responses
  - Pydantic Field() with default=None still requires explicit default= vs using just None for mypy strict mode
  - CacheStats from keyword_cache service has `hits`, `misses`, `errors` properties - calculate `total_keywords` as hits+misses
  - CrawledPage model doesn't have `primary_keyword` column yet - stats endpoint returns placeholder zeros with TODO comment
  - Full pipeline endpoint orchestrates all 6 steps with step-by-step timing and graceful partial failure handling
  - Pre-existing mypy errors in config.py, logging.py, redis.py are known issues
---

