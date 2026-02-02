"""Pydantic schemas for Content Score API endpoints.

Schemas for POP (PageOptimizer Pro) content scoring operations:
- ContentScoreRequest: Request to score content for a keyword/URL
- ContentScoreResponse: Full content scoring results from POP API
- Nested schemas for keyword analysis, LSI coverage, heading analysis, recommendations

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# NESTED SCHEMAS FOR CONTENT SCORE
# =============================================================================


class KeywordSectionAnalysisSchema(BaseModel):
    """Schema for keyword analysis in a specific section."""

    section: str = Field(
        ...,
        description="Section name (title, h1, h2, h3, paragraph)",
    )
    current_count: int = Field(
        0,
        ge=0,
        description="Current keyword occurrences in this section",
    )
    target_count: int | None = Field(
        None,
        ge=0,
        description="Target keyword occurrences",
    )
    density_current: float | None = Field(
        None,
        ge=0,
        description="Current keyword density percentage",
    )
    density_target: float | None = Field(
        None,
        ge=0,
        description="Target keyword density percentage",
    )
    meets_target: bool = Field(
        False,
        description="Whether current count meets target",
    )


class KeywordAnalysisSchema(BaseModel):
    """Schema for overall keyword usage analysis."""

    primary_keyword: str = Field(
        ...,
        description="The primary keyword being analyzed",
    )
    total_count: int = Field(
        0,
        ge=0,
        description="Total keyword occurrences across all sections",
    )
    overall_density: float | None = Field(
        None,
        ge=0,
        description="Overall keyword density percentage",
    )
    in_title: bool = Field(
        False,
        description="Whether keyword appears in title",
    )
    in_h1: bool = Field(
        False,
        description="Whether keyword appears in H1",
    )
    in_first_paragraph: bool = Field(
        False,
        description="Whether keyword appears in first paragraph",
    )
    section_analysis: list[KeywordSectionAnalysisSchema] = Field(
        default_factory=list,
        description="Keyword analysis by section",
    )


class LSICoverageItemSchema(BaseModel):
    """Schema for a single LSI term coverage item."""

    phrase: str = Field(
        ...,
        description="The LSI phrase",
    )
    current_count: int = Field(
        0,
        ge=0,
        description="Current occurrences in content",
    )
    target_count: int | None = Field(
        None,
        ge=0,
        description="Target occurrences",
    )
    weight: float | None = Field(
        None,
        ge=0,
        description="Importance weight",
    )
    coverage_percentage: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Coverage percentage (current/target * 100)",
    )
    met: bool = Field(
        False,
        description="Whether target is met",
    )


class LSICoverageSchema(BaseModel):
    """Schema for overall LSI term coverage."""

    total_terms: int = Field(
        0,
        ge=0,
        description="Total LSI terms analyzed",
    )
    terms_met: int = Field(
        0,
        ge=0,
        description="Number of terms meeting target",
    )
    coverage_percentage: float = Field(
        0,
        ge=0,
        le=100,
        description="Overall coverage percentage",
    )
    items: list[LSICoverageItemSchema] = Field(
        default_factory=list,
        description="Individual LSI term coverage",
    )


class HeadingLevelAnalysisSchema(BaseModel):
    """Schema for heading analysis at a specific level."""

    level: str = Field(
        ...,
        description="Heading level (h1, h2, h3, h4)",
    )
    current_count: int = Field(
        0,
        ge=0,
        description="Current heading count at this level",
    )
    min_count: int | None = Field(
        None,
        ge=0,
        description="Minimum recommended count",
    )
    max_count: int | None = Field(
        None,
        ge=0,
        description="Maximum recommended count",
    )
    meets_target: bool = Field(
        False,
        description="Whether current count is within min/max range",
    )


class HeadingAnalysisSchema(BaseModel):
    """Schema for overall heading structure analysis."""

    total_headings: int = Field(
        0,
        ge=0,
        description="Total headings in content",
    )
    structure_score: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Heading structure quality score (0-100)",
    )
    levels: list[HeadingLevelAnalysisSchema] = Field(
        default_factory=list,
        description="Analysis by heading level",
    )


class RecommendationSchema(BaseModel):
    """Schema for a content improvement recommendation."""

    type: str = Field(
        ...,
        description="Recommendation type (word_count, keyword, lsi, heading, etc.)",
    )
    message: str = Field(
        ...,
        description="Human-readable recommendation message",
    )
    priority: str = Field(
        "medium",
        description="Priority level (high, medium, low)",
    )
    impact: str | None = Field(
        None,
        description="Expected impact if implemented (high, medium, low)",
    )
    current_value: str | None = Field(
        None,
        description="Current value for context",
    )
    target_value: str | None = Field(
        None,
        description="Target value to achieve",
    )


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================


class ContentScoreRequest(BaseModel):
    """Request schema for scoring content."""

    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Target keyword for scoring",
        examples=["best hiking boots", "how to make sourdough bread"],
    )
    content_url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL of the content to score",
        examples=["https://example.com/hiking-boots"],
    )
    location_code: int = Field(
        2840,
        ge=1,
        description="Location code for SERP analysis (e.g., 2840 for US)",
    )
    language_code: str = Field(
        "en",
        min_length=2,
        max_length=5,
        description="Language code (e.g., 'en', 'es')",
    )

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        """Validate and normalize keyword."""
        v = v.strip()
        if not v:
            raise ValueError("Keyword cannot be empty")
        return v

    @field_validator("content_url")
    @classmethod
    def validate_content_url(cls, v: str) -> str:
        """Validate and normalize content URL."""
        v = v.strip()
        if not v:
            raise ValueError("Content URL cannot be empty")
        return v


class ContentScoreBatchRequest(BaseModel):
    """Request schema for batch content scoring."""

    items: list[ContentScoreRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of content score requests",
    )
    max_concurrent: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum concurrent scoring requests",
    )


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================


class ContentScoreResponse(BaseModel):
    """Response schema for content score results."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Content score UUID")
    page_id: str = Field(..., description="Associated page UUID")
    pop_task_id: str | None = Field(
        None,
        description="POP API task ID for tracking",
    )

    # Core score data
    page_score: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Overall page optimization score (0-100)",
    )
    passed: bool | None = Field(
        None,
        description="Whether content passes optimization threshold",
    )

    # Analysis data
    keyword_analysis: KeywordAnalysisSchema | None = Field(
        None,
        description="Keyword usage analysis",
    )
    lsi_coverage: LSICoverageSchema | None = Field(
        None,
        description="LSI term coverage analysis",
    )
    word_count_current: int | None = Field(
        None,
        ge=0,
        description="Current word count of the content",
    )
    heading_analysis: HeadingAnalysisSchema | None = Field(
        None,
        description="Heading structure analysis",
    )
    recommendations: list[RecommendationSchema] = Field(
        default_factory=list,
        description="Improvement recommendations",
    )

    # Metadata
    fallback_used: bool = Field(
        False,
        description="Whether fallback scoring was used due to POP unavailability",
    )
    scored_at: datetime | None = Field(
        None,
        description="When the scoring was performed",
    )
    created_at: datetime = Field(..., description="When the record was created")


class ContentScoreCreateResponse(BaseModel):
    """Response schema for content score creation operation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    score: ContentScoreResponse | None = Field(
        None,
        description="The content score results",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    fallback_used: bool = Field(
        False,
        description="Whether fallback scoring was used",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


class ContentScoreBatchItemResponse(BaseModel):
    """Response for a single item in batch scoring."""

    page_id: str = Field(..., description="Page UUID")
    keyword: str = Field(..., description="Target keyword")
    success: bool = Field(..., description="Whether this item succeeded")
    score_id: str | None = Field(
        None,
        description="Created score UUID if successful",
    )
    page_score: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Page score if successful",
    )
    passed: bool | None = Field(
        None,
        description="Whether content passed threshold",
    )
    fallback_used: bool = Field(
        False,
        description="Whether fallback scoring was used",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )


class ContentScoreBatchResponse(BaseModel):
    """Response schema for batch content scoring."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some items may have failed)",
    )
    results: list[ContentScoreBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each item",
    )
    total_items: int = Field(0, description="Total items in request")
    successful_items: int = Field(0, description="Items successfully scored")
    failed_items: int = Field(0, description="Items that failed")
    items_passed: int = Field(0, description="Items that passed threshold")
    items_failed_threshold: int = Field(
        0,
        description="Items scored but below threshold",
    )
    fallback_count: int = Field(
        0,
        description="Items that used fallback scoring",
    )
    error: str | None = Field(
        None,
        description="Error message if entire batch failed",
    )
    duration_ms: float = Field(
        ...,
        description="Total processing time in milliseconds",
    )


class ContentScoreStatsResponse(BaseModel):
    """Response schema for content score statistics."""

    project_id: str = Field(..., description="Project UUID")
    total_scores: int = Field(
        0,
        description="Total content scores for this project",
    )
    avg_page_score: float | None = Field(
        None,
        description="Average page score across all scores",
    )
    pass_rate: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Percentage of content passing threshold",
    )
    fallback_rate: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Percentage of scores using fallback",
    )
    scores_by_range: dict[str, int] = Field(
        default_factory=dict,
        description="Count of scores by range (0-50, 50-70, 70-85, 85-100)",
    )
