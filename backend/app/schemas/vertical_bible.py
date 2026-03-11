"""Pydantic schemas for Vertical Knowledge Bibles.

Defines request/response models for bible CRUD endpoints,
including QA rule structures and markdown import/export.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# QA RULE SUB-SCHEMAS
# =============================================================================


class PreferredTermRule(BaseModel):
    """A preferred term substitution rule."""

    use: str = Field(..., min_length=1, description="Preferred term to use")
    instead_of: str = Field(..., min_length=1, description="Term to avoid")


class BannedClaimRule(BaseModel):
    """A banned claim rule."""

    claim: str = Field(..., min_length=1, description="Claim text to ban")
    context: str = Field("", description="Context keyword the claim relates to")
    reason: str = Field("", description="Why this claim is banned")


class FeatureAttributionRule(BaseModel):
    """A feature attribution rule."""

    feature: str = Field(..., min_length=1, description="Feature name")
    correct_component: str = Field(
        ..., min_length=1, description="Component the feature belongs to"
    )
    wrong_components: list[str] = Field(
        default_factory=list,
        description="Components the feature should NOT be attributed to",
    )


class TermContextRule(BaseModel):
    """A term-context co-occurrence rule."""

    term: str = Field(..., min_length=1, description="Term to check context for")
    correct_context: list[str] = Field(
        default_factory=list, description="Terms that should appear with this term"
    )
    wrong_contexts: list[str] = Field(
        default_factory=list, description="Terms that should NOT appear with this term"
    )
    explanation: str = Field("", description="Why this context mapping matters")


class QARulesSchema(BaseModel):
    """Structured QA rules for a bible."""

    preferred_terms: list[PreferredTermRule] = Field(default_factory=list)
    banned_claims: list[BannedClaimRule] = Field(default_factory=list)
    feature_attribution: list[FeatureAttributionRule] = Field(default_factory=list)
    term_context_rules: list[TermContextRule] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


# =============================================================================
# CREATE / UPDATE SCHEMAS
# =============================================================================


class VerticalBibleCreate(BaseModel):
    """Request schema for creating a new bible."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Display name for the bible",
        examples=["Tattoo Cartridge Needles"],
    )
    slug: str | None = Field(
        None,
        max_length=255,
        description="URL-safe slug (auto-generated from name if not provided)",
        examples=["tattoo-cartridge-needles"],
    )
    content_md: str = Field(
        "",
        description="Markdown knowledge document",
    )
    trigger_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords that activate this bible",
        examples=[["cartridge needle", "membrane", "round liner"]],
    )
    qa_rules: QARulesSchema = Field(
        default_factory=QARulesSchema,
        description="Structured QA rules",
    )
    sort_order: int = Field(
        0,
        ge=0,
        description="Priority order (lower = higher priority)",
    )
    is_active: bool = Field(
        True,
        description="Whether this bible is active",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return v.strip()

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().lower()
            if not v:
                return None
        return v

    @field_validator("trigger_keywords")
    @classmethod
    def validate_keywords(cls, v: list[str]) -> list[str]:
        """Strip whitespace and remove empty strings."""
        return [kw.strip().lower() for kw in v if kw.strip()]


class VerticalBibleUpdate(BaseModel):
    """Request schema for updating an existing bible.

    All fields are optional -- only provided fields are updated.
    """

    name: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255)
    content_md: str | None = Field(None)
    trigger_keywords: list[str] | None = Field(None)
    qa_rules: QARulesSchema | None = Field(None)
    sort_order: int | None = Field(None, ge=0)
    is_active: bool | None = Field(None)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Name cannot be empty")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip().lower()
            if not v:
                raise ValueError("Slug cannot be empty")
        return v

    @field_validator("trigger_keywords")
    @classmethod
    def validate_keywords(cls, v: list[str] | None) -> list[str] | None:
        if v is not None:
            return [kw.strip().lower() for kw in v if kw.strip()]
        return v


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================


class VerticalBibleResponse(BaseModel):
    """Response schema for a single bible."""

    id: str
    project_id: str
    name: str
    slug: str
    content_md: str
    trigger_keywords: list[str]
    qa_rules: dict[str, Any]
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerticalBibleListResponse(BaseModel):
    """Response schema for listing bibles."""

    items: list[VerticalBibleResponse]
    total: int = Field(ge=0)


class VerticalBibleSummary(BaseModel):
    """Lightweight bible summary for list views."""

    id: str
    name: str
    slug: str
    keyword_count: int
    is_active: bool
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VerticalBibleListSummaryResponse(BaseModel):
    """Response schema for bible list with summaries."""

    items: list[VerticalBibleSummary]
    total: int = Field(ge=0)


# =============================================================================
# IMPORT / EXPORT SCHEMAS
# =============================================================================


class VerticalBibleImportRequest(BaseModel):
    """Request schema for importing a bible from markdown with frontmatter."""

    markdown: str = Field(
        ...,
        min_length=1,
        description="Full markdown content including YAML frontmatter",
    )
    is_active: bool = Field(True, description="Whether to activate immediately")


class VerticalBibleExportResponse(BaseModel):
    """Response schema for exporting a bible as markdown."""

    markdown: str = Field(..., description="Full markdown with YAML frontmatter")
    filename: str = Field(..., description="Suggested filename (slug.md)")


# =============================================================================
# MATCHING SCHEMAS
# =============================================================================


class BibleMatchResult(BaseModel):
    """Result of matching bibles against a keyword."""

    bible_id: str
    bible_name: str
    bible_slug: str
    matched_keywords: list[str] = Field(description="Which trigger keywords matched")


class BiblePreviewMatchedPage(BaseModel):
    """A page that matches this bible's trigger keywords."""

    page_id: str
    url: str
    keyword: str
    matched_trigger: str = Field(description="Which trigger keyword caused the match")


class BiblePreviewResponse(BaseModel):
    """Preview of how a bible will appear in prompts and which pages it matches."""

    prompt_section: str = Field(
        description="The '## Domain Knowledge' section as it appears in prompts"
    )
    matched_pages: list[BiblePreviewMatchedPage] = Field(default_factory=list)
    total_pages_in_project: int = Field(
        0, description="Total pages with keywords in the project"
    )


# =============================================================================
# TRANSCRIPT EXTRACTION SCHEMAS
# =============================================================================


class TranscriptExtractionRequest(BaseModel):
    """Request body for generating a bible from a transcript."""

    transcript: str = Field(
        ...,
        min_length=50,
        max_length=100_000,
        description="Raw transcript text from a domain expert interview",
    )
    vertical_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the vertical/domain (e.g., 'Tattoo Cartridge Needles')",
    )


class TranscriptExtractionResponse(BaseModel):
    """Response from transcript extraction -- the created draft bible."""

    id: str
    name: str
    slug: str
    trigger_keywords: list[str]
    content_md: str
    qa_rules: dict[str, list[str]]
    is_active: bool
    message: str = "Draft bible created. Review and activate when ready."
