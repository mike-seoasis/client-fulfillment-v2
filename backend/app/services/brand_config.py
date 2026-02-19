"""Brand configuration service for managing brand config generation.

Orchestrates the brand configuration generation process, including:
- Starting generation as a background task
- Tracking generation status in project.brand_wizard_state
- Reporting current progress
- Research phase: parallel data gathering from Perplexity, Crawl4AI, and documents
- Synthesis phase: sequential generation of 9 brand config sections + ai_prompt_snippet via Claude
- Post-synthesis: subreddit research via Perplexity (if Reddit config exists)
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
from sqlalchemy.orm.attributes import flag_modified

from app.integrations.claude import ClaudeClient, CompletionResult
from app.integrations.crawl4ai import Crawl4AIClient, CrawlResult
from app.integrations.perplexity import BrandResearchResult, PerplexityClient
from app.models.brand_config import BrandConfig
from app.models.project import Project
from app.models.project_file import ProjectFile

logger = logging.getLogger(__name__)

# Timeout for each section generation (in seconds)
SECTION_TIMEOUT_SECONDS = 60


def fix_json_control_chars(json_text: str) -> str:
    """Fix unescaped control characters in JSON strings.

    LLMs sometimes return JSON with literal newlines inside string values
    instead of escaped \\n. This function finds string values and escapes
    control characters properly.

    Args:
        json_text: Raw JSON text that may have unescaped control chars

    Returns:
        JSON text with control characters escaped in string values
    """
    # Process the JSON character by character to find string values
    # and escape control characters within them
    result = []
    in_string = False
    escape_next = False

    for char in json_text:
        if escape_next:
            result.append(char)
            escape_next = False
            continue

        if char == '\\' and in_string:
            result.append(char)
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
            continue

        if in_string:
            # Escape control characters inside strings
            if char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            elif ord(char) < 32:  # Other control characters
                result.append(f'\\u{ord(char):04x}')
            else:
                result.append(char)
        else:
            result.append(char)

    return ''.join(result)


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


# Generation steps for brand config (8 sections + ai_prompt_snippet summary)
GENERATION_STEPS = [
    "brand_foundation",
    "target_audience",
    "voice_dimensions",
    "voice_characteristics",
    "writing_style",
    "vocabulary",
    "trust_elements",
    "competitor_context",
    "ai_prompt_snippet",
    "subreddit_research",
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

Based on the research context and brand foundation provided, create DETAILED TARGET AUDIENCE PERSONAS.

REQUIREMENTS:
- You MUST create a minimum of 2 fully detailed personas
- Each persona MUST have ALL fields populated - no nulls or empty values
- Be specific and concrete based on the research - avoid generic placeholder text
- The first persona in the array is the PRIMARY persona

Output ONLY valid JSON in this exact format:
{
  "audience_overview": {
    "primary_persona": "string (name of first/primary persona)",
    "secondary_persona": "string (name of second persona)",
    "tertiary_persona": "string or null (name of third persona if exists)"
  },
  "personas": [
    {
      "name": "string (descriptive name, e.g., 'The Conscious Curator')",
      "percentage": "string (e.g., '55%')",
      "demographics": {
        "age_range": "string (specific range, e.g., '32-45')",
        "gender": "string (or 'All genders' if not relevant)",
        "location": "string (specific regions/characteristics)",
        "income_level": "string (specific range, e.g., '$75,000-$120,000')",
        "profession": "string (specific roles/industries)",
        "education": "string (specific level)"
      },
      "psychographics": {
        "values": ["string", "string", "string"],
        "aspirations": ["string (what they're trying to achieve)"],
        "fears": ["string (specific challenges and pain points)"],
        "frustrations": ["string (what frustrates them about current options)"],
        "identity": "string (how they see themselves)"
      },
      "behavioral": {
        "discovery_channels": ["string", "string", "string"],
        "research_behavior": "string (how they evaluate options)",
        "decision_factors": ["string", "string", "string"],
        "buying_triggers": ["string (what prompts purchase)"],
        "purchase_frequency": "string (how often they buy)"
      },
      "communication": {
        "tone_preference": "string (formal/casual, technical/accessible)",
        "language_style": "string (vocabulary, formality level)",
        "content_consumed": ["string", "string", "string"],
        "preferred_channels": ["string", "string"],
        "trust_signals": ["string", "string", "string"]
      },
      "summary": "string (one paragraph describing them as a real person)"
    },
    {
      "name": "string (second persona name)",
      "percentage": "string",
      "demographics": {
        "age_range": "string",
        "gender": "string",
        "location": "string",
        "income_level": "string",
        "profession": "string",
        "education": "string"
      },
      "psychographics": {
        "values": ["string", "string", "string"],
        "aspirations": ["string"],
        "fears": ["string"],
        "frustrations": ["string"],
        "identity": "string"
      },
      "behavioral": {
        "discovery_channels": ["string", "string", "string"],
        "research_behavior": "string",
        "decision_factors": ["string", "string", "string"],
        "buying_triggers": ["string"],
        "purchase_frequency": "string"
      },
      "communication": {
        "tone_preference": "string",
        "language_style": "string",
        "content_consumed": ["string", "string", "string"],
        "preferred_channels": ["string", "string"],
        "trust_signals": ["string", "string", "string"]
      },
      "summary": "string"
    }
  ]
}

IMPORTANT:
- personas array MUST contain at least 2 fully detailed personas
- The first persona is the PRIMARY persona
- ALL fields in the schema must be populated with specific, research-based content
- Create personas that are distinct from each other (different motivations, behaviors, needs)
- Percentages should add up to approximately 100%""",
    "voice_dimensions": """You are a brand strategist creating the Voice Dimensions section of a brand guidelines document.

Based on the research context and previous sections, rate the brand voice on the Nielsen Norman Group 4 dimensions (1-10 scale):

1. Formality (1 = Very Casual, 10 = Very Formal)
2. Humor (1 = Very Funny/Playful, 10 = Very Serious)
3. Reverence (1 = Irreverent/Edgy, 10 = Highly Respectful)
4. Enthusiasm (1 = Very Enthusiastic, 10 = Matter-of-Fact)

Output ONLY valid JSON in this exact format:
{
  "formality": {
    "position": 5,
    "description": "string explaining how this manifests",
    "example": "string with sample sentence"
  },
  "humor": {
    "position": 5,
    "description": "string explaining when/how humor is appropriate",
    "example": "string with sample sentence"
  },
  "reverence": {
    "position": 5,
    "description": "string explaining how brand treats competitors/industry/customers",
    "example": "string with sample sentence"
  },
  "enthusiasm": {
    "position": 5,
    "description": "string explaining energy level in communications",
    "example": "string with sample sentence"
  },
  "voice_summary": "string (2-3 sentences summarizing overall voice)"
}

Base scores on actual brand positioning and audience expectations.""",
    "voice_characteristics": """You are a brand strategist creating the Voice Characteristics section of a brand guidelines document.

Based on the research context and voice dimensions, define key voice characteristics with examples:

For each characteristic, provide:
- The characteristic name
- A brief description
- A "DO" example (on-brand writing)
- A "DON'T" example (off-brand writing)

Also define what the brand voice is NOT as a list of anti-characteristics.

Output ONLY valid JSON in this exact format:
{
  "we_are": [
    {
      "trait_name": "string (e.g., 'Knowledgeable')",
      "description": "string",
      "do_example": "string",
      "dont_example": "string"
    }
  ],
  "we_are_not": ["corporate", "stuffy", "salesy", "pushy", "generic"]
}

REQUIREMENTS:
- we_are: Provide at least 5 characteristics with full details (trait_name, description, do_example, dont_example)
- we_are_not: Provide an array of 5+ simple strings (NOT objects). Each string is a single word or short phrase describing what the brand voice avoids.
- Be specific with examples in we_are - show real on-brand vs off-brand writing""",
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
    "em_dashes": "Never use em dashes (—). Use commas, parentheses, or separate sentences instead.",
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

REQUIREMENTS:
- The em_dashes rule is MANDATORY and must always be "Never use em dashes (—). Use commas, parentheses, or separate sentences instead." - this is a non-negotiable brand standard that applies regardless of brand voice or context
- All other rules should align with the established voice and audience expectations.""",
    "vocabulary": """You are a brand strategist creating the Vocabulary Guide section of a brand guidelines document.

Based on the research context and voice established, define the brand's vocabulary:

Output ONLY valid JSON in this exact format:
{
  "power_words": ["string", "string", "string"],
  "words_we_prefer": [
    {"instead_of": "string", "we_say": "string"}
  ],
  "banned_words": ["—", "string", "string"],
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

REQUIREMENTS:
- power_words: Provide at least 20 words that align with brand voice and resonate with the target audience. These are high-impact words that should be used frequently in brand communications.
- banned_words: Provide at least 15 words to avoid. This MUST include "—" (em dash) as the first item. Also include generic/AI-sounding/off-brand words (e.g., "utilize", "leverage", "synergy", "cutting-edge", "game-changer", "robust", "seamless", "delve").
- words_we_prefer: Provide at least 5 word substitutions showing brand-specific language preferences.
- industry_terms: Include industry-specific terminology used correctly with clear usage guidance.
- brand_specific_terms: Include any proprietary terms, product names, or branded language.""",
    "trust_elements": """You are a brand strategist creating the Trust Elements section of a brand guidelines document.

Based on the research context, compile proof and trust elements:

Output ONLY valid JSON in this exact format:
{
  "hard_numbers": {
    "customer_count": "string or null",
    "years_in_business": "string or null",
    "products_sold": "string or null",
    "average_store_rating": "string or null (e.g., '4.8 out of 5 stars')",
    "review_count": "string or null (e.g., '2,500+ reviews')"
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

REQUIREMENTS:
- average_store_rating: Actively search for the brand's overall store/product rating (e.g., from their website, Amazon, Google reviews, Trustpilot, etc.). Format as "X.X out of 5 stars" or similar. This is a key trust signal for e-commerce.
- review_count: When a rating is found, also capture the total number of reviews to add credibility (e.g., "2,500+ reviews"). Rating without count is less impactful.
- Both fields are optional (use null if not found), but should be actively sought in research as they are high-value trust signals.
- Extract real data from research when available. For missing data, leave as null or empty array.""",
    "competitor_context": """You are a brand strategist creating the Competitor Context section of a brand guidelines document for an e-commerce/DTC brand.

Based on the research context, map the competitive landscape focusing on ONLINE/E-COMMERCE competitors:

Output ONLY valid JSON in this exact format:
{
  "direct_competitors": [
    {
      "name": "string (competitor brand name)",
      "category": "string (e.g., 'DTC', 'Amazon native', 'Traditional retailer with e-commerce', 'Marketplace seller')",
      "positioning": "string (how they position themselves in the market - their value prop, brand promise, target audience)",
      "pricing_tier": "string (e.g., 'Premium', 'Mid-market', 'Budget', 'Value')",
      "strengths": ["string (what they do well)", "string"],
      "weaknesses": ["string (where they fall short)", "string"],
      "our_difference": "string (specific ways we differentiate from this competitor - be concrete and actionable)"
    },
    {
      "name": "Competitor 2",
      "category": "string",
      "positioning": "string",
      "pricing_tier": "string",
      "strengths": ["string", "string"],
      "weaknesses": ["string", "string"],
      "our_difference": "string"
    },
    {
      "name": "Competitor 3",
      "category": "string",
      "positioning": "string",
      "pricing_tier": "string",
      "strengths": ["string", "string"],
      "weaknesses": ["string", "string"],
      "our_difference": "string"
    },
    {
      "name": "Competitor 4",
      "category": "string",
      "positioning": "string",
      "pricing_tier": "string",
      "strengths": ["string", "string"],
      "weaknesses": ["string", "string"],
      "our_difference": "string"
    },
    {
      "name": "Competitor 5",
      "category": "string",
      "positioning": "string",
      "pricing_tier": "string",
      "strengths": ["string", "string"],
      "weaknesses": ["string", "string"],
      "our_difference": "string"
    }
  ],
  "competitive_advantages": ["string", "string", "string", "string"],
  "competitive_weaknesses": ["string", "string"],
  "positioning_statements": {
    "vs_premium_brands": "string",
    "vs_budget_brands": "string",
    "vs_amazon_sellers": "string",
    "general_differentiation": "string"
  },
  "competitor_reference_rules": [
    "string (e.g., 'Never mention competitors by name in marketing copy')"
  ]
}

REQUIREMENTS:
- direct_competitors: Provide AT LEAST 5 e-commerce competitors (more is better for comprehensive analysis)
- Focus on ONLINE competitors: DTC brands, Amazon sellers, e-commerce retailers, marketplace competitors
- Do NOT include brick-and-mortar-only competitors unless they have significant e-commerce presence
- For EACH competitor, provide:
  - Detailed positioning (their value prop, who they target, how they present themselves)
  - Specific strengths AND weaknesses (be honest and analytical)
  - Concrete differentiation (how the brand can win against this specific competitor)
- competitive_advantages: Provide at least 4 unique advantages
- Be honest about competitive_weaknesses - this helps the brand address gaps
- Positioning statements should be usable in copy without naming competitors.""",
    "ai_prompt_snippet": """You are a brand strategist creating a COMPREHENSIVE AI Prompt for brand content generation.

This prompt will be used to generate ALL written content for this brand - product descriptions, emails, ads, social posts, website copy, and more. It must be THOROUGH and PRODUCTION-READY. A content writer using ONLY this prompt should be able to create perfectly on-brand content without any other reference materials.

Based on ALL the brand sections provided, create an exhaustive prompt that leaves nothing to interpretation.

Output ONLY valid JSON in this exact format:
{
  "full_prompt": "string (400-600 words - the complete, production-ready prompt - see requirements below)",
  "quick_reference": {
    "voice_in_three_words": ["string", "string", "string"],
    "we_sound_like": "string (comparison to a recognizable brand/personality for instant clarity)",
    "we_never_sound_like": "string (anti-comparison)",
    "elevator_pitch": "string (2-3 sentences: what the brand does, for whom, and why it matters)"
  },
  "audience_profile": {
    "primary_persona": "string (name and 1-sentence description)",
    "demographics": "string (age, income, location, lifestyle)",
    "psychographics": "string (values, motivations, pain points, aspirations)",
    "how_they_talk": "string (communication style, vocabulary level, references they'd understand)",
    "what_they_care_about": ["string", "string", "string", "string", "string"]
  },
  "voice_guidelines": {
    "personality_traits": ["string", "string", "string", "string", "string"],
    "tone_spectrum": {
      "formal_to_casual": "string (e.g., '70% casual, 30% professional')",
      "serious_to_playful": "string",
      "reserved_to_enthusiastic": "string"
    },
    "sentence_style": "string (length, structure, rhythm)",
    "vocabulary_level": "string (e.g., 'accessible but not dumbed down, 8th grade reading level')"
  },
  "writing_rules": {
    "always_do": ["string", "string", "string", "string", "string", "string", "string", "string"],
    "never_do": ["string", "string", "string", "string", "string", "string", "string", "string"],
    "banned_words": ["—", "string", "string", "string", "string", "string", "string", "string", "string", "string", "string", "string", "string", "string", "string"],
    "preferred_alternatives": [
      {"instead_of": "string", "use": "string"},
      {"instead_of": "string", "use": "string"},
      {"instead_of": "string", "use": "string"}
    ]
  },
  "content_patterns": {
    "headline_formula": "string (e.g., 'Benefit + Specificity + Emotion')",
    "cta_style": "string (how CTAs should feel - urgent, inviting, confident, etc.)",
    "proof_points_to_include": ["string", "string", "string", "string"],
    "emotional_triggers": ["string", "string", "string"]
  },
  "brand_specifics": {
    "key_messages": ["string", "string", "string"],
    "unique_value_props": ["string", "string", "string", "string", "string"],
    "competitive_angles": ["string", "string", "string"],
    "trust_signals_to_mention": ["string", "string", "string", "string"]
  }
}

REQUIREMENTS FOR full_prompt (THIS IS THE MOST IMPORTANT FIELD):
The full_prompt must be 400-600 words and structured as a complete, ready-to-use system prompt. It should include:

1. BRAND IDENTITY (50-75 words): Who is this brand? What do they sell? What's their mission? What makes them different?

2. TARGET AUDIENCE (50-75 words): Detailed description of who we're writing for - their demographics, psychographics, pain points, and aspirations. How do they talk? What do they care about?

3. VOICE & TONE (75-100 words): Detailed personality description. Are we formal or casual? Playful or serious? Expert or approachable? Use specific comparisons (e.g., "like a knowledgeable friend, not a pushy salesperson"). Include tone spectrum guidance.

4. WRITING STYLE (75-100 words): Sentence structure preferences, vocabulary level, rhythm and pacing. How long should sentences be? Do we use fragments? Contractions? Questions? What's our paragraph style?

5. RULES & CONSTRAINTS (75-100 words): Specific do's and don'ts. Banned words and phrases (MUST include em dashes). Required elements. Formatting preferences. Things that are absolutely off-brand.

6. PROOF & PERSUASION (50-75 words): What trust signals should be woven in? What emotional triggers work? What proof points matter most? How do we handle claims and benefits?

Write the full_prompt as flowing prose organized under clear headers, not as bullet points. It should read like expert guidance from a brand strategist.

For all other fields:
- voice_in_three_words: Exactly 3 distinctive, memorable descriptors
- banned_words: At least 15 words/phrases. MUST start with "—" (em dash). Include generic AI words (utilize, leverage, synergy, elevate, etc.)
- always_do/never_do: At least 8 items each, specific and actionable
- All arrays should have meaningful, specific content - no generic filler

This prompt will be used thousands of times to generate content. Make it count.""",
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
        # Flag the JSONB column as modified so SQLAlchemy detects the change
        flag_modified(project, "brand_wizard_state")

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
        # Flag the JSONB column as modified so SQLAlchemy detects the change
        flag_modified(project, "brand_wizard_state")

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
        # Flag the JSONB column as modified so SQLAlchemy detects the change
        flag_modified(project, "brand_wizard_state")

        logger.info(
            "complete_generation: updating project status",
            extra={
                "project_id": project_id,
                "new_status": generation_data["status"],
                "is_modified": project in db.dirty,
            },
        )

        await db.flush()
        await db.refresh(project)

        logger.info(
            "complete_generation: status updated",
            extra={
                "project_id": project_id,
                "updated_status": project.brand_wizard_state.get("generation", {}).get("status"),
            },
        )

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
        # Flag the JSONB column as modified so SQLAlchemy detects the change
        flag_modified(project, "brand_wizard_state")

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

        # Import here to avoid circular import
        from app.integrations.claude import get_claude

        # Debug logging for Claude client state
        logger.info(
            "Synthesis phase Claude client check",
            extra={
                "project_id": project_id,
                "claude_available": claude.available,
                "claude_model": claude.model,
                "claude_id": id(claude),
                "has_api_key": bool(claude._api_key),
            },
        )

        # If passed client isn't available, try getting fresh from global
        if not claude.available:
            logger.warning(
                "Passed Claude client not available, trying global instance",
                extra={"project_id": project_id},
            )
            claude = await get_claude()
            logger.info(
                "Got fresh Claude client from global",
                extra={
                    "project_id": project_id,
                    "fresh_claude_available": claude.available,
                    "fresh_claude_id": id(claude),
                },
            )

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

            # Skip sections handled outside the synthesis loop (e.g. subreddit_research)
            if section_name not in SECTION_PROMPTS:
                logger.info(
                    "Skipping section (handled post-synthesis)",
                    extra={"section": section_name},
                )
                continue

            # Get the system prompt for this section
            system_prompt = SECTION_PROMPTS[section_name]

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
            # ai_prompt_snippet needs more tokens for comprehensive output
            section_max_tokens = 4096 if section_name == "ai_prompt_snippet" else 2048
            try:
                result: CompletionResult = await asyncio.wait_for(
                    claude.complete(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
                        max_tokens=section_max_tokens,
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

                # Extract JSON from response that may have preamble text
                # Look for the first { and last } to extract JSON object
                if not json_text.startswith("{"):
                    first_brace = json_text.find("{")
                    if first_brace != -1:
                        last_brace = json_text.rfind("}")
                        if last_brace != -1 and last_brace > first_brace:
                            json_text = json_text[first_brace : last_brace + 1]

                # Fix unescaped control characters in string values
                json_text = fix_json_control_chars(json_text)

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

        # Post-processing: seed vocabulary.competitors from competitor_context
        _seed_competitors_from_context(generated_sections, project_id)

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
        try:
            logger.info("Calling complete_generation", extra={"project_id": project_id})
            await BrandConfigService.complete_generation(db, project_id)
            logger.info("complete_generation returned", extra={"project_id": project_id})
        except Exception as e:
            logger.exception(
                "Error in complete_generation",
                extra={"project_id": project_id, "error": str(e)},
            )

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

    @staticmethod
    async def get_brand_config(
        db: AsyncSession,
        project_id: str,
    ) -> BrandConfig:
        """Get the brand config for a project.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.

        Returns:
            BrandConfig instance.

        Raises:
            HTTPException: 404 if project not found or brand config not generated yet.
        """
        # Verify project exists
        await BrandConfigService._get_project(db, project_id)

        # Get brand config
        stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
        result = await db.execute(stmt)
        brand_config = result.scalar_one_or_none()

        if brand_config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Brand config not generated yet for project '{project_id}'",
            )

        return brand_config

    @staticmethod
    async def update_sections(
        db: AsyncSession,
        project_id: str,
        sections: dict[str, dict[str, Any]],
    ) -> BrandConfig:
        """Update specific sections of a brand config.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.
            sections: Dict mapping section names to their updated content.

        Returns:
            Updated BrandConfig instance.

        Raises:
            HTTPException: 404 if project not found or brand config not generated yet.
        """
        # Get existing brand config (validates project and config existence)
        brand_config = await BrandConfigService.get_brand_config(db, project_id)

        # Update the v2_schema with new section content
        updated_schema = dict(brand_config.v2_schema)  # Copy existing schema

        for section_name, section_content in sections.items():
            updated_schema[section_name] = section_content

        # Update the timestamp and schema
        brand_config.v2_schema = updated_schema
        brand_config.updated_at = datetime.now(UTC)

        await db.flush()
        await db.refresh(brand_config)

        logger.info(
            "Updated brand config sections",
            extra={
                "project_id": project_id,
                "brand_config_id": brand_config.id,
                "sections_updated": list(sections.keys()),
            },
        )

        return brand_config

    @staticmethod
    async def regenerate_sections(
        db: AsyncSession,
        project_id: str,
        sections: list[str] | None,
        perplexity: PerplexityClient,
        crawl4ai: Crawl4AIClient,
        claude: ClaudeClient,
    ) -> BrandConfig:
        """Regenerate specific sections or all sections of a brand config.

        Args:
            db: AsyncSession for database operations.
            project_id: UUID string of the project.
            sections: List of section names to regenerate, or None for all.
            perplexity: PerplexityClient for web research.
            crawl4ai: Crawl4AIClient for website crawling.
            claude: ClaudeClient for LLM generation.

        Returns:
            Updated BrandConfig instance.

        Raises:
            HTTPException: 404 if project not found or brand config not generated yet.
            HTTPException: 503 if Claude is not available.
        """
        # Import here to avoid circular import
        from app.integrations.claude import get_claude

        # Get existing brand config (validates project and config existence)
        brand_config = await BrandConfigService.get_brand_config(db, project_id)

        # If passed client isn't available, try getting fresh from global
        if not claude.available:
            logger.warning(
                "Passed Claude client not available in regenerate, trying global instance",
                extra={"project_id": project_id},
            )
            claude = await get_claude()

        if not claude.available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Claude LLM is not configured",
            )

        # Determine which sections to regenerate
        sections_to_regenerate = sections if sections else GENERATION_STEPS

        logger.info(
            "Starting section regeneration",
            extra={
                "project_id": project_id,
                "sections": sections_to_regenerate,
            },
        )

        # Run research phase to get fresh context
        research_context = await BrandConfigService._research_phase(
            db=db,
            project_id=project_id,
            perplexity=perplexity,
            crawl4ai=crawl4ai,
        )

        if not research_context.has_any_data():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No research data available for regeneration",
            )

        # Build research text for prompts
        import json

        research_text_parts: list[str] = []

        if research_context.perplexity_research:
            research_text_parts.append(
                f"## Web Research\n{research_context.perplexity_research}"
            )

        if research_context.crawl_content:
            crawl_preview = research_context.crawl_content[:8000]
            if len(research_context.crawl_content) > 8000:
                crawl_preview += "\n... (content truncated)"
            research_text_parts.append(f"## Website Content\n{crawl_preview}")

        if research_context.document_texts:
            docs_combined = "\n---\n".join(research_context.document_texts)
            if len(docs_combined) > 4000:
                docs_combined = docs_combined[:4000] + "\n... (documents truncated)"
            research_text_parts.append(f"## Uploaded Documents\n{docs_combined}")

        research_text = "\n\n".join(research_text_parts)

        # Get existing sections for context
        existing_sections = dict(brand_config.v2_schema)

        # Regenerate requested sections
        regenerated_sections: dict[str, Any] = {}
        errors: list[str] = []

        for section_name in sections_to_regenerate:
            if section_name not in SECTION_PROMPTS:
                errors.append(f"Unknown section: {section_name}")
                continue

            logger.info(
                "Regenerating section",
                extra={"project_id": project_id, "section": section_name},
            )

            system_prompt = SECTION_PROMPTS[section_name]

            # Build user prompt with research context and other existing sections
            user_prompt_parts = [
                "# Research Context",
                research_text,
            ]

            # Add other existing sections as context (not being regenerated)
            context_sections = {
                k: v
                for k, v in existing_sections.items()
                if k in GENERATION_STEPS
                and k != section_name
                and k not in sections_to_regenerate
            }
            if context_sections:
                user_prompt_parts.append("\n# Existing Brand Sections (for context)")
                for prev_section, prev_data in context_sections.items():
                    if isinstance(prev_data, dict):
                        user_prompt_parts.append(
                            f"\n## {prev_section}\n```json\n{json.dumps(prev_data, indent=2)}\n```"
                        )

            # Add already regenerated sections
            if regenerated_sections:
                user_prompt_parts.append("\n# Previously Regenerated Sections")
                for prev_section, prev_data in regenerated_sections.items():
                    user_prompt_parts.append(
                        f"\n## {prev_section}\n```json\n{json.dumps(prev_data, indent=2)}\n```"
                    )

            user_prompt_parts.append(
                f"\n\nRegenerate the {section_name.replace('_', ' ')} section now."
            )
            user_prompt = "\n".join(user_prompt_parts)

            # ai_prompt_snippet needs more tokens for comprehensive output
            section_max_tokens = 4096 if section_name == "ai_prompt_snippet" else 2048
            try:
                result = await asyncio.wait_for(
                    claude.complete(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
                        max_tokens=section_max_tokens,
                        temperature=0.3,
                    ),
                    timeout=SECTION_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                error_msg = f"Timeout regenerating {section_name}"
                logger.error(error_msg, extra={"project_id": project_id})
                errors.append(error_msg)
                continue

            if not result.success:
                error_msg = f"Failed to regenerate {section_name}: {result.error}"
                logger.error(error_msg, extra={"project_id": project_id})
                errors.append(error_msg)
                continue

            # Parse JSON response
            try:
                response_text = result.text or ""
                json_text = response_text.strip()

                if json_text.startswith("```"):
                    lines = json_text.split("\n")
                    lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    json_text = "\n".join(lines)

                # Extract JSON from response that may have preamble text
                if not json_text.startswith("{"):
                    first_brace = json_text.find("{")
                    if first_brace != -1:
                        last_brace = json_text.rfind("}")
                        if last_brace != -1 and last_brace > first_brace:
                            json_text = json_text[first_brace : last_brace + 1]

                # Fix unescaped control characters in string values
                json_text = fix_json_control_chars(json_text)

                section_data = json.loads(json_text)
                regenerated_sections[section_name] = section_data

                logger.info(
                    "Section regenerated successfully",
                    extra={"project_id": project_id, "section": section_name},
                )

            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse {section_name} JSON: {e}"
                logger.error(error_msg, extra={"project_id": project_id})
                errors.append(error_msg)
                continue

        # Update brand config with regenerated sections
        updated_schema = dict(brand_config.v2_schema)
        for section_name, section_data in regenerated_sections.items():
            updated_schema[section_name] = section_data

        if errors:
            updated_schema["_regeneration_warnings"] = errors

        brand_config.v2_schema = updated_schema
        brand_config.updated_at = datetime.now(UTC)

        await db.flush()
        await db.refresh(brand_config)

        logger.info(
            "Brand config regeneration completed",
            extra={
                "project_id": project_id,
                "sections_regenerated": list(regenerated_sections.keys()),
                "errors": errors if errors else None,
            },
        )

        return brand_config


def _seed_competitors_from_context(
    generated_sections: dict[str, Any],
    project_id: str,
) -> None:
    """Back-fill vocabulary.competitors from competitor_context.direct_competitors.

    After all sections are generated, extracts competitor names from the
    competitor_context section and stores them in vocabulary.competitors.
    This gives users a solid starting list of competitor brands from day one.

    Mutates generated_sections in place.
    """
    competitor_context = generated_sections.get("competitor_context")
    if not isinstance(competitor_context, dict):
        return

    direct_competitors = competitor_context.get("direct_competitors", [])
    if not isinstance(direct_competitors, list) or not direct_competitors:
        return

    # Extract competitor names
    competitor_names: list[str] = []
    for comp in direct_competitors:
        if isinstance(comp, dict):
            name = comp.get("name", "").strip()
            if name:
                competitor_names.append(name)

    if not competitor_names:
        return

    # Ensure vocabulary section exists
    vocabulary = generated_sections.get("vocabulary")
    if not isinstance(vocabulary, dict):
        vocabulary = {}
        generated_sections["vocabulary"] = vocabulary

    # Merge with any existing competitors (case-insensitive dedup)
    existing = vocabulary.get("competitors", [])
    if not isinstance(existing, list):
        existing = []

    existing_lower = {name.lower() for name in existing}
    for name in competitor_names:
        if name.lower() not in existing_lower:
            existing.append(name)
            existing_lower.add(name.lower())

    vocabulary["competitors"] = existing

    logger.info(
        "Seeded vocabulary.competitors from competitor_context",
        extra={
            "project_id": project_id,
            "competitor_count": len(existing),
        },
    )
