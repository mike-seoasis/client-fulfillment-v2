## 1. Backend API Endpoints

- [ ] 1.1 Add cross-project comment queue endpoint `GET /api/v1/reddit/comments` with status/project_id/search/limit/offset filters, eager-load post + project name, order by created_at desc
- [ ] 1.2 Add approve endpoint `POST /api/v1/projects/{project_id}/reddit/comments/{id}/approve` — draft→approved, optional body edit, 400 if not draft
- [ ] 1.3 Add reject endpoint `POST /api/v1/projects/{project_id}/reddit/comments/{id}/reject` — draft→rejected, required reason, 400 if not draft
- [ ] 1.4 Add bulk approve endpoint `POST .../comments/bulk-approve` — approve multiple drafts, skip non-drafts, return approved_count
- [ ] 1.5 Add bulk reject endpoint `POST .../comments/bulk-reject` — reject multiple drafts with shared reason, return rejected_count

## 2. Frontend API Client & Hooks

- [ ] 2.1 Add `fetchCommentQueue` API function with filter params (status, project_id, search, limit, offset)
- [ ] 2.2 Add `approveComment`, `rejectComment`, `bulkApproveComments`, `bulkRejectComments` API functions
- [ ] 2.3 Add `useCommentQueue` TanStack Query hook with filter params
- [ ] 2.4 Add `useApproveComment` mutation hook with optimistic removal from queue
- [ ] 2.5 Add `useRejectComment` mutation hook with optimistic removal from queue
- [ ] 2.6 Add `useBulkApprove` and `useBulkReject` mutation hooks with optimistic removal

## 3. Comment Queue Page Layout

- [ ] 3.1 Create `/reddit/comments/page.tsx` with split-view layout (60/40 left/right panels)
- [ ] 3.2 Add status filter tabs (Draft/Approved/Rejected/All) with count badges
- [ ] 3.3 Add filter bar with project dropdown and search input
- [ ] 3.4 Add "Comments" link to Reddit section header navigation

## 4. Comment List & Cards

- [ ] 4.1 Build comment card component with project badge, subreddit tag, truncated body, approach badge, promo/organic indicator, timestamp
- [ ] 4.2 Implement selected comment highlighting and click-to-select
- [ ] 4.3 Build post context panel (right side) showing subreddit, post title, snippet, Reddit link, and full comment body

## 5. Keyboard Shortcuts

- [ ] 5.1 Implement j/k navigation (move selection up/down, auto-scroll into view, update right panel)
- [ ] 5.2 Implement `a` to approve selected comment, `r` to open reject flow, `x` to toggle bulk selection
- [ ] 5.3 Guard shortcuts so they don't fire when textarea/input is focused

## 6. Inline Editing & Reject Flow

- [ ] 6.1 Implement inline edit mode (`e` key or button): textarea in right panel with word/char count, Cmd+Enter to save+approve, Escape to cancel
- [ ] 6.2 Implement reject reason picker: quick-pick options (Off-topic, Too promotional, Doesn't match voice, Low quality, Other) with freeform fallback

## 7. Bulk Actions

- [ ] 7.1 Implement bulk selection state (Set of selected IDs), `x` toggle per comment, select-all checkbox
- [ ] 7.2 Build floating action bar at bottom of left panel: "Approve Selected (N)" / "Reject Selected (N)" buttons, visible when selection count > 0
- [ ] 7.3 Wire bulk approve/reject to mutation hooks with optimistic removal and selection clearing

## 8. Polish & Verification

- [ ] 8.1 Add toast notifications for approve/reject/bulk actions (success + error)
- [ ] 8.2 Add empty states (no comments in tab, no comment selected)
- [ ] 8.3 Auto-select next comment after approve/reject so keyboard flow is uninterrupted
- [ ] 8.4 Update V2_REBUILD_PLAN.md with Phase 14d completion
