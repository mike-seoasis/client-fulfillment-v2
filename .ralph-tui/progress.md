# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Redis Cache Service Pattern
When creating new cache services, follow the established pattern in `backend/app/services/paa_cache.py`:

1. **Structure**:
   - `CacheStats` dataclass for hit/miss/error tracking
   - `CachedXxxData` dataclass for the cached payload
   - `XxxCacheResult` dataclass for operation results
   - Custom exceptions (`XxxCacheError`, `XxxCacheValidationError`)
   - Main service class with `get()`, `set()`, `delete()`, `get_ttl()`, `get_stats_summary()`
   - Global singleton via `get_xxx_cache_service()` function

2. **Key Format**: `prefix:{id}:{type}:{hash}` - use SHA256 truncated to 16 chars for long values (URLs, keywords)

3. **TTL Configuration**: Add to `backend/app/core/config.py` as `xxx_cache_ttl_days: int = Field(default=N, ...)`

4. **Logging Requirements**:
   - DEBUG: method entry/exit, parameters (sanitized), cache hits/misses with duration_ms
   - WARNING: slow operations (>1000ms), validation failures, cache set failures
   - ERROR: exceptions with full stack trace, error_type, context (entity IDs)

5. **Graceful Degradation**: Always check `self.available` (Redis unavailable = continue without cache)

### Frontend Panel Component Pattern
When creating new panel components in `frontend/src/components/`, follow the established pattern in `KeywordResearchPanel.tsx` or `PAAEnrichmentPanel.tsx`:

1. **Structure**:
   - Types section with interfaces for API responses
   - Constants section with default values and options
   - Sub-components (StatsCard, ProgressBar, etc.) defined inline
   - Main component with Props interface exported
   - Uses `useApiQuery` for data fetching, `useToastMutation` for mutations

2. **Collapsible Sections**: Use local `useState` for `showXxx` state, button with ChevronUp/ChevronDown icons

3. **Stats Cards**: Use consistent StatsCard sub-component with icon, label, value, and variant (default/success/warning)

4. **Form Fields**: Wrap inputs with `FormField` component for consistent label, helperText, and error display

5. **Error Handling**: Use `addBreadcrumb` for user actions, log errors with component context

6. **API Calls**: Use relative paths `/api/v1/projects/{projectId}/phases/{phase}/...` with userAction and component options

---

## 2026-02-01 - client-onboarding-v2-c3y.93
- What was implemented: Competitor analysis caching service with 7-day TTL
- Files changed:
  - `backend/app/core/config.py` - Added `competitor_analysis_cache_ttl_days` setting (default: 7 days)
  - `backend/app/services/competitor_analysis_cache.py` - New cache service following PAA cache pattern
- **Learnings:**
  - Patterns discovered: Redis cache services follow a well-established pattern (see Codebase Patterns above)
  - The cache key includes competitor_id, analysis_type, and URL hash for flexibility (different analysis types per competitor)
  - Existing Redis infrastructure handles Railway deployment requirements (SSL/TLS, circuit breaker, retry logic) automatically via `redis_manager`
  - Config settings use Pydantic Fields with defaults - TTL stored in days but converted to seconds internally

---

## 2026-02-01 - client-onboarding-v2-c3y.129
- What was implemented: BrandConfigPanel with document upload and brand configuration editor
- Files changed:
  - `frontend/src/components/BrandConfigPanel.tsx` - New panel component with:
    - Document upload via drag-and-drop (PDF, DOCX, TXT)
    - File-to-base64 conversion for API submission
    - Brand synthesis via Claude LLM endpoint
    - V2 schema editor for colors, typography, voice/tone, social media
    - Inline color picker with ColorSwatch component
    - Personality tags input with add/remove functionality
  - `frontend/src/pages/ProjectDetailPage.tsx` - Integrated BrandConfigPanel into project detail view
- **Learnings:**
  - Patterns discovered: Panel components follow a consistent collapsible section pattern with StatsCard overview
  - File upload requires base64 encoding before submission to the brand synthesis API
  - The brand_config API endpoints follow `/api/v1/projects/{projectId}/phases/brand_config/...` pattern
  - V2 schema has nested objects: colors, typography, logo, voice, social
  - Unused imports/variables cause TypeScript errors with strict settings - always clean up

---

