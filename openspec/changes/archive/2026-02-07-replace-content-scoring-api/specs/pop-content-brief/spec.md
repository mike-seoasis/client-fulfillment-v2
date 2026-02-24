# pop-content-brief

Integration with PageOptimizer Pro API to fetch SERP-based content targets after keyword approval.

## ADDED Requirements

### Requirement: System fetches content brief from POP API

The system SHALL call the PageOptimizer Pro API to create a report task for a given keyword and target URL, then poll for results until completion or timeout.

#### Scenario: Successful content brief fetch
- **WHEN** a content brief is requested for keyword "best running shoes" with target URL "https://example.com/running-shoes"
- **THEN** the system creates a POP report task with the keyword and URL
- **AND** polls the task status endpoint every 3 seconds
- **AND** returns the complete content brief when task status is "SUCCESS"

#### Scenario: POP API timeout
- **WHEN** a content brief is requested and POP task does not complete within 5 minutes
- **THEN** the system stops polling
- **AND** returns an error indicating timeout
- **AND** logs the timeout with task_id for debugging

#### Scenario: POP API authentication failure
- **WHEN** a content brief is requested with invalid API credentials
- **THEN** the system returns an authentication error
- **AND** does not retry the request
- **AND** logs the failure (without exposing credentials)

### Requirement: Content brief includes word count targets

The system SHALL extract word count targets from the POP response, including minimum, maximum, and recommended values based on competitor analysis.

#### Scenario: Word count targets extracted
- **WHEN** POP returns a successful content brief
- **THEN** the content brief includes `word_count_target` (recommended)
- **AND** includes `word_count_min` (competitor minimum)
- **AND** includes `word_count_max` (competitor maximum)

### Requirement: Content brief includes heading structure targets

The system SHALL extract heading structure targets from the POP response, specifying recommended counts for H1, H2, H3, and H4 tags.

#### Scenario: Heading targets extracted
- **WHEN** POP returns a successful content brief
- **THEN** the content brief includes heading targets with `h1_min`, `h1_max`, `h2_min`, `h2_max`, `h3_min`, `h3_max`, `h4_min`, `h4_max`

### Requirement: Content brief includes keyword density targets

The system SHALL extract keyword density targets from the POP response, specifying target counts for the primary keyword in different page sections (title, H1, H2, H3, paragraph text).

#### Scenario: Keyword density targets extracted
- **WHEN** POP returns a successful content brief for keyword "best running shoes"
- **THEN** the content brief includes keyword targets per section
- **AND** each section target includes `current` (if URL provided), `target`, and `section_name`

### Requirement: Content brief includes LSI/semantic terms

The system SHALL extract LSI (Latent Semantic Indexing) terms from the POP response, including term phrases, weights, and target counts.

#### Scenario: LSI terms extracted
- **WHEN** POP returns a successful content brief
- **THEN** the content brief includes an array of LSI terms
- **AND** each term includes `phrase`, `weight`, `average_count` (competitor average), and `target_count`

### Requirement: Content brief includes related questions (PAA)

The system SHALL extract related questions (People Also Ask) from the POP response for potential use in content planning.

#### Scenario: Related questions extracted
- **WHEN** POP returns a successful content brief
- **THEN** the content brief includes an array of related questions
- **AND** each question includes `question`, `link`, `snippet`, and `title`

### Requirement: Content brief includes competitor data

The system SHALL extract competitor analysis data from the POP response, including competitor URLs, page scores, and content metrics.

#### Scenario: Competitor data extracted
- **WHEN** POP returns a successful content brief
- **THEN** the content brief includes an array of competitors
- **AND** each competitor includes `url`, `title`, `page_score`, and `word_count`

### Requirement: Content brief is persisted to database

The system SHALL store the content brief in the database linked to the page/keyword for use during content generation.

#### Scenario: Content brief stored
- **WHEN** a content brief is successfully fetched from POP
- **THEN** the system stores the brief in the `content_briefs` table
- **AND** links it to the page via `page_id`
- **AND** stores the `pop_task_id` for reference
- **AND** stores structured fields (word count, headings, keywords)
- **AND** stores the full `raw_response` for debugging

#### Scenario: Existing brief is replaced
- **WHEN** a content brief is fetched for a page that already has a brief
- **THEN** the system replaces the existing brief with the new one
- **AND** updates the `created_at` timestamp

### Requirement: Circuit breaker prevents cascading failures

The system SHALL implement a circuit breaker that stops calling POP API after repeated failures.

#### Scenario: Circuit opens after failures
- **WHEN** 5 consecutive POP API calls fail
- **THEN** the circuit breaker opens
- **AND** subsequent requests immediately return an error without calling POP
- **AND** logs the circuit state change

#### Scenario: Circuit recovers after timeout
- **WHEN** the circuit has been open for 60 seconds
- **THEN** the circuit enters half-open state
- **AND** allows one test request through
- **AND** closes the circuit if the test succeeds

### Requirement: API credentials are never logged

The system SHALL mask API credentials in all log output to prevent credential exposure.

#### Scenario: Credentials masked in logs
- **WHEN** any POP API interaction is logged
- **THEN** the `apiKey` parameter is masked (e.g., "PARTNER_****")
- **AND** no log message contains the full API key
