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
