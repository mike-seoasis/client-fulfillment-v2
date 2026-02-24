"""Pydantic v2 schemas for BlogCampaign and BlogPost API endpoints.

Schemas for blog campaign management, post CRUD, content generation, and export:
- BlogCampaignCreate: Request to create a new blog campaign from a cluster
- BlogPostResponse: Full post response (content truncated in list views)
- BlogCampaignResponse: Full campaign response with nested posts
- BlogCampaignListItem: Summary response for campaign list views
- BlogPostUpdate: Request to update keyword-level fields on a post
- BlogContentUpdateRequest: Request to update content fields on a post
- BlogContentGenerationStatus: Status of content generation across a campaign
- BlogExportItem: Single post export with full HTML content
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BlogCampaignCreate(BaseModel):
    """Request schema for creating a blog campaign from a keyword cluster."""

    cluster_id: str = Field(
        ...,
        description="UUID of the keyword cluster to create a campaign for",
    )
    name: str | None = Field(
        None,
        description="Display name for the campaign (auto-generated from cluster if not provided)",
    )


class BlogPostResponse(BaseModel):
    """Response schema for a single blog post with all fields.

    NOTE: In list views, content is truncated to a preview snippet.
    Use the single-post detail endpoint for full content.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="BlogPost UUID")
    campaign_id: str = Field(..., description="Parent campaign UUID")
    primary_keyword: str = Field(..., description="Target keyword for this post")
    url_slug: str = Field(..., description="Generated URL slug")
    search_volume: int | None = Field(
        None, description="Estimated monthly search volume"
    )
    source_page_id: str | None = Field(
        None, description="Link to cluster page that seeded this topic"
    )
    title: str | None = Field(None, description="Page title")
    meta_description: str | None = Field(None, description="Meta description for SEO")
    content: str | None = Field(
        None, description="HTML content (truncated in list views)"
    )
    is_approved: bool = Field(..., description="Whether the keyword is approved")
    content_status: str = Field(..., description="Content generation status")
    content_approved: bool = Field(..., description="Whether the content is approved")
    pop_brief: dict[str, Any] | None = Field(None, description="POP brief data summary")
    qa_results: dict[str, Any] | None = Field(None, description="QA check results")
    status: str = Field(..., description="Overall post status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class BlogCampaignResponse(BaseModel):
    """Full campaign response with nested posts."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="BlogCampaign UUID")
    project_id: str = Field(..., description="Parent project UUID")
    cluster_id: str = Field(..., description="Keyword cluster UUID")
    name: str = Field(..., description="Display name")
    status: str = Field(..., description="Workflow status")
    generation_metadata: dict[str, Any] | None = Field(
        None, description="AI generation context"
    )
    posts: list[BlogPostResponse] = Field(
        default_factory=list, description="Posts in this campaign"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class BlogCampaignListItem(BaseModel):
    """Summary response for campaign list views."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="BlogCampaign UUID")
    name: str = Field(..., description="Display name")
    status: str = Field(..., description="Workflow status")
    cluster_name: str = Field(..., description="Name of the associated keyword cluster")
    post_count: int = Field(..., description="Total number of posts in campaign")
    approved_count: int = Field(..., description="Number of approved posts")
    content_complete_count: int = Field(
        ..., description="Number of posts with completed content"
    )
    created_at: datetime = Field(..., description="Creation timestamp")


class BlogPostUpdate(BaseModel):
    """Request schema for updating keyword-level fields on a post."""

    primary_keyword: str | None = Field(None, description="Target keyword")
    url_slug: str | None = Field(None, description="URL slug")
    is_approved: bool | None = Field(None, description="Keyword approval status")
    title: str | None = Field(None, description="Proposed blog post title")


class BlogContentUpdateRequest(BaseModel):
    """Request schema for updating content fields on a post."""

    title: str | None = Field(None, description="Page title")
    meta_description: str | None = Field(None, description="Meta description for SEO")
    content: str | None = Field(None, description="HTML content")


class BlogPostGenerationStatusItem(BaseModel):
    """Per-post status within a content generation run."""

    post_id: str = Field(..., description="BlogPost UUID")
    primary_keyword: str = Field(..., description="Target keyword")
    content_status: str = Field(..., description="Content generation status")


class BlogContentGenerationStatus(BaseModel):
    """Status of content generation across a campaign."""

    overall_status: str = Field(
        ..., description="Aggregate status (pending/generating/complete/failed)"
    )
    posts_total: int = Field(..., description="Total number of posts")
    posts_completed: int = Field(
        ..., description="Number of posts with completed content"
    )
    posts_failed: int = Field(..., description="Number of posts that failed generation")
    posts: list[BlogPostGenerationStatusItem] = Field(
        default_factory=list, description="Per-post status items"
    )


class BlogContentTriggerResponse(BaseModel):
    """Response returned when blog content generation is triggered."""

    status: str = Field(
        "accepted",
        description="Request status (always 'accepted' on success)",
    )
    message: str = Field(
        ...,
        description="Human-readable message about what was triggered",
    )


class BlogBulkApproveResponse(BaseModel):
    """Response for bulk content approval endpoint."""

    approved_count: int = Field(
        ..., ge=0, description="Number of posts approved in this request"
    )


class BlogExportItem(BaseModel):
    """Single post export with full HTML content and metadata."""

    post_id: str = Field(..., description="BlogPost UUID")
    primary_keyword: str = Field(..., description="Target keyword")
    url_slug: str = Field(..., description="URL slug")
    title: str | None = Field(None, description="Page title")
    meta_description: str | None = Field(None, description="Meta description")
    html_content: str | None = Field(None, description="Full HTML content")
    word_count: int = Field(..., description="Word count of the content")


class BlogLinkPlanTriggerResponse(BaseModel):
    """Response when blog link planning is triggered."""

    status: str = Field(
        "accepted",
        description="Request status (always 'accepted' on success)",
    )
    message: str = Field(
        ...,
        description="Human-readable message about what was triggered",
    )


class BlogLinkStatusResponse(BaseModel):
    """Status of blog link planning for a single post."""

    status: str = Field(
        ..., description="Planning status (pending/planning/complete/failed)"
    )
    step: str | None = Field(None, description="Current pipeline step")
    links_planned: int = Field(0, description="Number of links planned/injected")
    error: str | None = Field(None, description="Error message if failed")


class BlogLinkMapItem(BaseModel):
    """A single planned/injected link for a blog post."""

    target_page_id: str = Field(..., description="CrawledPage UUID of the target")
    anchor_text: str = Field(..., description="Anchor text used for the link")
    anchor_type: str = Field(
        ..., description="Type of anchor text (exact_match/partial_match/natural)"
    )
    target_keyword: str | None = Field(None, description="Target page keyword")
    target_url: str | None = Field(None, description="Target page URL")
    placement_method: str = Field(
        ..., description="How the link was placed (rule_based/llm_fallback)"
    )
    status: str = Field(..., description="Link status (planned/injected/verified)")


class BlogLinkMapResponse(BaseModel):
    """Full link map for a blog post."""

    blog_post_id: str = Field(..., description="BlogPost UUID")
    crawled_page_id: str | None = Field(
        None, description="CrawledPage UUID for this blog post"
    )
    total_links: int = Field(..., description="Total number of links")
    links: list[BlogLinkMapItem] = Field(
        default_factory=list, description="List of planned links"
    )
