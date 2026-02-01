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

