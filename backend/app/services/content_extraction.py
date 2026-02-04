"""Content extraction utilities for crawled HTML pages.

Uses BeautifulSoup to extract structured content from HTML:
- Title from <title> tag
- Meta description from <meta name="description">
- Headings as {h1: [...], h2: [...], h3: [...]}
- Body content truncation to 50KB limit
"""

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

# Maximum body content size in bytes (50KB)
MAX_BODY_CONTENT_BYTES = 50 * 1024


@dataclass
class ExtractedContent:
    """Container for extracted HTML content."""

    title: str | None = None
    meta_description: str | None = None
    headings: dict[str, list[str]] = field(default_factory=lambda: {"h1": [], "h2": [], "h3": []})
    body_content: str | None = None
    word_count: int = 0


def extract_content_from_html(html: str | None, markdown: str | None = None) -> ExtractedContent:
    """Extract structured content from HTML using BeautifulSoup.

    Args:
        html: Raw HTML content from crawler.
        markdown: Markdown content from crawler (used for body_content).

    Returns:
        ExtractedContent with title, meta_description, headings, body_content, word_count.
    """
    result = ExtractedContent()

    # Set body content from markdown (with truncation)
    if markdown:
        result.body_content = truncate_body_content(markdown)
        result.word_count = len(markdown.split())

    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")

    # Extract title from <title> tag
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        result.title = title_tag.string.strip()

    # Extract meta description from <meta name="description">
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        result.meta_description = str(meta_desc.get("content")).strip()

    # Extract headings (h1, h2, h3)
    for level in ["h1", "h2", "h3"]:
        headings = soup.find_all(level)
        result.headings[level] = [
            h.get_text(strip=True) for h in headings if h.get_text(strip=True)
        ]

    return result


def truncate_body_content(content: str) -> str:
    """Truncate body content to 50KB if larger.

    Truncates at a word boundary to avoid cutting mid-word.

    Args:
        content: Text content to potentially truncate.

    Returns:
        Truncated content if larger than 50KB, otherwise original content.
    """
    content_bytes = content.encode("utf-8")

    if len(content_bytes) <= MAX_BODY_CONTENT_BYTES:
        return content

    # Truncate at byte boundary first
    truncated_bytes = content_bytes[:MAX_BODY_CONTENT_BYTES]

    # Decode with error handling for partial multi-byte chars
    truncated = truncated_bytes.decode("utf-8", errors="ignore")

    # Find last complete word (space boundary)
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated + "..."
