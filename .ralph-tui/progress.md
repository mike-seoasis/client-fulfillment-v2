# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

- **Service pattern**: Services in `backend/app/services/` are classes with `@staticmethod` methods. No `__init__` needed for stateless utility services.

---

## 2026-02-08 - S7-001
- Created `ExportService` class with `extract_handle(url)` and `sanitize_filename(name)`
- `extract_handle`: Parses URL, strips query params and trailing slashes. If path contains `/collections/`, returns segment(s) after it; otherwise returns last non-empty path segment.
- `sanitize_filename`: Lowercases name, replaces non-alphanumeric chars with hyphens, collapses multiples, strips edges.
- Files changed: `backend/app/services/export.py` (new)
- **Learnings:**
  - `urlparse` handles query param stripping automatically via `.path` (no manual `?` splitting needed)
  - Ruff linting passes clean; mypy errors exist in other service files but not in new code
  - Run tests from `backend/` directory to get `app.` imports working
---

