# Primary Keyword Generation

Service that generates, enriches, filters, and scores keyword candidates for crawled pages.

## ADDED Requirements

### Requirement: Generate keyword candidates from page content
The system SHALL generate 20-25 keyword candidates for each crawled page by analyzing URL path, title, headings, body content, and product count using Claude AI.

#### Scenario: Successful candidate generation
- **WHEN** generation is triggered for a crawled page with title "Men's Trail Running Shoes" and URL "/collections/mens-trail-running-shoes"
- **THEN** system generates 20-25 keyword candidates including variations like "mens trail running shoes", "trail running shoes for men", "best mens trail shoes"

#### Scenario: Generation with minimal page content
- **WHEN** generation is triggered for a page with only URL and title (no body content)
- **THEN** system generates candidates based on URL path and title, returning at least 10 candidates

#### Scenario: Generation failure fallback
- **WHEN** Claude API call fails during generation
- **THEN** system uses page title and H1 as fallback candidates

### Requirement: Enrich candidates with search volume data
The system SHALL enrich all keyword candidates with search volume, CPC, and competition data from DataForSEO API.

#### Scenario: Successful enrichment
- **WHEN** 25 keyword candidates are submitted for enrichment
- **THEN** system returns volume, CPC, and competition (0-1 scale) for each keyword

#### Scenario: Batch enrichment for large candidate sets
- **WHEN** more than 100 keywords need enrichment across multiple pages
- **THEN** system batches requests to DataForSEO (max 1000 per request) with controlled concurrency

#### Scenario: DataForSEO unavailable
- **WHEN** DataForSEO API is unavailable or circuit breaker is open
- **THEN** system continues without volume data and flags keywords for retry

### Requirement: Filter candidates to page-specific keywords
The system SHALL filter keyword candidates to only those specific to the page's exact topic, removing generic category terms.

#### Scenario: Successful specificity filtering
- **WHEN** candidates include "mens trail running shoes", "trail running shoes", and "running shoes" for a mens trail running page
- **THEN** system keeps "mens trail running shoes" and "trail running shoes for men" but removes "running shoes" as too generic

#### Scenario: Filter with relevance scores
- **WHEN** filtering is performed
- **THEN** each remaining keyword receives a relevance score (0.0-1.0) indicating confidence of specificity

### Requirement: Score and rank keywords using weighted formula
The system SHALL calculate a composite score for each keyword using: 50% volume + 35% relevance + 15% competition.

#### Scenario: Score calculation
- **WHEN** a keyword has volume=8100, relevance=0.95, competition=0.7
- **THEN** system calculates composite score as approximately 48.5

#### Scenario: Ranking by score
- **WHEN** multiple keywords have scores calculated
- **THEN** keywords are ranked by composite score descending, with highest score as primary

### Requirement: Select primary and alternative keywords
The system SHALL select the highest-scoring keyword as primary and store the next 4 highest as alternatives.

#### Scenario: Primary selection
- **WHEN** scoring is complete for a page
- **THEN** system selects highest composite score keyword as primary_keyword

#### Scenario: Alternative storage
- **WHEN** primary is selected
- **THEN** system stores next 4 highest-scoring keywords in alternative_keywords JSON field

#### Scenario: Duplicate prevention
- **WHEN** the highest-scoring keyword is already used as primary for another page in the project
- **THEN** system selects the next highest-scoring unused keyword as primary

### Requirement: Process pages as background task with progress tracking
The system SHALL process keyword generation as a background task with progress updates for frontend polling.

#### Scenario: Background processing initiation
- **WHEN** POST /projects/{id}/generate-primary-keywords is called
- **THEN** system returns 202 Accepted with task_id and starts background processing

#### Scenario: Progress polling
- **WHEN** GET /projects/{id}/primary-keywords-status is called during processing
- **THEN** system returns current progress (pages completed, pages total, current status)

#### Scenario: Completion status
- **WHEN** all pages have been processed
- **THEN** status endpoint returns status="complete" and stops polling

### Requirement: Store AI reasoning for transparency
The system SHALL store the AI's reasoning for keyword selection to enable debugging and user understanding.

#### Scenario: Reasoning storage
- **WHEN** primary keyword is selected
- **THEN** system stores explanation in ai_reasoning field (e.g., "Highest volume specific keyword matching page topic")
