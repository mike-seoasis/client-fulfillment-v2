"""BrandConfigRepository with CRUD operations.

Handles all database operations for BrandConfig entities.
Follows the layered architecture pattern: API -> Service -> Repository -> Database.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, brand_config_id) in all logs
- Log validation failures with field names and rejected values
- Log state transitions at INFO level
- Add timing logs for operations >1 second
"""

import time
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import db_logger, get_logger
from app.models.brand_config import BrandConfig

logger = get_logger(__name__)


class BrandConfigRepository:
    """Repository for BrandConfig CRUD operations.

    All methods accept an AsyncSession and handle database operations
    with comprehensive logging as required.
    """

    TABLE_NAME = "brand_configs"
    SLOW_OPERATION_THRESHOLD_MS = 1000  # 1 second

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session for database operations
        """
        self.session = session
        logger.debug("BrandConfigRepository initialized")

    async def create(
        self,
        project_id: str,
        brand_name: str,
        domain: str | None = None,
        v2_schema: dict[str, Any] | None = None,
    ) -> BrandConfig:
        """Create a new brand config.

        Args:
            project_id: UUID of the associated project
            brand_name: Brand name
            domain: Optional brand domain
            v2_schema: V2 schema data (default: empty dict)

        Returns:
            Created BrandConfig instance

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Creating brand config",
            extra={
                "project_id": project_id,
                "brand_name": brand_name,
                "domain": domain,
                "has_v2_schema": v2_schema is not None,
            },
        )

        try:
            brand_config = BrandConfig(
                project_id=project_id,
                brand_name=brand_name,
                domain=domain,
                v2_schema=v2_schema or {},
            )
            self.session.add(brand_config)
            await self.session.flush()
            await self.session.refresh(brand_config)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Brand config created successfully",
                extra={
                    "brand_config_id": brand_config.id,
                    "project_id": project_id,
                    "brand_name": brand_name,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query="INSERT INTO brand_configs",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            logger.info(
                "Brand config created",
                extra={
                    "brand_config_id": brand_config.id,
                    "project_id": project_id,
                    "brand_name": brand_name,
                },
            )

            return brand_config

        except IntegrityError as e:
            logger.error(
                "Failed to create brand config - integrity error",
                extra={
                    "project_id": project_id,
                    "brand_name": brand_name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Creating brand_config for project_id={project_id}",
            )
            raise

    async def get_by_id(self, brand_config_id: str) -> BrandConfig | None:
        """Get a brand config by ID.

        Args:
            brand_config_id: UUID of the brand config

        Returns:
            BrandConfig instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching brand config by ID",
            extra={"brand_config_id": brand_config_id},
        )

        try:
            result = await self.session.execute(
                select(BrandConfig).where(BrandConfig.id == brand_config_id)
            )
            brand_config = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Brand config fetch completed",
                extra={
                    "brand_config_id": brand_config_id,
                    "found": brand_config is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM brand_configs WHERE id={brand_config_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return brand_config

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch brand config by ID",
                extra={
                    "brand_config_id": brand_config_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_project_id(self, project_id: str) -> list[BrandConfig]:
        """Get all brand configs for a project.

        Args:
            project_id: UUID of the project

        Returns:
            List of BrandConfig instances

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching brand configs by project ID",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                select(BrandConfig)
                .where(BrandConfig.project_id == project_id)
                .order_by(BrandConfig.created_at.desc())
            )
            brand_configs = list(result.scalars().all())

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Project brand configs fetch completed",
                extra={
                    "project_id": project_id,
                    "count": len(brand_configs),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM brand_configs WHERE project_id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return brand_configs

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch brand configs by project ID",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_by_project_and_brand(
        self,
        project_id: str,
        brand_name: str,
    ) -> BrandConfig | None:
        """Get a brand config by project ID and brand name.

        Args:
            project_id: UUID of the project
            brand_name: Name of the brand

        Returns:
            BrandConfig instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Fetching brand config by project and brand name",
            extra={
                "project_id": project_id,
                "brand_name": brand_name,
            },
        )

        try:
            result = await self.session.execute(
                select(BrandConfig)
                .where(BrandConfig.project_id == project_id)
                .where(BrandConfig.brand_name == brand_name)
            )
            brand_config = result.scalar_one_or_none()

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Brand config by name fetch completed",
                extra={
                    "project_id": project_id,
                    "brand_name": brand_name,
                    "found": brand_config is not None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"SELECT FROM brand_configs WHERE project_id={project_id} AND brand_name={brand_name}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            return brand_config

        except SQLAlchemyError as e:
            logger.error(
                "Failed to fetch brand config by project and brand name",
                extra={
                    "project_id": project_id,
                    "brand_name": brand_name,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def update(
        self,
        brand_config_id: str,
        brand_name: str | None = None,
        domain: str | None = None,
        v2_schema: dict[str, Any] | None = None,
    ) -> BrandConfig | None:
        """Update a brand config.

        Args:
            brand_config_id: UUID of the brand config to update
            brand_name: New brand name (optional)
            domain: New domain (optional)
            v2_schema: New V2 schema (optional, replaces existing)

        Returns:
            Updated BrandConfig instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()

        # Build update dict with only provided values
        update_values: dict[str, Any] = {}
        if brand_name is not None:
            update_values["brand_name"] = brand_name
        if domain is not None:
            update_values["domain"] = domain
        if v2_schema is not None:
            update_values["v2_schema"] = v2_schema

        if not update_values:
            logger.debug(
                "No update values provided, returning existing brand config",
                extra={"brand_config_id": brand_config_id},
            )
            return await self.get_by_id(brand_config_id)

        logger.debug(
            "Updating brand config",
            extra={
                "brand_config_id": brand_config_id,
                "update_fields": list(update_values.keys()),
            },
        )

        try:
            # Get current config for logging
            current_config = await self.get_by_id(brand_config_id)
            if current_config is None:
                logger.debug(
                    "Brand config not found for update",
                    extra={"brand_config_id": brand_config_id},
                )
                return None

            await self.session.execute(
                update(BrandConfig)
                .where(BrandConfig.id == brand_config_id)
                .values(**update_values)
            )
            await self.session.flush()

            # Refresh to get updated values
            updated_config = await self.get_by_id(brand_config_id)

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Brand config updated successfully",
                extra={
                    "brand_config_id": brand_config_id,
                    "project_id": current_config.project_id,
                    "update_fields": list(update_values.keys()),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"UPDATE brand_configs WHERE id={brand_config_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            logger.info(
                "Brand config updated",
                extra={
                    "brand_config_id": brand_config_id,
                    "project_id": current_config.project_id,
                    "update_fields": list(update_values.keys()),
                },
            )

            return updated_config

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Updating brand_config_id={brand_config_id}",
            )
            raise

    async def update_v2_schema(
        self,
        brand_config_id: str,
        v2_schema: dict[str, Any],
    ) -> BrandConfig | None:
        """Update only the V2 schema for a brand config.

        Convenience method for updating the V2 schema without affecting other fields.

        Args:
            brand_config_id: UUID of the brand config
            v2_schema: New V2 schema (replaces existing)

        Returns:
            Updated BrandConfig instance if found, None otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        return await self.update(brand_config_id, v2_schema=v2_schema)

    async def delete(self, brand_config_id: str) -> bool:
        """Delete a brand config.

        Args:
            brand_config_id: UUID of the brand config to delete

        Returns:
            True if brand config was deleted, False if not found

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting brand config",
            extra={"brand_config_id": brand_config_id},
        )

        try:
            # Get project_id for logging before deletion
            config = await self.get_by_id(brand_config_id)
            project_id = config.project_id if config else None

            result = await self.session.execute(
                delete(BrandConfig).where(BrandConfig.id == brand_config_id)
            )
            await self.session.flush()

            deleted = result.rowcount > 0

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Brand config delete completed",
                extra={
                    "brand_config_id": brand_config_id,
                    "project_id": project_id,
                    "deleted": deleted,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"DELETE FROM brand_configs WHERE id={brand_config_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            if deleted:
                logger.info(
                    "Brand config deleted",
                    extra={
                        "brand_config_id": brand_config_id,
                        "project_id": project_id,
                    },
                )

            return deleted

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting brand_config_id={brand_config_id}",
            )
            raise

    async def delete_by_project(self, project_id: str) -> int:
        """Delete all brand configs for a project.

        Args:
            project_id: UUID of the project

        Returns:
            Number of brand configs deleted

        Raises:
            SQLAlchemyError: On database errors
        """
        start_time = time.monotonic()
        logger.debug(
            "Deleting brand configs by project",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                delete(BrandConfig).where(BrandConfig.project_id == project_id)
            )
            await self.session.flush()

            deleted_count = result.rowcount

            duration_ms = (time.monotonic() - start_time) * 1000
            logger.debug(
                "Brand configs delete by project completed",
                extra={
                    "project_id": project_id,
                    "deleted_count": deleted_count,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > self.SLOW_OPERATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"DELETE FROM brand_configs WHERE project_id={project_id}",
                    duration_ms=duration_ms,
                    table=self.TABLE_NAME,
                )

            if deleted_count > 0:
                logger.info(
                    "Brand configs deleted for project",
                    extra={
                        "project_id": project_id,
                        "deleted_count": deleted_count,
                    },
                )

            return deleted_count

        except SQLAlchemyError as e:
            db_logger.transaction_failure(
                e,
                table=self.TABLE_NAME,
                context=f"Deleting brand_configs for project_id={project_id}",
            )
            raise

    async def exists(self, brand_config_id: str) -> bool:
        """Check if a brand config exists.

        Args:
            brand_config_id: UUID of the brand config

        Returns:
            True if brand config exists, False otherwise

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Checking brand config existence",
            extra={"brand_config_id": brand_config_id},
        )

        try:
            result = await self.session.execute(
                select(BrandConfig.id).where(BrandConfig.id == brand_config_id)
            )
            exists = result.scalar_one_or_none() is not None

            logger.debug(
                "Brand config existence check completed",
                extra={
                    "brand_config_id": brand_config_id,
                    "exists": exists,
                },
            )

            return exists

        except SQLAlchemyError as e:
            logger.error(
                "Failed to check brand config existence",
                extra={
                    "brand_config_id": brand_config_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise

    async def count_by_project(self, project_id: str) -> int:
        """Count brand configs for a project.

        Args:
            project_id: UUID of the project

        Returns:
            Count of brand configs for the project

        Raises:
            SQLAlchemyError: On database errors
        """
        logger.debug(
            "Counting brand configs by project",
            extra={"project_id": project_id},
        )

        try:
            result = await self.session.execute(
                select(func.count())
                .select_from(BrandConfig)
                .where(BrandConfig.project_id == project_id)
            )
            count = result.scalar_one()

            logger.debug(
                "Brand config count completed",
                extra={
                    "project_id": project_id,
                    "count": count,
                },
            )

            return count

        except SQLAlchemyError as e:
            logger.error(
                "Failed to count brand configs by project",
                extra={
                    "project_id": project_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise
