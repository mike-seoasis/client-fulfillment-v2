## ADDED Requirements

### Requirement: Taxonomy generation from all pages
The system SHALL analyze all crawled pages together to generate a unified label taxonomy.

#### Scenario: Claude receives all page data
- **WHEN** taxonomy generation starts
- **THEN** Claude is called with titles and content summaries from all completed pages

#### Scenario: Taxonomy contains 10-30 labels
- **WHEN** Claude generates taxonomy
- **THEN** result contains between 10 and 30 labels appropriate for the page set

#### Scenario: Labels are lowercase single words or short phrases
- **WHEN** taxonomy is generated
- **THEN** labels are lowercase, using hyphens for multi-word concepts (e.g., "trail-running", "waterproof")

### Requirement: Taxonomy storage in project
The system SHALL store the generated taxonomy in project phase_status.

#### Scenario: Taxonomy stored with timestamp
- **WHEN** taxonomy generation completes
- **THEN** phase_status.onboarding.taxonomy contains labels array and generated_at timestamp

#### Scenario: Taxonomy retrievable via API
- **WHEN** client calls GET `/api/v1/projects/{id}/taxonomy`
- **THEN** response contains labels array and generated_at timestamp

### Requirement: Label assignment to pages
The system SHALL assign 2-5 labels from taxonomy to each crawled page.

#### Scenario: Claude assigns labels per page
- **WHEN** taxonomy exists and pages need labeling
- **THEN** Claude assigns 2-5 labels from taxonomy to each page based on content

#### Scenario: Labels stored in CrawledPage
- **WHEN** labels are assigned
- **THEN** CrawledPage.labels contains array of assigned label strings

#### Scenario: All labels are from taxonomy
- **WHEN** labels are assigned to a page
- **THEN** every label in the array exists in the project taxonomy

### Requirement: Label editing by user
The system SHALL allow users to edit label assignments for any page.

#### Scenario: Update labels via API
- **WHEN** client calls PUT `/api/v1/projects/{id}/pages/{page_id}/labels` with labels array
- **THEN** page labels are updated to the provided array

#### Scenario: Invalid labels rejected
- **WHEN** client attempts to assign a label not in taxonomy
- **THEN** API returns 400 error "Label 'xyz' is not in project taxonomy"

#### Scenario: Label count validated
- **WHEN** client attempts to assign fewer than 2 or more than 5 labels
- **THEN** API returns 400 error "Pages must have 2-5 labels"

### Requirement: Taxonomy regeneration
The system SHALL allow regenerating the taxonomy if needed.

#### Scenario: Regenerate taxonomy clears existing
- **WHEN** taxonomy is regenerated
- **THEN** old taxonomy is replaced and all page labels are cleared

#### Scenario: Labels must be reassigned after regeneration
- **WHEN** taxonomy is regenerated
- **THEN** system automatically reassigns labels to all pages using new taxonomy

### Requirement: Labeling status tracking
The system SHALL track labeling progress in project phase_status.

#### Scenario: Status shows labeling in progress
- **WHEN** label assignment is running
- **THEN** phase_status.onboarding.status is "labeling"

#### Scenario: Status shows labels complete
- **WHEN** all pages have labels assigned
- **THEN** phase_status.onboarding.status is "labels_complete"

#### Scenario: Labeling progress tracked
- **WHEN** labeling is in progress
- **THEN** phase_status.onboarding.labeling shows total and labeled counts
