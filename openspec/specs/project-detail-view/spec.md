## ADDED Requirements

### Requirement: Project detail view displays project header
The project detail view SHALL display a header with the project name, site URL, and navigation back to dashboard.

#### Scenario: Header shows project name
- **WHEN** user navigates to `/projects/{id}`
- **THEN** page displays the project name as the main heading

#### Scenario: Header shows site URL
- **WHEN** user views a project detail page
- **THEN** the project's site URL is displayed below the name

#### Scenario: Back navigation to dashboard
- **WHEN** user clicks "All Projects" link in header
- **THEN** user is navigated back to the dashboard (`/`)

### Requirement: Project detail view has Onboarding section
The project detail view SHALL display an Onboarding section for existing page optimization workflow.

#### Scenario: Onboarding section is visible
- **WHEN** user views a project detail page
- **THEN** an "Onboarding" section is displayed with description "Optimize existing collection pages with new copy"

#### Scenario: Onboarding section shows placeholder status
- **WHEN** user views a project detail page (Phase 1)
- **THEN** Onboarding section shows "Not started" status since workflow is not yet implemented

#### Scenario: Onboarding continue button is disabled
- **WHEN** user views a project detail page (Phase 1)
- **THEN** "Continue Onboarding" button is present but disabled with tooltip "Coming in Phase 3"

### Requirement: Project detail view has New Content section
The project detail view SHALL display a New Content (Clusters) section for keyword cluster workflow.

#### Scenario: New Content section is visible
- **WHEN** user views a project detail page
- **THEN** a "New Content" section is displayed with description "Build new collection pages from keyword clusters"

#### Scenario: New Content section shows empty state
- **WHEN** user views a project detail page (Phase 1)
- **THEN** New Content section shows "+ New Cluster" button placeholder (disabled)

### Requirement: Project detail view has Edit Brand button
The project detail view SHALL have a button to access brand configuration (placeholder for Phase 2).

#### Scenario: Edit Brand button is visible but disabled
- **WHEN** user views a project detail page
- **THEN** "Edit Brand" button is visible but disabled with tooltip "Coming in Phase 2"

### Requirement: Project can be deleted from detail view
The project detail view SHALL allow users to delete the project with two-step confirmation.

#### Scenario: Delete button shows confirmation
- **WHEN** user clicks "Delete Project" button
- **THEN** button changes to "Confirm Delete" state

#### Scenario: Confirming delete removes project
- **WHEN** user clicks "Confirm Delete" button
- **THEN** project is deleted and user is redirected to dashboard

#### Scenario: Clicking away cancels delete
- **WHEN** user clicks "Delete Project" then clicks elsewhere on the page
- **THEN** delete confirmation is cancelled and button returns to normal state

### Requirement: Project detail view handles invalid project ID
The project detail view SHALL display an error state for non-existent projects.

#### Scenario: Invalid project ID shows not found
- **WHEN** user navigates to `/projects/{id}` with an ID that does not exist
- **THEN** page displays "Project not found" error with link back to dashboard

### Requirement: Create project form
The system SHALL provide a form to create a new project at `/projects/new`.

#### Scenario: Create form has required fields
- **WHEN** user navigates to `/projects/new`
- **THEN** form displays fields for "Project Name" (required) and "Website URL" (required)

#### Scenario: Submitting valid form creates project
- **WHEN** user fills in valid name and URL and clicks "Create Project"
- **THEN** project is created and user is redirected to the new project's detail page

#### Scenario: Form validates required fields
- **WHEN** user attempts to submit form with empty fields
- **THEN** validation errors are displayed inline for each missing field

#### Scenario: Form validates URL format
- **WHEN** user enters invalid URL format in Website URL field
- **THEN** validation error "Please enter a valid URL" is displayed

#### Scenario: Cancel button returns to dashboard
- **WHEN** user clicks "Cancel" on create form
- **THEN** user is navigated back to dashboard without creating a project
