# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Error Logging Pattern for Services
All backend services follow a consistent error logging pattern (see `backend/app/services/*.py`):

1. **Method Entry/Exit (DEBUG)**: Log at start with sanitized params, log completion with results
   ```python
   logger.debug("Phase 5C content quality check starting", extra={"content_id": content_id, "project_id": project_id, "page_id": page_id})
   ```

2. **Exception Logging (ERROR)**: Include full stack trace via `exc_info=True` and `traceback.format_exc()`
   ```python
   logger.error("Unexpected error", extra={"error": str(e), "error_type": type(e).__name__, "stack_trace": traceback.format_exc()}, exc_info=True)
   ```

3. **Entity IDs**: Always include `project_id`, `page_id`, `content_id` in extra dict

4. **Validation Failures (WARNING)**: Include field name and rejected value
   ```python
   logger.warning("Validation failed", extra={"field": "bottom_description", "rejected_value": "", "project_id": project_id})
   ```

5. **State Transitions (INFO)**: Log phase changes with status
   ```python
   logger.info("Phase 5C: Content quality check - in_progress", extra={"phase": "5C", "status": "in_progress"})
   ```

6. **Slow Operations (WARNING)**: Use `SLOW_OPERATION_THRESHOLD_MS = 1000` constant
   ```python
   if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
       logger.warning("Slow operation", extra={"duration_ms": duration_ms})
   ```

### Specialized Loggers in core/logging.py
The codebase has pre-built loggers for external services:
- `db_logger` - Database operations
- `redis_logger` - Redis operations
- `crawl4ai_logger` - Crawl4AI API
- `claude_logger` - Claude/Anthropic LLM
- `perplexity_logger` - Perplexity API
- `scheduler_logger` - APScheduler jobs
- `keywords_everywhere_logger` - Keywords Everywhere API
- `dataforseo_logger` - DataForSEO API

---

## 2026-02-01 - client-onboarding-v2-c3y.84
- **What was implemented**: Verified that comprehensive error logging is already implemented across all backend services
- **Files examined** (no changes needed):
  - `backend/app/services/project.py` - Full logging implementation
  - `backend/app/services/content_quality.py` - Full logging implementation
  - `backend/app/services/content_word_count.py` - Full logging implementation
  - `backend/app/services/link_validator.py` - Full logging implementation
  - `backend/app/services/llm_qa_fix.py` - Full logging implementation
  - `backend/app/core/logging.py` - Comprehensive logging infrastructure (2000+ lines)
- **Learnings:**
  - All services already implement the required error logging pattern
  - The codebase has a well-established logging pattern that should be followed for new services
  - Specialized loggers exist for external API integrations (Claude, DataForSEO, etc.)
  - `SLOW_OPERATION_THRESHOLD_MS = 1000` is the standard threshold for timing warnings
  - Validation errors include both field names and rejected values in logs
---

