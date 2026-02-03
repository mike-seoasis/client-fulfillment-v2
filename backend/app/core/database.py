"""Database configuration and session management.

Features:
- Async SQLAlchemy with connection pooling
- Slow query logging (>100ms at WARNING)
- Connection error logging with masked strings
- Transaction failure logging with rollback context
- Connection pool exhaustion logging at CRITICAL
"""

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import Pool

from app.core.config import get_settings
from app.core.logging import db_logger, get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Get the database engine, initializing if needed."""
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call init_db() first.")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory."""
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call init_db() first.")
        return self._session_factory

    def init_db(self) -> None:
        """Initialize database engine and session factory."""
        settings = get_settings()

        # Convert postgres:// to postgresql+asyncpg:// for async support
        db_url = str(settings.database_url)
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        try:
            self._engine = create_async_engine(
                db_url,
                pool_size=settings.db_pool_size,
                max_overflow=settings.db_max_overflow,
                pool_timeout=settings.db_pool_timeout,
                pool_pre_ping=True,  # Verify connections before use
                echo=settings.debug,  # SQL logging in debug mode
                # Connection arguments for Railway cold-start handling
                # Note: asyncpg uses 'ssl' not 'sslmode' (which is libpq/psycopg2)
                connect_args={
                    "timeout": settings.db_connect_timeout,
                    "command_timeout": settings.db_command_timeout,
                    # Only require SSL in production (Railway), disable for local dev
                    **({"ssl": "require"} if settings.environment == "production" else {}),
                },
            )

            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )

            # Set up pool event listeners for monitoring
            self._setup_pool_listeners()

            logger.info("Database engine initialized successfully")

        except Exception as e:
            db_logger.connection_error(e, db_url)
            raise

    def _setup_pool_listeners(self) -> None:
        """Set up SQLAlchemy pool event listeners."""
        if self._engine is None:
            return

        # Pool listeners are registered on the Pool class globally
        # sync_engine reference not needed since we listen to Pool class directly

        @event.listens_for(Pool, "checkout")
        def on_checkout(
            dbapi_conn: Any, connection_record: Any, connection_proxy: Any
        ) -> None:
            """Track connection checkouts for pool monitoring."""
            connection_record.info["checkout_time"] = time.monotonic()

        @event.listens_for(Pool, "checkin")
        def on_checkin(dbapi_conn: Any, connection_record: Any) -> None:
            """Clear checkout time on checkin."""
            connection_record.info.pop("checkout_time", None)

    async def close(self) -> None:
        """Close database connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connections closed")

    async def check_connection(self) -> bool:
        """Check if database connection is healthy."""
        try:
            async with self.session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            settings = get_settings()
            db_logger.connection_error(e, str(settings.database_url))
            return False


# Global database manager instance
db_manager = DatabaseManager()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions.

    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    settings = get_settings()
    threshold_ms = settings.db_slow_query_threshold_ms

    async with db_manager.session_factory() as session:
        start_time = time.monotonic()
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as e:
            await session.rollback()
            # Extract table name from error if possible
            table_name = _extract_table_from_error(e)
            db_logger.transaction_failure(
                e,
                table=table_name,
                context="Session rollback after SQLAlchemy error",
            )
            raise
        finally:
            duration_ms = (time.monotonic() - start_time) * 1000
            if duration_ms > threshold_ms:
                db_logger.slow_query(
                    query="session_transaction",
                    duration_ms=duration_ms,
                )


@asynccontextmanager
async def transaction(
    session: AsyncSession, table: str | None = None
) -> AsyncGenerator[AsyncSession, None]:
    """Context manager for explicit transaction handling.

    Usage:
        async with transaction(session, table="users") as txn:
            # perform operations
            ...
    """
    settings = get_settings()
    threshold_ms = settings.db_slow_query_threshold_ms
    start_time = time.monotonic()

    try:
        yield session
        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        db_logger.transaction_failure(
            e,
            table=table,
            context="Explicit transaction rollback",
        )
        raise
    finally:
        duration_ms = (time.monotonic() - start_time) * 1000
        if duration_ms > threshold_ms:
            db_logger.slow_query(
                query=f"transaction on {table or 'unknown'}",
                duration_ms=duration_ms,
                table=table,
            )


def _extract_table_from_error(error: Exception) -> str | None:
    """Try to extract table name from SQLAlchemy error."""
    error_str = str(error)
    # Common patterns for table names in error messages
    import re

    patterns = [
        r'relation "([^"]+)"',
        r"table '([^']+)'",
        r'INSERT INTO "?([^\s"]+)"?',
        r'UPDATE "?([^\s"]+)"?',
        r'DELETE FROM "?([^\s"]+)"?',
    ]
    for pattern in patterns:
        match = re.search(pattern, error_str, re.IGNORECASE)
        if match:
            return match.group(1)
    return None
