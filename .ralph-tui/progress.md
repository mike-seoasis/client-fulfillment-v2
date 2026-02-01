# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Pattern (Phase 5C Services)
All Phase 5C services follow this structure:
1. **Dataclasses** for input/output (not Pydantic in service layer)
2. **Singleton getter** function `get_*_service()`
3. **Service class** with async methods
4. **Convenience functions** that wrap service calls
5. **Custom exceptions** with project_id/page_id context

### Logging Pattern
- DEBUG: method entry/exit, detection details
- INFO: phase transitions (in_progress → completed), service creation
- WARNING: validation failures, slow operations (>1s)
- ERROR: unexpected exceptions with stack_trace

All logs include: `project_id`, `page_id`, `content_id`, `duration_ms`

### API Endpoint Pattern
1. Router defined with `APIRouter()`
2. `_get_request_id()` helper for tracing
3. `_verify_project_exists()` returns JSONResponse|None
4. `_convert_*` functions for schema↔service conversion
5. Structured error responses: `{error, code, request_id}`

### Router Registration
In `app/api/v1/__init__.py`:
- Import module from endpoints
- Call `router.include_router(module.router, prefix=..., tags=[...])`

---

## 2026-02-01 - client-onboarding-v2-c3y.83
- **What was implemented:** Phase 5C LLM QA Fix service for minimal content corrections using Claude
- **Files changed:**
  - `backend/app/schemas/llm_qa_fix.py` (new) - Pydantic schemas for LLM QA Fix API
  - `backend/app/services/llm_qa_fix.py` (new) - Service that uses Claude to fix AI tropes
  - `backend/app/api/v1/endpoints/llm_qa_fix.py` (new) - API endpoints for fix and batch operations
  - `backend/app/api/v1/__init__.py` (modified) - Registered new router
- **Learnings:**
  - isort requires alias imports (`X as Y`) to be in separate import statements
  - mypy needs explicit type annotation when using `json.loads()` to avoid `no-any-return`
  - `asyncio.gather(return_exceptions=True)` returns `list[T | BaseException]` - need `isinstance` checks for both branches
  - ClaudeClient has `complete()` method for generic LLM calls (not just categorization)
---

