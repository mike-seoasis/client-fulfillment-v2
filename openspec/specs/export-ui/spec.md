## ADDED Requirements

### Requirement: Export page exists at onboarding Step 5
The system SHALL render an export page at `/projects/{id}/onboarding/export` that shows as Step 5 ("Export") in the onboarding stepper, with all previous steps marked complete.

#### Scenario: Navigate to export page
- **WHEN** user clicks "Continue to Export" from the content list page
- **THEN** the export page SHALL load with the stepper showing Export as the active step

#### Scenario: Direct URL access
- **WHEN** user navigates directly to `/projects/{id}/onboarding/export`
- **THEN** the page SHALL load and fetch the project's page data for export

### Requirement: Page selection list with approval status
The export page SHALL display a list of all project pages with:
- Checkbox for selection (checked by default for approved pages)
- Page URL (displayed as path, e.g., `/collections/running-shoes`)
- Approval status indicator (approved or not)
- Unapproved pages SHALL have their checkbox disabled and appear visually muted

#### Scenario: All pages approved
- **WHEN** all pages have approved content
- **THEN** all checkboxes SHALL be checked and enabled

#### Scenario: Some pages not approved
- **WHEN** some pages have unapproved or incomplete content
- **THEN** those pages SHALL appear with disabled checkboxes and a visual indicator showing they need approval first

#### Scenario: Uncheck a page
- **WHEN** user unchecks an approved page
- **THEN** that page SHALL be excluded from the export count and download

### Requirement: Export summary
The page SHALL display an export summary showing:
- Count of selected pages (e.g., "Ready to export: 6 pages")
- List of fields being exported (Handle, Title, Body HTML, SEO Description, Top Description)
- Format indicator: "CSV - Matrixify compatible"

#### Scenario: Summary updates on selection change
- **WHEN** user checks or unchecks pages
- **THEN** the "Ready to export" count SHALL update immediately

### Requirement: Download export button
The page SHALL have a "Download Export" button that triggers the CSV file download.

#### Scenario: Successful download
- **WHEN** user clicks "Download Export" with at least one page selected
- **THEN** the browser SHALL download a CSV file named `{project-name}-matrixify-export.csv`

#### Scenario: No pages selected
- **WHEN** no pages are selected (all unchecked)
- **THEN** the "Download Export" button SHALL be disabled

#### Scenario: Download in progress
- **WHEN** the download request is in flight
- **THEN** the button SHALL show a loading state and be disabled to prevent double-clicks

### Requirement: Finish onboarding flow
The page SHALL have a "Finish Onboarding" button that navigates back to the project detail page.

#### Scenario: Finish onboarding
- **WHEN** user clicks "Finish Onboarding"
- **THEN** the user SHALL be navigated to `/projects/{id}`

### Requirement: Back navigation
The page SHALL have a "Back" button or link that navigates to the content list page.

#### Scenario: Navigate back
- **WHEN** user clicks "Back"
- **THEN** the user SHALL be navigated to `/projects/{id}/onboarding/content`
