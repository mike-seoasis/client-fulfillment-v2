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
from app.api.v1.reddit import webhook_router
from app.core.config import get_settings
from app.core.database import db_manager
from app.core.logging import get_logger, setup_logging
from app.core.redis import redis_manager
from app.core.scheduler import scheduler_manager
from app.core.websocket import connection_manager
from app.integrations.claude import init_claude
from app.integrations.crowdreply import close_crowdreply, init_crowdreply
from app.integrations.perplexity import init_perplexity
from app.integrations.serpapi import close_serpapi, init_serpapi

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

    # Initialize external API clients
    claude_client = await init_claude()
    if claude_client.available:
        logger.info("Claude client initialized", extra={"model": claude_client.model})
    else:
        logger.warning("Claude not configured (missing ANTHROPIC_API_KEY)")

    perplexity_client = await init_perplexity()
    if perplexity_client.available:
        logger.info("Perplexity client initialized", extra={"model": perplexity_client.model})
    else:
        logger.warning("Perplexity not configured (missing PERPLEXITY_API_KEY)")

    serpapi_client = await init_serpapi()
    if serpapi_client.available:
        logger.info("SerpAPI client initialized")
    else:
        logger.warning("SerpAPI not configured (missing SERPAPI_KEY)")

    crowdreply_client = await init_crowdreply()
    is_mock = hasattr(crowdreply_client, "_task_counter")
    if is_mock:
        logger.info("CrowdReply mock client initialized")
    elif crowdreply_client.available:
        logger.info(
            "CrowdReply client initialized",
            extra={"dry_run": crowdreply_client.dry_run},
        )
    else:
        logger.warning("CrowdReply not configured (missing CROWDREPLY_API_KEY)")

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

    await close_crowdreply()
    await close_serpapi()
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
        expose_headers=["Content-Disposition"],
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

    # Integrations health check
    @app.get("/health/integrations", tags=["Health"])
    async def integrations_health() -> dict[str, Any]:
        """Check status of external integrations (POP, DataForSEO, Claude)."""
        from app.core.config import get_settings
        from app.integrations.pop import get_pop_client, POPMockClient

        settings = get_settings()
        pop_client = await get_pop_client()
        is_mock = isinstance(pop_client, POPMockClient)

        return {
            "pop": {
                "mock_mode": settings.pop_use_mock,
                "is_mock_client": is_mock,
                "api_key_set": bool(settings.pop_api_key),
                "available": getattr(pop_client, "available", False) if not is_mock else True,
                "circuit_breaker": getattr(pop_client, "_circuit_breaker", None).state.value if hasattr(pop_client, "_circuit_breaker") else "n/a",
            },
            "dataforseo": {
                "login_set": bool(settings.dataforseo_api_login),
                "password_set": bool(settings.dataforseo_api_password),
            },
            "claude": {
                "api_key_set": bool(settings.anthropic_api_key),
                "model": settings.claude_model,
            },
        }

    # POP full 3-step flow test
    @app.get("/health/pop-test", tags=["Health"])
    async def pop_full_test() -> dict[str, Any]:
        """Run the full 3-step POP flow and report each step's result."""
        from app.integrations.pop import get_pop_client, POPMockClient, POPTaskStatus

        pop_client = await get_pop_client()

        if isinstance(pop_client, POPMockClient):
            return {"status": "skipped", "reason": "Using mock client"}

        if not pop_client.available:
            return {"status": "error", "reason": "POP client not available (missing API key)"}

        steps: dict[str, Any] = {}

        # --- Step 1: get-terms ---
        try:
            task_result = await pop_client.create_report_task(
                keyword="pet wellness supplements",
                url="https://www.example.com/pet-wellness",
            )
            if not task_result.success or not task_result.task_id:
                steps["step1_create"] = {"success": False, "error": task_result.error}
                return {"steps": steps}

            steps["step1_create"] = {"success": True, "task_id": task_result.task_id}

            poll_result = await pop_client.poll_for_result(task_result.task_id)
            response_data = dict(poll_result.data or {})
            prepare_id = response_data.get("prepareId")
            variations = response_data.get("variations", [])
            lsa_phrases = response_data.get("lsaPhrases", [])

            steps["step1_poll"] = {
                "success": poll_result.success,
                "status": poll_result.status.value if poll_result.status else None,
                "response_keys": list(response_data.keys()),
                "prepareId": prepare_id,
                "prepareId_type": type(prepare_id).__name__,
                "lsa_count": len(lsa_phrases),
                "variations_count": len(variations),
            }

            if not prepare_id:
                return {"steps": steps, "diagnosis": "No prepareId - steps 2+3 skipped"}

        except Exception as e:
            steps["step1_error"] = {"type": type(e).__name__, "message": str(e)}
            return {"steps": steps}

        # --- Step 2: create-report ---
        try:
            report_task = await pop_client.create_report(
                prepare_id=prepare_id,
                variations=variations,
                lsa_phrases=lsa_phrases,
            )

            steps["step2_create"] = {
                "success": report_task.success,
                "task_id": report_task.task_id,
                "error": report_task.error,
                "data_keys": list((report_task.data or {}).keys()),
                "reportId": (report_task.data or {}).get("reportId"),
            }

            if not report_task.success or not report_task.task_id:
                return {"steps": steps, "diagnosis": "create-report failed"}

            report_id = (report_task.data or {}).get("reportId")

            report_poll = await pop_client.poll_for_result(report_task.task_id)
            report_data = report_poll.data or {}

            steps["step2_poll"] = {
                "success": report_poll.success,
                "status": report_poll.status.value if report_poll.status else None,
                "response_keys": list(report_data.keys()),
                "has_report_key": "report" in report_data,
                "report_keys": list(report_data.get("report", {}).keys()) if isinstance(report_data.get("report"), dict) else None,
                "competitors_count": len(report_data.get("report", {}).get("competitors", [])) if isinstance(report_data.get("report"), dict) else 0,
            }

        except Exception as e:
            steps["step2_error"] = {"type": type(e).__name__, "message": str(e)}

        return {"steps": steps}

    # Project content/brief diagnostic
    @app.get("/health/project-debug/{project_id}", tags=["Health"])
    async def project_debug(project_id: str) -> dict[str, Any]:
        """Debug endpoint showing content generation state for a project."""
        from sqlalchemy import select as sa_select
        from app.models.content_brief import ContentBrief
        from app.models.crawled_page import CrawledPage
        from app.models.page_content import PageContent
        from app.models.page_keywords import PageKeywords

        async with db_manager.session_factory() as db:
            # Get all pages for project
            pages_stmt = sa_select(CrawledPage).where(CrawledPage.project_id == project_id)
            pages_result = await db.execute(pages_stmt)
            pages = list(pages_result.scalars().all())

            page_data = []
            for page in pages:
                # Get keywords
                kw_stmt = sa_select(PageKeywords).where(PageKeywords.crawled_page_id == page.id)
                kw_result = await db.execute(kw_stmt)
                kw = kw_result.scalar_one_or_none()

                # Get content
                content_stmt = sa_select(PageContent).where(PageContent.crawled_page_id == page.id)
                content_result = await db.execute(content_stmt)
                content = content_result.scalar_one_or_none()

                # Get brief
                brief_stmt = sa_select(ContentBrief).where(ContentBrief.page_id == page.id)
                brief_result = await db.execute(brief_stmt)
                brief = brief_result.scalar_one_or_none()

                # Extract raw response keys + prepareId from first brief only
                raw_keys = None
                prepare_id_value = None
                if brief and brief.raw_response and not page_data:
                    raw_keys = list(brief.raw_response.keys())
                    prepare_id_value = brief.raw_response.get("prepareId")

                page_data.append({
                    "page_id": page.id,
                    "url": page.normalized_url[:60],
                    "keyword": kw.primary_keyword if kw else None,
                    "keyword_approved": kw.is_approved if kw else False,
                    "content_status": content.status if content else None,
                    "has_brief": brief is not None,
                    "brief_lsi_count": len(brief.lsi_terms) if brief and brief.lsi_terms else 0,
                    "brief_competitors": len(brief.competitors) if brief and brief.competitors else 0,
                    "brief_pop_task_id": brief.pop_task_id[:20] if brief and brief.pop_task_id else None,
                    **({"raw_response_keys": raw_keys, "prepareId": prepare_id_value} if raw_keys is not None else {}),
                })

            return {
                "project_id": project_id,
                "total_pages": len(pages),
                "pages": page_data,
            }

    # Include API routers
    app.include_router(api_v1_router)

    # Mount webhook router directly on app (no auth required - external callbacks)
    app.include_router(webhook_router)

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
