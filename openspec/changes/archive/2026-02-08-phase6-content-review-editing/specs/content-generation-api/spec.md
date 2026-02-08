# Content Generation API

Delta spec for modifications to the existing content generation API capability.

## MODIFIED Requirements

### Requirement: Retrieve generated content for a page
The system SHALL provide an endpoint to get the full generated content, brief, and quality results for a specific page.

#### Scenario: Content exists
- **WHEN** `GET /projects/{id}/pages/{page_id}/content` is called for a page with generated content
- **THEN** system returns PageContent fields (page_title, meta_description, top_description, bottom_description, word_count, status, is_approved, approved_at), associated ContentBrief data (keyword, lsi_terms, heading_targets, keyword_targets), and qa_results

#### Scenario: Content not yet generated
- **WHEN** `GET /projects/{id}/pages/{page_id}/content` is called for a page without generated content
- **THEN** system returns 404 with message that content has not been generated yet

## ADDED Requirements

### Requirement: PageContent model includes approval fields
The system SHALL include `is_approved` and `approved_at` fields on the PageContent model.

#### Scenario: Default state
- **WHEN** a new PageContent record is created during content generation
- **THEN** `is_approved` defaults to false and `approved_at` is null

#### Scenario: Approval fields in response schema
- **WHEN** any endpoint returns a PageContentResponse
- **THEN** the response includes `is_approved` (boolean) and `approved_at` (datetime or null)

### Requirement: Content generation status includes approval counts
The system SHALL include approval status in the generation status response.

#### Scenario: Status with approval info
- **WHEN** `GET /projects/{id}/content-generation-status` is called after generation
- **THEN** the response includes `pages_approved` count in addition to existing fields (pages_total, pages_completed, pages_failed)
