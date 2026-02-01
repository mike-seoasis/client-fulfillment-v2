# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Pattern
Services follow a consistent structure:
1. **Dataclasses**: Request/Result dataclasses with `to_dict()` methods
2. **Exception hierarchy**: Base `ServiceError` with specific subclasses like `ValidationError`
3. **Singleton pattern**: `_service: Service | None = None` with `get_service()` accessor
4. **Convenience functions**: Module-level async functions that use the singleton
5. **Comprehensive logging**: DEBUG for entry/exit, INFO for state transitions, WARNING for slow ops

### Error Logging Requirements
All services must implement:
- Log method entry/exit at DEBUG level with sanitized parameters
- Log all exceptions with full stack trace (`exc_info=True`)
- Include entity IDs (project_id, page_id) in all logs via `extra={}` dict
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Log slow operations (>1000ms) at WARNING level with `SLOW_OPERATION_THRESHOLD_MS`

### Test Pattern
Tests organized by class with:
- Fixtures for service instances and sample data
- Dataclass tests, initialization tests, method tests
- Validation/error handling tests
- Edge case tests
- Constants verification tests
- Singleton and convenience function tests

---

## 2026-02-01 - client-onboarding-v2-c3y.90
- What was implemented: TF-IDF analysis service for term extraction
- Files changed:
  - `backend/app/services/tfidf_analysis.py` (new - 920 lines)
  - `backend/tests/services/test_tfidf_analysis.py` (new - 62 tests)
- **Learnings:**
  - Pure Python TF-IDF implementation avoids scikit-learn dependency
  - Single document TF-IDF edge case: all terms in 100% of docs, filtered by max_df_ratio - use max_df_ratio=1.0 for single doc
  - Dict comprehensions `{k: 0 for k in iterable}` trigger C420 lint warning; use `# noqa: C420` to suppress when appropriate
  - Existing mypy errors in `app/core/logging.py` and `app/core/redis.py` - pre-existing issues, not related to new code
---

