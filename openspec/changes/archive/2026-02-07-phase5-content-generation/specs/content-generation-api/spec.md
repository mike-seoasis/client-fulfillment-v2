# Content Generation API

API endpoints for triggering content generation, polling progress, retrieving content, and fetching prompt logs.

## ADDED Requirements

### Requirement: Trigger content generation as background task
The system SHALL provide an endpoint to start content generation for all pages with approved keywords.

#### Scenario: Successful generation trigger
- **WHEN** `POST /projects/{id}/generate-content` is called and project has pages with approved keywords
- **THEN** system returns 202 Accepted, starts a background task that processes each approved page through the pipeline (brief → write → check), and uses asyncio.Semaphore to control concurrency (default 1 for dev, configurable via CONTENT_GENERATION_CONCURRENCY)

#### Scenario: No approved keywords
- **WHEN** `POST /projects/{id}/generate-content` is called but no pages have approved keywords
- **THEN** system returns 400 Bad Request with message explaining that keywords must be approved first

#### Scenario: Generation already in progress
- **WHEN** `POST /projects/{id}/generate-content` is called while a generation task is already running
- **THEN** system returns 409 Conflict with message that generation is already in progress

### Requirement: Poll generation progress
The system SHALL provide an endpoint to check generation status across all pages.

#### Scenario: Progress during generation
- **WHEN** `GET /projects/{id}/content-generation-status` is called during generation
- **THEN** system returns: overall status ("generating", "complete", "failed"), pages_total, pages_completed, pages_failed, and per-page status array with [{page_id, url, keyword, status, error}]

#### Scenario: Generation complete
- **WHEN** `GET /projects/{id}/content-generation-status` is called after all pages finish
- **THEN** system returns overall status "complete" with pages_completed equal to pages_total (minus any failures)

#### Scenario: No generation started
- **WHEN** `GET /projects/{id}/content-generation-status` is called and no generation has been triggered
- **THEN** system returns overall status "idle" with counts at 0

### Requirement: Retrieve generated content for a page
The system SHALL provide an endpoint to get the full generated content, brief, and quality results for a specific page.

#### Scenario: Content exists
- **WHEN** `GET /projects/{id}/pages/{page_id}/content` is called for a page with generated content
- **THEN** system returns PageContent fields (page_title, meta_description, top_description, bottom_description, word_count, status), associated ContentBrief summary (lsi_terms count, keyword), and qa_results

#### Scenario: Content not yet generated
- **WHEN** `GET /projects/{id}/pages/{page_id}/content` is called for a page without generated content
- **THEN** system returns 404 with message that content has not been generated yet

### Requirement: Fetch prompt logs for prompt inspector
The system SHALL provide an endpoint to retrieve all prompts sent to Claude for a specific page.

#### Scenario: Prompts exist
- **WHEN** `GET /projects/{id}/pages/{page_id}/prompts` is called for a page that has been through content generation
- **THEN** system returns array of PromptLog records ordered by created_at, each with: step, role, prompt_text, response_text, model, input_tokens, output_tokens, duration_ms, created_at

#### Scenario: No prompts
- **WHEN** `GET /projects/{id}/pages/{page_id}/prompts` is called for a page without prompt logs
- **THEN** system returns an empty array

### Requirement: Pipeline processes pages with configurable concurrency
The system SHALL process pages in parallel using asyncio.Semaphore with configurable limit.

#### Scenario: Sequential processing (dev)
- **WHEN** CONTENT_GENERATION_CONCURRENCY=1
- **THEN** pages are processed one at a time sequentially

#### Scenario: Parallel processing (production)
- **WHEN** CONTENT_GENERATION_CONCURRENCY=5
- **THEN** up to 5 pages are processed concurrently, each running its own sequential pipeline (brief → write → check)

#### Scenario: Error isolation
- **WHEN** one page fails during generation
- **THEN** other pages continue processing normally; the failed page is marked with status "failed" and error details
