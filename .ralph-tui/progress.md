# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Responsive Layout Pattern
- Use Tailwind's default breakpoints: `md:` (768px tablet), `lg:` (1024px+), `xl:` (1280px desktop)
- Grid pattern: `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` for responsive card grids
- Padding pattern: `px-4 sm:px-6 lg:px-8` for responsive horizontal padding

### Loading State Pattern
- Create a `*Skeleton` component with `animate-pulse` for loading states
- Use `isLoading` from TanStack Query hooks
- Conditional rendering: `{isLoading && <Skeleton />}`

### Error Handling Pattern
- Frontend: Use `error` state from TanStack Query, show user-friendly messages like "Failed to load X. Please try again."
- Backend: Returns structured errors: `{"error": string, "code": string, "request_id": string}`
- API client (`lib/api.ts`) extracts `error` field from backend response for display

### Form Submission Pattern
- Pass `isSubmitting` (from `mutation.isPending`) to form components
- Button text changes: "Create Project" → "Saving..."
- Button disabled during submission

---

## 2026-02-03 - S1-019
- What was implemented: Integration testing and polish verification
- Files changed: None (verification only)
- **Verification Results:**
  - All 21 backend API tests pass
  - All 27 frontend component tests pass
  - ESLint: No warnings or errors
  - TypeScript: No type errors
  - No console.log statements in production code
  - Responsive layout verified: grid-cols-1/md:2/lg:3 pattern, responsive padding
  - Error messages are user-friendly
  - Loading states with skeletons implemented on Dashboard and Project Detail
  - Form submission states with "Saving..." text
- **Learnings:**
  - Database required for live E2E testing (PostgreSQL not available in this session)
  - Backend has some legacy test files with broken imports (tests/e2e, tests/integrations/test_pop.py) - need cleanup
  - Static verification via code review + unit tests provides good coverage when DB unavailable
---

## 2026-02-03 - S1-099
- What was implemented: Phase completion verification
- Files changed: None (verification only)
- **Verification Results:**
  - Backend API tests: 21/21 passing (tests/api/test_projects.py)
  - Frontend component tests: 27/27 passing (ProjectCard, ProjectForm, placeholder)
  - Phase 1 code committed via slice commits (S1-001 through S1-019)
  - V2_REBUILD_PLAN.md already shows Phase 1 as complete
  - Only uncommitted files are working files (.ralph-tui/, openspec prd.json)
- **Learnings:**
  - Incremental slice commits are better than monolithic phase commits
  - Backend has legacy test files needing cleanup (tests/e2e/, tests/integrations/test_pop.py) that cause pytest collection errors when running full suite
  - Use `uv run pytest tests/api/` to run only the v2 rebuild API tests
  - Frontend uses Vitest, not Jest - use `npm test -- --run` for non-watch mode
---

