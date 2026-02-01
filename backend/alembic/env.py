"""Alembic environment configuration for async SQLAlchemy migrations.

Supports:
- Async migrations with asyncpg
- Auto-detection of model changes
- Railway deployment (DATABASE_URL from environment)
- Migration logging with version info
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database import Base
from app.core.logging import db_logger

# Import all models so Alembic can detect them
from app.models.brand_config import BrandConfig  # noqa: F401
from app.models.crawl_history import CrawlHistory  # noqa: F401
from app.models.crawl_schedule import CrawlSchedule  # noqa: F401
from app.models.crawled_page import CrawledPage  # noqa: F401
from app.models.generated_content import GeneratedContent  # noqa: F401
from app.models.nlp_analysis_cache import NLPAnalysisCache  # noqa: F401
from app.models.page_keywords import PageKeywords  # noqa: F401
from app.models.page_paa import PagePAA  # noqa: F401
from app.models.project import Project  # noqa: F401

# Alembic Config object
config = context.config

# Setup logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate support
target_metadata = Base.metadata


def get_database_url() -> str:
    """Get database URL from environment, converting for async driver."""
    settings = get_settings()
    db_url = str(settings.database_url)

    # Convert to async driver URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Add sslmode=require if not present
    if "sslmode=" not in db_url:
        separator = "&" if "?" in db_url else "?"
        db_url = f"{db_url}{separator}sslmode=require"

    return db_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the SQL to the script output.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    # Get current migration info for logging
    current_rev = context.get_context().get_current_revision() if context.is_offline_mode() is False else None
    head_rev = context.get_head_revision()

    db_logger.migration_start(
        version=str(head_rev) if head_rev else "initial",
        description=f"Migrating from {current_rev or 'base'} to {head_rev or 'head'}",
    )

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    settings = get_settings()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={
            "timeout": settings.db_connect_timeout,
            "command_timeout": settings.db_command_timeout,
        },
    )

    success = False
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
        success = True
    except Exception:
        db_logger.migration_end(version=str(head_rev) if head_rev else "unknown", success=False)
        raise
    finally:
        if success:
            db_logger.migration_end(version=str(head_rev) if head_rev else "unknown", success=True)
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
