## ADDED Requirements

### Requirement: Comment queue page at /reddit/comments
The system SHALL provide a page at `/reddit/comments` with a split-view layout: left panel (60%) for the scrollable comment list, right panel (40%) for the selected comment's post context. The page SHALL be linked from the Reddit section header navigation.

#### Scenario: Navigate to comment queue
- **WHEN** user clicks "Comments" in the Reddit section header
- **THEN** system navigates to `/reddit/comments` showing the split-view layout with draft tab selected by default

#### Scenario: Empty queue
- **WHEN** user views the queue with no draft comments
- **THEN** system shows an empty state message in the left panel

### Requirement: Status filter tabs
The page SHALL display filter tabs at the top of the left panel: Draft (default), Approved, Rejected, All. Each tab SHALL show a count badge with the number of comments in that status. Switching tabs SHALL re-fetch comments with the selected status filter.

#### Scenario: Switch to Approved tab
- **WHEN** user clicks the "Approved" tab
- **THEN** system shows only approved comments and the Approved tab is highlighted

#### Scenario: Count badges update after action
- **WHEN** user approves a draft comment
- **THEN** the Draft tab count decreases by 1 and the Approved tab count increases by 1

### Requirement: Filter bar
The page SHALL provide a filter bar below the tabs with: project dropdown (all projects or specific), and text search input for comment body. Filters SHALL combine with the active status tab.

#### Scenario: Filter by project
- **WHEN** user selects a project from the dropdown
- **THEN** system shows only comments for that project within the active status tab

#### Scenario: Search comments
- **WHEN** user types "wellness" in the search input
- **THEN** system shows only comments whose body contains "wellness"

### Requirement: Comment cards in list
Each comment card SHALL display: project name badge, subreddit tag (r/name), comment body (truncated to 3 lines), approach type badge, promotional/organic indicator, status badge, and created-at timestamp. The selected comment SHALL be visually highlighted.

#### Scenario: View comment card
- **WHEN** user views the comment list
- **THEN** each card shows project name, subreddit, truncated body, approach badge, promo/organic badge, and timestamp

#### Scenario: Select a comment
- **WHEN** user clicks a comment card or navigates with j/k
- **THEN** the card is highlighted and the right panel updates with that comment's post context

### Requirement: Post context panel
The right panel SHALL display the selected comment's full post context: subreddit, post title, post snippet/content, link to the original Reddit post, and the full comment body. When no comment is selected, the panel SHALL show an empty state.

#### Scenario: View post context for selected comment
- **WHEN** user selects a comment
- **THEN** the right panel shows the post's subreddit, title, snippet, Reddit URL link, and the full comment text

### Requirement: Keyboard navigation
The page SHALL support keyboard shortcuts when no input/textarea is focused: `j` to move selection down, `k` to move selection up, `a` to approve selected comment, `e` to enter inline edit mode, `r` to open reject flow, `x` to toggle bulk selection on selected comment, `Escape` to cancel edit or deselect.

#### Scenario: Navigate with j/k
- **WHEN** user presses `j` with comment 1 selected
- **THEN** selection moves to comment 2 and the right panel updates

#### Scenario: Approve with keyboard
- **WHEN** user presses `a` with a draft comment selected
- **THEN** the comment is approved and removed from the draft list with the next comment auto-selected

#### Scenario: Shortcuts disabled during editing
- **WHEN** user is in inline edit mode (textarea focused)
- **THEN** j/k/a/r/x shortcuts do NOT fire

### Requirement: Inline editing
Pressing `e` or clicking an edit button SHALL replace the comment body in the right panel with a textarea pre-filled with the current body. The editor SHALL show character count and word count. `Cmd+Enter` SHALL save the edit and approve the comment. `Escape` SHALL cancel the edit.

#### Scenario: Edit and approve with Cmd+Enter
- **WHEN** user presses `e`, edits the body, then presses `Cmd+Enter`
- **THEN** system saves the edited body and approves the comment in one action

#### Scenario: Cancel edit with Escape
- **WHEN** user presses `Escape` while editing
- **THEN** the textarea is replaced with the original body and edit mode exits

### Requirement: Reject flow with reason picker
Pressing `r` or clicking a reject button SHALL open a reason picker with quick-pick options: "Off-topic", "Too promotional", "Doesn't match voice", "Low quality", "Other". Selecting "Other" SHALL show a freeform text input. Confirming SHALL reject the comment with the selected reason.

#### Scenario: Reject with quick-pick reason
- **WHEN** user presses `r` and selects "Too promotional"
- **THEN** system rejects the comment with reason "Too promotional" and removes it from the draft list

#### Scenario: Reject with custom reason
- **WHEN** user selects "Other" and types "Brand name misspelled"
- **THEN** system rejects the comment with the custom reason text

### Requirement: Bulk selection and actions
Users SHALL be able to select multiple comments with `x` toggle or a select-all checkbox. When comments are selected, a floating action bar SHALL appear at the bottom with "Approve Selected (N)" and "Reject Selected (N)" buttons. Bulk actions SHALL use optimistic updates.

#### Scenario: Bulk approve selected comments
- **WHEN** user selects 5 comments with `x` and clicks "Approve Selected (5)"
- **THEN** all 5 comments are approved and removed from the draft list instantly (optimistic)

#### Scenario: Floating bar visibility
- **WHEN** user selects at least 1 comment with `x`
- **THEN** the floating action bar appears at the bottom of the left panel

#### Scenario: Clear selection
- **WHEN** user presses `Escape` with bulk selections active
- **THEN** all selections are cleared and the floating bar disappears

### Requirement: Optimistic UI updates
All approve/reject/bulk mutations SHALL use optimistic updates to immediately remove comments from the current status tab. On error, the comment SHALL reappear (rollback). On settle, the query SHALL be invalidated to sync with the server.

#### Scenario: Optimistic removal on approve
- **WHEN** user approves a comment on the Draft tab
- **THEN** the comment disappears instantly, before the server responds

#### Scenario: Rollback on error
- **WHEN** the approve API call fails
- **THEN** the comment reappears in the list and a toast error is shown
