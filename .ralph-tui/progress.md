# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Logging Pattern
- All loggers use `python-json-logger` with custom `CustomJsonFormatter` in `app/core/logging.py`
- Service-specific logger classes (DatabaseLogger, RedisLogger, ClaudeLogger, etc.) as singletons
- JSON format in production, text format in development via `LOG_FORMAT` env var
- Logs go to stdout only (Railway standard - no file rotation needed)

### Circuit Breaker Pattern
- Used for all external services (Redis, Claude, Perplexity, DataForSEO, etc.)
- Configuration via `*_circuit_failure_threshold` and `*_circuit_recovery_timeout` settings
- States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing recovery)

### Request Correlation
- `RequestLoggingMiddleware` in `app/main.py` generates UUID `request_id` for every request
- Stored in `request.state.request_id`
- Added to response headers as `X-Request-ID`
- Passed through all log entries via `extra={"request_id": ...}`

### Redis Graceful Degradation
- Redis is optional - app works without it
- `redis_manager.available` property checks if Redis is usable
- `execute()` returns `None` when circuit breaker open or Redis unavailable
- SSL/TLS auto-detected from `rediss://` URL prefix

---

## 2026-02-01 - client-onboarding-v2-c3y.150
- **What was verified**: Production PostgreSQL and Redis configuration already fully implemented
- **Files reviewed** (no changes needed):
  - `backend/app/core/logging.py` - Structured JSON logging with python-json-logger, all log levels, exception capture
  - `backend/app/core/redis.py` - REDIS_URL env var, SSL/TLS support, circuit breaker, retry logic, graceful degradation
  - `backend/app/core/config.py` - All required settings for Redis and logging configuration
  - `backend/app/core/database.py` - Slow query logging, connection pooling, error handling
  - `backend/app/main.py` - Request correlation IDs, structured error responses, timing logs
  - `backend/railway.toml` - Production deployment configuration with JSON logging
  - `backend/pyproject.toml` - All dependencies present (python-json-logger, redis, etc.)
- **Learnings:**
  - Implementation was complete from previous iterations
  - Slow query threshold is configurable via `db_slow_query_threshold_ms` (default 100ms)
  - Railway captures stdout logs automatically - no file rotation needed
  - Redis connection uses exponential backoff: 1s, 2s, 4s delays between retries
---

