# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Integration Client Pattern
New integrations in `backend/app/integrations/` should follow these patterns:
- Use dataclasses for result types (e.g., `AmazonStoreDetectionResult`)
- Global singleton pattern with `init_*`, `get_*`, and `close_*` functions
- If relying on another integration (like Perplexity), delegate to it rather than implementing circuit breakers directly
- Log method entry/exit at DEBUG level
- Log slow operations (>1s) at INFO level
- Include `project_id` in all log extras for traceability

### Service Layer Pattern
Services in `backend/app/services/` should:
- Create custom exception classes (e.g., `ValidationError`, `LookupError`)
- Include `field_name`, `value`, `message` in validation errors
- Accept optional `project_id` parameter for logging context
- Call integration's `get_*` function to get singleton client
- Validate inputs before calling integration

### API Endpoint Pattern
Endpoints in `backend/app/api/v1/endpoints/` should:
- Use `_get_request_id(request)` helper to extract request ID
- Call `_verify_project_exists()` early to return 404 if needed
- Log requests at INFO level with request_id, project_id
- Return `JSONResponse` with `{"error", "code", "request_id"}` for errors
- Use `contextlib.suppress()` instead of try/except/pass (ruff SIM105)

---

## 2026-02-01 - client-onboarding-v2-c3y.65
- What was implemented: Amazon store auto-detection and review fetching using Perplexity AI
- Files changed:
  - `backend/app/integrations/amazon_reviews.py` - New integration client that uses Perplexity to search Amazon and analyze reviews
  - `backend/app/services/amazon_reviews.py` - Service layer with validation and error handling
  - `backend/app/schemas/amazon_reviews.py` - Pydantic request/response schemas
  - `backend/app/api/v1/endpoints/amazon_reviews.py` - API endpoints for detect and analyze operations
  - `backend/app/api/v1/__init__.py` - Registered new routes at `/projects/{project_id}/phases/amazon_reviews`
- **Learnings:**
  - Perplexity API can be used to avoid direct Amazon scraping while still getting product and review data
  - The existing Perplexity integration has robust circuit breaker and retry logic - new integrations can delegate to it
  - Ruff enforces `contextlib.suppress()` over try/except/pass (rule SIM105)
  - Type annotations need `dict[str, Any]` not just `dict` for mypy strict mode
---

