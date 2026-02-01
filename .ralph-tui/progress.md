# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### LLM-Based Classification Services
When building LLM-based classification services (like PAA categorization):
- Use batch processing with configurable batch size (default 10) and max concurrency (default 5)
- Use `asyncio.Semaphore` for rate limiting concurrent LLM calls
- Handle markdown code blocks in LLM responses (strip ``` wrappers)
- Match results back to original inputs case-insensitively (normalize with `.lower().strip()`)
- Return UNKNOWN for unmatched items rather than failing
- Use dataclasses for structured results (e.g., `CategorizationResult`, `CategorizationItem`)
- Track token usage across batches for cost monitoring
- Provide both `categorize_questions()` (strings) and `categorize_paa_questions()` (objects) methods

### Service Singleton Pattern
Services follow a consistent singleton pattern:
```python
_service_instance: ServiceClass | None = None

def get_service() -> ServiceClass:
    global _service_instance
    if _service_instance is None:
        _service_instance = ServiceClass()
        logger.info("ServiceClass singleton created")
    return _service_instance
```

### Error Logging Requirements
All services implement these logging patterns:
- DEBUG: Method entry/exit with parameters (sanitized), cache operations
- INFO: State transitions, operation completion, batch statistics
- WARNING: Slow operations (>1000ms), fallback triggers, validation failures
- ERROR: Exceptions with full stack trace, API failures
- Always include `project_id` and `page_id` in log extra for traceability

---

## 2026-02-01 - client-onboarding-v2-c3y.60
- What was implemented: PAA question categorization by intent (buying, usage, care, comparison)
- Files already exist (implementation was complete):
  - `backend/app/services/paa_enrichment.py` - Contains `PAAQuestionIntent` enum and integration
  - `backend/app/services/paa_categorization.py` - Full categorization service with LLM
  - `backend/tests/services/test_paa_categorization.py` - 32 unit tests (all passing)
- **Learnings:**
  - The feature was already fully implemented in a previous iteration
  - `PAAQuestionIntent` enum defined in paa_enrichment.py with values: BUYING, USAGE, CARE, COMPARISON, UNKNOWN
  - Categorization uses Claude LLM with temperature=0.0 for deterministic results
  - Integration point: `enrich_keyword()` accepts `categorize_enabled=True` to auto-categorize
  - Confidence scores: 0.8-1.0 (clear), 0.6-0.8 (likely), 0.4-0.6 (unclear)
---

