# POP Integration Logging Reference

This document describes log fields and levels for the POP (PageOptimizer Pro) integration, intended for ops/monitoring teams.

## Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Method entry/exit, request/response bodies (truncated), detailed diagnostics |
| INFO | Phase transitions, scoring results, task lifecycle, API calls |
| WARNING | Fallback events, circuit breaker changes, retries, validation failures |
| ERROR | Exceptions with stack traces, service failures |

## Loggers

| Logger | Component |
|--------|-----------|
| `app.integrations.pop` | POP API client |
| `app.services.pop_content_brief` | Content brief service |
| `app.services.pop_content_score` | Content scoring service |
| `app.api.v1.endpoints.content_brief` | Content brief endpoints |
| `app.api.v1.endpoints.pop_content_score` | Content scoring endpoints |

## Common Log Fields

These fields appear across all POP-related logs:

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | string | Project UUID |
| `page_id` | string | Page UUID |
| `request_id` | string | HTTP request UUID for correlation |
| `task_id` | string | POP task UUID |
| `duration_ms` | float | Operation duration in milliseconds |

## POP Client Logs (app.integrations.pop)

### API Request/Response

**Level:** INFO (call), DEBUG (body)

```json
{
  "message": "POP API request",
  "method": "POST",
  "endpoint": "/api/v1/report",
  "duration_ms": 234.56,
  "status_code": 200
}
```

Body logging (DEBUG only):
```json
{
  "message": "POP request body",
  "body": "{truncated if >5KB}",
  "body_size_bytes": 1234
}
```

**Note:** API key is NEVER logged - `_mask_api_key()` redacts it.

### Task Creation

**Level:** INFO

```json
{
  "message": "POP task created",
  "task_id": "pop-task-abc123",
  "keyword": "target keyword",
  "url": "https://example.com/page"
}
```

### Task Polling

**Level:** INFO (start/complete), DEBUG (each poll)

```json
{
  "message": "poll_for_result_started",
  "task_id": "pop-task-abc123",
  "poll_interval": 2.0,
  "timeout": 300
}
```

Poll attempt (DEBUG):
```json
{
  "message": "Poll attempt",
  "task_id": "pop-task-abc123",
  "poll_attempt": 5,
  "status": "PROCESSING",
  "elapsed_ms": 10234
}
```

Completion:
```json
{
  "message": "poll_for_result_completed",
  "task_id": "pop-task-abc123",
  "status": "SUCCESS",
  "total_polls": 12,
  "duration_ms": 24567.89
}
```

### Timeout

**Level:** ERROR

```json
{
  "message": "POP task timeout",
  "task_id": "pop-task-abc123",
  "elapsed_ms": 300456,
  "configured_timeout_seconds": 300,
  "poll_count": 150
}
```

### Rate Limiting (429)

**Level:** WARNING

```json
{
  "message": "POP rate limited",
  "status_code": 429,
  "retry_after": 30,
  "retry_after_present": true,
  "retry_attempt": 2,
  "max_retries": 3
}
```

### Auth Failure (401/403)

**Level:** ERROR

```json
{
  "message": "POP auth failure",
  "status_code": 401,
  "credentials_logged": false
}
```

### Retry Attempts

**Level:** WARNING

```json
{
  "message": "POP request retry",
  "retry_attempt": 2,
  "max_retries": 3,
  "error": "Connection timeout",
  "backoff_delay": 4.0
}
```

### Circuit Breaker State Changes

**Level:** WARNING

```json
{
  "message": "Circuit breaker state change",
  "previous_state": "CLOSED",
  "new_state": "OPEN",
  "failure_count": 5,
  "failure_threshold": 5
}
```

```json
{
  "message": "Circuit breaker state change",
  "previous_state": "OPEN",
  "new_state": "HALF_OPEN",
  "recovery_timeout": 60.0
}
```

### API Credits/Cost

**Level:** INFO

```json
{
  "message": "scoring_api_cost",
  "task_id": "pop-task-abc123",
  "credits_used": 1,
  "credits_remaining": 9999
}
```

## Content Brief Service Logs (app.services.pop_content_brief)

### Method Entry/Exit

**Level:** DEBUG

```json
{
  "message": "fetch_brief_entry",
  "project_id": "proj-123",
  "page_id": "page-456",
  "keyword": "target keyword (sanitized)"
}
```

```json
{
  "message": "fetch_brief_exit",
  "project_id": "proj-123",
  "page_id": "page-456",
  "brief_id": "brief-789",
  "success": true
}
```

### Phase Transitions

**Level:** INFO

```json
{
  "message": "brief_fetch_started",
  "project_id": "proj-123",
  "page_id": "page-456",
  "keyword": "target keyword"
}
```

```json
{
  "message": "brief_fetch_completed",
  "project_id": "proj-123",
  "page_id": "page-456",
  "brief_id": "brief-789",
  "task_id": "pop-task-abc123",
  "duration_ms": 5234.56
}
```

### Extraction Stats

**Level:** INFO

```json
{
  "message": "brief_extraction_stats",
  "project_id": "proj-123",
  "page_id": "page-456",
  "word_count_target": 1500,
  "word_count_min": 1200,
  "word_count_max": 1800,
  "lsi_term_count": 45,
  "competitor_count": 10,
  "heading_target_count": 4,
  "keyword_target_count": 12,
  "related_question_count": 8,
  "page_score_target": 85
}
```

### Validation Failures

**Level:** WARNING

```json
{
  "message": "Validation failed",
  "field": "keyword",
  "value": "",
  "reason": "keyword cannot be empty",
  "project_id": "proj-123",
  "page_id": "page-456"
}
```

## Content Score Service Logs (app.services.pop_content_score)

### Method Entry/Exit

**Level:** DEBUG

```json
{
  "message": "score_content_entry",
  "project_id": "proj-123",
  "page_id": "page-456",
  "keyword": "target keyword",
  "content_url": "https://example.com (sanitized)"
}
```

```json
{
  "message": "score_content_exit",
  "project_id": "proj-123",
  "page_id": "page-456",
  "score_id": "score-789",
  "page_score": 72.5,
  "passed": true,
  "fallback_used": false
}
```

### Phase Transitions

**Level:** INFO

```json
{
  "message": "scoring_started",
  "project_id": "proj-123",
  "page_id": "page-456",
  "keyword": "target keyword"
}
```

```json
{
  "message": "scoring_completed",
  "project_id": "proj-123",
  "page_id": "page-456",
  "score_id": "score-789",
  "task_id": "pop-task-abc123",
  "duration_ms": 8234.56
}
```

### Scoring Results

**Level:** INFO

```json
{
  "message": "scoring_results",
  "project_id": "proj-123",
  "page_id": "page-456",
  "score_id": "score-789",
  "page_score": 72.5,
  "passed": true,
  "recommendation_count": 12,
  "prioritized_recommendation_count": 5,
  "fallback_used": false
}
```

### Extraction Stats

**Level:** INFO

```json
{
  "message": "score_extraction_stats",
  "project_id": "proj-123",
  "page_id": "page-456",
  "page_score": 72.5,
  "word_count_current": 1456,
  "word_count_target": 1500,
  "lsi_coverage_percent": 78.5,
  "keyword_sections_analyzed": 4,
  "heading_levels_analyzed": 4,
  "recommendation_count": 12
}
```

### Fallback Events

**Level:** WARNING

```json
{
  "message": "Falling back to legacy scoring",
  "reason": "circuit_open",
  "project_id": "proj-123",
  "page_id": "page-456",
  "keyword": "target keyword"
}
```

Reasons: `circuit_open`, `timeout`, `api_error`

### Shadow Mode Comparison

**Level:** INFO

```json
{
  "message": "shadow_comparison_metrics",
  "project_id": "proj-123",
  "page_id": "page-456",
  "pop_score": 75.5,
  "legacy_score": 68.2,
  "score_difference": 7.3,
  "pop_passed": true,
  "legacy_passed": false,
  "pass_agreement": false,
  "pop_success": true,
  "legacy_success": true,
  "pop_duration_ms": 5234,
  "legacy_duration_ms": 156
}
```

## Endpoint Logs (app.api.v1.endpoints.*)

### Request Logging

**Level:** DEBUG

```json
{
  "message": "Content brief fetch request",
  "request_id": "req-abc123",
  "project_id": "proj-123",
  "page_id": "page-456",
  "keyword": "target keyw... (truncated)"
}
```

### Response Logging

**Level:** INFO (success), WARNING (4xx), ERROR (5xx)

```json
{
  "message": "Content brief fetch complete",
  "request_id": "req-abc123",
  "project_id": "proj-123",
  "page_id": "page-456",
  "brief_id": "brief-789",
  "success": true,
  "duration_ms": 5234.56
}
```

### Batch Scoring Statistics

**Level:** INFO

```json
{
  "message": "Batch content score complete",
  "request_id": "req-abc123",
  "project_id": "proj-123",
  "total_items": 10,
  "successful_items": 9,
  "failed_items": 1,
  "items_passed": 7,
  "items_failed_threshold": 2,
  "fallback_count": 1,
  "duration_ms": 15234.56
}
```

## Slow Operation Threshold

Operations exceeding `SLOW_OPERATION_THRESHOLD_MS` (1000ms) are logged at WARNING:

```json
{
  "message": "Slow content scoring operation",
  "duration_ms": 5234.56,
  "threshold_ms": 1000,
  "project_id": "proj-123",
  "page_id": "page-456"
}
```

## Error Logging

**Level:** ERROR

All errors include full stack traces via `exc_info=True`:

```json
{
  "message": "Content scoring exception",
  "error_type": "POPTimeoutError",
  "error_message": "Task pop-task-abc123 timed out after 300 seconds",
  "project_id": "proj-123",
  "page_id": "page-456",
  "duration_ms": 300456.78
}
```

## Log Correlation

Use these fields to correlate related logs:

1. **`request_id`**: Correlates all logs within a single HTTP request
2. **`task_id`**: Correlates all logs for a POP async task
3. **`project_id` + `page_id`**: Correlates all operations for a specific page

Example query (pseudo-SQL):
```sql
SELECT * FROM logs
WHERE request_id = 'req-abc123'
ORDER BY timestamp;
```

## Monitoring Queries

### Circuit Breaker Opens (Last 24h)

```sql
SELECT COUNT(*), DATE_TRUNC('hour', timestamp) as hour
FROM logs
WHERE message = 'Circuit breaker state change'
  AND new_state = 'OPEN'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;
```

### Fallback Rate

```sql
SELECT
  COUNT(*) FILTER (WHERE fallback_used = true) as fallback_count,
  COUNT(*) as total_count,
  ROUND(100.0 * COUNT(*) FILTER (WHERE fallback_used = true) / COUNT(*), 2) as fallback_rate
FROM logs
WHERE message = 'scoring_results'
  AND timestamp > NOW() - INTERVAL '1 hour';
```

### Pass Rate

```sql
SELECT
  COUNT(*) FILTER (WHERE passed = true) as passed_count,
  COUNT(*) as total_count,
  ROUND(100.0 * COUNT(*) FILTER (WHERE passed = true) / COUNT(*), 2) as pass_rate
FROM logs
WHERE message = 'scoring_results'
  AND timestamp > NOW() - INTERVAL '1 hour';
```

### Shadow Mode Agreement Rate

```sql
SELECT
  COUNT(*) FILTER (WHERE pass_agreement = true) as agreement_count,
  COUNT(*) as total_count,
  ROUND(100.0 * COUNT(*) FILTER (WHERE pass_agreement = true) / COUNT(*), 2) as agreement_rate,
  AVG(score_difference) as avg_score_diff
FROM logs
WHERE message = 'shadow_comparison_metrics'
  AND timestamp > NOW() - INTERVAL '1 hour';
```

### API Credit Usage

```sql
SELECT
  SUM(credits_used) as total_credits_used,
  MIN(credits_remaining) as min_credits_remaining
FROM logs
WHERE message = 'scoring_api_cost'
  AND timestamp > NOW() - INTERVAL '24 hours';
```
