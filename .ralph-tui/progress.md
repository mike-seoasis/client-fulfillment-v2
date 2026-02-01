# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Error Logging Pattern
All services follow a consistent error logging pattern:
- DEBUG: Method entry/exit with sanitized parameters (truncate strings to 50 chars)
- INFO: Phase transitions and state changes
- WARNING: Slow operations (>1000ms), non-fatal failures
- ERROR: Critical failures with full stack trace (`traceback.format_exc()`, `exc_info=True`)
- Always include entity IDs (`project_id`, `page_id`) in log `extra` dict

### Fan-Out Pattern for API Enrichment
When fetching data that can be recursively expanded:
1. Initial fetch with base query
2. Take first N results (configurable `max_fanout_questions`)
3. Concurrent secondary fetches using `asyncio.Semaphore` for rate limiting
4. Deduplicate across all results (normalize keys before comparison)
5. Track parent-child relationships (`is_nested`, `parent_question`)
6. Graceful degradation - individual failures don't fail the whole operation

### Graceful Degradation Pattern
When calling optional/fallback services:
```python
try:
    result = await optional_service()
except Exception as e:
    logger.warning("Service failed", extra={"error": str(e), "stack_trace": traceback.format_exc()})
    # Continue with existing results, don't fail the whole operation
```

### Log Key Naming Convention
Python's `logging` module reserves certain keys in `LogRecord`. When logging with `extra` dict:
- **Avoid using**: `filename`, `lineno`, `funcName`, `pathname`, `module`, `name`, `levelname`, `levelno`, `msg`, `args`, `exc_info`, `exc_text`, `created`, `msecs`, `relativeCreated`, `thread`, `threadName`, `processName`, `process`
- **Use prefixed alternatives**: `document_filename` instead of `filename`, `target_url` instead of `url` if ambiguous

---

## 2026-02-01 - client-onboarding-v2-c3y.58
- What was implemented: Fan-out strategy for PAA (People Also Ask) questions was already fully implemented
- Files changed: None - implementation was complete
- **Verification performed:**
  - All 38 unit tests pass in `tests/services/test_paa_enrichment.py`
  - Ruff linting passes
  - Module imports correctly
- **Learnings:**
  - Fan-out implementation lives in `backend/app/services/paa_enrichment.py`
  - Uses DataForSEO SERP API with `people_also_ask_click_depth` parameter (1-4)
  - Concurrent fan-out controlled by `asyncio.Semaphore(max_concurrent_fanout)`
  - Deduplication uses normalized question text (lowercase, strip, remove trailing `?`)
  - Related searches fallback triggers when PAA count < `min_paa_for_fallback`
  - All error logging requirements already satisfied (see docstring lines 9-16)
---

## 2026-02-01 - client-onboarding-v2-c3y.67
- What was implemented: Document parser utility for PDF, DOCX, TXT brand documents
- Files changed:
  - `backend/pyproject.toml` - Added `pypdf>=4.0.0` and `python-docx>=1.1.0` dependencies
  - `backend/app/utils/document_parser.py` - New module with DocumentParser class
  - `backend/app/utils/__init__.py` - Exported document parser types and functions
  - `backend/tests/utils/test_document_parser.py` - 51 comprehensive unit tests
- **Implementation details:**
  - `DocumentParser` class with `parse_bytes()` and `parse_file()` methods
  - Supports PDF (pypdf), DOCX (python-docx), and TXT (with encoding detection)
  - Returns `DocumentParseResult` with content, metadata, and sections
  - Metadata includes: filename, format, file_size, page_count, word_count, character_count, author, title, dates
  - File size validation with configurable `max_file_size` (default 50MB)
  - Exception hierarchy: `DocumentParserError` -> `UnsupportedFormatError`, `FileTooLargeError`, `DocumentCorruptedError`
  - Singleton pattern with `get_document_parser()` and convenience functions
- **Learnings:**
  - Python logging reserves `filename` key in LogRecord - use `document_filename` instead
  - pypdf's `reader.metadata` can be `None` - must check before accessing attributes
  - DOCX doesn't have reliable page count (property is None)
  - TXT encoding detection: try UTF-8 -> UTF-8-BOM -> Latin-1 -> CP1252 -> UTF-8 with replacements
  - Tests should handle both "library installed" and "library not installed" cases gracefully
  - All 51 tests pass, ruff lint clean
---

