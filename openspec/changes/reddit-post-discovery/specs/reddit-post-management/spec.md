## ADDED Requirements

### Requirement: Discovery can be triggered via API
The system SHALL provide a POST endpoint to trigger discovery as a background task, returning 202 Accepted immediately.

#### Scenario: Trigger discovery for a project
- **WHEN** a POST request is sent to `/api/v1/projects/{project_id}/reddit/discover`
- **THEN** the system returns 202 Accepted and starts the discovery pipeline in the background

#### Scenario: Trigger discovery when already running
- **WHEN** a POST request is sent while discovery is already in progress for the same project
- **THEN** the system returns 409 Conflict with message "Discovery already in progress"

#### Scenario: Trigger discovery without config
- **WHEN** a POST request is sent for a project with no RedditProjectConfig
- **THEN** the system returns 404 with message "Reddit config not found for this project"

#### Scenario: Trigger discovery without keywords
- **WHEN** a POST request is sent for a project whose config has an empty search_keywords list
- **THEN** the system returns 400 with message "No search keywords configured"

### Requirement: Discovery status can be polled
The system SHALL provide a GET endpoint to poll discovery progress.

#### Scenario: Poll during active discovery
- **WHEN** a GET request is sent to `/api/v1/projects/{project_id}/reddit/discover/status` while discovery is running
- **THEN** the system returns 200 with current progress (status, keywords_searched, posts_found, posts_scored)

#### Scenario: Poll when no discovery is running
- **WHEN** a GET request is sent and no discovery is active or has completed
- **THEN** the system returns 200 with status "idle"

### Requirement: Discovered posts can be listed and filtered
The system SHALL provide a GET endpoint to list discovered posts with query filters.

#### Scenario: List all posts for a project
- **WHEN** a GET request is sent to `/api/v1/projects/{project_id}/reddit/posts`
- **THEN** the system returns all RedditPost rows for that project, ordered by relevance_score descending

#### Scenario: Filter posts by filter_status
- **WHEN** a GET request includes query parameter `filter_status=relevant`
- **THEN** only posts with filter_status "relevant" are returned

#### Scenario: Filter posts by intent
- **WHEN** a GET request includes query parameter `intent=research`
- **THEN** only posts whose intent_categories JSONB array contains "research" are returned

#### Scenario: Filter posts by subreddit
- **WHEN** a GET request includes query parameter `subreddit=SkincareAddiction`
- **THEN** only posts from that subreddit are returned

### Requirement: Post filter status can be updated
The system SHALL provide a PATCH endpoint to update a post's filter_status.

#### Scenario: Approve a post
- **WHEN** a PATCH request is sent to `/api/v1/projects/{project_id}/reddit/posts/{post_id}` with body `{"filter_status": "relevant"}`
- **THEN** the post's filter_status is updated to "relevant"

#### Scenario: Reject a post
- **WHEN** a PATCH request is sent with body `{"filter_status": "irrelevant"}`
- **THEN** the post's filter_status is updated to "irrelevant"

#### Scenario: Post not found
- **WHEN** a PATCH request is sent for a non-existent post_id
- **THEN** the system returns 404

### Requirement: Bulk actions on posts
The system SHALL provide a POST endpoint for bulk approve/reject operations.

#### Scenario: Bulk approve posts
- **WHEN** a POST request is sent to `/api/v1/projects/{project_id}/reddit/posts/bulk-action` with body `{"post_ids": [...], "filter_status": "relevant"}`
- **THEN** all specified posts have their filter_status updated to "relevant"

#### Scenario: Bulk reject posts
- **WHEN** a POST request is sent with body `{"post_ids": [...], "filter_status": "irrelevant"}`
- **THEN** all specified posts have their filter_status updated to "irrelevant"
