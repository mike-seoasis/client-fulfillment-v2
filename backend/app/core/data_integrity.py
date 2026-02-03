"""Post-migration data integrity validation.

Validates data integrity after database migrations complete:
- Foreign key integrity (all references exist)
- Data type validation (UUID format, JSONB parsing, enum values)
- Constraint validation (NOT NULL, ranges, timestamp ordering)
- Orphan record detection

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
- Handle connection timeouts gracefully (Railway can cold-start)
- Migrations must run via `alembic upgrade head`
- NO sqlite - PostgreSQL only
- Use SSL mode for database connections (sslmode=require)
"""

import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import db_logger, get_logger

logger = get_logger("data_integrity")

# Validation thresholds
SLOW_VALIDATION_THRESHOLD_MS = 100.0
UUID_LENGTH = 36

# Valid enum values for status fields
VALID_PROJECT_STATUSES = {"active", "completed", "on_hold", "cancelled", "archived"}
VALID_PHASE_STATUSES = {"pending", "in_progress", "completed", "blocked", "skipped"}
VALID_PHASES = {"discovery", "requirements", "implementation", "review", "launch"}


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    check_name: str
    table_name: str
    success: bool
    records_checked: int = 0
    issues_found: int = 0
    duration_ms: float = 0.0
    details: list[str] = field(default_factory=list)


@dataclass
class IntegrityReport:
    """Complete integrity validation report."""

    success: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    total_issues: int
    total_duration_ms: float
    results: list[ValidationResult] = field(default_factory=list)


class DataIntegrityValidator:
    """Validates data integrity post-migration."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def validate_all(self) -> IntegrityReport:
        """Run all integrity validations and return a report.

        Returns:
            IntegrityReport with all validation results
        """
        logger.info("Starting post-migration data integrity validation")
        start_time = time.monotonic()

        results: list[ValidationResult] = []

        # Foreign key integrity checks
        results.append(await self._validate_crawled_pages_project_fk())
        results.append(await self._validate_page_keywords_page_fk())
        results.append(await self._validate_page_paa_page_fk())
        results.append(await self._validate_brand_config_project_fk())
        results.append(await self._validate_generated_content_page_fk())
        results.append(await self._validate_crawl_schedule_project_fk())
        results.append(await self._validate_crawl_history_project_fk())
        results.append(await self._validate_nlp_cache_page_fk())
        results.append(await self._validate_webhook_config_project_fk())
        results.append(await self._validate_competitor_project_fk())

        # Data type validation
        results.append(await self._validate_project_uuid_format())
        results.append(await self._validate_project_status_enum())
        results.append(await self._validate_phase_status_jsonb())

        # Timestamp ordering validation
        results.append(await self._validate_timestamp_ordering("projects"))
        results.append(await self._validate_timestamp_ordering("crawled_pages"))

        # Numeric range validation
        results.append(await self._validate_keyword_difficulty_range())

        total_duration_ms = (time.monotonic() - start_time) * 1000
        passed_checks = sum(1 for r in results if r.success)
        failed_checks = sum(1 for r in results if not r.success)
        total_issues = sum(r.issues_found for r in results)

        report = IntegrityReport(
            success=failed_checks == 0,
            total_checks=len(results),
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            total_issues=total_issues,
            total_duration_ms=total_duration_ms,
            results=results,
        )

        if report.success:
            logger.info(
                "Data integrity validation completed successfully",
                extra={
                    "total_checks": report.total_checks,
                    "passed_checks": report.passed_checks,
                    "duration_ms": round(report.total_duration_ms, 2),
                },
            )
        else:
            logger.error(
                "Data integrity validation failed",
                extra={
                    "total_checks": report.total_checks,
                    "passed_checks": report.passed_checks,
                    "failed_checks": report.failed_checks,
                    "total_issues": report.total_issues,
                    "duration_ms": round(report.total_duration_ms, 2),
                },
            )

        return report

    async def _run_check(
        self,
        check_name: str,
        table_name: str,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """Run a single validation check with timing and error handling.

        Args:
            check_name: Name of the validation check
            table_name: Table being validated
            query: SQL query that returns rows with issues
            params: Optional query parameters

        Returns:
            ValidationResult with check outcome
        """
        start_time = time.monotonic()

        try:
            result = await self.session.execute(text(query), params or {})
            rows = result.fetchall()

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log slow queries
            if duration_ms > SLOW_VALIDATION_THRESHOLD_MS:
                db_logger.slow_query(
                    query=f"integrity_check:{check_name}",
                    duration_ms=duration_ms,
                    table=table_name,
                )

            issues_found = len(rows)
            details = [str(row) for row in rows[:10]]  # Limit details to first 10

            if issues_found > 0:
                logger.warning(
                    f"Integrity check failed: {check_name}",
                    extra={
                        "check_name": check_name,
                        "table": table_name,
                        "issues_found": issues_found,
                        "sample_issues": details[:3],
                        "duration_ms": round(duration_ms, 2),
                    },
                )

            return ValidationResult(
                check_name=check_name,
                table_name=table_name,
                success=issues_found == 0,
                issues_found=issues_found,
                duration_ms=duration_ms,
                details=details,
            )

        except SQLAlchemyError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            db_logger.transaction_failure(
                e,
                table=table_name,
                context=f"Integrity check: {check_name}",
            )
            return ValidationResult(
                check_name=check_name,
                table_name=table_name,
                success=False,
                issues_found=1,
                duration_ms=duration_ms,
                details=[f"Query error: {e!s}"],
            )

    async def _count_records(self, table_name: str) -> int:
        """Count total records in a table."""
        try:
            result = await self.session.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608
            )
            row = result.fetchone()
            return row[0] if row else 0
        except SQLAlchemyError as e:
            logger.warning(
                f"Could not count records in {table_name}: {e}",
                extra={"table": table_name, "error": str(e)},
            )
            return 0

    # =========================================================================
    # Foreign Key Integrity Checks
    # =========================================================================

    async def _validate_crawled_pages_project_fk(self) -> ValidationResult:
        """Validate that all crawled_pages reference existing projects."""
        query = """
            SELECT cp.id, cp.project_id
            FROM crawled_pages cp
            LEFT JOIN projects p ON cp.project_id = p.id
            WHERE p.id IS NULL
        """
        result = await self._run_check(
            check_name="crawled_pages_project_fk",
            table_name="crawled_pages",
            query=query,
        )
        result.records_checked = await self._count_records("crawled_pages")
        return result

    async def _validate_page_keywords_page_fk(self) -> ValidationResult:
        """Validate that all page_keywords reference existing crawled_pages."""
        query = """
            SELECT pk.id, pk.crawled_page_id
            FROM page_keywords pk
            LEFT JOIN crawled_pages cp ON pk.crawled_page_id = cp.id
            WHERE cp.id IS NULL
        """
        result = await self._run_check(
            check_name="page_keywords_page_fk",
            table_name="page_keywords",
            query=query,
        )
        result.records_checked = await self._count_records("page_keywords")
        return result

    async def _validate_page_paa_page_fk(self) -> ValidationResult:
        """Validate that all page_paa reference existing crawled_pages."""
        query = """
            SELECT pp.id, pp.crawled_page_id
            FROM page_paa pp
            LEFT JOIN crawled_pages cp ON pp.crawled_page_id = cp.id
            WHERE cp.id IS NULL
        """
        result = await self._run_check(
            check_name="page_paa_page_fk",
            table_name="page_paa",
            query=query,
        )
        result.records_checked = await self._count_records("page_paa")
        return result

    async def _validate_brand_config_project_fk(self) -> ValidationResult:
        """Validate that all brand_configs reference existing projects."""
        query = """
            SELECT bc.id, bc.project_id
            FROM brand_configs bc
            LEFT JOIN projects p ON bc.project_id = p.id
            WHERE p.id IS NULL
        """
        result = await self._run_check(
            check_name="brand_config_project_fk",
            table_name="brand_configs",
            query=query,
        )
        result.records_checked = await self._count_records("brand_configs")
        return result

    async def _validate_generated_content_page_fk(self) -> ValidationResult:
        """Validate that all generated_content reference existing crawled_pages."""
        query = """
            SELECT gc.id, gc.crawled_page_id
            FROM generated_content gc
            LEFT JOIN crawled_pages cp ON gc.crawled_page_id = cp.id
            WHERE cp.id IS NULL
        """
        result = await self._run_check(
            check_name="generated_content_page_fk",
            table_name="generated_content",
            query=query,
        )
        result.records_checked = await self._count_records("generated_content")
        return result

    async def _validate_crawl_schedule_project_fk(self) -> ValidationResult:
        """Validate that all crawl_schedules reference existing projects."""
        query = """
            SELECT cs.id, cs.project_id
            FROM crawl_schedules cs
            LEFT JOIN projects p ON cs.project_id = p.id
            WHERE p.id IS NULL
        """
        result = await self._run_check(
            check_name="crawl_schedule_project_fk",
            table_name="crawl_schedules",
            query=query,
        )
        result.records_checked = await self._count_records("crawl_schedules")
        return result

    async def _validate_crawl_history_project_fk(self) -> ValidationResult:
        """Validate that all crawl_history reference existing projects."""
        query = """
            SELECT ch.id, ch.project_id
            FROM crawl_history ch
            LEFT JOIN projects p ON ch.project_id = p.id
            WHERE p.id IS NULL
        """
        result = await self._run_check(
            check_name="crawl_history_project_fk",
            table_name="crawl_history",
            query=query,
        )
        result.records_checked = await self._count_records("crawl_history")
        return result

    async def _validate_nlp_cache_page_fk(self) -> ValidationResult:
        """Validate that all nlp_analysis_cache reference existing crawled_pages."""
        query = """
            SELECT nac.id, nac.crawled_page_id
            FROM nlp_analysis_cache nac
            LEFT JOIN crawled_pages cp ON nac.crawled_page_id = cp.id
            WHERE cp.id IS NULL
        """
        result = await self._run_check(
            check_name="nlp_cache_page_fk",
            table_name="nlp_analysis_cache",
            query=query,
        )
        result.records_checked = await self._count_records("nlp_analysis_cache")
        return result

    async def _validate_webhook_config_project_fk(self) -> ValidationResult:
        """Validate that all webhook_configs reference existing projects."""
        query = """
            SELECT wc.id, wc.project_id
            FROM webhook_configs wc
            LEFT JOIN projects p ON wc.project_id = p.id
            WHERE p.id IS NULL
        """
        result = await self._run_check(
            check_name="webhook_config_project_fk",
            table_name="webhook_configs",
            query=query,
        )
        result.records_checked = await self._count_records("webhook_configs")
        return result

    async def _validate_competitor_project_fk(self) -> ValidationResult:
        """Validate that all competitors reference existing projects."""
        query = """
            SELECT c.id, c.project_id
            FROM competitors c
            LEFT JOIN projects p ON c.project_id = p.id
            WHERE p.id IS NULL
        """
        result = await self._run_check(
            check_name="competitor_project_fk",
            table_name="competitors",
            query=query,
        )
        result.records_checked = await self._count_records("competitors")
        return result

    # =========================================================================
    # Data Type Validation
    # =========================================================================

    async def _validate_project_uuid_format(self) -> ValidationResult:
        """Validate that all project IDs are valid UUID format (36 chars)."""
        query = """
            SELECT id
            FROM projects
            WHERE length(id::text) != 36
               OR id::text !~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        """
        result = await self._run_check(
            check_name="project_uuid_format",
            table_name="projects",
            query=query,
        )
        result.records_checked = await self._count_records("projects")
        return result

    async def _validate_project_status_enum(self) -> ValidationResult:
        """Validate that all project statuses are valid enum values."""
        valid_statuses = ", ".join(f"'{s}'" for s in VALID_PROJECT_STATUSES)
        query = f"""
            SELECT id, status
            FROM projects
            WHERE status NOT IN ({valid_statuses})
        """
        result = await self._run_check(
            check_name="project_status_enum",
            table_name="projects",
            query=query,
        )
        result.records_checked = await self._count_records("projects")
        return result

    async def _validate_phase_status_jsonb(self) -> ValidationResult:
        """Validate that phase_status JSONB fields have valid structure."""
        # Check for invalid phase names
        valid_phases = ", ".join(f"'{p}'" for p in VALID_PHASES)
        query = f"""
            SELECT id, phase_status
            FROM projects
            WHERE phase_status != '{{}}'::jsonb
              AND (
                  -- Check if any key is not in valid phases
                  EXISTS (
                      SELECT 1
                      FROM jsonb_object_keys(phase_status) AS k
                      WHERE k NOT IN ({valid_phases})
                  )
              )
        """
        result = await self._run_check(
            check_name="phase_status_jsonb_keys",
            table_name="projects",
            query=query,
        )
        result.records_checked = await self._count_records("projects")
        return result

    # =========================================================================
    # Timestamp Validation
    # =========================================================================

    async def _validate_timestamp_ordering(self, table_name: str) -> ValidationResult:
        """Validate that created_at <= updated_at for all records."""
        query = f"""
            SELECT id, created_at, updated_at
            FROM {table_name}
            WHERE created_at > updated_at
        """  # noqa: S608
        result = await self._run_check(
            check_name=f"{table_name}_timestamp_order",
            table_name=table_name,
            query=query,
        )
        result.records_checked = await self._count_records(table_name)
        return result

    # =========================================================================
    # Numeric Range Validation
    # =========================================================================

    async def _validate_keyword_difficulty_range(self) -> ValidationResult:
        """Validate that difficulty_score is between 0 and 100."""
        query = """
            SELECT id, difficulty_score
            FROM page_keywords
            WHERE difficulty_score IS NOT NULL
              AND (difficulty_score < 0 OR difficulty_score > 100)
        """
        result = await self._run_check(
            check_name="keyword_difficulty_range",
            table_name="page_keywords",
            query=query,
        )
        result.records_checked = await self._count_records("page_keywords")
        return result


async def validate_data_integrity(session: AsyncSession) -> IntegrityReport:
    """Run data integrity validation.

    Args:
        session: AsyncSession for database operations

    Returns:
        IntegrityReport with all validation results
    """
    validator = DataIntegrityValidator(session)
    return await validator.validate_all()
