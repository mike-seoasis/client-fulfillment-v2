## ADDED Requirements

### Requirement: List all projects
The system SHALL provide an API endpoint to retrieve all projects, ordered by most recently updated first.

#### Scenario: List projects when projects exist
- **WHEN** client sends GET request to `/api/v1/projects`
- **THEN** system returns 200 with array of project objects containing `id`, `name`, `site_url`, `status`, `created_at`, `updated_at`

#### Scenario: List projects when no projects exist
- **WHEN** client sends GET request to `/api/v1/projects` and no projects exist
- **THEN** system returns 200 with empty array `[]`

### Requirement: Create a project
The system SHALL provide an API endpoint to create a new project with name and site URL.

#### Scenario: Create project with valid data
- **WHEN** client sends POST to `/api/v1/projects` with `{"name": "Acme Store", "site_url": "https://acme.com"}`
- **THEN** system returns 201 with created project object including server-generated `id` and timestamps

#### Scenario: Create project with missing name
- **WHEN** client sends POST to `/api/v1/projects` with `{"site_url": "https://acme.com"}` (missing name)
- **THEN** system returns 422 with validation error indicating name is required

#### Scenario: Create project with missing site_url
- **WHEN** client sends POST to `/api/v1/projects` with `{"name": "Acme Store"}` (missing site_url)
- **THEN** system returns 422 with validation error indicating site_url is required

#### Scenario: Create project with invalid URL format
- **WHEN** client sends POST to `/api/v1/projects` with `{"name": "Acme", "site_url": "not-a-url"}`
- **THEN** system returns 422 with validation error indicating site_url must be a valid URL

### Requirement: Get a single project
The system SHALL provide an API endpoint to retrieve a single project by ID.

#### Scenario: Get existing project
- **WHEN** client sends GET to `/api/v1/projects/{id}` with valid project ID
- **THEN** system returns 200 with project object

#### Scenario: Get non-existent project
- **WHEN** client sends GET to `/api/v1/projects/{id}` with ID that does not exist
- **THEN** system returns 404 with error message "Project not found"

### Requirement: Update a project
The system SHALL provide an API endpoint to update project name and/or site_url.

#### Scenario: Update project name
- **WHEN** client sends PATCH to `/api/v1/projects/{id}` with `{"name": "New Name"}`
- **THEN** system returns 200 with updated project object and `updated_at` timestamp is refreshed

#### Scenario: Update project site_url
- **WHEN** client sends PATCH to `/api/v1/projects/{id}` with `{"site_url": "https://new-url.com"}`
- **THEN** system returns 200 with updated project object

#### Scenario: Update non-existent project
- **WHEN** client sends PATCH to `/api/v1/projects/{id}` with ID that does not exist
- **THEN** system returns 404 with error message "Project not found"

### Requirement: Delete a project
The system SHALL provide an API endpoint to delete a project by ID.

#### Scenario: Delete existing project
- **WHEN** client sends DELETE to `/api/v1/projects/{id}` with valid project ID
- **THEN** system returns 204 No Content and project is removed from database

#### Scenario: Delete non-existent project
- **WHEN** client sends DELETE to `/api/v1/projects/{id}` with ID that does not exist
- **THEN** system returns 404 with error message "Project not found"

### Requirement: Project data model includes site_url
The Project database model SHALL include a `site_url` field that stores the client's website URL.

#### Scenario: Project has site_url field
- **WHEN** a project is created with a site_url
- **THEN** the site_url is persisted and returned in all project responses

#### Scenario: site_url is indexed for performance
- **WHEN** database schema is inspected
- **THEN** the `site_url` column has an index for efficient lookups
