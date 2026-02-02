# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### FastAPI Endpoint Type Annotations
- When using `Response | JSONResponse` return types for endpoints with status_code=204, add `response_model=None` to the decorator
- Use old-style default value parameters (`param: str = Path(...)`) instead of `Annotated[str, Path(...)]` for better compatibility with different FastAPI versions

### Test Structure
- API integration tests belong in `tests/api/` directory
- Use the existing `client` fixture from `conftest.py` for synchronous API tests
- Use `async_client` fixture for async tests
- Set `DATABASE_URL` environment variable when running tests: `DATABASE_URL="postgresql://test:test@localhost:5432/test" pytest tests/api/`

### Error Response Format
All API error responses follow this structure:
```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "request_id": "uuid-from-request"
}
```

---

## 2026-02-01 - client-onboarding-v2-c3y.140
- What was implemented:
  - Created API integration tests for health endpoints (`tests/api/test_health_endpoints.py`)
  - Created API integration tests for projects CRUD endpoints (`tests/api/test_projects_endpoints.py`)
  - Created API integration tests for error handling and CORS (`tests/api/test_error_handling.py`)
  - Fixed FastAPI type annotation issues in `app/api/v1/endpoints/notifications.py`
  - Fixed FastAPI response_model issues in `app/api/v1/endpoints/documents.py` and `projects.py`

- Files changed:
  - `backend/tests/api/__init__.py` (new)
  - `backend/tests/api/test_health_endpoints.py` (new)
  - `backend/tests/api/test_projects_endpoints.py` (new)
  - `backend/tests/api/test_error_handling.py` (new)
  - `backend/app/api/v1/endpoints/notifications.py` (fixed Annotated type issues)
  - `backend/app/api/v1/endpoints/documents.py` (added response_model=None)
  - `backend/app/api/v1/endpoints/projects.py` (added response_model=None for delete)
  - `backend/tests/conftest.py` (minor cleanup)

- **Learnings:**
  - FastAPI 0.104.1 with starlette 0.27.0 has compatibility issues with httpx 0.28.1 - the TestClient breaks
  - Use `response_model=None` for endpoints that return `Response | JSONResponse` union types
  - Use `response_model=None` for endpoints with `status_code=204` (No Content)
  - `Annotated[str, Path(...)]` syntax can cause issues with certain FastAPI versions - use `param: str = Path(...)` instead
  - Health endpoints are defined in `main.py`, not in the `api/v1/endpoints/` directory
  - All responses include `X-Request-ID` header from the `RequestLoggingMiddleware`
---

