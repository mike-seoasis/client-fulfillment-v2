# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Layer Pattern (Backend)
Services follow a consistent structure in `/backend/app/services/`:
1. **Module docstring** with ERROR LOGGING REQUIREMENTS
2. **Constants section** (SLOW_OPERATION_THRESHOLD_MS, DEFAULT_MAX_CONCURRENT, etc.)
3. **LLM Prompt Templates** as module constants
4. **Data Classes** with `to_dict()` methods for serialization (Input, Result types)
5. **Exception Classes** (ServiceError base, ValidationError with field_name/value)
6. **Main Service Class** with comprehensive logging:
   - DEBUG: method entry/exit with sanitized params
   - INFO: phase transitions (in_progress → completed)
   - WARNING: validation failures, slow operations (>1s)
   - ERROR: exceptions with full stack trace
7. **Singleton pattern** via `get_service()` function
8. **Convenience functions** wrapping service methods

### API Endpoint Pattern (Backend)
Endpoints in `/backend/app/api/v1/endpoints/`:
1. Helper functions: `_get_request_id()`, `_verify_project_exists()`, `_convert_*()`
2. Request/Response conversion between API schemas and service data classes
3. Structured error responses: `{"error": str, "code": str, "request_id": str}`
4. Log 4xx at WARNING, 5xx at ERROR with exc_info=True

### Brand Voice Integration
Brand voice is injected via `VoiceSchema` from `/backend/app/schemas/brand_config.py`:
- Fields: tone, personality, writing_style, target_audience, value_proposition
- Format for prompts via `_format_brand_voice()` method in content services

### Frontend UI Component Pattern
UI components follow a consistent structure in `/frontend/src/components/ui/`:
1. **Module docstring** with usage examples
2. **CVA variants** via `class-variance-authority` for styling variants
3. **Props interface** extending HTML attributes with custom props
4. **Component exports** with forwardRef when needed
5. **Separate provider files** for context-based components
6. **Helper functions** in `/frontend/src/lib/` to avoid Fast Refresh warnings

### Frontend Error Handling Pattern
Error handling follows a layered approach:
1. **Global handlers** (`lib/globalErrorHandlers.ts`) - window.onerror, unhandledrejection
2. **Error reporting** (`lib/errorReporting.ts`) - Sentry-ready centralized logging
3. **Error boundaries** (`components/ErrorBoundary.tsx`) - React component error catching
4. **API client** (`lib/axiosClient.ts`) - Circuit breaker, retries, detailed error logging
5. **Query client** (`lib/queryClient.ts`) - React Query error handling with reporting
6. **Toast system** (`components/ui/toast-provider.tsx`) - User-visible error notifications

---

## 2026-02-01 - client-onboarding-v2-c3y.119
- What was implemented: Toast notification system with full error handling integration
- Files created:
  - `frontend/src/components/ui/toast.tsx` - Toast component with variants (success, error, warning, info)
  - `frontend/src/components/ui/toast-provider.tsx` - React context provider with useToast hook
  - `frontend/src/lib/toastHelpers.ts` - Helper function for API error toasts
  - `frontend/src/lib/hooks/useToastMutation.ts` - React Query mutation wrapper with auto-toast
- Files modified:
  - `frontend/src/App.tsx` - Added ToastProvider wrapper
  - `frontend/src/lib/hooks/index.ts` - Export useToastMutation hook
- **Learnings:**
  - Existing error infrastructure was comprehensive: ErrorBoundary, global handlers, error reporting, API client logging
  - Used `/* eslint-disable react-refresh/only-export-components */` pattern for files exporting hooks alongside components
  - Toast variants match design system: success (green), error (warm red), warning (amber), info (cream/gold)
  - Positioned toasts in top-right with max 5 visible at once
  - API error toasts provide user-friendly messages based on status codes (401, 403, 404, 5xx)
  - Integrated with breadcrumb system for debugging
---

## 2026-02-01 - client-onboarding-v2-c3y.77
- What was implemented: **Already complete** - Phase 5B: Brand voice context injection was implemented in commit b3cbfec
- Files changed (already exist):
  - `backend/app/services/content_writer.py` (959 lines) - Content generation with Skill Bible rules
  - `backend/app/schemas/content_writer.py` (322 lines) - API request/response schemas
  - `backend/app/api/v1/endpoints/content_writer.py` (464 lines) - API endpoints
  - `backend/app/api/v1/__init__.py` - Router registration
- **Learnings:**
  - Phase 5B implementation includes brand voice injection via `_format_brand_voice()` method
  - Skill Bible rules are embedded in `SKILL_BIBLE_SYSTEM_PROMPT` constant with banned words/patterns
  - Content structure: H1, title_tag, meta_description, top_description, bottom_description
  - All ERROR LOGGING REQUIREMENTS are met: DEBUG entry/exit, INFO phase transitions, WARNING validation failures + slow ops, ERROR with stack traces
  - Router registered at `/projects/{project_id}/phases/content_writer`
---

