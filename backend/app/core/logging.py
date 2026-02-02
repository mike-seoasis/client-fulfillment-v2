"""Structured logging configuration for Railway deployment.

All logs go to stdout/stderr for Railway to capture.
Uses JSON format for structured logging in production.

ERROR LOGGING REQUIREMENTS:
- Database connection errors with masked connection string
- Slow queries (>100ms) at WARNING level
- Transaction failures with rollback context
- Migration start/end with version info
- Table/model name in database error logs
- Connection pool exhaustion at CRITICAL level
"""

import logging
import sys
from datetime import UTC, datetime
from typing import Any

from pythonjsonlogger import jsonlogger

from app.core.config import get_settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):  # type: ignore[name-defined]
    """Custom JSON formatter with additional fields."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.now(UTC).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def mask_connection_string(conn_str: str) -> str:
    """Mask sensitive parts of database connection string."""
    if not conn_str:
        return ""
    # Mask password in postgresql://user:password@host:port/db format
    import re

    pattern = r"(://[^:]+:)([^@]+)(@)"
    return re.sub(pattern, r"\1****\3", conn_str)


def setup_logging() -> None:
    """Configure application logging.

    Outputs to stdout/stderr only for Railway deployment.
    Uses JSON format in production, text format in development.
    """
    settings = get_settings()

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create stdout handler (Railway captures stdout/stderr)
    handler = logging.StreamHandler(sys.stdout)

    formatter: logging.Formatter
    if settings.log_format == "json":
        formatter = CustomJsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Set log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


# Database-specific logging helpers
class DatabaseLogger:
    """Logger for database operations with required error logging."""

    def __init__(self) -> None:
        self.logger = get_logger("database")

    def connection_error(self, error: Exception, connection_string: str) -> None:
        """Log database connection error with masked connection string."""
        self.logger.error(
            "Database connection failed",
            extra={
                "connection_string": mask_connection_string(connection_string),
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )

    def slow_query(
        self, query: str, duration_ms: float, table: str | None = None
    ) -> None:
        """Log slow query at WARNING level."""
        self.logger.warning(
            "Slow query detected",
            extra={
                "duration_ms": duration_ms,
                "query": query[:500],  # Truncate long queries
                "table": table,
            },
        )

    def transaction_failure(
        self, error: Exception, table: str | None = None, context: str | None = None
    ) -> None:
        """Log transaction failure with rollback context."""
        self.logger.error(
            "Transaction failed, rolling back",
            extra={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "table": table,
                "rollback_context": context,
            },
        )

    def migration_start(self, version: str, description: str) -> None:
        """Log migration start."""
        self.logger.info(
            "Starting database migration",
            extra={
                "migration_version": version,
                "description": description,
            },
        )

    def migration_end(self, version: str, success: bool) -> None:
        """Log migration completion."""
        level = logging.INFO if success else logging.ERROR
        self.logger.log(
            level,
            "Database migration completed",
            extra={
                "migration_version": version,
                "success": success,
            },
        )

    def migration_step(
        self, step: str, revision: str, success: bool, duration_ms: float | None = None
    ) -> None:
        """Log individual migration step."""
        level = logging.INFO if success else logging.ERROR
        self.logger.log(
            level,
            f"Migration step: {step}",
            extra={
                "step": step,
                "revision": revision,
                "success": success,
                "duration_ms": duration_ms,
            },
        )

    def rollback_triggered(
        self, reason: str, from_version: str, to_version: str | None = None
    ) -> None:
        """Log rollback trigger."""
        self.logger.warning(
            "Database rollback triggered",
            extra={
                "reason": reason,
                "from_version": from_version,
                "to_version": to_version or "previous",
            },
        )

    def rollback_executed(self, from_version: str, to_version: str, success: bool) -> None:
        """Log rollback execution."""
        level = logging.INFO if success else logging.ERROR
        self.logger.log(
            level,
            "Database rollback executed",
            extra={
                "from_version": from_version,
                "to_version": to_version,
                "success": success,
            },
        )

    def pool_exhausted(self, pool_size: int, waiting: int) -> None:
        """Log connection pool exhaustion at CRITICAL level."""
        self.logger.critical(
            "Database connection pool exhausted",
            extra={
                "pool_size": pool_size,
                "waiting_connections": waiting,
            },
        )


# Singleton database logger
db_logger = DatabaseLogger()


class RedisLogger:
    """Logger for Redis operations with required error logging."""

    def __init__(self) -> None:
        self.logger = get_logger("redis")

    def connection_error(self, error: Exception, connection_string: str) -> None:
        """Log Redis connection error with masked connection string."""
        self.logger.error(
            "Redis connection failed",
            extra={
                "connection_string": mask_connection_string(connection_string),
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )

    def connection_success(self) -> None:
        """Log successful Redis connection."""
        self.logger.info("Redis connection established successfully")

    def operation(
        self,
        operation: str,
        key: str,
        duration_ms: float,
        success: bool,
        retry_attempt: int = 0,
    ) -> None:
        """Log Redis operation with timing."""
        level = logging.DEBUG if success else logging.WARNING
        self.logger.log(
            level,
            f"Redis {operation}",
            extra={
                "operation": operation,
                "key": key[:100] if key else None,  # Truncate long keys
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "retry_attempt": retry_attempt,
            },
        )

    def timeout(self, operation: str, key: str, timeout_seconds: float) -> None:
        """Log Redis timeout."""
        self.logger.warning(
            "Redis operation timeout",
            extra={
                "operation": operation,
                "key": key[:100] if key else None,
                "timeout_seconds": timeout_seconds,
            },
        )

    def circuit_state_change(
        self, previous_state: str, new_state: str, failure_count: int
    ) -> None:
        """Log circuit breaker state change."""
        self.logger.warning(
            "Redis circuit breaker state changed",
            extra={
                "previous_state": previous_state,
                "new_state": new_state,
                "failure_count": failure_count,
            },
        )

    def circuit_open(self, failure_count: int, recovery_timeout: float) -> None:
        """Log circuit breaker opening."""
        self.logger.error(
            "Redis circuit breaker opened - Redis operations disabled",
            extra={
                "failure_count": failure_count,
                "recovery_timeout_seconds": recovery_timeout,
            },
        )

    def circuit_recovery_attempt(self) -> None:
        """Log circuit breaker recovery attempt."""
        self.logger.info("Redis circuit breaker attempting recovery")

    def circuit_closed(self) -> None:
        """Log circuit breaker closing (recovery successful)."""
        self.logger.info("Redis circuit breaker closed - Redis operations restored")

    def pool_exhausted(self, pool_size: int) -> None:
        """Log Redis connection pool exhaustion at CRITICAL level."""
        self.logger.critical(
            "Redis connection pool exhausted",
            extra={
                "pool_size": pool_size,
            },
        )

    def graceful_fallback(self, operation: str, reason: str) -> None:
        """Log graceful fallback when Redis is unavailable."""
        self.logger.info(
            "Redis unavailable, using fallback",
            extra={
                "operation": operation,
                "reason": reason,
            },
        )


# Singleton Redis logger
redis_logger = RedisLogger()


class Crawl4AILogger:
    """Logger for Crawl4AI operations with required error logging.

    Logs all outbound API calls with endpoint, method, timing.
    Logs request/response bodies at DEBUG level.
    Handles timeouts, rate limits (429), auth failures (401/403).
    """

    def __init__(self) -> None:
        self.logger = get_logger("crawl4ai")

    def api_call_start(
        self,
        method: str,
        endpoint: str,
        url: str | None = None,
        retry_attempt: int = 0,
    ) -> None:
        """Log outbound API call start at DEBUG level."""
        self.logger.debug(
            f"Crawl4AI API call: {method} {endpoint}",
            extra={
                "method": method,
                "endpoint": endpoint,
                "target_url": url,
                "retry_attempt": retry_attempt,
            },
        )

    def api_call_success(
        self,
        method: str,
        endpoint: str,
        duration_ms: float,
        status_code: int,
        url: str | None = None,
    ) -> None:
        """Log successful API call at DEBUG level."""
        self.logger.debug(
            f"Crawl4AI API call completed: {method} {endpoint}",
            extra={
                "method": method,
                "endpoint": endpoint,
                "target_url": url,
                "duration_ms": round(duration_ms, 2),
                "status_code": status_code,
                "success": True,
            },
        )

    def api_call_error(
        self,
        method: str,
        endpoint: str,
        duration_ms: float,
        status_code: int | None,
        error: str,
        error_type: str,
        url: str | None = None,
        retry_attempt: int = 0,
    ) -> None:
        """Log failed API call at WARNING or ERROR level based on status."""
        # 4xx at WARNING, 5xx and others at ERROR
        level = logging.WARNING if status_code and 400 <= status_code < 500 else logging.ERROR
        self.logger.log(
            level,
            f"Crawl4AI API call failed: {method} {endpoint}",
            extra={
                "method": method,
                "endpoint": endpoint,
                "target_url": url,
                "duration_ms": round(duration_ms, 2),
                "status_code": status_code,
                "error": error,
                "error_type": error_type,
                "retry_attempt": retry_attempt,
                "success": False,
            },
        )

    def timeout(
        self, endpoint: str, timeout_seconds: float, url: str | None = None
    ) -> None:
        """Log request timeout at WARNING level."""
        self.logger.warning(
            "Crawl4AI request timeout",
            extra={
                "endpoint": endpoint,
                "target_url": url,
                "timeout_seconds": timeout_seconds,
            },
        )

    def rate_limit(
        self,
        endpoint: str,
        retry_after: int | None = None,
        url: str | None = None,
    ) -> None:
        """Log rate limit (429) at WARNING level."""
        self.logger.warning(
            "Crawl4AI rate limit hit (429)",
            extra={
                "endpoint": endpoint,
                "target_url": url,
                "retry_after_seconds": retry_after,
            },
        )

    def auth_failure(
        self, endpoint: str, status_code: int, url: str | None = None
    ) -> None:
        """Log authentication failure (401/403) at WARNING level."""
        self.logger.warning(
            f"Crawl4AI authentication failed ({status_code})",
            extra={
                "endpoint": endpoint,
                "target_url": url,
                "status_code": status_code,
            },
        )

    def request_body(self, endpoint: str, body: dict[str, Any]) -> None:
        """Log request body at DEBUG level (truncate large values)."""
        # Truncate large string values for logging
        truncated_body = self._truncate_body(body)
        self.logger.debug(
            "Crawl4AI request body",
            extra={
                "endpoint": endpoint,
                "request_body": truncated_body,
            },
        )

    def response_body(
        self, endpoint: str, body: dict[str, Any], duration_ms: float
    ) -> None:
        """Log response body at DEBUG level (truncate large values)."""
        truncated_body = self._truncate_body(body)
        self.logger.debug(
            "Crawl4AI response body",
            extra={
                "endpoint": endpoint,
                "response_body": truncated_body,
                "duration_ms": round(duration_ms, 2),
            },
        )

    def _truncate_body(self, body: dict[str, Any], max_length: int = 500) -> dict[str, Any]:
        """Truncate large string values in body for logging."""
        result: dict[str, Any] = {}
        for key, value in body.items():
            if isinstance(value, str) and len(value) > max_length:
                result[key] = value[:max_length] + f"... (truncated, {len(value)} chars)"
            elif isinstance(value, dict):
                result[key] = self._truncate_body(value, max_length)
            elif isinstance(value, list) and len(value) > 10:
                result[key] = f"[list with {len(value)} items]"
            else:
                result[key] = value
        return result

    def circuit_state_change(
        self, previous_state: str, new_state: str, failure_count: int
    ) -> None:
        """Log circuit breaker state change at WARNING level."""
        self.logger.warning(
            "Crawl4AI circuit breaker state changed",
            extra={
                "previous_state": previous_state,
                "new_state": new_state,
                "failure_count": failure_count,
            },
        )

    def circuit_open(self, failure_count: int, recovery_timeout: float) -> None:
        """Log circuit breaker opening at ERROR level."""
        self.logger.error(
            "Crawl4AI circuit breaker opened - API calls disabled",
            extra={
                "failure_count": failure_count,
                "recovery_timeout_seconds": recovery_timeout,
            },
        )

    def circuit_recovery_attempt(self) -> None:
        """Log circuit breaker recovery attempt at INFO level."""
        self.logger.info("Crawl4AI circuit breaker attempting recovery")

    def circuit_closed(self) -> None:
        """Log circuit breaker closing at INFO level."""
        self.logger.info("Crawl4AI circuit breaker closed - API calls restored")

    def graceful_fallback(self, operation: str, reason: str) -> None:
        """Log graceful fallback when Crawl4AI is unavailable."""
        self.logger.info(
            "Crawl4AI unavailable, using fallback",
            extra={
                "operation": operation,
                "reason": reason,
            },
        )

    def crawl_start(self, url: str, options: dict[str, Any] | None = None) -> None:
        """Log crawl operation start at INFO level."""
        self.logger.info(
            "Starting crawl",
            extra={
                "target_url": url,
                "options": options or {},
            },
        )

    def crawl_complete(
        self,
        url: str,
        duration_ms: float,
        success: bool,
        pages_crawled: int = 1,
    ) -> None:
        """Log crawl operation completion."""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            "Crawl completed" if success else "Crawl failed",
            extra={
                "target_url": url,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "pages_crawled": pages_crawled,
            },
        )


# Singleton Crawl4AI logger
crawl4ai_logger = Crawl4AILogger()


class ClaudeLogger:
    """Logger for Claude/Anthropic LLM operations with required error logging.

    Logs all outbound API calls with endpoint, method, timing.
    Logs request/response bodies at DEBUG level (truncate large responses).
    Handles timeouts, rate limits (429), auth failures (401/403).
    Includes retry attempt number in logs.
    Masks API keys in all logs.
    Logs circuit breaker state changes.
    """

    def __init__(self) -> None:
        self.logger = get_logger("claude")

    def api_call_start(
        self,
        model: str,
        prompt_length: int,
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log outbound API call start at DEBUG level."""
        self.logger.debug(
            f"Claude API call: {model}",
            extra={
                "model": model,
                "prompt_length": prompt_length,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
            },
        )

    def api_call_success(
        self,
        model: str,
        duration_ms: float,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log successful API call at DEBUG level with token usage."""
        self.logger.debug(
            f"Claude API call completed: {model}",
            extra={
                "model": model,
                "duration_ms": round(duration_ms, 2),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": (input_tokens or 0) + (output_tokens or 0),
                "request_id": request_id,
                "success": True,
            },
        )

    def api_call_error(
        self,
        model: str,
        duration_ms: float,
        status_code: int | None,
        error: str,
        error_type: str,
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log failed API call at WARNING or ERROR level based on status."""
        # 4xx at WARNING, 5xx and others at ERROR
        level = logging.WARNING if status_code and 400 <= status_code < 500 else logging.ERROR
        self.logger.log(
            level,
            f"Claude API call failed: {model}",
            extra={
                "model": model,
                "duration_ms": round(duration_ms, 2),
                "status_code": status_code,
                "error": error,
                "error_type": error_type,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
                "success": False,
            },
        )

    def timeout(self, model: str, timeout_seconds: float) -> None:
        """Log request timeout at WARNING level."""
        self.logger.warning(
            "Claude API request timeout",
            extra={
                "model": model,
                "timeout_seconds": timeout_seconds,
            },
        )

    def rate_limit(
        self,
        model: str,
        retry_after: float | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log rate limit (429) at WARNING level."""
        self.logger.warning(
            "Claude API rate limit hit (429)",
            extra={
                "model": model,
                "retry_after_seconds": retry_after,
                "request_id": request_id,
            },
        )

    def auth_failure(self, status_code: int) -> None:
        """Log authentication failure (401/403) at WARNING level."""
        self.logger.warning(
            f"Claude API authentication failed ({status_code})",
            extra={
                "status_code": status_code,
            },
        )

    def request_body(self, model: str, system_prompt: str, user_prompt: str) -> None:
        """Log request body at DEBUG level (truncate large values)."""
        self.logger.debug(
            "Claude API request body",
            extra={
                "model": model,
                "system_prompt": self._truncate_text(system_prompt, 200),
                "user_prompt": self._truncate_text(user_prompt, 500),
            },
        )

    def response_body(
        self,
        model: str,
        response_text: str,
        duration_ms: float,
        stop_reason: str | None = None,
    ) -> None:
        """Log response body at DEBUG level (truncate large values)."""
        self.logger.debug(
            "Claude API response body",
            extra={
                "model": model,
                "response_text": self._truncate_text(response_text, 500),
                "duration_ms": round(duration_ms, 2),
                "stop_reason": stop_reason,
            },
        )

    def _truncate_text(self, text: str, max_length: int = 500) -> str:
        """Truncate text for logging."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + f"... (truncated, {len(text)} chars)"

    def token_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_creation_input_tokens: int | None = None,
        cache_read_input_tokens: int | None = None,
    ) -> None:
        """Log API quota/credit usage at INFO level."""
        extra: dict[str, Any] = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
        if cache_creation_input_tokens:
            extra["cache_creation_input_tokens"] = cache_creation_input_tokens
        if cache_read_input_tokens:
            extra["cache_read_input_tokens"] = cache_read_input_tokens

        self.logger.info("Claude API token usage", extra=extra)

    def circuit_state_change(
        self, previous_state: str, new_state: str, failure_count: int
    ) -> None:
        """Log circuit breaker state change at WARNING level."""
        self.logger.warning(
            "Claude circuit breaker state changed",
            extra={
                "previous_state": previous_state,
                "new_state": new_state,
                "failure_count": failure_count,
            },
        )

    def circuit_open(self, failure_count: int, recovery_timeout: float) -> None:
        """Log circuit breaker opening at ERROR level."""
        self.logger.error(
            "Claude circuit breaker opened - API calls disabled",
            extra={
                "failure_count": failure_count,
                "recovery_timeout_seconds": recovery_timeout,
            },
        )

    def circuit_recovery_attempt(self) -> None:
        """Log circuit breaker recovery attempt at INFO level."""
        self.logger.info("Claude circuit breaker attempting recovery")

    def circuit_closed(self) -> None:
        """Log circuit breaker closing at INFO level."""
        self.logger.info("Claude circuit breaker closed - API calls restored")

    def graceful_fallback(self, operation: str, reason: str) -> None:
        """Log graceful fallback when Claude is unavailable."""
        self.logger.info(
            "Claude unavailable, using fallback",
            extra={
                "operation": operation,
                "reason": reason,
            },
        )

    def categorization_start(self, url: str, category_count: int) -> None:
        """Log categorization operation start at INFO level."""
        self.logger.info(
            "Starting page categorization",
            extra={
                "target_url": url[:200],
                "category_count": category_count,
            },
        )

    def categorization_complete(
        self,
        url: str,
        category: str,
        confidence: float,
        duration_ms: float,
        success: bool,
    ) -> None:
        """Log categorization operation completion."""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            "Categorization completed" if success else "Categorization failed",
            extra={
                "target_url": url[:200],
                "category": category,
                "confidence": round(confidence, 3),
                "duration_ms": round(duration_ms, 2),
                "success": success,
            },
        )

    def batch_start(
        self,
        batch_index: int,
        batch_size: int,
        total_batches: int,
        total_pages: int,
        project_id: str | None = None,
    ) -> None:
        """Log batch processing start at DEBUG level."""
        self.logger.debug(
            f"Starting LLM batch {batch_index + 1}/{total_batches}",
            extra={
                "batch_index": batch_index,
                "batch_size": batch_size,
                "total_batches": total_batches,
                "total_pages": total_pages,
                "project_id": project_id,
            },
        )

    def batch_complete(
        self,
        batch_index: int,
        batch_size: int,
        total_batches: int,
        success_count: int,
        failure_count: int,
        duration_ms: float,
        total_input_tokens: int,
        total_output_tokens: int,
        project_id: str | None = None,
    ) -> None:
        """Log batch processing completion at INFO level."""
        self.logger.info(
            f"LLM batch {batch_index + 1}/{total_batches} complete",
            extra={
                "batch_index": batch_index,
                "batch_size": batch_size,
                "total_batches": total_batches,
                "success_count": success_count,
                "failure_count": failure_count,
                "duration_ms": round(duration_ms, 2),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "project_id": project_id,
            },
        )

    def batch_error(
        self,
        batch_index: int,
        total_batches: int,
        error: str,
        error_type: str,
        duration_ms: float,
        project_id: str | None = None,
    ) -> None:
        """Log batch processing error at ERROR level."""
        self.logger.error(
            f"LLM batch {batch_index + 1}/{total_batches} failed",
            extra={
                "batch_index": batch_index,
                "total_batches": total_batches,
                "error": error,
                "error_type": error_type,
                "duration_ms": round(duration_ms, 2),
                "project_id": project_id,
            },
        )

    def batch_processing_start(
        self,
        total_pages: int,
        batch_size: int,
        total_batches: int,
        project_id: str | None = None,
    ) -> None:
        """Log batch processing session start at INFO level."""
        self.logger.info(
            f"Starting batch LLM categorization: {total_pages} pages in {total_batches} batches",
            extra={
                "total_pages": total_pages,
                "batch_size": batch_size,
                "total_batches": total_batches,
                "project_id": project_id,
            },
        )

    def batch_processing_complete(
        self,
        total_pages: int,
        total_batches: int,
        success_count: int,
        failure_count: int,
        duration_ms: float,
        total_input_tokens: int,
        total_output_tokens: int,
        project_id: str | None = None,
    ) -> None:
        """Log batch processing session completion at INFO level."""
        self.logger.info(
            f"Batch LLM categorization complete: {success_count}/{total_pages} succeeded",
            extra={
                "total_pages": total_pages,
                "total_batches": total_batches,
                "success_count": success_count,
                "failure_count": failure_count,
                "duration_ms": round(duration_ms, 2),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "average_ms_per_page": round(duration_ms / total_pages, 2) if total_pages > 0 else 0,
                "project_id": project_id,
            },
        )


# Singleton Claude logger
claude_logger = ClaudeLogger()


class PerplexityLogger:
    """Logger for Perplexity API operations with required error logging.

    Logs all outbound API calls with endpoint, method, timing.
    Logs request/response bodies at DEBUG level (truncate large responses).
    Handles timeouts, rate limits (429), auth failures (401/403).
    Includes retry attempt number in logs.
    Masks API keys in all logs.
    Logs circuit breaker state changes.
    """

    def __init__(self) -> None:
        self.logger = get_logger("perplexity")

    def api_call_start(
        self,
        model: str,
        prompt_length: int,
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log outbound API call start at DEBUG level."""
        self.logger.debug(
            f"Perplexity API call: {model}",
            extra={
                "model": model,
                "prompt_length": prompt_length,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
            },
        )

    def api_call_success(
        self,
        model: str,
        duration_ms: float,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log successful API call at DEBUG level with token usage."""
        self.logger.debug(
            f"Perplexity API call completed: {model}",
            extra={
                "model": model,
                "duration_ms": round(duration_ms, 2),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": (input_tokens or 0) + (output_tokens or 0),
                "request_id": request_id,
                "success": True,
            },
        )

    def api_call_error(
        self,
        model: str,
        duration_ms: float,
        status_code: int | None,
        error: str,
        error_type: str,
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log failed API call at WARNING or ERROR level based on status."""
        # 4xx at WARNING, 5xx and others at ERROR
        level = logging.WARNING if status_code and 400 <= status_code < 500 else logging.ERROR
        self.logger.log(
            level,
            f"Perplexity API call failed: {model}",
            extra={
                "model": model,
                "duration_ms": round(duration_ms, 2),
                "status_code": status_code,
                "error": error,
                "error_type": error_type,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
                "success": False,
            },
        )

    def timeout(self, model: str, timeout_seconds: float) -> None:
        """Log request timeout at WARNING level."""
        self.logger.warning(
            "Perplexity API request timeout",
            extra={
                "model": model,
                "timeout_seconds": timeout_seconds,
            },
        )

    def rate_limit(
        self,
        model: str,
        retry_after: float | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log rate limit (429) at WARNING level."""
        self.logger.warning(
            "Perplexity API rate limit hit (429)",
            extra={
                "model": model,
                "retry_after_seconds": retry_after,
                "request_id": request_id,
            },
        )

    def auth_failure(self, status_code: int) -> None:
        """Log authentication failure (401/403) at WARNING level."""
        self.logger.warning(
            f"Perplexity API authentication failed ({status_code})",
            extra={
                "status_code": status_code,
            },
        )

    def request_body(self, model: str, system_prompt: str, user_prompt: str) -> None:
        """Log request body at DEBUG level (truncate large values)."""
        self.logger.debug(
            "Perplexity API request body",
            extra={
                "model": model,
                "system_prompt": self._truncate_text(system_prompt, 200),
                "user_prompt": self._truncate_text(user_prompt, 500),
            },
        )

    def response_body(
        self,
        model: str,
        response_text: str,
        duration_ms: float,
        citations: list[str] | None = None,
    ) -> None:
        """Log response body at DEBUG level (truncate large values)."""
        self.logger.debug(
            "Perplexity API response body",
            extra={
                "model": model,
                "response_text": self._truncate_text(response_text, 500),
                "duration_ms": round(duration_ms, 2),
                "citation_count": len(citations) if citations else 0,
            },
        )

    def _truncate_text(self, text: str, max_length: int = 500) -> str:
        """Truncate text for logging."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + f"... (truncated, {len(text)} chars)"

    def token_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Log API token usage at INFO level."""
        self.logger.info(
            "Perplexity API token usage",
            extra={
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        )

    def circuit_state_change(
        self, previous_state: str, new_state: str, failure_count: int
    ) -> None:
        """Log circuit breaker state change at WARNING level."""
        self.logger.warning(
            "Perplexity circuit breaker state changed",
            extra={
                "previous_state": previous_state,
                "new_state": new_state,
                "failure_count": failure_count,
            },
        )

    def circuit_open(self, failure_count: int, recovery_timeout: float) -> None:
        """Log circuit breaker opening at ERROR level."""
        self.logger.error(
            "Perplexity circuit breaker opened - API calls disabled",
            extra={
                "failure_count": failure_count,
                "recovery_timeout_seconds": recovery_timeout,
            },
        )

    def circuit_recovery_attempt(self) -> None:
        """Log circuit breaker recovery attempt at INFO level."""
        self.logger.info("Perplexity circuit breaker attempting recovery")

    def circuit_closed(self) -> None:
        """Log circuit breaker closing at INFO level."""
        self.logger.info("Perplexity circuit breaker closed - API calls restored")

    def graceful_fallback(self, operation: str, reason: str) -> None:
        """Log graceful fallback when Perplexity is unavailable."""
        self.logger.info(
            "Perplexity unavailable, using fallback",
            extra={
                "operation": operation,
                "reason": reason,
            },
        )

    def analysis_start(self, url: str) -> None:
        """Log website analysis operation start at INFO level."""
        self.logger.info(
            "Starting website analysis",
            extra={
                "target_url": url[:200],
            },
        )

    def analysis_complete(
        self,
        url: str,
        duration_ms: float,
        success: bool,
        citation_count: int = 0,
    ) -> None:
        """Log website analysis operation completion."""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            "Website analysis completed" if success else "Website analysis failed",
            extra={
                "target_url": url[:200],
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "citation_count": citation_count,
            },
        )


# Singleton Perplexity logger
perplexity_logger = PerplexityLogger()


class SchedulerLogger:
    """Logger for APScheduler operations with required error logging.

    Logs scheduler lifecycle events (start, stop, pause, resume).
    Logs job execution (start, success, error, missed).
    Logs job store operations at DEBUG level.
    Handles graceful degradation when scheduler is unavailable.
    """

    def __init__(self) -> None:
        self.logger = get_logger("scheduler")

    def scheduler_start(self, job_count: int) -> None:
        """Log scheduler start at INFO level."""
        self.logger.info(
            "Scheduler started",
            extra={
                "job_count": job_count,
            },
        )

    def scheduler_stop(self, graceful: bool) -> None:
        """Log scheduler stop at INFO level."""
        self.logger.info(
            "Scheduler stopped",
            extra={
                "graceful": graceful,
            },
        )

    def scheduler_pause(self) -> None:
        """Log scheduler pause at INFO level."""
        self.logger.info("Scheduler paused")

    def scheduler_resume(self) -> None:
        """Log scheduler resume at INFO level."""
        self.logger.info("Scheduler resumed")

    def job_added(
        self,
        job_id: str,
        job_name: str | None,
        trigger: str,
        next_run: str | None = None,
    ) -> None:
        """Log job addition at INFO level."""
        self.logger.info(
            "Job added to scheduler",
            extra={
                "job_id": job_id,
                "job_name": job_name,
                "trigger": trigger,
                "next_run": next_run,
            },
        )

    def job_removed(self, job_id: str, job_name: str | None = None) -> None:
        """Log job removal at INFO level."""
        self.logger.info(
            "Job removed from scheduler",
            extra={
                "job_id": job_id,
                "job_name": job_name,
            },
        )

    def job_modified(
        self,
        job_id: str,
        job_name: str | None,
        changes: dict[str, Any] | None = None,
    ) -> None:
        """Log job modification at INFO level."""
        self.logger.info(
            "Job modified",
            extra={
                "job_id": job_id,
                "job_name": job_name,
                "changes": changes,
            },
        )

    def job_execution_start(
        self,
        job_id: str,
        job_name: str | None,
        scheduled_time: str | None = None,
    ) -> None:
        """Log job execution start at DEBUG level."""
        self.logger.debug(
            "Job execution started",
            extra={
                "job_id": job_id,
                "job_name": job_name,
                "scheduled_time": scheduled_time,
            },
        )

    def job_execution_success(
        self,
        job_id: str,
        job_name: str | None,
        duration_ms: float,
        result: Any = None,
    ) -> None:
        """Log job execution success at INFO level."""
        self.logger.info(
            "Job execution completed",
            extra={
                "job_id": job_id,
                "job_name": job_name,
                "duration_ms": round(duration_ms, 2),
                "success": True,
                "result": str(result)[:200] if result else None,
            },
        )

    def job_execution_error(
        self,
        job_id: str,
        job_name: str | None,
        duration_ms: float,
        error: str,
        error_type: str,
    ) -> None:
        """Log job execution error at ERROR level."""
        self.logger.error(
            "Job execution failed",
            extra={
                "job_id": job_id,
                "job_name": job_name,
                "duration_ms": round(duration_ms, 2),
                "success": False,
                "error": error,
                "error_type": error_type,
            },
        )

    def job_missed(
        self,
        job_id: str,
        job_name: str | None,
        scheduled_time: str,
        misfire_grace_time: int,
    ) -> None:
        """Log missed job execution at WARNING level."""
        self.logger.warning(
            "Job execution missed",
            extra={
                "job_id": job_id,
                "job_name": job_name,
                "scheduled_time": scheduled_time,
                "misfire_grace_time": misfire_grace_time,
            },
        )

    def job_max_instances_reached(
        self,
        job_id: str,
        job_name: str | None,
        max_instances: int,
    ) -> None:
        """Log when job max instances reached at WARNING level."""
        self.logger.warning(
            "Job max instances reached, skipping execution",
            extra={
                "job_id": job_id,
                "job_name": job_name,
                "max_instances": max_instances,
            },
        )

    def jobstore_operation(
        self,
        operation: str,
        store_name: str,
        job_id: str | None = None,
        success: bool = True,
        duration_ms: float | None = None,
    ) -> None:
        """Log job store operation at DEBUG level."""
        level = logging.DEBUG if success else logging.WARNING
        self.logger.log(
            level,
            f"Job store operation: {operation}",
            extra={
                "operation": operation,
                "store_name": store_name,
                "job_id": job_id,
                "success": success,
                "duration_ms": round(duration_ms, 2) if duration_ms else None,
            },
        )

    def jobstore_connection_error(
        self,
        store_name: str,
        error: str,
        error_type: str,
        connection_string: str | None = None,
    ) -> None:
        """Log job store connection error at ERROR level."""
        self.logger.error(
            "Job store connection failed",
            extra={
                "store_name": store_name,
                "error": error,
                "error_type": error_type,
                "connection_string": (
                    mask_connection_string(connection_string)
                    if connection_string
                    else None
                ),
            },
        )

    def slow_job_execution(
        self,
        job_id: str,
        job_name: str | None,
        duration_ms: float,
        threshold_ms: int = 1000,
    ) -> None:
        """Log slow job execution at WARNING level."""
        self.logger.warning(
            "Slow job execution detected",
            extra={
                "job_id": job_id,
                "job_name": job_name,
                "duration_ms": round(duration_ms, 2),
                "threshold_ms": threshold_ms,
            },
        )

    def scheduler_not_available(self, operation: str, reason: str) -> None:
        """Log scheduler unavailable at WARNING level."""
        self.logger.warning(
            "Scheduler not available",
            extra={
                "operation": operation,
                "reason": reason,
            },
        )


# Singleton scheduler logger
scheduler_logger = SchedulerLogger()


class KeywordsEverywhereLogger:
    """Logger for Keywords Everywhere API operations with required error logging.

    Logs all outbound API calls with endpoint, method, timing.
    Logs request/response bodies at DEBUG level (truncate large responses).
    Handles timeouts, rate limits (429), auth failures (401/403).
    Includes retry attempt number in logs.
    Masks API keys in all logs.
    Logs circuit breaker state changes.
    Logs credit usage for quota tracking.
    """

    def __init__(self) -> None:
        self.logger = get_logger("keywords_everywhere")

    def api_call_start(
        self,
        endpoint: str,
        keyword_count: int,
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log outbound API call start at DEBUG level."""
        self.logger.debug(
            f"Keywords Everywhere API call: {endpoint}",
            extra={
                "endpoint": endpoint,
                "keyword_count": keyword_count,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
            },
        )

    def api_call_success(
        self,
        endpoint: str,
        duration_ms: float,
        keyword_count: int,
        credits_used: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log successful API call at DEBUG level."""
        self.logger.debug(
            f"Keywords Everywhere API call completed: {endpoint}",
            extra={
                "endpoint": endpoint,
                "duration_ms": round(duration_ms, 2),
                "keyword_count": keyword_count,
                "credits_used": credits_used,
                "request_id": request_id,
                "success": True,
            },
        )

    def api_call_error(
        self,
        endpoint: str,
        duration_ms: float,
        status_code: int | None,
        error: str,
        error_type: str,
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log failed API call at WARNING or ERROR level based on status."""
        # 4xx at WARNING, 5xx and others at ERROR
        level = logging.WARNING if status_code and 400 <= status_code < 500 else logging.ERROR
        self.logger.log(
            level,
            f"Keywords Everywhere API call failed: {endpoint}",
            extra={
                "endpoint": endpoint,
                "duration_ms": round(duration_ms, 2),
                "status_code": status_code,
                "error": error,
                "error_type": error_type,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
                "success": False,
            },
        )

    def timeout(self, endpoint: str, timeout_seconds: float) -> None:
        """Log request timeout at WARNING level."""
        self.logger.warning(
            "Keywords Everywhere API request timeout",
            extra={
                "endpoint": endpoint,
                "timeout_seconds": timeout_seconds,
            },
        )

    def rate_limit(
        self,
        endpoint: str,
        retry_after: float | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log rate limit (429) at WARNING level."""
        self.logger.warning(
            "Keywords Everywhere API rate limit hit (429)",
            extra={
                "endpoint": endpoint,
                "retry_after_seconds": retry_after,
                "request_id": request_id,
            },
        )

    def auth_failure(self, status_code: int) -> None:
        """Log authentication failure (401/403) at WARNING level."""
        self.logger.warning(
            f"Keywords Everywhere API authentication failed ({status_code})",
            extra={
                "status_code": status_code,
            },
        )

    def request_body(
        self,
        endpoint: str,
        keywords: list[str],
        country: str,
        data_source: str,
    ) -> None:
        """Log request body at DEBUG level (truncate large values)."""
        # Show first 10 keywords for logging
        keywords_preview = keywords[:10]
        if len(keywords) > 10:
            keywords_preview_str = f"{keywords_preview}... ({len(keywords)} total)"
        else:
            keywords_preview_str = str(keywords_preview)

        self.logger.debug(
            "Keywords Everywhere API request body",
            extra={
                "endpoint": endpoint,
                "keywords": keywords_preview_str,
                "keyword_count": len(keywords),
                "country": country,
                "data_source": data_source,
            },
        )

    def response_body(
        self,
        endpoint: str,
        keyword_count: int,
        duration_ms: float,
        credits_used: int | None = None,
    ) -> None:
        """Log response body at DEBUG level."""
        self.logger.debug(
            "Keywords Everywhere API response body",
            extra={
                "endpoint": endpoint,
                "keyword_count": keyword_count,
                "duration_ms": round(duration_ms, 2),
                "credits_used": credits_used,
            },
        )

    def credit_usage(
        self,
        credits_used: int,
        credits_remaining: int | None = None,
    ) -> None:
        """Log API credit usage at INFO level."""
        self.logger.info(
            "Keywords Everywhere API credit usage",
            extra={
                "credits_used": credits_used,
                "credits_remaining": credits_remaining,
            },
        )

    def circuit_state_change(
        self, previous_state: str, new_state: str, failure_count: int
    ) -> None:
        """Log circuit breaker state change at WARNING level."""
        self.logger.warning(
            "Keywords Everywhere circuit breaker state changed",
            extra={
                "previous_state": previous_state,
                "new_state": new_state,
                "failure_count": failure_count,
            },
        )

    def circuit_open(self, failure_count: int, recovery_timeout: float) -> None:
        """Log circuit breaker opening at ERROR level."""
        self.logger.error(
            "Keywords Everywhere circuit breaker opened - API calls disabled",
            extra={
                "failure_count": failure_count,
                "recovery_timeout_seconds": recovery_timeout,
            },
        )

    def circuit_recovery_attempt(self) -> None:
        """Log circuit breaker recovery attempt at INFO level."""
        self.logger.info("Keywords Everywhere circuit breaker attempting recovery")

    def circuit_closed(self) -> None:
        """Log circuit breaker closing at INFO level."""
        self.logger.info("Keywords Everywhere circuit breaker closed - API calls restored")

    def graceful_fallback(self, operation: str, reason: str) -> None:
        """Log graceful fallback when Keywords Everywhere is unavailable."""
        self.logger.info(
            "Keywords Everywhere unavailable, using fallback",
            extra={
                "operation": operation,
                "reason": reason,
            },
        )

    def keyword_lookup_start(self, keyword_count: int, country: str) -> None:
        """Log keyword lookup operation start at INFO level."""
        self.logger.info(
            "Starting keyword data lookup",
            extra={
                "keyword_count": keyword_count,
                "country": country,
            },
        )

    def keyword_lookup_complete(
        self,
        keyword_count: int,
        duration_ms: float,
        success: bool,
        results_count: int = 0,
    ) -> None:
        """Log keyword lookup operation completion."""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            "Keyword lookup completed" if success else "Keyword lookup failed",
            extra={
                "keyword_count": keyword_count,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "results_count": results_count,
            },
        )

    def batch_start(
        self,
        batch_index: int,
        batch_size: int,
        total_batches: int,
        total_keywords: int,
    ) -> None:
        """Log batch processing start at DEBUG level."""
        self.logger.debug(
            f"Starting keyword batch {batch_index + 1}/{total_batches}",
            extra={
                "batch_index": batch_index,
                "batch_size": batch_size,
                "total_batches": total_batches,
                "total_keywords": total_keywords,
            },
        )

    def batch_complete(
        self,
        batch_index: int,
        batch_size: int,
        total_batches: int,
        success_count: int,
        duration_ms: float,
        credits_used: int | None = None,
    ) -> None:
        """Log batch processing completion at INFO level."""
        self.logger.info(
            f"Keyword batch {batch_index + 1}/{total_batches} complete",
            extra={
                "batch_index": batch_index,
                "batch_size": batch_size,
                "total_batches": total_batches,
                "success_count": success_count,
                "duration_ms": round(duration_ms, 2),
                "credits_used": credits_used,
            },
        )


# Singleton Keywords Everywhere logger
keywords_everywhere_logger = KeywordsEverywhereLogger()


class DataForSEOLogger:
    """Logger for DataForSEO API operations with required error logging.

    Logs all outbound API calls with endpoint, method, timing.
    Logs request/response bodies at DEBUG level (truncate large responses).
    Handles timeouts, rate limits (429), auth failures (401/403).
    Includes retry attempt number in logs.
    Masks API credentials in all logs.
    Logs circuit breaker state changes.
    Logs credit/cost usage for quota tracking.
    """

    def __init__(self) -> None:
        self.logger = get_logger("dataforseo")

    def api_call_start(
        self,
        endpoint: str,
        method: str = "POST",
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log outbound API call start at DEBUG level."""
        self.logger.debug(
            f"DataForSEO API call: {method} {endpoint}",
            extra={
                "endpoint": endpoint,
                "method": method,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
            },
        )

    def api_call_success(
        self,
        endpoint: str,
        duration_ms: float,
        method: str = "POST",
        cost: float | None = None,
        tasks_count: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log successful API call at DEBUG level."""
        self.logger.debug(
            f"DataForSEO API call completed: {method} {endpoint}",
            extra={
                "endpoint": endpoint,
                "method": method,
                "duration_ms": round(duration_ms, 2),
                "cost": cost,
                "tasks_count": tasks_count,
                "request_id": request_id,
                "success": True,
            },
        )

    def api_call_error(
        self,
        endpoint: str,
        duration_ms: float,
        status_code: int | None,
        error: str,
        error_type: str,
        method: str = "POST",
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log failed API call at WARNING or ERROR level based on status."""
        # 4xx at WARNING, 5xx and others at ERROR
        level = logging.WARNING if status_code and 400 <= status_code < 500 else logging.ERROR
        self.logger.log(
            level,
            f"DataForSEO API call failed: {method} {endpoint}",
            extra={
                "endpoint": endpoint,
                "method": method,
                "duration_ms": round(duration_ms, 2),
                "status_code": status_code,
                "error": error,
                "error_type": error_type,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
                "success": False,
            },
        )

    def timeout(self, endpoint: str, timeout_seconds: float) -> None:
        """Log request timeout at WARNING level."""
        self.logger.warning(
            "DataForSEO API request timeout",
            extra={
                "endpoint": endpoint,
                "timeout_seconds": timeout_seconds,
            },
        )

    def rate_limit(
        self,
        endpoint: str,
        retry_after: float | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log rate limit (429) at WARNING level."""
        self.logger.warning(
            "DataForSEO API rate limit hit (429)",
            extra={
                "endpoint": endpoint,
                "retry_after_seconds": retry_after,
                "request_id": request_id,
            },
        )

    def auth_failure(self, status_code: int) -> None:
        """Log authentication failure (401/403) at WARNING level."""
        self.logger.warning(
            f"DataForSEO API authentication failed ({status_code})",
            extra={
                "status_code": status_code,
            },
        )

    def request_body(
        self,
        endpoint: str,
        body: dict[str, Any] | list[dict[str, Any]],
    ) -> None:
        """Log request body at DEBUG level (truncate large values)."""
        truncated_body = self._truncate_body(body)
        self.logger.debug(
            "DataForSEO API request body",
            extra={
                "endpoint": endpoint,
                "request_body": truncated_body,
            },
        )

    def response_body(
        self,
        endpoint: str,
        body: dict[str, Any],
        duration_ms: float,
        cost: float | None = None,
    ) -> None:
        """Log response body at DEBUG level (truncate large values)."""
        truncated_body = self._truncate_body(body)
        self.logger.debug(
            "DataForSEO API response body",
            extra={
                "endpoint": endpoint,
                "response_body": truncated_body,
                "duration_ms": round(duration_ms, 2),
                "cost": cost,
            },
        )

    def _truncate_body(
        self, body: dict[str, Any] | list[Any], max_length: int = 500
    ) -> dict[str, Any] | list[Any] | str:
        """Truncate large values in body for logging."""
        if isinstance(body, list):
            if len(body) > 10:
                return f"[list with {len(body)} items]"
            return [self._truncate_body(item, max_length) for item in body[:10]]

        if isinstance(body, dict):
            result: dict[str, Any] = {}
            for key, value in body.items():
                if isinstance(value, str) and len(value) > max_length:
                    result[key] = value[:max_length] + f"... (truncated, {len(value)} chars)"
                elif isinstance(value, dict):
                    result[key] = self._truncate_body(value, max_length)
                elif isinstance(value, list) and len(value) > 10:
                    result[key] = f"[list with {len(value)} items]"
                else:
                    result[key] = value
            return result

        return body

    def cost_usage(
        self,
        cost: float,
        endpoint: str | None = None,
    ) -> None:
        """Log API cost usage at INFO level."""
        self.logger.info(
            "DataForSEO API cost usage",
            extra={
                "cost": cost,
                "endpoint": endpoint,
            },
        )

    def circuit_state_change(
        self, previous_state: str, new_state: str, failure_count: int
    ) -> None:
        """Log circuit breaker state change at WARNING level."""
        self.logger.warning(
            "DataForSEO circuit breaker state changed",
            extra={
                "previous_state": previous_state,
                "new_state": new_state,
                "failure_count": failure_count,
            },
        )

    def circuit_open(self, failure_count: int, recovery_timeout: float) -> None:
        """Log circuit breaker opening at ERROR level."""
        self.logger.error(
            "DataForSEO circuit breaker opened - API calls disabled",
            extra={
                "failure_count": failure_count,
                "recovery_timeout_seconds": recovery_timeout,
            },
        )

    def circuit_recovery_attempt(self) -> None:
        """Log circuit breaker recovery attempt at INFO level."""
        self.logger.info("DataForSEO circuit breaker attempting recovery")

    def circuit_closed(self) -> None:
        """Log circuit breaker closing at INFO level."""
        self.logger.info("DataForSEO circuit breaker closed - API calls restored")

    def graceful_fallback(self, operation: str, reason: str) -> None:
        """Log graceful fallback when DataForSEO is unavailable."""
        self.logger.info(
            "DataForSEO unavailable, using fallback",
            extra={
                "operation": operation,
                "reason": reason,
            },
        )

    def keyword_search_start(
        self,
        keywords: list[str],
        location_code: int,
    ) -> None:
        """Log keyword search operation start at INFO level."""
        keywords_preview = keywords[:5]
        if len(keywords) > 5:
            keywords_str = f"{keywords_preview}... ({len(keywords)} total)"
        else:
            keywords_str = str(keywords_preview)
        self.logger.info(
            "Starting DataForSEO keyword search",
            extra={
                "keywords": keywords_str,
                "keyword_count": len(keywords),
                "location_code": location_code,
            },
        )

    def keyword_search_complete(
        self,
        keyword_count: int,
        duration_ms: float,
        success: bool,
        results_count: int = 0,
        cost: float | None = None,
    ) -> None:
        """Log keyword search operation completion."""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            "DataForSEO keyword search completed" if success else "DataForSEO keyword search failed",
            extra={
                "keyword_count": keyword_count,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "results_count": results_count,
                "cost": cost,
            },
        )

    def serp_search_start(
        self,
        keyword: str,
        location_code: int,
        search_engine: str = "google",
    ) -> None:
        """Log SERP search operation start at INFO level."""
        self.logger.info(
            "Starting DataForSEO SERP search",
            extra={
                "keyword": keyword[:100],
                "location_code": location_code,
                "search_engine": search_engine,
            },
        )

    def serp_search_complete(
        self,
        keyword: str,
        duration_ms: float,
        success: bool,
        results_count: int = 0,
        cost: float | None = None,
    ) -> None:
        """Log SERP search operation completion."""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            "DataForSEO SERP search completed" if success else "DataForSEO SERP search failed",
            extra={
                "keyword": keyword[:100],
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "results_count": results_count,
                "cost": cost,
            },
        )

    def batch_start(
        self,
        batch_index: int,
        batch_size: int,
        total_batches: int,
        total_items: int,
        operation: str = "keyword_search",
    ) -> None:
        """Log batch processing start at DEBUG level."""
        self.logger.debug(
            f"Starting DataForSEO batch {batch_index + 1}/{total_batches}",
            extra={
                "batch_index": batch_index,
                "batch_size": batch_size,
                "total_batches": total_batches,
                "total_items": total_items,
                "operation": operation,
            },
        )

    def batch_complete(
        self,
        batch_index: int,
        batch_size: int,
        total_batches: int,
        success_count: int,
        duration_ms: float,
        cost: float | None = None,
        operation: str = "keyword_search",
    ) -> None:
        """Log batch processing completion at INFO level."""
        self.logger.info(
            f"DataForSEO batch {batch_index + 1}/{total_batches} complete",
            extra={
                "batch_index": batch_index,
                "batch_size": batch_size,
                "total_batches": total_batches,
                "success_count": success_count,
                "duration_ms": round(duration_ms, 2),
                "cost": cost,
                "operation": operation,
            },
        )


# Singleton DataForSEO logger
dataforseo_logger = DataForSEOLogger()


class GoogleNLPLogger:
    """Logger for Google Cloud NLP API operations with required error logging.

    Logs all outbound API calls with endpoint, method, timing.
    Logs request/response bodies at DEBUG level (truncate large responses).
    Handles timeouts, rate limits (429), auth failures (401/403).
    Includes retry attempt number in logs.
    Masks API keys in all logs.
    Logs circuit breaker state changes.
    """

    def __init__(self) -> None:
        self.logger = get_logger("google_nlp")

    def api_call_start(
        self,
        endpoint: str,
        text_length: int,
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log outbound API call start at DEBUG level."""
        self.logger.debug(
            f"Google Cloud NLP API call: {endpoint}",
            extra={
                "endpoint": endpoint,
                "text_length": text_length,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
            },
        )

    def api_call_success(
        self,
        endpoint: str,
        duration_ms: float,
        entity_count: int | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log successful API call at DEBUG level."""
        self.logger.debug(
            f"Google Cloud NLP API call completed: {endpoint}",
            extra={
                "endpoint": endpoint,
                "duration_ms": round(duration_ms, 2),
                "entity_count": entity_count,
                "request_id": request_id,
                "success": True,
            },
        )

    def api_call_error(
        self,
        endpoint: str,
        duration_ms: float,
        status_code: int | None,
        error: str,
        error_type: str,
        retry_attempt: int = 0,
        request_id: str | None = None,
    ) -> None:
        """Log failed API call at WARNING or ERROR level based on status."""
        # 4xx at WARNING, 5xx and others at ERROR
        level = logging.WARNING if status_code and 400 <= status_code < 500 else logging.ERROR
        self.logger.log(
            level,
            f"Google Cloud NLP API call failed: {endpoint}",
            extra={
                "endpoint": endpoint,
                "duration_ms": round(duration_ms, 2),
                "status_code": status_code,
                "error": error,
                "error_type": error_type,
                "retry_attempt": retry_attempt,
                "request_id": request_id,
                "success": False,
            },
        )

    def timeout(self, endpoint: str, timeout_seconds: float) -> None:
        """Log request timeout at WARNING level."""
        self.logger.warning(
            "Google Cloud NLP API request timeout",
            extra={
                "endpoint": endpoint,
                "timeout_seconds": timeout_seconds,
            },
        )

    def rate_limit(
        self,
        endpoint: str,
        retry_after: float | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log rate limit (429) at WARNING level."""
        self.logger.warning(
            "Google Cloud NLP API rate limit hit (429)",
            extra={
                "endpoint": endpoint,
                "retry_after_seconds": retry_after,
                "request_id": request_id,
            },
        )

    def auth_failure(self, status_code: int) -> None:
        """Log authentication failure (401/403) at WARNING level."""
        self.logger.warning(
            f"Google Cloud NLP API authentication failed ({status_code})",
            extra={
                "status_code": status_code,
            },
        )

    def request_body(
        self,
        endpoint: str,
        text: str,
        encoding_type: str | None = None,
    ) -> None:
        """Log request body at DEBUG level (truncate large values)."""
        self.logger.debug(
            "Google Cloud NLP API request body",
            extra={
                "endpoint": endpoint,
                "text": self._truncate_text(text, 500),
                "text_length": len(text),
                "encoding_type": encoding_type,
            },
        )

    def response_body(
        self,
        endpoint: str,
        entity_count: int,
        duration_ms: float,
    ) -> None:
        """Log response body at DEBUG level."""
        self.logger.debug(
            "Google Cloud NLP API response body",
            extra={
                "endpoint": endpoint,
                "entity_count": entity_count,
                "duration_ms": round(duration_ms, 2),
            },
        )

    def _truncate_text(self, text: str, max_length: int = 500) -> str:
        """Truncate text for logging."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + f"... (truncated, {len(text)} chars)"

    def quota_usage(
        self,
        units_used: int | None = None,
        endpoint: str | None = None,
    ) -> None:
        """Log API quota usage at INFO level."""
        self.logger.info(
            "Google Cloud NLP API quota usage",
            extra={
                "units_used": units_used,
                "endpoint": endpoint,
            },
        )

    def circuit_state_change(
        self, previous_state: str, new_state: str, failure_count: int
    ) -> None:
        """Log circuit breaker state change at WARNING level."""
        self.logger.warning(
            "Google Cloud NLP circuit breaker state changed",
            extra={
                "previous_state": previous_state,
                "new_state": new_state,
                "failure_count": failure_count,
            },
        )

    def circuit_open(self, failure_count: int, recovery_timeout: float) -> None:
        """Log circuit breaker opening at ERROR level."""
        self.logger.error(
            "Google Cloud NLP circuit breaker opened - API calls disabled",
            extra={
                "failure_count": failure_count,
                "recovery_timeout_seconds": recovery_timeout,
            },
        )

    def circuit_recovery_attempt(self) -> None:
        """Log circuit breaker recovery attempt at INFO level."""
        self.logger.info("Google Cloud NLP circuit breaker attempting recovery")

    def circuit_closed(self) -> None:
        """Log circuit breaker closing at INFO level."""
        self.logger.info("Google Cloud NLP circuit breaker closed - API calls restored")

    def graceful_fallback(self, operation: str, reason: str) -> None:
        """Log graceful fallback when Google Cloud NLP is unavailable."""
        self.logger.info(
            "Google Cloud NLP unavailable, using fallback",
            extra={
                "operation": operation,
                "reason": reason,
            },
        )

    def entity_extraction_start(self, text_length: int) -> None:
        """Log entity extraction operation start at INFO level."""
        self.logger.info(
            "Starting entity extraction",
            extra={
                "text_length": text_length,
            },
        )

    def entity_extraction_complete(
        self,
        text_length: int,
        duration_ms: float,
        success: bool,
        entity_count: int = 0,
    ) -> None:
        """Log entity extraction operation completion."""
        level = logging.INFO if success else logging.WARNING
        self.logger.log(
            level,
            "Entity extraction completed" if success else "Entity extraction failed",
            extra={
                "text_length": text_length,
                "duration_ms": round(duration_ms, 2),
                "success": success,
                "entity_count": entity_count,
            },
        )

    def batch_start(
        self,
        batch_index: int,
        batch_size: int,
        total_batches: int,
        total_texts: int,
    ) -> None:
        """Log batch processing start at DEBUG level."""
        self.logger.debug(
            f"Starting entity extraction batch {batch_index + 1}/{total_batches}",
            extra={
                "batch_index": batch_index,
                "batch_size": batch_size,
                "total_batches": total_batches,
                "total_texts": total_texts,
            },
        )

    def batch_complete(
        self,
        batch_index: int,
        batch_size: int,
        total_batches: int,
        success_count: int,
        failure_count: int,
        duration_ms: float,
        total_entities: int = 0,
    ) -> None:
        """Log batch processing completion at INFO level."""
        self.logger.info(
            f"Entity extraction batch {batch_index + 1}/{total_batches} complete",
            extra={
                "batch_index": batch_index,
                "batch_size": batch_size,
                "total_batches": total_batches,
                "success_count": success_count,
                "failure_count": failure_count,
                "duration_ms": round(duration_ms, 2),
                "total_entities": total_entities,
            },
        )

    def batch_error(
        self,
        batch_index: int,
        total_batches: int,
        error: str,
        error_type: str,
        duration_ms: float,
    ) -> None:
        """Log batch processing error at ERROR level."""
        self.logger.error(
            f"Entity extraction batch {batch_index + 1}/{total_batches} failed",
            extra={
                "batch_index": batch_index,
                "total_batches": total_batches,
                "error": error,
                "error_type": error_type,
                "duration_ms": round(duration_ms, 2),
            },
        )


# Singleton Google Cloud NLP logger
google_nlp_logger = GoogleNLPLogger()
