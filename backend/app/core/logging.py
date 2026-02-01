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


class CustomJsonFormatter(jsonlogger.JsonFormatter):
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
