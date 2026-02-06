# Page Keywords

Data model for storing primary keywords, approval status, and related metadata.

## ADDED Requirements

### Requirement: Store approval status
The system SHALL track whether a primary keyword has been approved by the user.

#### Scenario: Default unapproved
- **WHEN** a new PageKeywords record is created
- **THEN** is_approved defaults to false

#### Scenario: Approval persistence
- **WHEN** user approves a keyword via API
- **THEN** is_approved is set to true and persisted

### Requirement: Store priority flag
The system SHALL track whether a page is marked as priority for internal linking.

#### Scenario: Default not priority
- **WHEN** a new PageKeywords record is created
- **THEN** is_priority defaults to false

#### Scenario: Priority toggle
- **WHEN** user toggles priority via API
- **THEN** is_priority value is updated and persisted

### Requirement: Store alternative keywords
The system SHALL store up to 5 alternative keyword options with their scores.

#### Scenario: Alternative storage format
- **WHEN** keyword generation completes
- **THEN** alternative_keywords contains JSON array of objects with keyword, volume, and score

#### Scenario: Alternative structure
- **WHEN** alternative_keywords is queried
- **THEN** each entry has format: {"keyword": "string", "volume": number|null, "score": number}

### Requirement: Store composite score
The system SHALL store the calculated composite score for the primary keyword.

#### Scenario: Score storage
- **WHEN** primary keyword is selected
- **THEN** composite_score is stored as float (0-100 scale)

### Requirement: Store relevance score
The system SHALL store the AI-determined relevance score from the filtering step.

#### Scenario: Relevance storage
- **WHEN** keyword filtering completes
- **THEN** relevance_score is stored as float (0.0-1.0 scale)

### Requirement: Store AI reasoning
The system SHALL store the AI's explanation for keyword selection.

#### Scenario: Reasoning storage
- **WHEN** primary keyword is selected
- **THEN** ai_reasoning contains text explanation of selection rationale

### Requirement: Establish relationship with CrawledPage
The system SHALL maintain a one-to-one relationship between CrawledPage and PageKeywords.

#### Scenario: Relationship query
- **WHEN** CrawledPage is loaded with keywords
- **THEN** associated PageKeywords record is accessible via relationship

#### Scenario: Cascade delete
- **WHEN** CrawledPage is deleted
- **THEN** associated PageKeywords record is also deleted

### Requirement: API endpoints for keyword management
The system SHALL provide API endpoints for keyword CRUD operations.

#### Scenario: List pages with keywords
- **WHEN** GET /projects/{id}/pages-with-keywords is called
- **THEN** system returns all crawled pages with their PageKeywords data

#### Scenario: Update primary keyword
- **WHEN** PUT /projects/{id}/pages/{page_id}/primary-keyword is called with new keyword
- **THEN** system updates primary_keyword field and clears volume data if custom

#### Scenario: Approve keyword
- **WHEN** POST /projects/{id}/pages/{page_id}/approve-keyword is called
- **THEN** system sets is_approved=true

#### Scenario: Bulk approve
- **WHEN** POST /projects/{id}/approve-all-keywords is called
- **THEN** system sets is_approved=true for all pages in project

#### Scenario: Toggle priority
- **WHEN** PUT /projects/{id}/pages/{page_id}/priority is called
- **THEN** system toggles is_priority value
