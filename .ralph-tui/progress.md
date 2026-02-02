# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Error Logging Pattern in Services
All service files follow a standard error logging pattern:
```python
import time
from app.core.logging import get_logger

logger = get_logger(__name__)
SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second

# Method entry (DEBUG)
logger.debug("method_name() called", extra={"param": value, "project_id": id})

# Exception handling (ERROR with stack trace)
logger.error("Operation failed", extra={
    "project_id": id,
    "error_type": type(e).__name__,
    "error_message": str(e),
}, exc_info=True)

# Validation failures (WARNING)
logger.warning("Validation failed: field", extra={
    "field": field_name,
    "value": rejected_value,
    "valid": list_of_valid_options,
})

# State transitions (INFO)
logger.info("Status transition", extra={
    "from_status": old,
    "to_status": new,
    "project_id": id,
})

# Slow operations (WARNING)
if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
    logger.warning("Slow operation", extra={"duration_ms": duration_ms})
```

### Database Logging Pattern
Use `db_logger` singleton from `app.core.logging`:
- `db_logger.rollback_triggered(reason, from_version, to_version)`
- `db_logger.rollback_executed(from_version, to_version, success)`
- `db_logger.migration_start(version, description)`
- `db_logger.migration_end(version, success)`
- `db_logger.slow_query(query, duration_ms, table)`

---

## 2026-02-01 - client-onboarding-v2-c3y.148
- **What was implemented**: Created rollback procedure directive documentation
- **Files changed**:
  - `directives/rollback-procedure.md` (created) - Comprehensive rollback SOP with error logging requirements
- **Learnings:**
  - All 35 service files already have ERROR LOGGING REQUIREMENTS documented and implemented
  - `SLOW_OPERATION_THRESHOLD_MS = 1000` (1 second) is the standard threshold
  - All exception handlers use `exc_info=True` for full stack traces
  - The `DatabaseLogger` class provides rollback-specific logging methods
  - Directive format follows the template in `directives/README.md`
---

