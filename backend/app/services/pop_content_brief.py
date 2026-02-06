"""POP content brief service for fetching and storing content briefs.

Fetches content optimization data from PageOptimizer Pro (or mock) and stores
structured brief data as ContentBrief records. Handles caching, force refresh,
and graceful error handling so that content generation is never blocked.
"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.pop import (
    POPMockClient,
    POPTaskStatus,
    POPTimeoutError,
    get_pop_client,
)
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage

logger = get_logger(__name__)


@dataclass
class ContentBriefResult:
    """Result of a content brief fetch operation."""

    success: bool
    content_brief: ContentBrief | None = None
    error: str | None = None
    cached: bool = False


async def fetch_content_brief(
    db: AsyncSession,
    crawled_page: CrawledPage,
    keyword: str,
    target_url: str,
    force_refresh: bool = False,
) -> ContentBriefResult:
    """Fetch a content brief from POP and store as a ContentBrief record.

    Calls the POP get-terms endpoint (or mock) with the keyword and target URL,
    polls for completion, then parses the response into a ContentBrief record.

    Caching: if a ContentBrief already exists for the page and force_refresh is
    False, returns the existing record without making an API call.

    On POP API error or timeout, returns a failure result with error details
    but does NOT raise — content generation can proceed without LSI terms.

    Args:
        db: Async database session.
        crawled_page: The CrawledPage to associate the brief with.
        keyword: Target keyword for POP get-terms.
        target_url: URL to analyze.
        force_refresh: If True, make a new API call even if a brief exists.

    Returns:
        ContentBriefResult with success status, ContentBrief (or None), and
        error details if applicable.
    """
    page_id = crawled_page.id

    # Check for existing brief (caching)
    if not force_refresh:
        stmt = select(ContentBrief).where(ContentBrief.page_id == page_id)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            logger.info(
                "Content brief already exists, returning cached",
                extra={"page_id": page_id, "keyword": keyword[:50]},
            )
            return ContentBriefResult(
                success=True,
                content_brief=existing,
                cached=True,
            )

    # Get POP client (real or mock)
    pop_client = await get_pop_client()

    logger.info(
        "Fetching content brief from POP",
        extra={
            "page_id": page_id,
            "keyword": keyword[:50],
            "target_url": target_url[:100],
            "client_type": type(pop_client).__name__,
            "force_refresh": force_refresh,
        },
    )

    try:
        # Use get_terms() convenience method for mock, or create_report_task +
        # poll_for_result for real client
        if isinstance(pop_client, POPMockClient):
            task_result = await pop_client.get_terms(
                keyword=keyword,
                url=target_url,
            )
        else:
            # Real client: create task then poll
            task_result = await pop_client.create_report_task(
                keyword=keyword,
                url=target_url,
            )

            if not task_result.success or not task_result.task_id:
                error_msg = task_result.error or "Failed to create POP task"
                logger.warning(
                    "POP create_report_task failed",
                    extra={
                        "page_id": page_id,
                        "keyword": keyword[:50],
                        "error": error_msg,
                    },
                )
                return ContentBriefResult(success=False, error=error_msg)

            # Poll for completion
            task_result = await pop_client.poll_for_result(task_result.task_id)

        # Check task result
        if not task_result.success:
            error_msg = task_result.error or "POP task failed"
            logger.warning(
                "POP task failed",
                extra={
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "error": error_msg,
                },
            )
            return ContentBriefResult(success=False, error=error_msg)

        if task_result.status == POPTaskStatus.FAILURE:
            error_msg = task_result.data.get(
                "error", "POP task returned failure status"
            )
            logger.warning(
                "POP task returned failure status",
                extra={
                    "page_id": page_id,
                    "keyword": keyword[:50],
                    "error": error_msg,
                },
            )
            return ContentBriefResult(success=False, error=error_msg)

        # Parse response data
        response_data = task_result.data or {}
        lsi_terms = _parse_lsi_terms(response_data)
        related_searches = _parse_related_searches(response_data)
        pop_task_id = task_result.task_id

        logger.info(
            "POP get-terms response parsed",
            extra={
                "page_id": page_id,
                "keyword": keyword[:50],
                "lsi_term_count": len(lsi_terms),
                "related_search_count": len(related_searches),
                "pop_task_id": pop_task_id,
            },
        )

        # Create or replace ContentBrief record
        content_brief = await _upsert_content_brief(
            db=db,
            page_id=page_id,
            keyword=keyword,
            lsi_terms=lsi_terms,
            related_searches=related_searches,
            raw_response=response_data,
            pop_task_id=pop_task_id,
        )

        return ContentBriefResult(
            success=True,
            content_brief=content_brief,
        )

    except POPTimeoutError as e:
        logger.warning(
            "POP task timed out",
            extra={
                "page_id": page_id,
                "keyword": keyword[:50],
                "error": str(e),
            },
        )
        return ContentBriefResult(
            success=False,
            error=f"POP task timed out: {e}",
        )

    except Exception as e:
        logger.error(
            "Unexpected error fetching content brief",
            extra={
                "page_id": page_id,
                "keyword": keyword[:50],
                "error": str(e),
            },
            exc_info=True,
        )
        return ContentBriefResult(
            success=False,
            error=f"Unexpected error: {e}",
        )


def _parse_lsi_terms(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse lsaPhrases from POP response into lsi_terms list.

    Each term has: phrase, weight, averageCount, targetCount.

    Args:
        response_data: Raw POP API response dict.

    Returns:
        List of LSI term dicts.
    """
    lsa_phrases = response_data.get("lsaPhrases", [])
    if not isinstance(lsa_phrases, list):
        return []

    terms: list[dict[str, Any]] = []
    for item in lsa_phrases:
        if isinstance(item, dict) and "phrase" in item:
            terms.append(
                {
                    "phrase": item["phrase"],
                    "weight": item.get("weight", 0),
                    "averageCount": item.get("averageCount", 0),
                    "targetCount": item.get("targetCount", 0),
                }
            )
    return terms


def _parse_related_searches(response_data: dict[str, Any]) -> list[str]:
    """Parse variations from POP response into related_searches list.

    Args:
        response_data: Raw POP API response dict.

    Returns:
        List of related search strings.
    """
    variations = response_data.get("variations", [])
    if not isinstance(variations, list):
        return []
    return [v for v in variations if isinstance(v, str)]


async def _upsert_content_brief(
    db: AsyncSession,
    page_id: str,
    keyword: str,
    lsi_terms: list[dict[str, Any]],
    related_searches: list[str],
    raw_response: dict[str, Any],
    pop_task_id: str | None,
) -> ContentBrief:
    """Create or replace a ContentBrief record for the given page.

    If a ContentBrief already exists for the page_id, it is updated in place
    (force_refresh scenario). Otherwise a new record is created.

    Args:
        db: Async database session.
        page_id: UUID of the crawled page.
        keyword: Target keyword.
        lsi_terms: Parsed LSI terms from POP response.
        related_searches: Parsed related searches from POP response.
        raw_response: Full POP API response dict.
        pop_task_id: POP task ID for tracking.

    Returns:
        The created or updated ContentBrief instance.
    """
    stmt = select(ContentBrief).where(ContentBrief.page_id == page_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.keyword = keyword
        existing.lsi_terms = lsi_terms
        existing.related_searches = related_searches
        existing.raw_response = raw_response
        existing.pop_task_id = pop_task_id
        await db.commit()
        await db.refresh(existing)

        logger.info(
            "Updated existing ContentBrief",
            extra={"page_id": page_id, "brief_id": existing.id},
        )
        return existing

    brief = ContentBrief(
        page_id=page_id,
        keyword=keyword,
        lsi_terms=lsi_terms,
        related_searches=related_searches,
        raw_response=raw_response,
        pop_task_id=pop_task_id,
    )
    db.add(brief)
    await db.commit()
    await db.refresh(brief)

    logger.info(
        "Created new ContentBrief",
        extra={"page_id": page_id, "brief_id": brief.id},
    )
    return brief
