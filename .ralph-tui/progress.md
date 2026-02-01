# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Redis Caching Pattern
- Use `app/core/redis.py` RedisManager for all Redis operations - it handles circuit breaker, connection pooling, SSL/TLS
- Create domain-specific cache services (e.g., `serp_cache.py`, `keyword_cache.py`) that wrap RedisManager
- Cache services follow singleton pattern with `get_*_service()` factory functions
- Cache key format: `{prefix}:{dimension1}:{dimension2}:...:{identifier}`
- Always handle graceful degradation when Redis is unavailable
- Use dataclasses for cached data structures with `cached_at` timestamp

### DataForSEO Integration Pattern
- The client at `app/integrations/dataforseo.py` has its own circuit breaker
- Add `*_cached` methods to integrations that need caching (checks cache first, then API)
- Import cache services inside methods to avoid circular imports

### PAA Fan-Out Pattern
- Use `PAAEnrichmentService` for PAA discovery with optional fan-out
- Fan-out searches initial PAA questions for nested questions (controlled by `fanout_enabled`, `max_fanout_questions`)
- Rate-limit concurrent fan-out with `max_concurrent_fanout` (default 5)
- Use `enrich_keyword_paa_cached()` for cache-aware PAA enrichment (24h TTL)
- Questions are de-duplicated using normalized text (lowercase, stripped)
- Falls back to Related Searches (with LLM semantic filter) when PAA results are insufficient (`fallback_enabled`, `min_paa_for_fallback=3`)

### Related Searches Fallback Pattern
- Use `RelatedSearchesService` for extracting "related searches" from DataForSEO SERP response
- Related searches are extracted from items with `type="related_searches"`
- Apply LLM semantic filter via Claude to assess relevance and convert to question format
- Filter threshold: `min_relevance_score=0.6` (scale 0.0-1.0)
- Cache filtered results with 24h TTL (same as PAA/SERP caching)
- Gracefully degrades if LLM filter fails (returns raw results)
- Question conversion: uses LLM question_form or simple heuristic conversion

### PAA Intent Categorization Pattern
- Use `PAACategorizationService` to classify PAA questions by user intent
- Intent categories: buying (purchase decisions), usage (how-to), care (maintenance), comparison (alternatives)
- Enable via `categorize_enabled=True` in `enrich_keyword()` or `enrich_keyword_paa()`
- Uses Claude LLM with structured JSON output, `temperature=0.0` for consistency
- Batch processing (default 10 questions/batch) with rate-limited concurrency (default 5)
- Confidence scores 0.0-1.0: 0.8+ = clear intent, 0.6-0.8 = likely, <0.6 = ambiguous
- Questions retain `UNKNOWN` intent if categorization fails (graceful degradation)

### Parallel Processing with Rate Limiting Pattern
- Use `asyncio.Semaphore(max_concurrent)` for rate-limited parallel processing
- Standard default: `DEFAULT_MAX_CONCURRENT = 5` across all services
- Pattern: wrap async task in semaphore context manager
  ```python
  semaphore = asyncio.Semaphore(max_concurrent)
  async def process_item(item):
      async with semaphore:
          return await do_work(item)
  tasks = [process_item(x) for x in items]
  results = await asyncio.gather(*tasks)
  ```
- Services using this pattern:
  - `paa_enrichment.py`: fan-out (5) and batch enrichment (5)
  - `paa_categorization.py`: batch LLM calls (5)
  - `label.py`: batch label generation (5, max 10)
  - `dataforseo.py`: batch SERP requests (5)
  - `keywords_everywhere.py`: batch keyword data (5)
- Each service exposes `max_concurrent` parameter for configurability
- Label service adds validation: clamps to 1-10 range with logging

---

## 2026-02-01 - client-onboarding-v2-c3y.57
- What was implemented:
  - Created SERP result caching service (`app/services/serp_cache.py`)
  - Added `get_serp_cached()` method to DataForSEO client for cache-aware SERP lookups
  - 24-hour TTL for cached SERP results
  - Redis-based caching with graceful degradation when Redis is unavailable

- Files changed:
  - `backend/app/services/serp_cache.py` (new)
  - `backend/app/integrations/dataforseo.py` (modified)

- **Learnings:**
  - Pattern: Domain-specific caching services that wrap the core redis_manager
  - Cache key uses SHA256 hash of normalized keyword to handle long/special character keywords
  - Existing Redis infrastructure already has circuit breaker, SSL/TLS, and connection retry logic
  - Import cache services inside methods to avoid circular imports when cache depends on domain types
  - The mypy errors in core modules are pre-existing (config.py requires database_url, logging imports issue)
---

## 2026-02-01 - client-onboarding-v2-c3y.58
- What was implemented:
  - Created PAA enrichment service (`app/services/paa_enrichment.py`) with fan-out strategy
  - Created PAA cache service (`app/services/paa_cache.py`) with 24h TTL
  - Fan-out strategy: searches initial PAA questions for nested questions
  - Uses DataForSEO SERP Advanced endpoint with `people_also_ask_click_depth` parameter (1-4)
  - Supports rate-limited concurrent fan-out with configurable max_concurrent_fanout
  - De-duplicates questions using normalized question text
  - Comprehensive logging per error logging requirements

- Files changed:
  - `backend/app/services/paa_enrichment.py` (new)
  - `backend/app/services/paa_cache.py` (new)

- **Learnings:**
  - DataForSEO SERP Advanced endpoint (`/v3/serp/google/organic/live/advanced`) supports PAA click depth
  - `people_also_ask_click_depth` param (1-4) expands PAA questions, costs $0.00015 extra per click
  - PAA items in SERP response have type `people_also_ask` with nested `people_also_ask_element` items
  - Expanded elements can be `people_also_ask_expanded_element` (standard) or `people_also_ask_ai_overview_expanded_element` (AI-generated)
  - Fan-out strategy limits to first N questions to control API costs
  - Question deduplication uses normalized (lowercase, stripped, no trailing ?) comparison
---

## 2026-02-01 - client-onboarding-v2-c3y.59
- What was implemented:
  - Created Related Searches service (`app/services/related_searches.py`) with LLM semantic filter
  - Extracts `related_searches` items from DataForSEO SERP Advanced endpoint
  - Uses Claude LLM to evaluate semantic relevance of related searches (0.0-1.0 score)
  - LLM converts related searches to natural question format
  - Integrated as fallback in PAA enrichment when fewer than 3 PAA questions found
  - 24h TTL caching for related searches results
  - Comprehensive logging per error logging requirements

- Files changed:
  - `backend/app/services/related_searches.py` (new)
  - `backend/app/services/paa_enrichment.py` (modified - added fallback integration)

- **Learnings:**
  - Related searches in SERP have `type="related_searches"` with nested `items` array
  - Each item has a `title` field containing the search term
  - LLM semantic filter prompt should include: original keyword context, relevance score request, question conversion
  - Claude `complete()` method works well for structured JSON responses with `temperature=0.0`
  - Variable scoping in Python: must be careful when same variable name used in try/except blocks and conditional blocks (mypy catches this with `no-redef`)
  - Fallback triggers when `len(all_questions) < min_paa_for_fallback` (default 3)
  - Question conversion heuristic: detect existing question starters, else wrap with "What is/are"
---

## 2026-02-01 - client-onboarding-v2-c3y.60
- What was implemented:
  - Created PAA question categorization service (`app/services/paa_categorization.py`) with LLM-based intent classification
  - Categorizes PAA questions by user intent: buying, usage, care, comparison
  - Uses Claude LLM with structured JSON output for consistent categorization
  - Batch processing for efficient LLM usage (default 10 questions per batch)
  - Rate-limited concurrent processing (default max 5 concurrent batches)
  - Integrated as optional step in PAA enrichment (`categorize_enabled=True`)
  - Added `categorize_paa_questions()` convenience method for PAAQuestion objects

- Files changed:
  - `backend/app/services/paa_categorization.py` (new)
  - `backend/app/services/paa_enrichment.py` (modified - added `categorize_enabled` parameter)

- **Learnings:**
  - Intent categorization prompt should include: category definitions, confidence scoring guidelines, and explicit JSON format
  - Existing `PAAQuestionIntent` enum already defined in paa_enrichment.py with all required categories
  - Use dictionary lookup pattern instead of if-elif chains for enum parsing (ruff SIM116)
  - LLM question-intent lookup requires normalized matching (lowercase, stripped)
  - Graceful degradation: if LLM categorization fails, questions retain UNKNOWN intent without failing the whole enrichment
  - Batch processing reduces LLM calls: 100 questions = 10 LLM calls instead of 100
---

## 2026-02-01 - client-onboarding-v2-c3y.61
- What was implemented:
  - Verified parallel processing with rate limiting (max 5 concurrent) is already comprehensively implemented
  - Pattern is consistent across all services that need batch/parallel processing
  - Added "Parallel Processing with Rate Limiting Pattern" to Codebase Patterns section

- Files changed:
  - No code changes required - feature was already implemented in previous stories (c3y.58, c3y.59, c3y.60)
  - `.ralph-tui/progress.md` (updated - added pattern documentation)

- **Learnings:**
  - Parallel processing was already implemented as part of fan-out (c3y.58), related searches (c3y.59), and categorization (c3y.60)
  - The `asyncio.Semaphore` pattern is the idiomatic Python approach for rate-limited concurrency
  - Services that batch work include: paa_enrichment, paa_categorization, label, dataforseo, keywords_everywhere
  - All use consistent `max_concurrent: int = 5` default parameter
  - Label service additionally validates max_concurrent within 1-10 range with warning logs
  - Pre-existing mypy errors in core modules (config.py, logging.py, redis.py) are unrelated to this feature
---

## 2026-02-01 - client-onboarding-v2-c3y.62
- What was implemented:
  - Created PAA enrichment API endpoints (`/api/v1/projects/{id}/phases/paa_enrichment`)
  - Three endpoints:
    - `POST /enrich` - Enrich single keyword with PAA questions
    - `POST /batch` - Batch enrich multiple keywords concurrently
    - `GET /stats` - Get PAA enrichment statistics (placeholder until persistence added)
  - Created Pydantic schemas for request/response validation
  - Comprehensive error handling with structured error responses
  - Full logging per error logging requirements

- Files changed:
  - `backend/app/schemas/paa_enrichment.py` (new)
  - `backend/app/api/v1/endpoints/paa_enrichment.py` (new)
  - `backend/app/api/v1/__init__.py` (modified - registered PAA enrichment router)

- **Learnings:**
  - API endpoint pattern: use `_get_request_id()` helper and `_verify_project_exists()` for project validation
  - Convert service dataclasses to Pydantic response models before returning
  - Cache hit detection heuristic: check if `duration_ms < 100` for cached responses
  - Stats endpoint returns placeholder data - will need update when PAA results are persisted to database
  - Pre-existing issues: projects.py has 204 status code with response body error (FastAPI assertion)
  - Schema location: `app/schemas/` for Pydantic models, endpoints in `app/api/v1/endpoints/`
---

## 2026-02-01 - client-onboarding-v2-c3y.63
- What was implemented:
  - Created comprehensive unit tests for PAA enrichment fan-out logic (38 tests)
  - Created comprehensive unit tests for PAA categorization logic (32 tests)
  - Total: 70 new tests, all passing
  - Tests cover: dataclasses, validation, basic operations, fan-out strategy, related searches fallback, categorization integration, batch processing, error handling, and logging

- Files changed:
  - `backend/tests/services/test_paa_enrichment.py` (new - 38 tests)
  - `backend/tests/services/test_paa_categorization.py` (new - 32 tests)

- **Learnings:**
  - When mocking services imported inside method bodies, patch at the source module (e.g., `app.services.related_searches.get_related_searches_service`) not at the calling module
  - The `_normalize_question()` method uses `rstrip("?")` which removes ALL trailing question marks, not just one
  - Test pattern: Use AsyncMock for async methods, MagicMock for sync services/classes
  - For batching tests, counting calls is more reliable than parsing prompt content
  - Error propagation varies by implementation: some methods propagate errors to top-level result, others only mark success=False with errors in sub-results
  - Mypy in tests: Always check for `result.error is not None` before doing string operations on potentially None values
  - Pre-existing test failures in codebase (test_fixtures.py, test_url_categorizer.py) are unrelated to new code
  - Pre-existing mypy errors in core modules (config.py, logging.py, redis.py) are known issues
---

