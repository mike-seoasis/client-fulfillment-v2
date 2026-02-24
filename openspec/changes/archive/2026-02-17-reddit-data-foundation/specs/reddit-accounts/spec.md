## ADDED Requirements

### Requirement: Reddit account data model
The system SHALL store Reddit accounts in a `reddit_accounts` table with UUID primary keys, username, status lifecycle, warmup stage tracking, niche tags, karma stats, cooldown management, and timestamps.

#### Scenario: Account table schema
- **WHEN** the database schema is inspected
- **THEN** the `reddit_accounts` table has columns: `id` (UUID PK), `username` (String 100, unique, indexed), `status` (String 50, default "active", indexed), `warmup_stage` (String 50, default "observation"), `niche_tags` (JSONB, default []), `karma_post` (Integer, default 0), `karma_comment` (Integer, default 0), `account_age_days` (Integer, nullable), `cooldown_until` (DateTime with timezone, nullable), `last_used_at` (DateTime with timezone, nullable), `notes` (Text, nullable), `metadata` (JSONB, nullable), `created_at` (DateTime with timezone), `updated_at` (DateTime with timezone)

#### Scenario: Username is unique
- **WHEN** an account is created with a username that already exists
- **THEN** the database rejects the insert with a unique constraint violation

### Requirement: Account status enum
The system SHALL enforce account status values: `active`, `warming_up`, `cooldown`, `suspended`, `banned`.

#### Scenario: Valid status values
- **WHEN** an account status is set to "active", "warming_up", "cooldown", "suspended", or "banned"
- **THEN** the value is accepted and persisted

### Requirement: Account warmup stage enum
The system SHALL enforce warmup stage values: `observation`, `light_engagement`, `regular_activity`, `operational`.

#### Scenario: Valid warmup stage values
- **WHEN** an account warmup_stage is set to "observation", "light_engagement", "regular_activity", or "operational"
- **THEN** the value is accepted and persisted

### Requirement: List Reddit accounts
The system SHALL provide an API endpoint to list all Reddit accounts with optional filtering by niche, warmup stage, and status.

#### Scenario: List all accounts
- **WHEN** client sends GET to `/api/v1/reddit/accounts`
- **THEN** system returns 200 with array of account objects

#### Scenario: Filter accounts by niche tag
- **WHEN** client sends GET to `/api/v1/reddit/accounts?niche=skincare`
- **THEN** system returns only accounts whose `niche_tags` array contains "skincare"

#### Scenario: Filter accounts by status
- **WHEN** client sends GET to `/api/v1/reddit/accounts?status=active`
- **THEN** system returns only accounts with status "active"

#### Scenario: Filter accounts by warmup stage
- **WHEN** client sends GET to `/api/v1/reddit/accounts?warmup_stage=operational`
- **THEN** system returns only accounts with warmup_stage "operational"

#### Scenario: No accounts exist
- **WHEN** client sends GET to `/api/v1/reddit/accounts` and no accounts exist
- **THEN** system returns 200 with empty array

### Requirement: Create Reddit account
The system SHALL provide an API endpoint to create a new Reddit account.

#### Scenario: Create account with required fields
- **WHEN** client sends POST to `/api/v1/reddit/accounts` with `{"username": "u/helpfan", "niche_tags": ["skincare"]}`
- **THEN** system returns 201 with created account object including server-generated `id`, default status "active", default warmup_stage "observation"

#### Scenario: Create account with duplicate username
- **WHEN** client sends POST to `/api/v1/reddit/accounts` with a username that already exists
- **THEN** system returns 409 Conflict with error message

#### Scenario: Create account with missing username
- **WHEN** client sends POST to `/api/v1/reddit/accounts` without username field
- **THEN** system returns 422 with validation error

### Requirement: Update Reddit account
The system SHALL provide an API endpoint to update an existing Reddit account's fields.

#### Scenario: Update account status
- **WHEN** client sends PATCH to `/api/v1/reddit/accounts/{id}` with `{"status": "cooldown", "cooldown_until": "2026-02-17T12:00:00Z"}`
- **THEN** system returns 200 with updated account and `updated_at` is refreshed

#### Scenario: Update account niche tags
- **WHEN** client sends PATCH to `/api/v1/reddit/accounts/{id}` with `{"niche_tags": ["skincare", "beauty"]}`
- **THEN** system returns 200 with updated niche_tags array

#### Scenario: Update non-existent account
- **WHEN** client sends PATCH to `/api/v1/reddit/accounts/{id}` with ID that does not exist
- **THEN** system returns 404

### Requirement: Delete Reddit account
The system SHALL provide an API endpoint to delete a Reddit account.

#### Scenario: Delete existing account
- **WHEN** client sends DELETE to `/api/v1/reddit/accounts/{id}`
- **THEN** system returns 204 and account is removed

#### Scenario: Delete non-existent account
- **WHEN** client sends DELETE to `/api/v1/reddit/accounts/{id}` with ID that does not exist
- **THEN** system returns 404

### Requirement: Account management UI page
The system SHALL provide an account management page at `/reddit/accounts` with a table of all accounts, filter controls, and CRUD actions.

#### Scenario: Account table displays all accounts
- **WHEN** user navigates to `/reddit/accounts`
- **THEN** a table displays all accounts with columns: Username, Status, Warmup Stage, Niche Tags (as chips), Karma, Cooldown, Last Used

#### Scenario: Filter by niche
- **WHEN** user selects a niche from the filter dropdown
- **THEN** the table shows only accounts matching that niche

#### Scenario: Add account via modal
- **WHEN** user clicks "Add Account" button
- **THEN** a modal appears with fields: Username (required), Niche Tags (tag input), Notes (optional)

#### Scenario: Delete account with confirmation
- **WHEN** user clicks delete on an account row
- **THEN** a confirmation step is shown before deletion proceeds

#### Scenario: Empty state
- **WHEN** no accounts exist
- **THEN** page shows friendly empty state with "Add Account" CTA
