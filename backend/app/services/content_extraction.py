"""Content extraction utilities for crawled HTML pages.

Uses BeautifulSoup to extract structured content from HTML:
- Title from <title> tag
- Meta description from <meta name="description">
- Headings as {h1: [...], h2: [...], h3: [...]}
- Body content truncation to 50KB limit
- Product count for Shopify collection pages
"""

import json
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

# Maximum body content size in bytes (50KB)
MAX_BODY_CONTENT_BYTES = 50 * 1024


@dataclass
class ExtractedContent:
    """Container for extracted HTML content."""

    title: str | None = None
    meta_description: str | None = None
    headings: dict[str, list[str]] = field(
        default_factory=lambda: {"h1": [], "h2": [], "h3": []}
    )
    body_content: str | None = None
    word_count: int = 0
    product_count: int | None = None
    product_names: list[str] = field(default_factory=list)  # For label generation


# Elements to remove when extracting main content (boilerplate)
BOILERPLATE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "header",
    "nav",
    "footer",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".header",
    ".nav",
    ".navigation",
    ".footer",
    ".site-header",
    ".site-footer",
    ".cart-drawer",
    ".cart-notification",
    ".announcement-bar",
    ".cookie-banner",
    ".popup",
    ".modal",
    "#shopify-section-header",
    "#shopify-section-footer",
    "#shopify-section-announcement-bar",
]


def _extract_main_content(
    html: str | None,
    cleaned_html: str | None,
    markdown: str | None,
) -> str | None:
    """Extract main content text, stripping navigation/footer boilerplate.

    Args:
        html: Raw HTML content.
        cleaned_html: Pre-cleaned HTML from crawler.
        markdown: Markdown content from crawler.

    Returns:
        Main content text with boilerplate removed, or None if no content.
    """
    # Prefer markdown if available (usually already cleaned)
    if markdown and isinstance(markdown, str):
        return markdown.strip()

    # Use cleaned_html if available
    source_html = (
        cleaned_html if cleaned_html and isinstance(cleaned_html, str) else html
    )
    if not source_html or not isinstance(source_html, str):
        return None

    soup = BeautifulSoup(source_html, "html.parser")

    # Remove boilerplate elements
    for selector in BOILERPLATE_SELECTORS:
        try:
            for element in soup.select(selector):
                element.decompose()
        except Exception:
            # Some selectors might fail, continue with others
            pass

    # Try to find main content container
    main_content = (
        soup.find("main")
        or soup.find(id="MainContent")
        or soup.find(id="main-content")
        or soup.find(class_="main-content")
        or soup.find(role="main")
    )

    if main_content:
        text = main_content.get_text(separator=" ", strip=True)
    else:
        # Fall back to body content
        text = soup.get_text(separator=" ", strip=True)

    # Clean up excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text if text else None


def extract_content_from_html(
    html: str | None,
    markdown: str | None = None,
    cleaned_html: str | None = None,
) -> ExtractedContent:
    """Extract structured content from HTML using BeautifulSoup.

    Args:
        html: Raw HTML content from crawler.
        markdown: Markdown content from crawler (used for body_content if available).
        cleaned_html: Cleaned HTML from crawler (used as fallback for body_content).

    Returns:
        ExtractedContent with title, meta_description, headings, body_content, word_count, product_count.
    """
    result = ExtractedContent()

    # Extract main content text, stripping boilerplate
    main_content = _extract_main_content(html, cleaned_html, markdown)
    if main_content:
        result.body_content = truncate_body_content(main_content)
        result.word_count = len(main_content.split())

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

    # Extract product count and names for Shopify collection pages
    product_count, product_names = extract_shopify_products(soup, html)
    result.product_count = product_count
    result.product_names = product_names

    return result


def extract_shopify_products(
    soup: BeautifulSoup, html: str
) -> tuple[int | None, list[str]]:
    """Extract product count and names from Shopify collection pages.

    Prioritizes counting visible product cards on the page (more accurate than
    store-wide JSON counts). Also extracts product names for label generation.

    Args:
        soup: BeautifulSoup parsed HTML.
        html: Raw HTML string for regex-based JSON extraction.

    Returns:
        Tuple of (product_count, product_names list).
    """
    # Strategy 1: Count and extract from visible product cards (most accurate)
    count, names = _extract_from_product_cards(soup)
    if count is not None and count > 0:
        return count, names

    # Strategy 2: Try to extract from Shopify JSON (for product names)
    json_names = _extract_product_names_from_json(html)
    if json_names:
        return len(json_names), json_names

    return None, []


def _extract_from_product_cards(soup: BeautifulSoup) -> tuple[int | None, list[str]]:
    """Extract product count and names from the main collection grid only.

    Excludes products in carousels, related products sections, and footer areas
    to get an accurate count of the primary collection products.

    Args:
        soup: BeautifulSoup parsed HTML.

    Returns:
        Tuple of (count, list of product names).
    """
    product_names: list[str] = []

    # First, try to find the main product grid container
    # This excludes carousels, related products, and footer sections
    main_grid_selectors = [
        "#product-grid",
        ".collection-product-list",
        ".product-grid",
        ".collection__products",
        "[data-collection-products]",
        "main .product-list",
        "#MainContent .product-grid",
    ]

    main_grid = None
    for selector in main_grid_selectors:
        try:
            main_grid = soup.select_one(selector)
            if main_grid:
                break
        except Exception:
            continue

    # Use main grid if found, otherwise fall back to full page but exclude known non-collection areas
    search_area = main_grid if main_grid else soup

    # If no main grid found, create a copy and remove non-collection sections
    if not main_grid:
        from copy import copy

        search_area = copy(soup)
        # Remove sections that typically contain non-collection products
        non_collection_selectors = [
            ".product-recommendations",
            ".related-products",
            ".recently-viewed",
            ".upsell",
            ".cross-sell",
            "[data-recommendations]",
            ".swiper",  # Carousels
            ".carousel",
            ".slider",
            "footer",
            ".footer",
        ]
        for selector in non_collection_selectors:
            try:
                for elem in search_area.select(selector):
                    elem.decompose()
            except Exception:
                continue

    # Common Shopify product card class patterns
    product_card_patterns = [
        re.compile(r"product-card", re.I),
        re.compile(r"product-item", re.I),
        re.compile(r"product-grid-item", re.I),
        re.compile(r"card--product", re.I),
        re.compile(r"ProductItem", re.I),
        re.compile(r"ProductCard", re.I),
        re.compile(r"collection-product", re.I),
    ]

    product_cards: list[Tag] = []
    for pattern in product_card_patterns:
        cards = search_area.find_all(class_=pattern)
        if cards:
            product_cards = cards
            break

    # Try data attribute selectors if class patterns didn't work
    if not product_cards:
        product_cards = search_area.find_all(attrs={"data-product-card": True})
    if not product_cards:
        product_cards = search_area.find_all(attrs={"data-product-id": True})
    if not product_cards:
        product_cards = search_area.find_all("article", {"data-product": True})

    if not product_cards:
        return None, []

    # Extract unique product names from cards
    for card in product_cards:
        name = _extract_product_name_from_card(card)
        if name and name not in product_names:
            product_names.append(name)

    # Return unique product count (based on names) rather than total cards
    # This handles cases where the same product appears multiple times
    unique_count = len(product_names) if product_names else len(product_cards)

    return unique_count, product_names


def _extract_product_name_from_card(card: Tag) -> str | None:
    """Extract product name from a product card element.

    Args:
        card: Tag element representing a product card.

    Returns:
        Product name or None if not found.
    """
    # Common patterns for product title elements
    title_selectors = [
        ".product-card__title",
        ".product-item__title",
        ".product-title",
        ".card__title",
        ".ProductItem__Title",
        "[data-product-title]",
        "h3",
        "h4",  # Fallback to heading tags
    ]

    for selector in title_selectors:
        try:
            title_elem = card.select_one(selector)
            if title_elem:
                text = str(title_elem.get_text(strip=True))
                if text and len(text) > 2:  # Filter out empty or very short
                    return text
        except Exception:
            continue

    # Last resort: look for any link with product in the href
    product_link = card.find("a", href=re.compile(r"/products/"))
    if product_link:
        text = str(product_link.get_text(strip=True))
        if text and len(text) > 2:
            return text

    return None


def _extract_product_names_from_json(html: str) -> list[str]:
    """Extract product names from Shopify JSON embedded in the page.

    Args:
        html: Raw HTML string.

    Returns:
        List of product names found in JSON data.
    """
    product_names: list[str] = []

    # Look for product JSON-LD data
    jsonld_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    for match in re.finditer(jsonld_pattern, html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(match.group(1))
            # Handle ItemList (collection pages)
            if data.get("@type") == "ItemList":
                for item in data.get("itemListElement", []):
                    name = item.get("item", {}).get("name") or item.get("name")
                    if name and name not in product_names:
                        product_names.append(name)
            # Handle single Product
            elif data.get("@type") == "Product":
                name = data.get("name")
                if name and name not in product_names:
                    product_names.append(name)
        except (json.JSONDecodeError, TypeError):
            continue

    # Look for product titles in common Shopify patterns
    # Pattern: "title":"Product Name" in product JSON
    title_pattern = r'"title"\s*:\s*"([^"]{3,100})"'
    for match in re.finditer(title_pattern, html):
        name = match.group(1)
        # Filter out common non-product titles
        if name and name not in product_names:
            lower_name = name.lower()
            if not any(
                skip in lower_name
                for skip in [
                    "shipping",
                    "cart",
                    "checkout",
                    "policy",
                    "subscribe",
                    "newsletter",
                    "cookie",
                    "privacy",
                    "terms",
                ]
            ):
                product_names.append(name)
        if len(product_names) >= 50:  # Limit to prevent huge lists
            break

    return product_names[:30]  # Return max 30 product names


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
