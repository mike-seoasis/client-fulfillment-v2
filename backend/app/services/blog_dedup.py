"""Blog deduplication service using title similarity.

Compares generated blog topic titles against existing Shopify articles
to prevent generating content ideas that already exist as published posts.
Uses normalized Levenshtein distance via rapidfuzz.
"""

import re
from dataclasses import dataclass
from typing import Any

from rapidfuzz.distance import Levenshtein
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.shopify_page import ShopifyPage

logger = get_logger(__name__)

# Similarity thresholds
FILTER_THRESHOLD = 0.90  # >90% — silently exclude
WARN_THRESHOLD = 0.70  # 70-90% — include with warning


@dataclass
class DedupResult:
    """Result of deduplication check for a single title."""

    title: str
    action: str  # "filter", "warn", or "pass"
    similarity: float  # 0.0 to 1.0
    existing_title: str | None = None
    existing_url: str | None = None


def normalize_title(title: str) -> str:
    """Normalize a title for comparison.

    Lowercases, strips punctuation, collapses whitespace.
    """
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def levenshtein_ratio(a: str, b: str) -> float:
    """Compute Levenshtein similarity ratio between two strings.

    Returns 1 - (edit_distance / max(len(a), len(b))).
    Returns 1.0 for identical strings, 0.0 for completely different.
    """
    if not a and not b:
        return 1.0
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    distance = Levenshtein.distance(a, b)
    return 1.0 - (distance / max_len)


def check_duplicates(
    generated_titles: list[str],
    existing_articles: list[dict[str, Any]],
) -> list[DedupResult]:
    """Check generated titles against existing articles for duplicates.

    Args:
        generated_titles: List of generated blog topic titles.
        existing_articles: List of dicts with 'title' and 'full_url' keys
            from shopify_pages where page_type='article'.

    Returns:
        List of DedupResult for each generated title.
    """
    if not existing_articles:
        return [
            DedupResult(title=t, action="pass", similarity=0.0)
            for t in generated_titles
        ]

    # Pre-normalize existing titles
    normalized_existing = [
        {
            "normalized": normalize_title(a["title"] or ""),
            "original_title": a["title"],
            "full_url": a.get("full_url"),
        }
        for a in existing_articles
        if a.get("title")
    ]

    results: list[DedupResult] = []

    for title in generated_titles:
        norm_title = normalize_title(title)
        best_match = DedupResult(title=title, action="pass", similarity=0.0)

        for existing in normalized_existing:
            ratio = levenshtein_ratio(norm_title, existing["normalized"])
            if ratio > best_match.similarity:
                best_match = DedupResult(
                    title=title,
                    action="pass",
                    similarity=ratio,
                    existing_title=existing["original_title"],
                    existing_url=existing["full_url"],
                )

        # Classify action
        if best_match.similarity > FILTER_THRESHOLD:
            best_match.action = "filter"
        elif best_match.similarity > WARN_THRESHOLD:
            best_match.action = "warn"

        results.append(best_match)

    return results


async def get_existing_articles(
    project_id: str, db: AsyncSession
) -> list[dict[str, Any]]:
    """Fetch existing Shopify articles for a project.

    Returns:
        List of dicts with 'title' and 'full_url' for each article.
    """
    result = await db.execute(
        select(ShopifyPage.title, ShopifyPage.full_url).where(
            ShopifyPage.project_id == project_id,
            ShopifyPage.page_type == "article",
            ShopifyPage.is_deleted == False,  # noqa: E712
        )
    )
    return [{"title": row[0], "full_url": row[1]} for row in result.all()]
