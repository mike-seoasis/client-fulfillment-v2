# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Phase Service Pattern
All phase services follow a consistent structure:
1. **Data Classes**: Input, Result, and custom types (e.g., `LinkValidatorInput`, `LinkValidationBatchResult`)
2. **Exceptions**: Base exception and validation exception with `project_id`, `page_id` tracking
3. **Service Class**: Main service with validation methods prefixed `_validate_*` and detection methods prefixed `_detect_*`
4. **Singleton**: Global `_service: Service | None = None` with `get_*_service()` getter
5. **Convenience Functions**: Module-level async functions that use the singleton

### Logging Pattern (ERROR LOGGING REQUIREMENTS)
- DEBUG: Method entry/exit with parameters (sanitize content, log lengths instead)
- INFO: Phase transitions with `phase`, `status`, entity IDs
- WARNING: Validation failures with `field`, `rejected_value`
- ERROR: Full stack trace with `error_type`, `error_message`, `stack_trace`
- SLOW_OPERATION_THRESHOLD_MS = 1000 for timing warnings

### API Endpoint Pattern
1. Router with `_get_request_id()` helper
2. `_verify_project_exists()` returning `JSONResponse | None`
3. `_convert_request_to_input()` and `_convert_result_to_response()` converters
4. Structured error responses: `{"error": str, "code": str, "request_id": str}`
5. HTTP 400 for validation errors, 404 for not found, 500 for internal errors

### Router Registration (api/v1/__init__.py)
- Import module in alphabetical order
- Register with: `router.include_router(module.router, prefix="/projects/{project_id}/phases/phase_name", tags=["Phase Name Phase"])`

### Optimistic Update Pattern
Use `useOptimisticMutation` hook for mutations that should feel instant:
1. **mutationFn**: Standard API call function
2. **queryKey**: The query to update optimistically
3. **getOptimisticData**: `(currentData, variables) => newData` - applies update immediately
4. **invalidateKeys**: Additional queries to invalidate on success (optional)
5. **updateCacheWithResult**: `(currentData, result, variables) => newData` - sync with server response (optional, defaults to invalidation)
6. **entityIds**: Include `{ projectId }` etc for logging context
7. **userAction**: Description for logging and toasts
8. **component**: Component name for error context

The hook automatically:
- Snapshots current data for rollback
- Cancels in-flight queries to avoid race conditions
- Logs all state transitions per ERROR LOGGING REQUIREMENTS
- Reports slow operations (>1s) as warnings
- Rolls back on error with error toast

---

## 2026-02-01 - client-onboarding-v2-c3y.81
- What was implemented: Phase 5C Link Validation Against Collection Registry
  - `LinkValidatorService`: Validates internal links from generated content against a registry of known valid collection pages
  - `CollectionRegistry`: Registry data structure with normalized URL lookup for fast validation
  - URL normalization using existing `URLNormalizer` utility for consistent comparison
  - Detection of internal vs external links based on site domain
  - Batch validation support with aggregate statistics
- Files changed:
  - `backend/app/services/link_validator.py` (new) - Service with validation logic
  - `backend/app/schemas/link_validator.py` (new) - Pydantic request/response schemas
  - `backend/app/api/v1/endpoints/link_validator.py` (new) - FastAPI endpoints
  - `backend/app/api/v1/__init__.py` (modified) - Router registration
- **Learnings:**
  - Existing `URLNormalizer` in `app/utils/url.py` handles all URL normalization needs - no need to write custom logic
  - Phase services don't require database models if they operate on in-memory data (registry passed in request)
  - External links are intentionally not validated against registry - only internal links are checked
  - The `Collection` dataclass in `related_collections.py` is for label-based similarity, not URL-based validation
---

## 2026-02-01 - client-onboarding-v2-c3y.123
- What was implemented: ProjectSettingsPage for project configuration
  - Full settings page for editing project name, description, and status
  - Danger zone with archive/unarchive and delete functionality
  - Delete confirmation requiring exact project name match
  - Form validation with real-time feedback
  - Loading skeletons and error states matching existing patterns
  - Wrapped in ErrorBoundary for error isolation
- Files changed:
  - `frontend/src/pages/ProjectSettingsPage.tsx` (new) - Full settings page component
  - `frontend/src/App.tsx` (modified) - Added route `/projects/:projectId/settings`
- **Learnings:**
  - Frontend pages follow consistent structure: skeleton, error state, main content
  - Form fields use FormField wrapper with Input/Textarea/Select from `components/ui/form-field.tsx`
  - useToastMutation hook handles API mutations with automatic toast notifications
  - ErrorBoundary wraps each route with `componentName` prop for debugging
  - addBreadcrumb from errorReporting.ts used for tracking user actions
  - useApiQuery wraps React Query with built-in error handling and logging
  - Danger zone pattern: separate section with warning styling for destructive actions
---

## 2026-02-01 - client-onboarding-v2-c3y.138
- What was implemented: Optimistic updates for approval workflows
  - New `useOptimisticMutation` hook for reusable optimistic update pattern
  - Integrated with existing toast and error reporting infrastructure
  - Automatic rollback on error with cache snapshot restoration
  - Slow operation warnings (>1s) per ERROR LOGGING REQUIREMENTS
  - Full breadcrumb and error reporting integration
  - Updated `ProjectSettingsPage` to use optimistic updates for:
    - Project settings updates (name, description, status)
    - Archive/unarchive operations
- Files changed:
  - `frontend/src/lib/hooks/useOptimisticMutation.ts` (new) - Reusable optimistic mutation hook
  - `frontend/src/lib/hooks/index.ts` (modified) - Export new hook
  - `frontend/src/pages/ProjectSettingsPage.tsx` (modified) - Use optimistic mutations
- **Learnings:**
  - React Query's `onMutate` callback is where optimistic updates are applied
  - `queryClient.cancelQueries()` prevents race conditions with in-flight queries
  - Return a context object from `onMutate` containing the snapshot for rollback in `onError`
  - TypeScript requires explicit handling of undefined cache data - use `as unknown as T` pattern with a warning log
  - The hook can optionally update cache with server response via `updateCacheWithResult`, otherwise it invalidates
  - Existing `useToastMutation` remains for mutations that don't need optimistic updates
---

