"""Pydantic schemas for PAA Enrichment phase API endpoints.

Schemas for PAA (People Also Ask) enrichment operations:
- PAAEnrichmentRequest: Enrich a keyword with PAA questions
- PAAEnrichmentBatchRequest: Enrich multiple keywords
- PAAQuestionResponse: A single PAA question with metadata
- PAAEnrichmentResponse: Result of PAA enrichment operation
- PAAEnrichmentBatchResponse: Batch enrichment results
- PAAEnrichmentStatsResponse: Statistics about PAA enrichment for a project

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

# =============================================================================
# PAA QUESTION MODEL
# =============================================================================


class PAAQuestionResponse(BaseModel):
    """A single PAA question with metadata."""

    question: str = Field(..., description="The PAA question text")
    answer_snippet: str | None = Field(
        None,
        description="Brief answer snippet from SERP",
    )
    source_url: str | None = Field(
        None,
        description="URL of the source page for the answer",
    )
    source_domain: str | None = Field(
        None,
        description="Domain of the source page",
    )
    position: int | None = Field(
        None,
        description="Position in the PAA results",
    )
    is_nested: bool = Field(
        False,
        description="Whether this came from fan-out search",
    )
    parent_question: str | None = Field(
        None,
        description="Parent question for nested questions",
    )
    intent: str = Field(
        "unknown",
        description="Intent category: buying, usage, care, comparison, unknown",
    )


# =============================================================================
# SINGLE KEYWORD ENRICHMENT
# =============================================================================


class PAAEnrichmentRequest(BaseModel):
    """Request schema for enriching a keyword with PAA questions."""

    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Keyword to enrich with PAA questions",
        examples=["best hiking boots", "coffee storage containers"],
    )
    location_code: int = Field(
        2840,
        ge=1,
        description="Location code (e.g., 2840 for US, 2826 for UK)",
    )
    language_code: str = Field(
        "en",
        min_length=2,
        max_length=5,
        description="Language code (e.g., 'en', 'es')",
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
    fallback_enabled: bool = Field(
        True,
        description="Whether to use Related Searches fallback when PAA insufficient",
    )
    min_paa_for_fallback: int = Field(
        3,
        ge=0,
        le=20,
        description="Minimum PAA questions before triggering fallback",
    )
    categorize_enabled: bool = Field(
        False,
        description="Whether to categorize questions by intent (buying, usage, etc.)",
    )
    use_cache: bool = Field(
        True,
        description="Whether to use Redis cache (24h TTL)",
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


class PAAEnrichmentResponse(BaseModel):
    """Response schema for PAA enrichment operation."""

    success: bool = Field(..., description="Whether enrichment succeeded")
    keyword: str = Field(..., description="The enriched keyword")
    questions: list[PAAQuestionResponse] = Field(
        default_factory=list,
        description="Discovered PAA questions",
    )
    initial_count: int = Field(
        0,
        description="Count of questions from initial search",
    )
    nested_count: int = Field(
        0,
        description="Count of questions from fan-out searches",
    )
    related_search_count: int = Field(
        0,
        description="Count of questions from Related Searches fallback",
    )
    total_count: int = Field(
        0,
        description="Total questions discovered",
    )
    used_fallback: bool = Field(
        False,
        description="Whether Related Searches fallback was used",
    )
    from_cache: bool = Field(
        False,
        description="Whether results came from cache",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    cost: float | None = Field(
        None,
        description="API cost in USD (if available)",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


# =============================================================================
# BATCH ENRICHMENT
# =============================================================================


class PAAEnrichmentBatchRequest(BaseModel):
    """Request schema for batch PAA enrichment."""

    keywords: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Keywords to enrich with PAA questions",
        examples=[["hiking boots", "trail running shoes", "outdoor footwear"]],
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
    fanout_enabled: bool = Field(
        True,
        description="Whether to search initial PAA questions for nested questions",
    )
    max_fanout_questions: int = Field(
        10,
        ge=1,
        le=50,
        description="Max initial questions to fan-out on per keyword",
    )
    fallback_enabled: bool = Field(
        True,
        description="Whether to use Related Searches fallback",
    )
    min_paa_for_fallback: int = Field(
        3,
        ge=0,
        le=20,
        description="Minimum PAA questions before triggering fallback",
    )
    max_concurrent: int = Field(
        5,
        ge=1,
        le=20,
        description="Maximum concurrent keyword enrichments",
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


class PAAEnrichmentBatchItemResponse(BaseModel):
    """Response for a single keyword in batch enrichment."""

    keyword: str = Field(..., description="The enriched keyword")
    success: bool = Field(..., description="Whether enrichment succeeded")
    question_count: int = Field(0, description="Number of questions discovered")
    initial_count: int = Field(0, description="Questions from initial search")
    nested_count: int = Field(0, description="Questions from fan-out")
    related_search_count: int = Field(0, description="Questions from fallback")
    used_fallback: bool = Field(False, description="Whether fallback was used")
    error: str | None = Field(None, description="Error message if failed")


class PAAEnrichmentBatchResponse(BaseModel):
    """Response schema for batch PAA enrichment."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some keywords may have failed)",
    )
    results: list[PAAEnrichmentBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each keyword",
    )
    total_keywords: int = Field(0, description="Total keywords in request")
    successful_keywords: int = Field(0, description="Keywords successfully enriched")
    failed_keywords: int = Field(0, description="Keywords that failed")
    total_questions: int = Field(0, description="Total questions discovered")
    error: str | None = Field(None, description="Error message if batch failed")
    duration_ms: float = Field(..., description="Total processing time")


# =============================================================================
# STATISTICS
# =============================================================================


class PAAEnrichmentStatsResponse(BaseModel):
    """Response schema for PAA enrichment statistics."""

    project_id: str = Field(..., description="Project UUID")
    total_keywords_enriched: int = Field(
        0,
        description="Total keywords that have PAA enrichment",
    )
    total_questions_discovered: int = Field(
        0,
        description="Total PAA questions discovered across all keywords",
    )
    questions_by_intent: dict[str, int] = Field(
        default_factory=dict,
        description="Question counts by intent category",
    )
    cache_hit_rate: float = Field(
        0.0,
        description="PAA cache hit rate (0.0 to 1.0)",
    )
