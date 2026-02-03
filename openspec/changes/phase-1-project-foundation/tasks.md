## 1. Database & Model

- [ ] 1.1 Add `site_url` field to Project model (String, required, indexed)
- [ ] 1.2 Make `client_id` field optional (nullable) for backward compatibility
- [ ] 1.3 Create Alembic migration for schema changes
- [ ] 1.4 Run migration and verify database schema

## 2. Backend Schemas

- [ ] 2.1 Create `ProjectCreate` schema (name: str, site_url: HttpUrl)
- [ ] 2.2 Create `ProjectUpdate` schema (name: Optional, site_url: Optional)
- [ ] 2.3 Create `ProjectResponse` schema (id, name, site_url, status, created_at, updated_at)
- [ ] 2.4 Create `ProjectListResponse` schema (list of ProjectResponse)

## 3. Backend Service Layer

- [ ] 3.1 Create `ProjectService` class in `backend/app/services/project.py`
- [ ] 3.2 Implement `list_projects()` - returns all projects ordered by updated_at desc
- [ ] 3.3 Implement `get_project(id)` - returns single project or raises NotFound
- [ ] 3.4 Implement `create_project(data)` - creates and returns new project
- [ ] 3.5 Implement `update_project(id, data)` - updates and returns project
- [ ] 3.6 Implement `delete_project(id)` - deletes project or raises NotFound

## 4. Backend API Router

- [ ] 4.1 Create `/api/v1/projects` router in `backend/app/api/v1/projects.py`
- [ ] 4.2 Implement `GET /api/v1/projects` - list all projects
- [ ] 4.3 Implement `POST /api/v1/projects` - create project
- [ ] 4.4 Implement `GET /api/v1/projects/{id}` - get single project
- [ ] 4.5 Implement `PATCH /api/v1/projects/{id}` - update project
- [ ] 4.6 Implement `DELETE /api/v1/projects/{id}` - delete project
- [ ] 4.7 Register router in main app with `/api/v1` prefix

## 5. Backend Tests

- [ ] 5.1 Create test fixtures for Project in `conftest.py`
- [ ] 5.2 Write tests for ProjectService (all CRUD operations)
- [ ] 5.3 Write tests for projects API endpoints (happy paths)
- [ ] 5.4 Write tests for API error cases (404, 422 validation)
- [ ] 5.5 Verify all backend tests pass

## 6. Frontend Setup

- [ ] 6.1 Install and configure TanStack Query v5
- [ ] 6.2 Create QueryClientProvider wrapper in layout
- [ ] 6.3 Create API client utility (`frontend/src/lib/api.ts`)
- [ ] 6.4 Create project API hooks (`useProjects`, `useProject`, `useCreateProject`, `useDeleteProject`)
- [ ] 6.5 Configure Tailwind theme with warm color palette

## 7. Frontend Layout & Components

- [ ] 7.1 Create `Header` component with logo placeholder and app name
- [ ] 7.2 Create `Button` component with variants (primary, secondary, danger)
- [ ] 7.3 Create `Input` component with label and error state
- [ ] 7.4 Create `Card` component with hover state
- [ ] 7.5 Create `EmptyState` component for no-data scenarios
- [ ] 7.6 Update root layout with Header and main content area

## 8. Dashboard Page

- [ ] 8.1 Replace boilerplate `page.tsx` with dashboard layout
- [ ] 8.2 Create `ProjectCard` component showing name, URL, metrics placeholders, last activity
- [ ] 8.3 Implement project grid with responsive columns
- [ ] 8.4 Add "+ New Project" button linking to `/projects/new`
- [ ] 8.5 Add empty state when no projects exist
- [ ] 8.6 Add loading state while fetching projects

## 9. Create Project Page

- [ ] 9.1 Create `/projects/new/page.tsx` route
- [ ] 9.2 Create `ProjectForm` component with React Hook Form + Zod
- [ ] 9.3 Implement name field (required, min 1 char)
- [ ] 9.4 Implement site URL field (required, valid URL format)
- [ ] 9.5 Add form submission with loading state
- [ ] 9.6 Redirect to project detail on successful creation
- [ ] 9.7 Add Cancel button returning to dashboard

## 10. Project Detail Page

- [ ] 10.1 Create `/projects/[id]/page.tsx` route
- [ ] 10.2 Create project header with name, URL, back link
- [ ] 10.3 Create Onboarding section with placeholder status and disabled button
- [ ] 10.4 Create New Content section with disabled "+ New Cluster" placeholder
- [ ] 10.5 Add disabled "Edit Brand" button with tooltip
- [ ] 10.6 Implement two-step delete confirmation
- [ ] 10.7 Add 404 handling for invalid project IDs

## 11. Frontend Tests

- [ ] 11.1 Write Vitest tests for ProjectCard component
- [ ] 11.2 Write Vitest tests for ProjectForm validation
- [ ] 11.3 Write Vitest tests for delete confirmation behavior
- [ ] 11.4 Verify all frontend tests pass

## 12. Integration & Verification

- [ ] 12.1 Test full flow: create project → view dashboard → view detail → delete
- [ ] 12.2 Verify responsive layout on mobile/tablet/desktop
- [ ] 12.3 Verify API error handling displays user-friendly messages
- [ ] 12.4 Update V2_REBUILD_PLAN.md with Phase 1 completion status
- [ ] 12.5 Create commit with `feat(phase-1): Project foundation - dashboard, create, detail views`
