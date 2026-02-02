"""Content Generation service for generating page content.

Generates SEO-optimized content for various page types using LLM capabilities.

Features:
- Multi-format content generation (collection, product, blog, landing)
- Configurable tone and word count
- Context-aware content (research briefs, brand voice)
- Batch processing with concurrent execution

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import asyncio
import json
import time
import traceback
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.claude import CompletionResult, get_claude
from app.services.pop_content_brief import (
    POPContentBriefResult,
    POPContentBriefService,
)

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
DEFAULT_MAX_CONCURRENT = 5
CONTENT_PREVIEW_LENGTH = 200
CONTENT_GENERATION_TEMPERATURE = 0.4


# =============================================================================
# SYSTEM PROMPTS FOR DIFFERENT CONTENT TYPES
# =============================================================================

CONTENT_GENERATION_SYSTEM_PROMPT = """You are an expert content writer. Your task is to generate high-quality, SEO-optimized content that sounds natural and engaging.

## WRITING GUIDELINES

### Style
- Write in a clear, accessible style
- Use short, punchy sentences (one idea per sentence)
- Address the reader as "you" and "your"
- Focus on benefits over features
- Be specific with details, not vague

### Structure
- Use proper HTML structure with h1, h2, h3, p tags
- Break content into scannable sections
- Keep paragraphs to 2-4 sentences

### SEO Best Practices
- Include the primary keyword naturally in H1, title, and content
- Title tag: under 60 characters, format "[Keyword] | [Brand]"
- Meta description: 150-160 characters with soft CTA

### Avoid
- Em dashes (use periods or commas instead)
- AI-sounding words: delve, unlock, unleash, journey, game-changer, revolutionary, cutting-edge, elevate, leverage, synergy, innovative, paradigm, holistic, empower, transformative
- Banned phrases: "In today's fast-paced world", "It's important to note", "When it comes to", "At the end of the day", "Look no further"
- Triplet patterns: "Fast. Simple. Powerful."
- Rhetorical questions as openers

## OUTPUT FORMAT

Respond with valid JSON only (no markdown code blocks):
{
  "h1": "Page Title Here",
  "title_tag": "Title Tag Here | Brand",
  "meta_description": "Meta description here with keyword and CTA.",
  "body_content": "<h2>...</h2><p>...</p>...",
  "word_count": 400
}"""


CONTENT_TYPE_PROMPTS = {
    "collection": """Generate collection page content with:
- H1: 3-7 words, Title Case, includes primary keyword
- Body: Product benefits, selection highlights, why shop here
- Include sections for quality, selection, and value""",
    "product": """Generate product page content with:
- H1: Product name with key benefit
- Body: Features as benefits, use cases, specifications
- Include social proof elements and CTAs""",
    "blog": """Generate blog post content with:
- H1: Engaging title that promises value
- Body: Educational content with practical takeaways
- Include introduction, main sections, conclusion""",
    "landing": """Generate landing page content with:
- H1: Clear value proposition
- Body: Problem/solution, benefits, trust signals
- Include strong CTAs throughout""",
}


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ContentGenerationInput:
    """Input data for content generation."""

    keyword: str
    url: str
    brand_name: str
    content_type: str = "collection"
    tone: str = "professional"
    target_word_count: int = 400
    context: dict[str, Any] | None = None
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "keyword": self.keyword,
            "url": self.url,
            "brand_name": self.brand_name,
            "content_type": self.content_type,
            "tone": self.tone,
            "target_word_count": self.target_word_count,
            "has_context": self.context is not None,
            "project_id": self.project_id,
            "page_id": self.page_id,
        }


@dataclass
class GeneratedContent:
    """Generated content from content generation."""

    h1: str
    title_tag: str
    meta_description: str
    body_content: str
    word_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "h1": self.h1,
            "title_tag": self.title_tag,
            "meta_description": self.meta_description,
            "body_content": self.body_content,
            "word_count": self.word_count,
        }


@dataclass
class ContentGenerationResult:
    """Result of content generation."""

    success: bool
    keyword: str
    content_type: str
    content: GeneratedContent | None = None
    error: str | None = None
    duration_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "keyword": self.keyword,
            "content_type": self.content_type,
            "content": self.content.to_dict() if self.content else None,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "request_id": self.request_id,
            "project_id": self.project_id,
            "page_id": self.page_id,
        }


# =============================================================================
# EXCEPTIONS
# =============================================================================


class ContentGenerationServiceError(Exception):
    """Base exception for content generation service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class ContentGenerationValidationError(ContentGenerationServiceError):
    """Raised when validation fails."""

    def __init__(
        self,
        field_name: str,
        value: Any,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Validation error for {field_name}: {message}", project_id, page_id
        )
        self.field_name = field_name
        self.value = value


# =============================================================================
# SERVICE
# =============================================================================


class ContentGenerationService:
    """Service for content generation.

    Generates SEO-optimized content for various page types:
    1. Optionally fetches content brief from POP (when flag enabled)
    2. Builds prompt with content type-specific instructions
    3. Includes context (research, brand voice, POP brief) if provided
    4. Calls Claude with configured temperature
    5. Parses and validates response

    Usage:
        service = ContentGenerationService()
        result = await service.generate_content(
            input_data=ContentGenerationInput(
                keyword="leather wallets",
                url="/collections/leather-wallets",
                brand_name="Acme Co",
                content_type="collection",
            ),
        )
    """

    def __init__(
        self,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
        pop_brief_service: POPContentBriefService | None = None,
    ) -> None:
        """Initialize content generation service.

        Args:
            max_concurrent: Maximum concurrent content generations.
            pop_brief_service: Optional POP content brief service for dependency injection.
        """
        self._max_concurrent = max_concurrent
        self._pop_brief_service = pop_brief_service

        logger.debug(
            "ContentGenerationService initialized",
            extra={
                "max_concurrent": self._max_concurrent,
                "pop_brief_service_provided": pop_brief_service is not None,
            },
        )

    def _format_context(self, context: dict[str, Any] | None) -> str:
        """Format context for prompt insertion.

        Args:
            context: Additional context (research brief, brand voice, etc.)

        Returns:
            Formatted string for prompt
        """
        if not context:
            return "No additional context provided."

        parts: list[str] = []

        # Research brief
        brief = context.get("research_brief")
        if isinstance(brief, dict):
            if angle := brief.get("main_angle"):
                parts.append(f"Main Angle: {angle}")
            benefits = brief.get("benefits")
            if isinstance(benefits, list):
                parts.append(
                    "Key Benefits:\n" + "\n".join(f"- {b}" for b in benefits[:5])
                )
            questions = brief.get("priority_questions")
            if isinstance(questions, list):
                parts.append(
                    "Questions to Address:\n"
                    + "\n".join(f"- {q}" for q in questions[:5])
                )

        # Brand voice
        voice = context.get("brand_voice")
        if isinstance(voice, dict):
            if tone := voice.get("tone"):
                parts.append(f"Brand Tone: {tone}")
            personality = voice.get("personality")
            if isinstance(personality, list):
                parts.append(f"Brand Personality: {', '.join(personality)}")
            if style := voice.get("writing_style"):
                parts.append(f"Writing Style: {style}")

        # Additional notes
        if notes := context.get("notes"):
            parts.append(f"Additional Notes: {notes}")

        # POP Content Brief data (if present)
        pop_brief = context.get("pop_content_brief")
        if isinstance(pop_brief, dict):
            parts.append(self._format_pop_brief(pop_brief))

        return "\n\n".join(parts) if parts else "No additional context provided."

    def _format_pop_brief(self, pop_brief: dict[str, Any]) -> str:
        """Format POP content brief data for prompt insertion.

        Args:
            pop_brief: POP content brief data with word count targets, LSI terms, etc.

        Returns:
            Formatted string for prompt
        """
        parts: list[str] = []

        parts.append("## POP Content Brief Targets")

        # Word count targets
        word_count_target = pop_brief.get("word_count_target")
        word_count_min = pop_brief.get("word_count_min")
        word_count_max = pop_brief.get("word_count_max")
        if word_count_target is not None:
            word_count_info = f"Target Word Count: {word_count_target}"
            if word_count_min is not None and word_count_max is not None:
                word_count_info += f" (range: {word_count_min}-{word_count_max})"
            parts.append(word_count_info)

        # Page score target
        page_score_target = pop_brief.get("page_score_target")
        if page_score_target is not None:
            parts.append(f"Target Page Score: {page_score_target}")

        # Heading targets
        heading_targets = pop_brief.get("heading_targets", [])
        if heading_targets:
            heading_info = ["Heading Structure Targets:"]
            for h in heading_targets[:6]:
                if isinstance(h, dict):
                    level = h.get("level", "").upper()
                    min_count = h.get("min_count")
                    max_count = h.get("max_count")
                    if min_count is not None and max_count is not None:
                        heading_info.append(f"- {level}: {min_count}-{max_count} tags")
                    elif min_count is not None:
                        heading_info.append(f"- {level}: at least {min_count} tags")
            if len(heading_info) > 1:
                parts.append("\n".join(heading_info))

        # LSI terms (top 15 for prompt length)
        lsi_terms = pop_brief.get("lsi_terms", [])
        if lsi_terms:
            lsi_info = ["LSI Terms to Include (aim for target count):"]
            for term in lsi_terms[:15]:
                if isinstance(term, dict):
                    phrase = term.get("phrase", "")
                    target_count = term.get("target_count")
                    weight = term.get("weight")
                    if phrase:
                        term_line = f'- "{phrase}"'
                        if target_count is not None:
                            term_line += f" (target: {target_count}x)"
                        if weight is not None:
                            term_line += f" [weight: {weight:.2f}]"
                        lsi_info.append(term_line)
            if len(lsi_info) > 1:
                parts.append("\n".join(lsi_info))

        # Keyword targets by section (top keywords)
        keyword_targets = pop_brief.get("keyword_targets", [])
        # Filter out section totals
        actual_keywords = [
            k
            for k in keyword_targets
            if isinstance(k, dict)
            and not str(k.get("keyword", "")).startswith("_total_")
        ]
        if actual_keywords:
            kw_info = ["Keyword Density Targets by Section:"]
            seen_sections: set[str] = set()
            for kw in actual_keywords[:10]:
                if isinstance(kw, dict):
                    keyword = kw.get("keyword", "")
                    section = kw.get("section", "")
                    density_target = kw.get("density_target")
                    if keyword and section and section not in seen_sections:
                        kw_line = f'- {section}: "{keyword}"'
                        if density_target is not None:
                            kw_line += f" (target: {density_target})"
                        kw_info.append(kw_line)
                        seen_sections.add(section)
            if len(kw_info) > 1:
                parts.append("\n".join(kw_info))

        # Related questions (PAA)
        related_questions = pop_brief.get("related_questions", [])
        if related_questions:
            paa_info = ["Related Questions to Address:"]
            for q in related_questions[:5]:
                if isinstance(q, dict):
                    question = q.get("question", "")
                    if question:
                        paa_info.append(f"- {question}")
            if len(paa_info) > 1:
                parts.append("\n".join(paa_info))

        # Competitor insights (just count for context)
        competitors = pop_brief.get("competitors", [])
        if competitors:
            parts.append(
                f"Based on analysis of {len(competitors)} top-ranking competitors."
            )

        return "\n\n".join(parts) if len(parts) > 1 else ""

    async def _fetch_pop_content_brief(
        self,
        project_id: str | None,
        page_id: str | None,
        keyword: str,
        url: str,
    ) -> POPContentBriefResult | None:
        """Fetch content brief from POP API if enabled.

        This method checks the use_pop_content_brief flag and fetches
        the brief if enabled. Errors are logged but don't block content
        generation - the method returns None on failure.

        Args:
            project_id: Project ID for logging
            page_id: Page ID for logging
            keyword: Target keyword for content optimization
            url: Page URL for content optimization

        Returns:
            POPContentBriefResult if successful, None if disabled or failed
        """
        settings = get_settings()

        if not settings.use_pop_content_brief:
            logger.debug(
                "POP content brief disabled by feature flag",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "flag": "use_pop_content_brief",
                },
            )
            return None

        # Get or create the POP brief service
        if self._pop_brief_service is None:
            self._pop_brief_service = POPContentBriefService()

        try:
            logger.info(
                "Fetching POP content brief before content generation",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": keyword[:50] if keyword else "",
                },
            )

            result = await self._pop_brief_service.fetch_brief(
                project_id=project_id or "",
                page_id=page_id or "",
                keyword=keyword,
                target_url=url,
            )

            if result.success:
                logger.info(
                    "POP content brief fetched successfully",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "task_id": result.task_id,
                        "word_count_target": result.word_count_target,
                        "lsi_term_count": len(result.lsi_terms),
                        "duration_ms": round(result.duration_ms, 2),
                    },
                )
                return result
            else:
                logger.warning(
                    "POP content brief fetch failed - proceeding without brief",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "error": result.error,
                        "duration_ms": round(result.duration_ms, 2),
                    },
                )
                return None

        except Exception as e:
            logger.warning(
                "POP content brief fetch error - proceeding without brief",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "stack_trace": traceback.format_exc(),
                },
            )
            return None

    def _pop_brief_to_context(self, brief: POPContentBriefResult) -> dict[str, Any]:
        """Convert POP brief result to context dict for prompt inclusion.

        Args:
            brief: POPContentBriefResult from fetch_brief()

        Returns:
            Dictionary with brief data formatted for context
        """
        return {
            "word_count_target": brief.word_count_target,
            "word_count_min": brief.word_count_min,
            "word_count_max": brief.word_count_max,
            "heading_targets": brief.heading_targets,
            "keyword_targets": brief.keyword_targets,
            "lsi_terms": brief.lsi_terms,
            "related_questions": brief.related_questions,
            "competitors": brief.competitors,
            "page_score_target": brief.page_score_target,
        }

    def _build_user_prompt(self, input_data: ContentGenerationInput) -> str:
        """Build the user prompt with all context.

        Args:
            input_data: Input data for content generation

        Returns:
            Complete user prompt
        """
        content_type_prompt = CONTENT_TYPE_PROMPTS.get(
            input_data.content_type, CONTENT_TYPE_PROMPTS["collection"]
        )

        return f"""Generate {input_data.content_type} page content for:

## Page Details
- Primary Keyword: {input_data.keyword}
- URL: {input_data.url}
- Brand Name: {input_data.brand_name}
- Desired Tone: {input_data.tone}
- Target Word Count: {input_data.target_word_count} words

## Content Type Instructions
{content_type_prompt}

## Context
{self._format_context(input_data.context)}

## Requirements
1. H1: Include "{input_data.keyword}" naturally
2. Title tag: Under 60 chars, format "[Keyword] | {input_data.brand_name}"
3. Meta description: 150-160 chars with soft CTA
4. Body content: Approximately {input_data.target_word_count} words
5. Use {input_data.tone} tone throughout
6. NO em dashes, banned words, or AI patterns
7. Address reader as "you/your"

Generate the content now. Respond with JSON only:"""

    def _parse_content_response(
        self,
        response_text: str,
        project_id: str | None,
        page_id: str | None,
    ) -> GeneratedContent | None:
        """Parse LLM response into GeneratedContent.

        Args:
            response_text: Raw response text from Claude
            project_id: Project ID for logging
            page_id: Page ID for logging

        Returns:
            GeneratedContent or None if parsing fails
        """
        try:
            # Handle markdown code blocks
            text = response_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(
                    line for line in lines if not line.startswith("```")
                ).strip()

            # Remove any "json" label
            if text.startswith("json"):
                text = text[4:].strip()

            parsed = json.loads(text)

            if not isinstance(parsed, dict):
                logger.warning(
                    "Content response is not a dict",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "type": type(parsed).__name__,
                    },
                )
                return None

            # Extract and validate fields
            h1 = parsed.get("h1", "").strip()
            title_tag = parsed.get("title_tag", "").strip()
            meta_description = parsed.get("meta_description", "").strip()
            body_content = parsed.get("body_content", "").strip()
            word_count = parsed.get("word_count", 0)

            # Basic validation
            if not h1:
                logger.warning(
                    "Validation failed: empty h1",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "field": "h1",
                        "rejected_value": "",
                    },
                )
                return None

            if not body_content:
                logger.warning(
                    "Validation failed: empty body_content",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "field": "body_content",
                        "rejected_value": "",
                    },
                )
                return None

            # Calculate actual word count if not provided
            if not word_count:
                import re

                clean_text = re.sub(r"<[^>]+>", " ", body_content)
                word_count = len(clean_text.split())

            logger.debug(
                "Content response parsed successfully",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "h1_length": len(h1),
                    "word_count": word_count,
                },
            )

            return GeneratedContent(
                h1=h1,
                title_tag=title_tag,
                meta_description=meta_description,
                body_content=body_content,
                word_count=word_count,
            )

        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse content JSON",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "error": str(e),
                    "response_preview": response_text[:CONTENT_PREVIEW_LENGTH],
                },
            )
            return None

    async def generate_content(
        self,
        input_data: ContentGenerationInput,
    ) -> ContentGenerationResult:
        """Generate content for a single page.

        Content generation process:
        1. Check use_pop_content_brief flag and fetch brief if enabled
        2. Build prompt with content type-specific instructions
        3. Include context (including POP brief) if provided
        4. Call Claude with temperature 0.4
        5. Parse and validate response

        Args:
            input_data: Input data for content generation

        Returns:
            ContentGenerationResult with generated content or error
        """
        start_time = time.monotonic()
        project_id = input_data.project_id
        page_id = input_data.page_id

        logger.debug(
            "Content generation starting",
            extra={
                "keyword": input_data.keyword[:50],
                "url": input_data.url[:100],
                "brand_name": input_data.brand_name[:50],
                "content_type": input_data.content_type,
                "tone": input_data.tone,
                "target_word_count": input_data.target_word_count,
                "has_context": input_data.context is not None,
                "project_id": project_id,
                "page_id": page_id,
            },
        )

        # Validate inputs
        if not input_data.keyword or not input_data.keyword.strip():
            logger.warning(
                "Content generation validation failed - empty keyword",
                extra={
                    "field": "keyword",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise ContentGenerationValidationError(
                "keyword",
                "",
                "Keyword cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        if not input_data.brand_name or not input_data.brand_name.strip():
            logger.warning(
                "Content generation validation failed - empty brand_name",
                extra={
                    "field": "brand_name",
                    "value": "",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )
            raise ContentGenerationValidationError(
                "brand_name",
                "",
                "Brand name cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        try:
            # Log phase transition
            logger.info(
                "Content generation - in_progress",
                extra={
                    "keyword": input_data.keyword[:50],
                    "content_type": input_data.content_type,
                    "status": "in_progress",
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            # Get Claude client
            claude = await get_claude()

            if not claude.available:
                logger.warning(
                    "Claude not available for content generation",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return ContentGenerationResult(
                    success=False,
                    keyword=input_data.keyword,
                    content_type=input_data.content_type,
                    error="Claude LLM not available",
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    project_id=project_id,
                    page_id=page_id,
                )

            # Fetch POP content brief if enabled (errors don't block generation)
            pop_brief = await self._fetch_pop_content_brief(
                project_id=project_id,
                page_id=page_id,
                keyword=input_data.keyword,
                url=input_data.url,
            )

            # Merge POP brief data into context if available
            if pop_brief is not None:
                # Create or update context with POP brief data
                if input_data.context is None:
                    input_data.context = {}
                input_data.context["pop_content_brief"] = self._pop_brief_to_context(
                    pop_brief
                )

                # Override target word count if POP provides one
                if pop_brief.word_count_target is not None:
                    input_data.target_word_count = pop_brief.word_count_target
                    logger.debug(
                        "Using POP word count target",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "pop_word_count_target": pop_brief.word_count_target,
                        },
                    )

            # Build prompt
            user_prompt = self._build_user_prompt(input_data)

            # Call Claude
            result: CompletionResult = await claude.complete(
                system_prompt=CONTENT_GENERATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=CONTENT_GENERATION_TEMPERATURE,
                max_tokens=2000,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if not result.success or not result.text:
                logger.warning(
                    "LLM content generation failed",
                    extra={
                        "keyword": input_data.keyword[:50],
                        "content_type": input_data.content_type,
                        "error": result.error,
                        "status_code": result.status_code,
                        "request_id": result.request_id,
                        "duration_ms": round(duration_ms, 2),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return ContentGenerationResult(
                    success=False,
                    keyword=input_data.keyword,
                    content_type=input_data.content_type,
                    error=result.error or "LLM generation failed",
                    duration_ms=duration_ms,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                    project_id=project_id,
                    page_id=page_id,
                )

            # Parse response
            content = self._parse_content_response(result.text, project_id, page_id)

            if not content:
                return ContentGenerationResult(
                    success=False,
                    keyword=input_data.keyword,
                    content_type=input_data.content_type,
                    error="Failed to parse LLM response",
                    duration_ms=duration_ms,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                    project_id=project_id,
                    page_id=page_id,
                )

            # Log completion
            logger.info(
                "Content generation - completed",
                extra={
                    "keyword": input_data.keyword[:50],
                    "content_type": input_data.content_type,
                    "h1": content.h1[:50],
                    "word_count": content.word_count,
                    "status": "completed",
                    "duration_ms": round(duration_ms, 2),
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "request_id": result.request_id,
                    "project_id": project_id,
                    "page_id": page_id,
                },
            )

            if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                logger.warning(
                    "Slow content generation operation",
                    extra={
                        "keyword": input_data.keyword[:50],
                        "content_type": input_data.content_type,
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            return ContentGenerationResult(
                success=True,
                keyword=input_data.keyword,
                content_type=input_data.content_type,
                content=content,
                duration_ms=duration_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                request_id=result.request_id,
                project_id=project_id,
                page_id=page_id,
            )

        except ContentGenerationValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Content generation unexpected error",
                extra={
                    "keyword": input_data.keyword[:50] if input_data.keyword else "",
                    "content_type": input_data.content_type,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return ContentGenerationResult(
                success=False,
                keyword=input_data.keyword,
                content_type=input_data.content_type,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

    async def generate_content_batch(
        self,
        inputs: list[ContentGenerationInput],
        max_concurrent: int | None = None,
        project_id: str | None = None,
    ) -> list[ContentGenerationResult]:
        """Generate content for multiple pages.

        Args:
            inputs: List of input data for content generation
            max_concurrent: Maximum concurrent generations (None = use default)
            project_id: Project ID for logging

        Returns:
            List of ContentGenerationResult, one per input
        """
        start_time = time.monotonic()
        max_concurrent = max_concurrent or self._max_concurrent

        logger.info(
            "Batch content generation started",
            extra={
                "input_count": len(inputs),
                "max_concurrent": max_concurrent,
                "project_id": project_id,
            },
        )

        if not inputs:
            return []

        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_one(
            input_data: ContentGenerationInput,
        ) -> ContentGenerationResult:
            async with semaphore:
                return await self.generate_content(input_data)

        tasks = [generate_one(inp) for inp in inputs]
        results = await asyncio.gather(*tasks)

        duration_ms = (time.monotonic() - start_time) * 1000
        success_count = sum(1 for r in results if r.success)

        logger.info(
            "Batch content generation complete",
            extra={
                "input_count": len(inputs),
                "success_count": success_count,
                "failure_count": len(inputs) - success_count,
                "duration_ms": round(duration_ms, 2),
                "project_id": project_id,
            },
        )

        if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
            logger.warning(
                "Slow batch content generation operation",
                extra={
                    "input_count": len(inputs),
                    "duration_ms": round(duration_ms, 2),
                    "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                    "project_id": project_id,
                },
            )

        return list(results)


# =============================================================================
# SINGLETON
# =============================================================================


_content_generation_service: ContentGenerationService | None = None


def get_content_generation_service() -> ContentGenerationService:
    """Get the global content generation service instance.

    Usage:
        from app.services.content_generation import get_content_generation_service
        service = get_content_generation_service()
        result = await service.generate_content(input_data)
    """
    global _content_generation_service
    if _content_generation_service is None:
        _content_generation_service = ContentGenerationService()
        logger.info("ContentGenerationService singleton created")
    return _content_generation_service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def generate_content(
    keyword: str,
    url: str,
    brand_name: str,
    content_type: str = "collection",
    tone: str = "professional",
    target_word_count: int = 400,
    context: dict[str, Any] | None = None,
    project_id: str | None = None,
    page_id: str | None = None,
) -> ContentGenerationResult:
    """Convenience function for content generation.

    Args:
        keyword: Primary keyword for the page
        url: Page URL
        brand_name: Brand name for title tag
        content_type: Type of content (collection, product, blog, landing)
        tone: Desired tone for the content
        target_word_count: Target word count
        context: Additional context (research brief, brand voice)
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        ContentGenerationResult with generated content
    """
    service = get_content_generation_service()
    input_data = ContentGenerationInput(
        keyword=keyword,
        url=url,
        brand_name=brand_name,
        content_type=content_type,
        tone=tone,
        target_word_count=target_word_count,
        context=context,
        project_id=project_id,
        page_id=page_id,
    )
    return await service.generate_content(input_data)
