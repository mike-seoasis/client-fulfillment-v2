"""KeywordSpecificityService for LLM-based keyword specificity filtering.

Implements Step 4 of the keyword research workflow: filtering keywords
to only those that SPECIFICALLY describe a collection's products.

The specificity filter is CRITICAL because:
- SPECIFIC keywords reference the exact products on the page
- GENERIC keywords are too broad and don't convert well
- Primary keywords should always be specific to the collection

Features:
- LLM-based specificity analysis via Claude
- Preserves volume data for filtered keywords
- Comprehensive error logging per requirements
- Batch filtering support for multiple collections

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_claude
from app.services.keyword_volume import KeywordVolumeData

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000


# =============================================================================
# LLM PROMPT TEMPLATES FOR SPECIFICITY FILTERING
# =============================================================================
#
# These prompts are used to filter keywords to only SPECIFIC ones.
# SPECIFIC = references the exact product type in this collection
# GENERIC = too broad, could apply to many different collections
#
# The key insight: high-volume generic terms don't convert well.
# We need keywords that specifically describe what's on THIS page.

SPECIFICITY_FILTER_SYSTEM_PROMPT = """You are a keyword specificity analyst for e-commerce SEO. Your task is to filter keywords to only those that SPECIFICALLY describe a collection's products.

## What is a SPECIFIC keyword?

A SPECIFIC keyword:
- References the exact product type in this collection
- Would make sense as the H1 for this specific page
- Is not so broad it could apply to many different collections
- Describes what a customer would search to find THESE specific products

## What is a GENERIC keyword?

A GENERIC keyword (EXCLUDE these):
- Too broad (e.g., "kitchen storage" for a coffee container collection)
- Could apply to many different product types
- Doesn't specifically describe what's on this page
- Missing product-specific qualifiers

## Examples

For a "Coffee Containers" collection selling airtight coffee storage:

SPECIFIC (INCLUDE):
- "airtight coffee containers" ✓ (directly describes the products)
- "coffee bean storage container" ✓ (specific to coffee storage)
- "vacuum coffee canister" ✓ (specific product type)

GENERIC (EXCLUDE):
- "kitchen storage" ✗ (too broad)
- "food containers" ✗ (not specific to coffee)
- "storage solutions" ✗ (could be anything)

## Response Format

Return ONLY a JSON array of the SPECIFIC keywords (no explanation, no markdown):
["specific keyword 1", "specific keyword 2", ...]

Only include keywords that pass the specificity test. It's better to return fewer highly-specific keywords than many generic ones."""

SPECIFICITY_FILTER_USER_PROMPT_TEMPLATE = """Filter these keywords to only those that SPECIFICALLY describe THIS collection's products.

Collection: {collection_title}
URL: {url}
Products: {content_excerpt}

Keywords to evaluate:
{keywords_with_volumes_json}

Return JSON array of ONLY the SPECIFIC keywords:
["specific keyword 1", "specific keyword 2", ...]"""


class KeywordSpecificityServiceError(Exception):
    """Base exception for KeywordSpecificityService errors."""

    pass


class KeywordSpecificityValidationError(KeywordSpecificityServiceError):
    """Raised when input validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class KeywordSpecificityFilterError(KeywordSpecificityServiceError):
    """Raised when specificity filtering fails."""

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
class SpecificityFilterRequest:
    """Request for keyword specificity filtering.

    Attributes:
        collection_title: Title of the collection (e.g., "Coffee Containers")
        url: URL of the collection page
        content_excerpt: Products/content description from the page
        keywords: Keywords with volume data to filter
        project_id: Project ID for logging
        page_id: Page ID for logging
    """

    collection_title: str
    url: str
    content_excerpt: str
    keywords: list[KeywordVolumeData]
    project_id: str | None = None
    page_id: str | None = None


@dataclass
class SpecificityFilterResult:
    """Result of keyword specificity filtering.

    Attributes:
        success: Whether filtering succeeded
        specific_keywords: Keywords that passed specificity filter (with volume data)
        filtered_count: Number of keywords that passed
        original_count: Number of keywords before filtering
        filter_rate: Percentage of keywords filtered out
        error: Error message if failed
        duration_ms: Total time taken
        input_tokens: Claude input tokens used
        output_tokens: Claude output tokens used
        request_id: Claude request ID for debugging
        project_id: Project ID (for logging context)
        page_id: Page ID (for logging context)
    """

    success: bool
    specific_keywords: list[KeywordVolumeData] = field(default_factory=list)
    filtered_count: int = 0
    original_count: int = 0
    filter_rate: float = 0.0
    error: str | None = None
    duration_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "specific_keywords": [
                {
                    "keyword": kw.keyword,
                    "volume": kw.volume,
                    "cpc": kw.cpc,
                    "competition": kw.competition,
                }
                for kw in self.specific_keywords
            ],
            "filtered_count": self.filtered_count,
            "original_count": self.original_count,
            "filter_rate": self.filter_rate,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "request_id": self.request_id,
        }


class KeywordSpecificityService:
    """Service for filtering keywords by specificity using LLM.

    Uses Claude LLM to determine which keywords SPECIFICALLY describe
    a collection's products vs. generic keywords that are too broad.

    This is Step 4 of the keyword research workflow and is CRITICAL
    for ensuring we select high-quality, converting keywords rather
    than high-volume generic terms.

    Example usage:
        service = KeywordSpecificityService()

        result = await service.filter_keywords(
            collection_title="Coffee Containers",
            url="https://example.com/collections/coffee-containers",
            content_excerpt="Airtight coffee canisters, vacuum coffee storage...",
            keywords=[
                KeywordVolumeData(keyword="airtight coffee containers", volume=1500),
                KeywordVolumeData(keyword="kitchen storage", volume=5000),
                KeywordVolumeData(keyword="coffee bean storage", volume=800),
            ],
            project_id="abc-123",
            page_id="page-456",
        )

        # Result: only specific keywords
        # ["airtight coffee containers", "coffee bean storage"]
        # (kitchen storage filtered out as too generic)
    """

    def __init__(
        self,
        claude_client: ClaudeClient | None = None,
    ) -> None:
        """Initialize the keyword specificity service.

        Args:
            claude_client: Claude client for LLM filtering (uses global if None)
        """
        logger.debug(
            "KeywordSpecificityService.__init__ called",
            extra={
                "has_custom_client": claude_client is not None,
            },
        )

        self._claude_client = claude_client

        logger.debug("KeywordSpecificityService initialized")

    async def _get_claude_client(self) -> ClaudeClient | None:
        """Get Claude client for LLM filtering."""
        if self._claude_client is not None:
            return self._claude_client
        try:
            return await get_claude()
        except Exception as e:
            logger.warning(
                "Failed to get Claude client",
                extra={"error": str(e)},
            )
            return None

    def _normalize_keyword(self, keyword: str) -> str:
        """Normalize a keyword for matching.

        Args:
            keyword: Keyword to normalize

        Returns:
            Normalized keyword (lowercase, stripped, single spaces)
        """
        return " ".join(keyword.lower().strip().split())

    def _build_prompt(
        self,
        collection_title: str,
        url: str,
        content_excerpt: str,
        keywords: list[KeywordVolumeData],
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> tuple[str, str]:
        """Build the prompt for LLM specificity filtering.

        Args:
            collection_title: Title of the collection
            url: URL of the collection page
            content_excerpt: Content excerpt from the page
            keywords: Keywords with volume data
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        logger.debug(
            "_build_prompt() called",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "collection_title_length": len(collection_title),
                "url_length": len(url),
                "content_excerpt_length": len(content_excerpt),
                "keyword_count": len(keywords),
            },
        )

        # Truncate content excerpt if too long (for token efficiency)
        max_excerpt_length = 1500
        if len(content_excerpt) > max_excerpt_length:
            content_excerpt = content_excerpt[:max_excerpt_length] + "..."
            logger.debug(
                "Truncated content excerpt for prompt",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "truncated_to": max_excerpt_length,
                },
            )

        # Build keywords with volumes JSON
        keywords_data = [
            {
                "keyword": kw.keyword,
                "volume": kw.volume if kw.volume is not None else 0,
            }
            for kw in keywords
        ]
        keywords_with_volumes_json = json.dumps(keywords_data, indent=2)

        # Build user prompt from template
        user_prompt = SPECIFICITY_FILTER_USER_PROMPT_TEMPLATE.format(
            collection_title=collection_title,
            url=url,
            content_excerpt=content_excerpt or "(no content available)",
            keywords_with_volumes_json=keywords_with_volumes_json,
        )

        logger.debug(
            "_build_prompt() completed",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "system_prompt_length": len(SPECIFICITY_FILTER_SYSTEM_PROMPT),
                "user_prompt_length": len(user_prompt),
            },
        )

        return SPECIFICITY_FILTER_SYSTEM_PROMPT, user_prompt

    async def filter_keywords(
        self,
        collection_title: str,
        url: str,
        content_excerpt: str,
        keywords: list[KeywordVolumeData],
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> SpecificityFilterResult:
        """Filter keywords to only those that are SPECIFIC to the collection.

        Uses Claude LLM to determine which keywords specifically describe
        the collection's products vs. generic keywords that are too broad.

        Args:
            collection_title: Title of the collection (e.g., "Coffee Containers")
            url: URL of the collection page
            content_excerpt: Products/content description from the page
            keywords: Keywords with volume data to filter
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            SpecificityFilterResult with filtered keywords and metadata
        """
        start_time = time.monotonic()
        original_count = len(keywords)

        logger.debug(
            "filter_keywords() called",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "collection_title": collection_title[:100] if collection_title else "",
                "url": url[:200] if url else "",
                "content_excerpt_length": len(content_excerpt) if content_excerpt else 0,
                "keyword_count": original_count,
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
            return SpecificityFilterResult(
                success=False,
                error="Collection title cannot be empty",
                original_count=original_count,
                project_id=project_id,
                page_id=page_id,
            )

        if not url or not url.strip():
            logger.warning(
                "Validation failed: empty url",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "field": "url",
                    "rejected_value": repr(url),
                },
            )
            return SpecificityFilterResult(
                success=False,
                error="URL cannot be empty",
                original_count=original_count,
                project_id=project_id,
                page_id=page_id,
            )

        if not keywords:
            logger.warning(
                "Validation failed: empty keywords list",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "field": "keywords",
                    "rejected_value": "[]",
                },
            )
            return SpecificityFilterResult(
                success=False,
                error="No keywords provided to filter",
                original_count=0,
                project_id=project_id,
                page_id=page_id,
            )

        # Get Claude client
        claude = await self._get_claude_client()
        if not claude or not claude.available:
            logger.warning(
                "Claude not available for specificity filtering",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "reason": "client_unavailable",
                },
            )
            return SpecificityFilterResult(
                success=False,
                error="Claude LLM not available (missing API key or service unavailable)",
                original_count=original_count,
                project_id=project_id,
                page_id=page_id,
            )

        # Build keyword map for preserving volume data
        keyword_map: dict[str, KeywordVolumeData] = {
            self._normalize_keyword(kw.keyword): kw for kw in keywords
        }

        # Build prompts
        system_prompt, user_prompt = self._build_prompt(
            collection_title=collection_title.strip(),
            url=url.strip(),
            content_excerpt=content_excerpt,
            keywords=keywords,
            project_id=project_id,
            page_id=page_id,
        )

        try:
            # Call Claude
            result = await claude.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,  # Deterministic for consistent filtering
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if not result.success or not result.text:
                logger.warning(
                    "LLM specificity filtering failed",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "error": result.error,
                        "status_code": result.status_code,
                        "request_id": result.request_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return SpecificityFilterResult(
                    success=False,
                    error=result.error or "LLM request failed",
                    original_count=original_count,
                    duration_ms=round(duration_ms, 2),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                    project_id=project_id,
                    page_id=page_id,
                )

            # Parse response
            response_text: str = result.text

            # Handle markdown code blocks (LLM may wrap JSON in code fences)
            original_response = response_text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
                logger.debug(
                    "Extracted JSON from markdown code block",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "fence_type": "json",
                    },
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
                logger.debug(
                    "Extracted JSON from generic code block",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "fence_type": "generic",
                    },
                )

            response_text = response_text.strip()

            try:
                parsed = json.loads(response_text)

                # Validate response is a list
                if not isinstance(parsed, list):
                    logger.warning(
                        "Validation failed: LLM response is not a list",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "field": "response",
                            "rejected_value": type(parsed).__name__,
                            "expected_type": "list",
                        },
                    )
                    return SpecificityFilterResult(
                        success=False,
                        error="LLM response is not a list of keywords",
                        original_count=original_count,
                        duration_ms=round(duration_ms, 2),
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        request_id=result.request_id,
                        project_id=project_id,
                        page_id=page_id,
                    )

                # Match specific keywords back to original data (preserve volume)
                specific_keywords: list[KeywordVolumeData] = []
                matched_count = 0
                unmatched_keywords: list[str] = []

                for specific_kw in parsed:
                    if not specific_kw or not isinstance(specific_kw, str):
                        continue

                    normalized = self._normalize_keyword(specific_kw)

                    if normalized in keyword_map:
                        specific_keywords.append(keyword_map[normalized])
                        matched_count += 1
                    else:
                        unmatched_keywords.append(specific_kw)

                # Log if some LLM keywords didn't match our input
                if unmatched_keywords:
                    logger.debug(
                        "Some LLM keywords didn't match input keywords",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "unmatched_count": len(unmatched_keywords),
                            "unmatched_preview": unmatched_keywords[:5],
                        },
                    )

                # Calculate filter rate
                filter_rate = 0.0
                if original_count > 0:
                    filter_rate = (original_count - len(specific_keywords)) / original_count

                # Log state transition: filtering complete
                logger.info(
                    "Keyword specificity filtering complete",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "original_count": original_count,
                        "filtered_count": len(specific_keywords),
                        "filter_rate": round(filter_rate, 3),
                        "duration_ms": round(duration_ms, 2),
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "request_id": result.request_id,
                    },
                )

                if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                    logger.warning(
                        "Slow specificity filtering operation",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "duration_ms": round(duration_ms, 2),
                            "keyword_count": original_count,
                        },
                    )

                return SpecificityFilterResult(
                    success=True,
                    specific_keywords=specific_keywords,
                    filtered_count=len(specific_keywords),
                    original_count=original_count,
                    filter_rate=round(filter_rate, 3),
                    duration_ms=round(duration_ms, 2),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                    project_id=project_id,
                    page_id=page_id,
                )

            except json.JSONDecodeError as e:
                logger.warning(
                    "Validation failed: LLM response is not valid JSON",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "field": "response",
                        "rejected_value": response_text[:200],
                        "error": str(e),
                        "error_position": e.pos if hasattr(e, "pos") else None,
                        "original_response_preview": original_response[:200],
                    },
                )
                return SpecificityFilterResult(
                    success=False,
                    error=f"Failed to parse LLM response as JSON: {e}",
                    original_count=original_count,
                    duration_ms=round(duration_ms, 2),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                    project_id=project_id,
                    page_id=page_id,
                )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Keyword specificity filtering exception",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            return SpecificityFilterResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                original_count=original_count,
                duration_ms=round(duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

    async def filter_keywords_for_request(
        self,
        request: SpecificityFilterRequest,
    ) -> SpecificityFilterResult:
        """Filter keywords using a SpecificityFilterRequest object.

        Convenience method that unpacks a SpecificityFilterRequest.

        Args:
            request: The specificity filter request

        Returns:
            SpecificityFilterResult with filtered keywords and metadata
        """
        return await self.filter_keywords(
            collection_title=request.collection_title,
            url=request.url,
            content_excerpt=request.content_excerpt,
            keywords=request.keywords,
            project_id=request.project_id,
            page_id=request.page_id,
        )


# Global KeywordSpecificityService instance
_keyword_specificity_service: KeywordSpecificityService | None = None


def get_keyword_specificity_service() -> KeywordSpecificityService:
    """Get the default KeywordSpecificityService instance (singleton).

    Returns:
        Default KeywordSpecificityService instance.
    """
    global _keyword_specificity_service
    if _keyword_specificity_service is None:
        _keyword_specificity_service = KeywordSpecificityService()
        logger.info("KeywordSpecificityService singleton created")
    return _keyword_specificity_service


async def filter_keywords_by_specificity(
    collection_title: str,
    url: str,
    content_excerpt: str,
    keywords: list[KeywordVolumeData],
    project_id: str | None = None,
    page_id: str | None = None,
) -> SpecificityFilterResult:
    """Convenience function to filter keywords by specificity.

    Uses the default KeywordSpecificityService singleton.

    Args:
        collection_title: Title of the collection
        url: URL of the collection page
        content_excerpt: Products/content description from the page
        keywords: Keywords with volume data to filter
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        SpecificityFilterResult with filtered keywords and metadata

    Example:
        >>> from app.services.keyword_volume import KeywordVolumeData
        >>> keywords = [
        ...     KeywordVolumeData(keyword="airtight coffee containers", volume=1500),
        ...     KeywordVolumeData(keyword="kitchen storage", volume=5000),
        ...     KeywordVolumeData(keyword="coffee bean storage", volume=800),
        ... ]
        >>> result = await filter_keywords_by_specificity(
        ...     collection_title="Coffee Containers",
        ...     url="https://example.com/collections/coffee-containers",
        ...     content_excerpt="Airtight coffee canisters, vacuum coffee storage...",
        ...     keywords=keywords,
        ...     project_id="abc-123",
        ... )
        >>> print([kw.keyword for kw in result.specific_keywords])
        ['airtight coffee containers', 'coffee bean storage']
    """
    service = get_keyword_specificity_service()
    return await service.filter_keywords(
        collection_title=collection_title,
        url=url,
        content_excerpt=content_excerpt,
        keywords=keywords,
        project_id=project_id,
        page_id=page_id,
    )
