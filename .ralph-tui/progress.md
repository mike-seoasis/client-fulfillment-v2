# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### API Endpoint Pattern (FastAPI)
- Endpoints live in `backend/app/api/v1/endpoints/`
- Schemas live in `backend/app/schemas/`
- Register routers in `backend/app/api/v1/__init__.py`
- All endpoints must:
  1. Get `request_id` via `_get_request_id(request)` helper
  2. Log DEBUG at start with request details
  3. Log INFO on success with timing
  4. Return structured errors: `{"error": str, "code": str, "request_id": str}`
  5. Log 4xx at WARNING, 5xx at ERROR with `exc_info=True`

### Pydantic Schema Gotcha
- Avoid field names that conflict with Pydantic BaseModel methods
- Example: `schema_json` conflicts with `BaseModel.schema_json()`
- Use alternatives like `jsonld_schema` instead

### NLP/Content Analysis
- Existing content signal detection in `backend/app/utils/content_signals.py`
- `ContentSignalDetector` class with singleton via `get_content_signal_detector()`
- `analyze()` method returns `ContentAnalysis` with signals and boosted confidence

### Frontend Panel Component Pattern
- Panel components live in `frontend/src/components/`
- All panels take `projectId` and optional `className` props
- Use `useApiQuery` for data fetching with error context
- Use `useToastMutation` for mutations with automatic toasts
- Use `useProjectSubscription` for real-time WebSocket updates
- Follow collapsible card pattern with ChevronUp/ChevronDown
- Include StatsCard sub-component for metrics display
- Consistent styling: warm color palette, soft shadows, generous spacing

### Frontend Error Handling Infrastructure
- ErrorBoundary wraps all route components in App.tsx
- Global handlers (window.onerror, unhandledrejection) set up in main.tsx
- API client reports errors with full context (endpoint, status, response body)
- Sentry integration stub ready in `frontend/src/lib/errorReporting.ts`
- All errors include user action context for debugging

---

## 2026-02-01 - client-onboarding-v2-c3y.130
- **What was implemented**: Built ContentGenerationPanel with 3-phase progress UI
- **Files changed**:
  - `frontend/src/components/ContentGenerationPanel.tsx` (new) - Panel with 3-phase progress display
- **Learnings:**
  - Error logging infrastructure was already fully implemented (ErrorBoundary, global handlers, API client, Sentry stub)
  - Panel components follow consistent pattern: stats overview, configuration section, content list
  - Phase progress visualization uses vertical timeline with connector lines
  - Content review workflow uses expandable cards with approve/reject actions
  - WebSocket subscription with polling fallback for real-time updates during generation
---

## 2026-02-01 - client-onboarding-v2-c3y.94
- **What was implemented**: Created `/api/v1/nlp/analyze-content` POST endpoint for content signal analysis
- **Files changed**:
  - `backend/app/schemas/nlp.py` (new) - Pydantic schemas for request/response
  - `backend/app/api/v1/endpoints/nlp.py` (new) - Endpoint implementation
  - `backend/app/api/v1/__init__.py` - Registered NLP router at `/nlp` prefix
- **Learnings:**
  - Pydantic field names can conflict with BaseModel built-in methods (e.g., `schema_json`)
  - Existing `ContentSignalDetector` in utils handles all signal detection logic
  - Non-phase endpoints (like NLP) don't need `/projects/{project_id}/phases/` prefix
  - Error logging already handled by RequestLoggingMiddleware in main.py
---

