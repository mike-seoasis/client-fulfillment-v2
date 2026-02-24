"""POP content brief service for fetching and storing content briefs.

Fetches content optimization data from PageOptimizer Pro (or mock) and stores
structured brief data as ContentBrief records. Supports the full 3-step POP flow:
1. get-terms → LSI phrases, variations, prepareId
2. create-report → competitors, related questions, word count range, page score
3. get-custom-recommendations → keyword placement targets, heading structure

Handles caching, force refresh, and graceful error handling so that content
generation is never blocked.
"""

import contextlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.pop import (
    POPClient,
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

    For mock client: calls get_terms() which returns all 3 steps merged.
    For real client: orchestrates the 3-step flow:
      1. create_report_task (get-terms) → poll → extract prepareId
      2. create_report(prepareId) → poll → extract report data
      3. get_custom_recommendations(reportId) → extract recommendations

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
        if isinstance(pop_client, POPMockClient):
            # Mock client returns all 3 steps merged in get_terms()
            task_result = await pop_client.get_terms(
                keyword=keyword,
                url=target_url,
            )

            # Check task result status
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

            response_data = task_result.data or {}
            pop_task_id = task_result.task_id
        else:
            # Real client: 3-step orchestration
            response_data, pop_task_id = await _run_real_3step_flow(
                pop_client, keyword, target_url
            )

        # Parse all fields from merged response data
        lsi_terms = _parse_lsi_terms(response_data)
        related_searches = _parse_related_searches(response_data)
        word_count_target = _parse_word_count_target(response_data)
        competitors = _parse_competitors(response_data)
        related_questions = _parse_related_questions(response_data)
        heading_targets = _parse_heading_targets(response_data)
        keyword_targets = _parse_keyword_targets(response_data)
        word_count_min, word_count_max = _parse_word_count_range(response_data)
        page_score_target = _parse_page_score(response_data)

        logger.info(
            "POP 3-step response parsed",
            extra={
                "page_id": page_id,
                "keyword": keyword[:50],
                "lsi_term_count": len(lsi_terms),
                "related_search_count": len(related_searches),
                "competitor_count": len(competitors),
                "related_question_count": len(related_questions),
                "heading_target_count": len(heading_targets),
                "keyword_target_count": len(keyword_targets),
                "page_score_target": page_score_target,
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
            word_count_target=word_count_target,
            raw_response=response_data,
            pop_task_id=pop_task_id,
            competitors=competitors,
            related_questions=related_questions,
            heading_targets=heading_targets,
            keyword_targets=keyword_targets,
            word_count_min=word_count_min,
            word_count_max=word_count_max,
            page_score_target=page_score_target,
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


async def _run_real_3step_flow(
    pop_client: POPClient,
    keyword: str,
    target_url: str,
) -> tuple[dict[str, Any], str | None]:
    """Run the real 3-step POP API flow and merge results.

    Steps:
    1. get-terms (create_report_task → poll) → lsaPhrases, variations, prepareId
    2. create-report (prepareId → poll) → competitors, relatedQuestions, etc.
    3. get-custom-recommendations (reportId) → keyword/heading targets

    Step 3 is optional — if it fails, data from steps 1+2 is still returned.

    Returns:
        Tuple of (merged_response_data, pop_task_id)

    Raises:
        POPTimeoutError: If step 1 or 2 times out.
        Exception: On unexpected errors in step 1 or 2.
    """
    # --- Step 1: get-terms ---
    task_result = await pop_client.create_report_task(
        keyword=keyword,
        url=target_url,
    )

    if not task_result.success or not task_result.task_id:
        error_msg = task_result.error or "Failed to create POP task"
        raise Exception(error_msg)  # noqa: TRY002

    poll_result = await pop_client.poll_for_result(task_result.task_id)
    pop_task_id = task_result.task_id

    if not poll_result.success or poll_result.status == POPTaskStatus.FAILURE:
        error_msg = poll_result.error or poll_result.data.get(
            "error", "POP get-terms failed"
        )
        raise Exception(error_msg)  # noqa: TRY002

    response_data = dict(poll_result.data or {})

    # Extract data needed for step 2
    prepare_id = response_data.get("prepareId")
    lsa_phrases = response_data.get("lsaPhrases", [])
    variations = response_data.get("variations", [])

    # Preserve step 1 keyword variations (strings) before step 2/3 overwrite them
    # Steps 2+3 have their own "variations" key with recommendation objects
    response_data["_keyword_variations"] = list(variations)

    if not prepare_id:
        logger.warning(
            "No prepareId in get-terms response, skipping steps 2+3",
            extra={
                "keyword": keyword[:50],
                "response_keys": list(response_data.keys()),
                "status": response_data.get("status"),
                "has_lsa": len(lsa_phrases) > 0,
                "has_variations": len(variations) > 0,
            },
        )
        return response_data, pop_task_id

    # --- Step 2: create-report ---
    report_task = await pop_client.create_report(
        prepare_id=prepare_id,
        variations=variations,
        lsa_phrases=lsa_phrases,
    )

    if not report_task.success or not report_task.task_id:
        logger.warning(
            "create-report failed, continuing with get-terms data only",
            extra={"error": report_task.error, "keyword": keyword[:50]},
        )
        return response_data, pop_task_id

    # reportId comes in the initial create-report response, NOT in the polled result
    report_id = (report_task.data or {}).get("reportId")

    report_result = await pop_client.poll_for_result(report_task.task_id)

    if not report_result.success or report_result.status == POPTaskStatus.FAILURE:
        logger.warning(
            "create-report poll failed, continuing with get-terms data only",
            extra={"error": report_result.error, "keyword": keyword[:50]},
        )
        return response_data, pop_task_id

    # Merge step 2 data — POP nests report fields under "report" key
    report_data = report_result.data or {}
    report_inner = report_data.get("report", {})
    if isinstance(report_inner, dict) and report_inner:
        # Flatten: pull competitors, relatedQuestions, tagCounts, wordCount,
        # pageScore, cleanedContentBrief etc. to top level
        response_data.update(report_inner)
        logger.info(
            "Step 2 report data flattened",
            extra={
                "report_keys": list(report_inner.keys())[:20],
                "keyword": keyword[:50],
            },
        )
    else:
        # Fallback: merge as-is (some API versions may not nest)
        response_data.update(report_data)

    # --- Step 3: get-custom-recommendations (optional) ---
    # Also check polled data and merged response as fallback
    if not report_id:
        report_id = report_data.get("reportId") or response_data.get("reportId")

    if not report_id:
        logger.warning(
            "No reportId in create-report response, skipping step 3",
            extra={"keyword": keyword[:50]},
        )
        return response_data, pop_task_id

    try:
        recs_result = await pop_client.get_custom_recommendations(report_id=report_id)

        if recs_result.success:
            recs_data = recs_result.data or {}
            # POP nests recommendation fields under "recommendations" key
            recs_inner = recs_data.get("recommendations", {})
            if isinstance(recs_inner, dict) and recs_inner:
                # Flatten: pull exactKeyword, lsi, pageStructure to top level
                response_data.update(recs_inner)
                logger.info(
                    "Step 3 recommendations flattened",
                    extra={
                        "recs_keys": list(recs_inner.keys())[:20],
                        "report_id": report_id,
                        "keyword": keyword[:50],
                    },
                )
            else:
                # Fallback: merge as-is
                response_data.update(recs_data)
                logger.info(
                    "Step 3 recommendations merged (no nesting)",
                    extra={"report_id": report_id, "keyword": keyword[:50]},
                )
        else:
            logger.warning(
                "get-custom-recommendations failed, continuing without recs",
                extra={"error": recs_result.error, "keyword": keyword[:50]},
            )
    except Exception as e:
        logger.warning(
            "get-custom-recommendations raised exception, continuing without recs",
            extra={"error": str(e), "keyword": keyword[:50]},
        )

    return response_data, pop_task_id


# ---------------------------------------------------------------------------
# Parse helpers
# ---------------------------------------------------------------------------


def _parse_lsi_terms(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse lsaPhrases from POP response into lsi_terms list.

    Each term has: phrase, weight, averageCount, targetCount.
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
    """Parse keyword variations from POP response into related_searches list.

    Step 1 variations (strings) are preserved in _keyword_variations before
    steps 2/3 overwrite the "variations" key with recommendation objects.
    Falls back to relatedSearches (objects with "query" key) from step 2.
    """
    # Prefer preserved step 1 keyword variations (list of strings)
    kw_variations = response_data.get("_keyword_variations", [])
    if isinstance(kw_variations, list) and kw_variations:
        return [v for v in kw_variations if isinstance(v, str)]

    # Fallback: relatedSearches from step 2 (list of {query, link} objects)
    related = response_data.get("relatedSearches", [])
    if isinstance(related, list):
        results = []
        for item in related:
            if isinstance(item, str):
                results.append(item)
            elif isinstance(item, dict) and "query" in item:
                results.append(item["query"])
        if results:
            return results

    # Last fallback: variations if they're still strings
    variations = response_data.get("variations", [])
    if isinstance(variations, list):
        return [v for v in variations if isinstance(v, str)]

    return []


def _parse_word_count_target(response_data: dict[str, Any]) -> int | None:
    """Parse word count target from POP response.

    POP returns wordCount as {target, current} from create-report.
    Falls back to wordCountTarget (from get-terms, mock data).
    """
    # Step 2 format: {target: 2275, current: 0}
    wc = response_data.get("wordCount")
    if isinstance(wc, dict):
        target = wc.get("target")
        if target is not None:
            try:
                return int(target)
            except (ValueError, TypeError):
                pass

    # Fallback: wordCountTarget (mock data format)
    wc_target = response_data.get("wordCountTarget")
    if wc_target is not None:
        try:
            return int(wc_target)
        except (ValueError, TypeError):
            return None
    return None


def _parse_competitors(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse competitors from create-report response.

    Returns list of {url, title, h2Texts, h3Texts, pageScore, wordCount}.
    Real API may return null for pageScore and wordCount.
    """
    competitors = response_data.get("competitors", [])
    if not isinstance(competitors, list):
        return []

    parsed: list[dict[str, Any]] = []
    for comp in competitors:
        if not isinstance(comp, dict):
            continue
        parsed.append(
            {
                "url": comp.get("url", ""),
                "title": comp.get("title", ""),
                "h2Texts": comp.get("h2Texts", []),
                "h3Texts": comp.get("h3Texts", []),
                "pageScore": comp.get("pageScore") or 0,
                "wordCount": comp.get("wordCount") or 0,
            }
        )
    return parsed


def _parse_related_questions(response_data: dict[str, Any]) -> list[str]:
    """Parse relatedQuestions from create-report response.

    Real API returns list of {question, type, references} objects.
    Mock/fallback may return plain strings.
    """
    questions = response_data.get("relatedQuestions", [])
    if not isinstance(questions, list):
        return []

    results: list[str] = []
    for q in questions:
        if isinstance(q, str):
            results.append(q)
        elif isinstance(q, dict) and "question" in q:
            results.append(q["question"])
    return results


def _parse_heading_targets(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse heading structure targets from tagCounts + pageStructure recs.

    tagCounts from real API: list of {tagLabel, min, max, mean, comment}
    pageStructure from recommendations: list of {signal, target, comment}

    Returns list of {tag, target, min, max, source}.
    """
    targets: list[dict[str, Any]] = []

    # From pageStructure (recommendations) — preferred source
    # Note: pageStructure items have mean/min/max but NO "target" key
    page_structure = response_data.get("pageStructure", [])
    if isinstance(page_structure, list):
        for item in page_structure:
            if isinstance(item, dict) and "signal" in item:
                target_val = round(item.get("mean") or 0)
                targets.append(
                    {
                        "tag": item["signal"],
                        "target": target_val,
                        "min": item.get("min") or 0,
                        "max": item.get("max") or 0,
                        "source": "recommendations",
                    }
                )

    # Also include tagCounts which have richer min/max/mean data
    tag_counts = response_data.get("tagCounts", [])
    if isinstance(tag_counts, list):
        # Real API format: list of {tagLabel, min, max, mean, comment}
        for item in tag_counts:
            if not isinstance(item, dict) or "tagLabel" not in item:
                continue
            tag_label = item["tagLabel"]
            # Don't duplicate if already in pageStructure (case-insensitive)
            existing_tags = {t["tag"].lower() for t in targets}
            if tag_label.lower() not in existing_tags:
                targets.append(
                    {
                        "tag": tag_label,
                        "target": round(item.get("mean") or 0),
                        "min": item.get("min") or 0,
                        "max": item.get("max") or 0,
                        "source": "tagCounts",
                    }
                )
    elif isinstance(tag_counts, dict):
        # Mock/fallback format: {h1: 1, h2: 5}
        for tag, count in tag_counts.items():
            if isinstance(count, (int, float)):
                existing_tags = {t["tag"].lower() for t in targets}
                if tag.lower() not in existing_tags:
                    targets.append(
                        {
                            "tag": tag,
                            "target": int(count),
                            "source": "tagCounts",
                        }
                    )

    return targets


def _parse_keyword_targets(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse keyword placement targets from exactKeyword + lsi recs.

    Returns list of {signal, target, comment/phrase, type}.
    """
    targets: list[dict[str, Any]] = []

    # exactKeyword placements
    exact = response_data.get("exactKeyword", [])
    if isinstance(exact, list):
        for item in exact:
            if isinstance(item, dict) and "signal" in item:
                targets.append(
                    {
                        "signal": item["signal"],
                        "target": item.get("target", 0),
                        "comment": item.get("comment", ""),
                        "type": "exact",
                    }
                )

    # LSI placements (real API has "comment" not "phrase")
    lsi = response_data.get("lsi", [])
    if isinstance(lsi, list):
        for item in lsi:
            if isinstance(item, dict) and "signal" in item:
                targets.append(
                    {
                        "signal": item["signal"],
                        "phrase": item.get("phrase") or item.get("comment", ""),
                        "target": item.get("target", 0),
                        "type": "lsi",
                    }
                )

    return targets


def _parse_word_count_range(
    response_data: dict[str, Any],
) -> tuple[int | None, int | None]:
    """Parse word count range from competitor data or wordCount dict.

    Derives min/max from competitors' word counts (most accurate).
    Falls back to competitorsMin/competitorsMax in wordCount dict (mock format).
    Last resort: derives ±20% from wordCount.target.

    Returns (word_count_min, word_count_max).
    """
    # Best source: compute from competitors' actual word counts
    competitors = response_data.get("competitors", [])
    if isinstance(competitors, list) and competitors:
        word_counts = []
        for c in competitors:
            if isinstance(c, dict):
                wc = c.get("wordCount")
                if wc is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        word_counts.append(int(wc))
        if word_counts:
            return min(word_counts), max(word_counts)

    # Fallback: check wordCount dict for explicit min/max (mock format)
    wc = response_data.get("wordCount")
    if isinstance(wc, dict):
        wc_min = wc.get("competitorsMin")
        wc_max = wc.get("competitorsMax")
        if wc_min is not None and wc_max is not None:
            try:
                return int(wc_min), int(wc_max)
            except (ValueError, TypeError):
                pass

        # Last resort: derive ±20% from target
        target = wc.get("target")
        if target is not None:
            try:
                t = int(target)
                return int(t * 0.8), int(t * 1.2)
            except (ValueError, TypeError):
                pass

    return None, None


def _parse_page_score(response_data: dict[str, Any]) -> float | None:
    """Parse pageScore target from create-report response.

    Top-level pageScore is often null for new pages (pageNotBuiltYet=true).
    Falls back to computing average from competitors' pageScore values.
    """
    # Direct top-level pageScore (if available and not null)
    score = response_data.get("pageScore")
    if score is not None:
        try:
            return float(score)
        except (ValueError, TypeError):
            pass

    # Fallback: average of competitors' page scores
    competitors = response_data.get("competitors", [])
    if isinstance(competitors, list) and competitors:
        scores = []
        for c in competitors:
            if isinstance(c, dict):
                cs = c.get("pageScore")
                if cs is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        scores.append(float(cs))
        if scores:
            return round(sum(scores) / len(scores), 1)

    return None


# ---------------------------------------------------------------------------
# Upsert helper
# ---------------------------------------------------------------------------


async def _upsert_content_brief(
    db: AsyncSession,
    page_id: str,
    keyword: str,
    lsi_terms: list[dict[str, Any]],
    related_searches: list[str],
    word_count_target: int | None,
    raw_response: dict[str, Any],
    pop_task_id: str | None,
    competitors: list[dict[str, Any]] | None = None,
    related_questions: list[str] | None = None,
    heading_targets: list[dict[str, Any]] | None = None,
    keyword_targets: list[dict[str, Any]] | None = None,
    word_count_min: int | None = None,
    word_count_max: int | None = None,
    page_score_target: float | None = None,
) -> ContentBrief:
    """Create or replace a ContentBrief record for the given page.

    If a ContentBrief already exists for the page_id, it is updated in place
    (force_refresh scenario). Otherwise a new record is created.
    """
    stmt = select(ContentBrief).where(ContentBrief.page_id == page_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        existing.keyword = keyword
        existing.lsi_terms = lsi_terms
        existing.related_searches = related_searches
        existing.word_count_target = word_count_target
        existing.raw_response = raw_response
        existing.pop_task_id = pop_task_id
        existing.competitors = competitors or []
        existing.related_questions = related_questions or []
        existing.heading_targets = heading_targets or []
        existing.keyword_targets = keyword_targets or []
        existing.word_count_min = word_count_min
        existing.word_count_max = word_count_max
        existing.page_score_target = page_score_target
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
        word_count_target=word_count_target,
        raw_response=raw_response,
        pop_task_id=pop_task_id,
        competitors=competitors or [],
        related_questions=related_questions or [],
        heading_targets=heading_targets or [],
        keyword_targets=keyword_targets or [],
        word_count_min=word_count_min,
        word_count_max=word_count_max,
        page_score_target=page_score_target,
    )
    db.add(brief)
    await db.commit()
    await db.refresh(brief)

    logger.info(
        "Created new ContentBrief",
        extra={"page_id": page_id, "brief_id": brief.id},
    )
    return brief
