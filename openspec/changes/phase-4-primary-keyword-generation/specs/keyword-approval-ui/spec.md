# Keyword Approval UI

Frontend interface for reviewing, selecting, and approving primary keywords.

## ADDED Requirements

### Requirement: Display keywords page in onboarding flow
The system SHALL display a keywords approval page as Step 3 of 5 in the onboarding flow, accessible after crawling is complete.

#### Scenario: Navigation from crawl complete
- **WHEN** crawling is complete and user clicks "Continue"
- **THEN** system navigates to /projects/{id}/onboarding/keywords

#### Scenario: Step indicator display
- **WHEN** keywords page is displayed
- **THEN** step indicator shows Step 3 of 5 (Upload → Crawl → Keywords → Content → Export)

### Requirement: Show generation progress during processing
The system SHALL display progress indicator while keywords are being generated, polling every 2 seconds.

#### Scenario: Generation in progress
- **WHEN** keyword generation is running
- **THEN** system displays progress bar with "Generating keywords... X of Y pages"

#### Scenario: Polling stops on completion
- **WHEN** generation status returns "complete"
- **THEN** system stops polling and displays the keyword list

### Requirement: Display page list with keyword data
The system SHALL display a list of pages with their primary keyword, search volume, and approval status.

#### Scenario: Page row display
- **WHEN** keywords page loads with completed generation
- **THEN** each row shows: page URL (truncated), page title, primary keyword, search volume badge, composite score, approval status

#### Scenario: Volume formatting
- **WHEN** search volume is displayed
- **THEN** volumes are formatted with commas (e.g., "8,100") and "—" for no data

### Requirement: Enable alternative keyword selection
The system SHALL allow users to select a different primary keyword from the top 5 alternatives via dropdown.

#### Scenario: Dropdown display
- **WHEN** user clicks on the primary keyword field
- **THEN** system displays dropdown with current primary and up to 4 alternatives, each showing keyword and volume

#### Scenario: Alternative selection
- **WHEN** user selects an alternative keyword
- **THEN** system updates primary_keyword to selected value and saves immediately

### Requirement: Enable inline keyword editing
The system SHALL allow users to manually type a custom keyword if none of the alternatives are suitable.

#### Scenario: Manual edit mode
- **WHEN** user clicks "Edit" or types in the keyword field
- **THEN** system allows free text entry for custom keyword

#### Scenario: Save manual edit
- **WHEN** user enters custom keyword and presses Enter or clicks away
- **THEN** system saves the custom keyword as primary_keyword (no volume data)

### Requirement: Enable priority toggle
The system SHALL allow users to mark pages as "priority" for internal linking emphasis.

#### Scenario: Toggle priority on
- **WHEN** user clicks priority toggle (star icon) for a page
- **THEN** system sets is_priority=true and displays filled star icon

#### Scenario: Toggle priority off
- **WHEN** user clicks priority toggle on an already-priority page
- **THEN** system sets is_priority=false and displays empty star icon

### Requirement: Enable individual keyword approval
The system SHALL allow users to approve keywords one at a time.

#### Scenario: Approve single keyword
- **WHEN** user clicks "Approve" button for a page
- **THEN** system sets is_approved=true and displays checkmark

#### Scenario: Unapprove keyword
- **WHEN** user clicks checkmark on an approved keyword
- **THEN** system sets is_approved=false and displays "Approve" button

### Requirement: Enable bulk approval
The system SHALL allow users to approve all unapproved keywords at once.

#### Scenario: Bulk approve all
- **WHEN** user clicks "Approve All" button
- **THEN** system sets is_approved=true for all pages with keywords

#### Scenario: Bulk approve disabled when all approved
- **WHEN** all pages are already approved
- **THEN** "Approve All" button is disabled or hidden

### Requirement: Show approval progress and gate continuation
The system SHALL display approval progress and only enable continuation when all keywords are approved.

#### Scenario: Progress display
- **WHEN** keywords page is displayed
- **THEN** system shows "Approved: X of Y" count

#### Scenario: Continue button enabled
- **WHEN** all pages have is_approved=true
- **THEN** "Continue to Content" button is enabled

#### Scenario: Continue button disabled
- **WHEN** any page has is_approved=false
- **THEN** "Continue to Content" button is disabled with tooltip "Approve all keywords to continue"

### Requirement: Display score breakdown on hover
The system SHALL show the composite score breakdown when user hovers over the score.

#### Scenario: Score tooltip
- **WHEN** user hovers over composite score
- **THEN** system displays tooltip with: Volume score, Relevance score, Competition score, and formula weights
