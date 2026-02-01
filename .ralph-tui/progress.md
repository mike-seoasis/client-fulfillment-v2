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

