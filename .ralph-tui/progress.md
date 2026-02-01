# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Service Layer Pattern (Backend)
Services follow a consistent structure in `/backend/app/services/`:
1. **Module docstring** with ERROR LOGGING REQUIREMENTS
2. **Constants section** (SLOW_OPERATION_THRESHOLD_MS, DEFAULT_MAX_CONCURRENT, etc.)
3. **LLM Prompt Templates** as module constants
4. **Data Classes** with `to_dict()` methods for serialization (Input, Result types)
5. **Exception Classes** (ServiceError base, ValidationError with field_name/value)
6. **Main Service Class** with comprehensive logging:
   - DEBUG: method entry/exit with sanitized params
   - INFO: phase transitions (in_progress → completed)
   - WARNING: validation failures, slow operations (>1s)
   - ERROR: exceptions with full stack trace
7. **Singleton pattern** via `get_service()` function
8. **Convenience functions** wrapping service methods

### API Endpoint Pattern (Backend)
Endpoints in `/backend/app/api/v1/endpoints/`:
1. Helper functions: `_get_request_id()`, `_verify_project_exists()`, `_convert_*()`
2. Request/Response conversion between API schemas and service data classes
3. Structured error responses: `{"error": str, "code": str, "request_id": str}`
4. Log 4xx at WARNING, 5xx at ERROR with exc_info=True

### Brand Voice Integration
Brand voice is injected via `VoiceSchema` from `/backend/app/schemas/brand_config.py`:
- Fields: tone, personality, writing_style, target_audience, value_proposition
- Format for prompts via `_format_brand_voice()` method in content services

---

## 2026-02-01 - client-onboarding-v2-c3y.77
- What was implemented: **Already complete** - Phase 5B: Brand voice context injection was implemented in commit b3cbfec
- Files changed (already exist):
  - `backend/app/services/content_writer.py` (959 lines) - Content generation with Skill Bible rules
  - `backend/app/schemas/content_writer.py` (322 lines) - API request/response schemas
  - `backend/app/api/v1/endpoints/content_writer.py` (464 lines) - API endpoints
  - `backend/app/api/v1/__init__.py` - Router registration
- **Learnings:**
  - Phase 5B implementation includes brand voice injection via `_format_brand_voice()` method
  - Skill Bible rules are embedded in `SKILL_BIBLE_SYSTEM_PROMPT` constant with banned words/patterns
  - Content structure: H1, title_tag, meta_description, top_description, bottom_description
  - All ERROR LOGGING REQUIREMENTS are met: DEBUG entry/exit, INFO phase transitions, WARNING validation failures + slow ops, ERROR with stack traces
  - Router registered at `/projects/{project_id}/phases/content_writer`
---

