# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Integration Client Pattern
All external API clients (`/backend/app/integrations/`) follow this standard structure:
1. **Configuration** from `core/config.py` via Pydantic Settings (env vars)
2. **Circuit Breaker** class with 3 states (CLOSED/OPEN/HALF_OPEN)
3. **Retry logic** with exponential backoff (`retry_delay * 2^attempt`)
4. **Lazy initialization** via async `get_*()` dependency functions
5. **Dedicated logger** from `core/logging.py` (e.g., `perplexity_logger`, `claude_logger`)
6. **Dataclass result types** for typed responses with success/error/metadata
7. **Request ID tracking** via `request.state.request_id` passed through all layers

### Error Response Format
All endpoints return structured errors: `{"error": str, "code": str, "request_id": str}`

### Frontend Component Pattern
All frontend components (`/frontend/src/components/`) follow this standard structure:
1. **TypeScript interfaces** for all props with JSDoc comments
2. **`cn()` utility** from `@/lib/utils` for class merging (clsx + tailwind-merge)
3. **`addBreadcrumb()`** from `@/lib/errorReporting` for user action tracking
4. **Skeleton components** exported alongside main component for loading states
5. **Keyboard navigation** support (tabIndex, onKeyDown for Enter/Space)
6. **ARIA attributes** for accessibility (role, aria-label, aria-selected, etc.)
7. **Warm design tokens** - cream-*, warmgray-*, primary-*, soft shadows

---

## 2026-02-01 - client-onboarding-v2-c3y.116
- **What was implemented**: DataTable component for page listings with sorting, filtering, selection
- **Files changed**:
  - `frontend/src/components/DataTable.tsx` (NEW) - Full DataTable implementation (~450 lines)
- **Implementation includes**:
  - Generic `<T>` typing for flexible data structures
  - Sortable columns with visual indicators (asc/desc/none)
  - Search/filter functionality with customizable filter function
  - Row selection with select-all checkbox (including indeterminate state)
  - Click handlers for row interaction
  - Loading skeleton state with configurable row count
  - Empty state with icon and customizable messages
  - DataTableSkeleton component for pre-load state
  - Full keyboard navigation (Enter/Space on headers and rows)
  - ARIA attributes (aria-sort, aria-selected, role="button")
- **Learnings:**
  - Use `cn()` consistently for all conditional class names
  - Skeleton states should match the structure of the loaded component
  - Custom checkbox with ref callback for indeterminate state (`el.indeterminate = true`)
  - Column definitions use accessor functions for flexibility: `accessor: (row: T) => ReactNode`
  - Sort function allows custom comparisons via optional `sortFn` property
---

## 2026-02-01 - client-onboarding-v2-c3y.74
- **What was implemented**: Verified Phase 5A Perplexity research integration is ALREADY COMPLETE
- **Files reviewed** (no changes needed):
  - `backend/app/integrations/perplexity.py` - Full Perplexity client implementation (809 lines)
  - `backend/app/core/config.py` - Perplexity settings (lines 153-180)
  - `backend/app/core/logging.py` - PerplexityLogger class (lines 930-1171)
- **Implementation includes**:
  - CircuitBreaker with CLOSED/OPEN/HALF_OPEN states
  - Retry logic with exponential backoff
  - Complete error handling (timeouts, 429 rate limits, 401/403 auth failures)
  - Token usage logging for quota tracking
  - API key masking (never logged)
  - Request ID tracking via response headers
  - Three main methods: `complete()`, `analyze_website()`, `research_query()`
  - Dependency injection via `get_perplexity()`
- **Learnings:**
  - Integration clients use lazy initialization (no explicit init in main.py lifespan)
  - All env var config via Pydantic Settings with sensible defaults
  - Pre-existing errors in other files (logging.py, redis.py) don't affect perplexity.py
---

