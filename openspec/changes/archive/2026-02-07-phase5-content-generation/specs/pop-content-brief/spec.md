# POP Content Brief

Service that fetches content optimization data from PageOptimizer Pro API and stores structured brief data for content writing.

## ADDED Requirements

### Requirement: Fetch LSI terms via POP get-terms endpoint
The system SHALL call the POP get-terms API endpoint with the approved primary keyword and target URL, poll for completion, and return structured LSI term data.

#### Scenario: Successful get-terms fetch
- **WHEN** `fetch_content_brief()` is called with keyword "mens trail running shoes" and URL "https://example.com/collections/mens-trail-running-shoes"
- **THEN** system POSTs to `/api/expose/get-terms/` with keyword, targetUrl, locationName, targetLanguage, polls for task completion, and returns parsed lsaPhrases array with phrase, weight, averageCount, and targetCount for each term

#### Scenario: POP API unavailable
- **WHEN** POP API returns an error or circuit breaker is open
- **THEN** system returns a failure result with error details and does NOT block content generation (content can still be written without LSI terms)

#### Scenario: POP task timeout
- **WHEN** POP task does not complete within the configured timeout (default 300s)
- **THEN** system returns a failure result with timeout error and stores partial data if available

### Requirement: Parse and store content brief data
The system SHALL parse the POP get-terms response into a ContentBrief database record with structured fields.

#### Scenario: Successful parsing and storage
- **WHEN** POP get-terms task completes successfully
- **THEN** system creates a ContentBrief record with: keyword, lsi_terms (from lsaPhrases), related_searches (from variations), raw_response (full API response), and pop_task_id

#### Scenario: Store prepareId for future use
- **WHEN** POP get-terms response includes a prepareId
- **THEN** system stores prepareId in the ContentBrief raw_response for potential future create-report calls

### Requirement: Support mock mode for development
The system SHALL provide a mock POP client that returns realistic fixture data when `POP_USE_MOCK=true`.

#### Scenario: Mock mode returns fixture data
- **WHEN** `POP_USE_MOCK=true` and `fetch_content_brief()` is called with any keyword
- **THEN** system returns a ContentBrief with 15-25 realistic LSI terms derived from the keyword, with varied weights and counts, without making any API calls

#### Scenario: Mock mode is deterministic
- **WHEN** mock mode is called twice with the same keyword
- **THEN** system returns the same fixture data both times (seeded by keyword hash)

### Requirement: Cache POP responses to conserve credits
The system SHALL check for an existing ContentBrief before making a new API call.

#### Scenario: Brief already exists for page
- **WHEN** `fetch_content_brief()` is called for a page that already has a ContentBrief record
- **THEN** system returns the existing brief without making an API call

#### Scenario: Force refresh
- **WHEN** `fetch_content_brief()` is called with `force_refresh=True` for a page with existing brief
- **THEN** system makes a new API call and replaces the existing ContentBrief record
