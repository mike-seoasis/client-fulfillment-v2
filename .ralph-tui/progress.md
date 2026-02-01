# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Layer Pattern
Services follow a consistent pattern in `backend/app/services/`:
- Module docstring with ERROR LOGGING REQUIREMENTS
- Data classes for input/output (`@dataclass`)
- Custom exceptions inheriting from base `ServiceError`
- Constants for thresholds (`SLOW_OPERATION_THRESHOLD_MS = 1000`)
- Service class with `__init__` logging, async methods
- Singleton pattern via `_service: Service | None = None` + `get_service()` function
- Convenience functions that wrap the singleton

### Prompt Template Pattern
LLM prompts are structured as:
- `SYSTEM_PROMPT` constant with role, rules, output format
- `USER_PROMPT_TEMPLATE` with `.format()` placeholders
- Called via `claude.complete(system_prompt=..., user_prompt=..., temperature=0.X)`

### Error Logging Pattern
All services must include:
- DEBUG: Method entry/exit with sanitized parameters
- ERROR: Exceptions with full stack trace (`traceback.format_exc()`)
- Entity IDs: Always include `project_id`, `page_id` in `extra={}`
- Validation failures: Log field name and rejected value at WARNING
- Phase transitions: Log at INFO level with `phase`, `status` keys
- Slow operations: Log at WARNING when `duration_ms > SLOW_OPERATION_THRESHOLD_MS`

### API Endpoint Pattern
Endpoints in `backend/app/api/v1/endpoints/`:
- Router registered in `api/v1/__init__.py`
- `_get_request_id(request)` helper for logging
- `_verify_project_exists()` returns `JSONResponse | None`
- Convert service results to response schemas via helper function
- Return `ResponseModel | JSONResponse` union type
- Log request at DEBUG, response at INFO

### Frontend Error Handling Pattern
Frontend error handling follows a multi-layer approach in `frontend/src/`:
- **ErrorBoundary** (`components/ErrorBoundary.tsx`): React class component with `componentDidCatch`, logs component stack
- **Global handlers** (`lib/globalErrorHandlers.ts`): `window.onerror` and `onunhandledrejection`, called before React mounts in `main.tsx`
- **Error reporting** (`lib/errorReporting.ts`): Centralized service with Sentry integration point, `reportError()` and `reportApiError()` functions
- **API clients** (`lib/api.ts`, `lib/axiosClient.ts`): Include `userAction` and `component` context, call `reportApiError` on failures
- **React Query** (`lib/queryClient.ts`): Global error handlers in QueryCache/MutationCache

### Frontend Loading State Pattern
Loading states use skeletons matching component structure:
- Skeleton components co-located with main component (e.g., `ProjectCardSkeleton` in `ProjectCard.tsx`)
- Use `animate-pulse-soft` animation from tailwind config
- `bg-cream-200` for skeleton backgrounds matching warm design system
- Generic `LoadingSpinner` (`components/ui/loading-spinner.tsx`) for inline/page-level loading
- Size variants: `sm`, `md`, `lg`, `xl` with appropriate border widths

---

## 2026-02-01 - client-onboarding-v2-c3y.118
- Verified comprehensive error handling implementation already exists
- Created missing `LoadingSpinner` component for generic loading states
- Files created:
  - `frontend/src/components/ui/loading-spinner.tsx` - Generic spinner with size variants, plus `FullPageSpinner` and `ButtonSpinner` helpers
- **Error handling features verified:**
  - React Error Boundaries wrap all route components in `App.tsx`
  - Global `window.onerror` and `onunhandledrejection` handlers in `globalErrorHandlers.ts`
  - API errors logged with endpoint, status, response body via `reportApiError()`
  - User action context included via `userAction` field in `ErrorContext`
  - Sentry integration point fully stubbed with commented initialization code
- **Learnings:**
  - Frontend error handling was already implemented in previous iterations
  - Skeleton loading states exist for domain components (`ProjectCardSkeleton`, `PhaseProgressSkeleton`, `DataTable` loading)
  - Design system uses `primary-500` (gold) for spinner accent, `cream-300` for background track
  - `sr-only` class provides accessible labels without visual display
---

## 2026-02-01 - client-onboarding-v2-c3y.76
- Implemented Phase 5B: Content Writer service with Skill Bible rules in prompt template
- Files created:
  - `backend/app/services/content_writer.py` - Main service with Skill Bible system prompt
  - `backend/app/schemas/content_writer.py` - Pydantic schemas for API
  - `backend/app/api/v1/endpoints/content_writer.py` - API endpoints
  - `backend/app/api/v1/__init__.py` - Updated to register new router
- **Learnings:**
  - Skill Bible rules are comprehensive copywriting guidelines embedded in system prompt
  - Rules include: banned words (delve, unlock, unleash), banned patterns (em dashes, triplets), structure requirements (H1 3-7 words, bottom description 300-450 words)
  - Phase 5B takes research brief from Phase 5A and brand voice from V2 schema
  - Internal links are formatted as `<p>Related: <a>...</a> | <a>...</a></p>`
  - Ruff SIM102 rule prefers flat conditionals over nested walrus operator patterns
---

