# POP (PageOptimizer Pro) API Integration

This document describes the integration between the client onboarding system and the PageOptimizer Pro (POP) API for SERP-based content optimization scoring.

## Overview

The POP integration provides two main capabilities:

1. **Content Brief**: Fetch content optimization targets (word count, LSI terms, heading structure, keyword density) before content generation
2. **Content Scoring**: Score generated content against SERP competitors and provide actionable recommendations

## API Endpoints

### Content Brief Endpoints

Base path: `/api/v1/projects/{project_id}/phases/content_brief`

#### POST /fetch

Fetch a content brief from POP API for a keyword/URL.

**Query Parameters:**
- `page_id` (required): UUID of the crawled page to associate the brief with

**Request Body:**
```json
{
  "keyword": "target keyword phrase",
  "target_url": "https://example.com/page-to-analyze"
}
```

**Response:**
```json
{
  "success": true,
  "brief": {
    "id": "uuid",
    "page_id": "uuid",
    "keyword": "target keyword phrase",
    "pop_task_id": "pop-task-123",
    "word_count_target": 1500,
    "word_count_min": 1200,
    "word_count_max": 1800,
    "heading_targets": [...],
    "keyword_targets": [...],
    "lsi_terms": [...],
    "entities": [...],
    "related_questions": [...],
    "related_searches": [...],
    "competitors": [...],
    "page_score_target": 85,
    "created_at": "2026-02-02T12:00:00Z",
    "updated_at": "2026-02-02T12:00:00Z"
  },
  "error": null,
  "duration_ms": 5234.56
}
```

**Error Responses:**
- `404`: Project or page not found
- `422`: Validation error (missing page_id, empty keyword)
- `500`: Internal server error or POP API failure

#### GET /pages/{page_id}/brief

Get the existing content brief for a specific page.

**Response:** Same as POST /fetch, but returns the cached brief from the database.

### Content Scoring Endpoints

Base path: `/api/v1/projects/{project_id}/phases/content_score`

#### POST /score

Score content for a single page.

**Query Parameters:**
- `page_id` (required): UUID of the crawled page to score

**Request Body:**
```json
{
  "keyword": "target keyword phrase",
  "content_url": "https://example.com/page-to-score"
}
```

**Response:**
```json
{
  "success": true,
  "score": {
    "id": "uuid",
    "page_id": "uuid",
    "pop_task_id": "pop-task-456",
    "page_score": 72.5,
    "passed": true,
    "keyword_analysis": {...},
    "lsi_coverage": {...},
    "word_count_current": 1456,
    "heading_analysis": {...},
    "recommendations": [...],
    "fallback_used": false,
    "scored_at": "2026-02-02T12:05:00Z",
    "created_at": "2026-02-02T12:05:00Z"
  },
  "error": null,
  "fallback_used": false,
  "duration_ms": 8123.45
}
```

**Error Responses:**
- `404`: Project or page not found
- `422`: Validation error (missing page_id, empty keyword)
- `500`: Internal server error or POP API failure

#### POST /batch

Score content for multiple pages concurrently.

**Query Parameters:**
- `page_ids` (required): Comma-separated list of page UUIDs (must match items count)

**Request Body:**
```json
{
  "items": [
    {"keyword": "keyword 1", "content_url": "https://example.com/page1"},
    {"keyword": "keyword 2", "content_url": "https://example.com/page2"}
  ],
  "max_concurrent": 5
}
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "page_id": "uuid1",
      "keyword": "keyword 1",
      "success": true,
      "score_id": "uuid",
      "page_score": 72.5,
      "passed": true,
      "fallback_used": false,
      "error": null
    },
    {
      "page_id": "uuid2",
      "keyword": "keyword 2",
      "success": false,
      "error": "POP API timeout"
    }
  ],
  "total_items": 2,
  "successful_items": 1,
  "failed_items": 1,
  "items_passed": 1,
  "items_failed_threshold": 0,
  "fallback_count": 0,
  "error": null,
  "duration_ms": 15234.56
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POP_API_KEY` | PageOptimizer Pro API key | (required) |
| `POP_API_URL` | POP API base URL | `https://api.pageoptimizer.pro` |
| `USE_POP_CONTENT_BRIEF` | Enable POP for content briefs | `false` |
| `USE_POP_SCORING` | Enable POP for content scoring | `false` |
| `POP_SHADOW_MODE` | Run both POP and legacy for comparison | `false` |
| `POP_PASS_THRESHOLD` | Minimum score to pass (0-100) | `70` |
| `POP_TASK_POLL_INTERVAL` | Task polling interval (seconds) | `2.0` |
| `POP_TASK_TIMEOUT` | Maximum task wait time (seconds) | `300` |
| `POP_CIRCUIT_FAILURE_THRESHOLD` | Failures before circuit opens | `5` |
| `POP_CIRCUIT_RECOVERY_TIMEOUT` | Circuit recovery time (seconds) | `60.0` |
| `POP_MAX_RETRIES` | Maximum retry attempts | `3` |
| `POP_RETRY_DELAY` | Initial retry delay (seconds) | `1.0` |
| `POP_BATCH_RATE_LIMIT` | Max concurrent batch requests | `5` |

### Feature Flags

The integration uses feature flags for safe rollout:

- **`USE_POP_CONTENT_BRIEF=false`**: When disabled, content generation proceeds without POP brief data
- **`USE_POP_SCORING=false`**: When disabled, uses legacy `ContentScoreService` for local content analysis
- **`POP_SHADOW_MODE=false`**: When enabled, runs both POP and legacy scoring for comparison (returns legacy result)

## Fallback Behavior

When POP scoring is enabled but fails, the system automatically falls back to the legacy `ContentScoreService`:

### Fallback Triggers

1. **Circuit Breaker Open**: After 5 consecutive failures, the circuit opens and requests immediately fall back
2. **API Timeout**: If POP task doesn't complete within 300 seconds
3. **API Errors**: After retry attempts are exhausted (5xx errors, rate limits)

### Fallback Indicators

- `fallback_used: true` in response indicates fallback was used
- Fallback events logged at WARNING level with reason (`circuit_open`, `timeout`, `api_error`)
- Legacy score (0.0-1.0) converted to POP scale (0-100)

### Non-Fallback Legacy Usage

When `USE_POP_SCORING=false`, the legacy service is used intentionally (not as a fallback):
- `fallback_used: false` in response
- Logs indicate "Using legacy ContentScoreService (POP scoring disabled)"

## Shadow Mode

Shadow mode enables validation of POP scoring before full cutover:

```bash
POP_SHADOW_MODE=true
```

When enabled:
- Runs both POP and legacy scoring in parallel
- Logs comparison metrics for analysis
- Returns legacy result (production behavior unchanged)
- Metrics include score difference, pass/fail agreement, timing

### Shadow Comparison Metrics

```json
{
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

## Monitoring Alerts

### Recommended Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| POP Circuit Open | Circuit breaker enters OPEN state | High |
| High Fallback Rate | >20% of scoring requests use fallback | Medium |
| POP Timeout Spike | >5% of requests timeout | Medium |
| Pass Rate Deviation | Pass rate deviates >10% from shadow baseline | Low |
| API Cost Anomaly | Daily credits used exceeds budget | Medium |

### Key Metrics to Monitor

- `scoring_results.page_score` - Score distribution
- `scoring_results.passed` - Pass/fail ratio
- `scoring_results.fallback_used` - Fallback usage
- `scoring_api_cost.credits_used` - API credit consumption
- Circuit breaker state changes

## Logging Reference

See [LOGGING.md](./LOGGING.md) for comprehensive logging documentation.

### Quick Reference - Log Levels

| Event | Level | Logger |
|-------|-------|--------|
| API call start/complete | INFO | `app.integrations.pop` |
| Request/response bodies | DEBUG | `app.integrations.pop` |
| Task polling | INFO | `app.integrations.pop` |
| Retry attempts | WARNING | `app.integrations.pop` |
| Circuit state change | WARNING | `app.integrations.pop` |
| Fallback triggered | WARNING | `app.services.pop_content_score` |
| Scoring results | INFO | `app.services.pop_content_score` |
| Shadow comparison | INFO | `app.services.pop_content_score` |

## Database Tables

### content_briefs

Stores fetched content briefs:
- Links to `crawled_pages` via `page_id`
- Upsert behavior: existing brief replaced on re-fetch
- JSONB columns: `heading_targets`, `keyword_targets`, `lsi_terms`, `entities`, `related_questions`, `related_searches`, `competitors`, `raw_response`

### content_scores

Stores scoring results:
- Links to `crawled_pages` via `page_id`
- Append behavior: each scoring creates new record for history
- JSONB columns: `keyword_analysis`, `lsi_coverage`, `heading_analysis`, `recommendations`, `raw_response`
- `fallback_used` boolean indicates whether legacy service was used
- `scored_at` timestamp for when scoring was performed

## Migration Path

### Phase 1: Shadow Mode (Current)
1. Enable shadow mode: `POP_SHADOW_MODE=true`
2. Monitor comparison metrics
3. Validate scoring accuracy

### Phase 2: Gradual Rollout
1. Enable POP scoring: `USE_POP_SCORING=true`
2. Monitor fallback rate
3. Adjust pass threshold if needed

### Phase 3: Full Cutover
1. Disable shadow mode: `POP_SHADOW_MODE=false`
2. Remove legacy service dependency (optional - keep for fallback)
3. Archive legacy scoring code

## Troubleshooting

### Common Issues

**"POP circuit breaker is open"**
- Check POP API status
- Review recent error logs for root cause
- Circuit recovers automatically after 60 seconds

**High timeout rate**
- Check POP task queue status
- Consider increasing `POP_TASK_TIMEOUT`
- Verify network connectivity

**Score discrepancy with legacy**
- Expected due to different algorithms
- Use shadow mode metrics to establish baseline
- Review keyword and content quality

**Missing content brief data**
- Brief fetch is optional; content generation proceeds without
- Check for validation errors in logs
- Verify keyword and URL are valid
