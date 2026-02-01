# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Integration Client Pattern
All API integration clients follow a consistent pattern in `/backend/app/integrations/`:
1. **Configuration**: Settings in `app/core/config.py` with prefix naming (e.g., `google_nlp_api_key`, `google_nlp_timeout`)
2. **Logger**: Dedicated logger class in `app/core/logging.py` with methods for API calls, errors, circuit breaker events
3. **Client Class**: Async client with circuit breaker, retry logic, exponential backoff
4. **Global Instance**: Module-level client with `init_*`, `close_*`, and `get_*` dependency functions
5. **Error Classes**: Hierarchy of custom exceptions (Base, Timeout, RateLimit, Auth, CircuitOpen)

### Error Logging Requirements
- Log all outbound API calls with endpoint, method, timing at DEBUG level
- Log request/response bodies at DEBUG level (truncate large responses)
- Log 4xx errors at WARNING level, 5xx at ERROR level
- Include retry attempt number in logs
- Mask API keys and tokens in all logs

### Frontend Component Pattern
React components in `/frontend/src/components/` follow consistent patterns:
1. **Type definitions**: Types/interfaces for props, API responses, and form state at top of file
2. **Constants**: Default values, status configs, color mappings defined before components
3. **Utility functions**: Pure helper functions (formatters, validators) before components
4. **Sub-components**: Internal components (badges, cards, items) before main export
5. **Main component**: Single named export with comprehensive JSDoc
6. **Hooks usage**: useApiQuery for data fetching, useToastMutation for mutations with notifications, useProjectSubscription for WebSocket updates

### Error Handling in Frontend
- Use ErrorBoundary for route-level error catching (see App.tsx pattern)
- Log API errors with full context: endpoint, status, response body, user action
- Use addBreadcrumb for tracking user navigation/actions
- Form validation logged at debug level with field names
- Toast notifications for mutation success/failure via useToastMutation

---

## 2026-02-01 - client-onboarding-v2-c3y.124
- **What was implemented**: CrawlPhasePanel component with configuration form and progress display
- **Files changed**:
  - `frontend/src/components/CrawlPhasePanel.tsx` - NEW: Complete crawl phase panel component
- **Learnings:**
  - Crawl API endpoints follow pattern: `/api/v1/projects/{project_id}/phases/crawl`
  - Backend crawl schemas in `backend/app/schemas/crawl.py` define: CrawlStartRequest, CrawlHistoryResponse, CrawlProgressResponse
  - useApiQuery with refetchInterval for polling active crawl progress
  - useToastMutation wraps mutations with automatic success/error toast notifications
  - Form state pattern: separate state for values, errors, touched fields
  - Pattern arrays (include/exclude) stored as newline-separated strings in form, parsed to arrays on submit
---

## 2026-02-01 - client-onboarding-v2-c3y.88
- **What was implemented**: Google Cloud NLP integration client for entity extraction
- **Files changed**:
  - `backend/app/core/config.py` - Added Google Cloud NLP settings (api_key, project_id, timeout, max_retries, retry_delay, circuit breaker settings)
  - `backend/app/core/logging.py` - Added GoogleNLPLogger class with comprehensive logging methods
  - `backend/app/integrations/google_nlp.py` - NEW: Complete async client with entity extraction capabilities
- **Learnings:**
  - Integration clients follow a strict pattern: config settings -> logger -> client class -> global instance management
  - Circuit breaker pattern is consistent across all integrations with CLOSED/OPEN/HALF_OPEN states
  - Google Cloud NLP API uses API key as query parameter (`?key=`) rather than header auth
  - Entity extraction returns entities with: name, type (EntityType enum), salience score, mentions, metadata
---

