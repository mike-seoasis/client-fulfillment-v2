## ADDED Requirements

### Requirement: Dashboard displays project cards
The dashboard SHALL display all projects as cards in a responsive grid layout.

#### Scenario: Dashboard shows project cards
- **WHEN** user navigates to the dashboard (`/`)
- **THEN** system displays a card for each project showing project name and site URL

#### Scenario: Dashboard shows empty state
- **WHEN** user navigates to the dashboard and no projects exist
- **THEN** system displays an empty state message with prompt to create first project

### Requirement: Project cards show key information
Each project card SHALL display the project name, site URL, and last activity timestamp.

#### Scenario: Card displays project name
- **WHEN** a project card is rendered
- **THEN** the project name is displayed prominently as the card title

#### Scenario: Card displays site URL
- **WHEN** a project card is rendered
- **THEN** the site URL is displayed below the project name

#### Scenario: Card displays last activity
- **WHEN** a project card is rendered
- **THEN** the relative time since last update is displayed (e.g., "2 days ago", "Today")

### Requirement: Project cards show placeholder metrics
Each project card SHALL show placeholder metrics for pages, clusters, and pending items until real data is available in later phases.

#### Scenario: Card shows placeholder metrics
- **WHEN** a project card is rendered
- **THEN** metrics section shows "0 pages", "0 clusters", "0 pending" as placeholders

### Requirement: Dashboard has create project button
The dashboard SHALL have a prominent button to create a new project.

#### Scenario: Create button navigates to new project page
- **WHEN** user clicks "+ New Project" button
- **THEN** user is navigated to `/projects/new`

### Requirement: Project cards are clickable
Each project card SHALL be clickable to navigate to the project detail view.

#### Scenario: Clicking card navigates to project
- **WHEN** user clicks on a project card
- **THEN** user is navigated to `/projects/{id}` for that project

### Requirement: Dashboard has app header
The dashboard SHALL display an app header with logo and application name.

#### Scenario: Header displays branding
- **WHEN** user views the dashboard
- **THEN** header shows logo placeholder and "Client Onboarding" text

### Requirement: Projects are sorted by recent activity
The dashboard SHALL display projects ordered by most recently updated first.

#### Scenario: Recently updated projects appear first
- **WHEN** user views the dashboard with multiple projects
- **THEN** projects are displayed in descending order by `updated_at` timestamp
