"""Pydantic v2 schemas for Reddit entities.

Schemas for Reddit account management, project config, posts, comments,
and CrowdReply task tracking:
- RedditAccountCreate/Update/Response: Account CRUD
- RedditProjectConfigCreate/Response: Per-project Reddit settings
- RedditPostResponse: Discovered Reddit threads
- RedditCommentResponse: AI-generated comments with nested post
- CommentApproveRequest/RejectRequest: Comment workflow actions
- BulkCommentActionRequest: Batch comment operations
- CrowdReplyTaskResponse: CrowdReply submission tracking
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# RedditAccount schemas
# ---------------------------------------------------------------------------


class RedditAccountCreate(BaseModel):
    """Request schema for creating a Reddit account."""

    username: str = Field(..., max_length=100, description="Reddit username")
    niche_tags: list[str] = Field(default_factory=list, description="Niche/topic tags")
    warmup_stage: str = Field("observation", description="Initial warmup stage")
    notes: str | None = Field(None, description="Free-text notes")


class RedditAccountUpdate(BaseModel):
    """Request schema for updating a Reddit account (all fields optional)."""

    username: str | None = Field(None, max_length=100, description="Reddit username")
    status: str | None = Field(None, description="Account health status")
    warmup_stage: str | None = Field(None, description="Current warmup stage")
    niche_tags: list[str] | None = Field(None, description="Niche/topic tags")
    karma_post: int | None = Field(None, description="Post karma count")
    karma_comment: int | None = Field(None, description="Comment karma count")
    account_age_days: int | None = Field(None, description="Account age in days")
    cooldown_until: datetime | None = Field(None, description="Cooldown end time")
    last_used_at: datetime | None = Field(None, description="Last activity timestamp")
    notes: str | None = Field(None, description="Free-text notes")


class RedditAccountResponse(BaseModel):
    """Response schema for a Reddit account with all DB fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="RedditAccount UUID")
    username: str = Field(..., description="Reddit username")
    status: str = Field(..., description="Account health status")
    warmup_stage: str = Field(..., description="Current warmup stage")
    niche_tags: list[Any] = Field(default_factory=list, description="Niche/topic tags")
    karma_post: int = Field(..., description="Post karma count")
    karma_comment: int = Field(..., description="Comment karma count")
    account_age_days: int | None = Field(None, description="Account age in days")
    cooldown_until: datetime | None = Field(None, description="Cooldown end time")
    last_used_at: datetime | None = Field(None, description="Last activity timestamp")
    notes: str | None = Field(None, description="Free-text notes")
    extra_metadata: dict[str, Any] | None = Field(
        None, description="Arbitrary metadata"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# ---------------------------------------------------------------------------
# RedditProjectConfig schemas
# ---------------------------------------------------------------------------


class RedditProjectConfigCreate(BaseModel):
    """Request schema for creating/updating a project's Reddit config."""

    search_keywords: list[str] = Field(
        default_factory=list, description="Keywords to monitor"
    )
    target_subreddits: list[str] = Field(
        default_factory=list, description="Subreddits to engage in"
    )
    banned_subreddits: list[str] = Field(
        default_factory=list, description="Subreddits to avoid"
    )
    competitors: list[str] = Field(
        default_factory=list, description="Competitor identifiers"
    )
    comment_instructions: str | None = Field(
        None, description="Voice/tone instructions for comments"
    )
    niche_tags: list[str] = Field(default_factory=list, description="Niche/topic tags")
    discovery_settings: dict[str, Any] | None = Field(
        None, description="Advanced discovery configuration"
    )
    is_active: bool | None = Field(
        None, description="Whether Reddit engagement is active (defaults to True on create)"
    )


class RedditProjectConfigResponse(BaseModel):
    """Response schema for a project's Reddit config with all DB fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="RedditProjectConfig UUID")
    project_id: str = Field(..., description="Parent project UUID")
    search_keywords: list[Any] = Field(
        default_factory=list, description="Keywords to monitor"
    )
    target_subreddits: list[Any] = Field(
        default_factory=list, description="Subreddits to engage in"
    )
    banned_subreddits: list[Any] = Field(
        default_factory=list, description="Subreddits to avoid"
    )
    competitors: list[Any] = Field(
        default_factory=list, description="Competitor identifiers"
    )
    comment_instructions: str | None = Field(
        None, description="Voice/tone instructions for comments"
    )
    niche_tags: list[Any] = Field(default_factory=list, description="Niche/topic tags")
    discovery_settings: dict[str, Any] | None = Field(
        None, description="Advanced discovery configuration"
    )
    is_active: bool = Field(..., description="Whether Reddit engagement is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# ---------------------------------------------------------------------------
# RedditPost schemas
# ---------------------------------------------------------------------------


class RedditPostResponse(BaseModel):
    """Response schema for a discovered Reddit post with all DB fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="RedditPost UUID")
    project_id: str = Field(..., description="Parent project UUID")
    reddit_post_id: str | None = Field(
        None, description="Native Reddit post ID (e.g. t3_xxx)"
    )
    subreddit: str = Field(..., description="Subreddit name")
    title: str = Field(..., description="Post title")
    url: str = Field(..., description="Full URL to the Reddit post")
    snippet: str | None = Field(None, description="SERP snippet or post excerpt")
    keyword: str | None = Field(None, description="Search keyword that found this post")
    intent: str | None = Field(None, description="AI-classified intent category")
    intent_categories: list[Any] | None = Field(None, description="Intent labels")
    relevance_score: float | None = Field(
        None, description="AI relevance score (0.0-1.0)"
    )
    matched_keywords: list[Any] | None = Field(
        None, description="Keywords that matched"
    )
    ai_evaluation: dict[str, Any] | None = Field(
        None, description="Full AI evaluation details"
    )
    filter_status: str = Field(..., description="Workflow filter status")
    serp_position: int | None = Field(None, description="Position in SERP results")
    discovered_at: datetime = Field(..., description="When SERP returned this result")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# ---------------------------------------------------------------------------
# Discovery schemas (Phase 14b)
# ---------------------------------------------------------------------------


class DiscoveryTriggerRequest(BaseModel):
    """Request schema for triggering post discovery."""

    time_range: str = Field(
        "7d",
        description="Time range filter for search: '24h', '7d', or '30d'",
    )


class DiscoveryTriggerResponse(BaseModel):
    """Response schema for a discovery trigger (202 Accepted)."""

    message: str = Field(..., description="Confirmation message")


class DiscoveryStatusResponse(BaseModel):
    """Response schema for polling discovery progress."""

    status: str = Field(..., description="Pipeline status: searching | scoring | storing | complete | failed | idle")
    total_keywords: int = Field(0, description="Total keywords to search")
    keywords_searched: int = Field(0, description="Keywords searched so far")
    total_posts_found: int = Field(0, description="Raw posts found from SERP")
    posts_scored: int = Field(0, description="Posts scored by Claude so far")
    posts_stored: int = Field(0, description="Posts stored in database")
    error: str | None = Field(None, description="Error message if status is 'failed'")


class PostUpdateRequest(BaseModel):
    """Request schema for updating a post's filter status."""

    filter_status: str = Field(
        ...,
        description="New filter status: 'relevant', 'low_relevance', 'pending', or 'skipped'",
    )


class BulkPostActionRequest(BaseModel):
    """Request schema for bulk post filter status updates."""

    post_ids: list[str] = Field(..., description="List of post UUIDs to update")
    filter_status: str = Field(
        ...,
        description="New filter status: 'relevant', 'low_relevance', 'pending', or 'skipped'",
    )


# ---------------------------------------------------------------------------
# RedditComment schemas
# ---------------------------------------------------------------------------


class RedditCommentResponse(BaseModel):
    """Response schema for an AI-generated Reddit comment with all DB fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="RedditComment UUID")
    post_id: str = Field(..., description="Parent Reddit post UUID")
    project_id: str = Field(..., description="Parent project UUID")
    account_id: str | None = Field(None, description="Reddit account UUID")
    body: str = Field(..., description="Current comment text")
    original_body: str = Field(..., description="AI-generated text (immutable)")
    is_promotional: bool = Field(
        ..., description="Whether comment contains promotional content"
    )
    approach_type: str | None = Field(None, description="Strategy used for the comment")
    status: str = Field(..., description="Workflow status")
    reject_reason: str | None = Field(None, description="Reason for rejection")
    crowdreply_task_id: str | None = Field(
        None, description="External CrowdReply task ID"
    )
    posted_url: str | None = Field(None, description="URL of the posted comment")
    posted_at: datetime | None = Field(
        None, description="When the comment was posted to Reddit"
    )
    generation_metadata: dict[str, Any] | None = Field(
        None, description="AI generation details"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Optional nested post
    post: RedditPostResponse | None = None


class CommentApproveRequest(BaseModel):
    """Request schema for approving a comment (optionally with edited body)."""

    body: str | None = Field(None, description="Edited comment body (optional)")


class CommentRejectRequest(BaseModel):
    """Request schema for rejecting a comment."""

    reason: str | None = Field(None, description="Reason for rejection")


class BulkCommentActionRequest(BaseModel):
    """Request schema for bulk comment operations."""

    comment_ids: list[str] = Field(..., description="List of comment UUIDs to act on")


class BulkCommentRejectRequest(BaseModel):
    """Request schema for bulk comment rejection with shared reason."""

    comment_ids: list[str] = Field(..., description="List of comment UUIDs to reject")
    reason: str = Field(..., description="Shared rejection reason for all comments")


class CommentQueueStatusCounts(BaseModel):
    """Status counts for the comment queue."""

    draft: int = 0
    approved: int = 0
    rejected: int = 0
    submitting: int = 0
    posted: int = 0
    failed: int = 0
    mod_removed: int = 0
    all: int = 0


class CommentQueueResponse(BaseModel):
    """Paginated response for the cross-project comment queue."""

    items: list[RedditCommentResponse] = Field(
        ..., description="Comment list for the current page"
    )
    total: int = Field(..., description="Total count matching current filters (excl. pagination)")
    counts: CommentQueueStatusCounts = Field(
        ..., description="Status counts (independent of status filter)"
    )


# ---------------------------------------------------------------------------
# Comment generation schemas (Phase 14c)
# ---------------------------------------------------------------------------


class RedditCommentUpdateRequest(BaseModel):
    """Request schema for updating a comment's body text."""

    body: str = Field(..., description="Updated comment body text")


class GenerateCommentRequest(BaseModel):
    """Request schema for generating a comment for a single post."""

    is_promotional: bool = Field(
        True, description="Whether to generate a promotional comment (default True)"
    )


class BatchGenerateRequest(BaseModel):
    """Request schema for batch comment generation."""

    post_ids: list[str] | None = Field(
        None,
        description="Specific post IDs to generate for. If omitted, generates for all relevant posts without comments.",
    )


class GenerationStatusResponse(BaseModel):
    """Response schema for polling batch generation progress."""

    status: str = Field(
        ...,
        description="Generation status: generating | complete | failed | idle",
    )
    total_posts: int = Field(0, description="Total posts to generate for")
    posts_generated: int = Field(0, description="Posts generated so far")
    error: str | None = Field(None, description="Error message if status is 'failed'")


# ---------------------------------------------------------------------------
# CrowdReply submission schemas (Phase 14e)
# ---------------------------------------------------------------------------


class CommentSubmitRequest(BaseModel):
    """Request to submit approved comments to CrowdReply."""

    comment_ids: list[str] | None = None  # None = all approved
    upvotes_per_comment: int | None = Field(None, ge=0, le=50)


class CommentSubmitResponse(BaseModel):
    """Response from comment submission trigger."""

    message: str
    submitted_count: int = 0


class SubmissionStatusResponse(BaseModel):
    """Polling response for submission progress."""

    status: str  # submitting | complete | failed | idle
    total_comments: int = 0
    comments_submitted: int = 0
    comments_failed: int = 0
    errors: list[str] = Field(default_factory=list)


class CrowdReplyWebhookPayload(BaseModel):
    """Incoming webhook payload from CrowdReply."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(alias="_id")
    thread_url: str = Field("", alias="threadUrl")
    task_type: str = Field("", alias="taskType")
    status: str
    content: str = ""
    client_price: float | None = Field(None, alias="clientPrice")
    task_submission: list[dict[str, Any]] = Field(
        default_factory=list, alias="taskSubmission"
    )
    published_at: str | None = Field(None, alias="publishedAt")


class CrowdReplyBalanceResponse(BaseModel):
    """CrowdReply account balance."""

    balance: float
    currency: str = "USD"


class WebhookSimulateRequest(BaseModel):
    """Request to simulate a CrowdReply webhook (dev-only)."""

    comment_id: str
    status: str = "published"
    submission_url: str | None = None


# ---------------------------------------------------------------------------
# Reddit project list schemas (dashboard)
# ---------------------------------------------------------------------------


class RedditProjectCardResponse(BaseModel):
    """Summary card for a project with Reddit configured."""

    id: str
    name: str
    site_url: str
    is_active: bool
    post_count: int
    comment_count: int
    draft_count: int
    updated_at: datetime


class RedditProjectListResponse(BaseModel):
    """Paginated list of Reddit-enabled projects."""

    items: list[RedditProjectCardResponse]
    total: int


# ---------------------------------------------------------------------------
# CrowdReplyTask schemas
# ---------------------------------------------------------------------------


class CrowdReplyTaskResponse(BaseModel):
    """Response schema for a CrowdReply task with all DB fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="CrowdReplyTask UUID")
    comment_id: str | None = Field(None, description="Reddit comment UUID")
    external_task_id: str | None = Field(None, description="CrowdReply's task ID")
    task_type: str = Field(..., description="Task type (comment/post/reply/upvote)")
    status: str = Field(..., description="Current task status")
    target_url: str = Field(..., description="Reddit URL being targeted")
    content: str = Field(..., description="Text content submitted")
    crowdreply_project_id: str | None = Field(
        None, description="CrowdReply's project identifier"
    )
    request_payload: dict[str, Any] | None = Field(
        None, description="Raw request sent to CrowdReply API"
    )
    response_payload: dict[str, Any] | None = Field(
        None, description="Raw response from CrowdReply API"
    )
    upvotes_requested: int | None = Field(
        None, description="Number of upvotes requested"
    )
    price: float | None = Field(None, description="Cost of the task")
    submitted_at: datetime | None = Field(
        None, description="When task was submitted to CrowdReply"
    )
    published_at: datetime | None = Field(
        None, description="When task was published on Reddit"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
