# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Empty string env vars**: Pydantic validates empty string `""` as URL input, not `None`. Comment out unused URL env vars (e.g., `# REDIS_URL=`) instead of leaving empty.
- **Health endpoints**: Defined in `main.py` directly, not in routers. Routes: `/health`, `/health/db`, `/health/redis`, `/health/scheduler`
- **CircuitBreaker**: Use shared `app.core.circuit_breaker` module. Pass `name` parameter for logging context. Config via `CircuitBreakerConfig(failure_threshold, recovery_timeout)`.

---

## 2026-02-02 - P0-001
- What was implemented: Set up v2-rebuild branch with origin tracking
- Files changed: None (git operation only)
- **Learnings:**
  - Branch v2-rebuild already existed locally from previous work
  - Pushed to origin and set upstream tracking with `git push -u origin v2-rebuild`
  - Use `git branch -vv` to verify upstream tracking status
---

## 2026-02-02 - P0-002
- What was implemented: Deleted tangled backend code to enable fresh rebuild
- Files changed:
  - Deleted `backend/app/services/` (40+ files - crawl, content, keyword, etc.)
  - Deleted `backend/app/api/v1/endpoints/` (30+ files - all API endpoints)
  - Deleted `backend/app/repositories/` (7 files - data layer)
  - Deleted `backend/app/utils/` (8 files - URL, queue, parsing utils)
  - Deleted `backend/app/clients/` (2 files - websocket client)
  - Modified `backend/app/main.py` - removed crawl_recovery import and api router
  - Modified `backend/app/api/v1/__init__.py` - cleared all endpoint imports
  - Modified `backend/.env` - commented out empty REDIS_URL
- **Learnings:**
  - Health endpoints are defined directly in main.py, not in separate routers
  - The lifespan function in main.py had crawl recovery logic that needed removal
  - Empty string env vars (`REDIS_URL=`) cause Pydantic URL validation errors; comment them out instead
  - FastAPI TestClient is useful for quick endpoint verification without starting server
---

## 2026-02-02 - P0-003
- What was implemented: Cleaned up tests referencing deleted code
- Files changed:
  - Deleted `backend/tests/services/` (28 test files - tests for deleted services)
  - Deleted `backend/tests/api/` (3 test files - tests for deleted API endpoints)
  - Deleted `backend/tests/clients/` (1 test file - tests for deleted websocket client)
  - Deleted `backend/tests/utils/` (5 test files - tests for deleted utils)
- **Remaining test directories:**
  - `tests/core/` - data integrity tests (kept)
  - `tests/integrations/` - third-party integration tests (kept)
  - `tests/e2e/` - end-to-end tests (kept, may need review later)
  - `tests/migrations/` - migration tests (kept)
  - `tests/test_fixtures.py` - fixture validation tests (kept)
  - `tests/conftest.py` - shared fixtures (kept)
- **Learnings:**
  - Tests live in `backend/tests/`, not project root `tests/`
  - The acceptance criteria mentioned `tests/models/` but this directory doesn't exist; core tests serve this purpose
  - `conftest.py` only imports from `app.core` which was preserved, so no changes needed
  - 37 tests now pass cleanly: `python3 -m pytest tests/core/ tests/test_fixtures.py`
---

## 2026-02-02 - P0-004
- What was implemented: Created shared CircuitBreaker module to DRY up circuit breaker code
- Files changed:
  - Created `backend/app/core/circuit_breaker.py`
- **Learnings:**
  - Multiple loggers in `logging.py` have duplicate circuit breaker logging methods (RedisLogger, Crawl4AILogger, ClaudeLogger, etc.)
  - The shared module uses generic logging with `circuit_name` in `extra` dict for context
  - Reference implementation was in `redis.py` lines 38-158
  - Module exports: `CircuitState` (enum), `CircuitBreakerConfig` (dataclass), `CircuitBreaker` (class)
---

## 2026-02-02 - P0-005
- What was implemented: Refactored redis.py to use shared CircuitBreaker module
- Files changed:
  - Modified `backend/app/core/redis.py` - removed local CircuitState, CircuitBreakerConfig, CircuitBreaker definitions; now imports from shared module
- **Learnings:**
  - The local CircuitBreaker used `redis_logger` for logging; the shared module uses generic logging with `circuit_name` in extra dict
  - CircuitState was imported but not actually used in redis.py (only used internally by CircuitBreaker), so import was removed
  - Pre-existing `use_ssl` variable is defined but unused (not part of this refactor)
---

## 2026-02-02 - P0-006
- What was implemented: Refactored all 9 integration clients to use shared CircuitBreaker module
- Files changed:
  - Modified `backend/app/integrations/dataforseo.py` - uses shared CircuitBreaker with name='dataforseo'
  - Modified `backend/app/integrations/pop.py` - uses shared CircuitBreaker with name='pop'
  - Modified `backend/app/integrations/claude.py` - uses shared CircuitBreaker with name='claude'
  - Modified `backend/app/integrations/perplexity.py` - uses shared CircuitBreaker with name='perplexity'
  - Modified `backend/app/integrations/google_nlp.py` - uses shared CircuitBreaker with name='google_nlp'
  - Modified `backend/app/integrations/keywords_everywhere.py` - uses shared CircuitBreaker with name='keywords_everywhere'
  - Modified `backend/app/integrations/crawl4ai.py` - uses shared CircuitBreaker with name='crawl4ai'
  - Modified `backend/app/integrations/email.py` - uses shared CircuitBreaker with name='email'
  - Modified `backend/app/integrations/webhook.py` - uses shared CircuitBreaker with name='webhook'
- **Learnings:**
  - Each integration had its own local CircuitState, CircuitBreakerConfig, and CircuitBreaker class definitions (~100+ lines each)
  - Some integrations used specialized loggers (e.g., dataforseo_logger, claude_logger) while others used the generic logger for circuit breaker events
  - The shared module uses generic logging with `circuit_name` in the `extra` dict, which is simpler and consistent
  - No CircuitState import needed since it's only used internally by CircuitBreaker
  - Removed ~900 lines of duplicate code across the 9 integration files
---

