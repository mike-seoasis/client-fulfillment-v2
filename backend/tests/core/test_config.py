"""Tests for application configuration defaults.

Tests that database timeout/pool settings in Settings have the
expected default values for Railway/Neon deployment.
"""

import os

import pytest

# Ensure DATABASE_URL is set before importing Settings
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")

from app.core.config import Settings


class TestDatabaseConfigDefaults:
    """Test database configuration default values."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Create Settings with only the required DATABASE_URL."""
        return Settings(database_url="postgresql://test:test@localhost:5432/test")  # type: ignore[arg-type]

    def test_db_connect_timeout_defaults_to_10(self, settings: Settings) -> None:
        """db_connect_timeout should default to 10 seconds."""
        assert settings.db_connect_timeout == 10

    def test_db_command_timeout_defaults_to_30(self, settings: Settings) -> None:
        """db_command_timeout should default to 30 seconds."""
        assert settings.db_command_timeout == 30

    def test_db_pool_recycle_defaults_to_300(self, settings: Settings) -> None:
        """db_pool_recycle should default to 300 seconds (matches Neon idle timeout)."""
        assert settings.db_pool_recycle == 300
