# Content Editing

Backend API and service layer for updating content fields, approval workflow, re-running quality checks, and content field validation.

## ADDED Requirements

### Requirement: Update content fields for a page
The system SHALL provide an endpoint to save edited content for a single page.

#### Scenario: Successful content update
- **WHEN** `PUT /projects/{project_id}/pages/{page_id}/content` is called with a body containing any combination of `page_title`, `meta_description`, `top_description`, `bottom_description`
- **THEN** system updates the specified fields on the PageContent record, recalculates `word_count` by stripping HTML tags from all 4 fields and counting words, sets `updated_at` to now, and returns the updated PageContentResponse

#### Scenario: Partial update (only some fields provided)
- **WHEN** the request body omits one or more content fields (e.g., only `page_title` is sent)
- **THEN** system updates only the provided fields and leaves omitted fields unchanged

#### Scenario: Content does not exist
- **WHEN** `PUT /projects/{project_id}/pages/{page_id}/content` is called for a page without generated content
- **THEN** system returns 404 with message "Content has not been generated for this page"

#### Scenario: Clears approval on edit
- **WHEN** content is updated on a page that was previously approved (`is_approved=true`)
- **THEN** system sets `is_approved` to false and `approved_at` to null, because edits invalidate prior approval

### Requirement: Approve or unapprove content for a page
The system SHALL provide an endpoint to toggle content approval status.

#### Scenario: Approve content
- **WHEN** `POST /projects/{project_id}/pages/{page_id}/approve-content` is called with `value=true` (default)
- **THEN** system sets `is_approved` to true, `approved_at` to current timestamp, and returns the updated PageContentResponse

#### Scenario: Unapprove content
- **WHEN** `POST /projects/{project_id}/pages/{page_id}/approve-content` is called with `value=false`
- **THEN** system sets `is_approved` to false, `approved_at` to null, and returns the updated PageContentResponse

#### Scenario: Approve content that has not been generated
- **WHEN** `POST /projects/{project_id}/pages/{page_id}/approve-content` is called for a page without generated content or with status not "complete"
- **THEN** system returns 400 with message "Content must be fully generated before approval"

### Requirement: Re-run quality checks after editing
The system SHALL provide an endpoint to re-run the deterministic AI trope quality checks on the current content.

#### Scenario: Successful re-check
- **WHEN** `POST /projects/{project_id}/pages/{page_id}/recheck-content` is called for a page with status "complete"
- **THEN** system runs `run_quality_checks()` using the current content field values and brand config, stores updated results in `qa_results`, and returns the updated PageContentResponse with fresh qa_results

#### Scenario: Re-check with no content
- **WHEN** `POST /projects/{project_id}/pages/{page_id}/recheck-content` is called for a page without generated content
- **THEN** system returns 404 with message "Content has not been generated for this page"

### Requirement: Bulk approve all passing content
The system SHALL provide an endpoint to approve all pages that have complete content and passing quality checks.

#### Scenario: Bulk approve
- **WHEN** `POST /projects/{project_id}/bulk-approve-content` is called
- **THEN** system finds all PageContent records for the project where `status="complete"` and `qa_results.passed=true` and `is_approved=false`, sets each to `is_approved=true` with `approved_at=now()`, and returns a count of how many were approved

#### Scenario: No pages eligible
- **WHEN** `POST /projects/{project_id}/bulk-approve-content` is called but no pages meet the criteria
- **THEN** system returns 200 with `approved_count: 0`

### Requirement: Retrieve content brief data for editor sidebar
The system SHALL include content brief data (LSI terms, heading targets, keyword targets) in the page content response so the frontend can build the stats sidebar.

#### Scenario: Content with brief data
- **WHEN** `GET /projects/{project_id}/pages/{page_id}/content` is called for a page with both generated content and a ContentBrief
- **THEN** the response includes a `brief` object containing: `keyword` (string), `lsi_terms` (array of objects with `term` and `min_count` fields), `heading_targets` (array of objects with `level` and `text`), `keyword_targets` (array of objects with `keyword`, `count_min`, `count_max`)

#### Scenario: Content without brief data
- **WHEN** `GET /projects/{project_id}/pages/{page_id}/content` is called for a page with content but no ContentBrief
- **THEN** the response `brief` field is null
