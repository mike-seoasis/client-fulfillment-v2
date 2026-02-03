"""Brand configuration service for managing brand config generation.

Orchestrates the brand configuration generation process, including:
- Starting generation as a background task
- Tracking generation status in project.brand_wizard_state
- Reporting current progress
- Research phase: parallel data gathering from Perplexity, Crawl4AI, and documents
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.crawl4ai import Crawl4AIClient, CrawlResult
from app.integrations.perplexity import BrandResearchResult, PerplexityClient
from app.models.project import Project
from app.models.project_file import ProjectFile

logger = logging.getLogger(__name__)


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


@dataclass
class ResearchContext:
    """Combined research data from all sources for brand config generation.

    Attributes:
        perplexity_research: Raw text from Perplexity brand research (or None if failed)
        perplexity_citations: Citations from Perplexity research
        crawl_content: Markdown content from website crawl (or None if failed)
        crawl_metadata: Metadata from crawl result
        document_texts: List of extracted text from uploaded project files
        errors: List of error messages from failed research sources
    """

    perplexity_research: str | None = None
    perplexity_citations: list[str] | None = None
    crawl_content: str | None = None
    crawl_metadata: dict[str, Any] | None = None
    document_texts: list[str] | None = None
    errors: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage or serialization."""
        return {
            "perplexity_research": self.perplexity_research,
            "perplexity_citations": self.perplexity_citations,
            "crawl_content": self.crawl_content,
            "crawl_metadata": self.crawl_metadata,
            "document_texts": self.document_texts,
            "errors": self.errors,
        }

    def has_any_data(self) -> bool:
        """Check if any research data is available."""
        return bool(
            self.perplexity_research or self.crawl_content or self.document_texts
        )


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

    @staticmethod
    async def _research_phase(
        db: AsyncSession,
        project_id: str,
        perplexity: PerplexityClient,
        crawl4ai: Crawl4AIClient,
    ) -> ResearchContext:
        """Execute the research phase, gathering data from 3 sources in parallel.

        Runs Perplexity brand research, Crawl4AI website crawl, and document
        retrieval in parallel. Handles failures gracefully - continues with
        available data if one or more sources fail.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.
            perplexity: PerplexityClient instance for web research.
            crawl4ai: Crawl4AIClient instance for website crawling.

        Returns:
            ResearchContext with combined research data from all sources.

        Raises:
            HTTPException: 404 if project not found.
        """
        # Get project to access site_url
        project = await BrandConfigService._get_project(db, project_id)
        site_url = project.site_url
        brand_name = project.name

        errors: list[str] = []

        # Define async tasks for parallel execution
        async def research_with_perplexity() -> BrandResearchResult | None:
            """Run Perplexity brand research."""
            if not perplexity.available:
                logger.warning("Perplexity not available, skipping web research")
                return None
            try:
                return await perplexity.research_brand(site_url, brand_name)
            except Exception as e:
                logger.warning(
                    "Perplexity research failed",
                    extra={"project_id": project_id, "error": str(e)},
                )
                errors.append(f"Perplexity research failed: {e}")
                return None

        async def crawl_with_crawl4ai() -> CrawlResult | None:
            """Run Crawl4AI website crawl."""
            if not crawl4ai.available:
                logger.warning("Crawl4AI not available, skipping website crawl")
                return None
            try:
                return await crawl4ai.crawl(site_url)
            except Exception as e:
                logger.warning(
                    "Crawl4AI crawl failed",
                    extra={"project_id": project_id, "error": str(e)},
                )
                errors.append(f"Website crawl failed: {e}")
                return None

        async def get_document_texts() -> list[str]:
            """Retrieve extracted text from all project files."""
            try:
                stmt = select(ProjectFile.extracted_text).where(
                    ProjectFile.project_id == project_id,
                    ProjectFile.extracted_text.isnot(None),
                )
                result = await db.execute(stmt)
                texts = [row[0] for row in result.fetchall() if row[0]]
                logger.info(
                    "Retrieved document texts",
                    extra={"project_id": project_id, "count": len(texts)},
                )
                return texts
            except Exception as e:
                logger.warning(
                    "Failed to retrieve document texts",
                    extra={"project_id": project_id, "error": str(e)},
                )
                errors.append(f"Document retrieval failed: {e}")
                return []

        # Run all three tasks in parallel
        logger.info(
            "Starting research phase",
            extra={"project_id": project_id, "site_url": site_url},
        )

        perplexity_result, crawl_result, doc_texts = await asyncio.gather(
            research_with_perplexity(),
            crawl_with_crawl4ai(),
            get_document_texts(),
        )

        # Process results
        perplexity_research: str | None = None
        perplexity_citations: list[str] | None = None
        if perplexity_result and perplexity_result.success:
            perplexity_research = perplexity_result.raw_text
            perplexity_citations = perplexity_result.citations
            logger.info(
                "Perplexity research completed",
                extra={
                    "project_id": project_id,
                    "citations_count": len(perplexity_citations or []),
                },
            )
        elif perplexity_result and not perplexity_result.success:
            errors.append(f"Perplexity research failed: {perplexity_result.error}")

        crawl_content: str | None = None
        crawl_metadata: dict[str, Any] | None = None
        if crawl_result and crawl_result.success:
            crawl_content = crawl_result.markdown
            crawl_metadata = crawl_result.metadata
            logger.info(
                "Website crawl completed",
                extra={
                    "project_id": project_id,
                    "content_length": len(crawl_content or ""),
                },
            )
        elif crawl_result and not crawl_result.success:
            errors.append(f"Website crawl failed: {crawl_result.error}")

        # Build research context
        research_context = ResearchContext(
            perplexity_research=perplexity_research,
            perplexity_citations=perplexity_citations,
            crawl_content=crawl_content,
            crawl_metadata=crawl_metadata,
            document_texts=doc_texts if doc_texts else None,
            errors=errors if errors else None,
        )

        logger.info(
            "Research phase completed",
            extra={
                "project_id": project_id,
                "has_perplexity": bool(perplexity_research),
                "has_crawl": bool(crawl_content),
                "doc_count": len(doc_texts),
                "error_count": len(errors),
            },
        )

        return research_context
