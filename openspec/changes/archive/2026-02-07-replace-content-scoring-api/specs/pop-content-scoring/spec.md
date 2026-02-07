# pop-content-scoring

Integration with PageOptimizer Pro API to score generated content against SERP-based targets.

## ADDED Requirements

### Requirement: System scores content via POP API

The system SHALL call the PageOptimizer Pro API to score generated content for a given keyword and content URL/HTML, returning a page score and detailed breakdown.

#### Scenario: Successful content scoring
- **WHEN** content scoring is requested for keyword "best running shoes" with the generated content URL
- **THEN** the system creates a POP report task for the URL
- **AND** polls until completion
- **AND** returns the page score (0-100) and detailed metrics

#### Scenario: Scoring with HTML content instead of URL
- **WHEN** content scoring is requested with raw HTML content (no published URL)
- **THEN** the system submits the HTML to POP for analysis
- **AND** returns the same scoring metrics as URL-based scoring

### Requirement: Score response includes overall page score

The system SHALL extract the overall page score from the POP response as a number between 0 and 100.

#### Scenario: Page score extracted
- **WHEN** POP returns a successful scoring result
- **THEN** the response includes `page_score` as an integer 0-100
- **AND** includes `page_score_value` as the display string (e.g., "78")

### Requirement: Score response includes keyword density analysis

The system SHALL extract keyword density analysis showing current vs target counts for the primary keyword in each page section.

#### Scenario: Keyword density breakdown returned
- **WHEN** POP returns a successful scoring result
- **THEN** the response includes keyword analysis per section (title, H1, H2, H3, paragraph)
- **AND** each section shows `current` count and `target` count
- **AND** indicates whether the section is under, optimal, or over-optimized

### Requirement: Score response includes LSI term coverage

The system SHALL extract LSI term coverage showing which semantic terms are present and which are missing.

#### Scenario: LSI coverage analysis returned
- **WHEN** POP returns a successful scoring result
- **THEN** the response includes LSI term analysis
- **AND** each term shows `phrase`, `current_count`, `target_count`, and `weight`
- **AND** terms are sorted by importance (weight)

### Requirement: Score response includes word count comparison

The system SHALL extract word count comparison showing current word count vs competitor-derived targets.

#### Scenario: Word count comparison returned
- **WHEN** POP returns a successful scoring result
- **THEN** the response includes `word_count_current` and `word_count_target`
- **AND** indicates whether content is under, optimal, or over the target

### Requirement: Score response includes heading structure analysis

The system SHALL extract heading structure analysis showing current vs target counts for each heading level.

#### Scenario: Heading structure analysis returned
- **WHEN** POP returns a successful scoring result
- **THEN** the response includes heading analysis (H1, H2, H3, H4 counts)
- **AND** each level shows `current`, `min`, `max`, and `mean` (competitor average)
- **AND** includes recommendation text (e.g., "Reduce H2 count by 2")

### Requirement: Score response includes actionable recommendations

The system SHALL extract custom recommendations from the POP response, providing specific actions to improve the score.

#### Scenario: Recommendations returned
- **WHEN** POP returns a successful scoring result
- **THEN** the response includes a list of recommendations
- **AND** each recommendation includes `signal` (what to change), `comment` (action), `current`, and `target`

### Requirement: Scoring result is persisted to database

The system SHALL store the scoring result in the database linked to the content/page for historical tracking.

#### Scenario: Score stored
- **WHEN** content is successfully scored via POP
- **THEN** the system stores the score in the `content_scores` table
- **AND** links it to the page via `page_id`
- **AND** stores the overall `page_score`
- **AND** stores the `scored_at` timestamp
- **AND** stores the `raw_response` for detailed analysis

### Requirement: Score indicates pass/fail status

The system SHALL determine whether content passes quality threshold based on the page score.

#### Scenario: Content passes scoring threshold
- **WHEN** content receives a page score of 70 or higher
- **THEN** the response includes `passed: true`

#### Scenario: Content fails scoring threshold
- **WHEN** content receives a page score below 70
- **THEN** the response includes `passed: false`
- **AND** includes prioritized recommendations for improvement

### Requirement: Fallback to legacy scoring when POP unavailable

The system SHALL fall back to the legacy `ContentScoreService` when the POP API is unavailable.

#### Scenario: Fallback triggered on circuit open
- **WHEN** content scoring is requested and the POP circuit breaker is open
- **THEN** the system uses `ContentScoreService` for scoring
- **AND** the response includes `fallback: true` flag
- **AND** logs the fallback event

#### Scenario: Fallback triggered on API error
- **WHEN** POP API returns an error during scoring
- **THEN** the system falls back to `ContentScoreService`
- **AND** logs the error and fallback

### Requirement: Scoring supports batch operations

The system SHALL support scoring multiple content pieces in a single batch request for efficiency.

#### Scenario: Batch scoring request
- **WHEN** scoring is requested for 5 content URLs
- **THEN** the system creates POP tasks for each URL (respecting rate limits)
- **AND** returns results as they complete
- **AND** includes individual success/failure status per item

### Requirement: API costs are logged for monitoring

The system SHALL log API usage costs for each scoring request to enable cost monitoring.

#### Scenario: Cost logged per request
- **WHEN** a scoring request completes
- **THEN** the system logs the cost (if provided by POP)
- **AND** includes the `pop_task_id` for reconciliation
