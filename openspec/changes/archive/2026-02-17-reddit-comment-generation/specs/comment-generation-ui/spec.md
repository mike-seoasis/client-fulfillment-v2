## ADDED Requirements

### Requirement: Per-post generate button
The system SHALL display a "Generate" button in each row of the posts table for posts with filter_status "relevant". Clicking the button triggers single comment generation via the API and shows a loading spinner while generating.

#### Scenario: Generate for a single post
- **WHEN** the user clicks "Generate" on a relevant post row
- **THEN** the API is called to generate a single comment
- **AND** a loading spinner replaces the button during generation
- **AND** on success, the comments list refreshes to show the new draft

#### Scenario: Post already has a comment
- **WHEN** a post already has a draft comment
- **THEN** the button shows "Regenerate" instead of "Generate"
- **AND** clicking it creates a new comment (does not overwrite the existing one)

### Requirement: Batch generate button
The system SHALL display a "Generate Comments" button in the comments section header. Clicking it triggers batch generation for all relevant posts without existing draft comments. The button shows progress while generation is active.

#### Scenario: Batch generation trigger
- **WHEN** the user clicks "Generate Comments"
- **THEN** batch generation starts for all eligible posts
- **AND** the button shows a loading/progress state
- **AND** progress polls via the generation status endpoint

#### Scenario: Batch generation complete
- **WHEN** batch generation completes
- **THEN** the comments list refreshes to show new drafts
- **AND** the button returns to its default state

#### Scenario: No eligible posts
- **WHEN** all relevant posts already have draft comments
- **THEN** the button is disabled with a tooltip explaining why

### Requirement: Comments section display
The system SHALL display a comments section below the posts table showing all generated comments for the project. Each comment card shows the comment body, approach type badge, promotional/organic indicator, associated post title, and status.

#### Scenario: Comments list rendering
- **WHEN** comments exist for the project
- **THEN** each comment displays:
  - Comment body text
  - Approach type as a badge (e.g., "Sandwich", "Story-Based")
  - Promotional/organic indicator
  - Associated post title (truncated)
  - Status badge (draft/approved/rejected)
  - Created timestamp

#### Scenario: No comments yet
- **WHEN** no comments exist for the project
- **THEN** an empty state message is shown: "No comments generated yet"
- **AND** the batch generate button is prominently displayed

### Requirement: Inline comment editing
The system SHALL allow inline editing of a draft comment's body text. Editing updates only the body field while preserving original_body. A "Reset" link restores body to original_body.

#### Scenario: Edit a draft comment
- **WHEN** the user clicks on a draft comment's body
- **THEN** the body becomes editable (textarea)
- **AND** saving sends a PATCH request to update the body

#### Scenario: Reset to original
- **WHEN** the user clicks "Reset" on an edited comment
- **THEN** the body is restored to original_body

#### Scenario: Non-draft comments
- **WHEN** a comment has status other than "draft"
- **THEN** the body is not editable

### Requirement: Generation status polling
The system SHALL poll the generation status endpoint every 2 seconds while batch generation is active (status "generating"). Polling stops when status transitions to "complete" or "failed". On completion, the comments query is invalidated to refresh the list.

#### Scenario: Polling while active
- **WHEN** batch generation is in progress
- **THEN** the UI polls every 2 seconds for progress updates
- **AND** displays current progress (e.g., "Generating 3/10...")

#### Scenario: Polling stops on completion
- **WHEN** generation status changes to "complete"
- **THEN** polling stops
- **AND** the comments list is refreshed via query invalidation

### Requirement: API hooks for comment generation
The system SHALL add the following to the frontend API layer and React hooks:
- `generateComment(projectId, postId)` - single generation
- `generateBatch(projectId, postIds?)` - batch generation
- `fetchGenerationStatus(projectId)` - poll status
- `fetchComments(projectId, filters?)` - list comments
- `useComments(projectId)` - TanStack Query hook for comments list
- `useGenerationStatus(projectId)` - TanStack Query hook with 2s polling when active

#### Scenario: Hook integration
- **WHEN** the Reddit page mounts
- **THEN** useComments fetches the initial comments list
- **AND** useGenerationStatus checks for any active generation
