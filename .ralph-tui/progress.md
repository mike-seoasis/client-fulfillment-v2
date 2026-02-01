# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Frontend Page Pattern
New pages in `frontend/src/pages/` follow this structure:
1. Use `useApiQuery` hook for data fetching with `userAction` and `component` context
2. Use `useToastMutation` for mutations with automatic toast notifications
3. Add breadcrumbs via `addBreadcrumb()` for debugging
4. Wrap routes in `ErrorBoundary` in `App.tsx`
5. Follow loading → error → empty → content rendering pattern
6. Use `cn()` from `@/lib/utils` for conditional Tailwind classes
7. Keep local form state with `useState`, sync from API data with `useEffect`

### NLP Endpoint Pattern
All NLP endpoints follow a consistent structure in `backend/app/api/v1/endpoints/nlp.py`:
1. Use `_get_request_id(request)` helper to extract request_id
2. Log at DEBUG level for request details, INFO for completions
3. Time operations with `time.monotonic()` and include `duration_ms`
4. Return structured error responses: `{"error": str, "code": str, "request_id": str}`
5. Use `JSONResponse` with appropriate status codes for errors
6. Schemas live in `backend/app/schemas/nlp.py` with Pydantic Field descriptions

### TF-IDF Service Pattern
The `TFIDFAnalysisService` in `backend/app/services/tfidf_analysis.py`:
- Uses singleton pattern via `get_tfidf_analysis_service()`
- Supports both `analyze()` for general TF-IDF and `find_missing_terms()` for gap analysis
- Returns `TFIDFAnalysisResult` dataclass with `success`, `terms`, `error` fields
- Handles validation errors internally (returns result with `success=False`)

---

## 2026-02-01 - client-onboarding-v2-c3y.132
- What was implemented: ContentEditorPage with split-view live preview for editing content
- Files changed:
  - `frontend/src/pages/ContentEditorPage.tsx` - New page with editor, live preview, metadata editing, status management
  - `frontend/src/App.tsx` - Added route `/content/:contentId` with ErrorBoundary
  - `frontend/src/index.css` - Fixed `ease-smooth` → `ease-out` to unblock build
- **Learnings:**
  - Custom Tailwind transition timing functions in `transitionTimingFunction` can't be used with `@apply` - need inline values
  - ContentListPage provides excellent patterns for loading/error/empty states
  - `useToastMutation` handles both success toasts and API error toasts automatically
  - Split-view layout works well with `grid grid-cols-1 lg:grid-cols-2` pattern
  - Simple markdown preview can be done with regex replacements for basic formatting
---

## 2026-02-01 - client-onboarding-v2-c3y.96
- What was implemented: `/api/v1/nlp/recommend-terms` endpoint for content optimization recommendations
- Files changed:
  - `backend/app/schemas/nlp.py` - Added `RecommendedTermItem`, `RecommendTermsRequest`, `RecommendTermsResponse` schemas
  - `backend/app/api/v1/endpoints/nlp.py` - Added `recommend_terms` endpoint with priority scoring
- **Learnings:**
  - NLP endpoints follow a consistent pattern with request_id tracking, timing, and structured error responses
  - TF-IDF service already has `find_missing_terms()` method which does the heavy lifting
  - Priority scoring based on TF-IDF score and document frequency provides actionable recommendations
  - Pre-existing mypy errors in codebase are related to pydantic/fastapi stubs, not actual issues
---

