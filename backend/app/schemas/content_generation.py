"""Pydantic schemas for content generation and review API endpoints.

Schemas for the content generation pipeline:
- ContentGenerationTriggerResponse: Accepted response when pipeline is triggered
- ContentGenerationStatus: Overall pipeline status with per-page breakdown
- PageContentResponse: Generated content for a single page (from ORM)
- PromptLogResponse: Single prompt/response exchange record (from ORM)
- BriefSummary: Lightweight summary of the content brief used during generation
- ContentBriefData: Full brief data for review (keyword, LSI terms, heading/keyword targets)
- ContentUpdateRequest: Partial update request for editing content fields
- BulkApproveResponse: Response for bulk approval endpoint
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# CONTENT UPDATE REQUEST
# =============================================================================


class ContentUpdateRequest(BaseModel):
    """Request schema for partial content updates during review/editing."""

    page_title: str | None = Field(None, description="Updated SEO page title")
    meta_description: str | None = Field(None, description="Updated meta description")
    top_description: str | None = Field(
        None, description="Updated above-the-fold content (plain text)"
    )
    bottom_description: str | None = Field(
        None, description="Updated below-the-fold content (HTML)"
    )


# =============================================================================
# BULK APPROVE RESPONSE
# =============================================================================


class BulkApproveResponse(BaseModel):
    """Response schema for bulk content approval endpoint."""

    approved_count: int = Field(
        ..., ge=0, description="Number of pages approved in this request"
    )


# =============================================================================
# TRIGGER RESPONSE
# =============================================================================


class ContentGenerationTriggerResponse(BaseModel):
    """Response returned when content generation pipeline is triggered."""

    status: str = Field(
        "accepted",
        description="Request status (always 'accepted' on success)",
    )
    message: str = Field(
        ...,
        description="Human-readable message about what was triggered",
    )


# =============================================================================
# PIPELINE STATUS
# =============================================================================


class PageGenerationStatusItem(BaseModel):
    """Per-page status within the content generation pipeline."""

    page_id: str = Field(..., description="CrawledPage UUID")
    url: str = Field(..., description="Normalized page URL")
    keyword: str = Field(..., description="Primary keyword for this page")
    source: str = Field(..., description="Page source: 'onboarding' or 'cluster'")
    status: str = Field(
        ...,
        description="Page generation status (pending, generating_brief, writing, checking, complete, failed)",
    )
    error: str | None = Field(None, description="Error message if failed")
    qa_passed: bool | None = Field(
        None, description="Whether QA checks passed (null if not yet checked)"
    )
    qa_issue_count: int = Field(0, description="Number of QA issues found")
    is_approved: bool = Field(False, description="Whether content has been approved")


class ContentGenerationStatus(BaseModel):
    """Overall content generation pipeline status for a project."""

    overall_status: str = Field(
        ...,
        description="Pipeline status: idle, generating, complete, or failed",
    )
    pages_total: int = Field(..., ge=0, description="Total pages to generate")
    pages_completed: int = Field(..., ge=0, description="Pages completed successfully")
    pages_failed: int = Field(..., ge=0, description="Pages that failed generation")
    pages_approved: int = Field(0, ge=0, description="Pages approved for publishing")
    pages: list[PageGenerationStatusItem] = Field(
        default_factory=list,
        description="Per-page status breakdown",
    )


# =============================================================================
# BRIEF SUMMARY (nested in PageContentResponse)
# =============================================================================


class BriefSummary(BaseModel):
    """Lightweight summary of the content brief used during generation."""

    keyword: str = Field(..., description="Target keyword from the brief")
    lsi_terms_count: int = Field(
        ..., ge=0, description="Number of LSI terms in the brief"
    )
    competitors_count: int = Field(
        0, ge=0, description="Number of competitors analyzed"
    )
    related_questions_count: int = Field(
        0, ge=0, description="Number of related questions (PAA)"
    )
    page_score_target: float | None = Field(
        None, description="Target page optimization score"
    )
    word_count_range: str | None = Field(
        None,
        description="Word count range string (e.g., '800-1200')",
    )


# =============================================================================
# CONTENT BRIEF DATA (full brief for review)
# =============================================================================


class ContentBriefData(BaseModel):
    """Full content brief data exposed for the review/editing UI."""

    keyword: str = Field(..., description="Target keyword from the brief")
    lsi_terms: list[Any] = Field(
        default_factory=list, description="LSI terms for content optimization"
    )
    heading_targets: list[Any] = Field(
        default_factory=list, description="Recommended headings with level and priority"
    )
    keyword_targets: list[Any] = Field(
        default_factory=list, description="Keyword usage targets with min/max counts"
    )


# =============================================================================
# PAGE CONTENT RESPONSE (from ORM)
# =============================================================================


class PageContentResponse(BaseModel):
    """Response schema for generated page content."""

    model_config = ConfigDict(from_attributes=True)

    page_title: str | None = Field(None, description="Generated SEO page title")
    meta_description: str | None = Field(None, description="Generated meta description")
    top_description: str | None = Field(
        None, description="Above-the-fold content (plain text)"
    )
    bottom_description: str | None = Field(
        None, description="Below-the-fold content (HTML)"
    )
    word_count: int | None = Field(
        None, description="Total word count across content fields"
    )
    status: str = Field(
        ...,
        description="Content status (pending, generating_brief, writing, checking, complete, failed)",
    )
    is_approved: bool = Field(False, description="Whether content has been approved")
    approved_at: datetime | None = Field(None, description="When content was approved")
    qa_results: dict[str, Any] | None = Field(None, description="Quality check results")
    brief_summary: BriefSummary | None = Field(
        None, description="Summary of the content brief used"
    )
    brief: ContentBriefData | None = Field(
        None, description="Full content brief data for review"
    )
    generation_started_at: datetime | None = Field(
        None, description="When content generation started"
    )
    generation_completed_at: datetime | None = Field(
        None, description="When content generation completed"
    )


# =============================================================================
# PROMPT LOG RESPONSE (from ORM)
# =============================================================================


class PromptLogResponse(BaseModel):
    """Response schema for a prompt/response exchange record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="PromptLog UUID")
    step: str = Field(..., description="Pipeline step name (e.g. 'content_writing')")
    role: str = Field(..., description="Message role ('system' or 'user')")
    prompt_text: str = Field(..., description="The prompt sent to Claude")
    response_text: str | None = Field(None, description="Claude's response text")
    model: str | None = Field(None, description="Claude model identifier used")
    input_tokens: int | None = Field(None, description="Input tokens consumed")
    output_tokens: int | None = Field(None, description="Output tokens consumed")
    duration_ms: float | None = Field(
        None, description="API call duration in milliseconds"
    )
    created_at: datetime = Field(..., description="When the log was created")
