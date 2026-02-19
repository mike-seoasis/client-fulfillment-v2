## Why

Arly reviews every AI-generated comment before it goes to CrowdReply. Right now comments only live inside each project's Reddit config page — there's no cross-project view and no fast review workflow. She needs a dedicated, keyboard-driven queue where she can rip through 50+ comments in a session: scan the post context, approve/edit/reject, and move on. Speed is the #1 design goal.

## What Changes

- New cross-project comment queue API endpoint (`GET /api/v1/reddit/comments`) with status/project/niche filters and post context eager-loaded
- Approve endpoint (`POST .../comments/{id}/approve`) — transitions draft→approved, optionally saves an edited body
- Reject endpoint (`POST .../comments/{id}/reject`) — transitions draft→rejected with a reason
- Bulk approve/reject endpoints for batch processing
- New `/reddit/comments` frontend page with split-view layout (comment list + post context panel)
- Keyboard shortcuts for power-user navigation (j/k, a, e, r, x for bulk select)
- Inline editing with word/character count, Cmd+Enter to save+approve
- Reject flow with quick-pick reasons + freeform text
- Floating bulk action bar when multiple comments are selected
- Optimistic UI updates for approve/reject/bulk actions via TanStack Query

## Capabilities

### New Capabilities
- `comment-queue-api`: Cross-project comment queue endpoint, approve/reject/bulk endpoints with status transition logic
- `comment-queue-ui`: Split-view comment review page with keyboard shortcuts, inline editing, reject flow, bulk actions, and optimistic updates

### Modified Capabilities
(none — existing per-project comment endpoints from 14c remain unchanged)

## Impact

- **Backend:** New router or extend existing reddit router with cross-project comment query + 4 approval endpoints. RedditComment model already has `status`, `reject_reason` fields — no migration needed.
- **Frontend:** New page at `/reddit/comments`, new hooks for queue query + approve/reject mutations, keyboard event handling. Existing per-project comment hooks from `useReddit.ts` untouched.
- **API types:** New Pydantic schemas for approve/reject requests and queue response (comment + post context joined).
