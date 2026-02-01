"""Pydantic schemas for Phase 5A PAA Analysis API endpoints.

Schemas for PAA (People Also Ask) analysis by intent categorization:
- PAAAnalysisRequest: Analyze PAA questions for content planning
- PAAAnalysisResponse: Analysis result with grouped questions and content angle
- IntentGroupResponse: A group of questions sharing the same intent
- ContentAngleResponse: Recommended content angle for the keyword

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level

Railway Deployment Requirements:
- CORS must allow frontend domain (configure via FRONTEND_URL env var)
- Return proper error responses (Railway shows these in logs)
- Include request_id in all responses for debugging
- Health check endpoint at /health or /api/v1/health
"""

from pydantic import BaseModel, Field, field_validator

from app.schemas.paa_enrichment import PAAQuestionResponse

# =============================================================================
# INTENT GROUP MODEL
# =============================================================================


class IntentGroupResponse(BaseModel):
    """A group of PAA questions sharing the same intent."""

    intent: str = Field(
        ...,
        description="Intent category: buying, usage, care, comparison, unknown",
    )
    questions: list[PAAQuestionResponse] = Field(
        default_factory=list,
        description="Questions in this intent group",
    )
    count: int = Field(
        0,
        description="Number of questions in this group",
    )
    percentage: float = Field(
        0.0,
        description="Percentage of total questions (0-100)",
    )


# =============================================================================
# CONTENT ANGLE MODEL
# =============================================================================


class ContentAngleResponse(BaseModel):
    """Recommended content angle based on PAA question distribution."""

    primary_angle: str = Field(
        ...,
        description="Primary content angle: purchase_decision, longevity_maintenance, practical_benefits, balanced",
    )
    reasoning: str = Field(
        ...,
        description="Explanation of why this angle was chosen",
    )
    focus_areas: list[str] = Field(
        default_factory=list,
        description="Recommended focus areas for content",
    )


# =============================================================================
# ANALYSIS REQUEST
# =============================================================================


class PAAAnalysisRequest(BaseModel):
    """Request schema for Phase 5A PAA analysis by intent categorization."""

    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Keyword associated with the PAA questions",
        examples=["best hiking boots", "coffee storage containers"],
    )
    questions: list[PAAQuestionResponse] = Field(
        ...,
        description="PAA questions to analyze (with intent already categorized)",
    )
    top_priority_count: int = Field(
        5,
        ge=1,
        le=20,
        description="Number of top priority questions to select",
    )
    categorize_if_needed: bool = Field(
        True,
        description="Whether to categorize questions that have unknown intent",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        """Validate and normalize keyword."""
        v = v.strip()
        if not v:
            raise ValueError("Keyword cannot be empty")
        return v

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v: list[PAAQuestionResponse]) -> list[PAAQuestionResponse]:
        """Validate questions list."""
        if not v:
            raise ValueError("At least one question is required for analysis")
        return v


# =============================================================================
# ANALYSIS RESPONSE
# =============================================================================


class PAAAnalysisResponse(BaseModel):
    """Response schema for Phase 5A PAA analysis operation."""

    success: bool = Field(
        ...,
        description="Whether analysis succeeded",
    )
    keyword: str = Field(
        ...,
        description="The analyzed keyword",
    )
    total_questions: int = Field(
        0,
        description="Total number of questions analyzed",
    )
    categorized_count: int = Field(
        0,
        description="Number of questions with known intent",
    )
    uncategorized_count: int = Field(
        0,
        description="Number of questions with unknown intent",
    )
    intent_groups: dict[str, IntentGroupResponse] = Field(
        default_factory=dict,
        description="Questions grouped by intent category",
    )
    priority_questions: list[PAAQuestionResponse] = Field(
        default_factory=list,
        description="Top priority questions for content planning",
    )
    content_angle: ContentAngleResponse | None = Field(
        None,
        description="Recommended content angle based on question distribution",
    )
    intent_distribution: dict[str, float] = Field(
        default_factory=dict,
        description="Percentage distribution of intents",
    )
    error: str | None = Field(
        None,
        description="Error message if analysis failed",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


# =============================================================================
# ENRICHMENT + ANALYSIS COMBINED REQUEST
# =============================================================================


class PAAEnrichAndAnalyzeRequest(BaseModel):
    """Request schema for combined PAA enrichment and analysis.

    This endpoint first enriches a keyword with PAA questions,
    then analyzes them by intent categorization.
    """

    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Keyword to enrich and analyze",
        examples=["best hiking boots", "coffee storage containers"],
    )
    location_code: int = Field(
        2840,
        ge=1,
        description="Location code (e.g., 2840 for US)",
    )
    language_code: str = Field(
        "en",
        min_length=2,
        max_length=5,
        description="Language code (e.g., 'en')",
    )
    fanout_enabled: bool = Field(
        True,
        description="Whether to search initial PAA questions for nested questions",
    )
    max_fanout_questions: int = Field(
        10,
        ge=1,
        le=50,
        description="Max initial questions to fan-out on",
    )
    top_priority_count: int = Field(
        5,
        ge=1,
        le=20,
        description="Number of top priority questions to select",
    )
    use_cache: bool = Field(
        True,
        description="Whether to use Redis cache for PAA enrichment",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        """Validate and normalize keyword."""
        v = v.strip()
        if not v:
            raise ValueError("Keyword cannot be empty")
        return v


class PAAEnrichAndAnalyzeResponse(BaseModel):
    """Response schema for combined PAA enrichment and analysis."""

    success: bool = Field(
        ...,
        description="Whether the operation succeeded",
    )
    keyword: str = Field(
        ...,
        description="The enriched and analyzed keyword",
    )

    # Enrichment results
    enrichment_success: bool = Field(
        False,
        description="Whether PAA enrichment succeeded",
    )
    initial_count: int = Field(
        0,
        description="Questions from initial PAA search",
    )
    nested_count: int = Field(
        0,
        description="Questions from fan-out searches",
    )
    from_cache: bool = Field(
        False,
        description="Whether enrichment came from cache",
    )

    # Analysis results
    analysis_success: bool = Field(
        False,
        description="Whether PAA analysis succeeded",
    )
    total_questions: int = Field(
        0,
        description="Total questions analyzed",
    )
    categorized_count: int = Field(
        0,
        description="Questions with known intent",
    )
    intent_groups: dict[str, IntentGroupResponse] = Field(
        default_factory=dict,
        description="Questions grouped by intent",
    )
    priority_questions: list[PAAQuestionResponse] = Field(
        default_factory=list,
        description="Top priority questions",
    )
    content_angle: ContentAngleResponse | None = Field(
        None,
        description="Recommended content angle",
    )
    intent_distribution: dict[str, float] = Field(
        default_factory=dict,
        description="Intent percentage distribution",
    )

    # Metadata
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    enrichment_cost: float | None = Field(
        None,
        description="API cost for enrichment (if available)",
    )
    duration_ms: float = Field(
        ...,
        description="Total processing time in milliseconds",
    )
