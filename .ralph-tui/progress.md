# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### NLP Endpoint Pattern
- NLP endpoints are grouped under `/api/v1/nlp/` in `backend/app/api/v1/endpoints/nlp.py`
- Schemas live in `backend/app/schemas/nlp.py`
- Use `_get_request_id(request)` helper for extracting request_id from state
- All endpoints follow structured error response: `{"error": str, "code": str, "request_id": str}`
- Log DEBUG on request entry, INFO on success, WARNING on 4xx, ERROR on 5xx
- Include `duration_ms` in all response logs

### TF-IDF Analysis Pattern
- Use `get_tfidf_analysis_service()` singleton from `app/services/tfidf_analysis`
- `analyze()` for standard term extraction
- `find_missing_terms()` for content gap analysis (terms missing from user content)
- Results include `TermScore` objects with term, score, doc_frequency, term_frequency

### Frontend List Page Pattern
- List pages live in `frontend/src/pages/` and follow `ProjectListPage.tsx` as the template
- Use `useApiQuery` hook for data fetching with `queryKey` and `endpoint`
- All routes in `App.tsx` wrap pages with `<ErrorBoundary componentName="PageName">`
- Status filtering: define `STATUS_FILTER_OPTIONS` array with value/label/icon, manage state with `useState<StatusFilter>`
- Status colors: define `STATUS_COLORS` record mapping status to `{ bg, text }` Tailwind classes
- Memoize derived arrays with `useMemo` and include dependencies properly - avoid inline `|| []` in dependency arrays
- Card components include: main component + skeleton loader following `ProjectCardSkeleton` pattern
- Empty states: provide `EmptyState`, `NoSearchResults`, and `ErrorState` components

---

## 2026-02-01 - client-onboarding-v2-c3y.95
- What was implemented: `/api/v1/nlp/analyze-competitors` endpoint for TF-IDF competitor analysis
- Files changed:
  - `backend/app/api/v1/endpoints/nlp.py` - Added `analyze_competitors` endpoint
  - `backend/app/schemas/nlp.py` - Added `AnalyzeCompetitorsRequest`, `AnalyzeCompetitorsResponse`, `CompetitorTermItem` schemas
- **Learnings:**
  - NLP endpoints follow a consistent pattern with request_id logging and structured error responses
  - TF-IDF service already exists with both standard analysis and missing terms modes
  - The competitor phase endpoints at `/projects/{project_id}/phases/competitor/` are separate from NLP - they handle competitor CRUD and scraping, while NLP handles content analysis
---

## 2026-02-01 - client-onboarding-v2-c3y.131
- What was implemented: ContentListPage with status filtering for viewing all generated content
- Files changed:
  - `frontend/src/pages/ContentListPage.tsx` - New list page component with status filtering (All, Pending Review, Approved, Rejected)
  - `frontend/src/App.tsx` - Added route `/content` with ErrorBoundary wrapper
- **Learnings:**
  - When memoizing derived arrays from API data, avoid inline `|| []` fallbacks in useMemo dependencies - wrap the fallback itself in useMemo to avoid ESLint warnings
  - Content status uses `pending_review`, `approved`, `rejected` - different from project status values
  - Follow ProjectListPage pattern: header with nav + title, status filter tabs, search input, content grid with card/skeleton components
  - StatusCount component pattern: button with icon, label, and count badge - useful for filtering UX
  - Content types are stored as snake_case (`blog_post`) and need display labels for UI
---

