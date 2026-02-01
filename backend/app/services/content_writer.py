"""Phase 5B: Content writer service with Skill Bible rules.

Generates SEO-optimized content for collection pages by applying Skill Bible
copywriting rules and brand voice to produce human-sounding content.

Features:
- Skill Bible rules embedded in prompt templates (prevents AI-sounding content)
- Brand voice integration from V2 brand config
- Internal linking (related collections + priority pages)
- Structured output: H1, title tag, meta description, top/bottom descriptions

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
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import CompletionResult, get_claude

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
DEFAULT_MAX_CONCURRENT = 5
MAX_CONTENT_PREVIEW_LENGTH = 200
CONTENT_GENERATION_TEMPERATURE = 0.4  # Slightly creative but controlled


# =============================================================================
# SKILL BIBLE PROMPT TEMPLATE
# =============================================================================

SKILL_BIBLE_SYSTEM_PROMPT = """You are an expert SEO copywriter. Your task is to generate collection page content that sounds authentically human, not AI-generated.

## THE SKILL BIBLE - 5 LAWS OF GREAT COPY

### Law 1: Benefits Over Features
Say what it DOES FOR THE CUSTOMER, not what it is.
- BAD: "Made with premium leather"
- GOOD: "Stays soft and supple for years of daily use"

### Law 2: Specificity Sells
Use numbers, materials, and specific details. Vague claims are forgettable.
- BAD: "High-quality materials"
- GOOD: "Hand-stitched with 6oz full-grain leather"

### Law 3: One Idea Per Sentence
Short, punchy sentences. Each sentence delivers one clear thought.
- BAD: "Our products are designed with care and attention to detail and made with the finest materials sourced from around the world."
- GOOD: "Every piece is hand-inspected. We source materials from three trusted tanneries. Quality you can see and feel."

### Law 4: Write Like You Talk
If you stumble reading it aloud, rewrite it. Natural rhythm matters.

### Law 5: Every Word Earns Its Place
Cut unnecessary words. "Very unique" → "unique". "In order to" → "to".

## STRUCTURE REQUIREMENTS

### H1 (Title)
- 3-7 words, Title Case
- Include primary keyword naturally
- NO benefit taglines (never "for Ultimate Freshness")
- Example: "Premium Leather Wallets" NOT "Premium Leather Wallets for Everyday Elegance"

### Title Tag
- Under 60 characters
- Format: "[Primary Keyword] | [Brand Name]"

### Meta Description
- 150-160 characters
- Include primary keyword
- End with a soft CTA

### Paragraphs
- 2-4 sentences maximum per paragraph
- Address customer with "you" and "your"

### Bottom Description
- EXACTLY 300-450 words (this is mandatory)
- Follow this structure:
  <h2>[Primary keyword phrase, Title Case, max 7 words]</h2>
  <p>[Opening: 80-100 words about quality, selection]</p>
  <h3>[Selling point with keyword, max 7 words]</h3>
  <p>[Benefits: 80-100 words, weave in PAA answers naturally]</p>
  <p>Related: [3 internal links with descriptive anchor text]</p>
  <p>See Also: [3 internal links with descriptive anchor text]</p>
  <h3>[Second selling point, max 7 words]</h3>
  <p>[Closing: 60-80 words with CTA, mention shipping/guarantee]</p>

## BANNED ELEMENTS (Instant AI Detection)

### NEVER USE Em Dashes
- BAD: "Our collection — featuring premium items — delivers value"
- GOOD: "Our collection features premium items. Each one delivers value."

### BANNED WORDS (Never use these)
delve, unlock, unleash, journey, game-changer, revolutionary, crucial, cutting-edge, elevate, leverage, synergy, innovative, paradigm, holistic, empower, transformative

### BANNED PHRASES (Never use these)
- "In today's fast-paced world"
- "It's important to note"
- "When it comes to"
- "At the end of the day"
- "Look no further"
- "Whether you're looking for"

### BANNED PATTERNS
- Triplet patterns: "Fast. Simple. Powerful." or "Quality. Value. Trust."
- Negation patterns: "aren't just X, they're Y" or "more than just X"
- Rhetorical questions as openers

### LIMITED USE (Max 1 per page)
indeed, furthermore, moreover, robust, seamless, comprehensive, enhance, optimize, streamline

## OUTPUT FORMAT

Respond with valid JSON only (no markdown code blocks):
{
  "h1": "Title Here",
  "title_tag": "Title Tag Here | Brand",
  "meta_description": "Meta description here with keyword and CTA.",
  "top_description": "<p>Short intro paragraph for above the fold.</p>",
  "bottom_description": "<h2>...</h2><p>...</p>...",
  "word_count": 350
}"""


CONTENT_WRITER_USER_PROMPT_TEMPLATE = """Generate collection page content for:

## Page Details
- Primary Keyword: {keyword}
- URL: {url}
- Brand Name: {brand_name}

## Research Insights (from Phase 5A)
{research_brief}

## Brand Voice
{brand_voice}

## Internal Links to Include

Related Collections (use 3):
{related_links}

Priority Pages (use 3):
{priority_links}

## Requirements Checklist
1. H1: 3-7 words, Title Case, includes "{keyword}"
2. Title tag: Under 60 chars, format "[Keyword] | {brand_name}"
3. Meta description: 150-160 chars with soft CTA
4. Bottom description: EXACTLY 300-450 words
5. Include all 6 internal links (3 Related + 3 See Also)
6. NO em dashes, banned words, or AI patterns
7. Address reader as "you/your"

Generate the content now. Respond with JSON only:"""


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class InternalLink:
    """An internal link for content insertion."""

    url: str
    anchor_text: str
    link_type: str = "related"  # "related" or "priority"

    def to_html(self) -> str:
        """Convert to HTML anchor tag."""
        return f'<a href="{self.url}">{self.anchor_text}</a>'


@dataclass
class ContentWriterInput:
    """Input data for content generation."""

    keyword: str
    url: str
    brand_name: str
    research_brief: dict[str, Any] | None = None
    brand_voice: dict[str, Any] | None = None
    related_links: list[InternalLink] = field(default_factory=list)
    priority_links: list[InternalLink] = field(default_factory=list)
    project_id: str | None = None
    page_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "keyword": self.keyword,
            "url": self.url,
            "brand_name": self.brand_name,
            "research_brief": self.research_brief,
            "has_brand_voice": self.brand_voice is not None,
            "related_links_count": len(self.related_links),
            "priority_links_count": len(self.priority_links),
            "project_id": self.project_id,
            "page_id": self.page_id,
        }


@dataclass
class GeneratedContent:
    """Generated content from Phase 5B."""

    h1: str
    title_tag: str
    meta_description: str
    top_description: str
    bottom_description: str
    word_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "h1": self.h1,
            "title_tag": self.title_tag,
            "meta_description": self.meta_description,
            "top_description": self.top_description,
            "bottom_description": self.bottom_description,
            "word_count": self.word_count,
        }


@dataclass
class ContentWriterResult:
    """Result of Phase 5B content generation."""

    success: bool
    keyword: str
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


class ContentWriterServiceError(Exception):
    """Base exception for content writer service errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        page_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.page_id = page_id


class ContentWriterValidationError(ContentWriterServiceError):
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


class ContentWriterService:
    """Service for Phase 5B content generation with Skill Bible rules.

    Generates SEO-optimized collection page content by:
    1. Loading research briefs from Phase 5A
    2. Applying Skill Bible copywriting rules via prompt template
    3. Integrating brand voice
    4. Inserting internal links
    5. Producing structured content (H1, title tag, meta, descriptions)

    Usage:
        service = ContentWriterService()
        result = await service.generate_content(
            input_data=ContentWriterInput(
                keyword="leather wallets",
                url="/collections/leather-wallets",
                brand_name="Acme Co",
                research_brief={...},
                brand_voice={...},
            ),
        )
    """

    def __init__(
        self,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        """Initialize content writer service.

        Args:
            max_concurrent: Maximum concurrent content generations.
        """
        self._max_concurrent = max_concurrent

        logger.debug(
            "ContentWriterService initialized",
            extra={
                "max_concurrent": self._max_concurrent,
            },
        )

    def _format_research_brief(self, brief: dict[str, Any] | None) -> str:
        """Format research brief for prompt insertion.

        Args:
            brief: Research brief from Phase 5A

        Returns:
            Formatted string for prompt
        """
        if not brief:
            return "No research data available."

        parts: list[str] = []

        # Main angle
        main_angle = brief.get("main_angle")
        if isinstance(main_angle, dict):
            angle = main_angle.get("primary_angle", "")
            rationale = main_angle.get("rationale", "")
            if angle:
                parts.append(f"Main Angle: {angle}")
            if rationale:
                parts.append(f"Rationale: {rationale}")

        # Benefits
        benefits = brief.get("benefits")
        if isinstance(benefits, list) and benefits:
            benefit_texts = []
            for b in benefits[:5]:
                if isinstance(b, dict):
                    benefit_texts.append(f"- {b.get('benefit', '')}")
                elif isinstance(b, str):
                    benefit_texts.append(f"- {b}")
            if benefit_texts:
                parts.append("Key Benefits:\n" + "\n".join(benefit_texts))

        # Priority questions
        questions = brief.get("priority_questions")
        if isinstance(questions, list) and questions:
            question_texts = []
            for q in questions[:5]:
                if isinstance(q, dict):
                    question_texts.append(f"- {q.get('question', '')}")
                elif isinstance(q, str):
                    question_texts.append(f"- {q}")
            if question_texts:
                parts.append(
                    "Priority Questions to Address:\n" + "\n".join(question_texts)
                )

        return "\n\n".join(parts) if parts else "No research data available."

    def _format_brand_voice(self, voice: dict[str, Any] | None) -> str:
        """Format brand voice for prompt insertion.

        Args:
            voice: Brand voice config from V2 schema

        Returns:
            Formatted string for prompt
        """
        if not voice:
            return "Use a professional, helpful tone."

        parts: list[str] = []

        tone = voice.get("tone")
        if tone:
            parts.append(f"Tone: {tone}")

        personality = voice.get("personality")
        if isinstance(personality, list):
            parts.append(f"Personality: {', '.join(personality)}")

        if style := voice.get("writing_style"):
            parts.append(f"Writing Style: {style}")

        if audience := voice.get("target_audience"):
            parts.append(f"Target Audience: {audience}")

        if value_prop := voice.get("value_proposition"):
            parts.append(f"Value Proposition: {value_prop}")

        return "\n".join(parts) if parts else "Use a professional, helpful tone."

    def _format_links(self, links: list[InternalLink]) -> str:
        """Format internal links for prompt insertion.

        Args:
            links: List of internal links

        Returns:
            Formatted string for prompt
        """
        if not links:
            return "No links available."

        formatted = []
        for link in links[:3]:  # Max 3 links
            formatted.append(f"- {link.anchor_text}: {link.url}")

        return "\n".join(formatted)

    def _build_user_prompt(self, input_data: ContentWriterInput) -> str:
        """Build the user prompt with all context.

        Args:
            input_data: Input data for content generation

        Returns:
            Complete user prompt
        """
        return CONTENT_WRITER_USER_PROMPT_TEMPLATE.format(
            keyword=input_data.keyword,
            url=input_data.url,
            brand_name=input_data.brand_name,
            research_brief=self._format_research_brief(input_data.research_brief),
            brand_voice=self._format_brand_voice(input_data.brand_voice),
            related_links=self._format_links(input_data.related_links),
            priority_links=self._format_links(input_data.priority_links),
        )

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
            top_description = parsed.get("top_description", "").strip()
            bottom_description = parsed.get("bottom_description", "").strip()
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

            if not bottom_description:
                logger.warning(
                    "Validation failed: empty bottom_description",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "field": "bottom_description",
                        "rejected_value": "",
                    },
                )
                return None

            # Calculate actual word count if not provided
            if not word_count:
                # Strip HTML tags for word count
                import re

                clean_text = re.sub(r"<[^>]+>", " ", bottom_description)
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
                top_description=top_description,
                bottom_description=bottom_description,
                word_count=word_count,
            )

        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse content JSON",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "error": str(e),
                    "response_preview": response_text[:MAX_CONTENT_PREVIEW_LENGTH],
                },
            )
            return None

    async def generate_content(
        self,
        input_data: ContentWriterInput,
    ) -> ContentWriterResult:
        """Generate content for a single page.

        Phase 5B content generation:
        1. Build prompt with Skill Bible rules
        2. Include research brief, brand voice, and internal links
        3. Call Claude with temperature 0.4
        4. Parse and validate response

        Args:
            input_data: Input data for content generation

        Returns:
            ContentWriterResult with generated content or error
        """
        start_time = time.monotonic()
        project_id = input_data.project_id
        page_id = input_data.page_id

        logger.debug(
            "Phase 5B content generation starting",
            extra={
                "keyword": input_data.keyword[:50],
                "url": input_data.url[:100],
                "brand_name": input_data.brand_name[:50],
                "has_research_brief": input_data.research_brief is not None,
                "has_brand_voice": input_data.brand_voice is not None,
                "related_links_count": len(input_data.related_links),
                "priority_links_count": len(input_data.priority_links),
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
            raise ContentWriterValidationError(
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
            raise ContentWriterValidationError(
                "brand_name",
                "",
                "Brand name cannot be empty",
                project_id=project_id,
                page_id=page_id,
            )

        try:
            # Log phase transition
            logger.info(
                "Phase 5B: Content writer - in_progress",
                extra={
                    "keyword": input_data.keyword[:50],
                    "phase": "5B",
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
                return ContentWriterResult(
                    success=False,
                    keyword=input_data.keyword,
                    error="Claude LLM not available",
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    project_id=project_id,
                    page_id=page_id,
                )

            # Build prompt
            user_prompt = self._build_user_prompt(input_data)

            # Call Claude
            result: CompletionResult = await claude.complete(
                system_prompt=SKILL_BIBLE_SYSTEM_PROMPT,
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
                        "error": result.error,
                        "status_code": result.status_code,
                        "request_id": result.request_id,
                        "duration_ms": round(duration_ms, 2),
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )
                return ContentWriterResult(
                    success=False,
                    keyword=input_data.keyword,
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
                return ContentWriterResult(
                    success=False,
                    keyword=input_data.keyword,
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
                "Phase 5B: Content writer - completed",
                extra={
                    "keyword": input_data.keyword[:50],
                    "h1": content.h1[:50],
                    "word_count": content.word_count,
                    "phase": "5B",
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
                    "Slow Phase 5B content generation operation",
                    extra={
                        "keyword": input_data.keyword[:50],
                        "duration_ms": round(duration_ms, 2),
                        "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        "project_id": project_id,
                        "page_id": page_id,
                    },
                )

            return ContentWriterResult(
                success=True,
                keyword=input_data.keyword,
                content=content,
                duration_ms=duration_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                request_id=result.request_id,
                project_id=project_id,
                page_id=page_id,
            )

        except ContentWriterValidationError:
            raise
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Phase 5B content generation unexpected error",
                extra={
                    "keyword": input_data.keyword[:50] if input_data.keyword else "",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": round(duration_ms, 2),
                    "project_id": project_id,
                    "page_id": page_id,
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return ContentWriterResult(
                success=False,
                keyword=input_data.keyword,
                error=f"Unexpected error: {e}",
                duration_ms=duration_ms,
                project_id=project_id,
                page_id=page_id,
            )

    async def generate_content_batch(
        self,
        inputs: list[ContentWriterInput],
        max_concurrent: int | None = None,
        project_id: str | None = None,
    ) -> list[ContentWriterResult]:
        """Generate content for multiple pages.

        Args:
            inputs: List of input data for content generation
            max_concurrent: Maximum concurrent generations (None = use default)
            project_id: Project ID for logging

        Returns:
            List of ContentWriterResult, one per input
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

        async def generate_one(input_data: ContentWriterInput) -> ContentWriterResult:
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


_content_writer_service: ContentWriterService | None = None


def get_content_writer_service() -> ContentWriterService:
    """Get the global content writer service instance.

    Usage:
        from app.services.content_writer import get_content_writer_service
        service = get_content_writer_service()
        result = await service.generate_content(input_data)
    """
    global _content_writer_service
    if _content_writer_service is None:
        _content_writer_service = ContentWriterService()
        logger.info("ContentWriterService singleton created")
    return _content_writer_service


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def generate_content(
    keyword: str,
    url: str,
    brand_name: str,
    research_brief: dict[str, Any] | None = None,
    brand_voice: dict[str, Any] | None = None,
    related_links: list[InternalLink] | None = None,
    priority_links: list[InternalLink] | None = None,
    project_id: str | None = None,
    page_id: str | None = None,
) -> ContentWriterResult:
    """Convenience function for Phase 5B content generation.

    Args:
        keyword: Primary keyword for the page
        url: Page URL
        brand_name: Brand name for title tag
        research_brief: Research brief from Phase 5A
        brand_voice: Brand voice config from V2 schema
        related_links: Related collection links
        priority_links: Priority page links
        project_id: Project ID for logging
        page_id: Page ID for logging

    Returns:
        ContentWriterResult with generated content
    """
    service = get_content_writer_service()
    input_data = ContentWriterInput(
        keyword=keyword,
        url=url,
        brand_name=brand_name,
        research_brief=research_brief,
        brand_voice=brand_voice,
        related_links=related_links or [],
        priority_links=priority_links or [],
        project_id=project_id,
        page_id=page_id,
    )
    return await service.generate_content(input_data)
