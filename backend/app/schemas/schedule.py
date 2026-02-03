"""Pydantic schemas for Schedule configuration validation.

Defines request/response models for Schedule API endpoints with validation rules.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Valid schedule types
VALID_SCHEDULE_TYPES = frozenset({"manual", "daily", "weekly", "monthly", "cron"})


class ScheduleConfigCreate(BaseModel):
    """Schema for creating a new schedule configuration."""

    schedule_type: str = Field(
        ...,
        description="Type of schedule: manual, daily, weekly, monthly, or cron",
    )
    cron_expression: str | None = Field(
        None,
        max_length=100,
        description="Cron expression for custom schedules (e.g., '0 2 * * *')",
    )
    start_url: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="The URL to start crawling from",
    )
    max_pages: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum number of pages to crawl per run",
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum crawl depth from start URL",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional configuration (selectors, patterns, etc.)",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the schedule is currently active",
    )

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, v: str) -> str:
        """Validate schedule type is a known value."""
        if v not in VALID_SCHEDULE_TYPES:
            raise ValueError(
                f"Invalid schedule_type '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_SCHEDULE_TYPES))}"
            )
        return v

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: str | None) -> str | None:
        """Validate cron expression format (basic check)."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # Basic cron validation: should have 5 fields (minute hour day month weekday)
        parts = v.split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression '{v}'. "
                "Expected 5 space-separated fields (minute hour day month weekday)"
            )
        return v

    @field_validator("start_url")
    @classmethod
    def validate_start_url(cls, v: str) -> str:
        """Validate and normalize start URL."""
        v = v.strip()
        if not v:
            raise ValueError("start_url cannot be empty or whitespace only")
        if not v.startswith(("http://", "https://")):
            raise ValueError("start_url must start with http:// or https://")
        return v


class ScheduleConfigUpdate(BaseModel):
    """Schema for updating an existing schedule configuration."""

    schedule_type: str | None = Field(
        None,
        description="Type of schedule: manual, daily, weekly, monthly, or cron",
    )
    cron_expression: str | None = Field(
        None,
        max_length=100,
        description="Cron expression for custom schedules",
    )
    start_url: str | None = Field(
        None,
        min_length=1,
        max_length=2048,
        description="The URL to start crawling from",
    )
    max_pages: int | None = Field(
        None,
        ge=1,
        le=10000,
        description="Maximum number of pages to crawl per run",
    )
    max_depth: int | None = Field(
        None,
        ge=1,
        le=10,
        description="Maximum crawl depth from start URL",
    )
    config: dict[str, Any] | None = Field(
        None,
        description="Additional configuration (selectors, patterns, etc.)",
    )
    is_active: bool | None = Field(
        None,
        description="Whether the schedule is currently active",
    )

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, v: str | None) -> str | None:
        """Validate schedule type is a known value."""
        if v is None:
            return None
        if v not in VALID_SCHEDULE_TYPES:
            raise ValueError(
                f"Invalid schedule_type '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_SCHEDULE_TYPES))}"
            )
        return v

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: str | None) -> str | None:
        """Validate cron expression format (basic check)."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        parts = v.split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression '{v}'. "
                "Expected 5 space-separated fields (minute hour day month weekday)"
            )
        return v

    @field_validator("start_url")
    @classmethod
    def validate_start_url(cls, v: str | None) -> str | None:
        """Validate and normalize start URL."""
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("start_url cannot be empty or whitespace only")
        if not v.startswith(("http://", "https://")):
            raise ValueError("start_url must start with http:// or https://")
        return v


class ScheduleConfigResponse(BaseModel):
    """Schema for schedule configuration response."""

    id: str = Field(..., description="Schedule UUID")
    project_id: str = Field(..., description="Project UUID")
    schedule_type: str = Field(..., description="Type of schedule")
    cron_expression: str | None = Field(None, description="Cron expression if set")
    start_url: str = Field(..., description="Start URL for crawling")
    max_pages: int | None = Field(None, description="Maximum pages to crawl")
    max_depth: int | None = Field(None, description="Maximum crawl depth")
    config: dict[str, Any] = Field(..., description="Additional configuration")
    is_active: bool = Field(..., description="Whether schedule is active")
    last_run_at: datetime | None = Field(None, description="When schedule last ran")
    next_run_at: datetime | None = Field(
        None, description="When schedule will next run"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ScheduleConfigListResponse(BaseModel):
    """Schema for paginated schedule configuration list response."""

    items: list[ScheduleConfigResponse] = Field(
        ..., description="List of schedule configurations"
    )
    total: int = Field(..., ge=0, description="Total count of schedules")
    limit: int = Field(..., ge=1, description="Page size limit")
    offset: int = Field(..., ge=0, description="Offset from start")
