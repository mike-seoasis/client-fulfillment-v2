"""Pydantic schemas for Keyword Research phase API endpoints.

Schemas for keyword research operations:
- KeywordIdeaRequest/Response: Generate keyword ideas for a collection
- KeywordVolumeRequest/Response: Look up volumes for keywords
- KeywordSpecificityRequest/Response: Filter keywords by specificity
- PrimaryKeywordRequest/Response: Select primary keyword
- SecondaryKeywordRequest/Response: Select secondary keywords
- KeywordResearchFullRequest/Response: Run full keyword research pipeline
- KeywordResearchStatsResponse: Statistics about keyword research for a project

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

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# KEYWORD IDEA GENERATION (Step 1)
# =============================================================================


class KeywordIdeaRequest(BaseModel):
    """Request schema for generating keyword ideas for a collection."""

    collection_title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Title of the collection (e.g., 'Coffee Containers')",
        examples=["Coffee Containers", "Kitchen Storage Solutions"],
    )
    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL of the collection page",
        examples=["https://example.com/collections/coffee-containers"],
    )
    content_excerpt: str = Field(
        "",
        max_length=5000,
        description="Content excerpt from the page (products, descriptions)",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL has valid format."""
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        if not v.startswith(("http://", "https://", "/")):
            raise ValueError(f"URL must start with http://, https://, or /: {v[:50]}")
        return v


class KeywordIdeaResponse(BaseModel):
    """Response schema for keyword idea generation."""

    success: bool = Field(..., description="Whether generation succeeded")
    keywords: list[str] = Field(
        default_factory=list,
        description="Generated keyword ideas (20-30 keywords)",
    )
    keyword_count: int = Field(
        0,
        description="Number of keywords generated",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )
    input_tokens: int | None = Field(
        None,
        description="LLM input tokens used",
    )
    output_tokens: int | None = Field(
        None,
        description="LLM output tokens used",
    )


# =============================================================================
# KEYWORD VOLUME LOOKUP (Step 2)
# =============================================================================


class KeywordVolumeRequest(BaseModel):
    """Request schema for looking up keyword volumes."""

    keywords: list[str] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of keywords to look up volumes for",
        examples=[["coffee storage", "airtight containers", "coffee bean container"]],
    )
    country: str = Field(
        "us",
        min_length=2,
        max_length=2,
        description="Country code for volume data (e.g., 'us', 'uk')",
    )
    data_source: str = Field(
        "gkp",
        description="Data source: 'gkp' (Google Keyword Planner) or 'cli' (clickstream)",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
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


class KeywordVolumeDataResponse(BaseModel):
    """Response schema for a single keyword's volume data."""

    keyword: str = Field(..., description="The keyword")
    volume: int | None = Field(None, description="Monthly search volume")
    cpc: float | None = Field(None, description="Cost per click")
    competition: float | None = Field(None, description="Competition score 0-1")
    trend: list[int] | None = Field(None, description="Monthly trend data")
    from_cache: bool = Field(False, description="Whether data came from cache")


class VolumeStatsResponse(BaseModel):
    """Statistics for a volume lookup operation."""

    total_keywords: int = Field(default=0, description="Total keywords in request")
    cache_hits: int = Field(default=0, description="Keywords found in cache")
    cache_misses: int = Field(default=0, description="Keywords not in cache")
    api_lookups: int = Field(default=0, description="Keywords looked up via API")
    api_errors: int = Field(default=0, description="API lookup failures")
    cache_hit_rate: float = Field(
        default=0.0, description="Cache hit rate (0.0 to 1.0)"
    )


class KeywordVolumeResponse(BaseModel):
    """Response schema for keyword volume lookup."""

    success: bool = Field(..., description="Whether lookup succeeded")
    keywords: list[KeywordVolumeDataResponse] = Field(
        default_factory=list,
        description="Volume data for each keyword",
    )
    stats: VolumeStatsResponse = Field(
        default_factory=lambda: VolumeStatsResponse(),
        description="Lookup statistics",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )
    credits_used: int | None = Field(
        None,
        description="API credits used (if any)",
    )


# =============================================================================
# KEYWORD SPECIFICITY FILTERING (Step 4)
# =============================================================================


class KeywordWithVolume(BaseModel):
    """Keyword with volume data for specificity filtering."""

    keyword: str = Field(..., description="The keyword")
    volume: int | None = Field(None, description="Monthly search volume")
    cpc: float | None = Field(None, description="Cost per click")
    competition: float | None = Field(None, description="Competition score 0-1")


class KeywordSpecificityRequest(BaseModel):
    """Request schema for filtering keywords by specificity."""

    collection_title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Title of the collection",
    )
    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL of the collection page",
    )
    content_excerpt: str = Field(
        "",
        max_length=5000,
        description="Content excerpt from the page",
    )
    keywords: list[KeywordWithVolume] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Keywords with volume data to filter",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )


class KeywordSpecificityResponse(BaseModel):
    """Response schema for keyword specificity filtering."""

    success: bool = Field(..., description="Whether filtering succeeded")
    specific_keywords: list[KeywordWithVolume] = Field(
        default_factory=list,
        description="Keywords that passed specificity filter",
    )
    filtered_count: int = Field(
        0,
        description="Number of keywords that passed",
    )
    original_count: int = Field(
        0,
        description="Number of keywords before filtering",
    )
    filter_rate: float = Field(
        0.0,
        description="Percentage of keywords filtered out (0.0 to 1.0)",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )
    input_tokens: int | None = Field(
        None,
        description="LLM input tokens used",
    )
    output_tokens: int | None = Field(
        None,
        description="LLM output tokens used",
    )


# =============================================================================
# PRIMARY KEYWORD SELECTION (Step 5)
# =============================================================================


class PrimaryKeywordRequest(BaseModel):
    """Request schema for selecting the primary keyword."""

    collection_title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Title of the collection",
    )
    specific_keywords: list[KeywordWithVolume] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="SPECIFIC keywords with volume data (from Step 4)",
    )
    used_primaries: list[str] = Field(
        default_factory=list,
        description="Keywords already used as primary elsewhere (to avoid)",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )


class PrimaryKeywordResponse(BaseModel):
    """Response schema for primary keyword selection."""

    success: bool = Field(..., description="Whether selection succeeded")
    primary_keyword: str | None = Field(
        None,
        description="The selected primary keyword",
    )
    primary_volume: int | None = Field(
        None,
        description="Search volume of the primary keyword",
    )
    candidate_count: int = Field(
        0,
        description="Number of candidate keywords considered",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


# =============================================================================
# SECONDARY KEYWORD SELECTION (Step 6)
# =============================================================================


class SecondaryKeywordRequest(BaseModel):
    """Request schema for selecting secondary keywords."""

    collection_title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Title of the collection",
    )
    primary_keyword: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="The primary keyword (to exclude from secondaries)",
    )
    specific_keywords: list[KeywordWithVolume] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="SPECIFIC keywords with volume data (from Step 4)",
    )
    all_keywords: list[KeywordWithVolume] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="All keywords with volume data (for broader term selection)",
    )
    used_primaries: list[str] = Field(
        default_factory=list,
        description="Keywords already used as primary elsewhere (to avoid)",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )
    min_specific: int = Field(
        2,
        ge=0,
        le=5,
        description="Minimum specific keywords to select",
    )
    max_specific: int = Field(
        3,
        ge=1,
        le=10,
        description="Maximum specific keywords to select",
    )
    min_broader: int = Field(
        1,
        ge=0,
        le=5,
        description="Minimum broader keywords to select",
    )
    max_broader: int = Field(
        2,
        ge=0,
        le=10,
        description="Maximum broader keywords to select",
    )
    broader_volume_threshold: int = Field(
        1000,
        ge=0,
        description="Minimum volume for broader terms",
    )


class SecondaryKeywordResponse(BaseModel):
    """Response schema for secondary keyword selection."""

    success: bool = Field(..., description="Whether selection succeeded")
    secondary_keywords: list[KeywordWithVolume] = Field(
        default_factory=list,
        description="The selected secondary keywords",
    )
    specific_count: int = Field(
        0,
        description="Number of specific keywords selected",
    )
    broader_count: int = Field(
        0,
        description="Number of broader keywords selected",
    )
    total_count: int = Field(
        0,
        description="Total number of secondary keywords",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


# =============================================================================
# FULL KEYWORD RESEARCH PIPELINE
# =============================================================================


class KeywordResearchFullRequest(BaseModel):
    """Request schema for running the full keyword research pipeline."""

    collection_title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Title of the collection",
    )
    url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL of the collection page",
    )
    content_excerpt: str = Field(
        "",
        max_length=5000,
        description="Content excerpt from the page",
    )
    used_primaries: list[str] = Field(
        default_factory=list,
        description="Keywords already used as primary elsewhere (to avoid)",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )
    country: str = Field(
        "us",
        min_length=2,
        max_length=2,
        description="Country code for volume data",
    )
    data_source: str = Field(
        "gkp",
        description="Data source: 'gkp' or 'cli'",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL has valid format."""
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        if not v.startswith(("http://", "https://", "/")):
            raise ValueError(f"URL must start with http://, https://, or /: {v[:50]}")
        return v


class KeywordResearchFullResponse(BaseModel):
    """Response schema for full keyword research pipeline."""

    success: bool = Field(..., description="Whether the full pipeline succeeded")
    primary_keyword: str | None = Field(
        None,
        description="The selected primary keyword",
    )
    primary_volume: int | None = Field(
        None,
        description="Search volume of the primary keyword",
    )
    secondary_keywords: list[KeywordWithVolume] = Field(
        default_factory=list,
        description="The selected secondary keywords",
    )
    all_ideas: list[str] = Field(
        default_factory=list,
        description="All generated keyword ideas (Step 1)",
    )
    all_keywords_with_volume: list[KeywordWithVolume] = Field(
        default_factory=list,
        description="All keywords with volume data (Step 2)",
    )
    specific_keywords: list[KeywordWithVolume] = Field(
        default_factory=list,
        description="Keywords that passed specificity filter (Step 4)",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    duration_ms: float = Field(
        ...,
        description="Total processing time in milliseconds",
    )
    step_timings: dict[str, float] = Field(
        default_factory=dict,
        description="Processing time per step",
    )
    credits_used: int | None = Field(
        None,
        description="Total API credits used",
    )


# =============================================================================
# STATISTICS
# =============================================================================


class KeywordResearchStatsResponse(BaseModel):
    """Response schema for keyword research statistics."""

    project_id: str = Field(..., description="Project UUID")
    total_pages: int = Field(..., description="Total crawled pages in project")
    pages_with_keywords: int = Field(
        ...,
        description="Pages that have completed keyword research",
    )
    pages_without_keywords: int = Field(
        ...,
        description="Pages without keyword research",
    )
    total_primary_keywords: int = Field(
        ...,
        description="Number of unique primary keywords",
    )
    total_secondary_keywords: int = Field(
        ...,
        description="Number of unique secondary keywords",
    )
    cache_stats: VolumeStatsResponse | None = Field(
        None,
        description="Keyword volume cache statistics",
    )


# =============================================================================
# PRIMARY KEYWORD GENERATION & APPROVAL (Phase 4)
# =============================================================================


class KeywordCandidate(BaseModel):
    """A keyword candidate with volume metrics and AI scoring.

    Used in keyword generation to represent potential primary keyword options
    with their search metrics and AI-computed relevance scores.
    """

    keyword: str = Field(..., description="The keyword phrase")
    volume: int | None = Field(None, description="Monthly search volume")
    cpc: float | None = Field(None, description="Cost per click in USD")
    competition: float | None = Field(
        None, description="Competition score (0.0 to 1.0)"
    )
    relevance_score: float | None = Field(
        None, description="AI relevance score (0.0 to 100.0)"
    )
    composite_score: float | None = Field(
        None, description="Overall composite score combining metrics (0.0 to 100.0)"
    )


class PrimaryKeywordGenerationStatus(BaseModel):
    """Status of primary keyword generation for a project.

    Tracks progress when generating primary keywords across multiple pages.
    """

    status: str = Field(
        ...,
        description="Generation status: pending, generating, completed, failed",
    )
    total: int = Field(..., ge=0, description="Total pages to process")
    completed: int = Field(..., ge=0, description="Pages successfully processed")
    failed: int = Field(..., ge=0, description="Pages that failed processing")
    current_page: str | None = Field(
        None, description="URL or title of page currently being processed"
    )
    error: str | None = Field(
        None, description="Error message if generation failed"
    )


class PageKeywordsData(BaseModel):
    """Keyword data for a page, matching the PageKeywords model fields.

    Represents the keyword research results stored for a crawled page.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="PageKeywords record UUID")
    primary_keyword: str = Field(..., description="The primary target keyword")
    secondary_keywords: list[str] = Field(
        default_factory=list, description="Supporting/related keywords"
    )
    alternative_keywords: list[str] = Field(
        default_factory=list, description="Alternative keyword strings"
    )
    is_approved: bool = Field(False, description="Whether keywords are approved")
    is_priority: bool = Field(False, description="Whether page is marked as priority")
    composite_score: float | None = Field(
        None, description="Overall AI-generated score"
    )
    relevance_score: float | None = Field(
        None, description="Relevance score to page content"
    )
    ai_reasoning: str | None = Field(
        None, description="AI explanation for keyword recommendation"
    )
    search_volume: int | None = Field(
        None, description="Monthly search volume for primary keyword"
    )
    difficulty_score: int | None = Field(
        None, description="SEO difficulty score (0-100)"
    )


class PageWithKeywords(BaseModel):
    """Combined view of a crawled page with its keyword research data.

    Merges CrawledPage summary data with PageKeywords data for the
    keyword approval interface.
    """

    model_config = ConfigDict(from_attributes=True)

    # Page fields (from CrawledPage)
    id: str = Field(..., description="CrawledPage UUID")
    url: str = Field(..., description="Normalized page URL")
    title: str | None = Field(None, description="Page title")
    labels: list[str] = Field(default_factory=list, description="Page labels/tags")
    product_count: int | None = Field(None, description="Products found on page")

    # Keyword fields (from PageKeywords relationship)
    keywords: PageKeywordsData | None = Field(
        None, description="Keyword research data (null if not yet generated)"
    )


class UpdatePrimaryKeywordRequest(BaseModel):
    """Request schema for updating the primary keyword for a page."""

    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The new primary keyword to set",
        examples=["coffee storage containers", "airtight coffee jars"],
    )

    @field_validator("keyword")
    @classmethod
    def validate_keyword(cls, v: str) -> str:
        """Validate and normalize the keyword."""
        v = v.strip()
        if not v:
            raise ValueError("Keyword cannot be empty")
        return v


class BulkApproveResponse(BaseModel):
    """Response schema for bulk keyword approval operations."""

    approved_count: int = Field(
        ..., ge=0, description="Number of pages whose keywords were approved"
    )
