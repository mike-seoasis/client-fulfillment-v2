## ADDED Requirements

### Requirement: Reddit project config data model
The system SHALL store per-project Reddit settings in a `reddit_project_configs` table with a 1:1 relationship to the projects table.

#### Scenario: Config table schema
- **WHEN** the database schema is inspected
- **THEN** the `reddit_project_configs` table has columns: `id` (UUID PK), `project_id` (UUID FK to projects.id, unique, CASCADE delete, indexed), `search_keywords` (JSONB, default []), `target_subreddits` (JSONB, default []), `banned_subreddits` (JSONB, default []), `competitors` (JSONB, default []), `comment_instructions` (Text, nullable), `niche_tags` (JSONB, default []), `discovery_settings` (JSONB, nullable), `is_active` (Boolean, default true), `created_at` (DateTime with timezone), `updated_at` (DateTime with timezone)

#### Scenario: One config per project
- **WHEN** a second config is created for the same project_id
- **THEN** the database rejects the insert with a unique constraint violation on project_id

#### Scenario: Cascade delete
- **WHEN** a project is deleted
- **THEN** its associated reddit_project_config is also deleted

### Requirement: Get project Reddit config
The system SHALL provide an API endpoint to retrieve a project's Reddit configuration.

#### Scenario: Get existing config
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/reddit/config`
- **THEN** system returns 200 with the config object

#### Scenario: Get config when none exists
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/reddit/config` and no config exists
- **THEN** system returns 404

#### Scenario: Get config for non-existent project
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/reddit/config` with invalid project_id
- **THEN** system returns 404

### Requirement: Create or update project Reddit config
The system SHALL provide an API endpoint that upserts a project's Reddit configuration (create if none exists, update if it does).

#### Scenario: Create new config
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/reddit/config` with `{"search_keywords": ["best skincare"], "target_subreddits": ["SkincareAddiction"]}` and no config exists
- **THEN** system returns 201 with created config object

#### Scenario: Update existing config
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/reddit/config` with updated fields and a config already exists
- **THEN** system returns 200 with updated config object and `updated_at` is refreshed

#### Scenario: Create config with all fields
- **WHEN** client sends POST with search_keywords, target_subreddits, banned_subreddits, competitors, comment_instructions, niche_tags, and discovery_settings
- **THEN** all fields are persisted and returned in the response

#### Scenario: Config for non-existent project
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/reddit/config` with invalid project_id
- **THEN** system returns 404

### Requirement: Project Reddit config UI page
The system SHALL provide a Reddit settings page at `/projects/[id]/reddit` with a form for configuring all Reddit settings.

#### Scenario: Config form displays all fields
- **WHEN** user navigates to `/projects/[id]/reddit`
- **THEN** page displays a form with: Search Keywords (tag input), Target Subreddits (tag input with r/ prefix), Banned Subreddits (tag input), Competitors (tag input), Comment Instructions (textarea), Niche Tags (tag input), Discovery Settings (time range dropdown + max posts input), Active toggle

#### Scenario: Save settings
- **WHEN** user fills in settings and clicks "Save Settings"
- **THEN** settings are persisted via the upsert API and a success indication is shown

#### Scenario: Load existing settings
- **WHEN** user navigates to `/projects/[id]/reddit` and a config already exists
- **THEN** the form is pre-populated with the existing config values

#### Scenario: Empty state for new config
- **WHEN** user navigates to `/projects/[id]/reddit` and no config exists
- **THEN** the form displays with empty/default values

#### Scenario: Back navigation
- **WHEN** user clicks the back link
- **THEN** user is navigated to the project detail page
