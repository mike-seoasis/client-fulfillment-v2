"""Pydantic schemas for Project validation.

Defines request/response models for Project API endpoints with validation rules.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Valid project statuses
VALID_PROJECT_STATUSES = frozenset(
    {"active", "completed", "on_hold", "cancelled", "archived"}
)

# Valid phase statuses
VALID_PHASE_STATUSES = frozenset(
    {"pending", "in_progress", "completed", "blocked", "skipped"}
)

# Valid phase names (renamed for UX clarity)
VALID_PHASES = frozenset(
    {
        "brand_setup",  # was: discovery
        "site_analysis",  # was: requirements
        "content_generation",  # was: implementation
        "review_edit",  # was: review
        "export",  # was: launch
    }
)

# Phase display labels for UI
PHASE_LABELS = {
    "brand_setup": "Brand Setup",
    "site_analysis": "Site Analysis",
    "content_generation": "Content Generation",
    "review_edit": "Review & Edit",
    "export": "Export",
}


class PhaseStatusEntry(BaseModel):
    """Schema for a single phase status entry."""

    status: str = Field(..., description="Status of the phase")
    started_at: datetime | None = Field(None, description="When the phase started")
    completed_at: datetime | None = Field(None, description="When the phase completed")
    blocked_reason: str | None = Field(None, description="Reason if phase is blocked")

    model_config = ConfigDict(extra="allow")  # Allow additional metadata

    @field_validator("status")
    @classmethod
    def validate_phase_status(cls, v: str) -> str:
        """Validate phase status is a known value."""
        if v not in VALID_PHASE_STATUSES:
            raise ValueError(
                f"Invalid phase status '{v}'. Must be one of: {', '.join(sorted(VALID_PHASE_STATUSES))}"
            )
        return v


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Project name",
    )
    client_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Client identifier",
    )
    status: str = Field(
        default="active",
        description="Project status",
    )
    phase_status: dict[str, Any] = Field(
        default_factory=dict,
        description="Initial phase status dictionary",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and normalize project name."""
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be empty or whitespace only")
        return v

    @field_validator("client_id")
    @classmethod
    def validate_client_id(cls, v: str) -> str:
        """Validate client ID."""
        v = v.strip()
        if not v:
            raise ValueError("Client ID cannot be empty or whitespace only")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate project status is a known value."""
        if v not in VALID_PROJECT_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(VALID_PROJECT_STATUSES))}"
            )
        return v

    @field_validator("phase_status")
    @classmethod
    def validate_phase_status(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate phase_status structure."""
        for phase_name, phase_data in v.items():
            if phase_name not in VALID_PHASES:
                raise ValueError(
                    f"Invalid phase '{phase_name}'. Must be one of: {', '.join(sorted(VALID_PHASES))}"
                )
            if (
                isinstance(phase_data, dict)
                and "status" in phase_data
                and phase_data["status"] not in VALID_PHASE_STATUSES
            ):
                raise ValueError(
                    f"Invalid status '{phase_data['status']}' for phase '{phase_name}'. "
                    f"Must be one of: {', '.join(sorted(VALID_PHASE_STATUSES))}"
                )
        return v


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project."""

    name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="New project name",
    )
    status: str | None = Field(
        None,
        description="New project status",
    )
    phase_status: dict[str, Any] | None = Field(
        None,
        description="Updated phase status dictionary",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate and normalize project name."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("Project name cannot be empty or whitespace only")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        """Validate project status is a known value."""
        if v is None:
            return None
        if v not in VALID_PROJECT_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(VALID_PROJECT_STATUSES))}"
            )
        return v

    @field_validator("phase_status")
    @classmethod
    def validate_phase_status(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate phase_status structure."""
        if v is None:
            return None
        for phase_name, phase_data in v.items():
            if phase_name not in VALID_PHASES:
                raise ValueError(
                    f"Invalid phase '{phase_name}'. Must be one of: {', '.join(sorted(VALID_PHASES))}"
                )
            if (
                isinstance(phase_data, dict)
                and "status" in phase_data
                and phase_data["status"] not in VALID_PHASE_STATUSES
            ):
                raise ValueError(
                    f"Invalid status '{phase_data['status']}' for phase '{phase_name}'. "
                    f"Must be one of: {', '.join(sorted(VALID_PHASE_STATUSES))}"
                )
        return v


class PhaseStatusUpdate(BaseModel):
    """Schema for updating a single phase status."""

    phase: str = Field(..., description="Phase name to update")
    status: str = Field(..., description="New status for the phase")
    metadata: dict[str, Any] | None = Field(
        None,
        description="Additional metadata for the phase",
    )

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, v: str) -> str:
        """Validate phase name."""
        if v not in VALID_PHASES:
            raise ValueError(
                f"Invalid phase '{v}'. Must be one of: {', '.join(sorted(VALID_PHASES))}"
            )
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate phase status."""
        if v not in VALID_PHASE_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(VALID_PHASE_STATUSES))}"
            )
        return v


class ProjectResponse(BaseModel):
    """Schema for project response."""

    id: str = Field(..., description="Project UUID")
    name: str = Field(..., description="Project name")
    client_id: str = Field(..., description="Client identifier")
    status: str = Field(..., description="Project status")
    phase_status: dict[str, Any] = Field(..., description="Phase status dictionary")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ProjectListResponse(BaseModel):
    """Schema for paginated project list response."""

    items: list[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., ge=0, description="Total count of projects")
    limit: int = Field(..., ge=1, description="Page size limit")
    offset: int = Field(..., ge=0, description="Offset from start")
