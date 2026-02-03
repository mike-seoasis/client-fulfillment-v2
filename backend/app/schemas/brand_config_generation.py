"""Brand config generation schemas.

Pydantic models for brand config generation API responses.
"""

from pydantic import BaseModel, ConfigDict, Field


class GenerationStatusResponse(BaseModel):
    """Response schema for brand config generation status.

    Attributes:
        status: Current generation status (pending, generating, complete, failed)
        current_step: Name of the current step being processed
        steps_completed: Number of steps completed
        steps_total: Total number of steps
        error: Error message if generation failed
        started_at: ISO timestamp when generation started
        completed_at: ISO timestamp when generation completed
    """

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(
        ...,
        description="Current generation status",
        examples=["pending", "generating", "complete", "failed"],
    )
    current_step: str | None = Field(
        None,
        description="Name of the current step being processed",
        examples=["brand_foundation", "target_audience"],
    )
    steps_completed: int = Field(
        0,
        description="Number of steps completed",
        ge=0,
    )
    steps_total: int = Field(
        0,
        description="Total number of steps",
        ge=0,
    )
    error: str | None = Field(
        None,
        description="Error message if generation failed",
    )
    started_at: str | None = Field(
        None,
        description="ISO timestamp when generation started",
        examples=["2026-02-03T12:00:00+00:00"],
    )
    completed_at: str | None = Field(
        None,
        description="ISO timestamp when generation completed",
        examples=["2026-02-03T12:05:00+00:00"],
    )
