"""Pydantic v2 schemas for Phase 9 Internal Linking API endpoints.

Schemas for link planning, link management, and link map responses:
- LinkPlanRequest: Trigger link plan generation for a scope
- LinkPlanStatusResponse: SSE/polling status during plan generation
- InternalLinkResponse: Single internal link detail
- PageLinksResponse: All links for a specific page with diversity metrics
- LinkMapPageSummary / LinkMapResponse: Full link map overview
- AddLinkRequest / EditLinkRequest: Manual link CRUD
- AnchorSuggestionsResponse: Anchor text suggestions for a target page
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# LINK PLAN REQUEST / STATUS
# =============================================================================


class LinkPlanRequest(BaseModel):
    """Request to trigger link plan generation."""

    scope: Literal["onboarding", "cluster"] = Field(
        ...,
        description="Scope of the link plan: 'onboarding' for all priority pages, 'cluster' for a single cluster",
    )
    cluster_id: str | None = Field(
        None,
        description="Required when scope='cluster'. The keyword cluster to plan links for.",
    )


class LinkPlanStatusResponse(BaseModel):
    """Status response for link plan generation (polling/SSE)."""

    status: Literal["idle", "planning", "complete", "failed"] = Field(
        ...,
        description="Current status of the link planning process",
    )
    current_step: int | None = Field(
        None,
        description="Current step number in the planning process",
    )
    step_label: str | None = Field(
        None,
        description="Human-readable label for the current step",
    )
    pages_processed: int = Field(
        0,
        description="Number of pages processed so far",
    )
    total_pages: int = Field(
        0,
        description="Total number of pages to process",
    )
    total_links: int | None = Field(
        None,
        description="Total links generated (available when complete)",
    )
    error: str | None = Field(
        None,
        description="Error message if status is 'failed'",
    )


# =============================================================================
# INTERNAL LINK RESPONSE
# =============================================================================


class InternalLinkResponse(BaseModel):
    """Response schema for a single internal link."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="InternalLink UUID")
    source_page_id: str = Field(..., description="Source page UUID")
    target_page_id: str = Field(..., description="Target page UUID")
    target_url: str = Field(..., description="Target page URL")
    target_title: str = Field(..., description="Target page title")
    target_keyword: str = Field(..., description="Target page primary keyword")
    anchor_text: str = Field(..., description="Visible anchor text of the link")
    anchor_type: str = Field(
        ...,
        description="How anchor relates to keyword: 'exact_match', 'partial_match', 'natural'",
    )
    position_in_content: int | None = Field(
        None,
        description="Character offset in content where link is placed",
    )
    is_mandatory: bool = Field(..., description="Whether this link is required")
    placement_method: str = Field(
        ...,
        description="How the link was placed: 'rule_based' or 'llm_fallback'",
    )
    status: str = Field(
        ...,
        description="Lifecycle status: 'planned', 'injected', 'verified', 'removed'",
    )


# =============================================================================
# PAGE LINKS RESPONSE
# =============================================================================


class PageLinksResponse(BaseModel):
    """All links for a specific page with anchor diversity metrics."""

    outbound_links: list[InternalLinkResponse] = Field(
        default_factory=list,
        description="Links going out from this page",
    )
    inbound_links: list[InternalLinkResponse] = Field(
        default_factory=list,
        description="Links coming in to this page",
    )
    anchor_diversity: dict[str, int] = Field(
        default_factory=dict,
        description="Anchor type breakdown: {'exact_match': N, 'partial_match': N, 'natural': N}",
    )
    diversity_score: str = Field(
        ...,
        description="Anchor diversity rating: 'good', 'needs_variation', 'poor'",
    )


# =============================================================================
# LINK MAP (FULL OVERVIEW)
# =============================================================================


class LinkMapPageSummary(BaseModel):
    """Summary of a single page within the link map."""

    page_id: str = Field(..., description="CrawledPage UUID")
    url: str = Field(..., description="Page URL")
    title: str = Field(..., description="Page title")
    is_priority: bool = Field(..., description="Whether page is marked as priority")
    role: str | None = Field(
        None,
        description="Page role within onboarding (e.g., 'parent', 'child')",
    )
    labels: list[str] | None = Field(
        None,
        description="Page labels from onboarding taxonomy",
    )
    outbound_count: int = Field(..., description="Number of outbound links from this page")
    inbound_count: int = Field(..., description="Number of inbound links to this page")
    methods: dict[str, int] = Field(
        default_factory=dict,
        description="Placement method breakdown: {'rule_based': N, 'llm_fallback': N}",
    )
    validation_status: str = Field(
        ...,
        description="Validation status: 'pass', 'warning', 'fail'",
    )


class LinkMapResponse(BaseModel):
    """Full link map overview for a scope."""

    scope: str = Field(..., description="Link map scope: 'onboarding' or 'cluster'")
    total_links: int = Field(..., description="Total number of internal links")
    total_pages: int = Field(..., description="Total number of pages in the map")
    avg_links_per_page: float = Field(..., description="Average links per page")
    validation_pass_rate: float = Field(
        ...,
        description="Percentage of pages passing validation (0-100)",
    )
    method_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Placement method totals: {'rule_based': N, 'llm_fallback': N}",
    )
    anchor_diversity: dict[str, Any] = Field(
        default_factory=dict,
        description="Overall anchor type distribution and diversity metrics",
    )
    pages: list[LinkMapPageSummary] = Field(
        default_factory=list,
        description="Per-page link summaries",
    )
    hierarchy: dict[str, Any] | None = Field(
        None,
        description="Cluster hierarchy structure (only for cluster scope)",
    )


# =============================================================================
# MANUAL LINK CRUD
# =============================================================================


class AddLinkRequest(BaseModel):
    """Request to manually add an internal link."""

    source_page_id: str = Field(..., description="Source page UUID")
    target_page_id: str = Field(..., description="Target page UUID")
    anchor_text: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Visible anchor text for the link",
    )
    anchor_type: Literal["exact_match", "partial_match", "natural"] = Field(
        ...,
        description="How anchor text relates to target keyword",
    )


class EditLinkRequest(BaseModel):
    """Request to edit an existing internal link's anchor."""

    anchor_text: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Updated anchor text",
    )
    anchor_type: Literal["exact_match", "partial_match", "natural"] = Field(
        ...,
        description="Updated anchor type",
    )


# =============================================================================
# ANCHOR SUGGESTIONS
# =============================================================================


class AnchorSuggestionsResponse(BaseModel):
    """Suggested anchor text variations for a target page."""

    primary_keyword: str = Field(
        ...,
        description="The target page's primary keyword",
    )
    pop_variations: list[str] = Field(
        default_factory=list,
        description="Suggested anchor text variations based on keyword",
    )
    usage_counts: dict[str, int] = Field(
        default_factory=dict,
        description="How many times each anchor text is already used: {'anchor text': count}",
    )
