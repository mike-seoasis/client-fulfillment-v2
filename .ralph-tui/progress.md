# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Type Checking Configuration
- **Backend (mypy)**: Config in `backend/pyproject.toml` under `[tool.mypy]`. Third-party libs without stubs are handled via `[[tool.mypy.overrides]]` with `ignore_missing_imports = true`.
- **Frontend (tsc)**: Config in `frontend/tsconfig.json`. Run with `npm run typecheck`.
- When adding new third-party dependencies without type stubs, add them to the mypy overrides module list in `pyproject.toml`.

---

## 2026-02-01 - client-onboarding-v2-c3y.142
- Ran mypy type checking on backend (134 source files) and tsc on frontend
- Fixed 8 type errors across 4 backend files
- Files changed:
  - `backend/pyproject.toml` - Added `boto3` and `boto3.*` to mypy ignore_missing_imports list
  - `backend/app/core/logging.py` - Added `type: ignore[name-defined]` for JsonFormatter base class
  - `backend/app/core/redis.py` - Added `type: ignore[misc]` for async ping() call
  - `backend/app/api/v1/endpoints/projects.py` - Fixed return type for `create_project` (was missing `JSONResponse`), removed 4 unused `type: ignore[return-value]` comments
- **Learnings:**
  - Local imports (inside functions) are still affected by mypy module overrides in pyproject.toml
  - FastAPI endpoints that return either a response model or JSONResponse need union return types (`ProjectResponse | JSONResponse`)
  - The `warn_unused_ignores = true` mypy setting catches stale type: ignore comments
  - Redis async client's `ping()` returns `Awaitable[bool] | bool` which requires type: ignore for await
---

