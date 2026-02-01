# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Layer Pattern (Phase 5B/5C)
- Services live in `backend/app/services/`
- Use `@dataclass` for input/output data structures with `to_dict()` methods
- Singleton pattern via `_service: Service | None = None` and `get_service()` function
- Convenience functions wrap singleton for simple usage
- All async methods with `async def`
- Custom exceptions inherit from base `ServiceError` with `project_id`, `page_id` context

### Logging Requirements
- DEBUG: Method entry/exit with sanitized parameters
- INFO: State transitions (phase changes), operation completion
- WARNING: Validation failures, slow operations (>1s threshold)
- ERROR: Exceptions with full stack trace via `traceback.format_exc()`
- Always include: `project_id`, `page_id`, `duration_ms` in `extra={}` dict

### API Endpoint Pattern
- Endpoints in `backend/app/api/v1/endpoints/`
- Schemas in `backend/app/schemas/` (Pydantic BaseModel)
- Register in `backend/app/api/v1/__init__.py` with import + `router.include_router()`
- Return `Response | JSONResponse` union for error handling
- Use `_get_request_id(request)`, `_verify_project_exists()`, `_convert_*` helper functions
- Structured error responses: `{"error": str, "code": str, "request_id": str}`

---

## 2026-02-01 - client-onboarding-v2-c3y.80
- What was implemented: Phase 5C AI Trope Detection service
  - Detects banned words (17 words: delve, unlock, unleash, journey, game-changer, etc.)
  - Detects banned phrases (6 phrases: "In today's fast-paced world", etc.)
  - Detects em dashes (—) - strong AI indicator
  - Detects triplet patterns ("Fast. Simple. Powerful.")
  - Detects negation patterns ("aren't just X, they're Y")
  - Detects rhetorical questions as openers
  - Tracks limited-use words (max 1 per page: indeed, furthermore, robust, etc.)
  - Calculates quality score (0-100, pass threshold: 80)
  - Generates actionable improvement suggestions

- Files changed:
  - `backend/app/services/content_quality.py` (NEW - 762 lines)
  - `backend/app/schemas/content_quality.py` (NEW - 173 lines)
  - `backend/app/api/v1/endpoints/content_quality.py` (NEW - 299 lines)
  - `backend/app/api/v1/__init__.py` (MODIFIED - added content_quality router)

- **Learnings:**
  - Patterns discovered:
    - Pre-compile regex patterns in `__init__` for performance (stored as instance vars)
    - Skill Bible rules from Phase 5B system prompt define what to detect
    - Use `frozenset` for O(1) word lookups instead of lists
    - Quality scoring uses weighted deductions from base 100
  - Gotchas encountered:
    - Loop variable `word` unused in iteration → rename to `_word` for ruff compliance
    - Import sorting via ruff `--fix` auto-sorts Pydantic imports
    - Pre-existing mypy errors in other files (projects.py, documents.py) - ignore for new code
    - `documents.py` has invalid FastAPI return type annotation causing import chain error
---

