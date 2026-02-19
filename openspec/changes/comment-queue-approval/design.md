## Context

Phase 14c delivered per-project comment generation with inline display. Arly now needs a cross-project review queue where she can approve/edit/reject comments at speed. The RedditComment model already has `status` (draft/approved/rejected/submitting/posted/failed/mod_removed), `reject_reason`, and all needed fields. Pydantic schemas for approve/reject/bulk already exist in `reddit.py`. No migration needed.

## Goals / Non-Goals

**Goals:**
- Cross-project comment queue API with filtering (status, project, niche, search)
- Approve/reject/bulk endpoints with proper status transition guards
- Split-view frontend page at `/reddit/comments` optimised for speed
- Keyboard shortcuts (j/k/a/e/r/x) for power-user review workflow
- Inline editing with Cmd+Enter save+approve
- Optimistic UI updates for all mutations

**Non-Goals:**
- CrowdReply submission (Phase 14e)
- Comment analytics or stats dashboard (Phase 14f)
- Auto-approval rules or ML scoring
- Real-time multi-user collaboration / locking

## Decisions

### 1. Cross-project query on the global reddit router

Add `GET /api/v1/reddit/comments` to the existing `reddit_global_router` (same router as accounts). Returns comments across all projects with optional filters: `status`, `project_id`, `niche`, `search`. Eager-loads the post relationship (and post's project name) so the frontend gets everything in one call. Paginated with `limit`/`offset` (default 50).

**Why not per-project?** Arly reviews across all clients. A global endpoint avoids N+1 frontend calls.

### 2. Approve/reject on the project-scoped router

Keep approve/reject/bulk on the existing `reddit_project_router` (`/api/v1/projects/{project_id}/reddit/comments/...`). This matches the existing PATCH/DELETE pattern and keeps project_id in the URL for authorization.

- `POST .../comments/{id}/approve` — draft→approved, optional body edit
- `POST .../comments/{id}/reject` — draft→rejected, required reason
- `POST .../comments/bulk-approve` — bulk draft→approved
- `POST .../comments/bulk-reject` — bulk draft→rejected, shared reason

Guards: only `draft` status can be approved/rejected. Return 400 for wrong status.

### 3. Single page component (no extracted components)

Follow the existing pattern used for the Reddit config page — everything in one `page.tsx` file. The page is complex but self-contained. Extract components only if the file becomes unmanageable.

### 4. Keyboard handling via useEffect on document

Register keyboard event listeners at the document level within the queue page. Track `selectedIndex` for j/k navigation. Guard shortcuts so they don't fire when a textarea/input is focused (for inline editing). Cmd+Enter handled locally in the edit textarea's onKeyDown.

### 5. Optimistic updates for approve/reject

Use TanStack Query `onMutate` to instantly remove the comment from the current status tab (e.g., removing from "Draft" list on approve). Snapshot for rollback on error. Invalidate on settle.

### 6. Split-view layout

Left panel (60%): scrollable comment list with sticky filter bar at top.
Right panel (40%): selected comment's post context (subreddit, title, snippet, Reddit link). Sticky panel that updates as selection changes. Show empty state when nothing is selected.

## Risks / Trade-offs

- **Large query without pagination** → Mitigated by `limit`/`offset` defaults (50 per page) and status filter (most users view "draft" tab which is a small set)
- **Keyboard shortcuts conflict with browser/OS** → Mitigated by only activating when no input is focused, using single keys (not Cmd+key except for Cmd+Enter in edit mode and Cmd+A for select all)
- **Optimistic removal animation** → Keep it simple with CSS transitions; skip complex animation libraries
