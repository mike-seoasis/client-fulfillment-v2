# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Phase Endpoint Pattern
All phase endpoints follow a consistent 3-file structure:
1. **Schema file** (`app/schemas/{phase_name}.py`): Pydantic models for Request/Response
2. **Service file** (`app/services/{phase_name}.py`): Business logic with dataclasses, singleton pattern
3. **Endpoint file** (`app/api/v1/endpoints/{phase_name}.py`): FastAPI router with logging and error handling

Key service patterns:
- `get_{service_name}_service()` singleton factory
- `{Service}Input` dataclass for service input
- `{Service}Result` dataclass for service output
- `{Service}ValidationError` exception class
- Async `generate_*()` methods with timing and logging

Key endpoint patterns:
- `_get_request_id(request)` helper to extract request_id from state
- `_verify_project_exists()` helper for 404 handling
- `_convert_request_to_input()` and `_convert_result_to_response()` converters
- Structured JSON error responses: `{"error": str, "code": str, "request_id": str}`
- Log 4xx at WARNING, 5xx at ERROR with exc_info=True

### Router Registration
In `app/api/v1/__init__.py`:
- Import the endpoint module in the import block (alphabetical order)
- Add `router.include_router()` call with prefix and tags

---

## 2026-02-01 - client-onboarding-v2-c3y.85
- Implemented content_generation phase endpoints
- Files changed:
  - Created `app/schemas/content_generation.py` (request/response models)
  - Created `app/services/content_generation.py` (service with LLM integration)
  - Created `app/api/v1/endpoints/content_generation.py` (FastAPI router)
  - Modified `app/api/v1/__init__.py` (router registration)
- **Learnings:**
  - Codebase uses `get_claude()` async factory from `app.integrations.claude`
  - Claude returns `CompletionResult` with `success`, `text`, `input_tokens`, `output_tokens`, `request_id`
  - All phases support both single item (`/generate` or `/build`) and batch (`/batch`) endpoints
  - Ruff linting prefers simplified if statements over nested walrus operators
  - Pre-existing typecheck/lint errors in other files (documents.py) shouldn't block new feature development
---

