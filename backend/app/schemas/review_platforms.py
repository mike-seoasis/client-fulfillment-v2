"""Pydantic schemas for on-site review platform detection API.

Defines request and response schemas for review platform detection
endpoints supporting Yotpo, Judge.me, and other platforms.
"""

from pydantic import BaseModel, Field


class PlatformInfoResponse(BaseModel):
    """Information about a detected review platform."""

    platform: str = Field(
        ..., description="Platform identifier (e.g., 'yotpo', 'judge.me')"
    )
    platform_name: str = Field(
        ..., description="Human-readable platform name (e.g., 'Yotpo', 'Judge.me')"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Detection confidence score (0.0 to 1.0)",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence supporting the detection",
    )
    widget_locations: list[str] = Field(
        default_factory=list,
        description="Where widgets were found (e.g., 'product page', 'homepage')",
    )
    api_hints: dict[str, str] = Field(
        default_factory=dict,
        description="Platform-specific configuration hints",
    )


class ReviewPlatformDetectionRequest(BaseModel):
    """Request to detect review platforms on a website."""

    website_url: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Website URL to analyze (must start with http:// or https://)",
        examples=["https://example.com", "https://mystore.myshopify.com"],
    )


class ReviewPlatformDetectionResponse(BaseModel):
    """Response from review platform detection."""

    success: bool = Field(..., description="Whether the detection succeeded")
    website_url: str = Field(..., description="The website that was analyzed")
    platforms: list[PlatformInfoResponse] = Field(
        default_factory=list,
        description="List of detected review platforms",
    )
    primary_platform: str | None = Field(
        default=None,
        description="Primary platform identifier (if detected)",
    )
    primary_platform_name: str | None = Field(
        default=None,
        description="Human-readable name of the primary platform",
    )
    error: str | None = Field(
        default=None,
        description="Error message if detection failed",
    )
    duration_ms: float = Field(
        default=0.0,
        description="Detection duration in milliseconds",
    )
