"""Pydantic schemas for Phase 5C Content Quality API endpoints.

Schemas for AI trope detection and quality scoring:
- ContentQualityRequest: Check quality for generated content
- ContentQualityResponse: Quality score with detailed detections
- TropeDetectionItem: Individual trope detection results
- ContentQualityBatchRequest/Response: Batch quality checking

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

from pydantic import BaseModel, Field

# =============================================================================
# TROPE DETECTION MODELS
# =============================================================================


class WordMatchItem(BaseModel):
    """A detected banned word with its location."""

    word: str = Field(
        ...,
        description="The banned word that was detected",
        examples=["delve", "unlock", "journey"],
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of times the word appears",
    )
    positions: list[int] = Field(
        default_factory=list,
        description="Character positions where the word appears",
    )


class PhraseMatchItem(BaseModel):
    """A detected banned phrase with its location."""

    phrase: str = Field(
        ...,
        description="The banned phrase that was detected",
        examples=["In today's fast-paced world", "When it comes to"],
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of times the phrase appears",
    )
    positions: list[int] = Field(
        default_factory=list,
        description="Character positions where the phrase appears",
    )


class PatternMatchItem(BaseModel):
    """A detected pattern with context."""

    pattern_type: str = Field(
        ...,
        description="Type of pattern (triplet, negation)",
        examples=["triplet", "negation"],
    )
    matched_text: str = Field(
        ...,
        description="The actual text that matched the pattern",
        examples=[
            "Fast. Simple. Powerful.",
            "aren't just wallets, they're investments",
        ],
    )
    position: int = Field(
        ...,
        ge=0,
        description="Character position where the pattern starts",
    )


class TropeDetectionItem(BaseModel):
    """Complete trope detection results."""

    found_banned_words: list[WordMatchItem] = Field(
        default_factory=list,
        description="Banned words detected (instant AI flag)",
    )
    found_banned_phrases: list[PhraseMatchItem] = Field(
        default_factory=list,
        description="Banned phrases detected (instant AI flag)",
    )
    found_em_dashes: int = Field(
        0,
        ge=0,
        description="Number of em dashes found (should be 0)",
    )
    found_triplet_patterns: list[PatternMatchItem] = Field(
        default_factory=list,
        description="Triplet patterns detected (X. Y. Z.)",
    )
    found_negation_patterns: list[PatternMatchItem] = Field(
        default_factory=list,
        description="Negation patterns detected (aren't just X, they're Y)",
    )
    found_rhetorical_questions: int = Field(
        0,
        ge=0,
        description="Number of rhetorical question openers",
    )
    limited_use_words: dict[str, int] = Field(
        default_factory=dict,
        description="Limited-use words and their counts (max 1 per page)",
    )
    overall_score: float = Field(
        ...,
        ge=0,
        le=100,
        description="Quality score from 0-100 (80+ is passing)",
    )
    is_approved: bool = Field(
        ...,
        description="Whether content passes quality threshold",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Actionable suggestions for improvement",
    )


# =============================================================================
# CONTENT QUALITY REQUEST
# =============================================================================


class ContentQualityRequest(BaseModel):
    """Request schema for Phase 5C content quality check."""

    h1: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="H1 heading to check",
        examples=["Premium Leather Wallets"],
    )
    title_tag: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Title tag to check",
        examples=["Premium Leather Wallets | Acme Co"],
    )
    meta_description: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Meta description to check",
    )
    top_description: str = Field(
        "",
        description="Above-the-fold description (HTML)",
    )
    bottom_description: str = Field(
        ...,
        min_length=1,
        description="Full bottom description to check (HTML)",
    )
    page_id: str | None = Field(
        None,
        description="Optional page ID for tracking",
    )
    content_id: str | None = Field(
        None,
        description="Optional content ID for tracking",
    )


# =============================================================================
# CONTENT QUALITY RESPONSE
# =============================================================================


class ContentQualityResponse(BaseModel):
    """Response schema for Phase 5C content quality check."""

    success: bool = Field(
        ...,
        description="Whether quality check completed successfully",
    )
    content_id: str | None = Field(
        None,
        description="Content ID that was checked",
    )

    # Trope detection results
    trope_detection: TropeDetectionItem | None = Field(
        None,
        description="Detailed trope detection results (null if failed)",
    )

    # Quality summary
    passed_qa: bool = Field(
        ...,
        description="Whether content passes quality threshold (score >= 80)",
    )

    # Error handling
    error: str | None = Field(
        None,
        description="Error message if failed",
    )

    # Performance
    duration_ms: float = Field(
        ...,
        description="Processing time in milliseconds",
    )


# =============================================================================
# BATCH CONTENT QUALITY
# =============================================================================


class ContentQualityBatchItemRequest(BaseModel):
    """Single item in batch quality check request."""

    h1: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="H1 heading",
    )
    title_tag: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Title tag",
    )
    meta_description: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Meta description",
    )
    top_description: str = Field(
        "",
        description="Above-the-fold description",
    )
    bottom_description: str = Field(
        ...,
        min_length=1,
        description="Bottom description",
    )
    page_id: str | None = Field(None, description="Optional page ID")
    content_id: str | None = Field(None, description="Optional content ID")


class ContentQualityBatchRequest(BaseModel):
    """Request schema for batch quality check."""

    items: list[ContentQualityBatchItemRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Content items to check",
    )


class ContentQualityBatchItemResponse(BaseModel):
    """Response for a single item in batch quality check."""

    content_id: str | None = Field(None, description="Content ID")
    page_id: str | None = Field(None, description="Page ID")
    success: bool = Field(..., description="Whether check completed")
    quality_score: float | None = Field(None, description="Quality score 0-100")
    passed_qa: bool = Field(..., description="Whether content passes QA")
    issue_count: int = Field(0, description="Total issues found")
    error: str | None = Field(None, description="Error message if failed")


class ContentQualityBatchResponse(BaseModel):
    """Response schema for batch quality check."""

    success: bool = Field(
        ...,
        description="Whether batch completed (some may have failed)",
    )
    results: list[ContentQualityBatchItemResponse] = Field(
        default_factory=list,
        description="Results for each item",
    )
    total_items: int = Field(0, description="Total items in request")
    passed_qa_count: int = Field(0, description="Items passing QA")
    failed_qa_count: int = Field(0, description="Items failing QA")
    error_count: int = Field(0, description="Items with errors")
    average_score: float = Field(0.0, description="Average quality score")
    error: str | None = Field(None, description="Error if batch failed")
    duration_ms: float = Field(..., description="Total processing time")
