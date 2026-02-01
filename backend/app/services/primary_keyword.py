"""PrimaryKeywordService for selecting the primary keyword from specific keywords.

Implements Step 5 of the keyword research workflow: selecting the primary keyword
as the highest-volume SPECIFIC keyword.

The primary keyword is CRITICAL because:
- It's used as the collection's main H1 heading
- It appears in the title tag and meta description
- It's the most important keyword for SEO ranking
- It must be SPECIFIC (not generic) to convert visitors

Selection criteria:
- Input: List of SPECIFIC keywords (output from Step 4 specificity filter)
- Logic: Select the keyword with the highest search volume
- Tie-breaker: Prefer shorter keywords (more concise)

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.keyword_volume import KeywordVolumeData

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000


class PrimaryKeywordServiceError(Exception):
    """Base exception for PrimaryKeywordService errors."""

    pass


class PrimaryKeywordValidationError(PrimaryKeywordServiceError):
    """Raised when input validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class PrimaryKeywordSelectionError(PrimaryKeywordServiceError):
    """Raised when primary keyword selection fails."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ):
        self.project_id = project_id
        self.page_id = page_id
        super().__init__(message)


@dataclass
class PrimaryKeywordRequest:
    """Request for primary keyword selection.

    Attributes:
        collection_title: Title of the collection (for logging/context)
        specific_keywords: List of SPECIFIC keywords with volume data (from Step 4)
        used_primaries: Set of keywords already used as primary elsewhere (to avoid duplicates)
        project_id: Project ID for logging
        page_id: Page ID for logging
    """

    collection_title: str
    specific_keywords: list[KeywordVolumeData]
    used_primaries: set[str] = field(default_factory=set)
    project_id: str | None = None
    page_id: str | None = None


@dataclass
class PrimaryKeywordResult:
    """Result of primary keyword selection.

    Attributes:
        success: Whether selection succeeded
        primary_keyword: The selected primary keyword (highest volume specific)
        primary_volume: Search volume of the primary keyword
        candidate_count: Number of candidate keywords considered
        error: Error message if failed
        duration_ms: Total time taken
        project_id: Project ID (for logging context)
        page_id: Page ID (for logging context)
    """

    success: bool
    primary_keyword: str | None = None
    primary_volume: int | None = None
    candidate_count: int = 0
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "primary_keyword": self.primary_keyword,
            "primary_volume": self.primary_volume,
            "candidate_count": self.candidate_count,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class PrimaryKeywordService:
    """Service for selecting the primary keyword from specific keywords.

    The primary keyword is the HIGHEST VOLUME keyword from the list of
    SPECIFIC keywords (output from Step 4 specificity filter).

    Selection algorithm:
    1. Filter out keywords with no volume data (volume is None or 0)
    2. Sort by volume descending
    3. For ties, prefer shorter keywords (more concise)
    4. Return the top keyword as the primary

    Why highest volume?
    - Primary keyword is used in H1, title tag, meta description
    - Higher volume = more potential traffic
    - Specificity is already guaranteed by Step 4 filter

    Example usage:
        service = PrimaryKeywordService()

        # Specific keywords from Step 4
        specific_keywords = [
            KeywordVolumeData(keyword="airtight coffee containers", volume=1500),
            KeywordVolumeData(keyword="vacuum coffee canister", volume=800),
            KeywordVolumeData(keyword="coffee bean storage container", volume=2000),
        ]

        result = await service.select_primary(
            collection_title="Coffee Containers",
            specific_keywords=specific_keywords,
            project_id="abc-123",
            page_id="page-456",
        )

        # Result: "coffee bean storage container" (highest volume at 2000)
    """

    def __init__(self) -> None:
        """Initialize the primary keyword service."""
        logger.debug("PrimaryKeywordService.__init__ called")
        logger.debug("PrimaryKeywordService initialized")

    def _normalize_keyword(self, keyword: str) -> str:
        """Normalize a keyword for comparison.

        Args:
            keyword: Keyword to normalize

        Returns:
            Normalized keyword (lowercase, stripped, single spaces)
        """
        return " ".join(keyword.lower().strip().split())

    def _sort_key(self, keyword: KeywordVolumeData) -> tuple[int, int]:
        """Generate sort key for keyword selection.

        Sort by:
        1. Volume descending (negate for descending sort)
        2. Keyword length ascending (prefer shorter keywords for ties)

        Args:
            keyword: KeywordVolumeData to generate key for

        Returns:
            Tuple of (negated_volume, keyword_length) for sorting
        """
        volume = keyword.volume if keyword.volume is not None else 0
        return (-volume, len(keyword.keyword))

    async def select_primary(
        self,
        collection_title: str,
        specific_keywords: list[KeywordVolumeData],
        used_primaries: set[str] | None = None,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> PrimaryKeywordResult:
        """Select the primary keyword from a list of specific keywords.

        The primary keyword is the highest-volume keyword from the
        list of SPECIFIC keywords (already filtered by Step 4).

        Args:
            collection_title: Title of the collection (for logging/context)
            specific_keywords: SPECIFIC keywords with volume data (from Step 4)
            used_primaries: Set of keywords already used as primary elsewhere (to avoid)
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            PrimaryKeywordResult with the selected primary keyword
        """
        start_time = time.monotonic()
        candidate_count = len(specific_keywords)

        # Normalize used_primaries for comparison
        if used_primaries is None:
            used_primaries = set()
        normalized_used_primaries = {
            self._normalize_keyword(kw) for kw in used_primaries
        }

        logger.debug(
            "select_primary() called",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "collection_title": collection_title[:100] if collection_title else "",
                "candidate_count": candidate_count,
                "used_primaries_count": len(used_primaries),
            },
        )

        # Validate inputs
        if not collection_title or not collection_title.strip():
            logger.warning(
                "Validation failed: empty collection_title",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "field": "collection_title",
                    "rejected_value": repr(collection_title),
                },
            )
            return PrimaryKeywordResult(
                success=False,
                error="Collection title cannot be empty",
                candidate_count=0,
                project_id=project_id,
                page_id=page_id,
            )

        if not specific_keywords:
            logger.warning(
                "Validation failed: empty specific_keywords list",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "field": "specific_keywords",
                    "rejected_value": "[]",
                },
            )
            return PrimaryKeywordResult(
                success=False,
                error="No specific keywords provided for selection",
                candidate_count=0,
                project_id=project_id,
                page_id=page_id,
            )

        try:
            # Filter keywords with valid volume data, excluding used primaries
            keywords_with_volume = [
                kw for kw in specific_keywords
                if (
                    kw.volume is not None
                    and kw.volume > 0
                    and self._normalize_keyword(kw.keyword)
                    not in normalized_used_primaries
                )
            ]

            # Count how many were skipped due to being used elsewhere
            skipped_used_primaries = [
                kw for kw in specific_keywords
                if (
                    kw.volume is not None
                    and kw.volume > 0
                    and self._normalize_keyword(kw.keyword)
                    in normalized_used_primaries
                )
            ]

            if skipped_used_primaries:
                logger.debug(
                    "Skipped keywords already used as primary elsewhere",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "skipped_count": len(skipped_used_primaries),
                        "skipped_keywords": [kw.keyword for kw in skipped_used_primaries[:5]],
                    },
                )

            if not keywords_with_volume:
                # No keywords with volume - fall back to first unused keyword
                # Filter out used primaries from fallback candidates too
                fallback_candidates = [
                    kw for kw in specific_keywords
                    if self._normalize_keyword(kw.keyword)
                    not in normalized_used_primaries
                ]

                if not fallback_candidates:
                    # All keywords are already used as primaries elsewhere
                    duration_ms = (time.monotonic() - start_time) * 1000
                    logger.warning(
                        "No available keywords - all are used as primaries elsewhere",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "collection_title": collection_title[:100],
                            "candidate_count": candidate_count,
                            "used_primaries_count": len(used_primaries),
                            "duration_ms": round(duration_ms, 2),
                        },
                    )
                    return PrimaryKeywordResult(
                        success=False,
                        error="No available keywords - all are used as primaries elsewhere",
                        candidate_count=candidate_count,
                        duration_ms=round(duration_ms, 2),
                        project_id=project_id,
                        page_id=page_id,
                    )

                logger.warning(
                    "No keywords with volume data, falling back to first unused keyword",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "collection_title": collection_title[:100],
                        "candidate_count": candidate_count,
                        "fallback_candidates": len(fallback_candidates),
                    },
                )

                # Use first unused keyword as fallback
                primary = fallback_candidates[0]
                duration_ms = (time.monotonic() - start_time) * 1000

                logger.info(
                    "Primary keyword selected (fallback - no volume data)",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "collection_title": collection_title[:100],
                        "primary_keyword": primary.keyword,
                        "primary_volume": primary.volume,
                        "candidate_count": candidate_count,
                        "selection_reason": "fallback_no_volume",
                        "duration_ms": round(duration_ms, 2),
                    },
                )

                return PrimaryKeywordResult(
                    success=True,
                    primary_keyword=primary.keyword,
                    primary_volume=primary.volume,
                    candidate_count=candidate_count,
                    duration_ms=round(duration_ms, 2),
                    project_id=project_id,
                    page_id=page_id,
                )

            # Sort by volume descending, then by keyword length ascending
            sorted_keywords = sorted(keywords_with_volume, key=self._sort_key)

            # Select the top keyword (highest volume, shortest if tie)
            primary = sorted_keywords[0]

            duration_ms = (time.monotonic() - start_time) * 1000

            # Log the top candidates for debugging
            top_candidates = [
                {"keyword": kw.keyword, "volume": kw.volume}
                for kw in sorted_keywords[:5]
            ]

            # Log state transition: primary keyword selected
            logger.info(
                "Primary keyword selected",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "collection_title": collection_title[:100],
                    "primary_keyword": primary.keyword,
                    "primary_volume": primary.volume,
                    "candidate_count": candidate_count,
                    "keywords_with_volume": len(keywords_with_volume),
                    "top_candidates": top_candidates,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow primary keyword selection",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "duration_ms": round(duration_ms, 2),
                        "candidate_count": candidate_count,
                    },
                )

            return PrimaryKeywordResult(
                success=True,
                primary_keyword=primary.keyword,
                primary_volume=primary.volume,
                candidate_count=candidate_count,
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Primary keyword selection exception",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return PrimaryKeywordResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                candidate_count=candidate_count,
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

    async def select_primary_for_request(
        self,
        request: PrimaryKeywordRequest,
    ) -> PrimaryKeywordResult:
        """Select primary keyword using a PrimaryKeywordRequest object.

        Convenience method that unpacks a PrimaryKeywordRequest.

        Args:
            request: The primary keyword request

        Returns:
            PrimaryKeywordResult with the selected primary keyword
        """
        return await self.select_primary(
            collection_title=request.collection_title,
            specific_keywords=request.specific_keywords,
            used_primaries=request.used_primaries,
            project_id=request.project_id,
            page_id=request.page_id,
        )


# Global PrimaryKeywordService instance
_primary_keyword_service: PrimaryKeywordService | None = None


def get_primary_keyword_service() -> PrimaryKeywordService:
    """Get the default PrimaryKeywordService instance (singleton).

    Returns:
        Default PrimaryKeywordService instance.
    """
    global _primary_keyword_service
    if _primary_keyword_service is None:
        _primary_keyword_service = PrimaryKeywordService()
        logger.info("PrimaryKeywordService singleton created")
    return _primary_keyword_service


async def select_primary_keyword(
    collection_title: str,
    specific_keywords: list[KeywordVolumeData],
    used_primaries: set[str] | None = None,
    project_id: str | None = None,
    page_id: str | None = None,
) -> PrimaryKeywordResult:
    """Convenience function to select the primary keyword.

    Uses the default PrimaryKeywordService singleton.

    Args:
        collection_title: Title of the collection
        specific_keywords: SPECIFIC keywords with volume data (from Step 4)
        used_primaries: Set of keywords already used as primary elsewhere (to avoid)
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        PrimaryKeywordResult with the selected primary keyword

    Example:
        >>> from app.services.keyword_volume import KeywordVolumeData
        >>> keywords = [
        ...     KeywordVolumeData(keyword="airtight coffee containers", volume=1500),
        ...     KeywordVolumeData(keyword="coffee bean storage", volume=2000),
        ...     KeywordVolumeData(keyword="vacuum coffee canister", volume=800),
        ... ]
        >>> result = await select_primary_keyword(
        ...     collection_title="Coffee Containers",
        ...     specific_keywords=keywords,
        ...     used_primaries={"espresso machine parts"},  # Exclude already-used primaries
        ...     project_id="abc-123",
        ... )
        >>> print(result.primary_keyword)
        'coffee bean storage'
    """
    service = get_primary_keyword_service()
    return await service.select_primary(
        collection_title=collection_title,
        specific_keywords=specific_keywords,
        used_primaries=used_primaries,
        project_id=project_id,
        page_id=page_id,
    )
