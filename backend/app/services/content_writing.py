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
from app.integrations.claude import ClaudeClient, CompletionResult, get_api_key
from app.models.blog import BlogPost
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.page_content import ContentStatus, PageContent
from app.models.prompt_log import PromptLog

logger = get_logger(__name__)

# Model to use for content writing (Sonnet for quality)
CONTENT_WRITING_MODEL = "claude-sonnet-4-5"
CONTENT_WRITING_MAX_TOKENS = 8192
CONTENT_WRITING_TEMPERATURE = 0.7
CONTENT_WRITING_TIMEOUT = 180.0  # Longer timeout for content generation (POP targets can be 1500+ words)

# Default word count target when ContentBrief is missing
DEFAULT_WORD_COUNT_MIN = 300
DEFAULT_WORD_COUNT_MAX = 400


# Marketplace domains to skip when extracting competitor brand names from URLs
_MARKETPLACE_DOMAINS = frozenset({
    "amazon", "ebay", "walmart", "target", "etsy", "alibaba",
    "aliexpress", "wish", "wayfair", "overstock", "bestbuy",
    "homedepot", "lowes", "costco", "samsclub", "kohls",
    "macys", "nordstrom", "zappos", "chewy", "google",
    "youtube", "facebook", "instagram", "pinterest", "tiktok",
    "reddit", "twitter", "linkedin", "yelp", "bbb",
})


def extract_competitor_brands(competitors: list[dict[str, Any]]) -> list[str]:
    """Extract brand names from POP competitor URLs.

    Parses domains, strips 'www.', takes the second-level domain,
    and skips known marketplaces.

    Args:
        competitors: List of competitor dicts with 'url' keys.

    Returns:
        List of brand name strings extracted from domains.
    """
    from urllib.parse import urlparse

    brands: list[str] = []
    seen: set[str] = set()

    for comp in competitors:
        url = comp.get("url", "")
        if not url:
            continue

        try:
            parsed = urlparse(url if "://" in url else f"https://{url}")
            host = parsed.hostname or ""
        except Exception:
            continue

        # Strip www. and extract second-level domain
        host = host.lower().removeprefix("www.")
        sld = host.split(".")[0] if "." in host else host
        if not sld:
            continue

        # Skip marketplaces and social platforms
        if sld in _MARKETPLACE_DOMAINS:
            continue

        # Deduplicate
        if sld in seen:
            continue
        seen.add(sld)
        brands.append(sld)

    return brands


def is_competitor_term(phrase: str, competitor_names: list[str]) -> bool:
    """Check if a phrase contains a competitor brand name.

    Case-insensitive substring match against each competitor name.

    Args:
        phrase: The LSI term or phrase to check.
        competitor_names: List of competitor brand names.

    Returns:
        True if phrase contains any competitor name.
    """
    phrase_lower = phrase.lower()
    return any(name.lower() in phrase_lower for name in competitor_names)


def _get_word_count_override(brand_config: dict[str, Any]) -> int | None:
    """Extract max_word_count from brand_config.content_limits if set.

    Returns None if not configured (POP data drives the target).
    """
    limits = brand_config.get("content_limits")
    if isinstance(limits, dict):
        val = limits.get("max_word_count")
        if isinstance(val, (int, float)) and val > 0:
            return int(val)
    return None


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


def build_blog_content_prompt(
    blog_post: BlogPost,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None = None,
    trend_context: dict[str, Any] | None = None,
) -> PromptPair:
    """Build system and user prompts for blog post content generation.

    Similar to build_content_prompt() but outputs 3 fields (page_title,
    meta_description, content) instead of 4. The content field is a single
    HTML article with Introduction, Body H2 sections, FAQ, and Conclusion.

    Args:
        blog_post: The BlogPost to generate content for.
        keyword: Primary target keyword for the post.
        brand_config: The BrandConfig.v2_schema dict (contains ai_prompt_snippet,
            vocabulary, etc.).
        content_brief: Optional ContentBrief with LSI terms and word count targets.
        trend_context: Optional dict with trend research data from Perplexity.

    Returns:
        PromptPair with system_prompt and user_prompt ready for Claude.
    """
    system_prompt = _build_system_prompt(brand_config, content_type="blog")
    user_prompt = _build_blog_user_prompt(
        blog_post, keyword, brand_config, content_brief, trend_context=trend_context,
    )
    return PromptPair(system_prompt=system_prompt, user_prompt=user_prompt)


def _build_system_prompt(brand_config: dict[str, Any], content_type: str = "collection") -> str:
    """Build the system prompt using ai_prompt_snippet from brand config.

    Includes copywriting craft guidelines, AI trope avoidance rules, and
    formatting standards from the skill bible.

    Args:
        brand_config: The BrandConfig.v2_schema dict.
        content_type: "collection" or "blog" to adjust the role description.

    Returns:
        System prompt string.
    """
    ai_snippet = brand_config.get("ai_prompt_snippet", {})
    full_prompt = ""
    if isinstance(ai_snippet, dict):
        full_prompt = ai_snippet.get("full_prompt", "")

    if content_type == "blog":
        # Extract brand identity for the role description
        brand_foundation = brand_config.get("brand_foundation", {})
        company_overview = brand_foundation.get("company_overview", {}) if isinstance(brand_foundation, dict) else {}
        company_name = company_overview.get("company_name", "") if isinstance(company_overview, dict) else ""
        what_they_sell = brand_foundation.get("what_they_sell", {}) if isinstance(brand_foundation, dict) else {}
        primary_products = what_they_sell.get("primary_products_services", "") if isinstance(what_they_sell, dict) else ""

        if company_name and primary_products:
            role_desc = (
                f"You are an expert SEO blog writer for {company_name}, a brand that specializes in {primary_products}. "
                f"You write compelling, search-optimized blog posts that position {company_name} as a trusted authority. "
                "Every article should naturally connect the topic back to the brand's expertise and product offerings."
            )
        elif company_name:
            role_desc = (
                f"You are an expert SEO blog writer for {company_name}. "
                f"You write compelling, search-optimized blog posts that position {company_name} as a trusted authority. "
                "Every article should naturally connect the topic back to the brand's expertise and product offerings."
            )
        else:
            role_desc = (
                "You are an expert SEO blog writer generating long-form article content. "
                "You write compelling, search-optimized blog posts that drive organic traffic, "
                "establish topical authority, and engage readers."
            )
    else:
        role_desc = (
            "You are an expert e-commerce SEO copywriter generating collection page content. "
            "You write compelling, search-optimized content that drives organic traffic "
            "and converts visitors into customers."
        )

    parts = [
        role_desc,
        "",
        "## Writing Rules",
        "- Benefits over features (apply the \"So What?\" test)",
        "- Be specific, not vague (\"Ships in 2-3 days\" not \"Fast shipping\")",
        "- One idea per sentence",
        "- Write like you talk — read it aloud, if it sounds stiff, rewrite",
        "- Every word earns its place — cut filler ruthlessly",
        "- Use \"you\" and \"your\" — make it about the reader",
        "- Use contractions (you'll, we're, don't)",
        "- Active voice, not passive",
        "- Show, don't tell (\"Double-stitched seams\" not \"High quality\")",
        "",
        "## AI Writing Avoidance (Critical)",
        "NEVER use these words: delve, unlock, unleash, harness, leverage, embark, "
        "navigate, landscape, realm, game-changer, revolutionary, transformative, "
        "cutting-edge, groundbreaking, unprecedented, crucial, essential, vital, pivotal",
        "",
        "Limit to MAX 1 per piece: indeed, furthermore, moreover, robust, seamless, "
        "comprehensive, streamline, enhance, optimize, elevate, curated, tailored, bespoke",
        "",
        "NEVER use these phrases: \"In today's...\", \"Whether you're...\", "
        "\"It's no secret...\", \"When it comes to...\", \"In order to...\", "
        "\"It's important to note...\", \"At the end of the day...\"",
        "",
        "Avoid these patterns:",
        "- \"It's not just X, it's Y\" (max 1 per piece)",
        "- Triplet lists: \"X, Y, and Z\" — max 2 per piece. Vary your list structures: "
        "use pairs, use \"including\", use \"such as\", or restructure as separate sentences",
        "- Three parallel items in a row (\"Fast. Simple. Powerful.\")",
        "- Rhetorical question then answer (\"The result? ...\")",
        "- Em dashes (—) — use commas or periods instead",
        "",
        "## Formatting",
        "- NO em dashes (—)",
        "- Headers: Title Case, max 7 words",
        "- Paragraphs: 2-4 sentences max",
        "- Bold key phrases (not keywords)",
    ]

    if full_prompt:
        parts.append("")
        parts.append(f"## Brand Guidelines\n{full_prompt}")

    return "\n".join(parts)


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
    sections.append(_build_seo_targets_section(keyword, content_brief, brand_config))

    # ## Brand Voice
    brand_voice = _build_brand_voice_section(brand_config)
    if brand_voice:
        sections.append(brand_voice)

    # ## Output Format
    sections.append(_build_output_format_section(content_brief, brand_config))

    return "\n\n".join(sections)


def _build_blog_user_prompt(
    blog_post: BlogPost,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None,
    trend_context: dict[str, Any] | None = None,
) -> str:
    """Build the user prompt for blog post content generation.

    Args:
        blog_post: The BlogPost to generate content for.
        keyword: Primary target keyword.
        brand_config: The BrandConfig.v2_schema dict.
        content_brief: Optional ContentBrief with LSI terms and word count targets.
        trend_context: Optional dict with trend research data from Perplexity.

    Returns:
        User prompt string with ## Task, ## Blog Context, ## SEO Targets,
        ## Freshness, ## Entity Association, ## Brand Voice, and ## Output Format sections.
    """
    sections: list[str] = []

    # ## Task
    sections.append(
        f"## Task\n"
        f"Generate an SEO-optimized blog article targeting the keyword "
        f'"{keyword}". Produce all 3 content fields in a single JSON response.'
    )

    # ## Blog Context
    sections.append(_build_blog_context_section(blog_post))

    # ## SEO Targets (reuse existing function)
    sections.append(_build_seo_targets_section(keyword, content_brief, brand_config))

    # ## Recent Trends & Data (from Perplexity)
    freshness = _build_freshness_section(trend_context)
    if freshness:
        sections.append(freshness)

    # ## Entity Association (brand entity signals for AI visibility)
    entity = _build_entity_association_section(brand_config)
    if entity:
        sections.append(entity)

    # ## Brand Voice
    brand_voice = _build_brand_voice_section(brand_config)
    if brand_voice:
        sections.append(brand_voice)

    # ## Output Format (blog-specific: 3 fields, content-type-adapted)
    sections.append(_build_blog_output_format_section(content_brief, keyword=keyword))

    return "\n\n".join(sections)


def _build_blog_context_section(blog_post: BlogPost) -> str:
    """Build the ## Blog Context section with keyword, slug, and search volume."""
    lines = ["## Blog Context"]
    lines.append(f"- **Primary Keyword:** {blog_post.primary_keyword}")
    lines.append(f"- **URL Slug:** {blog_post.url_slug}")
    if blog_post.search_volume is not None:
        lines.append(f"- **Search Volume:** {blog_post.search_volume:,}/mo")
    return "\n".join(lines)


def _build_freshness_section(trend_context: dict[str, Any] | None) -> str | None:
    """Build the ## Recent Trends & Data section from Perplexity research.

    Returns None if no trend context is available.
    """
    if not trend_context:
        return None

    trends_text = trend_context.get("trends", "")
    if not trends_text:
        return None

    current_year = datetime.now(UTC).year
    lines = [
        "## Recent Trends & Data",
        "Incorporate these recent findings naturally into the article where relevant:",
        trends_text,
        "",
        f"Include the current year ({current_year}) in at least one section where "
        "appropriate. Reference specific recent data points rather than vague claims.",
    ]

    citations = trend_context.get("citations", [])
    if citations:
        lines.append("")
        lines.append("Source URLs for reference (cite where appropriate):")
        for url in citations[:5]:
            lines.append(f"  - {url}")

    return "\n".join(lines)


def _build_entity_association_section(brand_config: dict[str, Any]) -> str | None:
    """Build the ## Brand Positioning section for blog content.

    Extracts company name, primary products, and location from brand config
    to ensure blog content is written from the brand's perspective and
    positions their products/services as relevant solutions.

    Returns None if no brand foundation data is available.
    """
    brand_foundation = brand_config.get("brand_foundation")
    if not isinstance(brand_foundation, dict):
        return None

    company_name = None
    company_overview = brand_foundation.get("company_overview")
    if isinstance(company_overview, dict):
        company_name = company_overview.get("company_name")

    primary_products = None
    what_they_sell = brand_foundation.get("what_they_sell")
    if isinstance(what_they_sell, dict):
        primary_products = what_they_sell.get("primary_products_services")

    location = None
    if isinstance(company_overview, dict):
        location = company_overview.get("location")

    if not company_name:
        return None

    lines = ["## Brand Positioning (Critical)"]
    lines.append(
        f"You are writing this article on behalf of **{company_name}**."
    )

    if primary_products:
        lines.append(
            f"{company_name} specializes in **{primary_products}**."
        )

    if location:
        lines.append(f"Based in {location}.")

    lines.append("")
    lines.append("**How to integrate the brand:**")
    lines.append(
        f"- The article should be written from {company_name}'s perspective as a knowledgeable authority"
    )
    lines.append(
        f"- Naturally connect the topic to {company_name}'s products/expertise where relevant"
    )
    if primary_products:
        lines.append(
            f"- When discussing solutions, remedies, or recommendations, feature {company_name}'s "
            f"offerings ({primary_products}) as a primary option — not just one of many"
        )
    lines.append(
        "- The tone should feel like expert advice from a brand that lives and breathes this space, "
        "not a generic Wikipedia article"
    )
    lines.append(
        "- Value first — educate the reader genuinely, but let the brand's expertise and "
        "perspective come through naturally"
    )

    return "\n".join(lines)


def _detect_content_type(keyword: str) -> str:
    """Detect the content type from keyword patterns.

    Returns one of: "how-to", "comparison", "explainer", "guide", "review".
    """
    kw_lower = keyword.lower()

    if re.search(r"\bhow\s+(?:to|do)\b", kw_lower):
        return "how-to"
    if re.search(r"\b(?:best|top|vs|versus|comparison|compared)\b", kw_lower):
        return "comparison"
    if re.search(r"\b(?:what\s+is|what\s+are|definition|meaning)\b", kw_lower):
        return "explainer"
    if re.search(r"\b(?:review|worth\s+it)\b", kw_lower):
        return "review"
    if re.search(r"\b(?:guide|tutorial|step\s+by\s+step)\b", kw_lower):
        return "guide"

    return "guide"


def _build_blog_output_format_section(
    content_brief: ContentBrief | None = None,
    keyword: str = "",
) -> str:
    """Build the ## Output Format section for blog posts (3-field JSON).

    Specifies page_title, meta_description, and content (full article HTML).
    The content field includes Introduction, Body H2 sections, FAQ section
    from POP related_questions, and Conclusion with CTA.

    Adapts article structure based on detected content type from the keyword.
    """
    # Determine FAQ questions from content brief
    faq_questions: list[str] = []
    if content_brief is not None:
        faq_questions = content_brief.related_questions or []

    # Detect content type for structure adaptation
    content_type = _detect_content_type(keyword) if keyword else "guide"

    lines = [
        "## Output Format",
        "Respond with ONLY a valid JSON object (no markdown fencing, no extra text) "
        "containing exactly these 3 keys:",
        "",
        "```",
        "{",
        '  "page_title": "...",',
        '  "meta_description": "...",',
        '  "content": "..."',
        "}",
        "```",
        "",
        "**Field specifications:**",
        "- **page_title**: SEO-optimized, include primary keyword, under 60 chars. "
        "Title Case, benefit-driven.",
        "- **meta_description**: 150-160 chars, include primary keyword, optimized for "
        "click-through rate. Include a CTA.",
        "- **content** (full article HTML):",
        "",
        "  Structure the article as follows:",
        "",
        "  **1. Introduction**",
        "  - Open with a direct answer to the implied query in 1-2 sentences "
        "(this is what AI systems extract for citations)",
        "  - Then briefly state who this article is for",
        "  - Then bullet what the article covers",
        "  - 2-3 paragraphs max",
        "",
        "  **2. Body Sections**",
        "  - Use question-based H2 headings that match how people search "
        '(e.g., "How Do You Clean Leather Boots?" not "Cleaning Process")',
        "  - Start every H2 section with a direct answer in 1-2 sentences "
        "before supporting details (this makes content extractable by AI)",
        "  - Use H3 subheadings where appropriate",
        "  - 2-4 paragraphs per section, benefits-focused",
        "  - Address the reader directly with \"you\" and \"your\"",
        "",
    ]

    # Content-type-specific structure instructions
    if content_type == "how-to":
        lines.append("  **Content Type: How-To**")
        lines.append("  - Use numbered steps in body sections. Each step should be an H2.")
        lines.append("")
    elif content_type == "comparison":
        lines.append("  **Content Type: Comparison**")
        lines.append("  - Include a comparison table. Use objective criteria.")
        lines.append("  - Cover pros/cons for each option.")
        lines.append("")
    elif content_type == "explainer":
        lines.append("  **Content Type: Explainer**")
        lines.append("  - Define the core concept in the first paragraph.")
        lines.append("  - Build understanding progressively.")
        lines.append("")
    elif content_type == "review":
        lines.append("  **Content Type: Review**")
        lines.append("  - Include pros/cons section.")
        lines.append('  - End with clear recommendation and "who is this best for" section.')
        lines.append("")

    # FAQ section with specific questions from POP
    if faq_questions:
        lines.append("  **3. FAQ Section**")
        lines.append('  - Wrap in an H2 heading: "Frequently Asked Questions"')
        lines.append("  - Answer these questions (use H3 for each question):")
        for q in faq_questions[:8]:
            lines.append(f"    - {q}")
        lines.append("  - Keep answers concise: 2-3 sentences each")
        lines.append("")
    else:
        lines.append("  **3. FAQ Section**")
        lines.append('  - Wrap in an H2 heading: "Frequently Asked Questions"')
        lines.append("  - Include 3-5 relevant questions as H3 headings with concise answers")
        lines.append("")

    lines.extend([
        "  **4. Conclusion**",
        "  - Summarize key takeaways",
        "  - End with a clear call to action",
        "  - 1-2 paragraphs",
        "",
        "Use semantic HTML only (h2, h3, p, ul, ol, li, table, thead, tbody, tr, th, td tags). No inline styles. No div wrappers. No class attributes.",
    ])

    return "\n".join(lines)


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
    brand_config: dict[str, Any] | None = None,
) -> str:
    """Build the ## SEO Targets section from POP's cleanedContentBrief.

    Uses the per-location, per-term targets from POP directly rather than
    our own reconstructed version. Falls back to parsed ContentBrief fields
    if cleanedContentBrief is not available (e.g., mock mode).

    Filters out terms that match competitor brand names from vocabulary.competitors.
    Applies brand_config.content_limits.max_word_count cap when set.
    """
    # Load competitor names for filtering
    competitor_names: list[str] = []
    if brand_config:
        vocabulary = brand_config.get("vocabulary", {})
        if isinstance(vocabulary, dict):
            competitor_names = vocabulary.get("competitors", []) or []

    lines = ["## SEO Targets"]
    lines.append(f"- **Primary Keyword:** {keyword}")

    if content_brief is None:
        lines.append(
            "- **LSI Terms:** not available (generate naturally relevant content)"
        )
        return "\n".join(lines)

    raw = content_brief.raw_response or {}
    cb = raw.get("cleanedContentBrief")

    if isinstance(cb, dict) and cb:
        lines.extend(_build_from_cleaned_brief(cb, keyword, content_brief, raw, competitor_names))
    else:
        # Fallback: use parsed ContentBrief fields (mock mode)
        lines.extend(_build_from_parsed_brief(content_brief, competitor_names))

    return "\n".join(lines)


def _build_from_cleaned_brief(
    cb: dict[str, Any],
    keyword: str,
    content_brief: ContentBrief,
    raw: dict[str, Any],
    competitor_names: list[str] | None = None,
) -> list[str]:
    """Build SEO targets from POP's cleanedContentBrief data."""
    lines: list[str] = []
    _competitors = competitor_names or []

    # --- Title tag term targets ---
    title_terms = cb.get("title") or cb.get("pageTitle") or []
    if title_terms:
        lines.append("")
        lines.append("### Title Tag Targets")
        for item in title_terms:
            term = item.get("term", {})
            brief = item.get("contentBrief", {})
            phrase = term.get("phrase", "")
            if _competitors and is_competitor_term(phrase, _competitors):
                continue
            term_type = term.get("type", "")
            target = brief.get("target")
            t_min = brief.get("targetMin")
            t_max = brief.get("targetMax")
            count_str = _format_target_count(target, t_min, t_max)
            lines.append(f"  - \"{phrase}\" ({term_type}): {count_str}")
        title_total = cb.get("titleTotal") or cb.get("pageTitleTotal", {})
        if isinstance(title_total, dict) and title_total:
            lines.append(
                f"  - **Total term count:** {title_total.get('min', 0)}-{title_total.get('max', 0)}"
            )

    # --- Subheading term targets (use min to keep content lean) ---
    sub_terms = cb.get("subHeadings", [])
    if sub_terms:
        lines.append("")
        lines.append("### Subheading Targets (H2/H3)")
        for item in sub_terms:
            term = item.get("term", {})
            brief = item.get("contentBrief", {})
            phrase = term.get("phrase", "")
            if _competitors and is_competitor_term(phrase, _competitors):
                continue
            term_type = term.get("type", "")
            t_min = brief.get("targetMin")
            count_str = _format_min_target_count(t_min)
            lines.append(f"  - \"{phrase}\" ({term_type}): {count_str}")
        sub_total = cb.get("subHeadingsTotal", {})
        if isinstance(sub_total, dict) and sub_total:
            lines.append(
                f"  - **Total term count:** {sub_total.get('min', 0)}-{sub_total.get('max', 0)}"
            )

    # --- Paragraph text term targets (use min to keep content lean) ---
    p_terms = cb.get("p", [])
    if p_terms:
        lines.append("")
        lines.append("### Paragraph Text Targets")
        for item in p_terms:
            term = item.get("term", {})
            brief = item.get("contentBrief", {})
            phrase = term.get("phrase", "")
            if _competitors and is_competitor_term(phrase, _competitors):
                continue
            term_type = term.get("type", "")
            t_min = brief.get("targetMin")
            count_str = _format_min_target_count(t_min)
            lines.append(f"  - \"{phrase}\" ({term_type}): {count_str}")
        p_total = cb.get("pTotal", {})
        if isinstance(p_total, dict) and p_total:
            lines.append(
                f"  - **Total term count:** {p_total.get('min', 0)}-{p_total.get('max', 0)}"
            )

    # --- Heading structure (from pageStructure recs) ---
    heading_targets: list[dict[str, Any]] = content_brief.heading_targets or []
    heading_items = [
        h for h in heading_targets
        if h.get("tag", "").lower().startswith("h") and "tag total" in h.get("tag", "").lower()
    ]
    if heading_items:
        lines.append("")
        lines.append("### Heading Structure")
        for h in heading_items:
            tag = h.get("tag", "")
            target = h.get("target", 0)
            h_min = h.get("min")
            h_max = h.get("max")
            if h_min is not None and h_max is not None:
                lines.append(f"  - {tag}: {target} (range: {h_min}-{h_max})")
            else:
                lines.append(f"  - {tag}: {target}")

    # --- Exact keyword placement ---
    keyword_targets: list[dict[str, Any]] = content_brief.keyword_targets or []
    exact_targets = [t for t in keyword_targets if t.get("type") == "exact"]
    if exact_targets:
        lines.append("")
        lines.append("### Exact Keyword Placement")
        for t in exact_targets:
            signal = t.get("signal", "")
            target = t.get("target", "")
            comment = t.get("comment", "")
            if comment:
                lines.append(f"  - {signal}: {comment}")
            elif target:
                lines.append(f"  - {signal}: {target} time(s)")

    # --- Related questions ---
    related_questions: list[str] = content_brief.related_questions or []
    if related_questions:
        lines.append("")
        lines.append("### Related Questions (use for FAQ section)")
        for q in related_questions[:8]:
            lines.append(f"  - {q}")

    # --- Related searches ---
    related_searches = raw.get("relatedSearches", [])
    if related_searches:
        lines.append("")
        lines.append("### Related Searches")
        for s in related_searches:
            if isinstance(s, dict):
                lines.append(f"  - {s.get('query', '')}")
            elif isinstance(s, str):
                lines.append(f"  - {s}")

    # --- Keyword variations ---
    variations: list[str] = content_brief.related_searches or []
    if variations:
        lines.append("")
        lines.append("### Keyword Variations")
        lines.append(f"{', '.join(variations)}")

    # --- Competitor context ---
    competitors: list[dict[str, Any]] = content_brief.competitors or []
    if competitors:
        avg_score = sum(c.get("pageScore") or 0 for c in competitors) / len(competitors)
        lines.append(
            f"- **Competitor Context:** {len(competitors)} competitors analyzed"
            + (f" (avg score: {avg_score:.0f})" if avg_score else "")
        )

    return lines


def _build_from_parsed_brief(
    content_brief: ContentBrief,
    competitor_names: list[str] | None = None,
) -> list[str]:
    """Fallback: build SEO targets from parsed ContentBrief fields (mock mode)."""
    lines: list[str] = []
    _competitors = competitor_names or []

    lsi_terms: list[dict[str, Any]] = content_brief.lsi_terms or []
    if lsi_terms:
        lines.append("- **LSI Terms:**")
        for term in lsi_terms:
            phrase = term.get("phrase", "")
            if _competitors and is_competitor_term(phrase, _competitors):
                continue
            weight = term.get("weight", 0)
            avg_count = term.get("averageCount", 0)
            lines.append(
                f"  - {phrase} (weight: {weight}, target count: {avg_count})"
            )

    variations: list[str] = content_brief.related_searches or []
    if variations:
        lines.append(f"- **Keyword Variations:** {', '.join(variations)}")

    related_questions: list[str] = content_brief.related_questions or []
    if related_questions:
        lines.append("- **Related Questions (use for FAQ section):**")
        for q in related_questions[:8]:
            lines.append(f"  - {q}")

    return lines


def _format_target_count(
    target: int | None,
    target_min: int | None,
    target_max: int | None,
) -> str:
    """Format a term target count as a readable string."""
    if target is not None:
        return f"{target} time(s)"
    if target_min is not None and target_max is not None:
        if target_min == target_max:
            return f"{target_min} time(s)"
        return f"{target_min}-{target_max} times"
    return "include naturally"


def _format_min_target_count(target_min: int | None) -> str:
    """Format a term target using the minimum count with a floor of 1.

    Used for subheading and paragraph targets where we want the leaner end
    of the range to avoid verbose content stuffing.
    """
    count = max(1, target_min or 0)
    if count == 1:
        return "at least 1 time"
    return f"at least {count} times"


def _build_brand_voice_section(brand_config: dict[str, Any]) -> str | None:
    """Build the ## Brand Voice section with banned words and competitor exclusions.

    The full brand guidelines (ai_prompt_snippet) are already included in the
    system prompt, so we only add vocabulary constraints here to avoid duplication.

    Returns None if no banned words or competitor names are configured.
    """
    vocabulary = brand_config.get("vocabulary", {})
    if not isinstance(vocabulary, dict):
        return None

    parts: list[str] = []

    banned_words: list[str] = vocabulary.get("banned_words", [])
    if banned_words:
        parts.append(f"**Banned Words:** {', '.join(banned_words)}")

    competitors: list[str] = vocabulary.get("competitors", [])
    if competitors:
        parts.append(
            f"**Competitor Brands (never mention):** {', '.join(competitors)}"
        )

    if not parts:
        return None

    return "## Brand Voice\n" + "\n".join(parts)


def _build_output_format_section(
    content_brief: ContentBrief | None = None,
    brand_config: dict[str, Any] | None = None,
) -> str:
    """Build the ## Output Format section specifying JSON structure.

    Dynamically builds the bottom_description template from POP heading data
    when a ContentBrief is available. Falls back to a sensible default template.

    Args:
        content_brief: Optional ContentBrief with heading_targets and word count.
        brand_config: Optional brand config with content_limits override.
    """
    # --- Static parts (always included) ---
    lines = [
        "## Output Format",
        "Respond with ONLY a valid JSON object (no markdown fencing, no extra text) "
        "containing exactly these 4 keys:",
        "",
        "```",
        "{",
        '  "page_title": "...",',
        '  "meta_description": "...",',
        '  "top_description": "...",',
        '  "bottom_description": "..."',
        "}",
        "```",
        "",
        "**Field specifications:**",
        "- **page_title**: Title Case, 5-10 words, include primary keyword, under 60 chars, benefit-driven.",
        "- **meta_description**: 150-160 chars, include primary keyword, include a CTA. Optimized for click-through rate.",
        "- **top_description**: Plain text, 1-2 sentences. No HTML. Hook the reader, set expectations.",
    ]

    # --- Dynamic bottom_description template ---
    lines.append(_build_bottom_description_spec(content_brief, brand_config))

    # --- Shared formatting rules ---
    lines.append("")
    lines.append("Use semantic HTML only (h2, h3, p tags). No inline styles. No div wrappers. No class attributes.")

    return "\n".join(lines)


def _build_bottom_description_spec(
    content_brief: ContentBrief | None,
    brand_config: dict[str, Any] | None = None,  # noqa: ARG001
) -> str:
    """Build the bottom_description field spec from POP heading data.

    Uses the *minimum* heading counts from POP (capped at reasonable maxima)
    so the content stays lean. Word count is intentionally omitted — content
    length should be a natural consequence of the heading structure and term
    targets, not an arbitrary number driven by SERP competitors.
    """
    # Reasonable caps to prevent bloated pages
    H2_CAP = 8
    H3_CAP = 12

    # Defaults when no brief available
    h2_count = 3
    h3_count = 4

    if content_brief is not None:
        heading_targets = content_brief.heading_targets or []
        for h in heading_targets:
            tag = (h.get("tag") or "").lower()
            if "h2 tag total" in tag:
                # Use min of range, floor of 1, capped
                h2_count = min(max(1, h.get("min", 3)), H2_CAP)
            elif "h3 tag total" in tag:
                h3_count = min(max(1, h.get("min", 4)), H3_CAP)

    lines = [
        "- **bottom_description** (HTML)",
        "",
        "  Structure your content with approximately:",
        f"  - {h2_count} H2 sections",
        f"  - {h3_count} H3 subsections distributed across H2 sections",
        "",
        "  Follow this pattern:",
        "",
        "  <h2>[Section Topic, Title Case, Max 7 Words]</h2>",
        "  <p>[Benefits-focused. Address the reader directly. 120 words max.]</p>",
        "",
        "  <h3>[Subtopic, Title Case, Max 7 Words]</h3>",
        "  <p>[Specific details and differentiators. 120 words max.]</p>",
        "",
        "  ...repeat pattern for all sections...",
        "",
        "  End with a clear call to action in the final paragraph.",
        "  Brevity is valued. Not every paragraph needs the full 120 words.",
        "  Write just enough to cover each topic and incorporate the target terms.",
    ]

    return "\n".join(lines)


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

    # Mark as writing — commit so the polling endpoint sees this status
    page_content.status = ContentStatus.WRITING.value
    page_content.generation_started_at = datetime.now(UTC)
    await db.commit()

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

    # Call Claude Sonnet — explicit api_key for background task context
    client = ClaudeClient(
        api_key=get_api_key(),
        model=CONTENT_WRITING_MODEL,
        max_tokens=CONTENT_WRITING_MAX_TOKENS,
        timeout=CONTENT_WRITING_TIMEOUT,
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
        api_key=get_api_key(),
        model=CONTENT_WRITING_MODEL,
        max_tokens=CONTENT_WRITING_MAX_TOKENS,
        timeout=CONTENT_WRITING_TIMEOUT,
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

    Handles markdown code fences, control characters, and common JSON issues.
    Returns None if invalid.
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

    # Attempt 1: direct parse
    parsed = _try_json_loads(cleaned)

    # Attempt 2: fix control characters inside JSON string values
    if parsed is None:
        repaired = _repair_json_control_chars(cleaned)
        parsed = _try_json_loads(repaired)

    # Attempt 3: extract each key's value using regex boundaries
    if parsed is None:
        parsed = _extract_json_keys_fallback(cleaned, REQUIRED_CONTENT_KEYS)

    if parsed is None:
        snippet = cleaned[:300] if len(cleaned) > 300 else cleaned
        logger.warning(
            "All JSON parse strategies failed for collection content",
            extra={"snippet": snippet, "length": len(cleaned)},
        )
        return None

    if not isinstance(parsed, dict):
        return None

    # Validate required keys exist
    if not REQUIRED_CONTENT_KEYS.issubset(parsed.keys()):
        return None

    return {k: str(v) for k, v in parsed.items() if k in REQUIRED_CONTENT_KEYS}


def _try_json_loads(text: str) -> dict[str, Any] | None:
    """Try json.loads, return None on failure."""
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _repair_json_control_chars(text: str) -> str:
    """Repair common JSON issues: unescaped control characters in string values."""

    def _escape_string_value(m: re.Match[str]) -> str:
        val: str = m.group(0)
        val = val.replace("\t", "\\t")
        val = val.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
        return val

    return re.sub(r'"(?:[^"\\]|\\.)*"', _escape_string_value, text)


def _extract_json_keys_fallback(text: str, required_keys: set[str]) -> dict[str, str] | None:
    """Last-resort extraction: use key positions as boundaries to find values.

    Instead of scanning for individual closing quotes (which fails when HTML
    contains unescaped double quotes like class="..."), this finds all key
    positions and uses the gaps between them to determine value boundaries.
    """
    key_positions: list[tuple[str, int, int]] = []
    for key in required_keys:
        pattern = rf'"{key}"\s*:\s*"'
        match = re.search(pattern, text)
        if not match:
            return None
        key_positions.append((key, match.start(), match.end()))

    key_positions.sort(key=lambda x: x[1])

    result = {}
    for i, (key, _key_start, value_start) in enumerate(key_positions):
        if i + 1 < len(key_positions):
            next_key_start = key_positions[i + 1][1]
            region = text[value_start:next_key_start]
            last_quote = region.rfind('"')
            if last_quote <= 0:
                return None
            value = region[:last_quote]
        else:
            remaining = text[value_start:]
            last_close = remaining.rfind('"}')
            if last_close == -1:
                last_brace = remaining.rfind('}')
                if last_brace == -1:
                    return None
                last_close = remaining.rfind('"', 0, last_brace)
                if last_close == -1:
                    return None
            value = remaining[:last_close]

        value = (
            value.replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )
        result[key] = value

    return result


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
    """Update prompt log records with Claude's response metadata.

    Only the user log gets the response_text — there's a single Claude call
    for the system+user prompt pair, so showing the response on both entries
    is redundant.
    """
    response_text = result.text or result.error or ""

    # System log: metadata only, no response text (avoids duplication in inspector)
    system_log.model = CONTENT_WRITING_MODEL
    system_log.input_tokens = result.input_tokens
    system_log.output_tokens = result.output_tokens
    system_log.duration_ms = duration_ms

    # User log: includes the actual response
    user_log.response_text = response_text
    user_log.model = CONTENT_WRITING_MODEL
    user_log.input_tokens = result.input_tokens
    user_log.output_tokens = result.output_tokens
    user_log.duration_ms = duration_ms


def _mark_failed(page_content: PageContent, error: str) -> ContentWritingResult:
    """Mark PageContent as failed and return a failure result."""
    page_content.status = ContentStatus.FAILED.value
    page_content.generation_completed_at = datetime.now(UTC)
    page_content.qa_results = {"error": error}
    logger.error("Content generation failed", extra={"error": error, "page_content_id": page_content.id})
    return ContentWritingResult(success=False, page_content=page_content, error=error)
