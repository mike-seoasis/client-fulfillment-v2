"""FastAPI application entry point.

Railway Deployment Requirements:
- Binds to PORT from environment variable
- Health endpoint at /health for Railway health checks
- Graceful shutdown with SIGTERM handling
- All logs to stdout/stderr

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level
"""

import asyncio
import logging
import signal
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import router as api_v1_router
from app.core.config import get_settings
from app.core.database import db_manager
from app.core.logging import get_logger, setup_logging
from app.core.redis import redis_manager
from app.core.scheduler import scheduler_manager
from app.core.websocket import connection_manager

# Set up logging before anything else
setup_logging()
logger = get_logger(__name__)

# Sensitive fields to redact from request body logs
SENSITIVE_FIELDS = {
    "password",
    "token",
    "secret",
    "api_key",
    "authorization",
    "credit_card",
}


def sanitize_body(body: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from request body for logging."""
    if not isinstance(body, dict):
        return body
    sanitized: dict[str, Any] = {}
    for key, value in body.items():
        if key.lower() in SENSITIVE_FIELDS:
            sanitized[key] = "****"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_body(value)
        else:
            sanitized[key] = value
    return sanitized


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests with timing and request_id."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.monotonic()
        method = request.method
        path = request.url.path

        # Log incoming request
        logger.info(
            "Request started",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "query_params": str(request.query_params)
                if request.query_params
                else None,
            },
        )

        # Log request body at DEBUG level (for non-GET requests)
        if method not in ("GET", "HEAD", "OPTIONS") and logger.isEnabledFor(
            logging.DEBUG
        ):
            try:
                body = await request.body()
                if body:
                    import json

                    try:
                        body_json = json.loads(body)
                        sanitized = sanitize_body(body_json)
                        logger.debug(
                            "Request body",
                            extra={"request_id": request_id, "body": sanitized},
                        )
                    except json.JSONDecodeError:
                        logger.debug(
                            "Request body (non-JSON)",
                            extra={"request_id": request_id, "body_length": len(body)},
                        )
            except Exception:
                pass  # Don't fail on body logging errors

        # Process request
        response = await call_next(request)

        # Calculate timing
        duration_ms = (time.monotonic() - start_time) * 1000
        status_code = response.status_code

        # Add request_id to response headers
        response.headers["X-Request-ID"] = request_id

        # Determine log level based on status code
        log_extra = {
            "request_id": request_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        }

        if status_code >= 500:
            logger.error("Request failed", extra=log_extra)
        elif status_code >= 400:
            logger.warning("Request error", extra=log_extra)
        else:
            logger.info("Request completed", extra=log_extra)

        return response


def log_rate_limit_hit(
    request_id: str, path: str, client_ip: str | None = None
) -> None:
    """Log rate limit hits at WARNING level.

    Call this from rate limiting middleware/dependencies when a limit is hit.
    """
    logger.warning(
        "Rate limit exceeded",
        extra={
            "request_id": request_id,
            "path": path,
            "client_ip": client_ip,
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan manager for startup/shutdown.

    Handles:
    - Database initialization
    - Graceful shutdown on SIGTERM
    """
    settings = get_settings()
    logger.info(
        "Starting application",
        extra={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
        },
    )

    # Initialize database
    try:
        db_manager.init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    # Initialize Redis (optional - app works without it)
    redis_available = await redis_manager.init_redis()
    if redis_available:
        logger.info("Redis initialized")
    else:
        logger.info("Redis not available, caching disabled")

    # Start WebSocket heartbeat task
    await connection_manager.start_heartbeat()
    logger.info("WebSocket heartbeat task started")

    # Initialize and start scheduler
    if scheduler_manager.init_scheduler():
        if scheduler_manager.start():
            logger.info("Scheduler started")
        else:
            logger.warning("Failed to start scheduler")
    else:
        logger.info("Scheduler not initialized (disabled or error)")

    # Set up graceful shutdown handler
    shutdown_event = asyncio.Event()

    def handle_sigterm(*args: Any) -> None:
        logger.info("Received SIGTERM, initiating graceful shutdown")
        shutdown_event.set()

    # Register signal handlers (only in main thread)
    try:
        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)
    except ValueError:
        # Signal handling not available (e.g., not in main thread)
        pass

    yield

    # Shutdown
    logger.info("Shutting down application")

    # Stop scheduler first (allows running jobs to complete)
    scheduler_manager.stop(wait=True)
    logger.info("Scheduler stopped")

    # Notify WebSocket clients and stop heartbeat
    await connection_manager.broadcast_shutdown(reason="server_shutdown")
    await connection_manager.stop_heartbeat()
    logger.info("WebSocket connections closed")

    await redis_manager.close()
    await db_manager.close()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Request logging middleware (added first, runs last)
    app.add_middleware(RequestLoggingMiddleware)

    # CORS middleware - use FRONTEND_URL for production, allow all origins otherwise
    cors_origins: list[str] = ["*"]
    if settings.frontend_url:
        cors_origins = [settings.frontend_url]
        logger.info(
            "CORS configured for production",
            extra={"allowed_origins": cors_origins},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers for structured error responses
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle validation errors with structured response."""
        request_id = getattr(request.state, "request_id", "unknown")
        errors = exc.errors()
        error_msg = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors
        )
        logger.warning(
            "Validation error",
            extra={
                "request_id": request_id,
                "errors": errors,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": error_msg,
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )

    @app.exception_handler(status.HTTP_429_TOO_MANY_REQUESTS)
    async def rate_limit_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle rate limit errors with structured response."""
        request_id = getattr(request.state, "request_id", "unknown")
        log_rate_limit_hit(
            request_id,
            request.url.path,
            request.client.host if request.client else None,
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Too many requests. Please try again later.",
                "code": "RATE_LIMIT_EXCEEDED",
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Handle unexpected errors with structured response."""
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled exception",
            extra={
                "request_id": request_id,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "An internal error occurred. Please try again later.",
                "code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
        )

    # Health check endpoint for Railway
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, str]:
        """Health check endpoint for Railway.

        Returns {"status": "ok"} if the service is running.
        """
        return {"status": "ok"}

    # Database health check
    @app.get("/health/db", tags=["Health"])
    async def database_health() -> dict[str, str | bool]:
        """Check database connectivity."""
        is_healthy = await db_manager.check_connection()
        return {
            "status": "ok" if is_healthy else "error",
            "database": is_healthy,
        }

    # Redis health check
    @app.get("/health/redis", tags=["Health"])
    async def redis_health() -> dict[str, str | bool]:
        """Check Redis connectivity."""
        is_healthy = await redis_manager.check_health()
        circuit_state = (
            redis_manager.circuit_breaker.state.value
            if redis_manager.circuit_breaker
            else "not_initialized"
        )
        return {
            "status": "ok" if is_healthy else "unavailable",
            "redis": is_healthy,
            "circuit_breaker": circuit_state,
        }

    # Scheduler health check
    @app.get("/health/scheduler", tags=["Health"])
    async def scheduler_health() -> dict[str, Any]:
        """Check scheduler status."""
        health = scheduler_manager.check_health()
        return health

    # Include API routers
    app.include_router(api_v1_router)

    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
