# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Logging Pattern
All services follow a consistent logging pattern with structured context:
- `logger.debug()` for method entry/exit with sanitized parameters
- `logger.info()` for state transitions and operation completions
- `logger.warning()` for slow operations (>1000ms) and non-fatal errors
- `logger.error()` for exceptions with full stack trace via `traceback.format_exc()`
- Always include `project_id` and `page_id` in `extra={}` dict for traceability
- Log validation failures with field name and rejected value

### Async Service Pattern
Services use a singleton pattern with lazy initialization:
```python
_service: ServiceClass | None = None

def get_service() -> ServiceClass:
    global _service
    if _service is None:
        _service = ServiceClass()
        logger.info("ServiceClass singleton created")
    return _service
```

### Fallback Strategy Pattern
When primary data source is insufficient:
1. Check primary source (e.g., PAA questions)
2. If result count < threshold, trigger fallback
3. Fallback uses LLM semantic filter for relevance scoring
4. Results are cached with TTL (typically 24h)
5. Log fallback usage at INFO level

---

## 2026-02-01 - client-onboarding-v2-c3y.59
- What was implemented: **Already complete** - Verified existing implementation of Related Searches fallback with LLM semantic filter
- Files verified:
  - `backend/app/services/related_searches.py` (1009 lines) - Complete implementation
  - `backend/app/services/paa_enrichment.py` (1192 lines) - Integrates fallback via `_fetch_related_searches_fallback()`
- **Implementation details:**
  - `RelatedSearchesService` extracts related_searches from DataForSEO SERP API
  - Claude LLM semantic filtering with MIN_RELEVANCE_SCORE=0.6 threshold
  - Converts filtered searches to question format (PAA-style)
  - 24h Redis cache TTL
  - Graceful fallback when Claude unavailable (returns unfiltered results)
  - `paa_enrichment.py` triggers fallback when PAA questions < `min_paa_for_fallback` (default 3)
- **Learnings:**
  - Patterns discovered: Comprehensive logging pattern with entity IDs in all log statements
  - Gotchas encountered: mypy shows errors in dependency files (config.py, logging.py, redis.py) but target files type-check successfully
  - Both files pass ruff linting and Python syntax validation
---

