"""ReviewPlatformService for on-site review platform detection.

Orchestrates the review platform integration to:
1. Detect if a brand uses third-party review platforms (Yotpo, Judge.me, etc.)
2. Provide confidence scores and evidence for detections
3. Identify primary review platform in use

Features:
- Review platform auto-detection via Perplexity
- Multi-platform detection support
- Confidence scoring
- Widget location identification

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
from app.integrations.review_platforms import (
    DetectedPlatform,
    ReviewPlatform,
    ReviewPlatformClient,
    ReviewPlatformDetectionResult,
    get_review_platform_client,
)

logger = get_logger(__name__)

# Threshold for logging slow operations (in milliseconds)
SLOW_OPERATION_THRESHOLD_MS = 1000


class ReviewPlatformServiceError(Exception):
    """Base exception for ReviewPlatformService errors."""

    pass


class ReviewPlatformValidationError(ReviewPlatformServiceError):
    """Raised when input validation fails."""

    def __init__(self, field_name: str, value: str, message: str) -> None:
        super().__init__(f"Validation error for {field_name}: {message}")
        self.field_name = field_name
        self.value = value
        self.message = message


class ReviewPlatformLookupError(ReviewPlatformServiceError):
    """Raised when review platform detection fails."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        website_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.website_url = website_url


@dataclass
class PlatformInfo:
    """Information about a detected review platform.

    Attributes:
        platform: The platform identifier
        platform_name: Human-readable platform name
        confidence: Detection confidence (0.0 to 1.0)
        evidence: List of evidence supporting the detection
        widget_locations: Where widgets were found on the site
        api_hints: Platform-specific configuration hints
    """

    platform: str
    platform_name: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    widget_locations: list[str] = field(default_factory=list)
    api_hints: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformDetectionResult:
    """Result of review platform detection.

    Attributes:
        success: Whether the operation succeeded
        website_url: The website that was analyzed
        platforms: List of detected platforms
        primary_platform: The primary/main platform detected
        primary_platform_name: Human-readable name of primary platform
        error: Error message if operation failed
        duration_ms: Operation duration in milliseconds
    """

    success: bool
    website_url: str
    platforms: list[PlatformInfo] = field(default_factory=list)
    primary_platform: str | None = None
    primary_platform_name: str | None = None
    error: str | None = None
    duration_ms: float = 0.0


# Human-readable platform names
PLATFORM_DISPLAY_NAMES = {
    ReviewPlatform.YOTPO: "Yotpo",
    ReviewPlatform.JUDGEME: "Judge.me",
    ReviewPlatform.STAMPED: "Stamped.io",
    ReviewPlatform.LOOX: "Loox",
    ReviewPlatform.OKENDO: "Okendo",
    ReviewPlatform.REVIEWS_IO: "Reviews.io",
    ReviewPlatform.TRUSTPILOT: "Trustpilot",
    ReviewPlatform.BAZAARVOICE: "Bazaarvoice",
    ReviewPlatform.POWERREVIEWS: "PowerReviews",
    ReviewPlatform.UNKNOWN: "Unknown Platform",
}


def _get_platform_display_name(platform: ReviewPlatform) -> str:
    """Get human-readable display name for a platform."""
    return PLATFORM_DISPLAY_NAMES.get(platform, platform.value)


def _convert_detected_platform(detected: DetectedPlatform) -> PlatformInfo:
    """Convert DetectedPlatform to PlatformInfo."""
    return PlatformInfo(
        platform=detected.platform.value,
        platform_name=_get_platform_display_name(detected.platform),
        confidence=detected.confidence,
        evidence=detected.evidence,
        widget_locations=detected.widget_locations,
        api_hints=detected.api_hints,
    )


class ReviewPlatformService:
    """Service for on-site review platform detection.

    Provides business logic layer for:
    - Detecting review platforms on brand websites
    - Providing confidence scores and evidence
    - Identifying the primary review platform
    """

    def __init__(
        self,
        client: ReviewPlatformClient | None = None,
    ) -> None:
        """Initialize the service.

        Args:
            client: Optional ReviewPlatformClient instance.
                   If not provided, uses the global client.
        """
        self._client = client

    async def _get_client(self) -> ReviewPlatformClient:
        """Get the review platform client."""
        if self._client is None:
            self._client = await get_review_platform_client()
        return self._client

    def _validate_website_url(self, website_url: str) -> None:
        """Validate website URL input.

        Args:
            website_url: The website URL to validate

        Raises:
            ReviewPlatformValidationError: If validation fails
        """
        if not website_url:
            logger.warning(
                "Website URL validation failed: empty",
                extra={"field": "website_url", "value": ""},
            )
            raise ReviewPlatformValidationError(
                field_name="website_url",
                value="",
                message="Website URL cannot be empty",
            )

        if len(website_url) > 2000:
            logger.warning(
                "Website URL validation failed: too long",
                extra={"field": "website_url", "length": len(website_url)},
            )
            raise ReviewPlatformValidationError(
                field_name="website_url",
                value=website_url[:50] + "...",
                message="Website URL must be 2000 characters or less",
            )

        # Basic URL format check
        if not (
            website_url.startswith("http://") or website_url.startswith("https://")
        ):
            logger.warning(
                "Website URL validation failed: invalid format",
                extra={"field": "website_url", "value": website_url[:50]},
            )
            raise ReviewPlatformValidationError(
                field_name="website_url",
                value=website_url[:50],
                message="Website URL must start with http:// or https://",
            )

    async def detect_platforms(
        self,
        website_url: str,
        project_id: str | None = None,
    ) -> PlatformDetectionResult:
        """Detect review platforms on a website.

        Args:
            website_url: The website URL to analyze
            project_id: Optional project ID for logging

        Returns:
            PlatformDetectionResult with detection results

        Raises:
            ReviewPlatformValidationError: If input validation fails
        """
        logger.debug(
            "detect_platforms entry",
            extra={
                "website_url": website_url,
                "project_id": project_id,
            },
        )

        start_time = time.monotonic()

        # Validate input
        self._validate_website_url(website_url)

        try:
            client = await self._get_client()

            logger.info(
                "Starting review platform detection",
                extra={
                    "website_url": website_url,
                    "project_id": project_id,
                },
            )

            # Call the integration
            result: ReviewPlatformDetectionResult = await client.detect_platforms(
                website_url=website_url,
                project_id=project_id,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.info(
                    "Slow review platform detection",
                    extra={
                        "website_url": website_url,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )

            # Convert platforms
            platforms = [
                _convert_detected_platform(p) for p in result.platforms_detected
            ]

            # Get primary platform info
            primary_platform: str | None = None
            primary_platform_name: str | None = None
            if result.primary_platform:
                primary_platform = result.primary_platform.value
                primary_platform_name = _get_platform_display_name(
                    result.primary_platform
                )

            logger.info(
                "Review platform detection complete",
                extra={
                    "website_url": website_url,
                    "success": result.success,
                    "platforms_found": len(platforms),
                    "primary_platform": primary_platform,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )

            logger.debug(
                "detect_platforms exit",
                extra={
                    "website_url": website_url,
                    "success": result.success,
                    "project_id": project_id,
                },
            )

            return PlatformDetectionResult(
                success=result.success,
                website_url=result.website_url,
                platforms=platforms,
                primary_platform=primary_platform,
                primary_platform_name=primary_platform_name,
                error=result.error,
                duration_ms=duration_ms,
            )

        except ReviewPlatformValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.exception(
                "Exception in detect_platforms",
                extra={
                    "website_url": website_url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )
            raise ReviewPlatformLookupError(
                message=f"Failed to detect review platforms: {e}",
                project_id=project_id,
                website_url=website_url,
            ) from e


# Global service instance
_review_platform_service: ReviewPlatformService | None = None


def get_review_platform_service() -> ReviewPlatformService:
    """Get or create the global ReviewPlatformService instance.

    Returns:
        ReviewPlatformService singleton instance
    """
    global _review_platform_service
    if _review_platform_service is None:
        _review_platform_service = ReviewPlatformService()
    return _review_platform_service
