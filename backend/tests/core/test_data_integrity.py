"""Tests for post-migration data integrity validation.

Tests the data integrity validator to ensure:
- Foreign key integrity checks work correctly
- Data type validation catches invalid values
- Timestamp ordering is verified
- Numeric range validation works
- All logging requirements are met
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.data_integrity import (
    VALID_PHASE_STATUSES,
    VALID_PHASES,
    VALID_PROJECT_STATUSES,
    DataIntegrityValidator,
    IntegrityReport,
    ValidationResult,
    validate_data_integrity,
)

# Set DATABASE_URL for tests
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_validation_result_creation(self) -> None:
        """ValidationResult should store all check metadata."""
        result = ValidationResult(
            check_name="test_check",
            table_name="test_table",
            success=True,
            records_checked=100,
            issues_found=0,
            duration_ms=50.5,
            details=[],
        )

        assert result.check_name == "test_check"
        assert result.table_name == "test_table"
        assert result.success is True
        assert result.records_checked == 100
        assert result.issues_found == 0
        assert result.duration_ms == 50.5

    def test_validation_result_with_issues(self) -> None:
        """ValidationResult should capture issues found."""
        result = ValidationResult(
            check_name="fk_check",
            table_name="orders",
            success=False,
            records_checked=50,
            issues_found=3,
            duration_ms=25.0,
            details=["row 1", "row 2", "row 3"],
        )

        assert result.success is False
        assert result.issues_found == 3
        assert len(result.details) == 3


class TestIntegrityReport:
    """Test IntegrityReport dataclass."""

    def test_integrity_report_success(self) -> None:
        """IntegrityReport should aggregate successful results."""
        results = [
            ValidationResult(
                check_name="check1",
                table_name="table1",
                success=True,
                issues_found=0,
                duration_ms=10.0,
            ),
            ValidationResult(
                check_name="check2",
                table_name="table2",
                success=True,
                issues_found=0,
                duration_ms=15.0,
            ),
        ]

        report = IntegrityReport(
            success=True,
            total_checks=2,
            passed_checks=2,
            failed_checks=0,
            total_issues=0,
            total_duration_ms=25.0,
            results=results,
        )

        assert report.success is True
        assert report.total_checks == 2
        assert report.passed_checks == 2
        assert report.failed_checks == 0

    def test_integrity_report_with_failures(self) -> None:
        """IntegrityReport should track failed checks."""
        results = [
            ValidationResult(
                check_name="check1",
                table_name="table1",
                success=True,
                issues_found=0,
                duration_ms=10.0,
            ),
            ValidationResult(
                check_name="check2",
                table_name="table2",
                success=False,
                issues_found=5,
                duration_ms=15.0,
            ),
        ]

        report = IntegrityReport(
            success=False,
            total_checks=2,
            passed_checks=1,
            failed_checks=1,
            total_issues=5,
            total_duration_ms=25.0,
            results=results,
        )

        assert report.success is False
        assert report.passed_checks == 1
        assert report.failed_checks == 1
        assert report.total_issues == 5


class TestValidEnums:
    """Test that enum constants are defined correctly."""

    def test_valid_project_statuses(self) -> None:
        """VALID_PROJECT_STATUSES should contain expected values."""
        expected = {"active", "completed", "on_hold", "cancelled", "archived"}
        assert expected == VALID_PROJECT_STATUSES

    def test_valid_phase_statuses(self) -> None:
        """VALID_PHASE_STATUSES should contain expected values."""
        expected = {"pending", "in_progress", "completed", "blocked", "skipped"}
        assert expected == VALID_PHASE_STATUSES

    def test_valid_phases(self) -> None:
        """VALID_PHASES should contain expected workflow phases."""
        expected = {"discovery", "requirements", "implementation", "review", "launch"}
        assert expected == VALID_PHASES


class TestDataIntegrityValidator:
    """Test DataIntegrityValidator class."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def validator(self, mock_session: AsyncMock) -> DataIntegrityValidator:
        """Create a validator with mock session."""
        return DataIntegrityValidator(mock_session)

    @pytest.mark.asyncio
    async def test_run_check_success_no_issues(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """run_check should return success when no issues found."""
        # Mock empty result (no issues)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        result = await validator._run_check(
            check_name="test_check",
            table_name="test_table",
            query="SELECT * FROM test WHERE 1=0",
        )

        assert result.success is True
        assert result.issues_found == 0
        assert result.check_name == "test_check"
        assert result.table_name == "test_table"

    @pytest.mark.asyncio
    async def test_run_check_with_issues(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """run_check should return failure when issues found."""
        # Mock result with issues
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("row1",), ("row2",), ("row3",)]
        mock_session.execute.return_value = mock_result

        result = await validator._run_check(
            check_name="fk_check",
            table_name="orders",
            query="SELECT * FROM orphans",
        )

        assert result.success is False
        assert result.issues_found == 3
        assert len(result.details) == 3

    @pytest.mark.asyncio
    async def test_run_check_handles_sql_error(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """run_check should handle SQLAlchemy errors gracefully."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_session.execute.side_effect = SQLAlchemyError("Connection failed")

        with patch("app.core.data_integrity.db_logger") as mock_logger:
            result = await validator._run_check(
                check_name="error_check",
                table_name="test_table",
                query="SELECT * FROM nonexistent",
            )

        assert result.success is False
        assert result.issues_found == 1
        assert "Query error" in result.details[0]
        mock_logger.transaction_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_records(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """count_records should return row count."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (42,)
        mock_session.execute.return_value = mock_result

        count = await validator._count_records("projects")

        assert count == 42

    @pytest.mark.asyncio
    async def test_count_records_handles_error(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """count_records should return 0 on error."""
        from sqlalchemy.exc import SQLAlchemyError

        mock_session.execute.side_effect = SQLAlchemyError("Error")

        count = await validator._count_records("nonexistent")

        assert count == 0

    @pytest.mark.asyncio
    async def test_validate_all_aggregates_results(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """validate_all should run all checks and aggregate results."""
        # Mock all queries to return empty (no issues)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = (0,)
        mock_session.execute.return_value = mock_result

        report = await validator.validate_all()

        assert isinstance(report, IntegrityReport)
        assert report.total_checks > 0
        # All checks should pass with empty tables
        assert report.passed_checks == report.total_checks
        assert report.failed_checks == 0


class TestSlowQueryLogging:
    """Test that slow queries are logged correctly."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_slow_query_logged_at_warning(
        self, mock_session: AsyncMock
    ) -> None:
        """Slow queries (>100ms) should be logged at WARNING level."""
        validator = DataIntegrityValidator(mock_session)

        # Mock a slow query by making execute take time
        async def slow_execute(*args, **kwargs):
            import asyncio
            await asyncio.sleep(0.15)  # 150ms
            result = MagicMock()
            result.fetchall.return_value = []
            return result

        mock_session.execute = slow_execute

        with patch("app.core.data_integrity.db_logger") as mock_logger:
            await validator._run_check(
                check_name="slow_check",
                table_name="big_table",
                query="SELECT * FROM big_table",
            )

            # Should log slow query
            mock_logger.slow_query.assert_called_once()
            call_kwargs = mock_logger.slow_query.call_args.kwargs
            assert call_kwargs["table"] == "big_table"
            assert call_kwargs["duration_ms"] > 100


class TestForeignKeyValidation:
    """Test foreign key validation methods."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def validator(self, mock_session: AsyncMock) -> DataIntegrityValidator:
        """Create a validator with mock session."""
        return DataIntegrityValidator(mock_session)

    @pytest.mark.asyncio
    async def test_crawled_pages_fk_validation(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """Should validate crawled_pages reference existing projects."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = (10,)
        mock_session.execute.return_value = mock_result

        result = await validator._validate_crawled_pages_project_fk()

        assert result.check_name == "crawled_pages_project_fk"
        assert result.table_name == "crawled_pages"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_page_keywords_fk_validation(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """Should validate page_keywords reference existing crawled_pages."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = (5,)
        mock_session.execute.return_value = mock_result

        result = await validator._validate_page_keywords_page_fk()

        assert result.check_name == "page_keywords_page_fk"
        assert result.table_name == "page_keywords"


class TestDataTypeValidation:
    """Test data type validation methods."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def validator(self, mock_session: AsyncMock) -> DataIntegrityValidator:
        """Create a validator with mock session."""
        return DataIntegrityValidator(mock_session)

    @pytest.mark.asyncio
    async def test_uuid_format_validation(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """Should validate UUID format is correct."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = (3,)
        mock_session.execute.return_value = mock_result

        result = await validator._validate_project_uuid_format()

        assert result.check_name == "project_uuid_format"
        assert result.table_name == "projects"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_status_enum_validation(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """Should validate status enum values."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = (3,)
        mock_session.execute.return_value = mock_result

        result = await validator._validate_project_status_enum()

        assert result.check_name == "project_status_enum"
        assert result.success is True


class TestTimestampValidation:
    """Test timestamp ordering validation."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def validator(self, mock_session: AsyncMock) -> DataIntegrityValidator:
        """Create a validator with mock session."""
        return DataIntegrityValidator(mock_session)

    @pytest.mark.asyncio
    async def test_timestamp_ordering(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """Should validate created_at <= updated_at."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = (10,)
        mock_session.execute.return_value = mock_result

        result = await validator._validate_timestamp_ordering("projects")

        assert result.check_name == "projects_timestamp_order"
        assert result.table_name == "projects"
        assert result.success is True


class TestNumericRangeValidation:
    """Test numeric range validation."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock()

    @pytest.fixture
    def validator(self, mock_session: AsyncMock) -> DataIntegrityValidator:
        """Create a validator with mock session."""
        return DataIntegrityValidator(mock_session)

    @pytest.mark.asyncio
    async def test_difficulty_score_range(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """Should validate difficulty_score is 0-100."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = (20,)
        mock_session.execute.return_value = mock_result

        result = await validator._validate_keyword_difficulty_range()

        assert result.check_name == "keyword_difficulty_range"
        assert result.table_name == "page_keywords"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_difficulty_score_out_of_range_detected(
        self, validator: DataIntegrityValidator, mock_session: AsyncMock
    ) -> None:
        """Should detect difficulty_score outside 0-100."""
        mock_result = MagicMock()
        # Return rows with invalid scores
        mock_result.fetchall.return_value = [("id1", 150), ("id2", -5)]
        mock_result.fetchone.return_value = (20,)
        mock_session.execute.return_value = mock_result

        result = await validator._validate_keyword_difficulty_range()

        assert result.success is False
        assert result.issues_found == 2


class TestValidateDataIntegrityFunction:
    """Test the module-level validate_data_integrity function."""

    @pytest.mark.asyncio
    async def test_validate_data_integrity_creates_validator(self) -> None:
        """validate_data_integrity should create validator and run all checks."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = (0,)
        mock_session.execute.return_value = mock_result

        report = await validate_data_integrity(mock_session)

        assert isinstance(report, IntegrityReport)
        assert report.total_checks > 0


class TestLoggingRequirements:
    """Test that logging meets error logging requirements."""

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        """Create a mock async session."""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_validation_failure_logged_with_table_name(
        self, mock_session: AsyncMock
    ) -> None:
        """Failed validations should include table name in logs."""
        validator = DataIntegrityValidator(mock_session)

        # Mock a failed validation
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("orphan_row",)]
        mock_session.execute.return_value = mock_result

        with patch("app.core.data_integrity.logger") as mock_logger:
            await validator._run_check(
                check_name="fk_check",
                table_name="orders",
                query="SELECT * FROM orphans",
            )

            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args.kwargs
            assert call_kwargs["extra"]["table"] == "orders"

    @pytest.mark.asyncio
    async def test_successful_validation_logged_at_info(
        self, mock_session: AsyncMock
    ) -> None:
        """Successful validation should log at INFO level."""
        validator = DataIntegrityValidator(mock_session)

        # Mock all success
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.fetchone.return_value = (0,)
        mock_session.execute.return_value = mock_result

        with patch("app.core.data_integrity.logger") as mock_logger:
            await validator.validate_all()

            # Should log success at INFO level
            info_calls = [
                call for call in mock_logger.info.call_args_list
                if "successfully" in str(call)
            ]
            assert len(info_calls) > 0

    @pytest.mark.asyncio
    async def test_failed_validation_logged_at_error(
        self, mock_session: AsyncMock
    ) -> None:
        """Failed validation should log at ERROR level."""
        validator = DataIntegrityValidator(mock_session)

        # Mock a failure
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [("bad_row",)]
        mock_result.fetchone.return_value = (1,)
        mock_session.execute.return_value = mock_result

        with patch("app.core.data_integrity.logger") as mock_logger:
            await validator.validate_all()

            # Should log failure at ERROR level
            mock_logger.error.assert_called()
