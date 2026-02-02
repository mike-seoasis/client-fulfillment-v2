# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Error Logging Pattern
The codebase uses structured logging with the following conventions:
- `log_method_entry(name, **params)` - DEBUG level entry with sanitized params
- `log_method_exit(name, success, result_summary)` - DEBUG level exit
- `log_exception_with_context(error, context, operation)` - ERROR with full stack trace
- `log_slow_operation(operation, duration_s, **context)` - WARNING if >1s
- `log_validation_failure(entity_type, entity_id, field_name, rejected_value, reason)` - WARNING
- `log_phase_transition(project_id, phase_name, old_status, new_status)` - INFO

All service loggers (DatabaseLogger, ClaudeLogger, etc.) are singletons in `app/core/logging.py`.

### Schema Validation Pattern
Use Pydantic models with `@field_validator` decorators for validation:
```python
class V2Schema(BaseModel):
    field: str = Field(..., min_length=1)

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        if not valid(v):
            raise ValueError(f"Invalid: {v}")
        return v
```

---

## 2026-02-01 - client-onboarding-v2-c3y.145
- What was implemented: V2 schema transformation script with comprehensive error logging
- Files changed:
  - `execution/transform_v1_to_v2.py` (new file)
- **Learnings:**
  - V1 schema uses flat phase status fields (phase1_status, phase2_status, etc.) that need to be consolidated into V2's JSONB phase_status
  - V1 didn't have client_id - need to derive from project name
  - Page data can be in multiple files (crawl_results.json, categorized_pages.json, labeled_pages.json)
  - Error logging requirements require: method entry/exit at DEBUG, exceptions with stack trace, entity IDs in logs, validation failures with field names, phase transitions at INFO, timing for >1s operations
  - Use `dataclass` with `| None` type annotations and `__post_init__` for mutable defaults (not `= None`)
---

