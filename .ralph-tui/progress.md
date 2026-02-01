# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Phase 5B Content Writer Architecture
- **Service Layer**: `ContentWriterService` in `app/services/content_writer.py`
- **Data Flow**: `ContentWriterInput` → LLM prompt with Skill Bible rules → `GeneratedContent`
- **Link Types**: Two categories - `related_links` (Jaccard similarity on labels) and `priority_links` (business priority)
- **Prompt Template**: Links inserted via `_format_links()` method, max 3 per category
- **Output Format**: Bottom description includes `<p>Related: [links]</p>` and `<p>See Also: [links]</p>`

### Error Logging Pattern (All Services)
- **Entry Logging**: DEBUG level with sanitized params (truncate strings, counts for lists)
- **Exception Logging**: ERROR level with `traceback.format_exc()` and `exc_info=True`
- **Entity IDs**: Always include `project_id`, `page_id` in extra dict
- **State Transitions**: INFO level for phase status changes (in_progress, completed)
- **Slow Operations**: WARNING level when `duration_ms > SLOW_OPERATION_THRESHOLD_MS` (1000ms)

### Related Collections Service
- **Algorithm**: Jaccard similarity `J(A,B) = |A ∩ B| / |A ∪ B|` on label sets
- **Default Threshold**: 0.1 (10% label overlap minimum)
- **Service Location**: `app/services/related_collections.py`

### Frontend Page Component Pattern
- **Data Fetching**: `useApiQuery<T>` hook with `queryKey`, `endpoint`, `requestOptions` (userAction, component)
- **States**: Loading (skeleton grid), Error (retry button), Empty (CTA), NoResults (search-specific)
- **Breadcrumbs**: `addBreadcrumb(message, category, data)` for user action tracking
- **Routing**: Each route wrapped in `<ErrorBoundary componentName="PageName">`
- **Design**: `bg-cream-50`, `text-warmgray-*`, `rounded-xl`, warm palette, lucide-react icons

---

## 2026-02-01 - client-onboarding-v2-c3y.78
- **What was implemented**: Phase 5B Internal link insertion (Related + See Also rows) - ALREADY COMPLETE
- **Files verified**:
  - `app/services/content_writer.py` - Full implementation with `InternalLink` dataclass, `_format_links()`, prompt template with link sections
  - `app/services/related_collections.py` - Jaccard similarity service for finding related collections
  - `app/api/v1/endpoints/content_writer.py` - API endpoint with link conversion
  - `app/schemas/content_writer.py` - `InternalLinkItem` schema for API
- **Learnings:**
  - Phase 5B was already fully implemented with comprehensive error logging
  - All ERROR LOGGING REQUIREMENTS met: entry/exit DEBUG, exceptions with stack traces, entity IDs, validation failures, state transitions at INFO, slow operation warnings
  - Links are capped at 3 per category in `_format_links()` method
  - Lint/type checks pass for all Phase 5B files
---

## 2026-02-01 - client-onboarding-v2-c3y.120
- **What was implemented**: ProjectListPage with create button and search
- **Files changed**:
  - `frontend/src/pages/ProjectListPage.tsx` - New page component with search, create button, project grid, loading/error/empty states
  - `frontend/src/App.tsx` - Added route for `/projects` with ErrorBoundary
- **Learnings:**
  - Frontend uses React Query (`useApiQuery` hook) for data fetching with typed endpoints
  - Page components follow pattern: loading skeletons, error states, empty states, content grid
  - `addBreadcrumb` from `errorReporting.ts` used for user action tracking
  - Routes wrapped in `ErrorBoundary` with `componentName` prop for error context
  - UI components: `Button` (shadcn pattern), `Input` from form-field, `ProjectCard/ProjectCardSkeleton`
  - Design system: warm palette (cream-50 bg, warmgray text), soft shadows, rounded corners (rounded-xl/2xl)
  - lucide-react for icons (Plus, Search)
---

