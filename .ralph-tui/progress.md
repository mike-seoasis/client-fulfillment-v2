# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Parallel Processing with Rate Limiting
Use `asyncio.Semaphore` with `asyncio.gather()` for concurrent operations with rate limiting:
```python
semaphore = asyncio.Semaphore(max_concurrent)

async def process_with_semaphore(item):
    async with semaphore:
        return await do_work(item)

tasks = [process_with_semaphore(item) for item in items]
results = await asyncio.gather(*tasks)
```
- For indexed results, return `(index, result)` tuples and sort after gather
- Always wrap inner function in try/except to handle individual failures
- Log entry/exit at DEBUG level, state transitions at INFO level

### Error Logging Pattern
- Entry/exit: DEBUG level with sanitized parameters (truncate URLs to 200 chars)
- Exceptions: ERROR with `exc_info=True` for full stack trace
- State transitions: INFO level (status changes, phase changes)
- Slow operations (>1s): WARNING level with duration_ms
- Include entity IDs (project_id, page_id, crawl_id) in all logs

### FastAPI DELETE Endpoint Pattern
For DELETE endpoints that return 204 on success but need error responses (404, 400):
```python
@router.delete(
    "/{item_id}",
    response_model=None,  # Required to disable automatic response model
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Item deleted successfully"},
        404: {"description": "Item not found", ...},
    },
)
async def delete_item(...) -> Response | JSONResponse:
    try:
        await service.delete_item(item_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except NotFoundError as e:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={...})
```
- Must use `response_model=None` to disable response model validation
- Return `Response(status_code=204)` for success (not `None`)
- Can still return `JSONResponse` for error cases

---

## 2026-02-01 - client-onboarding-v2-c3y.61
- What was implemented: Parallel processing with rate limiting (max 5 concurrent) for CrawlService
- Files changed:
  - `backend/app/services/crawl.py` - Added parallel processing to `run_crawl()` and `fetch_urls()` methods
- **Learnings:**
  - Existing semaphore patterns in `paa_categorization.py` and `label.py` serve as good templates
  - For crawling with URL discovery, batch processing works well: collect batch -> process in parallel -> merge discovered URLs -> repeat
  - Import `QueuedURL` type from crawl_queue for proper type annotations
  - Use `MAX_CONCURRENT_CRAWLS = 5` constant for consistency
  - Inner async functions with semaphore need proper exception handling to return error results instead of raising
---

## 2026-02-01 - client-onboarding-v2-c3y.70
- What was implemented: Brand config endpoints at `/api/v1/projects/{id}/phases/brand_config`
- Files changed:
  - `backend/app/api/v1/__init__.py` - Updated router prefix from `/brand-config` to `/phases/brand_config` to match phase endpoint convention
  - `backend/app/api/v1/endpoints/brand_config.py` - Updated docstring paths and fixed DELETE endpoint to use FastAPI-compliant pattern
- **Learnings:**
  - FastAPI 0.104+ enforces strict 204 No Content rules - cannot use `status_code=204` with union return types
  - For DELETE endpoints, must use `response_model=None` and return `Response(status_code=204)` instead of `None`
  - Phase endpoints follow pattern: `/projects/{project_id}/phases/{phase_name}`
  - Brand config endpoints provide: synthesize (POST), list (GET), get (GET), update (PUT), delete (DELETE)
---

## 2026-02-01 - client-onboarding-v2-c3y.103
- What was implemented: Schedule endpoints at `/api/v1/projects/{id}/phases/schedule` were already mostly complete; fixed DELETE endpoint to use FastAPI-compliant pattern
- Files changed:
  - `backend/app/api/v1/endpoints/schedule.py` - Fixed DELETE endpoint to use `response_model=None`, import `Response`, and return `Response(status_code=204)` instead of `None`
- **Learnings:**
  - Schedule endpoints already existed with full CRUD operations (create, list, get, update, delete)
  - Router was already properly registered in `backend/app/api/v1/__init__.py` at prefix `/projects/{project_id}/phases/schedule`
  - Endpoints already met error logging requirements with proper structured error responses including `request_id`
  - The DELETE endpoint pattern discovered in c3y.70 needs to be applied consistently across all endpoints
---

