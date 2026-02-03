## Context

Phase 0 established:
- Backend: FastAPI with SQLAlchemy 2.0 async, existing Project model (missing `site_url`)
- Frontend: Next.js 14 App Router with Tailwind, currently boilerplate
- Infrastructure: Docker dev environment, CI/CD pipeline, uv package manager

Current Project model has: `id`, `name`, `client_id`, `status`, `phase_status`, `brand_wizard_state`, timestamps. Missing `site_url` required by FEATURE_SPEC.

Frontend is default Next.js template — needs complete replacement with dashboard and project views.

## Goals / Non-Goals

**Goals:**
- Establish the project CRUD API pattern that subsequent phases will follow
- Create reusable UI components (cards, forms, layout) for the design system
- Set up TanStack Query patterns for data fetching
- Deliver working dashboard → create → detail flow

**Non-Goals:**
- Brand configuration (Phase 2)
- File uploads (Phase 2)
- Onboarding workflow functionality (Phase 3+)
- Cluster creation functionality (Phase 8)
- Authentication (deferred, single user for MVP)
- Real-time updates (polling patterns come later)

## Decisions

### 1. API Structure: RESTful under `/api/v1/projects`

**Decision:** Standard REST endpoints with versioned API prefix.

```
GET    /api/v1/projects          # List all projects
POST   /api/v1/projects          # Create project
GET    /api/v1/projects/{id}     # Get single project
PATCH  /api/v1/projects/{id}     # Update project
DELETE /api/v1/projects/{id}     # Delete project
```

**Alternatives considered:**
- GraphQL: Overkill for MVP, adds complexity
- No versioning: Harder to evolve API later

**Rationale:** REST is simple, well-understood, matches FastAPI patterns. Version prefix allows future API evolution.

### 2. Database: Add `site_url` via Alembic migration

**Decision:** Add `site_url: str` (required, indexed) to Project model. Keep `client_id` for now but make it optional (will remove in future cleanup).

**Migration approach:**
1. Add column as nullable first
2. Backfill any existing data (unlikely in fresh rebuild)
3. Set NOT NULL constraint

**Rationale:** Alembic handles migrations cleanly. Index on `site_url` supports future duplicate checking.

### 3. Frontend Routing: Next.js App Router structure

**Decision:**
```
frontend/src/app/
├── page.tsx                    # Dashboard (project list)
├── layout.tsx                  # Root layout with header
├── projects/
│   ├── new/
│   │   └── page.tsx           # Create project form
│   └── [id]/
│       └── page.tsx           # Project detail view
```

**Alternatives considered:**
- Pages under `/dashboard/*`: Adds unnecessary nesting
- Single page with modals: Loses URL shareability, back button behavior

**Rationale:** Clean URLs (`/`, `/projects/new`, `/projects/{id}`), standard Next.js patterns, good UX with browser navigation.

### 4. Data Fetching: TanStack Query v5

**Decision:** Use TanStack Query for all server state with these patterns:
- `useQuery` for reads (list, detail)
- `useMutation` for writes (create, update, delete)
- Query invalidation on mutations
- Optimistic updates for delete (with rollback)

**Query keys:**
```typescript
['projects']           // List
['projects', id]       // Single project
```

**Rationale:** Industry standard, handles caching/refetching/loading states, integrates well with Next.js.

### 5. Component Architecture

**Decision:** Flat component structure, no premature abstraction:
```
frontend/src/components/
├── ui/                        # Primitive UI components
│   ├── Button.tsx
│   ├── Input.tsx
│   ├── Card.tsx
│   └── ...
├── ProjectCard.tsx            # Dashboard card
├── ProjectForm.tsx            # Create/edit form
├── Header.tsx                 # App header with nav
└── EmptyState.tsx             # No projects state
```

**Alternatives considered:**
- Feature folders (`features/projects/components/`): Premature for MVP size
- Barrel exports: Adds maintenance overhead

**Rationale:** Keep it simple. Extract shared patterns only when duplication emerges.

### 6. Form Handling: React Hook Form + Zod

**Decision:** Use React Hook Form with Zod schema validation.

**Rationale:** Type-safe validation, good DX, minimal re-renders. Zod schemas can be shared with backend for consistency.

### 7. Styling: Tailwind with Design Tokens

**Decision:** Tailwind utility classes with custom theme extending warm color palette per design context:
- Primary: Warm gold/amber tones
- Neutrals: Warm grays
- Accent: Soft coral

**Rationale:** Matches design brief ("warm, airy, sophisticated"). Tailwind config centralizes tokens.

### 8. Delete Confirmation: Two-step inline

**Decision:** Delete button shows confirmation inline (not modal). Click once to reveal "Confirm delete", click again to execute.

**Alternatives considered:**
- Modal dialog: Heavier, interrupts flow
- Type-to-confirm: Overkill for project cards (reserved for destructive bulk actions per FEATURE_SPEC)

**Rationale:** Quick but safe. Matches "two-step for items" decision in architecture doc.

## Risks / Trade-offs

**[Risk] No loading skeletons initially** → Accept for Phase 1, add polish in Phase 9. TanStack Query's `isLoading` state is sufficient.

**[Risk] No error boundaries** → Add basic error boundary in root layout. Detailed error handling in Phase 9.

**[Risk] `client_id` field is vestigial** → Keep as optional for now, document for cleanup. Removing requires migration coordination.

**[Trade-off] No optimistic create** → Creates wait for server response. Acceptable for MVP — optimistic updates add complexity and create requires server-generated ID.

**[Trade-off] No pagination** → Fine for MVP scale (< 50 projects). Add cursor pagination when needed.

## Open Questions

1. **Metrics on project cards**: Dashboard shows "pages", "clusters", "pending" counts. These don't exist yet. **Decision:** Show placeholder "—" or "0" until Phase 3+ populates real data.

2. **Project deletion cascade**: When deleting a project, what happens to associated data (crawled pages, content, etc.)? **Decision:** For Phase 1, projects have no children. Add cascade behavior as children are introduced in later phases.
