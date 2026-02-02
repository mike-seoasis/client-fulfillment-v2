"""POP Content Score service for scoring content against POP API.

Fetches content scoring data from PageOptimizer Pro API and manages storage.
Content scores provide page score, keyword analysis, LSI coverage, heading
analysis, and recommendations for content optimization.

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.pop import (
    POPClient,
    POPError,
    get_pop_client,
)

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000


@dataclass
class POPContentScoreResult:
    """Result of a POP content score operation."""

    success: bool
    keyword: str
    content_url: str
    task_id: str | None = None
    score_id: str | None = None  # Database record ID after persistence
    page_score: float | None = None
    passed: bool | None = None
    keyword_analysis: dict[str, Any] = field(default_factory=dict)
    lsi_coverage: dict[str, Any] = field(default_factory=dict)
    word_count_current: int | None = None
    heading_analysis: dict[str, Any] = field(default_factory=dict)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    fallback_used: bool = False
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


class POPContentScoreServiceError(Exception):
    """Base exception for POP content score service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class POPContentScoreValidationError(POPContentScoreServiceError):
    """Raised when validation fails."""

    def __init__(
        self,
        field_name: str,
        value: str,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Validation error for {field_name}: {message}", project_id, page_id
        )
        self.field_name = field_name
        self.value = value


class POPContentScoreService:
    """Service for scoring content using POP API.

    Features:
    - Scores content against PageOptimizer Pro API
    - Creates POP tasks and polls for results
    - Parses and normalizes score data
    - Comprehensive logging per requirements

    Usage:
        service = POPContentScoreService()
        result = await service.score_content(
            project_id="uuid",
            page_id="uuid",
            keyword="best hiking boots",
            content_url="https://example.com/hiking-boots",
        )
    """

    def __init__(
        self,
        client: POPClient | None = None,
    ) -> None:
        """Initialize POP content score service.

        Args:
            client: POP client instance. If None, uses global instance.
        """
        self._client = client

        logger.debug(
            "POPContentScoreService initialized",
            extra={
                "client_provided": client is not None,
            },
        )

    async def _get_client(self) -> POPClient:
        """Get POP client instance."""
        if self._client is None:
            self._client = await get_pop_client()
        return self._client

    async def score_content(
        self,
        project_id: str,
        page_id: str,
        keyword: str,
        content_url: str,
    ) -> POPContentScoreResult:
        """Score content from POP API for a keyword/URL.

        Creates a POP scoring task, polls for completion, and parses
        the results into a structured content score.

        Args:
            project_id: Project ID for logging context
            page_id: Page ID for logging context
            keyword: Target keyword for scoring
            content_url: URL of the content to score

        Returns:
            POPContentScoreResult with score data or error
        """
        start_time = time.monotonic()

        # Method entry log with sanitized parameters
        logger.debug(
            "score_content method entry",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "keyword": keyword[:50] if keyword else "",
                "content_url": content_url[:100] if content_url else "",
            },
        )

        # Validate inputs
        if not keyword or not keyword.strip():
            logger.warning(
                "Content score validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise POPContentScoreValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        if not content_url or not content_url.strip():
            logger.warning(
                "Content score validation failed - empty content_url",
                extra={
                    "field": "content_url",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise POPContentScoreValidationError(
                "content_url",
                "",
                "Content URL cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        keyword = keyword.strip()
        content_url = content_url.strip()

        try:
            client = await self._get_client()

            # Phase transition: score_started
            logger.info(
                "score_started",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "content_url": content_url[:100],
                },
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            # Placeholder: Actual POP API scoring integration will be implemented
            # in future stories. This story only creates the service structure.
            logger.info(
                "score_completed",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "success": True,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow content score operation",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            result = POPContentScoreResult(
                success=True,
                keyword=keyword,
                content_url=content_url,
                duration_ms=duration_ms,
            )

            # Method exit log with result summary
            logger.debug(
                "score_content method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "success": True,
                    "score_id": None,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            # Store reference to client to suppress unused variable warning
            _ = client

            return result

        except POPContentScoreValidationError:
            raise
        except POPError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "POP API error during content scoring",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Method exit log on error
            logger.debug(
                "score_content method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "success": False,
                    "score_id": None,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return POPContentScoreResult(
                success=False,
                keyword=keyword,
                content_url=content_url,
                error=str(e),
                duration_ms=duration_ms,
                request_id=getattr(e, "request_id", None),
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Unexpected error during content scoring",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            # Method exit log on unexpected error
            logger.debug(
                "score_content method exit",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "success": False,
                    "score_id": None,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
            )
            return POPContentScoreResult(
                success=False,
                keyword=keyword,
                content_url=content_url,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
            )


# Global singleton instance
_pop_content_score_service: POPContentScoreService | None = None


def get_pop_content_score_service() -> POPContentScoreService:
    """Get the global POP content score service instance.

    Usage:
        from app.services.pop_content_score import get_pop_content_score_service
        service = get_pop_content_score_service()
        result = await service.score_content(
            project_id="uuid",
            page_id="uuid",
            keyword="hiking boots",
            content_url="https://example.com/hiking-boots",
        )
    """
    global _pop_content_score_service
    if _pop_content_score_service is None:
        _pop_content_score_service = POPContentScoreService()
        logger.info("POPContentScoreService singleton created")
    return _pop_content_score_service


async def score_content(
    project_id: str,
    page_id: str,
    keyword: str,
    content_url: str,
) -> POPContentScoreResult:
    """Convenience function for scoring content.

    Args:
        project_id: Project ID for logging context
        page_id: Page ID for logging context
        keyword: Target keyword for scoring
        content_url: URL of the content to score

    Returns:
        POPContentScoreResult with score data or error
    """
    service = get_pop_content_score_service()
    return await service.score_content(
        project_id=project_id,
        page_id=page_id,
        keyword=keyword,
        content_url=content_url,
    )
