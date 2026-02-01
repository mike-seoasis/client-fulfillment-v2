# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Pattern
- Services use dataclasses for result types with `to_dict()` methods
- Global singleton pattern via `_service: T | None = None` and `get_*_service()` function
- Comprehensive logging with `extra={}` dict containing context (project_id, page_id, etc.)
- Slow operation threshold logged at WARNING (>1000ms)
- Phase transitions logged at INFO level

### Error Logging Requirements
- Method entry/exit at DEBUG level with parameters (sanitized)
- All exceptions with full stack trace via `traceback.format_exc()`
- Entity IDs (project_id, page_id) in all service logs
- Validation failures with field names and rejected values
- Timing logs for operations >1 second

### Schema Pattern
- Use Pydantic BaseModel with Field() for all properties
- Include docstring with Error Logging Requirements and Railway Deployment Requirements
- Use `field_validator` for input validation
- Always include `description` in Field()

### Frontend Component Pattern
- Component files should only export React components (functions returning JSX)
- Utility functions and constants go in `lib/` directory to satisfy `react-refresh/only-export-components` lint rule
- Use `cn()` from `@/lib/utils` for conditional Tailwind class merging
- Include JSDoc comments with `@example` usage patterns
- Provide skeleton loading states as companion exports (e.g., `PhaseProgressSkeleton`)
- Accessibility: include `aria-*` attributes and `title` tooltips

---

## 2026-02-01 - client-onboarding-v2-c3y.115
- What was implemented:
  - PhaseProgress component for visualizing project phase status
  - Color-coded status indicators (pending, in_progress, completed, blocked, skipped)
  - Three size variants (sm, md, lg)
  - Optional labels showing current phase and completion percentage
  - Animated pulse effect for active (in_progress) phases
  - PhaseProgressSkeleton loading state component
  - Shared phase utilities (types, constants, helper functions)

- Files changed:
  - `frontend/src/components/PhaseProgress.tsx` (NEW) - Main component with skeleton
  - `frontend/src/lib/phaseUtils.ts` (NEW) - Shared phase types and utility functions

- **Learnings:**
  - ESLint `react-refresh/only-export-components` rule prevents mixing component and utility exports in same file
  - Solution: Create separate `lib/*.ts` files for shared utilities, import into components
  - `role="progressbar"` with `aria-valuenow/min/max` provides screen reader accessibility
  - Re-exporting utilities from component files still triggers the lint warning; import directly from utils instead

---

## 2026-02-01 - client-onboarding-v2-c3y.73
- What was implemented:
  - Phase 5A: PAA analysis by intent categorization service
  - Groups PAA questions by intent category (buying, usage, care, comparison)
  - Prioritizes questions per content-generation spec (buying → care → usage)
  - Determines content angle recommendation based on question distribution
  - Calculates intent distribution percentages

- Files changed:
  - `backend/app/services/paa_analysis.py` (NEW) - Core analysis service
  - `backend/app/schemas/paa_analysis.py` (NEW) - Request/response schemas

- **Learnings:**
  - PAA categorization is separate from PAA analysis - categorization assigns intent to questions, analysis groups and prioritizes them
  - Content angle determination follows spec rules: more care questions = longevity focus, more buying = purchase focus
  - Priority order: buying (highest) → care → usage → comparison
  - All dataclasses need `to_dict()` for serialization compatibility
  - Import `get_paa_categorization_service` inside method to avoid circular imports

---

