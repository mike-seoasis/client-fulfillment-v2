## ADDED Requirements

### Requirement: Project accepts additional_info on create
The system SHALL allow users to provide optional additional notes when creating a project.

#### Scenario: Create project with additional_info
- **WHEN** client sends POST to `/api/v1/projects` with `{"name": "Acme Store", "site_url": "https://acme.com", "additional_info": "They prefer a friendly tone. Key competitor is BigStore."}`
- **THEN** system returns 201 with project object including `additional_info` field

#### Scenario: Create project without additional_info
- **WHEN** client sends POST to `/api/v1/projects` with only `name` and `site_url` (no additional_info)
- **THEN** system returns 201 with project object where `additional_info` is null

### Requirement: Project returns brand_config_status
The system SHALL include brand config status in project responses to indicate generation state.

#### Scenario: Project response includes brand_config_status
- **WHEN** client sends GET to `/api/v1/projects/{id}`
- **THEN** system returns project object with `brand_config_status` field indicating "pending", "generating", "complete", or "failed"

#### Scenario: List projects includes brand_config_status
- **WHEN** client sends GET to `/api/v1/projects`
- **THEN** system returns array of project objects, each including `brand_config_status` field

### Requirement: Project returns has_brand_config boolean
The system SHALL include a convenience flag indicating whether brand config exists.

#### Scenario: Project without brand config
- **WHEN** client retrieves a project that has no generated brand config
- **THEN** project response includes `has_brand_config: false`

#### Scenario: Project with brand config
- **WHEN** client retrieves a project that has a generated brand config
- **THEN** project response includes `has_brand_config: true`

### Requirement: Project returns uploaded_files_count
The system SHALL include a count of uploaded files in project responses.

#### Scenario: Project with uploaded files
- **WHEN** client retrieves a project that has 3 uploaded files
- **THEN** project response includes `uploaded_files_count: 3`

#### Scenario: Project without uploaded files
- **WHEN** client retrieves a project that has no uploaded files
- **THEN** project response includes `uploaded_files_count: 0`

## MODIFIED Requirements

### Requirement: Create a project
The system SHALL provide an API endpoint to create a new project with name, site URL, and optional additional info.

#### Scenario: Create project with valid data
- **WHEN** client sends POST to `/api/v1/projects` with `{"name": "Acme Store", "site_url": "https://acme.com"}`
- **THEN** system returns 201 with created project object including server-generated `id`, timestamps, `brand_config_status: "pending"`, `has_brand_config: false`, and `uploaded_files_count: 0`

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
The system SHALL provide an API endpoint to retrieve a single project by ID, including brand config status and file count.

#### Scenario: Get existing project
- **WHEN** client sends GET to `/api/v1/projects/{id}` with valid project ID
- **THEN** system returns 200 with project object including `brand_config_status`, `has_brand_config`, and `uploaded_files_count`

#### Scenario: Get non-existent project
- **WHEN** client sends GET to `/api/v1/projects/{id}` with ID that does not exist
- **THEN** system returns 404 with error message "Project not found"

### Requirement: Delete a project
The system SHALL provide an API endpoint to delete a project by ID, cascading to delete associated files and brand config.

#### Scenario: Delete existing project
- **WHEN** client sends DELETE to `/api/v1/projects/{id}` with valid project ID
- **THEN** system returns 204 No Content, project is removed from database, associated ProjectFile records are deleted, files are removed from S3, and associated BrandConfig is deleted

#### Scenario: Delete non-existent project
- **WHEN** client sends DELETE to `/api/v1/projects/{id}` with ID that does not exist
- **THEN** system returns 404 with error message "Project not found"
