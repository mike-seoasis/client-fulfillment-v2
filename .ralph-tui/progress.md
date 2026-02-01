# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Structure Pattern
Services follow a consistent structure:
1. Module docstring with ERROR LOGGING REQUIREMENTS
2. Constants and configuration at top (e.g., `SLOW_OPERATION_THRESHOLD_MS = 1000`)
3. Exception classes inheriting from base service error
4. Dataclasses for input/output with `to_dict()` methods for serialization
5. Main service class with private helper methods (`_compute_*`, `_detect_*`)
6. Singleton pattern with `_service: Service | None = None` and `get_service()` getter
7. Convenience functions that use the singleton

### Logging Pattern
- DEBUG: Method entry with parameters (sanitized), internal operations
- INFO: Phase transitions with `phase`, `status`, `duration_ms`
- WARNING: Validation failures with `field`, `rejected_value`; slow operations with threshold
- ERROR: Full stack trace with `exc_info=True`, include `error_type`, `error_message`

### Test Structure Pattern
- Fixtures at top: service instance, sample data
- Test classes grouped by functionality (TestDataClasses, TestValidation, TestMainLogic)
- Use `@pytest.mark.asyncio` for async tests
- 80% coverage target

---

## 2026-02-01 - client-onboarding-v2-c3y.91
- What was implemented: ContentScoreService with 5 scoring components (word count, semantic, readability, keyword density, entity coverage)
- Files changed:
  - `backend/app/services/content_score.py` (new - 850+ lines)
  - `backend/tests/services/test_content_score.py` (new - 62 tests, all passing)
- **Learnings:**
  - Patterns discovered: Pure Python implementations preferred over external ML libs (no scikit-learn). Follow existing TF-IDF and content_quality patterns for consistency.
  - Gotchas encountered: Pre-existing mypy errors in logging.py and redis.py - ignore those when checking new code. Use `python3` not `python` for commands in this environment.
---

