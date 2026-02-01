"""CategoryService with two-tier approach (patterns → LLM fallback).

Provides intelligent page categorization using a two-tier approach:
1. First tier: URL pattern matching + content signal boosting (fast, free)
2. Second tier: LLM fallback via Claude (slower, costs tokens)

The service falls back to LLM only when pattern-based confidence is below
a configurable threshold. This optimizes for speed and cost while
maintaining accuracy.

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
from app.integrations.claude import ClaudeClient, get_claude
from app.utils.content_signals import (
    ContentAnalysis,
    ContentSignalDetector,
    get_content_signal_detector,
)
from app.utils.url_categorizer import (
    VALID_PAGE_CATEGORIES,
    URLCategorizer,
    get_url_categorizer,
)

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000

# Default confidence threshold for LLM fallback
DEFAULT_LLM_FALLBACK_THRESHOLD = 0.6


class CategoryServiceError(Exception):
    """Base exception for CategoryService errors."""

    pass


class CategoryValidationError(CategoryServiceError):
    """Raised when validation fails."""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation failed for '{field}': {message}")


class CategoryNotFoundError(CategoryServiceError):
    """Raised when a category is not found."""

    def __init__(self, category: str):
        self.category = category
        super().__init__(f"Category not found: {category}")


@dataclass
class CategorizationRequest:
    """Request for page categorization.

    Attributes:
        url: Page URL (required)
        title: Page title (optional, improves accuracy)
        content: Page content/body text (optional, improves accuracy)
        headings: List of heading texts (optional)
        schema_json: JSON-LD schema content (optional)
        meta_description: Meta description (optional)
        breadcrumbs: Breadcrumb trail texts (optional)
        project_id: Project ID for logging
        page_id: Page ID for logging
    """

    url: str
    title: str | None = None
    content: str | None = None
    headings: list[str] | None = None
    schema_json: str | None = None
    meta_description: str | None = None
    breadcrumbs: list[str] | None = None
    project_id: str | None = None
    page_id: str | None = None


@dataclass
class CategorizationResult:
    """Result of page categorization.

    Attributes:
        success: Whether categorization succeeded
        url: The categorized URL
        category: Final category assigned
        confidence: Confidence score (0.0 to 1.0)
        tier: Which tier was used ('pattern', 'llm', 'fallback')
        url_category: Category from URL patterns only
        url_confidence: Confidence from URL patterns only
        content_analysis: Full content analysis (if available)
        llm_result: LLM categorization result (if used)
        labels: Additional labels (from LLM)
        reasoning: Categorization reasoning (from LLM)
        error: Error message if failed
        duration_ms: Total time taken
        project_id: Project ID (for logging context)
        page_id: Page ID (for logging context)
    """

    success: bool
    url: str
    category: str = "other"
    confidence: float = 0.0
    tier: str = "pattern"  # 'pattern', 'llm', 'fallback'
    url_category: str = "other"
    url_confidence: float = 0.0
    content_analysis: ContentAnalysis | None = None
    llm_result: dict[str, Any] | None = None
    labels: list[str] = field(default_factory=list)
    reasoning: str | None = None
    error: str | None = None
    duration_ms: float = 0.0
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "url": self.url,
            "category": self.category,
            "confidence": self.confidence,
            "tier": self.tier,
            "url_category": self.url_category,
            "url_confidence": self.url_confidence,
            "content_analysis": (
                self.content_analysis.to_dict()
                if self.content_analysis
                else None
            ),
            "llm_result": self.llm_result,
            "labels": self.labels,
            "reasoning": self.reasoning,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class CategoryService:
    """Service for intelligent page categorization.

    Uses a two-tier approach:
    1. URL patterns + content signals (fast, free)
    2. LLM fallback via Claude (slower, costs tokens)

    The LLM is only used when pattern-based confidence is below
    the configured threshold, optimizing for speed and cost.

    Example usage:
        service = CategoryService()

        # Categorize a single page
        result = await service.categorize(
            url="https://example.com/products/widget",
            title="Buy Widget Pro - Free Shipping",
            content="Product details... Add to cart... $29.99...",
            project_id="abc-123",
            page_id="xyz-456",
        )

        print(f"Category: {result.category}")  # "product"
        print(f"Confidence: {result.confidence}")  # 0.95
        print(f"Tier: {result.tier}")  # "pattern" (didn't need LLM)

        # Categorize with low-confidence URL
        result = await service.categorize(
            url="https://example.com/about-our-widgets",
            title="Learn More About Us",
        )
        # May fall back to LLM if pattern confidence is low
    """

    def __init__(
        self,
        url_categorizer: URLCategorizer | None = None,
        signal_detector: ContentSignalDetector | None = None,
        claude_client: ClaudeClient | None = None,
        llm_fallback_threshold: float = DEFAULT_LLM_FALLBACK_THRESHOLD,
        enable_llm_fallback: bool = True,
    ) -> None:
        """Initialize the category service.

        Args:
            url_categorizer: URL pattern categorizer (uses default if None)
            signal_detector: Content signal detector (uses default if None)
            claude_client: Claude client for LLM fallback (uses global if None)
            llm_fallback_threshold: Confidence threshold below which LLM is used
            enable_llm_fallback: Whether to enable LLM fallback at all
        """
        logger.debug(
            "CategoryService.__init__ called",
            extra={
                "llm_fallback_threshold": llm_fallback_threshold,
                "enable_llm_fallback": enable_llm_fallback,
            },
        )

        self._url_categorizer = url_categorizer or get_url_categorizer()
        self._signal_detector = signal_detector or get_content_signal_detector()
        self._claude_client = claude_client
        self._llm_fallback_threshold = llm_fallback_threshold
        self._enable_llm_fallback = enable_llm_fallback

        logger.debug(
            "CategoryService initialized",
            extra={
                "categories": list(VALID_PAGE_CATEGORIES),
                "llm_fallback_threshold": llm_fallback_threshold,
                "enable_llm_fallback": enable_llm_fallback,
            },
        )

    @property
    def llm_fallback_threshold(self) -> float:
        """Get the LLM fallback threshold."""
        return self._llm_fallback_threshold

    @property
    def valid_categories(self) -> frozenset[str]:
        """Get valid category names."""
        return VALID_PAGE_CATEGORIES

    async def _get_claude_client(self) -> ClaudeClient | None:
        """Get Claude client for LLM fallback."""
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

    def _validate_url(self, url: str) -> None:
        """Validate URL format.

        Args:
            url: URL to validate

        Raises:
            CategoryValidationError: If URL is invalid
        """
        if not url or not url.strip():
            logger.warning(
                "Validation failed: empty URL",
                extra={"field": "url", "rejected_value": repr(url)},
            )
            raise CategoryValidationError("url", url, "URL is required")

        # Basic URL format check
        url = url.strip()
        if not url.startswith(("http://", "https://", "/")):
            logger.warning(
                "Validation failed: invalid URL format",
                extra={"field": "url", "rejected_value": url[:200]},
            )
            raise CategoryValidationError(
                "url", url, "URL must start with http://, https://, or /"
            )

    def _validate_category(self, category: str) -> None:
        """Validate category name.

        Args:
            category: Category to validate

        Raises:
            CategoryValidationError: If category is invalid
        """
        if category not in VALID_PAGE_CATEGORIES:
            logger.warning(
                "Validation failed: invalid category",
                extra={
                    "field": "category",
                    "rejected_value": category,
                    "valid_values": list(VALID_PAGE_CATEGORIES),
                },
            )
            raise CategoryValidationError(
                "category",
                category,
                f"Must be one of: {', '.join(sorted(VALID_PAGE_CATEGORIES))}",
            )

    async def categorize(
        self,
        url: str,
        title: str | None = None,
        content: str | None = None,
        headings: list[str] | None = None,
        schema_json: str | None = None,
        meta_description: str | None = None,
        breadcrumbs: list[str] | None = None,
        project_id: str | None = None,
        page_id: str | None = None,
        force_llm: bool = False,
        skip_llm: bool = False,
    ) -> CategorizationResult:
        """Categorize a page using the two-tier approach.

        First tries URL pattern matching with content signal boosting.
        If confidence is below threshold, falls back to LLM.

        Args:
            url: Page URL (required)
            title: Page title (optional, improves accuracy)
            content: Page content/body text (optional, improves accuracy)
            headings: List of heading texts (optional)
            schema_json: JSON-LD schema content (optional)
            meta_description: Meta description (optional)
            breadcrumbs: Breadcrumb trail texts (optional)
            project_id: Project ID for logging
            page_id: Page ID for logging
            force_llm: Always use LLM regardless of pattern confidence
            skip_llm: Never use LLM even if confidence is low

        Returns:
            CategorizationResult with category, confidence, and metadata

        Raises:
            CategoryValidationError: If URL validation fails
        """
        start_time = time.monotonic()
        logger.debug(
            "categorize() called",
            extra={
                "url": url[:200] if url else "",
                "project_id": project_id,
                "page_id": page_id,
                "has_title": title is not None,
                "has_content": content is not None,
                "force_llm": force_llm,
                "skip_llm": skip_llm,
            },
        )

        try:
            # Validate URL
            self._validate_url(url)

            # --- TIER 1: URL Patterns + Content Signals ---
            tier1_start = time.monotonic()

            # Get URL-based category
            url_category, matched_pattern = self._url_categorizer.categorize(url)

            # Base confidence: 0.5 for specific pattern match, 0.3 for 'other'
            url_confidence = 0.5 if url_category != "other" else 0.3
            if matched_pattern:
                # Boost confidence slightly for specific pattern match
                url_confidence = 0.6

            # Analyze content signals for confidence boosting
            content_analysis = self._signal_detector.analyze(
                url_category=url_category,
                url_confidence=url_confidence,
                title=title,
                headings=headings,
                body_text=content,
                schema_json=schema_json,
                meta_description=meta_description,
                breadcrumbs=breadcrumbs,
                project_id=project_id,
                page_id=page_id,
            )

            tier1_duration_ms = (time.monotonic() - tier1_start) * 1000

            logger.debug(
                "Tier 1 categorization complete",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "url_category": url_category,
                    "url_confidence": url_confidence,
                    "final_category": content_analysis.final_category,
                    "boosted_confidence": content_analysis.boosted_confidence,
                    "signal_count": len(content_analysis.signals),
                    "tier1_duration_ms": round(tier1_duration_ms, 2),
                },
            )

            # Check if we should use LLM
            use_llm = False
            if force_llm:
                use_llm = True
                logger.debug(
                    "LLM forced by parameter",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
            elif skip_llm:
                use_llm = False
            elif (
                self._enable_llm_fallback
                and content_analysis.boosted_confidence < self._llm_fallback_threshold
            ):
                use_llm = True
                logger.debug(
                    "LLM fallback triggered (low confidence)",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "boosted_confidence": content_analysis.boosted_confidence,
                        "threshold": self._llm_fallback_threshold,
                    },
                )

            # --- TIER 2: LLM Fallback (if needed) ---
            llm_result: dict[str, Any] | None = None
            tier = "pattern"
            final_category = content_analysis.final_category
            final_confidence = content_analysis.boosted_confidence
            labels: list[str] = []
            reasoning: str | None = None

            if use_llm:
                tier = "llm"
                claude_client = await self._get_claude_client()

                if claude_client and claude_client.available:
                    tier2_start = time.monotonic()

                    result = await claude_client.categorize_page(
                        url=url,
                        title=title,
                        content=content,
                        categories=list(VALID_PAGE_CATEGORIES),
                    )

                    tier2_duration_ms = (time.monotonic() - tier2_start) * 1000

                    if result.success:
                        final_category = result.category
                        final_confidence = result.confidence
                        labels = result.labels
                        reasoning = result.reasoning
                        llm_result = {
                            "category": result.category,
                            "confidence": result.confidence,
                            "reasoning": result.reasoning,
                            "labels": result.labels,
                            "input_tokens": result.input_tokens,
                            "output_tokens": result.output_tokens,
                            "duration_ms": result.duration_ms,
                        }

                        logger.info(
                            "LLM categorization complete",
                            extra={
                                "project_id": project_id,
                                "page_id": page_id,
                                "url": url[:200],
                                "llm_category": result.category,
                                "llm_confidence": result.confidence,
                                "pattern_category": content_analysis.final_category,
                                "pattern_confidence": content_analysis.boosted_confidence,
                                "tier2_duration_ms": round(tier2_duration_ms, 2),
                                "input_tokens": result.input_tokens,
                                "output_tokens": result.output_tokens,
                            },
                        )
                    else:
                        # LLM failed, fall back to pattern result
                        tier = "fallback"
                        logger.warning(
                            "LLM categorization failed, using pattern fallback",
                            extra={
                                "project_id": project_id,
                                "page_id": page_id,
                                "url": url[:200],
                                "error": result.error,
                                "fallback_category": content_analysis.final_category,
                            },
                        )
                else:
                    # Claude not available, fall back to pattern result
                    tier = "fallback"
                    logger.warning(
                        "Claude not available, using pattern fallback",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "url": url[:200],
                            "fallback_category": content_analysis.final_category,
                        },
                    )

            total_duration_ms = (time.monotonic() - start_time) * 1000

            logger.debug(
                "categorize() completed",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "url": url[:200],
                    "category": final_category,
                    "confidence": final_confidence,
                    "tier": tier,
                    "duration_ms": round(total_duration_ms, 2),
                },
            )

            if total_duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow categorization",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "url": url[:200],
                        "duration_ms": round(total_duration_ms, 2),
                        "tier": tier,
                    },
                )

            return CategorizationResult(
                success=True,
                url=url,
                category=final_category,
                confidence=final_confidence,
                tier=tier,
                url_category=url_category,
                url_confidence=url_confidence,
                content_analysis=content_analysis,
                llm_result=llm_result,
                labels=labels,
                reasoning=reasoning,
                duration_ms=round(total_duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

        except CategoryServiceError:
            raise
        except Exception as e:
            total_duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Categorization failed with exception",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "url": url[:200] if url else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            return CategorizationResult(
                success=False,
                url=url,
                category="other",
                confidence=0.0,
                tier="pattern",
                error=str(e),
                duration_ms=round(total_duration_ms, 2),
                project_id=project_id,
                page_id=page_id,
            )

    async def categorize_request(
        self,
        request: CategorizationRequest,
        force_llm: bool = False,
        skip_llm: bool = False,
    ) -> CategorizationResult:
        """Categorize a page using a CategorizationRequest object.

        Convenience method that unpacks a CategorizationRequest.

        Args:
            request: The categorization request
            force_llm: Always use LLM regardless of pattern confidence
            skip_llm: Never use LLM even if confidence is low

        Returns:
            CategorizationResult with category, confidence, and metadata
        """
        return await self.categorize(
            url=request.url,
            title=request.title,
            content=request.content,
            headings=request.headings,
            schema_json=request.schema_json,
            meta_description=request.meta_description,
            breadcrumbs=request.breadcrumbs,
            project_id=request.project_id,
            page_id=request.page_id,
            force_llm=force_llm,
            skip_llm=skip_llm,
        )

    async def categorize_many(
        self,
        pages: list[CategorizationRequest],
        force_llm: bool = False,
        skip_llm: bool = False,
        project_id: str | None = None,
        batch_size: int = 10,
    ) -> list[CategorizationResult]:
        """Categorize multiple pages with batch processing.

        Uses a two-phase approach:
        1. First pass: Pattern-based categorization for all pages (fast)
        2. Second pass: Batch LLM calls for low-confidence pages (groups of 10)

        This optimizes for speed/cost by only using LLM where needed,
        and processes LLM calls in batches to improve efficiency.

        Args:
            pages: List of categorization requests
            force_llm: Always use LLM regardless of pattern confidence
            skip_llm: Never use LLM even if confidence is low
            project_id: Project ID for logging (overrides per-request IDs)
            batch_size: Number of pages to process per LLM batch (default 10)

        Returns:
            List of CategorizationResult objects
        """
        start_time = time.monotonic()
        logger.debug(
            "categorize_many() called",
            extra={
                "page_count": len(pages),
                "project_id": project_id,
                "force_llm": force_llm,
                "skip_llm": skip_llm,
                "batch_size": batch_size,
            },
        )

        if not pages:
            return []

        results: list[CategorizationResult] = []
        category_counts: dict[str, int] = {}
        tier_counts: dict[str, int] = {"pattern": 0, "llm": 0, "fallback": 0}

        # Track pages that need LLM processing
        llm_needed_indices: list[int] = []
        llm_needed_pages: list[CategorizationRequest] = []

        # --- PHASE 1: Pattern-based categorization for all pages ---
        phase1_start = time.monotonic()

        for i, page in enumerate(pages):
            # Use provided project_id if not set on request
            if project_id and not page.project_id:
                page.project_id = project_id

            # Do pattern-based categorization first (skip_llm=True for phase 1)
            result = await self.categorize_request(
                request=page,
                force_llm=False,  # Never force LLM in phase 1
                skip_llm=True,    # Always skip LLM in phase 1
            )
            results.append(result)

            # Check if this page needs LLM processing
            if force_llm or (
                not skip_llm
                and self._enable_llm_fallback
                and result.confidence < self._llm_fallback_threshold
            ):
                llm_needed_indices.append(i)
                llm_needed_pages.append(page)

        phase1_duration_ms = (time.monotonic() - phase1_start) * 1000
        logger.debug(
            "Phase 1 (pattern) complete",
            extra={
                "project_id": project_id,
                "page_count": len(pages),
                "llm_needed_count": len(llm_needed_pages),
                "phase1_duration_ms": round(phase1_duration_ms, 2),
            },
        )

        # --- PHASE 2: Batch LLM processing for low-confidence pages ---
        if llm_needed_pages and not skip_llm:
            phase2_start = time.monotonic()
            total_batches = (len(llm_needed_pages) + batch_size - 1) // batch_size

            logger.info(
                "Starting LLM batch processing",
                extra={
                    "project_id": project_id,
                    "llm_pages_count": len(llm_needed_pages),
                    "batch_size": batch_size,
                    "total_batches": total_batches,
                },
            )

            claude_client = await self._get_claude_client()

            if claude_client and claude_client.available:
                # Process in batches of batch_size
                for batch_index in range(total_batches):
                    batch_start_idx = batch_index * batch_size
                    batch_end_idx = min(batch_start_idx + batch_size, len(llm_needed_pages))
                    batch_pages = llm_needed_pages[batch_start_idx:batch_end_idx]
                    batch_indices = llm_needed_indices[batch_start_idx:batch_end_idx]

                    batch_start = time.monotonic()

                    logger.debug(
                        f"Processing LLM batch {batch_index + 1}/{total_batches}",
                        extra={
                            "project_id": project_id,
                            "batch_index": batch_index,
                            "batch_size": len(batch_pages),
                            "total_batches": total_batches,
                        },
                    )

                    # Process each page in the batch with LLM
                    for page_offset, page in enumerate(batch_pages):
                        original_index = batch_indices[page_offset]

                        try:
                            llm_result = await self.categorize_request(
                                request=page,
                                force_llm=True,  # Force LLM in phase 2
                                skip_llm=False,
                            )

                            # Update the result in place
                            results[original_index] = llm_result

                        except Exception as e:
                            logger.warning(
                                "LLM categorization failed for page, keeping pattern result",
                                extra={
                                    "project_id": project_id,
                                    "page_id": page.page_id,
                                    "url": page.url[:200] if page.url else "",
                                    "error": str(e),
                                },
                                exc_info=True,
                            )
                            # Keep the pattern-based result; update tier to 'fallback'
                            results[original_index].tier = "fallback"

                    batch_duration_ms = (time.monotonic() - batch_start) * 1000
                    logger.debug(
                        f"LLM batch {batch_index + 1}/{total_batches} complete",
                        extra={
                            "project_id": project_id,
                            "batch_index": batch_index,
                            "batch_size": len(batch_pages),
                            "batch_duration_ms": round(batch_duration_ms, 2),
                        },
                    )

            else:
                # Claude not available, mark all as fallback
                logger.warning(
                    "Claude not available, using pattern fallback for all LLM-needed pages",
                    extra={
                        "project_id": project_id,
                        "llm_pages_count": len(llm_needed_pages),
                    },
                )
                for idx in llm_needed_indices:
                    results[idx].tier = "fallback"

            phase2_duration_ms = (time.monotonic() - phase2_start) * 1000
            logger.debug(
                "Phase 2 (LLM batch) complete",
                extra={
                    "project_id": project_id,
                    "llm_pages_count": len(llm_needed_pages),
                    "total_batches": total_batches,
                    "phase2_duration_ms": round(phase2_duration_ms, 2),
                },
            )

        # Compute final statistics
        for result in results:
            category_counts[result.category] = (
                category_counts.get(result.category, 0) + 1
            )
            tier_counts[result.tier] = tier_counts.get(result.tier, 0) + 1

        total_duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Batch categorization complete",
            extra={
                "project_id": project_id,
                "page_count": len(pages),
                "success_count": sum(1 for r in results if r.success),
                "category_counts": category_counts,
                "tier_counts": tier_counts,
                "llm_calls": len(llm_needed_pages) if not skip_llm else 0,
                "batch_size": batch_size,
                "duration_ms": round(total_duration_ms, 2),
            },
        )

        if total_duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch categorization",
                extra={
                    "project_id": project_id,
                    "page_count": len(pages),
                    "duration_ms": round(total_duration_ms, 2),
                },
            )

        return results

    def categorize_url_only(self, url: str) -> tuple[str, float]:
        """Quick URL-only categorization (synchronous, no content analysis).

        For fast, pattern-only categorization when content is not available.

        Args:
            url: The URL to categorize

        Returns:
            Tuple of (category, confidence)
        """
        logger.debug(
            "categorize_url_only() called",
            extra={"url": url[:200] if url else ""},
        )

        if not url or not url.strip():
            return "other", 0.0

        category, matched_pattern = self._url_categorizer.categorize(url)

        # Base confidence
        confidence = 0.5 if category != "other" else 0.3
        if matched_pattern:
            confidence = 0.6

        return category, confidence

    def is_high_confidence(
        self,
        confidence: float,
        threshold: float | None = None,
    ) -> bool:
        """Check if a confidence score is above the LLM fallback threshold.

        Args:
            confidence: The confidence score to check
            threshold: Custom threshold (defaults to service threshold)

        Returns:
            True if confidence is above threshold
        """
        threshold = threshold or self._llm_fallback_threshold
        return confidence >= threshold


# Global CategoryService instance
_category_service: CategoryService | None = None


def get_category_service() -> CategoryService:
    """Get the default CategoryService instance (singleton).

    Returns:
        Default CategoryService instance.
    """
    global _category_service
    if _category_service is None:
        _category_service = CategoryService()
    return _category_service


async def categorize_page(
    url: str,
    title: str | None = None,
    content: str | None = None,
    headings: list[str] | None = None,
    schema_json: str | None = None,
    meta_description: str | None = None,
    project_id: str | None = None,
    page_id: str | None = None,
) -> CategorizationResult:
    """Convenience function to categorize a page.

    Uses the default CategoryService singleton.

    Args:
        url: Page URL
        title: Page title
        content: Page content
        headings: List of headings
        schema_json: JSON-LD schema
        meta_description: Meta description
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        CategorizationResult with category and confidence

    Example:
        >>> result = await categorize_page(
        ...     url="https://example.com/products/widget",
        ...     title="Buy Widget Pro",
        ...     content="Add to cart... $29.99...",
        ... )
        >>> print(result.category)
        'product'
        >>> print(result.confidence)
        0.95
    """
    service = get_category_service()
    return await service.categorize(
        url=url,
        title=title,
        content=content,
        headings=headings,
        schema_json=schema_json,
        meta_description=meta_description,
        project_id=project_id,
        page_id=page_id,
    )
