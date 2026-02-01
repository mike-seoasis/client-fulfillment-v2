# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Pattern
- Services use dataclasses for result types with `to_dict()` methods
- Global singleton pattern via `_service: T | None = None` and `get_*_service()` function
- Comprehensive logging with `extra={}` dict containing context (project_id, page_id, etc.)
- Slow operation threshold logged at WARNING (>1000ms)
- Phase transitions logged at INFO level

### Error Logging Requirements
- Method entry/exit at DEBUG level with parameters (sanitized)
- All exceptions with full stack trace via `traceback.format_exc()`
- Entity IDs (project_id, page_id) in all service logs
- Validation failures with field names and rejected values
- Timing logs for operations >1 second

### Schema Pattern
- Use Pydantic BaseModel with Field() for all properties
- Include docstring with Error Logging Requirements and Railway Deployment Requirements
- Use `field_validator` for input validation
- Always include `description` in Field()

---

## 2026-02-01 - client-onboarding-v2-c3y.73
- What was implemented:
  - Phase 5A: PAA analysis by intent categorization service
  - Groups PAA questions by intent category (buying, usage, care, comparison)
  - Prioritizes questions per content-generation spec (buying → care → usage)
  - Determines content angle recommendation based on question distribution
  - Calculates intent distribution percentages

- Files changed:
  - `backend/app/services/paa_analysis.py` (NEW) - Core analysis service
  - `backend/app/schemas/paa_analysis.py` (NEW) - Request/response schemas

- **Learnings:**
  - PAA categorization is separate from PAA analysis - categorization assigns intent to questions, analysis groups and prioritizes them
  - Content angle determination follows spec rules: more care questions = longevity focus, more buying = purchase focus
  - Priority order: buying (highest) → care → usage → comparison
  - All dataclasses need `to_dict()` for serialization compatibility
  - Import `get_paa_categorization_service` inside method to avoid circular imports

---

