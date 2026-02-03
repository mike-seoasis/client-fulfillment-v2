# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Empty string env vars**: Pydantic validates empty string `""` as URL input, not `None`. Comment out unused URL env vars (e.g., `# REDIS_URL=`) instead of leaving empty.
- **Health endpoints**: Defined in `main.py` directly, not in routers. Routes: `/health`, `/health/db`, `/health/redis`, `/health/scheduler`
- **CircuitBreaker**: Use shared `app.core.circuit_breaker` module. Pass `name` parameter for logging context. Config via `CircuitBreakerConfig(failure_threshold, recovery_timeout)`.
- **uv package manager**: uv installed at `~/.local/bin/uv`. Run `uv lock` in backend/ to regenerate lockfile. Use `uv run pytest` or `uv run python` to execute commands with dependencies.
- **uv in Docker**: Use `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv` to get uv binary. Install deps with `uv sync --frozen --no-dev --no-install-project`.

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

## 2026-02-02 - P0-007
- What was implemented: Created comprehensive unit tests for the shared CircuitBreaker module
- Files changed:
  - Created `backend/tests/core/test_circuit_breaker.py` (20 tests)
- **Learnings:**
  - Mock `time.monotonic` for timeout tests rather than using actual delays
  - Can directly set internal state (`cb._state`, `cb._last_failure_time`) for testing specific transitions
  - pytest-asyncio with `mode=Mode.AUTO` means no need for `@pytest.mark.asyncio` decorator (but added for explicitness)
  - Use `unittest.mock.patch` for mocking `time.monotonic` and logger in async tests
---

## 2026-02-02 - P0-008
- What was implemented: Migrated to uv package manager
- Files changed:
  - Modified `backend/pyproject.toml` - added `[tool.setuptools.packages.find]` to include only `app*` packages
  - Created `backend/uv.lock` - lockfile generated by `uv lock`
- **Learnings:**
  - uv installs to `~/.local/bin/` by default; add to PATH with `export PATH="$HOME/.local/bin:$PATH"`
  - setuptools flat-layout with multiple top-level directories (app, alembic, uploads) causes build failure
  - Fix: add `[tool.setuptools.packages.find]` with `include = ["app*"]` to pyproject.toml
  - uv automatically creates a virtual environment and installs dependencies on first `uv run` command
  - 45 tests pass via `uv run pytest tests/core/`
---

## 2026-02-02 - P0-009
- What was implemented: Created Backend Dockerfile for Railway deployment
- Files changed:
  - Created `backend/Dockerfile` - multi-stage build with uv for dependencies
- **Learnings:**
  - Use `COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv` to get uv in Docker without installing from scratch
  - `uv sync --frozen --no-dev --no-install-project` installs only production dependencies using lockfile
  - Dockerfile `EXPOSE` directive doesn't support variable substitution; use fixed port value as documentation
  - CMD in shell form (`CMD command $VAR`) expands environment variables at runtime
  - Non-root user pattern: `useradd --create-home --shell /bin/bash appuser` then `USER appuser`
  - Virtual environment path from uv: `/app/.venv` - add to PATH with `ENV PATH="/app/.venv/bin:$PATH"`
---

## 2026-02-02 - P0-010
- What was implemented: Deleted existing Vite frontend and created fresh Next.js 14 project
- Files changed:
  - Deleted `frontend/` (Vite-based React app)
  - Created `frontend/` (Next.js 14 project with App Router)
- **Learnings:**
  - Use `npx create-next-app@14` to pin to Next.js 14 (latest is 15.x)
  - Flags `--typescript --tailwind --eslint --app --src-dir --use-npm --no-import-alias` configure all options non-interactively
  - Next.js 14 creates `src/app/` directory for App Router by default with `--app` flag
  - TypeScript strict mode is enabled by default in Next.js 14's tsconfig.json
  - The `@/*` path alias is configured by default (maps to `./src/*`)
---

## 2026-02-02 - P0-011
- What was implemented: Configured Next.js frontend dependencies and testing tools
- Files changed:
  - Modified `frontend/package.json` - added dependencies and test scripts
  - Created `frontend/vitest.config.ts` - Vitest configuration with React plugin and jsdom
  - Created `frontend/playwright.config.ts` - Playwright E2E configuration
  - Created `frontend/src/test/setup.ts` - Test setup with jest-dom matchers
  - Created `frontend/e2e/` - Directory for Playwright E2E tests
- **Dependencies installed:**
  - Production: @tanstack/react-query@5, zustand, axios
  - Dev: vitest, @vitejs/plugin-react, @playwright/test, jsdom, @testing-library/jest-dom, @testing-library/react
- **Learnings:**
  - Vitest for Next.js: Use jsdom environment and @vitejs/plugin-react for JSX support
  - The vitest.config.ts needs path alias matching tsconfig.json's `@/*` mapping
  - Added @testing-library/jest-dom and @testing-library/react for React component testing
  - Playwright webServer config can auto-start Next.js dev server during E2E tests
  - npm audit shows vulnerabilities in Next.js dependency tree (common, not blocking)
---

## 2026-02-02 - P0-012
- What was implemented: Configured Tailwind with warm color palette
- Files changed:
  - Modified `frontend/tailwind.config.ts` - added custom warm color palette and softer border-radius
- **Color palette added:**
  - `gold` (50-900): Warm golden tones for accents and CTAs
  - `cream` (50-900): Soft neutral backgrounds
  - `coral` (50-900): Warm accent for highlights and alerts
  - `warm-gray` (50-900): Neutral text and borders with warm undertones
- **Border-radius increased:** sm=0.25rem, DEFAULT=0.375rem, md=0.5rem, lg=0.75rem, xl=1rem, 2xl=1.25rem, 3xl=1.75rem
- **Content paths:** Simplified to `./src/app/**/*` and `./src/components/**/*` (removed `./src/pages/**/*` since using App Router)
- **Learnings:**
  - Tailwind color scales follow 50-900 pattern for flexibility in light/dark variations
  - `warm-gray` uses hyphenated name since Tailwind supports kebab-case for custom colors
  - Border-radius extend values override defaults for more pronounced softness
---

