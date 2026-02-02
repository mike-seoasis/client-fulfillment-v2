"""Pydantic schemas for Content Brief API endpoints.

Schemas for POP (PageOptimizer Pro) content brief operations:
- ContentBriefRequest: Request to fetch a content brief for a keyword/URL
- ContentBriefResponse: Full content brief data from POP API
- Nested schemas for LSI terms, competitors, keyword targets, heading targets, etc.

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
# NESTED SCHEMAS FOR CONTENT BRIEF
# =============================================================================


class HeadingTargetSchema(BaseModel):
    """Schema for a heading target recommendation."""

    level: str = Field(
        ...,
        description="Heading level (h1, h2, h3, h4)",
        examples=["h2", "h3"],
    )
    text: str | None = Field(
        None,
        description="Suggested heading text",
    )
    min_count: int | None = Field(
        None,
        ge=0,
        description="Minimum recommended count for this heading level",
    )
    max_count: int | None = Field(
        None,
        ge=0,
        description="Maximum recommended count for this heading level",
    )
    priority: int | None = Field(
        None,
        ge=1,
        description="Priority ranking (1 = highest)",
    )


class KeywordTargetSchema(BaseModel):
    """Schema for a keyword usage target."""

    keyword: str = Field(
        ...,
        description="The target keyword or phrase",
    )
    section: str | None = Field(
        None,
        description="Section where keyword should appear (title, h1, h2, h3, paragraph)",
    )
    count_min: int | None = Field(
        None,
        ge=0,
        description="Minimum keyword occurrences",
    )
    count_max: int | None = Field(
        None,
        ge=0,
        description="Maximum keyword occurrences",
    )
    density_target: float | None = Field(
        None,
        ge=0,
        description="Target keyword density percentage",
    )


class LSITermSchema(BaseModel):
    """Schema for an LSI (Latent Semantic Indexing) term."""

    phrase: str = Field(
        ...,
        description="The LSI phrase",
    )
    weight: float | None = Field(
        None,
        ge=0,
        description="Importance weight of the term",
    )
    average_count: float | None = Field(
        None,
        ge=0,
        description="Average count in top-ranking content",
    )
    target_count: int | None = Field(
        None,
        ge=0,
        description="Recommended target count",
    )


class EntitySchema(BaseModel):
    """Schema for an entity to include in content."""

    name: str = Field(
        ...,
        description="Entity name",
    )
    type: str | None = Field(
        None,
        description="Entity type (person, place, organization, etc.)",
    )
    salience: float | None = Field(
        None,
        ge=0,
        le=1,
        description="Salience score (0-1)",
    )


class RelatedQuestionSchema(BaseModel):
    """Schema for a related question (People Also Ask)."""

    question: str = Field(
        ...,
        description="The question text",
    )
    answer_snippet: str | None = Field(
        None,
        description="Brief answer snippet if available",
    )
    source_url: str | None = Field(
        None,
        description="Source URL for the answer",
    )


class RelatedSearchSchema(BaseModel):
    """Schema for a related search query."""

    query: str = Field(
        ...,
        description="The related search query",
    )
    relevance: float | None = Field(
        None,
        ge=0,
        le=1,
        description="Relevance score (0-1)",
    )


class CompetitorSchema(BaseModel):
    """Schema for competitor page data in content brief."""

    url: str = Field(
        ...,
        description="Competitor page URL",
    )
    title: str | None = Field(
        None,
        description="Page title",
    )
    page_score: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Competitor's page optimization score (0-100)",
    )
    word_count: int | None = Field(
        None,
        ge=0,
        description="Competitor's word count",
    )
    position: int | None = Field(
        None,
        ge=1,
        description="SERP position",
    )


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================


class ContentBriefRequest(BaseModel):
    """Request schema for fetching a content brief."""

    keyword: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Target keyword for content optimization",
        examples=["best hiking boots", "how to make sourdough bread"],
    )
    target_url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="URL of the page to optimize",
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

    @field_validator("target_url")
    @classmethod
    def validate_target_url(cls, v: str) -> str:
        """Validate and normalize target URL."""
        v = v.strip()
        if not v:
            raise ValueError("Target URL cannot be empty")
        return v


class ContentBriefBatchRequest(BaseModel):
    """Request schema for batch content brief fetching."""

    items: list[ContentBriefRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of content brief requests",
    )
    max_concurrent: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum concurrent brief fetches",
    )


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================


class ContentBriefResponse(BaseModel):
    """Response schema for a content brief."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Content brief UUID")
    page_id: str = Field(..., description="Associated page UUID")
    keyword: str = Field(..., description="Target keyword")
    pop_task_id: str | None = Field(
        None,
        description="POP API task ID for tracking",
    )

    # Word count targets
    word_count_target: int | None = Field(
        None,
        description="Recommended target word count",
    )
    word_count_min: int | None = Field(
        None,
        description="Minimum recommended word count",
    )
    word_count_max: int | None = Field(
        None,
        description="Maximum recommended word count",
    )

    # Structured targets
    heading_targets: list[HeadingTargetSchema] = Field(
        default_factory=list,
        description="Recommended heading structure",
    )
    keyword_targets: list[KeywordTargetSchema] = Field(
        default_factory=list,
        description="Keyword usage targets by section",
    )
    lsi_terms: list[LSITermSchema] = Field(
        default_factory=list,
        description="LSI terms to include",
    )
    entities: list[EntitySchema] = Field(
        default_factory=list,
        description="Entities to mention",
    )
    related_questions: list[RelatedQuestionSchema] = Field(
        default_factory=list,
        description="Related questions (People Also Ask)",
    )
    related_searches: list[RelatedSearchSchema] = Field(
        default_factory=list,
        description="Related search queries",
    )
    competitors: list[CompetitorSchema] = Field(
        default_factory=list,
        description="Competitor page data",
    )

    # Score target
    page_score_target: float | None = Field(
        None,
        ge=0,
        le=100,
        description="Target page optimization score (0-100)",
    )

    # Timestamps
    created_at: datetime = Field(..., description="When the brief was created")
    updated_at: datetime = Field(..., description="When the brief was last updated")


class ContentBriefCreateResponse(BaseModel):
    """Response schema for content brief creation operation."""

    success: bool = Field(..., description="Whether the operation succeeded")
    brief: ContentBriefResponse | None = Field(
        None,
        description="The created content brief",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


class ContentBriefBatchItemResponse(BaseModel):
    """Response for a single item in batch brief creation."""

    page_id: str = Field(..., description="Page UUID")
    keyword: str = Field(..., description="Target keyword")
    success: bool = Field(..., description="Whether this item succeeded")
    brief_id: str | None = Field(
        None,
        description="Created brief UUID if successful",
    )
    error: str | None = Field(
        None,
        description="Error message if failed",
    )


class ContentBriefBatchResponse(BaseModel):
    """Response schema for batch content brief creation."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some items may have failed)",
    )
    results: list[ContentBriefBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each item",
    )
    total_items: int = Field(0, description="Total items in request")
    successful_items: int = Field(0, description="Items successfully processed")
    failed_items: int = Field(0, description="Items that failed")
    error: str | None = Field(
        None,
        description="Error message if entire batch failed",
    )
    duration_ms: float = Field(
        ...,
        description="Total processing time in milliseconds",
    )


class ContentBriefStatsResponse(BaseModel):
    """Response schema for content brief statistics."""

    project_id: str = Field(..., description="Project UUID")
    total_briefs: int = Field(
        0,
        description="Total content briefs for this project",
    )
    avg_word_count_target: float | None = Field(
        None,
        description="Average word count target across briefs",
    )
    avg_lsi_terms: float | None = Field(
        None,
        description="Average number of LSI terms per brief",
    )
    avg_competitors_analyzed: float | None = Field(
        None,
        description="Average competitors analyzed per brief",
    )
