## MODIFIED Requirements

### Requirement: Project detail view displays project header
The project detail view SHALL display a header with the project name, site URL, navigation back to dashboard, and a tab bar for Tools and Pages.

#### Scenario: Header shows project name
- **WHEN** user navigates to `/projects/{id}`
- **THEN** page displays the project name as the main heading

#### Scenario: Header shows site URL
- **WHEN** user views a project detail page
- **THEN** the project's site URL is displayed below the name

#### Scenario: Back navigation to dashboard
- **WHEN** user clicks "All Projects" link in header
- **THEN** user is navigated back to the dashboard (`/`)

#### Scenario: Tab bar renders below header
- **WHEN** user views a project detail page
- **THEN** a tab bar with "Tools" and "Pages" tabs is displayed below the project name and site URL, above the content area

### Requirement: Create project form
The system SHALL provide a form to create a new project at `/projects/new` with an optional "Connect Shopify" step.

#### Scenario: Create form has required fields
- **WHEN** user navigates to `/projects/new`
- **THEN** form displays fields for "Project Name" (required) and "Website URL" (required)

#### Scenario: Create form has optional Shopify connection
- **WHEN** user navigates to `/projects/new`
- **THEN** form displays an optional "Connect Shopify Store" section below the required fields, with a text input for store domain and a description explaining the benefit

#### Scenario: Submitting valid form creates project
- **WHEN** user fills in valid name and URL and clicks "Create Project"
- **THEN** project is created and user is redirected to the new project's detail page

#### Scenario: Submitting form with Shopify domain creates project then initiates OAuth
- **WHEN** user fills in valid name, URL, and Shopify store domain, then clicks "Create Project"
- **THEN** project is created, then user is redirected to the Shopify OAuth install endpoint to authorize the connection

#### Scenario: Form validates required fields
- **WHEN** user attempts to submit form with empty fields
- **THEN** validation errors are displayed inline for each missing field

#### Scenario: Form validates URL format
- **WHEN** user enters invalid URL format in Website URL field
- **THEN** validation error "Please enter a valid URL" is displayed

#### Scenario: Form validates Shopify domain format
- **WHEN** user enters an invalid Shopify store domain (not matching *.myshopify.com)
- **THEN** validation error "Enter a valid Shopify domain (e.g., yourstore.myshopify.com)" is displayed

#### Scenario: Cancel button returns to dashboard
- **WHEN** user clicks "Cancel" on create form
- **THEN** user is navigated back to dashboard without creating a project
