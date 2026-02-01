# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### External API Integration Pattern
All external API clients in `backend/app/integrations/` follow this consistent pattern:
1. **Circuit Breaker**: Each client has its own `CircuitBreaker` class (CLOSED → OPEN → HALF_OPEN states)
2. **Lazy HTTP Client**: `httpx.AsyncClient` created on first use via `_get_client()` method
3. **Retry Logic**: Exponential backoff with configurable `max_retries` and `retry_delay`
4. **Exception Hierarchy**: Base error class + specific exceptions (Timeout, RateLimit, Auth, CircuitOpen)
5. **Result Dataclasses**: `success: bool`, `error: str | None`, `duration_ms: float`, `request_id: str | None`
6. **Global Instance Pattern**: Module-level client + `init_*()`, `close_*()`, `get_*()` functions

### Logger Pattern
Each integration gets a dedicated logger class in `app/core/logging.py`:
- Singleton instance at module level (e.g., `dataforseo_logger = DataForSEOLogger()`)
- Standard methods: `api_call_start`, `api_call_success`, `api_call_error`, `timeout`, `rate_limit`, `auth_failure`
- Circuit breaker logging: `circuit_state_change`, `circuit_open`, `circuit_recovery_attempt`, `circuit_closed`
- Body logging at DEBUG with truncation: `request_body`, `response_body`

### Config Pattern
Settings in `app/core/config.py` use Pydantic `BaseSettings`:
- All API credentials via env vars
- Sensible defaults for timeouts (30-60s), retries (3), delays (1s)
- Circuit breaker defaults: `failure_threshold=5`, `recovery_timeout=60.0`

---

## 2026-02-01 - client-onboarding-v2-c3y.56
- What was implemented: DataForSEO API integration client with full feature parity to other integrations
- Files changed:
  - `backend/app/core/config.py` - Added DataForSEO settings (api_login, api_password, timeout, retries, location_code, language_code, circuit breaker)
  - `backend/app/core/logging.py` - Added `DataForSEOLogger` class with all standard logging methods + singleton
  - `backend/app/integrations/dataforseo.py` - New file with complete async client
- **Learnings:**
  - DataForSEO uses HTTP Basic Auth (login/password) vs Bearer token used by others
  - DataForSEO API expects `json=payload` (JSON body) vs `data=payload` (form data) used by Keywords Everywhere
  - DataForSEO batch limit is 1000 keywords vs 100 for Keywords Everywhere
  - Response structure: `tasks[].result[]` pattern for accessing data
  - Location codes: 2840 = United States (default)
---

