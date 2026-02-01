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

### Fallback Persona Generation Pattern
When no reviews are available, generate personas from website analysis:
- Add `needs_review` and `fallback_used` flags to result dataclasses
- Use Perplexity to analyze brand website/positioning for persona inference
- Limit generated personas to 3 maximum
- Flag results with `needs_review=True` when fallback is used (for user validation)
- Make fallback opt-in via `use_fallback` parameter (default True)
- Gracefully handle fallback failures (return empty personas, don't fail the overall operation)

---

## 2026-02-01 - client-onboarding-v2-c3y.69
- What was implemented: Fallback persona generation when no reviews available
- Files changed:
  - `backend/app/integrations/amazon_reviews.py` - Added `FallbackPersona` dataclass, `FALLBACK_PERSONA_PROMPT`, `generate_fallback_personas()` method, updated `analyze_brand_reviews()` to use fallback
  - `backend/app/services/amazon_reviews.py` - Added `needs_review`, `fallback_used`, `fallback_source` fields to `ReviewAnalysisResult`, updated `analyze_reviews()` method signature
  - `backend/app/schemas/amazon_reviews.py` - Updated `CustomerPersonaResponse`, `AmazonReviewAnalysisRequest`, `AmazonReviewAnalysisResponse` with new fields
  - `backend/tests/integrations/test_amazon_reviews_fallback.py` - 20 comprehensive tests (all passing)
- **Learnings:**
  - Per brand-config spec: when no reviews available, generate fallback persona from website analysis and flag as "needs_review"
  - FallbackPersona includes: name, description, source ("website_analysis"), inferred (True), characteristics (list)
  - Perplexity temperature 0.3 for slightly creative but grounded persona generation
  - Fallback personas are converted to dict format matching existing persona structure for API consistency
  - Test integration directory needed `__init__.py` file creation
  - The `_parse_json_from_response()` helper handles markdown code block wrapping in LLM responses
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

