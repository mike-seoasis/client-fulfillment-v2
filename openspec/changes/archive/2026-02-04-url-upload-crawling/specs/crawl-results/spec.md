## ADDED Requirements

### Requirement: Crawl progress display
The system SHALL display real-time crawl progress with overall status.

#### Scenario: Progress bar shows completion
- **WHEN** user views crawl progress page
- **THEN** progress bar shows X of Y pages completed

#### Scenario: Progress updates via polling
- **WHEN** crawl is in progress
- **THEN** page polls `/api/v1/projects/{id}/crawl-status` every 2 seconds

#### Scenario: Polling stops when complete
- **WHEN** all pages are completed or failed
- **THEN** polling stops automatically

### Requirement: Per-page status display
The system SHALL display status for each individual page being crawled.

#### Scenario: Pending pages show waiting status
- **WHEN** page has status "pending"
- **THEN** page row shows "Pending" with neutral indicator

#### Scenario: Crawling pages show in-progress status
- **WHEN** page has status "crawling"
- **THEN** page row shows "Crawling..." with spinner indicator

#### Scenario: Completed pages show success status
- **WHEN** page has status "completed"
- **THEN** page row shows checkmark with extracted data summary

#### Scenario: Failed pages show error status
- **WHEN** page has status "failed"
- **THEN** page row shows error icon with crawl_error message

### Requirement: Extracted data summary per page
The system SHALL display a summary of extracted data for completed pages.

#### Scenario: Title displayed
- **WHEN** page is completed
- **THEN** page row shows extracted title

#### Scenario: Word count displayed
- **WHEN** page is completed
- **THEN** page row shows word count (e.g., "245 words")

#### Scenario: Heading count displayed
- **WHEN** page is completed
- **THEN** page row shows heading counts (e.g., "H2s: 3")

#### Scenario: Product count displayed when available
- **WHEN** page is completed and has product_count
- **THEN** page row shows product count (e.g., "24 products")

### Requirement: Crawl status API
The system SHALL provide an API endpoint for crawl status.

#### Scenario: Status endpoint returns progress
- **WHEN** client calls GET `/api/v1/projects/{id}/crawl-status`
- **THEN** response contains status, progress object, and pages array

#### Scenario: Progress object has counts
- **WHEN** client calls crawl-status endpoint
- **THEN** progress contains total, completed, failed, and pending counts

#### Scenario: Pages array has per-page status
- **WHEN** client calls crawl-status endpoint
- **THEN** pages array contains id, url, status, and extracted data for each page

### Requirement: Taxonomy generation status display
The system SHALL display taxonomy generation status after crawling completes.

#### Scenario: Taxonomy generation shows progress
- **WHEN** taxonomy generation is in progress
- **THEN** UI shows "Generating label taxonomy..." with spinner

#### Scenario: Taxonomy complete shows labels
- **WHEN** taxonomy generation completes
- **THEN** UI shows generated label count and list of labels

### Requirement: Label assignment display
The system SHALL display label assignments for each page after taxonomy is generated.

#### Scenario: Labels shown per page
- **WHEN** page has labels assigned
- **THEN** page row displays assigned labels as tags/chips

#### Scenario: Labels editable via dropdown
- **WHEN** user clicks edit on page labels
- **THEN** dropdown shows all taxonomy labels with checkboxes

#### Scenario: Label changes saved immediately
- **WHEN** user selects/deselects labels in dropdown
- **THEN** changes are saved via PUT `/api/v1/projects/{id}/pages/{page_id}/labels`

### Requirement: Navigation after crawl complete
The system SHALL provide navigation to next workflow step.

#### Scenario: Continue button appears when complete
- **WHEN** crawling and labeling are complete
- **THEN** "Continue to Keywords" button appears

#### Scenario: Continue button disabled during crawl
- **WHEN** crawling is still in progress
- **THEN** continue button is disabled

### Requirement: Retry failed pages
The system SHALL allow retrying failed page crawls.

#### Scenario: Retry button on failed pages
- **WHEN** page has status "failed"
- **THEN** page row shows "Retry" button

#### Scenario: Retry resets page to pending
- **WHEN** user clicks retry on a failed page
- **THEN** page status changes to "pending" and crawl is re-attempted
