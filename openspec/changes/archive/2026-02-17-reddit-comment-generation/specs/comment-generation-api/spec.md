## ADDED Requirements

### Requirement: Single comment generation endpoint
The system SHALL expose POST /api/v1/projects/{project_id}/reddit/posts/{post_id}/generate that synchronously generates a single comment for a post and returns the RedditCommentResponse. Returns 404 if the post does not exist or does not belong to the project.

#### Scenario: Successful single generation
- **WHEN** POST is called with a valid project_id and post_id
- **THEN** a comment is generated synchronously
- **AND** the response is a RedditCommentResponse with status "draft"
- **AND** HTTP status is 201

#### Scenario: Post not found
- **WHEN** the post_id does not exist or does not belong to project_id
- **THEN** HTTP 404 is returned with an error message

### Requirement: Batch comment generation endpoint
The system SHALL expose POST /api/v1/projects/{project_id}/reddit/generate-batch that starts batch comment generation as a background task (202 Accepted). It generates comments for all relevant posts that don't yet have a draft comment, unless specific post_ids are provided.

#### Scenario: Batch generation trigger
- **WHEN** POST /generate-batch is called without post_ids
- **THEN** the system finds all relevant posts without draft comments
- **AND** starts batch generation as a background task
- **AND** returns 202 with a confirmation message

#### Scenario: Batch with specific post_ids
- **WHEN** POST /generate-batch is called with a list of post_ids
- **THEN** only those posts are included in the batch

#### Scenario: No eligible posts
- **WHEN** all relevant posts already have draft comments
- **THEN** the response indicates 0 posts to process
- **AND** no background task is started

#### Scenario: Generation already in progress
- **WHEN** batch generation is already running for the project
- **THEN** HTTP 409 is returned

### Requirement: Generation status polling endpoint
The system SHALL expose GET /api/v1/projects/{project_id}/reddit/generate/status that returns the current batch generation progress (status, total_posts, posts_generated) or "idle" if no generation is active.

#### Scenario: Generation in progress
- **WHEN** GET /generate/status is called while generation is active
- **THEN** the response includes status "generating" with progress counts

#### Scenario: No active generation
- **WHEN** GET /generate/status is called with no active generation
- **THEN** the response includes status "idle"

### Requirement: List comments endpoint
The system SHALL expose GET /api/v1/projects/{project_id}/reddit/comments that returns all comments for the project, ordered by created_at descending. Supports optional query filters for status (draft/approved/rejected) and post_id.

#### Scenario: List all comments
- **WHEN** GET /comments is called without filters
- **THEN** all comments for the project are returned, newest first

#### Scenario: Filter by status
- **WHEN** GET /comments is called with ?status=draft
- **THEN** only comments with status "draft" are returned

#### Scenario: Filter by post_id
- **WHEN** GET /comments is called with ?post_id={uuid}
- **THEN** only comments for that specific post are returned

### Requirement: Pydantic request schemas
The system SHALL define GenerateCommentRequest (optional is_promotional bool) and BatchGenerateRequest (optional post_ids list) Pydantic schemas in schemas/reddit.py.

#### Scenario: GenerateCommentRequest defaults
- **WHEN** a GenerateCommentRequest is created without specifying is_promotional
- **THEN** is_promotional defaults to None (service uses its own default of true)

#### Scenario: BatchGenerateRequest with post_ids
- **WHEN** BatchGenerateRequest is created with a list of post_ids
- **THEN** those IDs are available for the endpoint to scope the batch

### Requirement: Generation status response schema
The system SHALL define GenerationStatusResponse Pydantic schema with fields: status (str), total_posts (int), posts_generated (int), error (str|None).

#### Scenario: Schema structure
- **WHEN** a GenerationStatusResponse is created
- **THEN** it includes status, total_posts, posts_generated, and optional error
