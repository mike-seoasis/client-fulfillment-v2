## ADDED Requirements

### Requirement: URL upload via text input
The system SHALL accept URLs pasted into a textarea, one URL per line.

#### Scenario: Paste multiple URLs
- **WHEN** user pastes URLs into the textarea (one per line)
- **THEN** system parses and displays each URL in a preview list

#### Scenario: Empty lines are ignored
- **WHEN** user pastes text with empty lines between URLs
- **THEN** empty lines are filtered out and only valid URLs appear in preview

### Requirement: URL upload via CSV file
The system SHALL accept CSV file uploads containing URLs.

#### Scenario: Upload CSV with URL column
- **WHEN** user uploads a CSV file with a column named "url" or "URL"
- **THEN** system extracts URLs from that column and displays in preview list

#### Scenario: Upload CSV without URL column
- **WHEN** user uploads a CSV where first column contains URLs (no header or different header)
- **THEN** system extracts URLs from first column and displays in preview list

#### Scenario: Invalid file type rejected
- **WHEN** user attempts to upload a non-CSV file (e.g., .xlsx, .pdf)
- **THEN** system displays error "Please upload a CSV file"

### Requirement: URL format validation
The system SHALL validate that each URL has proper format before accepting.

#### Scenario: Valid HTTP/HTTPS URLs accepted
- **WHEN** user enters URLs starting with http:// or https://
- **THEN** URLs are marked as valid in the preview list

#### Scenario: Invalid URL format rejected
- **WHEN** user enters a URL without protocol or with invalid format
- **THEN** URL is marked as invalid with error "Invalid URL format"

#### Scenario: Duplicate URLs deduplicated
- **WHEN** user enters the same URL multiple times
- **THEN** only one instance appears in the preview list

### Requirement: URL normalization
The system SHALL normalize URLs for consistent storage.

#### Scenario: Trailing slashes normalized
- **WHEN** user enters URLs with inconsistent trailing slashes
- **THEN** URLs are normalized to consistent format (with trailing slash for paths)

#### Scenario: Case normalized
- **WHEN** user enters URLs with mixed case domains
- **THEN** domain portion is lowercased, path case is preserved

### Requirement: URL preview list
The system SHALL display a preview list of URLs before starting crawl.

#### Scenario: Preview shows URL count
- **WHEN** user has entered valid URLs
- **THEN** system displays "X URLs to process" count

#### Scenario: Preview allows removal
- **WHEN** user clicks remove button on a URL in preview list
- **THEN** URL is removed from the list

#### Scenario: Preview shows validation status
- **WHEN** user views the preview list
- **THEN** each URL shows a status indicator (valid/invalid)

### Requirement: Domain warning
The system SHALL warn (not block) when URLs are from different domains than project site_url.

#### Scenario: Same domain URLs pass silently
- **WHEN** user enters URLs matching the project's site_url domain
- **THEN** no warning is displayed

#### Scenario: Different domain URLs show warning
- **WHEN** user enters URLs from a different domain than project's site_url
- **THEN** warning is displayed: "Some URLs are from a different domain"

### Requirement: Start crawl action
The system SHALL provide a button to start crawling when valid URLs are present.

#### Scenario: Start crawl button enabled with valid URLs
- **WHEN** user has at least one valid URL in preview
- **THEN** "Start Crawl" button is enabled

#### Scenario: Start crawl button disabled without URLs
- **WHEN** preview list is empty or all URLs are invalid
- **THEN** "Start Crawl" button is disabled

#### Scenario: Start crawl submits URLs to backend
- **WHEN** user clicks "Start Crawl"
- **THEN** system POSTs URLs to `/api/v1/projects/{id}/urls` and navigates to crawl progress page
