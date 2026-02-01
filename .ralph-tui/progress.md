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

