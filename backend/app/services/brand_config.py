"""Brand configuration service for managing brand config generation.

Orchestrates the brand configuration generation process, including:
- Starting generation as a background task
- Tracking generation status in project.brand_wizard_state
- Reporting current progress
- Research phase: parallel data gathering from Perplexity, Crawl4AI, and documents
- Synthesis phase: sequential generation of 10 brand config sections via Claude
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

from app.integrations.claude import ClaudeClient, CompletionResult
from app.integrations.crawl4ai import Crawl4AIClient, CrawlResult
from app.integrations.perplexity import BrandResearchResult, PerplexityClient
from app.models.brand_config import BrandConfig
from app.models.project import Project
from app.models.project_file import ProjectFile

logger = logging.getLogger(__name__)

# Timeout for each section generation (in seconds)
SECTION_TIMEOUT_SECONDS = 60


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


# Generation steps for brand config (9 sections + ai_prompt_snippet summary)
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
    "ai_prompt_snippet",
]


# Section-specific system prompts for brand config generation
SECTION_PROMPTS: dict[str, str] = {
    "brand_foundation": """You are a brand strategist creating the Brand Foundation section of a brand guidelines document.

Based on the research context provided, extract and synthesize:
- Company Overview (name, founded, location, industry, business model)
- What They Sell (primary products/services, secondary offerings, price point, sales channels)
- Brand Positioning (tagline/slogan, one-sentence description, category position)
- Mission & Values (mission statement, core values, brand promise)
- Differentiators (primary USP, supporting differentiators, what they're NOT)

Output ONLY valid JSON in this exact format:
{
  "company_overview": {
    "company_name": "string",
    "founded": "string or null",
    "location": "string or null",
    "industry": "string",
    "business_model": "string"
  },
  "what_they_sell": {
    "primary_products_services": "string",
    "secondary_offerings": "string or null",
    "price_point": "string (Budget/Mid-range/Premium/Luxury)",
    "sales_channels": "string"
  },
  "brand_positioning": {
    "tagline": "string or null",
    "one_sentence_description": "string",
    "category_position": "string (Leader/Challenger/Specialist/Disruptor)"
  },
  "mission_and_values": {
    "mission_statement": "string",
    "core_values": ["string", "string", "string"],
    "brand_promise": "string"
  },
  "differentiators": {
    "primary_usp": "string",
    "supporting_differentiators": ["string", "string"],
    "what_they_are_not": "string"
  }
}

Be specific and concrete based on the research. If information is not available, make reasonable inferences based on industry norms.""",
    "target_audience": """You are a brand strategist creating the Target Audience section of a brand guidelines document.

Based on the research context and brand foundation provided, identify and describe the target audience:
- Demographics (age range, gender if relevant, location, income level, profession, education)
- Psychographics (values, aspirations, fears/pain points, frustrations, identity)
- Behavioral Insights (discovery channels, research behavior, decision factors, buying triggers, common objections)
- Communication Preferences (tone they respond to, language they use, content they consume, trust signals needed)
- Persona Summary Statement (one paragraph describing them as a real person)

Output ONLY valid JSON in this exact format:
{
  "primary_persona": {
    "name": "string (e.g., 'Professional Pat')",
    "percentage_of_customers": "string (e.g., '60%')",
    "demographics": {
      "age_range": "string",
      "gender": "string or null",
      "location": "string",
      "income_level": "string",
      "profession": "string",
      "education": "string or null"
    },
    "psychographics": {
      "values": ["string", "string", "string"],
      "aspirations": "string",
      "fears_pain_points": "string",
      "frustrations": "string",
      "identity": "string"
    },
    "behavioral_insights": {
      "discovery_channels": ["string", "string"],
      "research_behavior": "string",
      "decision_factors": ["string", "string", "string"],
      "buying_triggers": "string",
      "common_objections": ["string", "string"]
    },
    "communication_preferences": {
      "tone_they_respond_to": "string",
      "language_they_use": "string",
      "content_they_consume": ["string", "string"],
      "trust_signals_needed": ["string", "string"]
    },
    "summary_statement": "string"
  },
  "secondary_personas": []
}

Be specific and concrete based on the research. Create realistic personas.""",
    "voice_dimensions": """You are a brand strategist creating the Voice Dimensions section of a brand guidelines document.

Based on the research context and previous sections, rate the brand voice on the Nielsen Norman Group 4 dimensions (1-10 scale):

1. Formality (1 = Very Casual, 10 = Very Formal)
2. Humor (1 = Very Funny/Playful, 10 = Very Serious)
3. Reverence (1 = Irreverent/Edgy, 10 = Highly Respectful)
4. Enthusiasm (1 = Very Enthusiastic, 10 = Matter-of-Fact)

Output ONLY valid JSON in this exact format:
{
  "formality": {
    "score": 5,
    "description": "string explaining how this manifests",
    "example": "string with sample sentence"
  },
  "humor": {
    "score": 5,
    "description": "string explaining when/how humor is appropriate",
    "example": "string with sample sentence"
  },
  "reverence": {
    "score": 5,
    "description": "string explaining how brand treats competitors/industry/customers",
    "example": "string with sample sentence"
  },
  "enthusiasm": {
    "score": 5,
    "description": "string explaining energy level in communications",
    "example": "string with sample sentence"
  },
  "voice_summary": "string (2-3 sentences summarizing overall voice)"
}

Base scores on actual brand positioning and audience expectations.""",
    "voice_characteristics": """You are a brand strategist creating the Voice Characteristics section of a brand guidelines document.

Based on the research context and voice dimensions, define 3-5 key voice characteristics with examples:

For each characteristic, provide:
- The characteristic name
- A brief description
- A "DO" example (on-brand writing)
- A "DON'T" example (off-brand writing)

Also define what the brand voice is NOT (3-5 anti-characteristics).

Output ONLY valid JSON in this exact format:
{
  "we_are": [
    {
      "characteristic": "string (e.g., 'Knowledgeable')",
      "description": "string",
      "do_example": "string",
      "dont_example": "string"
    }
  ],
  "we_are_not": [
    {
      "characteristic": "string (e.g., 'Hype-driven')",
      "description": "string"
    }
  ]
}

Provide 3-5 characteristics for each section. Be specific with examples.""",
    "writing_style": """You are a brand strategist creating the Writing Style Rules section of a brand guidelines document.

Based on the research context and voice established, define concrete writing style rules:

Output ONLY valid JSON in this exact format:
{
  "sentence_structure": {
    "average_sentence_length": "string (e.g., '12-18 words')",
    "paragraph_length": "string (e.g., '2-4 sentences')",
    "use_contractions": "string (Yes/No/When)",
    "active_vs_passive": "string"
  },
  "capitalization": {
    "headlines": "string (Title Case/Sentence case)",
    "product_names": "string",
    "feature_names": "string"
  },
  "punctuation": {
    "serial_comma": "string (Yes/No)",
    "em_dashes": "string",
    "exclamation_points": "string",
    "ellipses": "string"
  },
  "numbers": {
    "spell_out": "string",
    "currency": "string",
    "percentages": "string"
  },
  "formatting": {
    "bold": "string",
    "italics": "string",
    "bullet_points": "string",
    "headers": "string"
  }
}

Rules should align with the established voice and audience expectations.""",
    "vocabulary": """You are a brand strategist creating the Vocabulary Guide section of a brand guidelines document.

Based on the research context and voice established, define the brand's vocabulary:

Output ONLY valid JSON in this exact format:
{
  "power_words": ["string", "string", "string"],
  "words_we_prefer": [
    {"instead_of": "string", "we_say": "string"}
  ],
  "banned_words": ["string", "string", "string"],
  "industry_terms": [
    {"term": "string", "usage": "string"}
  ],
  "brand_specific_terms": [
    {"term": "string", "definition": "string", "usage": "string"}
  ],
  "signature_phrases": {
    "confidence_without_arrogance": ["string", "string"],
    "direct_and_helpful": ["string", "string"]
  }
}

Power words: 15-20 words that align with brand voice
Banned words: 10-15 generic/AI-sounding/off-brand words to avoid
Include industry-specific terminology used correctly.""",
    "trust_elements": """You are a brand strategist creating the Trust Elements section of a brand guidelines document.

Based on the research context, compile proof and trust elements:

Output ONLY valid JSON in this exact format:
{
  "hard_numbers": {
    "customer_count": "string or null",
    "years_in_business": "string or null",
    "products_sold": "string or null",
    "review_average": "string or null",
    "review_count": "string or null"
  },
  "credentials": {
    "certifications": ["string"],
    "industry_memberships": ["string"],
    "awards": ["string"]
  },
  "media_and_press": {
    "publications_featured_in": ["string"],
    "notable_mentions": ["string"]
  },
  "endorsements": {
    "influencer_endorsements": ["string"],
    "partnership_badges": ["string"]
  },
  "guarantees": {
    "return_policy": "string",
    "warranty": "string",
    "satisfaction_guarantee": "string"
  },
  "customer_quotes": [
    {"quote": "string", "attribution": "string"}
  ],
  "proof_integration_guidelines": {
    "headlines": "string",
    "body_copy": "string",
    "ctas": "string",
    "what_not_to_do": ["string"]
  }
}

Extract real data from research when available. For missing data, leave as null or empty array.""",
    "examples_bank": """You are a brand strategist creating the Examples Bank section of a brand guidelines document.

Based on the research context and all previous sections, create example copy that demonstrates the brand voice:

Output ONLY valid JSON in this exact format:
{
  "headlines_that_work": ["string", "string", "string", "string", "string"],
  "product_description_example": {
    "product_name": "string",
    "description": "string (100-200 words in brand voice)"
  },
  "email_subject_lines": ["string", "string", "string", "string", "string"],
  "social_media_posts": {
    "instagram_product": "string",
    "instagram_social_proof": "string",
    "facebook_value": "string"
  },
  "ctas_that_work": ["string", "string", "string", "string", "string"],
  "what_not_to_write": [
    {"example": "string", "reason": "string"}
  ]
}

Create 5-10 examples for each category. Make them specific to this brand.
What NOT to write examples should show common mistakes to avoid.""",
    "competitor_context": """You are a brand strategist creating the Competitor Context section of a brand guidelines document.

Based on the research context, map the competitive landscape:

Output ONLY valid JSON in this exact format:
{
  "direct_competitors": [
    {
      "name": "string",
      "positioning": "string",
      "our_difference": "string"
    }
  ],
  "competitive_advantages": ["string", "string", "string"],
  "competitive_weaknesses": ["string", "string"],
  "positioning_statements": {
    "vs_premium_brands": "string",
    "vs_budget_brands": "string",
    "general_differentiation": "string"
  },
  "competitor_reference_rules": [
    "string (e.g., 'Never mention competitors by name in marketing copy')"
  ]
}

Identify 3-5 direct competitors. Be honest about both advantages and weaknesses.
Positioning statements should be usable in copy without naming competitors.""",
    "ai_prompt_snippet": """You are a brand strategist creating the AI Prompt Snippet for a brand guidelines document.

This snippet will be prepended to AI writing requests to ensure consistent brand voice.

Based on ALL the brand sections provided, create a concise but comprehensive prompt snippet.

Output ONLY valid JSON in this exact format:
{
  "snippet": "string (the full prompt snippet, 100-200 words)",
  "voice_in_three_words": ["string", "string", "string"],
  "we_sound_like": "string (1-sentence comparison)",
  "we_never_sound_like": "string (1-sentence anti-comparison)",
  "primary_audience_summary": "string (1-sentence)",
  "key_differentiators": ["string", "string", "string"],
  "never_use_words": ["string", "string", "string", "string", "string"],
  "always_include": ["string", "string"]
}

The snippet should be immediately usable before any AI writing request.
It should capture the essence of the entire brand guidelines document.""",
}


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

    @staticmethod
    async def _synthesis_phase(
        project_id: str,
        research_context: ResearchContext,
        claude: ClaudeClient,
        update_status_callback: Any | None = None,
    ) -> dict[str, Any]:
        """Execute the synthesis phase, generating brand config sections sequentially.

        Generates 10 brand config sections using Claude, in order:
        1. brand_foundation
        2. target_audience
        3. voice_dimensions
        4. voice_characteristics
        5. writing_style
        6. vocabulary
        7. trust_elements
        8. examples_bank
        9. competitor_context
        10. ai_prompt_snippet (generated last as summary of all sections)

        Each section builds on previous sections - the prompts include previously
        generated sections as context for coherence.

        Args:
            project_id: UUID string of the project (for logging).
            research_context: Combined research data from research phase.
            claude: ClaudeClient instance for LLM completion.
            update_status_callback: Optional async callback(step_name, step_index) for progress updates.

        Returns:
            Dictionary with all generated sections, keyed by section name.

        Raises:
            HTTPException: If Claude is not available or a section fails to generate.
        """
        import json

        if not claude.available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Claude LLM is not configured",
            )

        logger.info(
            "Starting synthesis phase",
            extra={"project_id": project_id, "total_sections": len(GENERATION_STEPS)},
        )

        # Build the research context string for prompts
        research_text_parts: list[str] = []

        if research_context.perplexity_research:
            research_text_parts.append(
                f"## Web Research\n{research_context.perplexity_research}"
            )

        if research_context.crawl_content:
            # Truncate crawl content to avoid token limits
            crawl_preview = research_context.crawl_content[:8000]
            if len(research_context.crawl_content) > 8000:
                crawl_preview += "\n... (content truncated)"
            research_text_parts.append(f"## Website Content\n{crawl_preview}")

        if research_context.document_texts:
            # Combine document texts with truncation
            docs_combined = "\n---\n".join(research_context.document_texts)
            if len(docs_combined) > 4000:
                docs_combined = docs_combined[:4000] + "\n... (documents truncated)"
            research_text_parts.append(f"## Uploaded Documents\n{docs_combined}")

        research_text = "\n\n".join(research_text_parts)

        if not research_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No research data available for synthesis",
            )

        # Generated sections accumulator
        generated_sections: dict[str, Any] = {}
        errors: list[str] = []

        # Generate each section sequentially
        for step_index, section_name in enumerate(GENERATION_STEPS):
            logger.info(
                "Generating section",
                extra={
                    "project_id": project_id,
                    "section": section_name,
                    "step": step_index + 1,
                    "total": len(GENERATION_STEPS),
                },
            )

            # Update progress if callback provided
            if update_status_callback:
                await update_status_callback(section_name, step_index)

            # Get the system prompt for this section
            system_prompt = SECTION_PROMPTS.get(section_name)
            if not system_prompt:
                logger.error(
                    "Missing system prompt for section",
                    extra={"section": section_name},
                )
                errors.append(f"Missing prompt for {section_name}")
                continue

            # Build user prompt with research context and previous sections
            user_prompt_parts = [
                "# Research Context",
                research_text,
            ]

            # Add previously generated sections as context
            if generated_sections:
                user_prompt_parts.append("\n# Previously Generated Sections")
                for prev_section, prev_data in generated_sections.items():
                    user_prompt_parts.append(
                        f"\n## {prev_section}\n```json\n{json.dumps(prev_data, indent=2)}\n```"
                    )

            user_prompt_parts.append(
                f"\n\nGenerate the {section_name.replace('_', ' ')} section now."
            )
            user_prompt = "\n".join(user_prompt_parts)

            # Call Claude with timeout
            try:
                result: CompletionResult = await asyncio.wait_for(
                    claude.complete(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
                        max_tokens=2048,
                        temperature=0.3,  # Slight creativity for brand voice
                    ),
                    timeout=SECTION_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                error_msg = f"Timeout generating {section_name} (exceeded {SECTION_TIMEOUT_SECONDS}s)"
                logger.error(
                    error_msg,
                    extra={"project_id": project_id, "section": section_name},
                )
                errors.append(error_msg)
                continue

            if not result.success:
                error_msg = f"Failed to generate {section_name}: {result.error}"
                logger.error(
                    error_msg,
                    extra={
                        "project_id": project_id,
                        "section": section_name,
                        "error": result.error,
                    },
                )
                errors.append(error_msg)
                continue

            # Parse JSON response
            try:
                response_text = result.text or ""
                json_text = response_text.strip()

                # Handle markdown code blocks
                if json_text.startswith("```"):
                    lines = json_text.split("\n")
                    lines = lines[1:]  # Remove opening fence
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    json_text = "\n".join(lines)

                section_data = json.loads(json_text)
                generated_sections[section_name] = section_data

                logger.info(
                    "Section generated successfully",
                    extra={
                        "project_id": project_id,
                        "section": section_name,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "duration_ms": result.duration_ms,
                    },
                )

            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse {section_name} JSON: {e}"
                logger.error(
                    error_msg,
                    extra={
                        "project_id": project_id,
                        "section": section_name,
                        "response_preview": (result.text or "")[:500],
                    },
                )
                errors.append(error_msg)
                continue

        # Log completion
        logger.info(
            "Synthesis phase completed",
            extra={
                "project_id": project_id,
                "sections_generated": len(generated_sections),
                "sections_failed": len(errors),
                "errors": errors if errors else None,
            },
        )

        # Add errors to result if any
        if errors:
            generated_sections["_errors"] = errors

        return generated_sections

    @staticmethod
    async def store_brand_config(
        db: AsyncSession,
        project_id: str,
        generated_sections: dict[str, Any],
        source_file_ids: list[str],
    ) -> BrandConfig:
        """Store the generated brand config in BrandConfig.v2_schema.

        Creates a new BrandConfig record if one doesn't exist for the project,
        or updates the existing one. Also updates generation status to complete
        or failed based on the result.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.
            generated_sections: Dictionary with all generated sections from synthesis.
            source_file_ids: List of ProjectFile IDs used as source documents.

        Returns:
            BrandConfig instance with stored v2_schema.

        Raises:
            HTTPException: 404 if project not found.
        """
        # Get project to verify existence and get brand name
        project = await BrandConfigService._get_project(db, project_id)

        # Check for errors in generated sections
        errors = generated_sections.pop("_errors", None)
        has_errors = bool(errors)

        # Determine if we have minimum required sections for success
        # We need at least brand_foundation for a valid config
        required_sections = ["brand_foundation"]
        has_required = all(
            section in generated_sections for section in required_sections
        )

        if not has_required:
            # Mark as failed - not enough data to create brand config
            error_msg = "Failed to generate required sections: " + ", ".join(
                s for s in required_sections if s not in generated_sections
            )
            if errors:
                error_msg += f". Additional errors: {errors}"

            await BrandConfigService.fail_generation(db, project_id, error_msg)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg,
            )

        # Build v2_schema structure
        v2_schema: dict[str, Any] = {
            "version": "2.0",
            "generated_at": datetime.now(UTC).isoformat(),
            "source_documents": source_file_ids,
        }

        # Add all 9 sections + ai_prompt_snippet
        for section_name in GENERATION_STEPS:
            if section_name in generated_sections:
                v2_schema[section_name] = generated_sections[section_name]

        # Include partial errors as metadata if any
        if errors:
            v2_schema["_generation_warnings"] = errors

        # Check if BrandConfig already exists for this project
        stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
        result = await db.execute(stmt)
        brand_config = result.scalar_one_or_none()

        if brand_config:
            # Update existing record
            brand_config.v2_schema = v2_schema
            brand_config.updated_at = datetime.now(UTC)
            logger.info(
                "Updated existing BrandConfig",
                extra={
                    "project_id": project_id,
                    "brand_config_id": brand_config.id,
                    "sections_stored": len(
                        [s for s in GENERATION_STEPS if s in v2_schema]
                    ),
                },
            )
        else:
            # Create new record
            brand_config = BrandConfig(
                project_id=project_id,
                brand_name=project.name,
                domain=project.site_url,
                v2_schema=v2_schema,
            )
            db.add(brand_config)
            logger.info(
                "Created new BrandConfig",
                extra={
                    "project_id": project_id,
                    "sections_stored": len(
                        [s for s in GENERATION_STEPS if s in v2_schema]
                    ),
                },
            )

        await db.flush()
        await db.refresh(brand_config)

        # Mark generation as complete (even if there were some non-critical errors)
        await BrandConfigService.complete_generation(db, project_id)

        logger.info(
            "Brand config stored successfully",
            extra={
                "project_id": project_id,
                "brand_config_id": brand_config.id,
                "has_warnings": has_errors,
            },
        )

        return brand_config

    @staticmethod
    async def get_source_file_ids(db: AsyncSession, project_id: str) -> list[str]:
        """Get all file IDs for a project that have extracted text.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.

        Returns:
            List of ProjectFile UUIDs that were used as source documents.
        """
        stmt = select(ProjectFile.id).where(
            ProjectFile.project_id == project_id,
            ProjectFile.extracted_text.isnot(None),
        )
        result = await db.execute(stmt)
        return [row[0] for row in result.fetchall()]
