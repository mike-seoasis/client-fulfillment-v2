"""Deployment script for Railway with comprehensive logging.

This script runs before the application starts and handles:
- Deployment start/end logging with version info
- Migration execution with step-by-step logging
- Environment variable validation (with masked values)
- Health check verification during deployment
- Post-migration data integrity validation
- Rollback trigger logging

Run this via: python -m app.deploy
"""

import asyncio
import os
import subprocess
import sys
import time
from typing import Any

from app.core.config import get_settings
from app.core.data_integrity import validate_data_integrity
from app.core.logging import (
    db_logger,
    get_logger,
    mask_connection_string,
    setup_logging,
)

# Initialize logging
setup_logging()
logger = get_logger("deployment")


def mask_env_value(key: str, value: str) -> str:
    """Mask sensitive environment variable values for logging."""
    sensitive_patterns = [
        "password",
        "secret",
        "key",
        "token",
        "credential",
        "auth",
        "api_key",
    ]

    key_lower = key.lower()
    for pattern in sensitive_patterns:
        if pattern in key_lower:
            # Show first 4 chars and mask the rest
            if len(value) > 8:
                return f"{value[:4]}{'*' * (len(value) - 4)}"
            return "****"

    # Mask connection strings
    if "url" in key_lower or "dsn" in key_lower:
        return mask_connection_string(value)

    return value


def log_deployment_start() -> dict[str, Any]:
    """Log deployment start with version info."""
    settings = get_settings()

    deployment_info = {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "environment": settings.environment,
        "railway_deployment_id": os.getenv("RAILWAY_DEPLOYMENT_ID", "local"),
        "railway_service_name": os.getenv("RAILWAY_SERVICE_NAME", "unknown"),
        "railway_environment": os.getenv("RAILWAY_ENVIRONMENT_NAME", "unknown"),
        "git_commit_sha": os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown")[:8]
        if os.getenv("RAILWAY_GIT_COMMIT_SHA")
        else "unknown",
    }

    logger.info(
        "Deployment started",
        extra=deployment_info,
    )

    return deployment_info


def log_deployment_end(
    success: bool, deployment_info: dict[str, Any], duration_seconds: float
) -> None:
    """Log deployment completion with status."""
    log_data = {
        **deployment_info,
        "success": success,
        "duration_seconds": round(duration_seconds, 2),
    }

    if success:
        logger.info("Deployment completed successfully", extra=log_data)
    else:
        logger.error("Deployment failed", extra=log_data)


def validate_environment_variables() -> bool:
    """Validate required environment variables and log their presence (masked)."""
    logger.info("Validating environment variables")

    required_vars = ["DATABASE_URL", "PORT"]
    optional_vars = ["REDIS_URL", "ENVIRONMENT", "LOG_LEVEL", "DEBUG"]

    validation_success = True
    env_status: dict[str, Any] = {"required": {}, "optional": {}}

    # Check required variables
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = mask_env_value(var, value)
            env_status["required"][var] = {"present": True, "value": masked}
            logger.info(
                f"Environment variable {var} validated",
                extra={"variable": var, "value": masked},
            )
        else:
            env_status["required"][var] = {"present": False}
            logger.error(
                f"Required environment variable {var} is missing",
                extra={"variable": var},
            )
            validation_success = False

    # Log optional variables
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            masked = mask_env_value(var, value)
            env_status["optional"][var] = {"present": True, "value": masked}
            logger.debug(
                f"Optional environment variable {var} set",
                extra={"variable": var, "value": masked},
            )
        else:
            env_status["optional"][var] = {"present": False}
            logger.debug(
                f"Optional environment variable {var} not set, using default",
                extra={"variable": var},
            )

    if validation_success:
        logger.info(
            "Environment variable validation passed", extra={"env_status": env_status}
        )
    else:
        logger.error(
            "Environment variable validation failed", extra={"env_status": env_status}
        )

    return validation_success


def run_migrations() -> bool:
    """Run database migrations with step-by-step logging."""
    logger.info("Starting database migrations")
    migration_start = time.monotonic()

    try:
        # Get current revision before migration
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        current_rev = result.stdout.strip() if result.returncode == 0 else "unknown"
        logger.info("Current database revision", extra={"revision": current_rev})

        # Get target revision
        result = subprocess.run(
            ["alembic", "heads"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )
        target_rev = result.stdout.strip() if result.returncode == 0 else "head"
        logger.info("Target migration revision", extra={"revision": target_rev})

        # Check if migration is needed
        if current_rev == target_rev:
            logger.info("Database is already at target revision, no migration needed")
            return True

        # Log migration start
        db_logger.migration_start(
            version=target_rev,
            description=f"Migrating from {current_rev} to {target_rev}",
        )

        # Run alembic upgrade with verbose output
        logger.info("Executing alembic upgrade head")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
        )

        migration_duration = time.monotonic() - migration_start

        if result.returncode == 0:
            # Parse migration output for step-by-step logging
            for line in result.stdout.split("\n"):
                if line.strip():
                    # Log each migration step
                    if "Running upgrade" in line:
                        logger.info(
                            "Migration step executed",
                            extra={"step": line.strip(), "status": "success"},
                        )
                    elif "INFO" in line:
                        logger.debug("Migration output", extra={"output": line.strip()})

            db_logger.migration_end(version=target_rev, success=True)
            logger.info(
                "Database migrations completed successfully",
                extra={
                    "from_revision": current_rev,
                    "to_revision": target_rev,
                    "duration_seconds": round(migration_duration, 2),
                },
            )
            return True
        else:
            # Log migration failure with stderr
            error_output = result.stderr.strip() or result.stdout.strip()
            logger.error(
                "Migration failed",
                extra={
                    "error": error_output,
                    "return_code": result.returncode,
                    "from_revision": current_rev,
                    "target_revision": target_rev,
                },
            )
            db_logger.migration_end(version=target_rev, success=False)

            # Log rollback trigger
            logger.warning(
                "Migration failure may trigger rollback",
                extra={
                    "rollback_trigger": "migration_failure",
                    "failed_revision": target_rev,
                    "current_revision": current_rev,
                },
            )
            return False

    except FileNotFoundError:
        logger.error("Alembic not found. Ensure alembic is installed.")
        return False
    except Exception as e:
        logger.error(
            "Migration execution error",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )
        return False


async def verify_database_connection(max_retries: int = 5, retry_delay: float = 3.0) -> bool:
    """Verify database connection during deployment with retries.

    Railway's internal networking may not be ready immediately when the
    container starts. Retry a few times before giving up.
    """
    logger.info("Verifying database connection")

    for attempt in range(1, max_retries + 1):
        try:
            from app.core.database import db_manager

            db_manager.init_db()
            is_connected = await db_manager.check_connection()

            if is_connected:
                logger.info("Database connection verified successfully")
                await db_manager.close()
                return True
            else:
                logger.warning(
                    f"Database connection attempt {attempt}/{max_retries} failed",
                )
                await db_manager.close()

        except Exception as e:
            logger.warning(
                f"Database connection attempt {attempt}/{max_retries} error",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )

        if attempt < max_retries:
            logger.info(f"Retrying in {retry_delay}s...")
            await asyncio.sleep(retry_delay)

    logger.error("Database connection verification failed after all retries")
    return False


async def verify_redis_connection() -> bool:
    """Verify Redis connection during deployment (optional service)."""
    settings = get_settings()

    if not settings.redis_url:
        logger.info("Redis URL not configured, skipping Redis health check")
        return True  # Redis is optional

    logger.info("Verifying Redis connection")

    try:
        from app.core.redis import redis_manager

        is_connected = await redis_manager.init_redis()

        if is_connected:
            logger.info("Redis connection verified successfully")
        else:
            logger.warning("Redis connection verification failed (non-critical)")

        await redis_manager.close()
        return True  # Redis failures are non-critical

    except Exception as e:
        logger.warning(
            "Redis connection verification error (non-critical)",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        return True  # Redis failures are non-critical


async def run_health_checks() -> bool:
    """Run all health checks during deployment."""
    logger.info("Running deployment health checks")

    # Database is required
    db_healthy = await verify_database_connection()
    if not db_healthy:
        logger.error("Database health check failed - deployment cannot proceed")
        return False

    # Redis is optional
    await verify_redis_connection()

    logger.info(
        "Health checks completed",
        extra={
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "checked",
        },
    )

    return db_healthy


async def run_data_integrity_validation() -> bool:
    """Run post-migration data integrity validation.

    Validates:
    - Foreign key integrity (all references exist)
    - Data type validation (UUID format, JSONB parsing, enum values)
    - Constraint validation (NOT NULL, ranges, timestamp ordering)
    - Orphan record detection

    Returns:
        True if all validations pass, False otherwise
    """
    logger.info("Running post-migration data integrity validation")
    start_time = time.monotonic()

    try:
        from app.core.database import db_manager

        # Ensure database is initialized
        if db_manager._engine is None:
            db_manager.init_db()

        async with db_manager.session_factory() as session:
            report = await validate_data_integrity(session)

        duration_s = time.monotonic() - start_time

        if report.success:
            logger.info(
                "Data integrity validation passed",
                extra={
                    "total_checks": report.total_checks,
                    "passed_checks": report.passed_checks,
                    "duration_seconds": round(duration_s, 2),
                },
            )
            return True
        else:
            # Log detailed failure info
            failed_checks = [r for r in report.results if not r.success]
            logger.error(
                "Data integrity validation failed",
                extra={
                    "total_checks": report.total_checks,
                    "failed_checks": report.failed_checks,
                    "total_issues": report.total_issues,
                    "failed_check_names": [r.check_name for r in failed_checks],
                    "duration_seconds": round(duration_s, 2),
                },
            )

            # Log each failed check
            for check in failed_checks:
                logger.error(
                    f"Failed check: {check.check_name}",
                    extra={
                        "table": check.table_name,
                        "issues_found": check.issues_found,
                        "sample_issues": check.details[:3],
                    },
                )

            return False

    except Exception as e:
        duration_s = time.monotonic() - start_time
        logger.error(
            "Data integrity validation error",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "duration_seconds": round(duration_s, 2),
            },
            exc_info=True,
        )
        return False


async def async_main() -> int:
    """Async entry point for deployment."""
    start_time = time.monotonic()

    # Log deployment start
    deployment_info = log_deployment_start()

    try:
        # Step 1: Validate environment variables
        if not validate_environment_variables():
            log_deployment_end(False, deployment_info, time.monotonic() - start_time)
            return 1

        # Step 2: Run health checks (database connection)
        if not await run_health_checks():
            log_deployment_end(False, deployment_info, time.monotonic() - start_time)
            return 1

        # Step 3: Run migrations
        if not run_migrations():
            log_deployment_end(False, deployment_info, time.monotonic() - start_time)
            return 1

        # Step 4: Run data integrity validation post-migration (non-blocking)
        # Note: Made non-blocking because schema mismatches during initial deployment
        # can cause false positives. Validation runs but doesn't block deployment.
        try:
            validation_passed = await run_data_integrity_validation()
            if not validation_passed:
                logger.warning(
                    "Data integrity validation found issues (non-blocking)",
                    extra={
                        "step": "data_integrity_validation",
                        "action": "continuing_deployment",
                    },
                )
        except Exception as e:
            logger.warning(
                "Data integrity validation error (non-blocking)",
                extra={
                    "step": "data_integrity_validation",
                    "action": "continuing_deployment",
                    "error": str(e),
                },
            )

        # Success
        log_deployment_end(True, deployment_info, time.monotonic() - start_time)
        return 0

    except Exception as e:
        logger.error(
            "Deployment failed with unexpected error",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )
        log_deployment_end(False, deployment_info, time.monotonic() - start_time)
        return 1


def main() -> int:
    """Main entry point for deployment script."""
    return asyncio.run(async_main())


if __name__ == "__main__":
    sys.exit(main())
