"""Brand configuration service for managing brand config generation.

Orchestrates the brand configuration generation process, including:
- Starting generation as a background task
- Tracking generation status in project.brand_wizard_state
- Reporting current progress
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


class GenerationStatusValue(str, Enum):
    """Possible status values for brand config generation."""

    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class GenerationStatus:
    """Status of brand config generation for a project.

    Attributes:
        status: Current generation status (pending, generating, complete, failed)
        current_step: Name of the current step being processed
        steps_completed: Number of steps completed
        steps_total: Total number of steps
        error: Error message if generation failed
        started_at: Timestamp when generation started
        completed_at: Timestamp when generation completed
    """

    status: GenerationStatusValue
    current_step: str | None = None
    steps_completed: int = 0
    steps_total: int = 0
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSONB storage."""
        return {
            "status": self.status.value,
            "current_step": self.current_step,
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationStatus":
        """Create from dictionary (JSONB data)."""
        return cls(
            status=GenerationStatusValue(data.get("status", "pending")),
            current_step=data.get("current_step"),
            steps_completed=data.get("steps_completed", 0),
            steps_total=data.get("steps_total", 0),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


# Generation steps for brand config (matches the 9 sections from brand research)
GENERATION_STEPS = [
    "brand_foundation",
    "target_audience",
    "voice_dimensions",
    "voice_characteristics",
    "writing_style",
    "vocabulary",
    "trust_elements",
    "examples_bank",
    "competitor_context",
]


class BrandConfigService:
    """Service for orchestrating brand configuration generation.

    Manages the generation lifecycle including starting background tasks,
    tracking progress, and reporting status. Status is persisted in the
    project's brand_wizard_state JSONB field.
    """

    @staticmethod
    async def _get_project(db: AsyncSession, project_id: str) -> Project:
        """Get a project by ID.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.

        Returns:
            Project instance.

        Raises:
            HTTPException: 404 if project not found.
        """
        stmt = select(Project).where(Project.id == project_id)
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()

        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with id '{project_id}' not found",
            )

        return project

    @staticmethod
    async def get_status(db: AsyncSession, project_id: str) -> GenerationStatus:
        """Get the current generation status for a project.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.

        Returns:
            GenerationStatus with current generation state.

        Raises:
            HTTPException: 404 if project not found.
        """
        project = await BrandConfigService._get_project(db, project_id)

        # Extract generation status from brand_wizard_state
        wizard_state = project.brand_wizard_state or {}
        generation_data = wizard_state.get("generation", {})

        if not generation_data:
            # No generation started yet
            return GenerationStatus(status=GenerationStatusValue.PENDING)

        return GenerationStatus.from_dict(generation_data)

    @staticmethod
    async def start_generation(db: AsyncSession, project_id: str) -> GenerationStatus:
        """Start brand config generation for a project.

        Initializes the generation state and kicks off the background task.
        If generation is already in progress, returns current status.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.

        Returns:
            GenerationStatus with initial generation state.

        Raises:
            HTTPException: 404 if project not found.
            HTTPException: 409 if generation is already in progress.
        """
        project = await BrandConfigService._get_project(db, project_id)

        # Check if generation is already in progress
        wizard_state = project.brand_wizard_state or {}
        generation_data = wizard_state.get("generation", {})

        if generation_data.get("status") == GenerationStatusValue.GENERATING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Brand config generation is already in progress",
            )

        # Initialize generation status
        initial_status = GenerationStatus(
            status=GenerationStatusValue.GENERATING,
            current_step=GENERATION_STEPS[0],
            steps_completed=0,
            steps_total=len(GENERATION_STEPS),
            started_at=datetime.now(UTC).isoformat(),
        )

        # Update project's brand_wizard_state
        new_wizard_state = {
            **wizard_state,
            "generation": initial_status.to_dict(),
        }
        project.brand_wizard_state = new_wizard_state

        await db.flush()
        await db.refresh(project)

        # TODO: Kick off background task for actual generation
        # This will be implemented in a later story when we wire up
        # the Perplexity research and Claude generation pipeline

        return initial_status

    @staticmethod
    async def update_progress(
        db: AsyncSession,
        project_id: str,
        current_step: str,
        steps_completed: int,
    ) -> GenerationStatus:
        """Update generation progress for a project.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.
            current_step: Name of the current step.
            steps_completed: Number of steps completed.

        Returns:
            Updated GenerationStatus.

        Raises:
            HTTPException: 404 if project not found.
        """
        project = await BrandConfigService._get_project(db, project_id)

        wizard_state = project.brand_wizard_state or {}
        generation_data = wizard_state.get("generation", {})

        # Update progress
        generation_data["current_step"] = current_step
        generation_data["steps_completed"] = steps_completed

        new_wizard_state = {
            **wizard_state,
            "generation": generation_data,
        }
        project.brand_wizard_state = new_wizard_state

        await db.flush()
        await db.refresh(project)

        return GenerationStatus.from_dict(generation_data)

    @staticmethod
    async def complete_generation(
        db: AsyncSession,
        project_id: str,
    ) -> GenerationStatus:
        """Mark generation as complete for a project.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.

        Returns:
            Updated GenerationStatus.

        Raises:
            HTTPException: 404 if project not found.
        """
        project = await BrandConfigService._get_project(db, project_id)

        wizard_state = project.brand_wizard_state or {}
        generation_data = wizard_state.get("generation", {})

        # Mark as complete
        generation_data["status"] = GenerationStatusValue.COMPLETE.value
        generation_data["current_step"] = None
        generation_data["steps_completed"] = len(GENERATION_STEPS)
        generation_data["completed_at"] = datetime.now(UTC).isoformat()

        new_wizard_state = {
            **wizard_state,
            "generation": generation_data,
        }
        project.brand_wizard_state = new_wizard_state

        await db.flush()
        await db.refresh(project)

        return GenerationStatus.from_dict(generation_data)

    @staticmethod
    async def fail_generation(
        db: AsyncSession,
        project_id: str,
        error: str,
    ) -> GenerationStatus:
        """Mark generation as failed for a project.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.
            error: Error message describing the failure.

        Returns:
            Updated GenerationStatus.

        Raises:
            HTTPException: 404 if project not found.
        """
        project = await BrandConfigService._get_project(db, project_id)

        wizard_state = project.brand_wizard_state or {}
        generation_data = wizard_state.get("generation", {})

        # Mark as failed
        generation_data["status"] = GenerationStatusValue.FAILED.value
        generation_data["error"] = error
        generation_data["completed_at"] = datetime.now(UTC).isoformat()

        new_wizard_state = {
            **wizard_state,
            "generation": generation_data,
        }
        project.brand_wizard_state = new_wizard_state

        await db.flush()
        await db.refresh(project)

        return GenerationStatus.from_dict(generation_data)
