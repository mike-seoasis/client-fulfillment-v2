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

### React Query Error Integration Pattern
When configuring React Query with error handling:
- Use `QueryCache` and `MutationCache` `onError` callbacks for global error handling
- Integrate with existing error reporting service (reportApiError, reportError)
- Add breadcrumbs for debugging context
- Custom retry logic: don't retry 4xx client errors (except 408 timeout, 429 rate limit)
- React Query v5 `onSuccess` callback takes 4 arguments: `(data, variables, context, mutation)`

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

## 2026-02-01 - client-onboarding-v2-c3y.100
- What was implemented: Change detection algorithm for comparing crawl results using content hash comparison
- Files changed:
  - `backend/app/utils/change_detection.py` - New module with ContentHasher, ChangeDetector, and related classes
  - `backend/app/utils/__init__.py` - Exported change detection types and functions
  - `backend/tests/utils/test_change_detection.py` - 62 comprehensive unit tests
- **Implementation details:**
  - `ContentHasher` class: Computes semantic content hashes from title, h1, meta_description, body_text
    - Uses MD5 for fast comparison (not cryptographic security)
    - Normalizes text (lowercase, whitespace normalization) for consistent hashing
    - Configurable `max_content_length` for body text truncation (default 5000 chars)
    - `compute_hash()` and `compute_hash_from_dict()` methods
  - `ChangeDetector` class: Compares page snapshots between crawls
    - Classifies pages as NEW, REMOVED, CHANGED, or UNCHANGED
    - Matches by normalized URL, compares by content_hash
    - Configurable significance thresholds: `new_page_threshold` (default 5), `change_percentage_threshold` (default 10%)
    - `compare()` and `compare_from_dicts()` methods
  - Data classes: `PageSnapshot`, `PageChange`, `ChangeSummary`
  - `ChangeSummary.to_dict()` matches the JSON schema from scheduled-crawls spec
  - Singleton pattern with `get_content_hasher()`, `get_change_detector()`
  - Convenience functions: `compute_content_hash()`, `detect_changes()`
- **Learnings:**
  - The existing `CrawlService.save_crawled_page()` uses a simple SHA256 of markdown content
  - The spec requires semantic hashing: `title|h1|meta_description|content_text[:1000]`
  - Significance = 5+ new pages OR 10%+ content changes (from spec)
  - MD5 is appropriate for change detection (fast, collision-resistant enough for this use case)
  - Text normalization (lowercase, whitespace) ensures minor formatting changes don't trigger false changes
  - All 62 tests pass, ruff lint clean
---

## 2026-02-01 - client-onboarding-v2-c3y.109
- What was implemented: React Query configuration for data fetching and caching with error handling integration
- Files changed:
  - `frontend/package.json` - Added `@tanstack/react-query@^5.90.20` dependency
  - `frontend/src/lib/queryClient.ts` - New QueryClient with error handling integration
  - `frontend/src/lib/hooks/useApiQuery.ts` - Custom hooks for typed API queries and mutations
  - `frontend/src/lib/hooks/index.ts` - Export file for hooks
  - `frontend/src/App.tsx` - Added QueryClientProvider wrapper
- **Implementation details:**
  - `queryClient.ts`:
    - QueryCache/MutationCache with `onError` callbacks tied to error reporting service
    - Custom `shouldRetry` logic: no retry on 4xx (except 408/429), retry 5xx and network errors
    - Default staleTime: 30s, gcTime: 5min
    - Exponential backoff for retries (max 30s)
    - offlineFirst network mode for graceful offline handling
  - `useApiQuery.ts`:
    - `useApiQuery<T>` - Type-safe GET queries with API client integration
    - `useApiMutation<T, V>` - Type-safe mutations with auto-invalidation support
    - `usePrefetch<T>` - Prefetch data on hover/transitions
    - Dynamic endpoint support for mutations via function
  - Error boundaries and global handlers were already implemented (c3y.108)
- **Learnings:**
  - React Query v5 `onSuccess` callback signature is `(data, variables, context, mutation)` - 4 args not 3
  - Use `QueryCache`/`MutationCache` for global error handling, not defaultOptions
  - npm cache permission issues can be bypassed with `--cache /tmp/npm-cache-$USER`
  - Typecheck and lint pass
---

