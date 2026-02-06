"""Content writing prompt builder for SEO collection page content.

Constructs structured prompts from ContentBrief, brand config, and page context
for generating page_title, meta_description, top_description, and bottom_description.
"""

from dataclasses import dataclass
from typing import Any

from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage

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
