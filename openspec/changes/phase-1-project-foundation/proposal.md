## Why

Phase 0 established the technical foundation (backend cleanup, Docker, Next.js 14, CI/CD). Now we need the core project management capability before building any workflows. Users cannot onboard clients or create content clusters without first creating and managing projects. This is the foundation that all other features depend on.

## What Changes

- **Backend API**: New CRUD endpoints for projects (`/api/projects`) with list, create, get, update, delete operations
- **Database**: Add `site_url` field to existing Project model (currently has `name`, `client_id`, `status`, `phase_status`)
- **Dashboard UI**: Replace Next.js boilerplate with project listing page showing cards with name, URL, metrics placeholders, and last activity
- **Create Project Flow**: Simple form with name (required) and site URL (required) — brand docs/config deferred to Phase 2
- **Project Detail View**: Shell page with sections for Onboarding and New Content (Clusters) — actual functionality in later phases
- **Navigation**: Header with logo, app name, and breadcrumb navigation between dashboard and project views

## Capabilities

### New Capabilities
- `project-management`: CRUD operations for projects (create, read, update, delete, list) with API endpoints and database persistence
- `dashboard`: Main dashboard UI showing project cards with navigation to project details
- `project-detail-view`: Project detail page shell with Onboarding and Clusters sections (placeholders for future phases)

### Modified Capabilities
<!-- None - these are new capabilities -->

## Impact

**Backend:**
- `backend/app/models/project.py` — Add `site_url` field
- `backend/app/schemas/` — New project request/response schemas
- `backend/app/api/` — New `/api/projects` router
- `backend/app/services/` — New project service layer
- Database migration for `site_url` column

**Frontend:**
- `frontend/src/app/page.tsx` — Replace boilerplate with dashboard
- `frontend/src/app/projects/` — New routes for create and detail views
- `frontend/src/components/` — ProjectCard, CreateProjectForm, layout components
- TanStack Query setup for data fetching

**Testing:**
- Backend: pytest tests for API endpoints and service layer
- Frontend: Vitest component tests for ProjectCard, forms
