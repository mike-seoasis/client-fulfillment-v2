# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Integration Client Pattern
All API integration clients follow a consistent pattern in `/backend/app/integrations/`:
1. **Configuration**: Settings in `app/core/config.py` with prefix naming (e.g., `google_nlp_api_key`, `google_nlp_timeout`)
2. **Logger**: Dedicated logger class in `app/core/logging.py` with methods for API calls, errors, circuit breaker events
3. **Client Class**: Async client with circuit breaker, retry logic, exponential backoff
4. **Global Instance**: Module-level client with `init_*`, `close_*`, and `get_*` dependency functions
5. **Error Classes**: Hierarchy of custom exceptions (Base, Timeout, RateLimit, Auth, CircuitOpen)

### Error Logging Requirements
- Log all outbound API calls with endpoint, method, timing at DEBUG level
- Log request/response bodies at DEBUG level (truncate large responses)
- Log 4xx errors at WARNING level, 5xx at ERROR level
- Include retry attempt number in logs
- Mask API keys and tokens in all logs

---

## 2026-02-01 - client-onboarding-v2-c3y.88
- **What was implemented**: Google Cloud NLP integration client for entity extraction
- **Files changed**:
  - `backend/app/core/config.py` - Added Google Cloud NLP settings (api_key, project_id, timeout, max_retries, retry_delay, circuit breaker settings)
  - `backend/app/core/logging.py` - Added GoogleNLPLogger class with comprehensive logging methods
  - `backend/app/integrations/google_nlp.py` - NEW: Complete async client with entity extraction capabilities
- **Learnings:**
  - Integration clients follow a strict pattern: config settings -> logger -> client class -> global instance management
  - Circuit breaker pattern is consistent across all integrations with CLOSED/OPEN/HALF_OPEN states
  - Google Cloud NLP API uses API key as query parameter (`?key=`) rather than header auth
  - Entity extraction returns entities with: name, type (EntityType enum), salience score, mentions, metadata
---

