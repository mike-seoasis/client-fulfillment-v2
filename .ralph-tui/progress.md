# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### ServiceLogger Pattern
Use `ServiceLogger` from `app.core.logging` for standardized service-layer logging:
```python
from app.core.logging import get_service_logger

class MyService:
    def __init__(self) -> None:
        self.logger = get_service_logger("my_service")

    async def do_work(self, project_id: str) -> Entity:
        with self.logger.operation("do_work", project_id=project_id) as ctx:
            # Business logic...
            ctx.add_result(entity_id=result.id)
            return result
```

Key methods:
- `operation()` - Context manager for automatic entry/exit logging with timing
- `validation_failure()` - Log validation errors with field/value
- `state_transition()` - Log phase/status changes at INFO level
- `exception()` - Log exceptions with full stack trace

---

## 2026-02-01 - client-onboarding-v2-c3y.156
- What was implemented: Added `ServiceLogger` class to `backend/app/core/logging.py` implementing ERROR LOGGING REQUIREMENTS
- Files changed: `backend/app/core/logging.py`
- **Learnings:**
  - Patterns discovered: Existing services (project.py, category.py, crawl.py) already implement logging manually - the ServiceLogger centralizes this
  - Gotchas encountered: mypy requires `__exit__` return type to be `None` (not `bool`) when always returning False to propagate exceptions
  - The codebase already has comprehensive logging infrastructure with specialized loggers (DatabaseLogger, RedisLogger, ClaudeLogger, etc.) - ServiceLogger complements these for service layer

---

