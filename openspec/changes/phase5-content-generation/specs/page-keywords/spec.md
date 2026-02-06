# Page Keywords

Data model for storing primary keywords, approval status, and related metadata.

## MODIFIED Requirements

### Requirement: Validate keyword approval before content generation
The system SHALL require that a page's primary keyword is approved before content can be generated for that page.

#### Scenario: Content generation with approved keyword
- **WHEN** content generation is triggered for a page with is_approved=true
- **THEN** page is included in the content generation pipeline

#### Scenario: Content generation with unapproved keyword
- **WHEN** content generation is triggered for a page with is_approved=false
- **THEN** page is skipped in the content generation pipeline (not treated as an error — simply not included)

#### Scenario: Bulk generation filters to approved only
- **WHEN** `POST /projects/{id}/generate-content` is called
- **THEN** system filters to only pages where PageKeywords.is_approved=true and processes only those pages
