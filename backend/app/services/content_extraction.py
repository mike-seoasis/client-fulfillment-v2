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

from bs4 import BeautifulSoup

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


def extract_content_from_html(
    html: str | None, markdown: str | None = None
) -> ExtractedContent:
    """Extract structured content from HTML using BeautifulSoup.

    Args:
        html: Raw HTML content from crawler.
        markdown: Markdown content from crawler (used for body_content).

    Returns:
        ExtractedContent with title, meta_description, headings, body_content, word_count, product_count.
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

    # Extract product count for Shopify collection pages
    result.product_count = extract_shopify_product_count(soup, html)

    return result


def extract_shopify_product_count(soup: BeautifulSoup, html: str) -> int | None:
    """Extract product count from Shopify collection pages.

    Attempts to find product count in this order:
    1. Parse Shopify collection JSON data (window.ShopifyAnalytics or meta.page.resourceId)
    2. Count product card elements with common Shopify class names

    Args:
        soup: BeautifulSoup parsed HTML.
        html: Raw HTML string for regex-based JSON extraction.

    Returns:
        Product count as integer, or None if not detectable (non-collection page).
    """
    # Strategy 1: Look for Shopify collection JSON in script tags
    # Try to find collection product count in various Shopify JSON structures
    product_count = _extract_product_count_from_json(html)
    if product_count is not None:
        return product_count

    # Strategy 2: Fall back to counting product card elements
    product_count = _count_product_card_elements(soup)
    if product_count is not None:
        return product_count

    # Return None for non-collection pages
    return None


def _extract_product_count_from_json(html: str) -> int | None:
    """Extract product count from Shopify JSON embedded in the page.

    Looks for common Shopify patterns:
    - ShopifyAnalytics.meta.page.resourceId (collection page indicator)
    - collection.products_count in page data
    - products array length in collection JSON

    Args:
        html: Raw HTML string.

    Returns:
        Product count or None if not found.
    """
    # Pattern 1: Look for ShopifyAnalytics.meta with products_count
    # Format: ShopifyAnalytics.meta = {"page":{"pageType":"collection",...}}
    shopify_analytics_pattern = r"ShopifyAnalytics\.meta\s*=\s*(\{[^;]+\})"
    match = re.search(shopify_analytics_pattern, html)
    if match:
        try:
            data = json.loads(match.group(1))
            # Check if this is a collection page with products_count
            page_data = data.get("page", {})
            if (
                page_data.get("pageType") == "collection"
                and "products_count" in page_data
            ):
                return int(page_data["products_count"])
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass

    # Pattern 2: Look for collection JSON data with products_count
    # Format: "products_count":123 or "productsCount":123
    products_count_pattern = r'"products_count"\s*:\s*(\d+)'
    match = re.search(products_count_pattern, html)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    # Pattern 3: Alternative camelCase format
    products_count_camel_pattern = r'"productsCount"\s*:\s*(\d+)'
    match = re.search(products_count_camel_pattern, html)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    # Pattern 4: Look for collection data in window.__INITIAL_STATE__ or similar
    # Some themes embed products array in a JSON block
    initial_state_pattern = r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\});"
    match = re.search(initial_state_pattern, html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            # Look for products array in various locations
            products = data.get("collection", {}).get("products", []) or data.get(
                "products", []
            )
            if products:
                return len(products)
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            pass

    return None


def _count_product_card_elements(soup: BeautifulSoup) -> int | None:
    """Count product card elements using common Shopify class names.

    Looks for elements with common Shopify product card class patterns:
    - product-card, product-item, product-grid-item
    - card--product, grid__item--product
    - ProductItem, ProductCard

    Args:
        soup: BeautifulSoup parsed HTML.

    Returns:
        Product count if cards found, None otherwise.
    """
    # Common Shopify product card class patterns (case-insensitive regex)
    product_class_patterns = [
        re.compile(r"product-card", re.I),
        re.compile(r"product-item", re.I),
        re.compile(r"product-grid-item", re.I),
        re.compile(r"card--product", re.I),
        re.compile(r"grid__item.*product", re.I),
        re.compile(r"ProductItem", re.I),
        re.compile(r"ProductCard", re.I),
        re.compile(r"collection-product", re.I),
    ]

    for pattern in product_class_patterns:
        products = soup.find_all(class_=pattern)
        if products:
            return len(products)

    # Try data attribute selectors
    products = soup.find_all(attrs={"data-product-card": True})
    if products:
        return len(products)

    products = soup.find_all(attrs={"data-product-id": True})
    if products:
        return len(products)

    # Also try article elements with product type (common in some themes)
    article_products = soup.find_all("article", {"data-product": True})
    if article_products:
        return len(article_products)

    # Try finding elements with product-form inside (each product usually has one)
    product_forms = soup.find_all("form", {"action": re.compile(r"/cart/add")})
    if product_forms:
        return len(product_forms)

    return None


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
