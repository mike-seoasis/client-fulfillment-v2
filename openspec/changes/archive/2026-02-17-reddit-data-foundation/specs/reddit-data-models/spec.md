## ADDED Requirements

### Requirement: Reddit post data model
The system SHALL store discovered Reddit posts in a `reddit_posts` table linked to projects.

#### Scenario: Post table schema
- **WHEN** the database schema is inspected
- **THEN** the `reddit_posts` table has columns: `id` (UUID PK), `project_id` (UUID FK to projects.id, CASCADE, indexed), `reddit_post_id` (String 50, nullable), `subreddit` (String 100, not null, indexed), `title` (Text, not null), `url` (String 2048, not null), `snippet` (Text, nullable), `keyword` (String 500, nullable), `intent` (String 50, nullable), `intent_categories` (JSONB, nullable), `relevance_score` (Float, nullable), `matched_keywords` (JSONB, nullable), `ai_evaluation` (JSONB, nullable), `filter_status` (String 50, default "pending", indexed), `serp_position` (Integer, nullable), `discovered_at` (DateTime with timezone, not null), `created_at` (DateTime with timezone), `updated_at` (DateTime with timezone)

#### Scenario: Unique constraint on project + URL
- **WHEN** a post with the same project_id and url combination is inserted
- **THEN** the database rejects the insert with a unique constraint violation (`uq_reddit_posts_project_url`)

#### Scenario: Cascade delete from project
- **WHEN** a project is deleted
- **THEN** all associated reddit_posts are also deleted

### Requirement: Post filter status enum
The system SHALL enforce post filter status values: `pending`, `relevant`, `irrelevant`, `skipped`.

#### Scenario: Valid filter status values
- **WHEN** a post filter_status is set to "pending", "relevant", "irrelevant", or "skipped"
- **THEN** the value is accepted and persisted

### Requirement: Post intent enum
The system SHALL support post intent classification values: `research`, `pain_point`, `competitor`, `question`, `general`.

#### Scenario: Valid intent values
- **WHEN** a post intent is set to "research", "pain_point", "competitor", "question", or "general"
- **THEN** the value is accepted and persisted

### Requirement: Reddit comment data model
The system SHALL store AI-generated comments in a `reddit_comments` table linked to posts, projects, and optionally accounts.

#### Scenario: Comment table schema
- **WHEN** the database schema is inspected
- **THEN** the `reddit_comments` table has columns: `id` (UUID PK), `post_id` (UUID FK to reddit_posts.id, CASCADE, indexed), `project_id` (UUID FK to projects.id, CASCADE, indexed), `account_id` (UUID FK to reddit_accounts.id, SET NULL, nullable, indexed), `body` (Text, not null), `original_body` (Text, not null), `is_promotional` (Boolean, not null, default true), `approach_type` (String 100, nullable), `status` (String 50, default "draft", indexed), `reject_reason` (Text, nullable), `crowdreply_task_id` (String 255, nullable), `posted_url` (String 2048, nullable), `posted_at` (DateTime with timezone, nullable), `generation_metadata` (JSONB, nullable), `created_at` (DateTime with timezone), `updated_at` (DateTime with timezone)

#### Scenario: Comment cascade from post
- **WHEN** a reddit_post is deleted
- **THEN** all associated reddit_comments are also deleted

#### Scenario: Account deletion sets null
- **WHEN** a reddit_account is deleted
- **THEN** the account_id on associated comments is set to NULL (not cascaded)

### Requirement: Comment status enum
The system SHALL enforce comment status values: `draft`, `approved`, `rejected`, `submitting`, `posted`, `failed`, `mod_removed`.

#### Scenario: Valid comment status values
- **WHEN** a comment status is set to any of the defined values
- **THEN** the value is accepted and persisted

### Requirement: CrowdReply task data model
The system SHALL store CrowdReply API task tracking in a `crowdreply_tasks` table linked to comments.

#### Scenario: CrowdReply task table schema
- **WHEN** the database schema is inspected
- **THEN** the `crowdreply_tasks` table has columns: `id` (UUID PK), `comment_id` (UUID FK to reddit_comments.id, SET NULL, nullable, indexed), `external_task_id` (String 255, nullable, indexed), `task_type` (String 50, not null), `status` (String 50, default "pending", indexed), `target_url` (String 2048, not null), `content` (Text, not null), `crowdreply_project_id` (String 255, nullable), `request_payload` (JSONB, nullable), `response_payload` (JSONB, nullable), `upvotes_requested` (Integer, nullable), `price` (Float, nullable), `submitted_at` (DateTime with timezone, nullable), `published_at` (DateTime with timezone, nullable), `created_at` (DateTime with timezone), `updated_at` (DateTime with timezone)

#### Scenario: Comment deletion sets null
- **WHEN** a reddit_comment is deleted
- **THEN** the comment_id on associated crowdreply_tasks is set to NULL

### Requirement: CrowdReply task type enum
The system SHALL support task type values: `comment`, `post`, `reply`, `upvote`.

#### Scenario: Valid task type values
- **WHEN** a task_type is set to "comment", "post", "reply", or "upvote"
- **THEN** the value is accepted and persisted

### Requirement: CrowdReply task status enum
The system SHALL enforce task status values: `pending`, `submitted`, `assigned`, `published`, `mod_removed`, `cancelled`, `failed`.

#### Scenario: Valid task status values
- **WHEN** a task status is set to any of the defined values
- **THEN** the value is accepted and persisted

### Requirement: All Reddit tables created in single migration
The system SHALL create all 5 Reddit tables (reddit_accounts, reddit_project_configs, reddit_posts, reddit_comments, crowdreply_tasks) in a single Alembic migration.

#### Scenario: Migration creates all tables
- **WHEN** `alembic upgrade head` is run
- **THEN** all 5 tables exist with correct columns, indexes, foreign keys, and unique constraints

#### Scenario: Migration is reversible
- **WHEN** `alembic downgrade -1` is run
- **THEN** all 5 Reddit tables are dropped

### Requirement: Pydantic v2 schemas for all Reddit entities
The system SHALL provide Pydantic v2 request and response schemas for all 5 Reddit entities in a single `reddit.py` schemas file.

#### Scenario: Response schemas include all fields
- **WHEN** a Reddit entity is serialized using its response schema
- **THEN** all database columns are represented with correct types and `model_config = ConfigDict(from_attributes=True)`

#### Scenario: Create schemas validate required fields
- **WHEN** a create schema is instantiated without required fields
- **THEN** Pydantic raises a validation error

#### Scenario: Update schemas allow partial updates
- **WHEN** an update schema is instantiated with only some fields
- **THEN** unset fields are None and only provided fields are used for update

### Requirement: Reddit settings in application config
The system SHALL include SERP API and CrowdReply configuration in the Settings class with sensible defaults.

#### Scenario: SERP API config
- **WHEN** the Settings class is inspected
- **THEN** it includes `serpapi_key` (str, default "")

#### Scenario: CrowdReply config
- **WHEN** the Settings class is inspected
- **THEN** it includes `crowdreply_api_key` (str, default ""), `crowdreply_project_id` (str, default ""), `crowdreply_webhook_secret` (str, default ""), `crowdreply_base_url` (str, default "https://crowdreply.io/api")
