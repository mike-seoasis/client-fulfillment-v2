## ADDED Requirements

### Requirement: Cross-project comment queue endpoint
The system SHALL provide `GET /api/v1/reddit/comments` that returns comments across all projects with eager-loaded post data (title, subreddit, snippet, url) and project name. The endpoint SHALL support query parameters: `status` (string), `project_id` (UUID), `search` (text search in comment body), `limit` (int, default 50), `offset` (int, default 0). Results SHALL be ordered by `created_at` descending.

#### Scenario: Fetch draft comments across all projects
- **WHEN** client sends `GET /api/v1/reddit/comments?status=draft`
- **THEN** system returns 200 with all draft comments across all projects, each including nested `post` object with title/subreddit/snippet/url, ordered by created_at desc

#### Scenario: Filter by project
- **WHEN** client sends `GET /api/v1/reddit/comments?status=draft&project_id={id}`
- **THEN** system returns only draft comments for that specific project

#### Scenario: Text search in comment body
- **WHEN** client sends `GET /api/v1/reddit/comments?search=wellness`
- **THEN** system returns comments where body contains "wellness" (case-insensitive)

#### Scenario: Pagination
- **WHEN** client sends `GET /api/v1/reddit/comments?limit=20&offset=40`
- **THEN** system returns at most 20 comments starting from offset 40

### Requirement: Approve a comment
The system SHALL provide `POST /api/v1/projects/{project_id}/reddit/comments/{id}/approve` that transitions a comment from `draft` to `approved`. The request body MAY include an edited `body` field; if provided, the comment body SHALL be updated before approval. The response SHALL return the updated comment with 200.

#### Scenario: Approve a draft comment
- **WHEN** client sends `POST .../comments/{id}/approve` with empty body for a draft comment
- **THEN** system sets status to "approved" and returns 200 with updated comment

#### Scenario: Approve with edited body
- **WHEN** client sends `POST .../comments/{id}/approve` with `{"body": "edited text"}`
- **THEN** system updates the comment body and sets status to "approved"

#### Scenario: Approve a non-draft comment
- **WHEN** client sends `POST .../comments/{id}/approve` for a comment with status "approved" or "rejected"
- **THEN** system returns 400 with error "Only draft comments can be approved"

### Requirement: Reject a comment
The system SHALL provide `POST /api/v1/projects/{project_id}/reddit/comments/{id}/reject` that transitions a comment from `draft` to `rejected`. The request body SHALL include a `reason` field. The response SHALL return the updated comment with 200.

#### Scenario: Reject a draft comment with reason
- **WHEN** client sends `POST .../comments/{id}/reject` with `{"reason": "Too promotional"}`
- **THEN** system sets status to "rejected", stores the reason in `reject_reason`, and returns 200

#### Scenario: Reject without reason
- **WHEN** client sends `POST .../comments/{id}/reject` with empty body or no reason
- **THEN** system returns 422 validation error requiring a reason

#### Scenario: Reject a non-draft comment
- **WHEN** client sends `POST .../comments/{id}/reject` for a non-draft comment
- **THEN** system returns 400 with error "Only draft comments can be rejected"

### Requirement: Bulk approve comments
The system SHALL provide `POST /api/v1/projects/{project_id}/reddit/comments/bulk-approve` that transitions multiple draft comments to approved. The request body SHALL include `comment_ids` (list of UUIDs). Comments that are not in draft status SHALL be silently skipped. The response SHALL return the count of approved comments.

#### Scenario: Bulk approve draft comments
- **WHEN** client sends bulk-approve with 5 comment IDs, 4 of which are drafts
- **THEN** system approves the 4 drafts, skips the 1 non-draft, returns `{"approved_count": 4}`

### Requirement: Bulk reject comments
The system SHALL provide `POST /api/v1/projects/{project_id}/reddit/comments/bulk-reject` that transitions multiple draft comments to rejected. The request body SHALL include `comment_ids` and `reason`. The response SHALL return the count of rejected comments.

#### Scenario: Bulk reject with shared reason
- **WHEN** client sends bulk-reject with 3 comment IDs and reason "Low quality"
- **THEN** system rejects all 3 drafts with the shared reason, returns `{"rejected_count": 3}`
