# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Empty string env vars**: Pydantic validates empty string `""` as URL input, not `None`. Comment out unused URL env vars (e.g., `# REDIS_URL=`) instead of leaving empty.
- **Health endpoints**: Defined in `main.py` directly, not in routers. Routes: `/health`, `/health/db`, `/health/redis`, `/health/scheduler`

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

