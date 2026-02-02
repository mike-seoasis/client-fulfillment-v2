"""POP Content Brief service for fetching and storing content briefs.

Fetches content brief data from PageOptimizer Pro API and manages storage.
Content briefs provide keyword targets, LSI terms, competitor data, and
optimization recommendations for content creation.

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
    POPTaskStatus,
    get_pop_client,
)

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000


@dataclass
class POPContentBriefResult:
    """Result of a POP content brief fetch operation."""

    success: bool
    keyword: str
    target_url: str
    task_id: str | None = None
    word_count_target: int | None = None
    word_count_min: int | None = None
    word_count_max: int | None = None
    heading_targets: list[dict[str, Any]] = field(default_factory=list)
    keyword_targets: list[dict[str, Any]] = field(default_factory=list)
    lsi_terms: list[dict[str, Any]] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    related_questions: list[dict[str, Any]] = field(default_factory=list)
    related_searches: list[dict[str, Any]] = field(default_factory=list)
    competitors: list[dict[str, Any]] = field(default_factory=list)
    page_score_target: float | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


class POPContentBriefServiceError(Exception):
    """Base exception for POP content brief service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class POPContentBriefValidationError(POPContentBriefServiceError):
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


class POPContentBriefService:
    """Service for fetching and storing POP content briefs.

    Features:
    - Fetches content briefs from PageOptimizer Pro API
    - Creates POP tasks and polls for results
    - Parses and normalizes brief data
    - Comprehensive logging per requirements

    Usage:
        service = POPContentBriefService()
        result = await service.fetch_brief(
            project_id="uuid",
            page_id="uuid",
            keyword="best hiking boots",
            target_url="https://example.com/hiking-boots",
        )
    """

    def __init__(
        self,
        client: POPClient | None = None,
    ) -> None:
        """Initialize POP content brief service.

        Args:
            client: POP client instance. If None, uses global instance.
        """
        self._client = client

        logger.debug(
            "POPContentBriefService initialized",
            extra={
                "client_provided": client is not None,
            },
        )

    async def _get_client(self) -> POPClient:
        """Get POP client instance."""
        if self._client is None:
            self._client = await get_pop_client()
        return self._client

    def _parse_brief_data(
        self,
        raw_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse raw POP API response into structured brief data.

        Args:
            raw_data: Raw API response data

        Returns:
            Dictionary with parsed brief fields
        """
        # Extract word count recommendations
        word_count = raw_data.get("word_count", {})
        if isinstance(word_count, dict):
            word_count_target = word_count.get("target") or word_count.get(
                "recommended"
            )
            word_count_min = word_count.get("min") or word_count.get("minimum")
            word_count_max = word_count.get("max") or word_count.get("maximum")
        else:
            word_count_target = raw_data.get("word_count_target")
            word_count_min = raw_data.get("word_count_min")
            word_count_max = raw_data.get("word_count_max")

        # Extract heading targets
        heading_targets = raw_data.get("heading_targets") or raw_data.get(
            "headings", []
        )
        if not isinstance(heading_targets, list):
            heading_targets = []

        # Extract keyword targets
        keyword_targets = raw_data.get("keyword_targets") or raw_data.get(
            "keywords", []
        )
        if not isinstance(keyword_targets, list):
            keyword_targets = []

        # Extract LSI terms
        lsi_terms = raw_data.get("lsi_terms") or raw_data.get("lsi", [])
        if not isinstance(lsi_terms, list):
            lsi_terms = []

        # Extract entities
        entities = raw_data.get("entities", [])
        if not isinstance(entities, list):
            entities = []

        # Extract related questions
        related_questions = raw_data.get("related_questions") or raw_data.get("paa", [])
        if not isinstance(related_questions, list):
            related_questions = []

        # Extract related searches
        related_searches = raw_data.get("related_searches", [])
        if not isinstance(related_searches, list):
            related_searches = []

        # Extract competitors
        competitors = raw_data.get("competitors") or raw_data.get("serp_results", [])
        if not isinstance(competitors, list):
            competitors = []

        # Extract page score target
        page_score_target = raw_data.get("page_score_target") or raw_data.get(
            "target_score"
        )

        return {
            "word_count_target": word_count_target,
            "word_count_min": word_count_min,
            "word_count_max": word_count_max,
            "heading_targets": heading_targets,
            "keyword_targets": keyword_targets,
            "lsi_terms": lsi_terms,
            "entities": entities,
            "related_questions": related_questions,
            "related_searches": related_searches,
            "competitors": competitors,
            "page_score_target": page_score_target,
        }

    async def fetch_brief(
        self,
        project_id: str,
        page_id: str,
        keyword: str,
        target_url: str,
    ) -> POPContentBriefResult:
        """Fetch a content brief from POP API for a keyword/URL.

        Creates a POP report task, polls for completion, and parses
        the results into a structured content brief.

        Args:
            project_id: Project ID for logging context
            page_id: Page ID for logging context
            keyword: Target keyword for content optimization
            target_url: URL of the page to optimize

        Returns:
            POPContentBriefResult with brief data or error
        """
        start_time = time.monotonic()

        logger.debug(
            "Fetching POP content brief",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "keyword": keyword[:50] if keyword else "",
                "target_url": target_url[:100] if target_url else "",
            },
        )

        # Validate inputs
        if not keyword or not keyword.strip():
            logger.warning(
                "Content brief validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise POPContentBriefValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        if not target_url or not target_url.strip():
            logger.warning(
                "Content brief validation failed - empty target_url",
                extra={
                    "field": "target_url",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise POPContentBriefValidationError(
                "target_url",
                "",
                "Target URL cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        keyword = keyword.strip()
        target_url = target_url.strip()

        try:
            client = await self._get_client()

            # Step 1: Create report task
            logger.info(
                "Creating POP report task for content brief",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                },
            )

            task_result = await client.create_report_task(
                keyword=keyword,
                url=target_url,
            )

            if not task_result.success or not task_result.task_id:
                duration_ms = (time.monotonic() - start_time) * 1000
                logger.error(
                    "Failed to create POP report task",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "error": task_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPContentBriefResult(
                    success=False,
                    keyword=keyword,
                    target_url=target_url,
                    error=task_result.error or "Failed to create report task",
                    duration_ms=duration_ms,
                    request_id=task_result.request_id,
                )

            task_id = task_result.task_id

            logger.info(
                "POP report task created, polling for results",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "task_id": task_id,
                },
            )

            # Step 2: Poll for task completion
            poll_result = await client.poll_for_result(task_id)

            if not poll_result.success:
                duration_ms = (time.monotonic() - start_time) * 1000
                logger.error(
                    "POP task polling failed",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "task_id": task_id,
                        "error": poll_result.error,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPContentBriefResult(
                    success=False,
                    keyword=keyword,
                    target_url=target_url,
                    task_id=task_id,
                    error=poll_result.error or "Task polling failed",
                    duration_ms=duration_ms,
                    request_id=poll_result.request_id,
                )

            if poll_result.status == POPTaskStatus.FAILURE:
                duration_ms = (time.monotonic() - start_time) * 1000
                error_msg = poll_result.data.get("error") if poll_result.data else None
                logger.error(
                    "POP task failed",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "task_id": task_id,
                        "error": error_msg,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return POPContentBriefResult(
                    success=False,
                    keyword=keyword,
                    target_url=target_url,
                    task_id=task_id,
                    error=error_msg or "Task failed",
                    raw_response=poll_result.data,
                    duration_ms=duration_ms,
                    request_id=poll_result.request_id,
                )

            # Step 3: Parse the response data
            raw_data = poll_result.data
            parsed = self._parse_brief_data(raw_data)

            duration_ms = (time.monotonic() - start_time) * 1000

            logger.info(
                "POP content brief fetched successfully",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "task_id": task_id,
                    "word_count_target": parsed.get("word_count_target"),
                    "lsi_terms_count": len(parsed.get("lsi_terms", [])),
                    "competitors_count": len(parsed.get("competitors", [])),
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow content brief fetch operation",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    },
                )

            return POPContentBriefResult(
                success=True,
                keyword=keyword,
                target_url=target_url,
                task_id=task_id,
                word_count_target=parsed.get("word_count_target"),
                word_count_min=parsed.get("word_count_min"),
                word_count_max=parsed.get("word_count_max"),
                heading_targets=parsed.get("heading_targets", []),
                keyword_targets=parsed.get("keyword_targets", []),
                lsi_terms=parsed.get("lsi_terms", []),
                entities=parsed.get("entities", []),
                related_questions=parsed.get("related_questions", []),
                related_searches=parsed.get("related_searches", []),
                competitors=parsed.get("competitors", []),
                page_score_target=parsed.get("page_score_target"),
                raw_response=raw_data,
                duration_ms=duration_ms,
                request_id=poll_result.request_id,
            )

        except POPContentBriefValidationError:
            raise
        except POPError as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "POP API error during content brief fetch",
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
            return POPContentBriefResult(
                success=False,
                keyword=keyword,
                target_url=target_url,
                error=str(e),
                duration_ms=duration_ms,
                request_id=getattr(e, "request_id", None),
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Unexpected error during content brief fetch",
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
            return POPContentBriefResult(
                success=False,
                keyword=keyword,
                target_url=target_url,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
            )


# Global singleton instance
_pop_content_brief_service: POPContentBriefService | None = None


def get_pop_content_brief_service() -> POPContentBriefService:
    """Get the global POP content brief service instance.

    Usage:
        from app.services.pop_content_brief import get_pop_content_brief_service
        service = get_pop_content_brief_service()
        result = await service.fetch_brief(
            project_id="uuid",
            page_id="uuid",
            keyword="hiking boots",
            target_url="https://example.com/hiking-boots",
        )
    """
    global _pop_content_brief_service
    if _pop_content_brief_service is None:
        _pop_content_brief_service = POPContentBriefService()
        logger.info("POPContentBriefService singleton created")
    return _pop_content_brief_service


async def fetch_content_brief(
    project_id: str,
    page_id: str,
    keyword: str,
    target_url: str,
) -> POPContentBriefResult:
    """Convenience function for fetching a content brief.

    Args:
        project_id: Project ID for logging context
        page_id: Page ID for logging context
        keyword: Target keyword for content optimization
        target_url: URL of the page to optimize

    Returns:
        POPContentBriefResult with brief data or error
    """
    service = get_pop_content_brief_service()
    return await service.fetch_brief(
        project_id=project_id,
        page_id=page_id,
        keyword=keyword,
        target_url=target_url,
    )
