"""Phase 5C: Word count validation service.

Validates that generated content meets word count requirements (300-450 words).
Part of Phase 5C quality assurance along with AI trope detection and link validation.

Features:
- Word count validation against configurable min/max thresholds
- HTML tag stripping for accurate counting
- Batch checking support
- Detailed feedback with suggestions

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import re
import time
import traceback
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000

# Word count thresholds (for bottom_description)
WORD_COUNT_MIN = 300
WORD_COUNT_MAX = 450


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class WordCountCheckResult:
    """Result of a single word count check."""

    field_name: str
    word_count: int
    min_required: int
    max_allowed: int
    is_valid: bool
    error: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "field_name": self.field_name,
            "word_count": self.word_count,
            "min_required": self.min_required,
            "max_allowed": self.max_allowed,
            "is_valid": self.is_valid,
            "error": self.error,
            "suggestion": self.suggestion,
        }


@dataclass
class ContentWordCountInput:
    """Input data for word count validation."""

    content: str
    field_name: str = "bottom_description"
    project_id: str | None = None
    page_id: str | None = None
    content_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging (sanitized)."""
        return {
            "content_length": len(self.content),
            "field_name": self.field_name,
            "project_id": self.project_id,
            "page_id": self.page_id,
            "content_id": self.content_id,
        }


@dataclass
class ContentWordCountResult:
    """Result of Phase 5C word count validation."""

    success: bool
    content_id: str | None = None
    field_name: str | None = None
    word_count: int = 0
    min_required: int = WORD_COUNT_MIN
    max_allowed: int = WORD_COUNT_MAX
    is_valid: bool = False
    error: str | None = None
    suggestion: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "content_id": self.content_id,
            "field_name": self.field_name,
            "word_count": self.word_count,
            "min_required": self.min_required,
            "max_allowed": self.max_allowed,
            "is_valid": self.is_valid,
            "error": self.error,
            "suggestion": self.suggestion,
            "duration_ms": round(self.duration_ms, 2),
            "project_id": self.project_id,
            "page_id": self.page_id,
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================


class ContentWordCountServiceError(Exception):
    """Base exception for word count service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class ContentWordCountValidationError(ContentWordCountServiceError):
    """Raised when validation fails."""

    def __init__(
        self,
        field_name: str,
        value: Any,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Validation error for {field_name}: {message}", project_id, page_id
        )
        self.field_name = field_name
        self.value = value


# =============================================================================
# SERVICE
# =============================================================================


class ContentWordCountService:
    """Service for Phase 5C word count validation.

    Validates that generated content meets word count requirements:
    - bottom_description must be 300-450 words

    Usage:
        service = ContentWordCountService()
        result = await service.check_word_count(
            input_data=ContentWordCountInput(
                content="<p>Your HTML content here...</p>",
                field_name="bottom_description",
            ),
        )
    """

    def __init__(self) -> None:
        """Initialize word count service."""
        # Pre-compile regex for HTML tag stripping
        self._html_tag_pattern = re.compile(r"<[^>]+>")
        logger.debug("ContentWordCountService initialized")

    def _strip_html_tags(self, text: str) -> str:
        """Remove HTML tags from text for word counting.

        Args:
            text: Text with potential HTML tags

        Returns:
            Clean text without HTML tags
        """
        return self._html_tag_pattern.sub(" ", text)

    def _count_words(self, text: str) -> int:
        """Count words in text after stripping HTML tags.

        Args:
            text: Text to count words in (may contain HTML)

        Returns:
            Number of words in the text
        """
        clean_text = self._strip_html_tags(text)
        # Split on whitespace and filter empty strings
        words = [w for w in clean_text.split() if w.strip()]
        return len(words)

    def _validate_word_count(
        self,
        text: str,
        field_name: str,
        project_id: str | None,
        page_id: str | None,
    ) -> WordCountCheckResult:
        """Validate word count for a field.

        Args:
            text: Text content to validate
            field_name: Name of the field being validated
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            WordCountCheckResult with validation details
        """
        word_count = self._count_words(text)
        is_valid = WORD_COUNT_MIN <= word_count <= WORD_COUNT_MAX

        error = None
        suggestion = None

        if not is_valid:
            if word_count < WORD_COUNT_MIN:
                diff = WORD_COUNT_MIN - word_count
                error = f"Word count too low: {word_count} words (minimum {WORD_COUNT_MIN} required)"
                suggestion = f"Add approximately {diff} more words to meet the minimum requirement."
            else:
                diff = word_count - WORD_COUNT_MAX
                error = f"Word count too high: {word_count} words (maximum {WORD_COUNT_MAX} allowed)"
                suggestion = f"Remove approximately {diff} words to meet the maximum limit."

            logger.warning(
                "Word count validation failed",
                extra={
                    "field": field_name,
                    "word_count": word_count,
                    "min_required": WORD_COUNT_MIN,
                    "max_allowed": WORD_COUNT_MAX,
                    "rejected_value": f"{word_count} words",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

        return WordCountCheckResult(
            field_name=field_name,
            word_count=word_count,
            min_required=WORD_COUNT_MIN,
            max_allowed=WORD_COUNT_MAX,
            is_valid=is_valid,
            error=error,
            suggestion=suggestion,
        )

    async def check_word_count(
        self,
        input_data: ContentWordCountInput,
    ) -> ContentWordCountResult:
        """Validate word count for content.

        Phase 5C word count validation:
        1. Strip HTML tags from content
        2. Count words
        3. Validate against min/max thresholds
        4. Generate suggestions if failed

        Args:
            input_data: Content to validate

        Returns:
            ContentWordCountResult with validation results
        """
        start_time = time.monotonic()
        project_id = input_data.project_id
        page_id = input_data.page_id
        content_id = input_data.content_id
        field_name = input_data.field_name

        logger.debug(
            "Phase 5C word count check starting",
            extra={
                "content_id": content_id,
                "field_name": field_name,
                "content_length": len(input_data.content),
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate inputs
        if not input_data.content or not input_data.content.strip():
            logger.warning(
                "Word count validation failed - empty content",
                extra={
                    "field": field_name,
                    "rejected_value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise ContentWordCountValidationError(
                field_name,
                "",
                "Content cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        try:
            # Log phase transition
            logger.info(
                "Phase 5C: Word count validation - in_progress",
                extra={
                    "content_id": content_id,
                    "field_name": field_name,
                    "phase": "5C",
                    "status": "in_progress",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Run validation
            result = self._validate_word_count(
                input_data.content,
                field_name,
                project_id,
                page_id,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log completion
            logger.info(
                "Phase 5C: Word count validation - completed",
                extra={
                    "content_id": content_id,
                    "field_name": field_name,
                    "word_count": result.word_count,
                    "is_valid": result.is_valid,
                    "phase": "5C",
                    "status": "completed",
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow Phase 5C word count check operation",
                    extra={
                        "content_id": content_id,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            return ContentWordCountResult(
                success=True,
                content_id=content_id,
                field_name=field_name,
                word_count=result.word_count,
                min_required=result.min_required,
                max_allowed=result.max_allowed,
                is_valid=result.is_valid,
                error=result.error,
                suggestion=result.suggestion,
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

        except ContentWordCountValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Phase 5C word count validation unexpected error",
                extra={
                    "content_id": content_id,
                    "field_name": field_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return ContentWordCountResult(
                success=False,
                content_id=content_id,
                field_name=field_name,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

    async def check_word_count_batch(
        self,
        inputs: list[ContentWordCountInput],
        project_id: str | None = None,
    ) -> list[ContentWordCountResult]:
        """Check word count for multiple content items.

        Note: This runs synchronously since word count checks are fast (no I/O).
        Parallelization overhead would exceed the benefit.

        Args:
            inputs: List of content items to check
            project_id: Project ID for logging

        Returns:
            List of ContentWordCountResult, one per input
        """
        start_time = time.monotonic()

        logger.info(
            "Batch word count check started",
            extra={
                "input_count": len(inputs),
                "project_id": project_id,
            },
        )

        if not inputs:
            return []

        results: list[ContentWordCountResult] = []
        for input_data in inputs:
            try:
                result = await self.check_word_count(input_data)
                results.append(result)
            except ContentWordCountValidationError as e:
                # For batch, we catch validation errors and return failure result
                results.append(
                    ContentWordCountResult(
                        success=False,
                        content_id=input_data.content_id,
                        field_name=input_data.field_name,
                        error=str(e),
                        project_id=input_data.project_id,
                        page_id=input_data.page_id,
                    )
                )

        duration_ms = (time.monotonic() - start_time) * 1000
        success_count = sum(1 for r in results if r.success)
        valid_count = sum(1 for r in results if r.is_valid)

        logger.info(
            "Batch word count check complete",
            extra={
                "input_count": len(inputs),
                "success_count": success_count,
                "failure_count": len(inputs) - success_count,
                "valid_count": valid_count,
                "invalid_count": len(inputs) - valid_count,
                "duration_ms": round(duration_ms, 2),
                "project_id": project_id,
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch word count check operation",
                extra={
                    "input_count": len(inputs),
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    "project_id": project_id,
                },
            )

        return results


# =============================================================================
# SINGLETON
# =============================================================================


_content_word_count_service: ContentWordCountService | None = None


def get_content_word_count_service() -> ContentWordCountService:
    """Get the global word count service instance.

    Usage:
        from app.services.content_word_count import get_content_word_count_service
        service = get_content_word_count_service()
        result = await service.check_word_count(input_data)
    """
    global _content_word_count_service
    if _content_word_count_service is None:
        _content_word_count_service = ContentWordCountService()
        logger.info("ContentWordCountService singleton created")
    return _content_word_count_service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def check_word_count(
    content: str,
    field_name: str = "bottom_description",
    project_id: str | None = None,
    page_id: str | None = None,
    content_id: str | None = None,
) -> ContentWordCountResult:
    """Convenience function for Phase 5C word count validation.

    Args:
        content: Content to validate (may contain HTML)
        field_name: Name of the field being validated
        project_id: Project ID for logging
        page_id: Page ID for logging
        content_id: Content ID for tracking

    Returns:
        ContentWordCountResult with validation results
    """
    service = get_content_word_count_service()
    input_data = ContentWordCountInput(
        content=content,
        field_name=field_name,
        project_id=project_id,
        page_id=page_id,
        content_id=content_id,
    )
    return await service.check_word_count(input_data)
