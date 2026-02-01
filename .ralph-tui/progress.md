# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### LLM-Based Classification Services
When building LLM-based classification services (like PAA categorization):
- Use batch processing with configurable batch size (default 10) and max concurrency (default 5)
- Use `asyncio.Semaphore` for rate limiting concurrent LLM calls
- Handle markdown code blocks in LLM responses (strip ``` wrappers)
- Match results back to original inputs case-insensitively (normalize with `.lower().strip()`)
- Return UNKNOWN for unmatched items rather than failing
- Use dataclasses for structured results (e.g., `CategorizationResult`, `CategorizationItem`)
- Track token usage across batches for cost monitoring
- Provide both `categorize_questions()` (strings) and `categorize_paa_questions()` (objects) methods

### Service Singleton Pattern
Services follow a consistent singleton pattern:
```python
_service_instance: ServiceClass | None = None

def get_service() -> ServiceClass:
    global _service_instance
    if _service_instance is None:
        _service_instance = ServiceClass()
        logger.info("ServiceClass singleton created")
    return _service_instance
```

### Error Logging Requirements
All services implement these logging patterns:
- DEBUG: Method entry/exit with parameters (sanitized), cache operations
- INFO: State transitions, operation completion, batch statistics
- WARNING: Slow operations (>1000ms), fallback triggers, validation failures
- ERROR: Exceptions with full stack trace, API failures
- Always include `project_id` and `page_id` in log extra for traceability

### Fallback Persona Generation Pattern
When no reviews are available, generate personas from website analysis:
- Add `needs_review` and `fallback_used` flags to result dataclasses
- Use Perplexity to analyze brand website/positioning for persona inference
- Limit generated personas to 3 maximum
- Flag results with `needs_review=True` when fallback is used (for user validation)
- Make fallback opt-in via `use_fallback` parameter (default True)
- Gracefully handle fallback failures (return empty personas, don't fail the overall operation)

### Startup Recovery Pattern
When implementing background job recovery for interrupted operations:
- Add a dedicated recovery service (e.g., `CrawlRecoveryService`) separate from the main service
- Use dataclasses for structured results: `InterruptedCrawl`, `RecoveryResult`, `RecoverySummary`
- Query for abandoned jobs: `WHERE status IN ('running', 'pending') AND updated_at < cutoff_time`
- Default stale threshold: 5 minutes (configurable via parameter)
- Store recovery metadata in existing JSONB stats field: `stats.recovery = {interrupted: true, recovery_reason, ...}`
- Add new status value (e.g., "interrupted") or mark as "failed" with metadata
- Integration: Call recovery in main.py lifespan after database init, before scheduler start
- Don't fail app startup if recovery fails—log error and continue
- Always include `crawl_id`, `project_id` in recovery logs for traceability

### WebSocket Client Pattern
When building WebSocket clients for real-time updates:
- Use `websockets` library for async WebSocket connections
- Implement connection state machine: DISCONNECTED → CONNECTING → CONNECTED → RECONNECTING → CLOSED
- Use dataclasses for configuration: `WebSocketClientConfig`, `ReconnectConfig`, `CircuitBreakerConfig`
- Implement heartbeat/ping mechanism to keep connections alive (Railway idle timeout is ~60s)
- Use exponential backoff for reconnection: `delay = min(initial * (backoff ** attempt), max_delay)`
- Add circuit breaker with failure_threshold and recovery_timeout
- Implement polling fallback when WebSocket unavailable (for Railway deploy resilience)
- Re-subscribe to projects automatically on reconnection
- Mask sensitive data (tokens, keys) in all log messages using regex
- Use `type: ignore[attr-defined]` for websockets imports (library has incomplete stubs)
- Test async iterators must block (not return immediately) to prevent receive_loop completion

---

## 2026-02-01 - client-onboarding-v2-c3y.69
- What was implemented: Fallback persona generation when no reviews available
- Files changed:
  - `backend/app/integrations/amazon_reviews.py` - Added `FallbackPersona` dataclass, `FALLBACK_PERSONA_PROMPT`, `generate_fallback_personas()` method, updated `analyze_brand_reviews()` to use fallback
  - `backend/app/services/amazon_reviews.py` - Added `needs_review`, `fallback_used`, `fallback_source` fields to `ReviewAnalysisResult`, updated `analyze_reviews()` method signature
  - `backend/app/schemas/amazon_reviews.py` - Updated `CustomerPersonaResponse`, `AmazonReviewAnalysisRequest`, `AmazonReviewAnalysisResponse` with new fields
  - `backend/tests/integrations/test_amazon_reviews_fallback.py` - 20 comprehensive tests (all passing)
- **Learnings:**
  - Per brand-config spec: when no reviews available, generate fallback persona from website analysis and flag as "needs_review"
  - FallbackPersona includes: name, description, source ("website_analysis"), inferred (True), characteristics (list)
  - Perplexity temperature 0.3 for slightly creative but grounded persona generation
  - Fallback personas are converted to dict format matching existing persona structure for API consistency
  - Test integration directory needed `__init__.py` file creation
  - The `_parse_json_from_response()` helper handles markdown code block wrapping in LLM responses
---

## 2026-02-01 - client-onboarding-v2-c3y.60
- What was implemented: PAA question categorization by intent (buying, usage, care, comparison)
- Files already exist (implementation was complete):
  - `backend/app/services/paa_enrichment.py` - Contains `PAAQuestionIntent` enum and integration
  - `backend/app/services/paa_categorization.py` - Full categorization service with LLM
  - `backend/tests/services/test_paa_categorization.py` - 32 unit tests (all passing)
- **Learnings:**
  - The feature was already fully implemented in a previous iteration
  - `PAAQuestionIntent` enum defined in paa_enrichment.py with values: BUYING, USAGE, CARE, COMPARISON, UNKNOWN
  - Categorization uses Claude LLM with temperature=0.0 for deterministic results
  - Integration point: `enrich_keyword()` accepts `categorize_enabled=True` to auto-categorize
  - Confidence scores: 0.8-1.0 (clear), 0.6-0.8 (likely), 0.4-0.6 (unclear)
---

## 2026-02-01 - client-onboarding-v2-c3y.102
- What was implemented: Startup recovery for interrupted crawls
- Files changed:
  - `backend/app/services/crawl_recovery.py` - New service with `CrawlRecoveryService`, dataclasses (`InterruptedCrawl`, `RecoveryResult`, `RecoverySummary`), methods for finding and recovering interrupted crawls
  - `backend/app/main.py` - Added import and call to `run_startup_recovery()` in lifespan after database/scheduler init
  - `backend/app/services/crawl.py` - Added "interrupted" to valid crawl statuses in `_validate_crawl_status()`
  - `backend/app/schemas/crawl.py` - Added "interrupted" to `VALID_CRAWL_STATUSES` frozenset
  - `backend/tests/services/test_crawl_recovery.py` - 35+ comprehensive tests covering all recovery scenarios
- **Learnings:**
  - Crawls left in "running" state during server restart become orphaned—recovery detects via `updated_at < cutoff_time`
  - Recovery stores metadata in `stats.recovery` JSONB field: interrupted flag, timestamp, previous status, progress at interruption
  - Setting `mark_as_failed=True` (default) marks recovered crawls as "failed"; `mark_as_failed=False` uses new "interrupted" status
  - Error message is set on recovery describing the interruption and progress made
  - Session-scoped service (not singleton) since recovery runs once at startup with a dedicated db session
  - Recovery is non-blocking: errors are logged but don't prevent app startup
  - Updated both service validation and schema constants to accept "interrupted" as valid status
---

## 2026-02-01 - client-onboarding-v2-c3y.111
- What was implemented: WebSocket client for real-time updates
- Files changed:
  - `backend/app/clients/__init__.py` - New module for client connections
  - `backend/app/clients/websocket_client.py` - Full WebSocket client implementation with connection management, heartbeat, reconnection, circuit breaker, and polling fallback
  - `backend/tests/clients/__init__.py` - Tests module
  - `backend/tests/clients/test_websocket_client.py` - 42 comprehensive tests (all passing)
  - `backend/pyproject.toml` - Added `websockets>=12.0` dependency and mypy override
- **Learnings:**
  - websockets library returns an async context manager from `connect()`, mock with `side_effect` returning coroutine
  - Receive loop completes immediately with empty async iterator, use blocking iterator in tests
  - Heartbeat loop sleeps first, then sends ping—wait longer than heartbeat_interval in tests
  - Use `lambda _self: iter()` pattern to mock `__aiter__` with underscore prefix to satisfy ARG005
  - Circuit breaker state machine: CLOSED → OPEN (after failures) → HALF_OPEN (after recovery timeout) → CLOSED (on success)
  - Polling fallback converts WebSocket URL to HTTP by replacing ws:// with http://
  - Railway deployment: implement heartbeat (30s default), handle reconnection gracefully during deploys
---

