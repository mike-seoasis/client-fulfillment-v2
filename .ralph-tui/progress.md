# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Phase Endpoint Pattern
New phases follow this structure:
1. **Model** (`app/models/<name>.py`) - SQLAlchemy model with UUID primary key, project_id FK, JSONB for flexible data, timestamps
2. **Migration** (`alembic/versions/00XX_<name>.py`) - Create table with indexes, FK constraints
3. **Repository** (`app/repositories/<name>.py`) - CRUD operations with comprehensive logging, timing, error handling
4. **Service** (`app/services/<name>.py`) - Business logic, validation, integration orchestration
5. **Schemas** (`app/schemas/<name>.py`) - Pydantic models for API requests/responses
6. **Endpoints** (`app/api/v1/endpoints/<name>.py`) - FastAPI router with structured error responses

### Error Response Format
All endpoints return structured errors:
```python
{
    "error": str,      # Human-readable message
    "code": str,       # Error code (NOT_FOUND, VALIDATION_ERROR, etc.)
    "request_id": str  # UUID from request state for tracing
}
```

### Delete Endpoint Pattern
For 204 NO_CONTENT responses:
```python
@router.delete("/{id}", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
async def delete_thing(...) -> Response | JSONResponse:
    # ... on success:
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

### Integration Pattern (Crawl4AI)
Use `get_crawl4ai()` dependency to get the global client. Check `.available` before use.

---

## 2026-02-01 - client-onboarding-v2-c3y.89
- **What was implemented**: Competitor content fetching and scraping feature
- **Files changed**:
  - `backend/app/models/competitor.py` - Competitor model with JSONB content storage
  - `backend/app/models/__init__.py` - Added Competitor export
  - `backend/alembic/versions/0011_create_competitors_table.py` - Migration with unique constraint on (project_id, url)
  - `backend/app/repositories/competitor.py` - CompetitorRepository with full CRUD, status updates, content updates
  - `backend/app/repositories/__init__.py` - Added CompetitorRepository export
  - `backend/app/services/competitor.py` - CompetitorService with URL validation, scraping orchestration
  - `backend/app/schemas/competitor.py` - Request/response schemas with nested content model
  - `backend/app/api/v1/endpoints/competitor.py` - Full REST API (add, list, get, scrape, progress, delete)
  - `backend/app/api/v1/__init__.py` - Registered competitor router at /phases/competitor

- **Learnings:**
  - FastAPI delete endpoints with 204 status require `response_model=None` and must return `Response(status_code=...)` not `None`
  - Background tasks in FastAPI use `BackgroundTasks` and `background_tasks.add_task()`
  - Repository pattern includes timing logs for slow operations (>1s threshold)
  - Status transitions logged at INFO level, all other DB ops at DEBUG
  - URL deduplication via composite unique index on (project_id, url)
  - Crawl4AI integration returns markdown content, links, and metadata from scraped pages

---

