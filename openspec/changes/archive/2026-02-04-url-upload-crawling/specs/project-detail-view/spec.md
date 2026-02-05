## MODIFIED Requirements

### Requirement: Project detail view has Onboarding section
The project detail view SHALL display an Onboarding section for existing page optimization workflow.

#### Scenario: Onboarding section is visible
- **WHEN** user views a project detail page
- **THEN** an "Onboarding" section is displayed with description "Optimize existing collection pages with new copy"

#### Scenario: Onboarding section shows crawl status when URLs uploaded
- **WHEN** project has crawled pages
- **THEN** Onboarding section shows progress (e.g., "8 of 12 pages complete")

#### Scenario: Onboarding section shows step indicators
- **WHEN** user views a project with onboarding in progress
- **THEN** section shows completed steps with checkmarks (e.g., "URLs uploaded", "Crawled", "Keywords approved")

#### Scenario: Continue Onboarding navigates to current step
- **WHEN** user clicks "Continue Onboarding" button
- **THEN** user is navigated to the appropriate onboarding step based on progress

#### Scenario: Start Onboarding button when not started
- **WHEN** project has no crawled pages
- **THEN** button shows "Start Onboarding" and navigates to URL upload page

## ADDED Requirements

### Requirement: Onboarding progress tracking
The project detail view SHALL display onboarding progress from phase_status.

#### Scenario: Progress bar shows overall completion
- **WHEN** project has onboarding in progress
- **THEN** progress bar shows percentage complete across all onboarding steps

#### Scenario: Individual step status shown
- **WHEN** project has partial onboarding progress
- **THEN** each step shows status: completed (checkmark), in progress (dot), pending (empty)

### Requirement: Onboarding quick stats
The project detail view SHALL display key statistics for onboarding.

#### Scenario: URL count displayed
- **WHEN** project has crawled pages
- **THEN** section shows "X pages" count

#### Scenario: Failed crawl count highlighted
- **WHEN** project has failed crawls
- **THEN** section shows failed count in warning style

#### Scenario: Labels status displayed
- **WHEN** taxonomy has been generated
- **THEN** section shows "Labels assigned" or "Labels pending" status
