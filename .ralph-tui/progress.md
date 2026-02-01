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

