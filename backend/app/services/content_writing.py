"""Content writing service for SEO collection page content.

Constructs structured prompts from ContentBrief, brand config, and page context
for generating page_title, meta_description, top_description, and bottom_description.
Calls Claude Sonnet to generate content and stores results in PageContent.
"""

import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, CompletionResult
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.page_content import ContentStatus, PageContent
from app.models.prompt_log import PromptLog

logger = get_logger(__name__)

# Model to use for content writing (Sonnet for quality)
CONTENT_WRITING_MODEL = "claude-sonnet-4-5-20250929"
CONTENT_WRITING_MAX_TOKENS = 4096
CONTENT_WRITING_TEMPERATURE = 0.7

# Default word count target when ContentBrief is missing
DEFAULT_WORD_COUNT_MIN = 300
DEFAULT_WORD_COUNT_MAX = 400


@dataclass
class PromptPair:
    """System and user prompts for a content writing Claude call."""

    system_prompt: str
    user_prompt: str


def build_content_prompt(
    page: CrawledPage,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None = None,
) -> PromptPair:
    """Build system and user prompts for content generation.

    Constructs a structured prompt with labeled sections combining POP brief data,
    brand configuration, and crawled page context. Falls back gracefully when
    ContentBrief is missing (omits LSI terms, uses default word count).

    Args:
        page: The CrawledPage to generate content for.
        keyword: Primary target keyword for the page.
        brand_config: The BrandConfig.v2_schema dict (contains ai_prompt_snippet,
            vocabulary, etc.).
        content_brief: Optional ContentBrief with LSI terms and word count targets.

    Returns:
        PromptPair with system_prompt and user_prompt ready for Claude.
    """
    system_prompt = _build_system_prompt(brand_config)
    user_prompt = _build_user_prompt(page, keyword, brand_config, content_brief)
    return PromptPair(system_prompt=system_prompt, user_prompt=user_prompt)


def _build_system_prompt(brand_config: dict[str, Any]) -> str:
    """Build the system prompt using ai_prompt_snippet from brand config.

    Args:
        brand_config: The BrandConfig.v2_schema dict.

    Returns:
        System prompt string.
    """
    ai_snippet = brand_config.get("ai_prompt_snippet", {})
    full_prompt = ""
    if isinstance(ai_snippet, dict):
        full_prompt = ai_snippet.get("full_prompt", "")

    base = (
        "You are an expert SEO copywriter generating collection page content. "
        "You write compelling, search-optimized content that drives organic traffic "
        "and converts visitors into customers."
    )

    if full_prompt:
        return f"{base}\n\n## Brand Guidelines\n{full_prompt}"

    return base


def _build_user_prompt(
    page: CrawledPage,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None,
) -> str:
    """Build the user prompt with labeled sections.

    Args:
        page: The CrawledPage to generate content for.
        keyword: Primary target keyword.
        brand_config: The BrandConfig.v2_schema dict.
        content_brief: Optional ContentBrief with LSI terms and word count targets.

    Returns:
        User prompt string with ## Task, ## Page Context, ## SEO Targets,
        ## Brand Voice, and ## Output Format sections.
    """
    sections: list[str] = []

    # ## Task
    sections.append(_build_task_section(keyword))

    # ## Page Context
    sections.append(_build_page_context_section(page))

    # ## SEO Targets
    sections.append(_build_seo_targets_section(keyword, content_brief))

    # ## Brand Voice
    brand_voice = _build_brand_voice_section(brand_config)
    if brand_voice:
        sections.append(brand_voice)

    # ## Output Format
    sections.append(_build_output_format_section())

    return "\n\n".join(sections)


def _build_task_section(keyword: str) -> str:
    """Build the ## Task section."""
    return (
        f"## Task\n"
        f"Generate SEO-optimized content for a collection page targeting "
        f'the keyword "{keyword}". Produce all 4 content fields in a single '
        f"JSON response."
    )


def _build_page_context_section(page: CrawledPage) -> str:
    """Build the ## Page Context section with URL, title, meta, product count, labels."""
    lines = ["## Page Context"]
    lines.append(f"- **URL:** {page.normalized_url}")
    lines.append(f"- **Current Title:** {page.title or '(none)'}")
    lines.append(f"- **Current Meta Description:** {page.meta_description or '(none)'}")
    lines.append(
        f"- **Product Count:** {page.product_count if page.product_count is not None else 'unknown'}"
    )

    labels = page.labels or []
    if labels:
        lines.append(f"- **Labels:** {', '.join(str(label) for label in labels)}")
    else:
        lines.append("- **Labels:** (none)")

    return "\n".join(lines)


def _build_seo_targets_section(
    keyword: str,
    content_brief: ContentBrief | None,
) -> str:
    """Build the ## SEO Targets section with LSI terms, variations, and word count."""
    lines = ["## SEO Targets"]
    lines.append(f"- **Primary Keyword:** {keyword}")

    if content_brief is not None:
        # LSI terms with weights
        lsi_terms: list[dict[str, Any]] = content_brief.lsi_terms or []
        if lsi_terms:
            lines.append("- **LSI Terms:**")
            for term in lsi_terms:
                phrase = term.get("phrase", "")
                weight = term.get("weight", 0)
                target_count = term.get("targetCount", 0)
                lines.append(
                    f"  - {phrase} (weight: {weight}, target count: {target_count})"
                )

        # Variations / related searches
        variations: list[str] = content_brief.related_searches or []
        if variations:
            lines.append(f"- **Keyword Variations:** {', '.join(variations)}")

        # Word count target from brief
        wc_target = content_brief.word_count_target
        if wc_target:
            lines.append(
                f"- **Word Count Target (bottom_description):** ~{wc_target} words"
            )
        else:
            lines.append(
                f"- **Word Count Target (bottom_description):** "
                f"{DEFAULT_WORD_COUNT_MIN}-{DEFAULT_WORD_COUNT_MAX} words"
            )
    else:
        # Fallback: no brief available
        lines.append(
            "- **LSI Terms:** not available (generate naturally relevant content)"
        )
        lines.append(
            f"- **Word Count Target (bottom_description):** "
            f"{DEFAULT_WORD_COUNT_MIN}-{DEFAULT_WORD_COUNT_MAX} words"
        )

    return "\n".join(lines)


def _build_brand_voice_section(brand_config: dict[str, Any]) -> str | None:
    """Build the ## Brand Voice section from ai_prompt_snippet and vocabulary.

    Returns None if no brand voice data is available.
    """
    lines = ["## Brand Voice"]
    has_content = False

    # ai_prompt_snippet content
    ai_snippet = brand_config.get("ai_prompt_snippet", {})
    if isinstance(ai_snippet, dict):
        full_prompt = ai_snippet.get("full_prompt", "")
        if full_prompt:
            lines.append(full_prompt)
            has_content = True

    # Banned words from vocabulary section
    vocabulary = brand_config.get("vocabulary", {})
    if isinstance(vocabulary, dict):
        banned_words: list[str] = vocabulary.get("banned_words", [])
        if banned_words:
            lines.append(f"\n**Banned Words:** {', '.join(banned_words)}")
            has_content = True

    if not has_content:
        return None

    return "\n".join(lines)


def _build_output_format_section() -> str:
    """Build the ## Output Format section specifying JSON structure."""
    return (
        "## Output Format\n"
        "Respond with ONLY a valid JSON object (no markdown fencing, no extra text) "
        "containing exactly these 4 keys:\n"
        "\n"
        "```\n"
        "{\n"
        '  "page_title": "...",\n'
        '  "meta_description": "...",\n'
        '  "top_description": "...",\n'
        '  "bottom_description": "..."\n'
        "}\n"
        "```\n"
        "\n"
        "**Field specifications:**\n"
        "- **page_title**: SEO-optimized, includes the primary keyword, under 60 characters.\n"
        "- **meta_description**: Optimized for click-through rate, includes the primary keyword, under 160 characters.\n"
        "- **top_description**: Plain text, 1-2 sentences describing the collection page. No HTML.\n"
        "- **bottom_description**: HTML with headings (`<h2>`, `<h3>`) and an FAQ section. "
        "Target the word count specified above. Use semantic HTML (no inline styles)."
    )


# ---------------------------------------------------------------------------
# Content generation service
# ---------------------------------------------------------------------------

REQUIRED_CONTENT_KEYS = {"page_title", "meta_description", "top_description", "bottom_description"}

STRICT_RETRY_PROMPT = (
    "Your previous response was not valid JSON. "
    "You MUST respond with ONLY a raw JSON object. "
    "No markdown fencing (```), no explanation, no text before or after. "
    "Just the JSON object with these exact keys: "
    "page_title, meta_description, top_description, bottom_description."
)


@dataclass
class ContentWritingResult:
    """Result of a content generation attempt."""

    success: bool
    page_content: PageContent | None = None
    error: str | None = None


async def generate_content(
    db: AsyncSession,
    crawled_page: CrawledPage,
    content_brief: ContentBrief | None,
    brand_config: dict[str, Any],
    keyword: str,
) -> ContentWritingResult:
    """Generate content for a page using Claude Sonnet.

    Builds prompts, calls Claude, parses the JSON response into PageContent fields,
    and creates PromptLog records for auditing.

    Args:
        db: Async database session.
        crawled_page: The page to generate content for.
        content_brief: Optional POP content brief with LSI terms.
        brand_config: The BrandConfig.v2_schema dict.
        keyword: Primary target keyword.

    Returns:
        ContentWritingResult with success status and the PageContent record.
    """
    # Get or create PageContent record
    page_content = crawled_page.page_content
    if page_content is None:
        page_content = PageContent(crawled_page_id=crawled_page.id)
        db.add(page_content)
        await db.flush()

    # Mark as writing
    page_content.status = ContentStatus.WRITING.value
    page_content.generation_started_at = datetime.now(UTC)
    await db.flush()

    # Build prompts
    prompts = build_content_prompt(crawled_page, keyword, brand_config, content_brief)

    # Create PromptLog records before calling Claude
    system_log = PromptLog(
        page_content_id=page_content.id,
        step="content_writing",
        role="system",
        prompt_text=prompts.system_prompt,
    )
    user_log = PromptLog(
        page_content_id=page_content.id,
        step="content_writing",
        role="user",
        prompt_text=prompts.user_prompt,
    )
    db.add(system_log)
    db.add(user_log)
    await db.flush()

    # Call Claude Sonnet
    client = ClaudeClient(
        model=CONTENT_WRITING_MODEL,
        max_tokens=CONTENT_WRITING_MAX_TOKENS,
    )
    try:
        start_ms = time.monotonic()
        result = await client.complete(
            user_prompt=prompts.user_prompt,
            system_prompt=prompts.system_prompt,
            max_tokens=CONTENT_WRITING_MAX_TOKENS,
            temperature=CONTENT_WRITING_TEMPERATURE,
        )
        duration_ms = (time.monotonic() - start_ms) * 1000
    except Exception as exc:
        duration_ms = 0.0
        result = CompletionResult(success=False, error=str(exc))
    finally:
        await client.close()

    # Update prompt logs with response metadata
    _update_prompt_logs(system_log, user_log, result, duration_ms)

    if not result.success:
        return _mark_failed(page_content, f"Claude API error: {result.error}")

    # Parse JSON response
    parsed = _parse_content_json(result.text or "")
    if parsed is None:
        # Retry once with stricter prompt
        logger.warning(
            "Invalid JSON from Claude, retrying with strict prompt",
            extra={"page_id": crawled_page.id},
        )
        return await _retry_with_strict_prompt(
            db, client, page_content, prompts, result.text or "", brand_config
        )

    # Populate PageContent fields
    _apply_parsed_content(page_content, parsed)
    page_content.status = ContentStatus.COMPLETE.value
    page_content.generation_completed_at = datetime.now(UTC)
    await db.flush()

    logger.info(
        "Content generated successfully",
        extra={
            "page_id": crawled_page.id,
            "word_count": page_content.word_count,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        },
    )

    return ContentWritingResult(success=True, page_content=page_content)


async def _retry_with_strict_prompt(
    db: AsyncSession,
    _client: ClaudeClient,  # noqa: ARG001
    page_content: PageContent,
    original_prompts: PromptPair,
    original_response: str,
    brand_config: dict[str, Any],  # noqa: ARG001
) -> ContentWritingResult:
    """Retry content generation with a stricter JSON-only prompt.

    Creates new PromptLog records for the retry attempt.
    """
    retry_user_prompt = f"{STRICT_RETRY_PROMPT}\n\nOriginal prompt:\n{original_prompts.user_prompt}"

    # Create retry prompt logs
    retry_system_log = PromptLog(
        page_content_id=page_content.id,
        step="content_writing_retry",
        role="system",
        prompt_text=original_prompts.system_prompt,
    )
    retry_user_log = PromptLog(
        page_content_id=page_content.id,
        step="content_writing_retry",
        role="user",
        prompt_text=retry_user_prompt,
    )
    db.add(retry_system_log)
    db.add(retry_user_log)
    await db.flush()

    retry_client = ClaudeClient(
        model=CONTENT_WRITING_MODEL,
        max_tokens=CONTENT_WRITING_MAX_TOKENS,
    )
    try:
        start_ms = time.monotonic()
        retry_result = await retry_client.complete(
            user_prompt=retry_user_prompt,
            system_prompt=original_prompts.system_prompt,
            max_tokens=CONTENT_WRITING_MAX_TOKENS,
            temperature=0.0,  # Deterministic for retry
        )
        duration_ms = (time.monotonic() - start_ms) * 1000
    except Exception as exc:
        duration_ms = 0.0
        retry_result = CompletionResult(success=False, error=str(exc))
    finally:
        await retry_client.close()

    _update_prompt_logs(retry_system_log, retry_user_log, retry_result, duration_ms)

    if not retry_result.success:
        return _mark_failed(
            page_content,
            f"Retry Claude API error: {retry_result.error}",
        )

    parsed = _parse_content_json(retry_result.text or "")
    if parsed is None:
        return _mark_failed(
            page_content,
            f"Invalid JSON after retry. Original response: {original_response[:500]}",
        )

    _apply_parsed_content(page_content, parsed)
    page_content.status = ContentStatus.COMPLETE.value
    page_content.generation_completed_at = datetime.now(UTC)
    await db.flush()

    return ContentWritingResult(success=True, page_content=page_content)


def _parse_content_json(text: str) -> dict[str, str] | None:
    """Parse Claude's response as JSON with the 4 required content keys.

    Handles markdown code fences and extracts JSON. Returns None if invalid.
    """
    cleaned = text.strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # Remove opening fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Try to extract JSON object if surrounded by other text
    if not cleaned.startswith("{"):
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            cleaned = match.group(0)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    # Validate required keys exist
    if not REQUIRED_CONTENT_KEYS.issubset(parsed.keys()):
        return None

    return {k: str(v) for k, v in parsed.items() if k in REQUIRED_CONTENT_KEYS}


def _apply_parsed_content(page_content: PageContent, parsed: dict[str, str]) -> None:
    """Apply parsed content fields to PageContent and compute word count."""
    page_content.page_title = parsed["page_title"]
    page_content.meta_description = parsed["meta_description"]
    page_content.top_description = parsed["top_description"]
    page_content.bottom_description = parsed["bottom_description"]

    # Compute total word count across all fields
    total_words = 0
    for value in parsed.values():
        # Strip HTML tags for word counting
        text_only = re.sub(r"<[^>]+>", " ", value)
        total_words += len(text_only.split())
    page_content.word_count = total_words


def _update_prompt_logs(
    system_log: PromptLog,
    user_log: PromptLog,
    result: CompletionResult,
    duration_ms: float,
) -> None:
    """Update both prompt log records with Claude's response metadata."""
    response_text = result.text or result.error or ""
    for log in (system_log, user_log):
        log.response_text = response_text
        log.model = CONTENT_WRITING_MODEL
        log.input_tokens = result.input_tokens
        log.output_tokens = result.output_tokens
        log.duration_ms = duration_ms


def _mark_failed(page_content: PageContent, error: str) -> ContentWritingResult:
    """Mark PageContent as failed and return a failure result."""
    page_content.status = ContentStatus.FAILED.value
    page_content.generation_completed_at = datetime.now(UTC)
    page_content.qa_results = {"error": error}
    logger.error("Content generation failed", extra={"error": error, "page_content_id": page_content.id})
    return ContentWritingResult(success=False, page_content=page_content, error=error)
