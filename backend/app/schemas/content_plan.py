"""Pydantic schemas for Phase 5A Content Plan Builder API endpoints.

Schemas for building content plans from PAA analysis and Perplexity research:
- ContentPlanRequest: Build a content plan for a keyword/page
- ContentPlanResponse: Full content plan with main angle, benefits, questions
- BenefitItem: A single benefit extracted from research
- PriorityQuestion: A prioritized question with intent and relevance

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

from app.schemas.paa_analysis import ContentAngleResponse

# =============================================================================
# BENEFIT MODEL
# =============================================================================


class BenefitItem(BaseModel):
    """A single benefit extracted from Perplexity research."""

    benefit: str = Field(
        ...,
        description="The benefit statement",
    )
    source: str | None = Field(
        None,
        description="Source of this benefit (citation or 'PAA' or 'research')",
    )
    confidence: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this benefit (0.0-1.0)",
    )


# =============================================================================
# PRIORITY QUESTION MODEL
# =============================================================================


class PriorityQuestion(BaseModel):
    """A prioritized PAA question for content planning."""

    question: str = Field(
        ...,
        description="The PAA question text",
    )
    intent: str = Field(
        "unknown",
        description="Intent category: buying, usage, care, comparison, unknown",
    )
    priority_rank: int = Field(
        ...,
        ge=1,
        description="Priority rank (1 = highest priority)",
    )
    answer_snippet: str | None = Field(
        None,
        description="Brief answer snippet from SERP if available",
    )
    source_url: str | None = Field(
        None,
        description="Source URL for the answer if available",
    )


# =============================================================================
# CONTENT PLAN REQUEST
# =============================================================================


class ContentPlanRequest(BaseModel):
    """Request schema for Phase 5A content plan builder."""

    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Primary keyword for content planning",
        examples=["best hiking boots", "coffee storage containers"],
    )
    page_url: str | None = Field(
        None,
        description="Target page URL (optional, for context)",
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
    include_perplexity_research: bool = Field(
        True,
        description="Whether to include Perplexity web research for benefits",
    )
    max_benefits: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum number of benefits to extract",
    )
    max_priority_questions: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum number of priority questions to include",
    )
    fanout_enabled: bool = Field(
        True,
        description="Whether to fan-out PAA questions for more discovery",
    )
    use_cache: bool = Field(
        True,
        description="Whether to use cached PAA results",
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


# =============================================================================
# CONTENT PLAN RESPONSE
# =============================================================================


class ContentPlanResponse(BaseModel):
    """Response schema for Phase 5A content plan builder."""

    success: bool = Field(
        ...,
        description="Whether content plan was built successfully",
    )
    keyword: str = Field(
        ...,
        description="The keyword this plan is for",
    )

    # Main angle recommendation
    main_angle: ContentAngleResponse | None = Field(
        None,
        description="Recommended content angle based on question distribution",
    )

    # Benefits from research
    benefits: list[BenefitItem] = Field(
        default_factory=list,
        description="Key benefits extracted from research",
    )

    # Priority questions
    priority_questions: list[PriorityQuestion] = Field(
        default_factory=list,
        description="Top priority questions to address in content",
    )

    # Intent distribution for reference
    intent_distribution: dict[str, float] = Field(
        default_factory=dict,
        description="Percentage distribution of question intents",
    )

    # Research metadata
    total_questions_analyzed: int = Field(
        0,
        description="Total PAA questions analyzed",
    )
    perplexity_used: bool = Field(
        False,
        description="Whether Perplexity research was included",
    )
    perplexity_citations: list[str] = Field(
        default_factory=list,
        description="Citations from Perplexity research",
    )

    # Error handling
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    partial_success: bool = Field(
        False,
        description="True if some components succeeded but others failed",
    )

    # Performance
    duration_ms: float = Field(
        ...,
        description="Total processing time in milliseconds",
    )


# =============================================================================
# BATCH CONTENT PLAN
# =============================================================================


class ContentPlanBatchRequest(BaseModel):
    """Request schema for batch content plan building."""

    keywords: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Keywords to build content plans for",
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
        description="Language code",
    )
    include_perplexity_research: bool = Field(
        True,
        description="Whether to include Perplexity research",
    )
    max_benefits: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum benefits per keyword",
    )
    max_priority_questions: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum priority questions per keyword",
    )
    max_concurrent: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum concurrent plan builds",
    )

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: list[str]) -> list[str]:
        """Validate and normalize keywords."""
        validated = []
        for kw in v:
            if kw and isinstance(kw, str):
                kw = kw.strip()
                if kw:
                    validated.append(kw)
        if not validated:
            raise ValueError("At least one valid keyword is required")
        return validated


class ContentPlanBatchItemResponse(BaseModel):
    """Response for a single keyword in batch content plan building."""

    keyword: str = Field(..., description="The keyword")
    success: bool = Field(..., description="Whether plan was built successfully")
    main_angle: str | None = Field(None, description="Primary content angle")
    benefits_count: int = Field(0, description="Number of benefits extracted")
    questions_count: int = Field(0, description="Number of priority questions")
    error: str | None = Field(None, description="Error message if failed")


class ContentPlanBatchResponse(BaseModel):
    """Response schema for batch content plan building."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some may have failed)",
    )
    results: list[ContentPlanBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each keyword",
    )
    total_keywords: int = Field(0, description="Total keywords in request")
    successful_keywords: int = Field(0, description="Keywords with successful plans")
    failed_keywords: int = Field(0, description="Keywords that failed")
    error: str | None = Field(None, description="Error if batch failed")
    duration_ms: float = Field(..., description="Total processing time")
