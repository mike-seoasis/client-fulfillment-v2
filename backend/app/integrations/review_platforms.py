"""On-site review platform detection integration.

Detects third-party review platforms embedded on e-commerce websites,
such as Yotpo, Judge.me, Stamped.io, etc.

Uses Perplexity API to search for embedded review widgets and scripts
on a brand's website, avoiding direct scraping which would violate ToS.

Features:
- Detect embedded review platforms (Yotpo, Judge.me, Stamped.io, etc.)
- Extract platform-specific configuration hints
- Identify review widget locations
- Provide confidence scores for detection

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
from enum import Enum
from typing import Any

from app.core.logging import get_logger
from app.integrations.perplexity import PerplexityClient, get_perplexity

logger = get_logger(__name__)


class ReviewPlatform(Enum):
    """Supported review platforms."""

    YOTPO = "yotpo"
    JUDGEME = "judge.me"
    STAMPED = "stamped.io"
    LOOX = "loox"
    OKENDO = "okendo"
    REVIEWS_IO = "reviews.io"
    TRUSTPILOT = "trustpilot"
    BAZAARVOICE = "bazaarvoice"
    POWERREVIEWS = "powerreviews"
    UNKNOWN = "unknown"


@dataclass
class DetectedPlatform:
    """A detected review platform on a website."""

    platform: ReviewPlatform
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)
    widget_locations: list[str] = field(default_factory=list)
    api_hints: dict[str, str] = field(default_factory=dict)


@dataclass
class ReviewPlatformDetectionResult:
    """Result of review platform detection."""

    success: bool
    website_url: str
    platforms_detected: list[DetectedPlatform] = field(default_factory=list)
    primary_platform: ReviewPlatform | None = None
    error: str | None = None
    duration_ms: float = 0.0


# Platform detection signatures for LLM guidance
PLATFORM_SIGNATURES = {
    "yotpo": [
        "yotpo.js",
        "staticw2.yotpo.com",
        "yotpo-widget",
        "data-yotpo-product-id",
        "yotpoProductId",
    ],
    "judge.me": [
        "judge.me",
        "judgeme",
        "jdgm-widget",
        "jdgm-rev",
        "data-id jdgm",
    ],
    "stamped.io": [
        "stamped.io",
        "stamped-reviews",
        "stamped-main-widget",
        "data-widget-id stamped",
    ],
    "loox": [
        "loox.io",
        "loox-widget",
        "loox-reviews",
        "data-loox-id",
    ],
    "okendo": [
        "okendo.io",
        "okeReviews",
        "oke-reviews",
        "data-oke-reviews",
    ],
    "reviews.io": [
        "reviews.io",
        "widget.reviews.io",
        "reviews-widget",
        "carouselInline",
    ],
    "trustpilot": [
        "trustpilot.com",
        "trustpilot-widget",
        "tp-widget",
        "data-template-id trustpilot",
    ],
    "bazaarvoice": [
        "bazaarvoice.com",
        "bvapi.com",
        "bv-rating",
        "data-bv-show",
    ],
    "powerreviews": [
        "powerreviews.com",
        "pwr-",
        "pr-snippet",
        "pr-review-snippet",
    ],
}

PLATFORM_DETECTION_PROMPT = """Analyze the website at {website_url} to detect any third-party review platforms being used.

Look for embedded review widgets, scripts, and integrations from these common platforms:
- Yotpo (yotpo.js, staticw2.yotpo.com, data-yotpo-product-id)
- Judge.me (judge.me, jdgm-widget, jdgm-rev)
- Stamped.io (stamped.io, stamped-reviews, stamped-main-widget)
- Loox (loox.io, loox-widget, loox-reviews)
- Okendo (okendo.io, okeReviews, oke-reviews)
- Reviews.io (reviews.io, widget.reviews.io)
- Trustpilot (trustpilot.com, trustpilot-widget, tp-widget)
- Bazaarvoice (bazaarvoice.com, bvapi.com, bv-rating)
- PowerReviews (powerreviews.com, pwr-, pr-snippet)

Check the HTML source, loaded scripts, and visible widgets on product pages.

Format your findings as JSON:
```json
{{
  "platforms_detected": [
    {{
      "platform": "yotpo|judge.me|stamped.io|loox|okendo|reviews.io|trustpilot|bazaarvoice|powerreviews|unknown",
      "confidence": 0.95,
      "evidence": ["specific script URL found", "widget class detected", "API call observed"],
      "widget_locations": ["product page", "homepage", "collection page"],
      "api_hints": {{"store_id": "optional if visible", "widget_type": "carousel|inline|etc"}}
    }}
  ],
  "primary_platform": "most prominent platform name or null if none found",
  "notes": "any additional observations"
}}
```

If no review platform is detected, return:
```json
{{
  "platforms_detected": [],
  "primary_platform": null,
  "notes": "No third-party review platform detected"
}}
```

Return ONLY the JSON, no explanation."""


def _parse_json_from_response(response: str) -> Any:
    """Parse JSON from a Perplexity response that may include markdown.

    Args:
        response: Raw response text, possibly with markdown code blocks

    Returns:
        Parsed JSON data

    Raises:
        ValueError: If JSON cannot be parsed
    """
    json_text = response

    # Try to extract JSON from markdown code blocks
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0].strip()
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0].strip()

    return json.loads(json_text)


def _parse_platform(platform_str: str) -> ReviewPlatform:
    """Parse platform string to ReviewPlatform enum.

    Args:
        platform_str: Platform name string from LLM response

    Returns:
        ReviewPlatform enum value
    """
    platform_map = {
        "yotpo": ReviewPlatform.YOTPO,
        "judge.me": ReviewPlatform.JUDGEME,
        "judgeme": ReviewPlatform.JUDGEME,
        "stamped.io": ReviewPlatform.STAMPED,
        "stamped": ReviewPlatform.STAMPED,
        "loox": ReviewPlatform.LOOX,
        "okendo": ReviewPlatform.OKENDO,
        "reviews.io": ReviewPlatform.REVIEWS_IO,
        "reviewsio": ReviewPlatform.REVIEWS_IO,
        "trustpilot": ReviewPlatform.TRUSTPILOT,
        "bazaarvoice": ReviewPlatform.BAZAARVOICE,
        "powerreviews": ReviewPlatform.POWERREVIEWS,
    }
    normalized = platform_str.lower().strip()
    return platform_map.get(normalized, ReviewPlatform.UNKNOWN)


class ReviewPlatformClient:
    """Client for detecting on-site review platforms.

    Uses Perplexity's web search capabilities to find embedded review
    widgets and scripts without direct website scraping.
    """

    def __init__(
        self,
        perplexity_client: PerplexityClient | None = None,
    ) -> None:
        """Initialize review platform detection client.

        Args:
            perplexity_client: Optional Perplexity client instance.
                              If not provided, uses the global client.
        """
        self._perplexity = perplexity_client
        self._initialized = False

    async def _get_perplexity(self) -> PerplexityClient:
        """Get the Perplexity client, initializing if needed."""
        if self._perplexity is None:
            self._perplexity = await get_perplexity()
        return self._perplexity

    @property
    def available(self) -> bool:
        """Check if the client is available (Perplexity configured)."""
        if self._perplexity:
            return self._perplexity.available
        return True  # Will be checked when actually used

    async def detect_platforms(
        self,
        website_url: str,
        project_id: str | None = None,
    ) -> ReviewPlatformDetectionResult:
        """Detect review platforms embedded on a website.

        Args:
            website_url: The website URL to analyze
            project_id: Optional project ID for logging context

        Returns:
            ReviewPlatformDetectionResult with detected platforms
        """
        logger.debug(
            "detect_platforms entry",
            extra={
                "website_url": website_url,
                "project_id": project_id,
            },
        )

        start_time = time.monotonic()

        try:
            perplexity = await self._get_perplexity()

            if not perplexity.available:
                logger.warning(
                    "Perplexity not available for review platform detection",
                    extra={"project_id": project_id},
                )
                return ReviewPlatformDetectionResult(
                    success=False,
                    website_url=website_url,
                    error="Perplexity API not configured",
                )

            # Build the prompt
            prompt = PLATFORM_DETECTION_PROMPT.format(website_url=website_url)

            logger.info(
                "Detecting review platforms on website",
                extra={
                    "website_url": website_url,
                    "project_id": project_id,
                },
            )

            # Query Perplexity
            result = await perplexity.complete(
                user_prompt=prompt,
                temperature=0.1,  # Low temperature for factual results
                return_citations=True,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if not result.success:
                logger.warning(
                    "Review platform detection failed",
                    extra={
                        "website_url": website_url,
                        "error": result.error,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )
                return ReviewPlatformDetectionResult(
                    success=False,
                    website_url=website_url,
                    error=result.error or "Failed to analyze website",
                    duration_ms=duration_ms,
                )

            # Parse the response
            try:
                detection_data = _parse_json_from_response(result.text or "{}")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    "Failed to parse review platform detection response",
                    extra={
                        "website_url": website_url,
                        "error": str(e),
                        "response_preview": (result.text or "")[:200],
                        "project_id": project_id,
                    },
                )
                detection_data = {"platforms_detected": [], "primary_platform": None}

            # Convert to DetectedPlatform objects
            platforms: list[DetectedPlatform] = []
            raw_platforms = detection_data.get("platforms_detected", [])

            for p in raw_platforms:
                if isinstance(p, dict):
                    platform_enum = _parse_platform(p.get("platform", "unknown"))
                    confidence = p.get("confidence", 0.5)
                    # Ensure confidence is in valid range
                    confidence = max(0.0, min(1.0, float(confidence)))

                    platforms.append(
                        DetectedPlatform(
                            platform=platform_enum,
                            confidence=confidence,
                            evidence=p.get("evidence", []),
                            widget_locations=p.get("widget_locations", []),
                            api_hints=p.get("api_hints", {}),
                        )
                    )

            # Determine primary platform
            primary_platform: ReviewPlatform | None = None
            primary_str = detection_data.get("primary_platform")
            if primary_str:
                primary_platform = _parse_platform(primary_str)
            elif platforms:
                # If not specified but platforms detected, use highest confidence
                platforms_sorted = sorted(
                    platforms, key=lambda x: x.confidence, reverse=True
                )
                primary_platform = platforms_sorted[0].platform

            logger.info(
                "Review platform detection complete",
                extra={
                    "website_url": website_url,
                    "platforms_found": len(platforms),
                    "primary_platform": (
                        primary_platform.value if primary_platform else None
                    ),
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )

            if duration_ms > 1000:
                logger.info(
                    "Slow review platform detection",
                    extra={
                        "website_url": website_url,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )

            logger.debug(
                "detect_platforms exit",
                extra={
                    "website_url": website_url,
                    "platforms_count": len(platforms),
                    "project_id": project_id,
                },
            )

            return ReviewPlatformDetectionResult(
                success=True,
                website_url=website_url,
                platforms_detected=platforms,
                primary_platform=primary_platform,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.exception(
                "Exception during review platform detection",
                extra={
                    "website_url": website_url,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )
            return ReviewPlatformDetectionResult(
                success=False,
                website_url=website_url,
                error=f"Error detecting review platforms: {e}",
                duration_ms=duration_ms,
            )


# Global client instance
_review_platform_client: ReviewPlatformClient | None = None


async def init_review_platform_client() -> ReviewPlatformClient:
    """Initialize the global review platform client.

    Returns:
        Initialized ReviewPlatformClient instance
    """
    global _review_platform_client
    if _review_platform_client is None:
        _review_platform_client = ReviewPlatformClient()
        logger.info("Review platform client initialized")
    return _review_platform_client


async def get_review_platform_client() -> ReviewPlatformClient:
    """Dependency for getting review platform client.

    Usage:
        @app.get("/platforms")
        async def detect_platforms(
            website_url: str,
            client: ReviewPlatformClient = Depends(get_review_platform_client)
        ):
            result = await client.detect_platforms(website_url)
            ...
    """
    global _review_platform_client
    if _review_platform_client is None:
        await init_review_platform_client()
    return _review_platform_client  # type: ignore[return-value]
