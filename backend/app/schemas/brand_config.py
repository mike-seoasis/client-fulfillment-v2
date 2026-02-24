"""Pydantic schemas for Brand Config V2 synthesis.

Defines request/response models for brand config synthesis endpoints,
including V2 schema structure for colors, typography, logo, voice/tone, and social media.

ERROR LOGGING REQUIREMENTS:
- Log validation failures with field names and rejected values
- Include entity IDs (project_id) in all logs
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# V2 SCHEMA NESTED MODELS
# =============================================================================


class ColorsSchema(BaseModel):
    """Color palette schema for brand configuration."""

    primary: str | None = Field(
        None,
        description="Primary brand color (hex format, e.g., '#FF5733')",
        examples=["#FF5733"],
    )
    secondary: str | None = Field(
        None,
        description="Secondary brand color (hex format)",
        examples=["#33C1FF"],
    )
    accent: str | None = Field(
        None,
        description="Accent color for highlights and CTAs (hex format)",
        examples=["#FFC300"],
    )
    background: str | None = Field(
        None,
        description="Background color (hex format)",
        examples=["#FFFFFF"],
    )
    text: str | None = Field(
        None,
        description="Primary text color (hex format)",
        examples=["#333333"],
    )

    model_config = ConfigDict(extra="allow")

    @field_validator(
        "primary", "secondary", "accent", "background", "text", mode="before"
    )
    @classmethod
    def normalize_hex_color(cls, v: str | None) -> str | None:
        """Normalize hex color codes."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # Ensure hex format starts with #
        if not v.startswith("#"):
            v = f"#{v}"
        return v.upper()


class TypographySchema(BaseModel):
    """Typography settings schema for brand configuration."""

    heading_font: str | None = Field(
        None,
        description="Font family for headings",
        examples=["Inter", "Playfair Display"],
    )
    body_font: str | None = Field(
        None,
        description="Font family for body text",
        examples=["Open Sans", "Roboto"],
    )
    base_size: int | None = Field(
        None,
        ge=10,
        le=24,
        description="Base font size in pixels",
        examples=[16],
    )
    heading_weight: str | None = Field(
        None,
        description="Font weight for headings",
        examples=["bold", "600", "semibold"],
    )
    body_weight: str | None = Field(
        None,
        description="Font weight for body text",
        examples=["regular", "400", "normal"],
    )

    model_config = ConfigDict(extra="allow")


class LogoSchema(BaseModel):
    """Logo configuration schema."""

    url: str | None = Field(
        None,
        description="URL to the brand logo",
        examples=["https://cdn.example.com/logo.svg"],
    )
    alt_text: str | None = Field(
        None,
        description="Alt text for the logo",
        examples=["Brand Logo"],
    )
    dark_url: str | None = Field(
        None,
        description="URL to the dark mode version of the logo",
    )
    favicon_url: str | None = Field(
        None,
        description="URL to the favicon",
    )

    model_config = ConfigDict(extra="allow")


class VoiceSchema(BaseModel):
    """Brand voice and tone schema."""

    tone: str | None = Field(
        None,
        description="Overall tone of the brand voice",
        examples=["professional", "friendly", "playful", "authoritative"],
    )
    personality: list[str] = Field(
        default_factory=list,
        description="Personality traits that define the brand",
        examples=[["helpful", "warm", "knowledgeable"]],
    )
    writing_style: str | None = Field(
        None,
        description="Writing style guidelines",
        examples=["conversational", "formal", "technical"],
    )
    target_audience: str | None = Field(
        None,
        description="Description of the target audience",
    )
    value_proposition: str | None = Field(
        None,
        description="Core value proposition statement",
    )
    tagline: str | None = Field(
        None,
        description="Brand tagline or slogan",
    )

    model_config = ConfigDict(extra="allow")


class SocialSchema(BaseModel):
    """Social media configuration schema."""

    twitter: str | None = Field(
        None,
        description="Twitter/X handle",
        examples=["@brand"],
    )
    linkedin: str | None = Field(
        None,
        description="LinkedIn company page",
        examples=["company/brand"],
    )
    instagram: str | None = Field(
        None,
        description="Instagram handle",
        examples=["@brand"],
    )
    facebook: str | None = Field(
        None,
        description="Facebook page",
    )
    youtube: str | None = Field(
        None,
        description="YouTube channel",
    )
    tiktok: str | None = Field(
        None,
        description="TikTok handle",
    )

    model_config = ConfigDict(extra="allow")


class V2SchemaModel(BaseModel):
    """Complete V2 brand configuration schema.

    This is the core schema structure stored in the brand_configs.v2_schema JSONB field.
    """

    colors: ColorsSchema = Field(
        default_factory=lambda: ColorsSchema(),
        description="Brand color palette",
    )
    typography: TypographySchema = Field(
        default_factory=lambda: TypographySchema(),
        description="Typography settings",
    )
    logo: LogoSchema = Field(
        default_factory=lambda: LogoSchema(),
        description="Logo configuration",
    )
    voice: VoiceSchema = Field(
        default_factory=lambda: VoiceSchema(),
        description="Brand voice and tone",
    )
    social: SocialSchema = Field(
        default_factory=lambda: SocialSchema(),
        description="Social media handles",
    )
    version: str = Field(
        default="2.0",
        description="Schema version",
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# API REQUEST/RESPONSE SCHEMAS
# =============================================================================


class BrandConfigSynthesisRequest(BaseModel):
    """Request schema for synthesizing brand config from documents or URLs.

    The synthesis process uses Claude to extract brand information from
    provided source materials and generate a V2 schema.
    """

    brand_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the brand",
        examples=["Acme Corp"],
    )
    domain: str | None = Field(
        None,
        description="Primary domain for the brand (optional)",
        examples=["acme.com"],
    )
    source_urls: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="URLs to scrape for brand information (max 10)",
        examples=[["https://acme.com/about", "https://acme.com/brand-guide"]],
    )
    source_documents: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Base64-encoded documents (PDF, DOCX, TXT) for brand extraction (max 5)",
    )
    document_filenames: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Filenames for the source documents (used for format detection)",
        examples=[["brand-guide.pdf", "style-guide.docx"]],
    )
    additional_context: str | None = Field(
        None,
        max_length=5000,
        description="Additional context or instructions for the synthesis",
    )
    partial_v2_schema: V2SchemaModel | None = Field(
        None,
        description="Partial V2 schema to merge with synthesized results",
    )

    @field_validator("brand_name")
    @classmethod
    def validate_brand_name(cls, v: str) -> str:
        """Validate and normalize brand name."""
        v = v.strip()
        if not v:
            raise ValueError("Brand name cannot be empty or whitespace only")
        return v

    @field_validator("source_documents", "document_filenames")
    @classmethod
    def validate_document_lists(cls, v: list[str]) -> list[str]:
        """Validate document-related lists."""
        return [item for item in v if item and item.strip()]


class BrandConfigSynthesisResponse(BaseModel):
    """Response schema for brand config synthesis."""

    success: bool = Field(..., description="Whether synthesis succeeded")
    brand_config_id: str | None = Field(
        None,
        description="UUID of the created or updated brand config",
    )
    project_id: str = Field(..., description="Project ID the config belongs to")
    brand_name: str = Field(..., description="Name of the brand")
    domain: str | None = Field(None, description="Brand domain")
    v2_schema: V2SchemaModel = Field(
        ...,
        description="Synthesized V2 brand configuration schema",
    )
    error: str | None = Field(None, description="Error message if synthesis failed")
    duration_ms: float = Field(
        default=0.0,
        ge=0,
        description="Total synthesis duration in milliseconds",
    )
    input_tokens: int | None = Field(
        None,
        description="Claude input tokens used",
    )
    output_tokens: int | None = Field(
        None,
        description="Claude output tokens used",
    )
    request_id: str | None = Field(
        None,
        description="Claude request ID for debugging",
    )
    sources_used: list[str] = Field(
        default_factory=list,
        description="List of sources that were successfully used for synthesis",
    )

    model_config = ConfigDict(from_attributes=True)


class BrandConfigResponse(BaseModel):
    """Response schema for a brand config entity."""

    id: str = Field(..., description="Brand config UUID")
    project_id: str = Field(..., description="Associated project UUID")
    brand_name: str = Field(..., description="Brand name")
    domain: str | None = Field(None, description="Brand domain")
    v2_schema: dict[str, Any] = Field(..., description="V2 brand configuration schema")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class BrandConfigListResponse(BaseModel):
    """Response schema for listing brand configs."""

    items: list[BrandConfigResponse] = Field(
        ...,
        description="List of brand configs",
    )
    total: int = Field(..., ge=0, description="Total count of brand configs")


class BrandConfigUpdateRequest(BaseModel):
    """Request schema for updating a brand config."""

    brand_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="New brand name",
    )
    domain: str | None = Field(
        None,
        description="New domain",
    )
    v2_schema: V2SchemaModel | None = Field(
        None,
        description="Updated V2 schema (replaces existing)",
    )

    @field_validator("brand_name")
    @classmethod
    def validate_brand_name(cls, v: str | None) -> str | None:
        """Validate and normalize brand name."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Brand name cannot be empty or whitespace only")
        return v


# =============================================================================
# SECTION UPDATE AND REGENERATION SCHEMAS
# =============================================================================

# Valid section names for brand config v2_schema
VALID_SECTION_NAMES = [
    "brand_foundation",
    "target_audience",
    "voice_dimensions",
    "voice_characteristics",
    "writing_style",
    "vocabulary",
    "trust_elements",
    "examples_bank",
    "competitor_context",
    "ai_prompt_snippet",
]


class SectionUpdate(BaseModel):
    """Request schema for updating specific sections of a brand config.

    Allows partial updates to individual sections without replacing the entire
    v2_schema. Section content is provided as a dict that will be merged with
    or replace the existing section.
    """

    sections: dict[str, dict[str, Any]] = Field(
        ...,
        description="Dict mapping section names to their updated content",
        examples=[
            {
                "brand_foundation": {
                    "company_name": "Acme Corp",
                    "mission": "Making the world better",
                },
                "voice_characteristics": {
                    "is": ["friendly", "professional"],
                    "is_not": ["corporate", "stiff"],
                },
            }
        ],
    )

    @field_validator("sections")
    @classmethod
    def validate_section_names(
        cls, v: dict[str, dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Validate that all section names are valid."""
        invalid_sections = [name for name in v if name not in VALID_SECTION_NAMES]
        if invalid_sections:
            raise ValueError(
                f"Invalid section names: {invalid_sections}. "
                f"Valid sections are: {VALID_SECTION_NAMES}"
            )
        return v


class RegenerateRequest(BaseModel):
    """Request schema for regenerating brand config sections.

    Supports regenerating either specific sections or the entire config.
    When no sections are specified, regenerates all sections.
    """

    section: str | None = Field(
        None,
        description="Single section to regenerate (mutually exclusive with sections)",
        examples=["brand_foundation", "voice_characteristics"],
    )
    sections: list[str] | None = Field(
        None,
        description="List of sections to regenerate (mutually exclusive with section)",
        examples=[["brand_foundation", "target_audience"]],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"section": "brand_foundation"},
                {"sections": ["voice_dimensions", "voice_characteristics"]},
                {},  # Empty body = regenerate all
            ]
        }
    )

    @field_validator("section")
    @classmethod
    def validate_single_section(cls, v: str | None) -> str | None:
        """Validate that single section name is valid."""
        if v is not None and v not in VALID_SECTION_NAMES:
            raise ValueError(
                f"Invalid section name: {v}. Valid sections are: {VALID_SECTION_NAMES}"
            )
        return v

    @field_validator("sections")
    @classmethod
    def validate_section_list(cls, v: list[str] | None) -> list[str] | None:
        """Validate that all section names in list are valid."""
        if v is None:
            return None
        invalid_sections = [name for name in v if name not in VALID_SECTION_NAMES]
        if invalid_sections:
            raise ValueError(
                f"Invalid section names: {invalid_sections}. "
                f"Valid sections are: {VALID_SECTION_NAMES}"
            )
        return v

    def get_sections_to_regenerate(self) -> list[str] | None:
        """Get the list of sections to regenerate.

        Returns:
            List of section names to regenerate, or None for all sections.
        """
        if self.section:
            return [self.section]
        return self.sections  # None means regenerate all
