"""Blog HTML export service for generating clean HTML for Shopify blog editor.

BlogExportService generates clean HTML for blog posts by:
- Stripping editor artifacts (highlight spans, data attributes)
- Preserving internal links
- Ensuring proper heading hierarchy (H2/H3)
- Returning semantic HTML strings

This is HTML for pasting into Shopify's blog editor — NOT Matrixify CSV.
"""

import re

from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.blog import BlogPost, ContentStatus
from app.schemas.blog import BlogExportItem

logger = get_logger(__name__)

# Highlight CSS classes from the frontend Lexical HighlightPlugin.
# These are <span class="hl-*"> wrappers around text.
HIGHLIGHT_CLASSES = {"hl-keyword", "hl-keyword-var", "hl-lsi", "hl-trope"}


class BlogExportService:
    """Service for generating clean HTML exports of blog posts."""

    @staticmethod
    def generate_clean_html(blog_post: BlogPost) -> str:
        """Generate clean HTML from a blog post's content.

        Strips editor artifacts (highlight spans, data attributes), preserves
        internal links, and ensures proper heading hierarchy (H2/H3).

        Args:
            blog_post: BlogPost model instance with content populated.

        Returns:
            Cleaned semantic HTML string. Empty string if no content.
        """
        if not blog_post.content:
            return ""

        soup = BeautifulSoup(blog_post.content, "html.parser")

        # 1. Strip highlight spans — unwrap <span class="hl-*"> keeping children
        for span in soup.find_all("span"):
            raw_classes = span.get("class")
            if raw_classes is None:
                classes: list[str] = []
            elif isinstance(raw_classes, str):
                classes = raw_classes.split()
            else:
                classes = list(raw_classes)
            if any(cls in HIGHLIGHT_CLASSES for cls in classes):
                span.unwrap()

        # 2. Remove data-* attributes from all elements
        for tag in soup.find_all(True):
            attrs_to_remove = [attr for attr in tag.attrs if attr.startswith("data-")]
            for attr in attrs_to_remove:
                del tag[attr]

        # 3. Ensure heading hierarchy — demote any H1 to H2
        for h1 in soup.find_all("h1"):
            h1.name = "h2"

        # 4. Clean up empty spans left after unwrapping
        for span in soup.find_all("span"):
            # Remove spans with no meaningful attributes (class, style, id)
            if not span.get("class") and not span.get("style") and not span.get("id"):
                span.unwrap()

        # 5. Normalize whitespace in the output
        html = str(soup)
        # Collapse multiple blank lines into single blank line
        html = re.sub(r"\n{3,}", "\n\n", html)

        return html.strip()

    @staticmethod
    async def generate_export_package(
        campaign_id: str,
        db: AsyncSession,
        post_ids: list[str] | None = None,
    ) -> list[BlogExportItem]:
        """Generate an export package for approved blog posts.

        Queries posts with content_approved=True and content_status='complete',
        generates clean HTML + metadata for each.

        Args:
            campaign_id: UUID of the blog campaign.
            db: Async database session.
            post_ids: Optional list of specific post IDs to export.
                      If None, exports all approved+complete posts.

        Returns:
            List of BlogExportItem with clean HTML and metadata.
        """
        stmt = select(BlogPost).where(
            BlogPost.campaign_id == campaign_id,
            BlogPost.content_approved.is_(True),
            BlogPost.content_status == ContentStatus.COMPLETE.value,
        )

        if post_ids is not None:
            stmt = stmt.where(BlogPost.id.in_(post_ids))

        result = await db.execute(stmt)
        posts = result.scalars().all()

        items: list[BlogExportItem] = []
        for post in posts:
            clean_html = BlogExportService.generate_clean_html(post)
            word_count = _count_words(clean_html)

            items.append(
                BlogExportItem(
                    post_id=post.id,
                    primary_keyword=post.primary_keyword,
                    url_slug=post.url_slug,
                    title=post.title,
                    meta_description=post.meta_description,
                    html_content=clean_html,
                    word_count=word_count,
                )
            )

        logger.info(
            "Blog export package generated",
            extra={
                "campaign_id": campaign_id,
                "posts_exported": len(items),
            },
        )

        return items


def _count_words(html: str) -> int:
    """Count words in HTML content by stripping tags first.

    Args:
        html: HTML string.

    Returns:
        Word count (0 for empty/blank content).
    """
    if not html:
        return 0
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return len(text.split())
