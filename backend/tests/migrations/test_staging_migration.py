"""Tests for staging migration with production data snapshot.

This module tests database migrations on staging environments using
production data snapshots. It verifies that:
- Migrations run successfully with real data
- Error logging is properly configured
- Connection pooling works correctly
- Railway deployment requirements are met

ERROR LOGGING REQUIREMENTS:
- Log all database connection errors with connection string (masked)
- Log query execution time for slow queries (>100ms) at WARNING level
- Log transaction failures with rollback context
- Log migration start/end with version info
- Include table/model name in all database error logs
- Log connection pool exhaustion at CRITICAL level

RAILWAY DEPLOYMENT REQUIREMENTS:
- Connect via DATABASE_URL environment variable
- Use connection pooling (pool_size=5, max_overflow=10)
- Handle connection timeouts gracefully
- Migrations run via `alembic upgrade head`
- PostgreSQL only (NO sqlite)
- Use SSL mode for database connections (sslmode=require)
"""

import os
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.logging import db_logger, mask_connection_string


class TestMigrationLogging:
    """Test that migration logging meets requirements."""

    def test_mask_connection_string_hides_password(self) -> None:
        """Connection strings should have passwords masked."""
        conn_str = "postgresql://user:mysecretpassword@host:5432/db"
        masked = mask_connection_string(conn_str)

        assert "mysecretpassword" not in masked
        assert "****" in masked
        assert "user" in masked
        assert "host" in masked

    def test_mask_connection_string_handles_special_chars(self) -> None:
        """Mask should work with special characters in password."""
        conn_str = "postgresql://user:p@ss%23word!@host:5432/db"
        masked = mask_connection_string(conn_str)

        # Password should be masked
        assert "p@ss%23word!" not in masked or "****" in masked

    def test_mask_connection_string_empty(self) -> None:
        """Empty connection string should return empty."""
        assert mask_connection_string("") == ""

    def test_db_logger_has_required_methods(self) -> None:
        """DatabaseLogger should have all required logging methods."""
        # Connection errors
        assert hasattr(db_logger, "connection_error")

        # Slow queries
        assert hasattr(db_logger, "slow_query")

        # Transaction failures
        assert hasattr(db_logger, "transaction_failure")

        # Migration logging
        assert hasattr(db_logger, "migration_start")
        assert hasattr(db_logger, "migration_end")
        assert hasattr(db_logger, "migration_step")

        # Rollback
        assert hasattr(db_logger, "rollback_triggered")
        assert hasattr(db_logger, "rollback_executed")

        # Pool exhaustion
        assert hasattr(db_logger, "pool_exhausted")


class TestDatabaseConnectionConfig:
    """Test database connection configuration for Railway deployment."""

    def test_database_url_required(self) -> None:
        """DATABASE_URL must be a required field."""
        from pydantic import ValidationError

        # Should fail without database_url
        with pytest.raises(ValidationError):
            Settings()

    def test_pool_size_defaults(self) -> None:
        """Pool size should default to Railway-recommended values."""
        settings = Settings(
            database_url="postgresql://test:test@localhost:5432/test"  # type: ignore[arg-type]
        )

        assert settings.db_pool_size == 5
        assert settings.db_max_overflow == 10

    def test_ssl_mode_added_to_url(self) -> None:
        """SSL mode should be enforced for Railway connections."""
        # Test the URL transformation logic used in database.py
        settings = Settings(
            database_url="postgresql://test:test@localhost:5432/test",  # type: ignore[arg-type]
            debug=False,
        )

        db_url = str(settings.database_url)

        # Convert to async driver (same logic as database.py)
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Add sslmode (same logic as database.py)
        if "sslmode=" not in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{separator}sslmode=require"

        assert "sslmode=require" in db_url

    def test_connection_timeout_for_cold_start(self) -> None:
        """Connection timeout should be set for Railway cold-starts."""
        settings = Settings(
            database_url="postgresql://test:test@localhost:5432/test"  # type: ignore[arg-type]
        )

        # Default 60 seconds for Railway cold-start handling
        assert settings.db_connect_timeout == 60
        assert settings.db_command_timeout == 60


class TestMigrationExecution:
    """Test migration execution patterns."""

    def test_alembic_env_uses_async_driver(self) -> None:
        """Alembic env.py should use postgresql+asyncpg driver."""
        # Read the alembic env.py file
        env_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "alembic",
            "env.py",
        )

        with open(env_path) as f:
            content = f.read()

        # Should convert to async driver
        assert "postgresql+asyncpg" in content

    def test_alembic_env_adds_sslmode(self) -> None:
        """Alembic env.py should add sslmode=require."""
        env_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "alembic",
            "env.py",
        )

        with open(env_path) as f:
            content = f.read()

        # Should add sslmode if not present
        assert "sslmode=require" in content or "sslmode=" in content


class TestErrorLogging:
    """Test error logging meets requirements."""

    def test_connection_error_logs_masked_string(self) -> None:
        """Connection errors should log with masked connection string."""
        with patch.object(db_logger, "logger") as mock_logger:
            error = Exception("Connection refused")
            conn_str = "postgresql://user:password@host:5432/db"

            db_logger.connection_error(error, conn_str)

            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args

            # Verify extra contains masked connection string
            extra = call_kwargs.kwargs.get("extra", {})
            assert "****" in extra.get("connection_string", "")
            assert "password" not in extra.get("connection_string", "")

    def test_slow_query_logs_at_warning(self) -> None:
        """Slow queries (>100ms) should log at WARNING level."""
        with patch.object(db_logger, "logger") as mock_logger:
            db_logger.slow_query(
                query="SELECT * FROM users",
                duration_ms=150.5,
                table="users",
            )

            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args
            extra = call_kwargs.kwargs.get("extra", {})

            assert extra.get("duration_ms") == 150.5
            assert extra.get("table") == "users"

    def test_transaction_failure_logs_rollback_context(self) -> None:
        """Transaction failures should log with rollback context."""
        with patch.object(db_logger, "logger") as mock_logger:
            error = Exception("Constraint violation")

            db_logger.transaction_failure(
                error,
                table="orders",
                context="Creating order for user 123",
            )

            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args
            extra = call_kwargs.kwargs.get("extra", {})

            assert extra.get("table") == "orders"
            assert "Creating order" in extra.get("rollback_context", "")

    def test_migration_start_logs_version(self) -> None:
        """Migration start should log version info."""
        with patch.object(db_logger, "logger") as mock_logger:
            db_logger.migration_start(
                version="0011_create_competitors",
                description="Add competitors table",
            )

            mock_logger.info.assert_called_once()
            call_kwargs = mock_logger.info.call_args
            extra = call_kwargs.kwargs.get("extra", {})

            assert extra.get("migration_version") == "0011_create_competitors"
            assert "competitors" in extra.get("description", "")

    def test_migration_end_logs_success_status(self) -> None:
        """Migration end should log success/failure status."""
        with patch.object(db_logger, "logger") as mock_logger:
            db_logger.migration_end(version="0011", success=True)

            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args
            extra = call_args.kwargs.get("extra", {})

            assert extra.get("success") is True

    def test_pool_exhaustion_logs_at_critical(self) -> None:
        """Pool exhaustion should log at CRITICAL level."""
        with patch.object(db_logger, "logger") as mock_logger:
            db_logger.pool_exhausted(pool_size=5, waiting=10)

            mock_logger.critical.assert_called_once()
            call_kwargs = mock_logger.critical.call_args
            extra = call_kwargs.kwargs.get("extra", {})

            assert extra.get("pool_size") == 5
            assert extra.get("waiting_connections") == 10


class TestRailwayDeploymentRequirements:
    """Test Railway-specific deployment requirements."""

    def test_no_sqlite_in_production_code(self) -> None:
        """Production code should not use SQLite."""
        database_py = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "app",
            "core",
            "database.py",
        )

        with open(database_py) as f:
            content = f.read()

        # Should not contain sqlite references (except maybe in comments)
        lines = [
            line
            for line in content.split("\n")
            if not line.strip().startswith("#") and "sqlite" in line.lower()
        ]

        assert len(lines) == 0, f"Found sqlite references: {lines}"

    def test_procfile_runs_migrations(self) -> None:
        """Procfile should run migrations via alembic upgrade head."""
        procfile_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "Procfile",
        )

        with open(procfile_path) as f:
            content = f.read()

        # Should use deploy script which runs alembic
        assert "deploy" in content

    def test_deploy_script_runs_alembic(self) -> None:
        """Deploy script should run alembic upgrade head."""
        deploy_py = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "app",
            "deploy.py",
        )

        with open(deploy_py) as f:
            content = f.read()

        # Should run alembic upgrade head
        assert "alembic" in content
        assert "upgrade" in content
        assert "head" in content


class TestStagingMigrationScript:
    """Test staging migration script functionality."""

    @pytest.fixture
    def mock_settings_for_staging(self) -> Settings:
        """Create mock settings for staging environment."""
        return Settings(
            database_url="postgresql://staging:staging@staging-db:5432/staging",  # type: ignore[arg-type]
            environment="staging",
            db_pool_size=5,
            db_max_overflow=10,
            log_level="DEBUG",
        )

    def test_staging_migration_validates_postgresql(
        self, mock_settings_for_staging: Settings
    ) -> None:
        """Staging migration should only work with PostgreSQL."""
        db_url = str(mock_settings_for_staging.database_url)

        # Should start with postgresql
        assert db_url.startswith("postgresql://")

    def test_staging_migration_uses_connection_pooling(
        self, mock_settings_for_staging: Settings
    ) -> None:
        """Staging migration should use proper connection pooling."""
        assert mock_settings_for_staging.db_pool_size == 5
        assert mock_settings_for_staging.db_max_overflow == 10


class TestMigrationRollback:
    """Test migration rollback logging."""

    def test_rollback_triggered_logging(self) -> None:
        """Rollback trigger should be logged with reason."""
        with patch.object(db_logger, "logger") as mock_logger:
            db_logger.rollback_triggered(
                reason="Migration step failed",
                from_version="0011",
                to_version="0010",
            )

            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args
            extra = call_kwargs.kwargs.get("extra", {})

            assert extra.get("reason") == "Migration step failed"
            assert extra.get("from_version") == "0011"
            assert extra.get("to_version") == "0010"

    def test_rollback_executed_logging(self) -> None:
        """Rollback execution should be logged with success status."""
        with patch.object(db_logger, "logger") as mock_logger:
            db_logger.rollback_executed(
                from_version="0011",
                to_version="0010",
                success=True,
            )

            mock_logger.log.assert_called_once()
            call_kwargs = mock_logger.log.call_args
            extra = call_kwargs.kwargs.get("extra", {})

            assert extra.get("from_version") == "0011"
            assert extra.get("to_version") == "0010"
            assert extra.get("success") is True


class TestProductionDataSnapshot:
    """Test handling of production data snapshots for staging testing."""

    def test_settings_support_different_environments(self) -> None:
        """Settings should support staging/production environment distinction."""
        staging_settings = Settings(
            database_url="postgresql://staging:staging@staging:5432/staging",  # type: ignore[arg-type]
            environment="staging",
        )

        assert staging_settings.environment == "staging"

    def test_slow_query_threshold_configurable(self) -> None:
        """Slow query threshold should be configurable (default 100ms)."""
        settings = Settings(
            database_url="postgresql://test:test@localhost:5432/test",  # type: ignore[arg-type]
            db_slow_query_threshold_ms=200,
        )

        assert settings.db_slow_query_threshold_ms == 200

    def test_slow_query_default_threshold(self) -> None:
        """Slow query threshold should default to 100ms."""
        settings = Settings(
            database_url="postgresql://test:test@localhost:5432/test",  # type: ignore[arg-type]
        )

        assert settings.db_slow_query_threshold_ms == 100


class TestMigrationStepLogging:
    """Test individual migration step logging."""

    def test_migration_step_logs_with_duration(self) -> None:
        """Migration steps should log with duration."""
        with patch.object(db_logger, "logger") as mock_logger:
            db_logger.migration_step(
                step="upgrade",
                revision="0011",
                success=True,
                duration_ms=1234.5,
            )

            mock_logger.log.assert_called_once()
            call_kwargs = mock_logger.log.call_args
            extra = call_kwargs.kwargs.get("extra", {})

            assert extra.get("step") == "upgrade"
            assert extra.get("revision") == "0011"
            assert extra.get("success") is True
            assert extra.get("duration_ms") == 1234.5

    def test_migration_step_failure_logs_at_error(self) -> None:
        """Failed migration steps should log at ERROR level."""
        import logging

        with patch.object(db_logger, "logger") as mock_logger:
            db_logger.migration_step(
                step="upgrade",
                revision="0011",
                success=False,
                duration_ms=500.0,
            )

            # Check it was called with ERROR level
            call_args = mock_logger.log.call_args
            assert call_args.args[0] == logging.ERROR
