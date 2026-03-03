"""Content outline service for outline-first content generation.

Generates structured outlines from POP brief data and brand config,
then generates full content from approved outlines.
"""

import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, CompletionResult, get_api_key
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.page_content import ContentStatus, PageContent
from app.models.prompt_log import PromptLog
from app.services.content_writing import _build_system_prompt

logger = get_logger(__name__)

OUTLINE_MODEL = "claude-sonnet-4-5"
OUTLINE_MAX_TOKENS = 8192
OUTLINE_TEMPERATURE = 0.7
OUTLINE_TIMEOUT = 180.0


@dataclass
class OutlineResult:
    """Result of an outline generation attempt."""

    success: bool
    page_content: PageContent | None = None
    outline_json: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class OutlineContentResult:
    """Result of generating content from an approved outline."""

    success: bool
    page_content: PageContent | None = None
    error: str | None = None


def _build_outline_system_prompt() -> str:
    """Build system prompt for outline generation."""
    return (
        "You are an expert SEO content strategist. Your task is to create a detailed "
        "content outline for a collection page that will rank well in search engines "
        "and convert visitors into customers.\n\n"
        "You produce structured outlines that define the page's heading hierarchy, "
        "section purposes, and key talking points. The outline serves as a blueprint "
        "for a copywriter to follow.\n\n"
        "## Guidelines\n"
        "- Every H2 section should answer a specific question the searcher has\n"
        "- Order sections by search intent priority (most important questions first)\n"
        "- Include 4-8 H2 sections depending on topic complexity\n"
        "- Each section should have 2-4 concrete key points\n"
        "- Use the provided LSI terms and keyword variations to inform section topics\n"
        "- Incorporate People Also Ask questions as natural section topics\n"
        "- Analyze competitor headings to ensure comprehensive coverage\n"
    )


def _build_outline_user_prompt(
    page: CrawledPage,
    keyword: str,
    content_brief: ContentBrief | None,
    brand_config: dict[str, Any],
) -> str:
    """Build user prompt for outline generation with POP brief data."""
    sections: list[str] = []

    # Task
    sections.append(
        f'## Task\nCreate a detailed content outline for a collection page targeting '
        f'the keyword "{keyword}". Produce a JSON response following the exact schema below.'
    )

    # Page context
    context_lines = ["## Page Context"]
    context_lines.append(f"- **URL:** {page.normalized_url}")
    context_lines.append(f"- **Primary Keyword:** {keyword}")
    if page.title:
        context_lines.append(f"- **Current Title:** {page.title}")
    sections.append("\n".join(context_lines))

    # POP Brief Data
    if content_brief:
        brief_lines = ["## SEO Research Data"]

        # LSI Terms
        lsi_terms = content_brief.lsi_terms or []
        if lsi_terms:
            brief_lines.append(f"\n### LSI Terms ({len(lsi_terms)})")
            for term in lsi_terms[:25]:
                phrase = term.get("phrase", "")
                avg_count = term.get("averageCount", 0)
                weight = term.get("weight", 0)
                brief_lines.append(f"- {phrase} (target count: {avg_count}, weight: {weight})")

        # Keyword Variations
        variations = content_brief.related_searches or []
        if variations:
            brief_lines.append(f"\n### Keyword Variations ({len(variations)})")
            for v in variations:
                brief_lines.append(f"- {v}")

        # People Also Ask
        paa = content_brief.related_questions or []
        if paa:
            brief_lines.append(f"\n### People Also Ask ({len(paa)})")
            for q in paa:
                brief_lines.append(f"- {q}")

        # Competitors
        competitors = content_brief.competitors or []
        if competitors:
            brief_lines.append(f"\n### Top Competitors ({len(competitors)})")
            for comp in competitors[:10]:
                url = comp.get("url", "")
                title = comp.get("title", "")
                wc = comp.get("wordCount") or 0
                brief_lines.append(f"- {title} ({url}) - {wc} words")

        # Heading Structure Targets
        heading_targets = content_brief.heading_targets or []
        if heading_targets:
            brief_lines.append(f"\n### Heading Structure Targets")
            for h in heading_targets:
                tag = h.get("tag", "")
                target = h.get("target", 0)
                brief_lines.append(f"- {tag}: {target}")

        sections.append("\n".join(brief_lines))

    # Brand context
    brand_foundation = brand_config.get("brand_foundation", {})
    if isinstance(brand_foundation, dict):
        company_overview = brand_foundation.get("company_overview", {})
        if isinstance(company_overview, dict):
            company_name = company_overview.get("company_name", "")
            if company_name:
                sections.append(f"## Brand\n- **Company:** {company_name}")

    # Output schema
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    sections.append(
        '## Output Format\n'
        'Respond with ONLY a raw JSON object (no markdown fencing). Use this exact schema:\n'
        '```\n'
        '{\n'
        f'  "page_name": "Descriptive page name",\n'
        f'  "primary_keyword": "{keyword}",\n'
        '  "secondary_keywords": ["keyword2", "keyword3"],\n'
        f'  "date": "{today}",\n'
        '  "audience": "2-3 sentences describing who this page is for",\n'
        '  "keyword_reference": {\n'
        '    "lsi_terms": [{"term": "example term", "target_count": 3}],\n'
        '    "keyword_variations": [{"variation": "example variation", "verbatim_required": true}]\n'
        '  },\n'
        '  "people_also_ask": ["Question 1", "Question 2"],\n'
        '  "top_ranked_results": [{"url": "https://...", "title": "...", "word_count": 1200}],\n'
        '  "page_progression": [\n'
        '    {"order": 1, "question_answered": "What question does this section answer?", "label": "section-label", "tag": "h2", "headline": "Section Headline"}\n'
        '  ],\n'
        '  "section_details": [\n'
        '    {\n'
        '      "label": "section-label",\n'
        '      "tag": "h2",\n'
        '      "headline": "Section Headline",\n'
        '      "purpose": "One sentence describing section purpose",\n'
        '      "key_points": ["Point 1", "Point 2", "Point 3"],\n'
        '      "client_notes": ""\n'
        '    }\n'
        '  ]\n'
        '}\n'
        '```\n\n'
        'IMPORTANT:\n'
        '- keyword_reference, people_also_ask, and top_ranked_results should be populated from the SEO Research Data above\n'
        '- page_progression and section_details are YOUR strategic recommendations\n'
        '- Each section_details entry must have a matching page_progression entry\n'
        '- Labels should be kebab-case slugs\n'
        '- client_notes must ALWAYS be an empty string "" — this field is reserved for human input\n'
    )

    return "\n\n".join(sections)


def _extract_json_block(text: str) -> str | None:
    """Find the outermost balanced JSON object in text."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_outline_json(text: str) -> dict[str, Any] | None:
    """Parse Claude's outline response as JSON."""
    cleaned = text.strip()

    # Strip markdown code fences (```json or ```)
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # drop closing fence
        cleaned = "\n".join(lines).strip()

    # Try direct parse first
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and ("section_details" in parsed or "page_progression" in parsed):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Extract balanced JSON object from surrounding text
    json_block = _extract_json_block(cleaned)
    if json_block:
        try:
            parsed = json.loads(json_block)
            if isinstance(parsed, dict) and ("section_details" in parsed or "page_progression" in parsed):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning(
        "Failed to parse outline JSON",
        extra={"snippet": cleaned[:300], "length": len(cleaned)},
    )
    return None


async def generate_outline(
    db: AsyncSession,
    crawled_page: CrawledPage,
    content_brief: ContentBrief | None,
    brand_config: dict[str, Any],
    keyword: str,
) -> OutlineResult:
    """Generate a content outline for a page using Claude.

    Builds prompts from POP brief data and brand config, calls Claude,
    parses the JSON outline, and stores it in page_content.outline_json.

    Args:
        db: Async database session.
        crawled_page: The page to generate an outline for.
        content_brief: Optional POP content brief with LSI terms.
        brand_config: The BrandConfig.v2_schema dict.
        keyword: Primary target keyword.

    Returns:
        OutlineResult with success status and the outline JSON.
    """
    # Get or create PageContent record
    page_content = crawled_page.page_content
    if page_content is None:
        page_content = PageContent(crawled_page_id=crawled_page.id)
        db.add(page_content)
        await db.flush()
        crawled_page.page_content = page_content

    # Mark as writing with outline_status='generating' for frontend polling
    page_content.status = ContentStatus.WRITING.value
    page_content.outline_status = "generating"
    page_content.generation_started_at = datetime.now(UTC)
    await db.commit()

    # Build prompts
    system_prompt = _build_outline_system_prompt()
    user_prompt = _build_outline_user_prompt(
        crawled_page, keyword, content_brief, brand_config
    )

    # Create PromptLog records
    system_log = PromptLog(
        page_content_id=page_content.id,
        step="write_outline",
        role="system",
        prompt_text=system_prompt,
    )
    user_log = PromptLog(
        page_content_id=page_content.id,
        step="write_outline",
        role="user",
        prompt_text=user_prompt,
    )
    db.add(system_log)
    db.add(user_log)
    await db.flush()

    # Call Claude
    client = ClaudeClient(
        api_key=get_api_key(),
        model=OUTLINE_MODEL,
        max_tokens=OUTLINE_MAX_TOKENS,
        timeout=OUTLINE_TIMEOUT,
    )
    try:
        start_ms = time.monotonic()
        result = await client.complete(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=OUTLINE_MAX_TOKENS,
            temperature=OUTLINE_TEMPERATURE,
        )
        duration_ms = (time.monotonic() - start_ms) * 1000
    except Exception as exc:
        duration_ms = 0.0
        result = CompletionResult(success=False, error=str(exc))
    finally:
        await client.close()

    # Update prompt logs
    response_text = result.text or result.error or ""
    system_log.model = OUTLINE_MODEL
    system_log.input_tokens = result.input_tokens
    system_log.output_tokens = result.output_tokens
    system_log.duration_ms = duration_ms

    user_log.response_text = response_text
    user_log.model = OUTLINE_MODEL
    user_log.input_tokens = result.input_tokens
    user_log.output_tokens = result.output_tokens
    user_log.duration_ms = duration_ms

    if not result.success:
        page_content.status = ContentStatus.FAILED.value
        page_content.outline_status = None  # Clear generating state on failure
        page_content.generation_completed_at = datetime.now(UTC)
        page_content.qa_results = {"error": f"Claude API error: {result.error}"}
        await db.commit()
        return OutlineResult(
            success=False,
            page_content=page_content,
            error=f"Claude API error: {result.error}",
        )

    # Parse outline JSON
    outline = _parse_outline_json(result.text or "")
    if outline is None:
        page_content.status = ContentStatus.FAILED.value
        page_content.outline_status = None  # Clear generating state on failure
        page_content.generation_completed_at = datetime.now(UTC)
        page_content.qa_results = {"error": "Failed to parse outline JSON from Claude response"}
        await db.commit()
        return OutlineResult(
            success=False,
            page_content=page_content,
            error="Failed to parse outline JSON",
        )

    # Store outline
    page_content.outline_json = outline
    page_content.outline_status = "draft"
    page_content.status = ContentStatus.COMPLETE.value
    page_content.generation_completed_at = datetime.now(UTC)
    await db.commit()

    logger.info(
        "Outline generated successfully",
        extra={
            "page_id": crawled_page.id,
            "sections": len(outline.get("section_details", [])),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        },
    )

    return OutlineResult(
        success=True,
        page_content=page_content,
        outline_json=outline,
    )


async def generate_content_from_outline(
    db: AsyncSession,
    crawled_page: CrawledPage,
    content_brief: ContentBrief | None,
    brand_config: dict[str, Any],
    keyword: str,
    outline_json: dict[str, Any],
) -> OutlineContentResult:
    """Generate full content from an approved outline.

    Uses the brand system prompt from content_writing and instructs Claude
    to follow the outline's structure exactly.

    Args:
        db: Async database session.
        crawled_page: The page to generate content for.
        content_brief: Optional POP content brief.
        brand_config: The BrandConfig.v2_schema dict.
        keyword: Primary target keyword.
        outline_json: The approved outline JSON.

    Returns:
        OutlineContentResult with success status.
    """
    page_content = crawled_page.page_content
    if page_content is None:
        page_content = PageContent(crawled_page_id=crawled_page.id)
        db.add(page_content)
        await db.flush()
        crawled_page.page_content = page_content

    # Mark as writing
    page_content.status = ContentStatus.WRITING.value
    page_content.generation_started_at = datetime.now(UTC)
    await db.commit()

    # Build prompts - use the brand system prompt from content_writing
    system_prompt = _build_system_prompt(brand_config)
    user_prompt = _build_content_from_outline_prompt(
        crawled_page, keyword, content_brief, outline_json
    )

    # Create PromptLog records
    system_log = PromptLog(
        page_content_id=page_content.id,
        step="write_from_outline",
        role="system",
        prompt_text=system_prompt,
    )
    user_log = PromptLog(
        page_content_id=page_content.id,
        step="write_from_outline",
        role="user",
        prompt_text=user_prompt,
    )
    db.add(system_log)
    db.add(user_log)
    await db.flush()

    # Call Claude
    client = ClaudeClient(
        api_key=get_api_key(),
        model=OUTLINE_MODEL,
        max_tokens=OUTLINE_MAX_TOKENS,
        timeout=OUTLINE_TIMEOUT,
    )
    try:
        start_ms = time.monotonic()
        result = await client.complete(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=OUTLINE_MAX_TOKENS,
            temperature=OUTLINE_TEMPERATURE,
        )
        duration_ms = (time.monotonic() - start_ms) * 1000
    except Exception as exc:
        duration_ms = 0.0
        result = CompletionResult(success=False, error=str(exc))
    finally:
        await client.close()

    # Update prompt logs
    response_text = result.text or result.error or ""
    system_log.model = OUTLINE_MODEL
    system_log.input_tokens = result.input_tokens
    system_log.output_tokens = result.output_tokens
    system_log.duration_ms = duration_ms

    user_log.response_text = response_text
    user_log.model = OUTLINE_MODEL
    user_log.input_tokens = result.input_tokens
    user_log.output_tokens = result.output_tokens
    user_log.duration_ms = duration_ms

    if not result.success:
        page_content.status = ContentStatus.FAILED.value
        page_content.generation_completed_at = datetime.now(UTC)
        page_content.qa_results = {"error": f"Claude API error: {result.error}"}
        await db.commit()
        return OutlineContentResult(
            success=False,
            page_content=page_content,
            error=f"Claude API error: {result.error}",
        )

    # Parse content JSON (4 fields)
    parsed = _parse_content_from_outline_json(result.text or "")
    if parsed is None:
        page_content.status = ContentStatus.FAILED.value
        page_content.generation_completed_at = datetime.now(UTC)
        page_content.qa_results = {"error": "Failed to parse content JSON from Claude response"}
        await db.commit()
        return OutlineContentResult(
            success=False,
            page_content=page_content,
            error="Failed to parse content JSON",
        )

    # Apply content fields
    page_content.page_title = parsed["page_title"]
    page_content.meta_description = parsed["meta_description"]
    page_content.top_description = parsed["top_description"]
    page_content.bottom_description = parsed["bottom_description"]

    # Compute word count
    total_words = 0
    for value in parsed.values():
        text_only = re.sub(r"<[^>]+>", " ", value)
        total_words += len(text_only.split())
    page_content.word_count = total_words

    page_content.status = ContentStatus.COMPLETE.value
    page_content.generation_completed_at = datetime.now(UTC)
    await db.commit()

    logger.info(
        "Content generated from outline successfully",
        extra={
            "page_id": crawled_page.id,
            "word_count": page_content.word_count,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        },
    )

    return OutlineContentResult(success=True, page_content=page_content)


def _build_content_from_outline_prompt(
    page: CrawledPage,
    keyword: str,
    content_brief: ContentBrief | None,
    outline_json: dict[str, Any],
) -> str:
    """Build user prompt for generating content from an approved outline."""
    sections: list[str] = []

    # Task
    sections.append(
        f'## Task\n'
        f'Generate SEO-optimized collection page content for the keyword "{keyword}". '
        f'Follow the approved outline below as your structural blueprint. '
        f'Produce all 4 content fields in a single JSON response.'
    )

    # Page context
    context_lines = ["## Page Context"]
    context_lines.append(f"- **URL:** {page.normalized_url}")
    context_lines.append(f"- **Primary Keyword:** {keyword}")
    sections.append("\n".join(context_lines))

    # Approved outline
    sections.append(
        "## Approved Outline (Follow This Structure Exactly)\n"
        f"```json\n{json.dumps(outline_json, indent=2)}\n```\n\n"
        "Instructions for using the outline:\n"
        "- Follow the page_progression order exactly\n"
        "- Use each section_details headline as your H2/H3 heading\n"
        "- Expand each key_point into 1-2 paragraphs\n"
        "- Incorporate any client_notes verbatim where provided\n"
        "- Use the keyword_reference terms naturally throughout the content\n"
        "- Address people_also_ask questions within relevant sections"
    )

    # LSI terms from brief for density guidance
    if content_brief:
        lsi_terms = content_brief.lsi_terms or []
        if lsi_terms:
            terms_list = []
            for term in lsi_terms[:20]:
                phrase = term.get("phrase", "")
                avg_count = term.get("averageCount", 0)
                terms_list.append(f"- {phrase} (target: {avg_count}x)")
            sections.append(
                "## LSI Term Targets\n"
                "Include these terms at approximately the target frequency:\n"
                + "\n".join(terms_list)
            )

    # Output format
    sections.append(
        '## Output Format\n'
        'Respond with ONLY a raw JSON object (no markdown fencing) with these exact keys:\n'
        '{\n'
        '  "page_title": "SEO-optimized page title (50-60 chars)",\n'
        '  "meta_description": "Compelling meta description (150-160 chars)",\n'
        '  "top_description": "Above-the-fold intro paragraph (plain text, 2-4 sentences)",\n'
        '  "bottom_description": "Full HTML content following the outline structure. '
        'Use <h2>, <h3>, <p>, <ul>, <li>, <strong> tags. '
        'Follow the outline sections in order."\n'
        '}'
    )

    return "\n\n".join(sections)


REQUIRED_CONTENT_KEYS = {"page_title", "meta_description", "top_description", "bottom_description"}


def _parse_content_from_outline_json(text: str) -> dict[str, str] | None:
    """Parse Claude's content response as JSON with 4 required keys."""
    cleaned = text.strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Extract JSON object
    if not cleaned.startswith("{"):
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            cleaned = match.group(0)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and REQUIRED_CONTENT_KEYS.issubset(parsed.keys()):
            return {k: str(v) for k, v in parsed.items() if k in REQUIRED_CONTENT_KEYS}
    except (json.JSONDecodeError, ValueError):
        pass

    logger.warning(
        "Failed to parse content-from-outline JSON",
        extra={"snippet": cleaned[:300], "length": len(cleaned)},
    )
    return None
