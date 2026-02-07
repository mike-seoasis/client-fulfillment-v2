# Implementation Tasks

## 1. Configuration & Setup

- [ ] 1.1 Add POP API configuration to `app/core/config.py` (api_key, api_url, poll_interval, timeout, circuit breaker settings)
- [ ] 1.2 Add `POP_API_KEY` to `.env.example` with documentation
- [ ] 1.3 Create database migration for `content_briefs` table
- [ ] 1.4 Create database migration for `content_scores` table (POP scores)

## 2. POP Integration Client

- [ ] 2.1 Create `app/integrations/pop.py` with base client structure (httpx async, auth handling)
- [ ] 2.2 Implement `create_report_task()` method (POST to create task with keyword/URL)
- [ ] 2.3 Implement `get_task_result()` method (GET task status/results)
- [ ] 2.4 Implement polling loop with configurable interval and timeout
- [ ] 2.5 Implement circuit breaker (failure threshold, recovery timeout, state transitions)
- [ ] 2.6 Implement retry logic with exponential backoff for transient errors
- [ ] 2.7 Add factory function `get_pop_client()` for dependency injection

### 2.8 Integration Client Logging

- [ ] 2.8.1 Log all outbound API calls with endpoint, method, and timing (INFO level)
- [ ] 2.8.2 Log request/response bodies at DEBUG level (truncate responses >5KB)
- [ ] 2.8.3 Implement credential masking — `apiKey` must never appear in logs
- [ ] 2.8.4 Log timeout errors with task_id, elapsed time, and configured timeout
- [ ] 2.8.5 Log rate limit errors (429) with retry-after header if present
- [ ] 2.8.6 Log auth failures (401/403) without exposing credentials
- [ ] 2.8.7 Include retry attempt number in all retry-related logs
- [ ] 2.8.8 Log API cost/credits used per request (if POP provides this)
- [ ] 2.8.9 Log circuit breaker state changes (CLOSED→OPEN, OPEN→HALF_OPEN, etc.) at WARNING level
- [ ] 2.8.10 Log poll attempts with task_id, attempt number, and current status

- [ ] 2.9 Write unit tests for POP client with mocked responses
- [ ] 2.10 Write unit tests verifying credential masking in logs

## 3. Database Models

- [ ] 3.1 Create `ContentBrief` SQLAlchemy model in `app/models/content_brief.py`
- [ ] 3.2 Create `ContentScore` SQLAlchemy model in `app/models/content_score.py` (for POP scores)
- [ ] 3.3 Add relationships to `CrawledPage` model
- [ ] 3.4 Create Pydantic schemas for content brief request/response in `app/schemas/content_brief.py`
- [ ] 3.5 Create Pydantic schemas for content score request/response in `app/schemas/content_score.py`

## 4. Content Brief Service

- [ ] 4.1 Create `app/services/pop_content_brief.py` with service class structure and ERROR LOGGING REQUIREMENTS docstring
- [ ] 4.2 Implement `fetch_brief()` method that calls POP client and parses response
- [ ] 4.3 Implement word count target extraction (min, max, target)
- [ ] 4.4 Implement heading structure target extraction (H1-H4 counts)
- [ ] 4.5 Implement keyword density target extraction (by section)
- [ ] 4.6 Implement LSI term extraction (phrase, weight, target_count)
- [ ] 4.7 Implement related questions (PAA) extraction
- [ ] 4.8 Implement competitor data extraction
- [ ] 4.9 Implement database persistence (save brief to `content_briefs` table)

### 4.10 Content Brief Service Logging

- [ ] 4.10.1 Log method entry at DEBUG level with parameters (project_id, page_id, keyword — sanitized)
- [ ] 4.10.2 Log method exit at DEBUG level with result summary (success/failure, brief_id)
- [ ] 4.10.3 Log all exceptions with full stack trace, project_id, page_id, and context
- [ ] 4.10.4 Include entity IDs (project_id, page_id, brief_id) in ALL log messages
- [ ] 4.10.5 Log validation failures with field name and rejected value
- [ ] 4.10.6 Log phase state transitions at INFO level (e.g., "brief_fetch_started", "brief_fetch_completed")
- [ ] 4.10.7 Add timing logs for operations >1 second (SLOW_OPERATION_THRESHOLD_MS = 1000)
- [ ] 4.10.8 Log brief extraction stats at INFO level (word_count_target, lsi_term_count, competitor_count)

- [ ] 4.11 Write unit tests for content brief service
- [ ] 4.12 Write unit tests verifying logging output includes required fields

## 5. Content Scoring Service

- [ ] 5.1 Create `app/services/pop_content_score.py` with service class structure and ERROR LOGGING REQUIREMENTS docstring
- [ ] 5.2 Implement `score_content()` method that calls POP client and parses response
- [ ] 5.3 Implement page score extraction (0-100)
- [ ] 5.4 Implement keyword density analysis extraction (current vs target per section)
- [ ] 5.5 Implement LSI term coverage extraction
- [ ] 5.6 Implement word count comparison extraction
- [ ] 5.7 Implement heading structure analysis extraction
- [ ] 5.8 Implement recommendations extraction
- [ ] 5.9 Implement pass/fail determination (threshold: 70)
- [ ] 5.10 Implement fallback to `ContentScoreService` when POP unavailable
- [ ] 5.11 Implement database persistence (save score to `content_scores` table)
- [ ] 5.12 Implement batch scoring support

### 5.13 Content Scoring Service Logging

- [ ] 5.13.1 Log method entry at DEBUG level with parameters (project_id, page_id, content_url — sanitized)
- [ ] 5.13.2 Log method exit at DEBUG level with result summary (score, passed, fallback_used)
- [ ] 5.13.3 Log all exceptions with full stack trace, project_id, page_id, and context
- [ ] 5.13.4 Include entity IDs (project_id, page_id, score_id) in ALL log messages
- [ ] 5.13.5 Log validation failures with field name and rejected value
- [ ] 5.13.6 Log phase state transitions at INFO level (e.g., "scoring_started", "scoring_completed")
- [ ] 5.13.7 Add timing logs for operations >1 second
- [ ] 5.13.8 Log fallback events at WARNING level with reason (circuit_open, api_error, timeout)
- [ ] 5.13.9 Log scoring results at INFO level (page_score, passed, recommendation_count)
- [ ] 5.13.10 Log API cost per scoring request for monitoring/alerting

- [ ] 5.14 Write unit tests for content scoring service
- [ ] 5.15 Write unit tests verifying logging output includes required fields

## 6. API Endpoints

- [ ] 6.1 Create `app/api/v1/endpoints/content_brief.py` with brief endpoints
- [ ] 6.2 Implement `POST /projects/{project_id}/phases/content_brief/fetch` endpoint
- [ ] 6.3 Implement `GET /projects/{project_id}/pages/{page_id}/brief` endpoint
- [ ] 6.4 Create `app/api/v1/endpoints/pop_content_score.py` with scoring endpoints
- [ ] 6.5 Implement `POST /projects/{project_id}/phases/content_score/score` endpoint (single)
- [ ] 6.6 Implement `POST /projects/{project_id}/phases/content_score/batch` endpoint
- [ ] 6.7 Register new endpoints in router
- [ ] 6.8 Add request_id tracking to all endpoint logs for request correlation

## 7. Workflow Integration

- [ ] 7.1 Add feature flag for POP integration (`use_pop_content_brief`, `use_pop_scoring`)
- [ ] 7.2 Update content generation phase to fetch brief first (when flag enabled)
- [ ] 7.3 Pass brief data (word count targets, LSI terms, etc.) to content writer
- [ ] 7.4 Update content scoring phase to use POP scoring (when flag enabled)
- [ ] 7.5 Add "fallback" indicator to scoring responses

## 8. Testing & Validation

- [ ] 8.1 Create integration tests for POP client against real API (skip in CI)
- [ ] 8.2 Create end-to-end test for content brief → generation → scoring flow
- [ ] 8.3 Add shadow mode: run POP scoring alongside legacy, compare results
- [ ] 8.4 Document comparison metrics for validation
- [ ] 8.5 Verify all log messages contain required entity IDs (grep tests)

## 9. Documentation & Cleanup

- [ ] 9.1 Update API documentation with new endpoints
- [ ] 9.2 Add POP integration section to project README
- [ ] 9.3 Document fallback behavior and monitoring alerts
- [ ] 9.4 Document log fields and levels for ops/monitoring team
- [ ] 9.5 Mark `ContentScoreService` as deprecated in docstring (keep for fallback)
