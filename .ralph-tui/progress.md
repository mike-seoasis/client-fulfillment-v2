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

