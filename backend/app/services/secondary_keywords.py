"""SecondaryKeywordService for selecting secondary keywords from specific and broader terms.

Implements Step 6 of the keyword research workflow: selecting 3-5 secondary keywords
as a mix of specific and broader terms to complement the primary keyword.

Secondary keywords are important because:
- They provide additional ranking opportunities
- They capture related search intent
- They help with long-tail keyword coverage
- They should NOT duplicate the primary keyword

Selection criteria:
- 2-3 specific keywords (lower volume than primary, from Step 4 output)
- 1-2 broader terms with volume > 1000 (from all keywords)
- Avoid keywords already used as primary elsewhere

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

# Default configuration for secondary keyword selection
DEFAULT_MIN_SPECIFIC_KEYWORDS = 2
DEFAULT_MAX_SPECIFIC_KEYWORDS = 3
DEFAULT_MIN_BROADER_KEYWORDS = 1
DEFAULT_MAX_BROADER_KEYWORDS = 2
DEFAULT_BROADER_VOLUME_THRESHOLD = 1000
DEFAULT_TOTAL_SECONDARY_KEYWORDS = 5


class SecondaryKeywordServiceError(Exception):
    """Base exception for SecondaryKeywordService errors."""

    pass


class SecondaryKeywordValidationError(SecondaryKeywordServiceError):
    """Raised when input validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class SecondaryKeywordSelectionError(SecondaryKeywordServiceError):
    """Raised when secondary keyword selection fails."""

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
class SecondaryKeywordRequest:
    """Request for secondary keyword selection.

    Attributes:
        collection_title: Title of the collection (for logging/context)
        primary_keyword: The primary keyword (to exclude from secondaries)
        specific_keywords: List of SPECIFIC keywords with volume data (from Step 4)
        all_keywords: All keywords with volume data (for broader term selection)
        used_primaries: Set of keywords already used as primary elsewhere (to avoid)
        project_id: Project ID for logging
        page_id: Page ID for logging
        min_specific: Minimum specific keywords to select (default: 2)
        max_specific: Maximum specific keywords to select (default: 3)
        min_broader: Minimum broader keywords to select (default: 1)
        max_broader: Maximum broader keywords to select (default: 2)
        broader_volume_threshold: Minimum volume for broader terms (default: 1000)
    """

    collection_title: str
    primary_keyword: str
    specific_keywords: list[KeywordVolumeData]
    all_keywords: list[KeywordVolumeData]
    used_primaries: set[str] = field(default_factory=set)
    project_id: str | None = None
    page_id: str | None = None
    min_specific: int = DEFAULT_MIN_SPECIFIC_KEYWORDS
    max_specific: int = DEFAULT_MAX_SPECIFIC_KEYWORDS
    min_broader: int = DEFAULT_MIN_BROADER_KEYWORDS
    max_broader: int = DEFAULT_MAX_BROADER_KEYWORDS
    broader_volume_threshold: int = DEFAULT_BROADER_VOLUME_THRESHOLD


@dataclass
class SecondaryKeywordResult:
    """Result of secondary keyword selection.

    Attributes:
        success: Whether selection succeeded
        secondary_keywords: The selected secondary keywords with volume data
        specific_count: Number of specific keywords selected
        broader_count: Number of broader keywords selected
        total_count: Total number of secondary keywords selected
        error: Error message if failed
        duration_ms: Total time taken
        project_id: Project ID (for logging context)
        page_id: Page ID (for logging context)
    """

    success: bool
    secondary_keywords: list[KeywordVolumeData] = field(default_factory=list)
    specific_count: int = 0
    broader_count: int = 0
    total_count: int = 0
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "secondary_keywords": [
                {
                    "keyword": kw.keyword,
                    "volume": kw.volume,
                    "cpc": kw.cpc,
                    "competition": kw.competition,
                }
                for kw in self.secondary_keywords
            ],
            "specific_count": self.specific_count,
            "broader_count": self.broader_count,
            "total_count": self.total_count,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class SecondaryKeywordService:
    """Service for selecting secondary keywords from specific and broader terms.

    Secondary keywords complement the primary keyword by providing
    additional ranking opportunities and capturing related search intent.

    Selection algorithm:
    1. From SPECIFIC keywords (Step 4 output):
       - Exclude the primary keyword
       - Exclude keywords already used as primary elsewhere
       - Sort by volume descending
       - Select 2-3 specific keywords

    2. From ALL keywords (broader terms):
       - Exclude already selected keywords
       - Exclude keywords already used as primary elsewhere
       - Filter to volume > 1000
       - Sort by volume descending
       - Select 1-2 broader keywords

    Why this mix?
    - Specific keywords target highly relevant, converting traffic
    - Broader keywords capture higher-volume, related searches
    - Together they provide comprehensive keyword coverage

    Example usage:
        service = SecondaryKeywordService()

        result = await service.select_secondary(
            collection_title="Coffee Containers",
            primary_keyword="coffee bean storage container",
            specific_keywords=[
                KeywordVolumeData(keyword="coffee bean storage container", volume=2000),
                KeywordVolumeData(keyword="airtight coffee containers", volume=1500),
                KeywordVolumeData(keyword="vacuum coffee canister", volume=800),
            ],
            all_keywords=[
                KeywordVolumeData(keyword="coffee storage", volume=3000),
                KeywordVolumeData(keyword="kitchen containers", volume=2500),
                ...
            ],
            used_primaries={"coffee maker", "espresso machine"},
            project_id="abc-123",
            page_id="page-456",
        )

        # Result: mix of specific + broader keywords
        # ["airtight coffee containers", "vacuum coffee canister", "coffee storage"]
    """

    def __init__(self) -> None:
        """Initialize the secondary keyword service."""
        logger.debug("SecondaryKeywordService.__init__ called")
        logger.debug("SecondaryKeywordService initialized")

    def _normalize_keyword(self, keyword: str) -> str:
        """Normalize a keyword for comparison.

        Args:
            keyword: Keyword to normalize

        Returns:
            Normalized keyword (lowercase, stripped, single spaces)
        """
        return " ".join(keyword.lower().strip().split())

    def _sort_key_volume_desc(self, keyword: KeywordVolumeData) -> tuple[int, int]:
        """Generate sort key for volume descending, then length ascending.

        Args:
            keyword: KeywordVolumeData to generate key for

        Returns:
            Tuple of (negated_volume, keyword_length) for sorting
        """
        volume = keyword.volume if keyword.volume is not None else 0
        return (-volume, len(keyword.keyword))

    async def select_secondary(
        self,
        collection_title: str,
        primary_keyword: str,
        specific_keywords: list[KeywordVolumeData],
        all_keywords: list[KeywordVolumeData],
        used_primaries: set[str] | None = None,
        project_id: str | None = None,
        page_id: str | None = None,
        min_specific: int = DEFAULT_MIN_SPECIFIC_KEYWORDS,
        max_specific: int = DEFAULT_MAX_SPECIFIC_KEYWORDS,
        min_broader: int = DEFAULT_MIN_BROADER_KEYWORDS,
        max_broader: int = DEFAULT_MAX_BROADER_KEYWORDS,
        broader_volume_threshold: int = DEFAULT_BROADER_VOLUME_THRESHOLD,
    ) -> SecondaryKeywordResult:
        """Select secondary keywords from specific and broader terms.

        Args:
            collection_title: Title of the collection (for logging/context)
            primary_keyword: The primary keyword (to exclude from secondaries)
            specific_keywords: SPECIFIC keywords with volume data (from Step 4)
            all_keywords: All keywords with volume data (for broader term selection)
            used_primaries: Set of keywords already used as primary elsewhere
            project_id: Project ID for logging
            page_id: Page ID for logging
            min_specific: Minimum specific keywords to select (default: 2)
            max_specific: Maximum specific keywords to select (default: 3)
            min_broader: Minimum broader keywords to select (default: 1)
            max_broader: Maximum broader keywords to select (default: 2)
            broader_volume_threshold: Minimum volume for broader terms (default: 1000)

        Returns:
            SecondaryKeywordResult with selected secondary keywords
        """
        start_time = time.monotonic()

        # Normalize used_primaries
        if used_primaries is None:
            used_primaries = set()

        # Normalize the used primaries for comparison
        normalized_used_primaries = {
            self._normalize_keyword(kw) for kw in used_primaries
        }

        logger.debug(
            "select_secondary() called",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "collection_title": collection_title[:100] if collection_title else "",
                "primary_keyword": primary_keyword,
                "specific_keyword_count": len(specific_keywords),
                "all_keyword_count": len(all_keywords),
                "used_primaries_count": len(used_primaries),
                "min_specific": min_specific,
                "max_specific": max_specific,
                "min_broader": min_broader,
                "max_broader": max_broader,
                "broader_volume_threshold": broader_volume_threshold,
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
            return SecondaryKeywordResult(
                success=False,
                error="Collection title cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        if not primary_keyword or not primary_keyword.strip():
            logger.warning(
                "Validation failed: empty primary_keyword",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "field": "primary_keyword",
                    "rejected_value": repr(primary_keyword),
                },
            )
            return SecondaryKeywordResult(
                success=False,
                error="Primary keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        # Normalize the primary keyword for comparison
        normalized_primary = self._normalize_keyword(primary_keyword)

        try:
            selected_keywords: list[KeywordVolumeData] = []
            selected_normalized: set[str] = set()

            # =========================================================
            # STEP 1: Select specific keywords (2-3)
            # =========================================================
            # Filter specific keywords:
            # - Exclude primary keyword
            # - Exclude keywords already used as primary elsewhere
            # - Must have volume data
            specific_candidates = [
                kw
                for kw in specific_keywords
                if (
                    self._normalize_keyword(kw.keyword) != normalized_primary
                    and self._normalize_keyword(kw.keyword)
                    not in normalized_used_primaries
                    and kw.volume is not None
                    and kw.volume > 0
                )
            ]

            # Sort by volume descending
            specific_candidates.sort(key=self._sort_key_volume_desc)

            # Select up to max_specific keywords
            for kw in specific_candidates:
                if len([k for k in selected_keywords if k in specific_candidates]) >= max_specific:
                    break
                normalized = self._normalize_keyword(kw.keyword)
                if normalized not in selected_normalized:
                    selected_keywords.append(kw)
                    selected_normalized.add(normalized)

            specific_selected = len(selected_keywords)

            logger.debug(
                "Selected specific keywords",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "specific_candidates": len(specific_candidates),
                    "specific_selected": specific_selected,
                    "selected_preview": [kw.keyword for kw in selected_keywords[:3]],
                },
            )

            # =========================================================
            # STEP 2: Select broader keywords (1-2)
            # =========================================================
            # Calculate how many broader keywords to target
            # If we have fewer specific keywords, allow more broader
            current_total = len(selected_keywords)
            broader_target = min(
                max_broader,
                DEFAULT_TOTAL_SECONDARY_KEYWORDS - current_total,
            )

            # Filter broader keywords from all_keywords:
            # - Exclude already selected keywords
            # - Exclude primary keyword
            # - Exclude keywords already used as primary elsewhere
            # - Must meet volume threshold (>1000 by default)
            # - Exclude specific keywords (we want "broader" terms)
            specific_normalized = {
                self._normalize_keyword(kw.keyword) for kw in specific_keywords
            }

            broader_candidates = [
                kw
                for kw in all_keywords
                if (
                    self._normalize_keyword(kw.keyword) not in selected_normalized
                    and self._normalize_keyword(kw.keyword) != normalized_primary
                    and self._normalize_keyword(kw.keyword)
                    not in normalized_used_primaries
                    and self._normalize_keyword(kw.keyword) not in specific_normalized
                    and kw.volume is not None
                    and kw.volume >= broader_volume_threshold
                )
            ]

            # Sort by volume descending
            broader_candidates.sort(key=self._sort_key_volume_desc)

            # Select up to broader_target keywords
            broader_selected = 0
            for kw in broader_candidates:
                if broader_selected >= broader_target:
                    break
                normalized = self._normalize_keyword(kw.keyword)
                if normalized not in selected_normalized:
                    selected_keywords.append(kw)
                    selected_normalized.add(normalized)
                    broader_selected += 1

            logger.debug(
                "Selected broader keywords",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "broader_candidates": len(broader_candidates),
                    "broader_target": broader_target,
                    "broader_selected": broader_selected,
                    "broader_preview": [
                        kw.keyword
                        for kw in broader_candidates[:3]
                        if self._normalize_keyword(kw.keyword) in selected_normalized
                    ],
                },
            )

            # =========================================================
            # STEP 3: Fill remaining slots from specific if needed
            # =========================================================
            # If we couldn't find enough broader keywords, add more specific
            remaining_slots = DEFAULT_TOTAL_SECONDARY_KEYWORDS - len(selected_keywords)
            if remaining_slots > 0:
                additional_specific = [
                    kw
                    for kw in specific_candidates
                    if self._normalize_keyword(kw.keyword) not in selected_normalized
                ]
                for kw in additional_specific[:remaining_slots]:
                    normalized = self._normalize_keyword(kw.keyword)
                    if normalized not in selected_normalized:
                        selected_keywords.append(kw)
                        selected_normalized.add(normalized)
                        specific_selected += 1

            duration_ms = (time.monotonic() - start_time) * 1000

            total_count = len(selected_keywords)
            # Recalculate specific_count and broader_count for accuracy
            specific_count = sum(
                1
                for kw in selected_keywords
                if self._normalize_keyword(kw.keyword) in specific_normalized
            )
            broader_count = total_count - specific_count

            # Log state transition: secondary keywords selected
            logger.info(
                "Secondary keywords selected",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "collection_title": collection_title[:100],
                    "primary_keyword": primary_keyword,
                    "total_count": total_count,
                    "specific_count": specific_count,
                    "broader_count": broader_count,
                    "selected_keywords": [
                        {"keyword": kw.keyword, "volume": kw.volume}
                        for kw in selected_keywords
                    ],
                    "duration_ms": round(duration_ms, 2),
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow secondary keyword selection",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "duration_ms": round(duration_ms, 2),
                        "specific_keyword_count": len(specific_keywords),
                        "all_keyword_count": len(all_keywords),
                    },
                )

            return SecondaryKeywordResult(
                success=True,
                secondary_keywords=selected_keywords,
                specific_count=specific_count,
                broader_count=broader_count,
                total_count=total_count,
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Secondary keyword selection exception",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return SecondaryKeywordResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

    async def select_secondary_for_request(
        self,
        request: SecondaryKeywordRequest,
    ) -> SecondaryKeywordResult:
        """Select secondary keywords using a SecondaryKeywordRequest object.

        Convenience method that unpacks a SecondaryKeywordRequest.

        Args:
            request: The secondary keyword request

        Returns:
            SecondaryKeywordResult with the selected secondary keywords
        """
        return await self.select_secondary(
            collection_title=request.collection_title,
            primary_keyword=request.primary_keyword,
            specific_keywords=request.specific_keywords,
            all_keywords=request.all_keywords,
            used_primaries=request.used_primaries,
            project_id=request.project_id,
            page_id=request.page_id,
            min_specific=request.min_specific,
            max_specific=request.max_specific,
            min_broader=request.min_broader,
            max_broader=request.max_broader,
            broader_volume_threshold=request.broader_volume_threshold,
        )


# Global SecondaryKeywordService instance
_secondary_keyword_service: SecondaryKeywordService | None = None


def get_secondary_keyword_service() -> SecondaryKeywordService:
    """Get the default SecondaryKeywordService instance (singleton).

    Returns:
        Default SecondaryKeywordService instance.
    """
    global _secondary_keyword_service
    if _secondary_keyword_service is None:
        _secondary_keyword_service = SecondaryKeywordService()
        logger.info("SecondaryKeywordService singleton created")
    return _secondary_keyword_service


async def select_secondary_keywords(
    collection_title: str,
    primary_keyword: str,
    specific_keywords: list[KeywordVolumeData],
    all_keywords: list[KeywordVolumeData],
    used_primaries: set[str] | None = None,
    project_id: str | None = None,
    page_id: str | None = None,
) -> SecondaryKeywordResult:
    """Convenience function to select secondary keywords.

    Uses the default SecondaryKeywordService singleton.

    Args:
        collection_title: Title of the collection
        primary_keyword: The primary keyword (to exclude from secondaries)
        specific_keywords: SPECIFIC keywords with volume data (from Step 4)
        all_keywords: All keywords with volume data (for broader term selection)
        used_primaries: Set of keywords already used as primary elsewhere
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        SecondaryKeywordResult with the selected secondary keywords

    Example:
        >>> from app.services.keyword_volume import KeywordVolumeData
        >>> specific = [
        ...     KeywordVolumeData(keyword="coffee bean storage container", volume=2000),
        ...     KeywordVolumeData(keyword="airtight coffee containers", volume=1500),
        ...     KeywordVolumeData(keyword="vacuum coffee canister", volume=800),
        ... ]
        >>> all_kw = [
        ...     *specific,
        ...     KeywordVolumeData(keyword="coffee storage", volume=3000),
        ...     KeywordVolumeData(keyword="kitchen containers", volume=2500),
        ... ]
        >>> result = await select_secondary_keywords(
        ...     collection_title="Coffee Containers",
        ...     primary_keyword="coffee bean storage container",
        ...     specific_keywords=specific,
        ...     all_keywords=all_kw,
        ...     project_id="abc-123",
        ... )
        >>> print([kw.keyword for kw in result.secondary_keywords])
        ['airtight coffee containers', 'vacuum coffee canister', 'coffee storage', 'kitchen containers']
    """
    service = get_secondary_keyword_service()
    return await service.select_secondary(
        collection_title=collection_title,
        primary_keyword=primary_keyword,
        specific_keywords=specific_keywords,
        all_keywords=all_keywords,
        used_primaries=used_primaries,
        project_id=project_id,
        page_id=page_id,
    )
