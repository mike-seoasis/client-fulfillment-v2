# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Testing Patterns
- **Test file structure**: Tests organized by service/util in `tests/services/` and `tests/utils/`
- **Fixture pattern**: Per-class fixtures with `@pytest.fixture`, mock external clients with `AsyncMock`
- **Async testing**: Use `@pytest.mark.asyncio` decorator (auto mode enabled in pyproject.toml)
- **Mocking strategy**: Patch at module import source (`app.services.xxx.get_xxx_service`) not at usage point
- **Singleton testing**: Reset module-level `_xxx_service = None` before and after tests
- **Error logging verification**: Use `caplog` fixture with `caplog.at_level(logging.DEBUG/INFO)`
- **Coverage target**: 80% minimum, tests achieve 87% overall

- **Logging extra key gotcha**: Service code using `extra={"filename": ...}` conflicts with Python logging's reserved LogRecord attributes - tests should patch the logger when testing paths that trigger these logs
- **Logging extra verification**: To check structured logging extra fields, use `hasattr(record, 'field')` and `record.field` on LogRecord objects - `caplog.text` doesn't include extra fields
- **Slow operation testing**: Use `monkeypatch.setattr(time, "monotonic", mock_fn)` to test slow operation warning paths by simulating elapsed time >1 second

---

## 2026-02-01 - client-onboarding-v2-c3y.72
- What was implemented: Comprehensive unit tests for brand config synthesis service
- Files changed:
  - `backend/tests/services/test_brand_config.py` - New test file with 50 tests covering:
    - SynthesisResult dataclass validation
    - Exception classes (BrandConfigServiceError, ValidationError, NotFoundError, SynthesisError)
    - Schema merging (_merge_v2_schemas) with partial overrides
    - Document parsing (_parse_documents) with base64, failures, exceptions
    - V2 schema synthesis (synthesize_v2_schema) success, validation, Claude errors, JSON parsing
    - Synthesize and save (synthesize_and_save) create/update flows, DB errors
    - CRUD operations (get, list, update, delete) with ownership validation
    - Service factory function (get_brand_config_service)
    - Service initialization and helper methods
- **Learnings:**
  - Patterns discovered:
    - Brand config service uses dependency injection for Claude client and document parser
    - Synthesis result includes token usage metrics (input_tokens, output_tokens, request_id)
    - Schema merging uses deep merge for nested dicts (colors, typography, etc.)
    - Test coverage achieved: 93% for app.services.brand_config
  - Gotchas encountered:
    - Service logs use `extra={"filename": ...}` which conflicts with Python's reserved LogRecord attribute
    - Must patch `app.services.brand_config.logger` in tests that trigger warning/debug paths using filename
    - BrandConfigSynthesisRequest requires brand_name, tests with empty string need to use pydantic validation path
    - Markdown code block handling (`\`\`\`json`) is tested for Claude responses

---

## 2026-02-01 - client-onboarding-v2-c3y.63
- What was implemented: Verified and fixed existing comprehensive unit tests for fan-out and categorization logic
- Files changed:
  - `backend/tests/utils/test_url_categorizer.py` - Fixed edge case test for relative paths without leading `/`
- **Learnings:**
  - Patterns discovered:
    - Tests already existed and were comprehensive (208 total tests for these modules)
    - Fan-out tests in `test_paa_enrichment.py` - TestEnrichKeywordFanout class
    - Categorization tests in `test_category_service.py`, `test_paa_categorization.py`, `test_url_categorizer.py`
    - Test docstrings include ERROR LOGGING REQUIREMENTS verification notes
  - Gotchas encountered:
    - `urlparse` treats relative paths without leading `/` ambiguously - they should have `/` prefix
    - Use `python3` directly (no poetry wrapper needed in this environment)
    - Coverage module path syntax uses dots not slashes: `--cov=app.services.paa_enrichment`
---

## 2026-02-01 - client-onboarding-v2-c3y.105
- What was implemented: Comprehensive unit tests for change detection module
- Files changed:
  - `backend/tests/utils/test_change_detection.py` - Enhanced test file from 62 to 87 tests covering:
    - ContentHasher: hash computation, normalization, truncation, dict parsing
    - PageSnapshot, PageChange, ChangeSummary: dataclasses and serialization
    - ChangeDetector: page comparison, significance detection, custom thresholds
    - Convenience functions: singletons, compute_content_hash, detect_changes
    - Edge cases: unicode, special chars, duplicates, large datasets
    - ERROR LOGGING REQUIREMENTS: method entry/exit logging, entity IDs, timing
    - Slow operation warnings: >1 second threshold logging with monkeypatch
    - Exception handling: full error context logging with stack traces
    - Singleton reset: module-level singleton isolation for tests
- **Learnings:**
  - Patterns discovered:
    - Logging uses `extra={}` dict for structured fields - not in text output, check LogRecord attributes directly
    - Use `hasattr(record, 'field')` and `record.field` to verify extra log data
    - Monkeypatch `time.monotonic` to test slow operation warning paths
    - Exception handling logs include `error_type`, `error_message`, `stack_trace` fields
    - Test coverage achieved: 100% for app.utils.change_detection
  - Gotchas encountered:
    - caplog.text doesn't include extra={} fields - must check record.__dict__ or record.field_name
    - Combine context managers: `with caplog.at_level(...), pytest.raises(...)` not nested
    - Import order matters for ruff: `from datetime import UTC, datetime` (alphabetical)
---

