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

from app.core.logging import get_logger
from app.integrations.claude import CompletionResult, get_claude

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
    1. Builds prompt with content type-specific instructions
    2. Includes context (research, brand voice) if provided
    3. Calls Claude with configured temperature
    4. Parses and validates response

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
    ) -> None:
        """Initialize content generation service.

        Args:
            max_concurrent: Maximum concurrent content generations.
        """
        self._max_concurrent = max_concurrent

        logger.debug(
            "ContentGenerationService initialized",
            extra={
                "max_concurrent": self._max_concurrent,
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
                parts.append("Key Benefits:\n" + "\n".join(f"- {b}" for b in benefits[:5]))
            questions = brief.get("priority_questions")
            if isinstance(questions, list):
                parts.append("Questions to Address:\n" + "\n".join(f"- {q}" for q in questions[:5]))

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

        return "\n\n".join(parts) if parts else "No additional context provided."

    def _build_user_prompt(self, input_data: ContentGenerationInput) -> str:
        """Build the user prompt with all context.

        Args:
            input_data: Input data for content generation

        Returns:
            Complete user prompt
        """
        content_type_prompt = CONTENT_TYPE_PROMPTS.get(
            input_data.content_type,
            CONTENT_TYPE_PROMPTS["collection"]
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
        1. Build prompt with content type-specific instructions
        2. Include context if provided
        3. Call Claude with temperature 0.4
        4. Parse and validate response

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
            content = self._parse_content_response(
                result.text, project_id, page_id
            )

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

        async def generate_one(input_data: ContentGenerationInput) -> ContentGenerationResult:
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
