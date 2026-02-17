"""Pydantic v2 schemas for WordPress blog linking tool API endpoints.

Schemas for the 7-step wizard: Connect, Import, Analyze, Label, Plan, Review, Export.
"""

from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# STEP 1: CONNECT
# =============================================================================


class WPConnectRequest(BaseModel):
    """Request to validate WordPress credentials."""

    site_url: str = Field(..., description="WordPress site URL (e.g. https://example.com)")
    username: str = Field(..., description="WordPress username")
    app_password: str = Field(..., description="WordPress application password")


class WPConnectResponse(BaseModel):
    """Response from credential validation."""

    site_name: str = Field(..., description="WordPress site name")
    site_url: str = Field(..., description="WordPress site URL")
    total_posts: int = Field(..., description="Total published posts on the site")
    valid: bool = Field(..., description="Whether credentials are valid")


# =============================================================================
# STEP 2: IMPORT
# =============================================================================


class WPImportRequest(BaseModel):
    """Request to import WordPress posts."""

    site_url: str = Field(..., description="WordPress site URL")
    username: str = Field(..., description="WordPress username")
    app_password: str = Field(..., description="WordPress application password")
    title_filter: list[str] | None = Field(
        None,
        description="Optional list of title substrings to filter posts",
    )
    post_status: str = Field(
        "publish",
        description="WordPress post status to fetch: 'publish', 'private', or 'any'",
    )
    existing_project_id: str | None = Field(
        None,
        description="Optional existing project ID to import WP posts into (for blog→collection linking)",
    )


class WPImportResponse(BaseModel):
    """Response from post import."""

    project_id: str = Field(..., description="Created project UUID")
    posts_imported: int = Field(..., description="Number of posts imported")
    job_id: str = Field(..., description="Job ID for progress polling")


# =============================================================================
# STEP 3: ANALYZE (POP)
# =============================================================================


class WPAnalyzeRequest(BaseModel):
    """Request to run POP analysis on imported posts."""

    project_id: str = Field(..., description="Project UUID from import step")


# =============================================================================
# STEP 4: LABEL
# =============================================================================


class WPLabelRequest(BaseModel):
    """Request to generate taxonomy and assign labels."""

    project_id: str = Field(..., description="Project UUID")


class WPLabelAssignment(BaseModel):
    """Label assignment for a single post."""

    page_id: str = Field(..., description="CrawledPage UUID")
    title: str = Field(..., description="Post title")
    url: str = Field(..., description="Post URL")
    labels: list[str] = Field(..., description="Assigned labels (primary first)")
    primary_label: str = Field(..., description="Primary label (silo group)")


class WPTaxonomyLabel(BaseModel):
    """A label in the generated taxonomy."""

    name: str = Field(..., description="Label slug (e.g. 'seo-strategy')")
    description: str = Field(..., description="What this label covers")
    post_count: int = Field(0, description="Number of posts assigned this label")


class WPLabelReviewResponse(BaseModel):
    """Response for reviewing taxonomy and label assignments."""

    taxonomy: list[WPTaxonomyLabel] = Field(..., description="Generated taxonomy labels")
    assignments: list[WPLabelAssignment] = Field(..., description="Per-post label assignments")
    total_groups: int = Field(..., description="Number of silo groups (unique primary labels)")


# =============================================================================
# STEP 5: PLAN
# =============================================================================


class WPPlanRequest(BaseModel):
    """Request to plan internal links per silo."""

    project_id: str = Field(..., description="Project UUID")


# =============================================================================
# STEP 6: REVIEW
# =============================================================================


class WPReviewGroup(BaseModel):
    """Link stats for a single silo group."""

    group_name: str = Field(..., description="Silo group label name")
    post_count: int = Field(..., description="Number of posts in this group")
    link_count: int = Field(..., description="Number of internal links in this group")
    avg_links_per_post: float = Field(..., description="Average links per post")
    collection_link_count: int = Field(0, description="Number of links targeting collection/onboarding pages")


class WPReviewResponse(BaseModel):
    """Response for reviewing planned links."""

    total_posts: int = Field(..., description="Total posts with links")
    total_links: int = Field(..., description="Total internal links planned")
    avg_links_per_post: float = Field(..., description="Average links per post across all groups")
    groups: list[WPReviewGroup] = Field(..., description="Per-group link stats")
    validation_pass_rate: float = Field(..., description="Percentage of pages passing validation (0-100)")


# =============================================================================
# STEP 7: EXPORT
# =============================================================================


class WPExportRequest(BaseModel):
    """Request to export modified content back to WordPress."""

    project_id: str = Field(..., description="Project UUID")
    site_url: str = Field(..., description="WordPress site URL")
    username: str = Field(..., description="WordPress username")
    app_password: str = Field(..., description="WordPress application password")
    title_filter: list[str] | None = Field(
        None,
        description="Optional title filter to export only specific posts",
    )


# =============================================================================
# PROJECT PICKER (for linking to existing projects)
# =============================================================================


class WPProjectOption(BaseModel):
    """A project available for importing WP posts into."""

    id: str = Field(..., description="Project UUID")
    name: str = Field(..., description="Project name")
    site_url: str = Field(..., description="Project site URL")
    collection_page_count: int = Field(..., description="Number of onboarding collection pages")


# =============================================================================
# PROGRESS (shared across steps)
# =============================================================================


class WPProgressResponse(BaseModel):
    """Progress response for any background operation."""

    job_id: str = Field(..., description="Job ID being tracked")
    step: str = Field(..., description="Current step name (e.g. 'import', 'analyze', 'label')")
    step_label: str = Field(..., description="Human-readable step description")
    status: str = Field(..., description="Status: 'running', 'complete', 'failed'")
    current: int = Field(0, description="Current progress count")
    total: int = Field(0, description="Total items to process")
    error: str | None = Field(None, description="Error message if failed")
    result: dict[str, Any] | None = Field(None, description="Result data when complete")
