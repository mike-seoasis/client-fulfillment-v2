"""Pydantic v2 schemas for KeywordCluster and ClusterPage API endpoints.

Schemas for cluster creation, page management, and list/detail responses:
- ClusterCreate: Request to create a new keyword cluster
- ClusterPageResponse: Response for a single cluster page with all fields
- ClusterResponse: Full cluster response with nested pages
- ClusterListResponse: Summary response for cluster list views
- ClusterPageUpdate: Request to update editable fields on a cluster page
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClusterCreate(BaseModel):
    """Request schema for creating a new keyword cluster."""

    seed_keyword: str = Field(
        ...,
        min_length=2,
        description="The root keyword to build the cluster around",
    )
    name: str | None = Field(
        None,
        description="Display name for the cluster (auto-generated from seed_keyword if not provided)",
    )


class ClusterPageResponse(BaseModel):
    """Response schema for a single cluster page with all fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="ClusterPage UUID")
    keyword: str = Field(..., description="Target keyword for this page")
    role: str = Field(..., description="Role within the cluster (parent or child)")
    url_slug: str = Field(..., description="Generated URL slug")
    expansion_strategy: str | None = Field(
        None, description="AI-generated strategy for content expansion"
    )
    reasoning: str | None = Field(
        None, description="AI reasoning for this page's inclusion"
    )
    search_volume: int | None = Field(
        None, description="Estimated monthly search volume"
    )
    cpc: float | None = Field(None, description="Cost per click")
    competition: float | None = Field(None, description="Competition score (0-1)")
    competition_level: str | None = Field(None, description="Competition level label")
    composite_score: float | None = Field(
        None, description="Overall score combining metrics"
    )
    is_approved: bool = Field(
        ..., description="Whether approved for content generation"
    )
    crawled_page_id: str | None = Field(
        None, description="Link to existing crawled page"
    )


class ClusterResponse(BaseModel):
    """Full cluster response with nested pages."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="KeywordCluster UUID")
    project_id: str = Field(..., description="Parent project UUID")
    seed_keyword: str = Field(..., description="Root keyword for the cluster")
    name: str = Field(..., description="Display name")
    status: str = Field(..., description="Workflow status")
    generation_metadata: dict[str, Any] | None = Field(
        None, description="AI generation context"
    )
    pages: list[ClusterPageResponse] = Field(
        default_factory=list, description="Pages in this cluster"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ClusterListResponse(BaseModel):
    """Summary response for cluster list views."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="KeywordCluster UUID")
    seed_keyword: str = Field(..., description="Root keyword for the cluster")
    name: str = Field(..., description="Display name")
    status: str = Field(..., description="Workflow status")
    page_count: int = Field(..., description="Total number of pages in cluster")
    approved_count: int = Field(..., description="Number of approved pages")
    created_at: datetime = Field(..., description="Creation timestamp")


class ClusterPageUpdate(BaseModel):
    """Request schema for updating editable fields on a cluster page."""

    is_approved: bool | None = Field(None, description="Approval status")
    keyword: str | None = Field(None, description="Target keyword")
    url_slug: str | None = Field(None, description="URL slug")
    role: str | None = Field(None, description="Role (parent or child)")


class ClusterPageAdd(BaseModel):
    """Request schema for manually adding a keyword to a cluster."""

    keyword: str = Field(
        ...,
        min_length=2,
        description="Target keyword for the new page",
    )
