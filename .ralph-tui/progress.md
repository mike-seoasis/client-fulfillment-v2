# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Pattern
Services use dataclass results with success/error indicators and comprehensive logging:
```python
@dataclass
class ServiceResult:
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        ...
```

### Error Logging Pattern
All services follow the error logging requirements:
- Method entry/exit at DEBUG level with sanitized params
- Exceptions with full stack trace (`traceback.format_exc()`)
- Include entity IDs (project_id, page_id) in all logs
- Validation failures with field names and rejected values
- State transitions (phase changes) at INFO level
- Timing logs for operations >1 second (SLOW_OPERATION_THRESHOLD_MS)

### Endpoint Pattern
Endpoints use `_get_request_id(request)` and `_verify_project_exists()` helpers.
Return `JSONResponse` for errors with structured format:
```python
{"error": str, "code": str, "request_id": str}
```

### Singleton Factory Pattern
Services use singleton factory functions:
```python
_service: ServiceClass | None = None

def get_service() -> ServiceClass:
    global _service
    if _service is None:
        _service = ServiceClass()
        logger.info("ServiceClass singleton created")
    return _service
```

### Frontend Component Pattern
Form components use forwardRef with class-variance-authority (cva) for variants:
```tsx
const inputVariants = cva('base-classes', {
  variants: {
    variant: { default: '...', error: '...', success: '...' },
    size: { default: '...', sm: '...', lg: '...' },
  },
  defaultVariants: { variant: 'default', size: 'default' },
})

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, variant, size, ...props }, ref) => (
    <input className={cn(inputVariants({ variant, size, className }))} ref={ref} {...props} />
  )
)
Input.displayName = 'Input'
```

---

## 2026-02-01 - client-onboarding-v2-c3y.117
- **What was implemented**: FormField components with validation display
  - Input, Textarea, Select components with variant states (default/error/success)
  - Checkbox component with label support
  - Label component with required/optional indicators
  - HelperText component for validation messages (error/success/warning/default)
  - FormField composite component that wraps inputs with labels and validation feedback
  - Proper aria attributes for accessibility (aria-invalid, aria-describedby, role="alert")

- **Files created**:
  - `frontend/src/components/ui/form-field.tsx` - All form field components

- **Learnings:**
  - React hooks must be called unconditionally - use `const generatedId = React.useId(); const inputId = id || generatedId;` not `const inputId = id || React.useId()`
  - Files exporting both components and variants (cva) need `/* eslint-disable react-refresh/only-export-components */` at the top
  - Error logging infrastructure already exists in frontend (ErrorBoundary, globalErrorHandlers, errorReporting, api client with error logging)
  - Design system uses warm colors (cream, warmgray, primary/gold, coral, error, success, warning) with soft shadows and rounded-xl borders
---

## 2026-02-01 - client-onboarding-v2-c3y.75
- **What was implemented**: Phase 5A Content Plan Builder
  - Service that combines PAA analysis with Perplexity research
  - Produces content plan with main angle, benefits, and priority questions
  - Concurrent execution of PAA enrichment and Perplexity research
  - Full error logging per requirements

- **Files created**:
  - `backend/app/schemas/content_plan.py` - Pydantic schemas
  - `backend/app/services/content_plan.py` - Content plan builder service
  - `backend/app/api/v1/endpoints/content_plan.py` - API endpoints

- **Files changed**:
  - `backend/app/api/v1/__init__.py` - Added content_plan router

- **API Endpoints**:
  - `POST /api/v1/projects/{project_id}/phases/content_plan/build` - Build content plan for keyword
  - `POST /api/v1/projects/{project_id}/phases/content_plan/batch` - Batch build for multiple keywords

- **Learnings:**
  - PAA enrichment, categorization, and analysis services already exist and work well together
  - Perplexity integration uses circuit breaker pattern for fault tolerance
  - Services should use `asyncio.gather()` for concurrent operations
  - Benefits extraction from Perplexity requires JSON parsing with fallback handling
  - The codebase has a pre-existing issue in documents.py (FastAPI return type annotation error) unrelated to this implementation
---

