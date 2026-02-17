"""Reddit post discovery service.

Orchestrates the full discovery pipeline:
1. SERP search for Reddit posts matching project keywords
2. Deduplication by URL
3. Filter banned/marketing subreddits
4. Keyword-based intent classification (fast, no API calls)
5. Claude Sonnet relevance scoring
6. Store results with upsert semantics

Follows the trigger → background task → poll status pattern
from content_generation.py.
"""

import json
from app.core.logging import get_logger
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import db_manager
from app.integrations.claude import ClaudeClient, get_api_key
from app.integrations.serpapi import SerpResult, get_serpapi
from app.models.brand_config import BrandConfig
from app.models.reddit_config import RedditProjectConfig
from app.models.reddit_post import RedditPost

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Intent classification keyword lists
# Ported exactly from the Flask app (REDDIT_INTEGRATION_PLAN.md)
# ---------------------------------------------------------------------------

RESEARCH_INTENT_KEYWORDS: list[str] = [
    "recommend",
    "recommendation",
    "suggestions",
    "suggest",
    "advice",
    "best",
    "looking for",
    "help me find",
    "what should i",
    "which",
    "vs",
    "compare",
    "alternative",
    "instead of",
    "similar to",
    "thoughts on",
    "opinions on",
    "reviews",
    "worth it",
    "good",
    "anyone tried",
    "has anyone used",
    "experiences with",
    "ideas",
    "options",
    "need help",
    "new to",
    "know nothing",
    "where to start",
    "beginner",
    "first time",
]

PAIN_POINT_KEYWORDS: list[str] = [
    "struggling",
    "problem",
    "issue",
    "help",
    "not working",
    "failed",
    "disappointed",
    "waste",
    "regret",
    "frustrated",
    "confused",
    "expensive",
    "can't afford",
    "too much",
    "overpriced",
    "dry skin",
    "sensitive skin",
    "acne",
    "wrinkles",
    "aging",
    "irritation",
    "redness",
    "breakout",
    "doesn't work",
    "afraid",
    "worried",
    "concern",
    "losing",
    "getting worse",
    "don't know",
    "clueless",
    "overwhelmed",
    "unsure",
]

QUESTION_PATTERNS: list[str] = [
    "?",
    "how do i",
    "how to",
    "what is",
    "what are",
    "why",
    "can i",
    "should i",
    "is it",
    "are there",
    "does anyone",
]

PROMOTIONAL_KEYWORDS: list[str] = [
    "my brand",
    "i founded",
    "my company",
    "my business",
    "i'm selling",
    "our product",
    "check out my",
    "my store",
    "promotion",
    "discount code",
    "affiliate",
    "my website",
    "buy from",
    "i created",
    "launching my",
    "for sale",
    "selling",
    "buy now",
    "shop",
    "coupon",
    "promo code",
]

MARKETING_SUBREDDITS: set[str] = {
    "facebookads",
    "ppc",
    "marketing",
    "entrepreneur",
    "smallbusiness",
    "ecommerce",
    "shopify",
    "business",
    "startup",
    "advertising",
}


# ---------------------------------------------------------------------------
# Intent classification data structures
# ---------------------------------------------------------------------------


@dataclass
class IntentResult:
    """Result of keyword-based intent classification for a single post."""

    intents: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    is_promotional: bool = False


# ---------------------------------------------------------------------------
# Intent classification functions
# ---------------------------------------------------------------------------


def _text_for_classification(post: SerpResult) -> str:
    """Combine title + snippet into a single lowercase string for matching."""
    parts: list[str] = []
    if post.title:
        parts.append(post.title)
    if post.snippet:
        parts.append(post.snippet)
    return " ".join(parts).lower()


def classify_intent(
    post: SerpResult,
    competitors: list[str] | None = None,
) -> IntentResult:
    """Classify the intent of a Reddit post using keyword matching.

    This is a fast, no-API-call classification step. It checks the post
    title and snippet against keyword lists to determine intent categories.

    Args:
        post: The SerpResult to classify.
        competitors: Optional list of competitor names for competitor detection.

    Returns:
        IntentResult with matched intents and keywords.
    """
    text = _text_for_classification(post)
    result = IntentResult()

    # Check for promotional content first (exclusion signal)
    for keyword in PROMOTIONAL_KEYWORDS:
        if keyword in text:
            result.is_promotional = True
            result.matched_keywords.append(f"promotional:{keyword}")
            break  # One promotional match is enough

    # Research intent
    for keyword in RESEARCH_INTENT_KEYWORDS:
        if keyword in text:
            if "research" not in result.intents:
                result.intents.append("research")
            result.matched_keywords.append(f"research:{keyword}")

    # Pain point intent
    for keyword in PAIN_POINT_KEYWORDS:
        if keyword in text:
            if "pain_point" not in result.intents:
                result.intents.append("pain_point")
            result.matched_keywords.append(f"pain_point:{keyword}")

    # Question intent
    for pattern in QUESTION_PATTERNS:
        if pattern in text:
            if "question" not in result.intents:
                result.intents.append("question")
            result.matched_keywords.append(f"question:{pattern}")

    # Competitor mention
    if competitors:
        for competitor in competitors:
            if competitor.lower() in text:
                if "competitor" not in result.intents:
                    result.intents.append("competitor")
                result.matched_keywords.append(f"competitor:{competitor}")

    # If no intents matched, mark as general
    if not result.intents:
        result.intents.append("general")

    return result


def is_excluded_post(
    post: SerpResult,
    banned_subreddits: list[str] | None = None,
) -> bool:
    """Check if a post should be excluded from further processing.

    A post is excluded if:
    - Its subreddit is in the banned_subreddits list
    - Its subreddit is a known marketing subreddit
    - Its content matches promotional keywords

    Args:
        post: The SerpResult to check.
        banned_subreddits: Project-specific banned subreddits.

    Returns:
        True if the post should be excluded.
    """
    subreddit_lower = post.subreddit.lower()

    # Check banned subreddits
    if banned_subreddits:
        banned_lower = {s.lower() for s in banned_subreddits}
        if subreddit_lower in banned_lower:
            logger.debug(
                "Post excluded: banned subreddit",
                extra={"subreddit": post.subreddit, "url": post.url},
            )
            return True

    # Check marketing subreddits
    if subreddit_lower in MARKETING_SUBREDDITS:
        logger.debug(
            "Post excluded: marketing subreddit",
            extra={"subreddit": post.subreddit, "url": post.url},
        )
        return True

    # Check promotional content
    text = _text_for_classification(post)
    for keyword in PROMOTIONAL_KEYWORDS:
        if keyword in text:
            logger.debug(
                "Post excluded: promotional content",
                extra={"keyword": keyword, "url": post.url},
            )
            return True

    return False


# ---------------------------------------------------------------------------
# Claude Sonnet relevance scoring
# ---------------------------------------------------------------------------

# System prompt for Reddit post relevance scoring
SCORING_SYSTEM_PROMPT = """You are evaluating Reddit posts for marketing opportunities. Score each post's relevance to the brand on a 0-10 scale.

Respond ONLY with valid JSON in this exact format:
{"score": N, "reasoning": "brief explanation", "intent": "research|pain_point|competitor|question|general"}

Guidelines:
- Score 0-3: Unrelated to the brand, purely negative/ranting, promotional/spam
- Score 4-6: Somewhat relevant but not a clear opportunity
- Score 7-10: Strong opportunity — asking for recommendations, has a problem the brand could solve, comparing products
- REJECT (low score) if: unrelated to brand's niche, purely negative rant, obvious spam
- ACCEPT (high score) if: asking for product recommendations, describing a problem the brand solves, comparing competitors"""


@dataclass
class ScoringResult:
    """Result of Claude Sonnet relevance scoring for a single post."""

    score: float
    reasoning: str
    intent: str
    filter_status: str  # "relevant", "irrelevant", or "pending"
    raw_response: dict[str, Any] | None = None
    error: str | None = None


def _determine_filter_status(score: float) -> str:
    """Map a 0-10 score to a filter status.

    - score < 4: irrelevant (auto-reject)
    - 4 <= score <= 6: pending (human review)
    - score >= 7: relevant (auto-approve)
    """
    if score < 4:
        return "irrelevant"
    if score >= 7:
        return "relevant"
    return "pending"


def _build_scoring_prompt(
    post: SerpResult,
    brand_name: str,
    brand_description: str,
    competitors: list[str],
) -> str:
    """Build the user prompt for Claude Sonnet scoring.

    Args:
        post: The Reddit post to score.
        brand_name: Name of the brand.
        brand_description: Description of what the brand does/sells.
        competitors: List of competitor names.

    Returns:
        Formatted user prompt string.
    """
    competitors_str = ", ".join(competitors) if competitors else "none specified"

    return f"""Evaluate this Reddit post for marketing opportunities for {brand_name}.

Brand: {brand_name}
Products: {brand_description}
Competitors: {competitors_str}

Reddit Post:
Subreddit: r/{post.subreddit}
Title: {post.title}
Content: {post.snippet or "(no snippet available)"}

Score 0-10: Is this a natural opportunity to mention {brand_name}?
REJECT if: unrelated to brand, purely negative/ranting, promotional/spam
ACCEPT if: asking for recommendations, has a problem brand could solve, comparing products

Return JSON: {{"score": N, "reasoning": "...", "intent": "research|pain_point|competitor|question|general"}}"""


async def score_post_with_claude(
    post: SerpResult,
    claude_client: ClaudeClient,
    brand_name: str,
    brand_description: str,
    competitors: list[str],
) -> ScoringResult:
    """Score a single Reddit post's relevance using Claude Sonnet.

    Args:
        post: The Reddit post to score.
        claude_client: Initialized ClaudeClient instance.
        brand_name: Name of the brand.
        brand_description: Description of what the brand does/sells.
        competitors: List of competitor names.

    Returns:
        ScoringResult with score, reasoning, intent, and filter_status.
    """
    user_prompt = _build_scoring_prompt(
        post, brand_name, brand_description, competitors
    )

    # Always use Sonnet (ClaudeClient default from settings), never Haiku
    result = await claude_client.complete(
        user_prompt=user_prompt,
        system_prompt=SCORING_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=256,
    )

    if not result.success:
        logger.warning(
            "Claude scoring failed for post",
            extra={"url": post.url, "error": result.error},
        )
        return ScoringResult(
            score=0.0,
            reasoning="Claude scoring failed",
            intent="general",
            filter_status="pending",
            error=result.error,
        )

    # Parse the JSON response
    try:
        response_text = (result.text or "").strip()

        # Handle markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)

        parsed = json.loads(response_text)
        score = float(parsed.get("score", 0))
        reasoning = parsed.get("reasoning", "")
        intent = parsed.get("intent", "general")

        # Clamp score to 0-10
        score = max(0.0, min(10.0, score))

        filter_status = _determine_filter_status(score)

        return ScoringResult(
            score=score,
            reasoning=reasoning,
            intent=intent,
            filter_status=filter_status,
            raw_response=parsed,
        )

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(
            "Failed to parse Claude scoring response",
            extra={
                "url": post.url,
                "response": (result.text or "")[:500],
                "error": str(e),
            },
        )
        return ScoringResult(
            score=0.0,
            reasoning="Failed to parse scoring response",
            intent="general",
            filter_status="pending",
            error=f"Parse error: {e}",
        )


async def score_posts_batch(
    posts: list[SerpResult],
    claude_client: ClaudeClient,
    brand_name: str,
    brand_description: str,
    competitors: list[str],
    on_progress: Any | None = None,
) -> list[ScoringResult]:
    """Score multiple Reddit posts with Claude Sonnet, one at a time.

    Processes posts sequentially (Claude rate limits make parallelism risky).
    Calls on_progress callback after each post if provided.

    Args:
        posts: List of SerpResult posts to score.
        claude_client: Initialized ClaudeClient instance.
        brand_name: Name of the brand.
        brand_description: Description of what the brand does/sells.
        competitors: List of competitor names.
        on_progress: Optional callback(scored_count, total_count) for progress updates.

    Returns:
        List of ScoringResult objects, one per input post.
    """
    results: list[ScoringResult] = []
    total = len(posts)

    for i, post in enumerate(posts):
        try:
            scoring = await score_post_with_claude(
                post=post,
                claude_client=claude_client,
                brand_name=brand_name,
                brand_description=brand_description,
                competitors=competitors,
            )
            results.append(scoring)
        except Exception as e:
            logger.error(
                "Unexpected error scoring post",
                extra={"url": post.url, "error": str(e), "error_type": type(e).__name__},
            )
            results.append(
                ScoringResult(
                    score=0.0,
                    reasoning=f"Scoring error: {e}",
                    intent="general",
                    filter_status="pending",
                    error=str(e),
                )
            )

        # Progress callback
        if on_progress:
            try:
                on_progress(i + 1, total)
            except Exception:
                pass  # Don't let progress callback errors break scoring

    logger.info(
        "Batch scoring complete",
        extra={
            "total_posts": total,
            "scored": len(results),
            "relevant": sum(1 for r in results if r.filter_status == "relevant"),
            "irrelevant": sum(1 for r in results if r.filter_status == "irrelevant"),
            "pending": sum(1 for r in results if r.filter_status == "pending"),
        },
    )

    return results


# ---------------------------------------------------------------------------
# Discovery progress tracking (in-memory)
# ---------------------------------------------------------------------------


@dataclass
class DiscoveryProgress:
    """Real-time progress data for a running discovery pipeline."""

    status: str = "searching"  # searching | scoring | storing | complete | failed
    total_keywords: int = 0
    keywords_searched: int = 0
    total_posts_found: int = 0
    posts_scored: int = 0
    posts_stored: int = 0
    error: str | None = None
    started_at: str = ""
    completed_at: str = ""


# In-memory dict keyed by project_id → DiscoveryProgress.
# For single-process deployments (Railway). If the server restarts,
# status resets — user can re-trigger, posts already in DB are safe.
_active_discoveries: dict[str, DiscoveryProgress] = {}


def get_discovery_progress(project_id: str) -> DiscoveryProgress | None:
    """Get the current discovery progress for a project, if any."""
    return _active_discoveries.get(project_id)


def is_discovery_active(project_id: str) -> bool:
    """Check if a discovery is currently running for a project."""
    progress = _active_discoveries.get(project_id)
    if progress is None:
        return False
    return progress.status in ("searching", "scoring", "storing")


def _set_progress(project_id: str, progress: DiscoveryProgress) -> None:
    """Store progress in the in-memory dict."""
    _active_discoveries[project_id] = progress


def _clear_progress(project_id: str) -> None:
    """Remove progress entry (called after completion/failure persists)."""
    _active_discoveries.pop(project_id, None)


# ---------------------------------------------------------------------------
# Deduplication helper
# ---------------------------------------------------------------------------


def _deduplicate_posts(posts: list[SerpResult]) -> list[SerpResult]:
    """Deduplicate SerpResult posts by URL (first occurrence wins)."""
    seen_urls: set[str] = set()
    unique: list[SerpResult] = []
    for post in posts:
        normalized = post.url.rstrip("/")
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            unique.append(post)
    return unique


# ---------------------------------------------------------------------------
# Store discovered posts (upsert)
# ---------------------------------------------------------------------------


async def store_discovered_posts(
    project_id: str,
    posts: list[SerpResult],
    intent_results: list[IntentResult],
    scoring_results: list[ScoringResult],
    keywords_used: list[str],
    db: AsyncSession,
) -> int:
    """Upsert discovered posts into the database.

    Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE to handle deduplication
    at the DB level. Does NOT overwrite filter_status if it was manually
    changed by a user (i.e., not 'pending').

    Args:
        project_id: The project UUID.
        posts: List of SerpResult posts.
        intent_results: Parallel list of IntentResult for each post.
        scoring_results: Parallel list of ScoringResult for each post.
        keywords_used: Keywords that were searched (for the keyword field).
        db: Async database session.

    Returns:
        Number of posts stored/updated.
    """
    from sqlalchemy import case

    stored = 0

    for post, intent, scoring in zip(posts, intent_results, scoring_results):
        # Determine primary intent (first from keyword classification,
        # enriched by Claude's assessment)
        primary_intent = intent.intents[0] if intent.intents else "general"
        # If Claude identified a specific intent, prefer it
        if scoring.intent and scoring.intent != "general":
            primary_intent = scoring.intent

        # Normalize relevance_score from 0-10 to 0.0-1.0 for the DB field
        relevance_score = scoring.score / 10.0 if scoring.score else None

        values = {
            "project_id": project_id,
            "url": post.url,
            "title": post.title,
            "snippet": post.snippet,
            "subreddit": post.subreddit,
            "keyword": post.search_keyword or None,
            "intent": primary_intent,
            "intent_categories": intent.intents,
            "relevance_score": relevance_score,
            "matched_keywords": intent.matched_keywords,
            "ai_evaluation": {
                "score": scoring.score,
                "reasoning": scoring.reasoning,
                "intent": scoring.intent,
                "raw": scoring.raw_response,
            },
            "filter_status": scoring.filter_status,
            "discovered_at": post.discovered_at,
        }

        stmt = pg_insert(RedditPost).values(**values)

        # On conflict (project_id, url): update metadata but preserve
        # user-set filter_status. CASE: if existing is still 'pending',
        # update it from new scoring; otherwise keep the user's choice.
        stmt = stmt.on_conflict_do_update(
            constraint="uq_reddit_posts_project_url",
            set_={
                "title": stmt.excluded.title,
                "snippet": stmt.excluded.snippet,
                "subreddit": stmt.excluded.subreddit,
                "intent": stmt.excluded.intent,
                "intent_categories": stmt.excluded.intent_categories,
                "relevance_score": stmt.excluded.relevance_score,
                "matched_keywords": stmt.excluded.matched_keywords,
                "ai_evaluation": stmt.excluded.ai_evaluation,
                "discovered_at": stmt.excluded.discovered_at,
                "updated_at": datetime.now(UTC),
                "filter_status": case(
                    (
                        RedditPost.__table__.c.filter_status == "pending",
                        stmt.excluded.filter_status,
                    ),
                    else_=RedditPost.__table__.c.filter_status,
                ),
            },
        )

        try:
            await db.execute(stmt)
            stored += 1
        except Exception as e:
            logger.error(
                "Failed to upsert Reddit post",
                extra={"url": post.url, "project_id": project_id, "error": str(e)},
            )

    await db.commit()

    logger.info(
        "Stored discovered posts",
        extra={"project_id": project_id, "stored": stored, "total": len(posts)},
    )

    return stored


# ---------------------------------------------------------------------------
# Discovery pipeline orchestrator
# ---------------------------------------------------------------------------


async def discover_posts(
    project_id: str,
    time_range: str = "7d",
) -> dict[str, Any]:
    """Full discovery pipeline for a project.

    Designed to run in a FastAPI BackgroundTask. Creates its own DB sessions.

    Steps:
    1. Load project Reddit config + brand config
    2. Search SerpAPI for each keyword (with optional subreddit scoping)
    3. Deduplicate results by URL
    4. Filter banned/marketing subreddits and promotional content
    5. Classify intent via keyword matching
    6. Score relevance via Claude Sonnet
    7. Store results with upsert semantics

    Args:
        project_id: UUID of the project.
        time_range: Time filter for SERP search ("24h", "7d", "30d").

    Returns:
        Summary dict with total_found, unique, filtered, scored, stored counts.
    """
    progress = DiscoveryProgress(
        status="searching",
        started_at=datetime.now(UTC).isoformat(),
    )
    _set_progress(project_id, progress)

    try:
        # --- Step 1: Load config ---
        async with db_manager.session_factory() as db:
            config_stmt = select(RedditProjectConfig).where(
                RedditProjectConfig.project_id == project_id
            )
            config_result = await db.execute(config_stmt)
            config = config_result.scalar_one_or_none()

            if not config:
                raise ValueError(f"No Reddit config found for project {project_id}")

            if not config.search_keywords:
                raise ValueError(f"No search keywords configured for project {project_id}")

            brand_stmt = select(BrandConfig).where(
                BrandConfig.project_id == project_id
            )
            brand_result = await db.execute(brand_stmt)
            brand = brand_result.scalar_one_or_none()

            # Extract brand info for Claude scoring
            brand_name = brand.brand_name if brand else "Unknown Brand"
            brand_description = ""
            brand_competitors: list[str] = []
            if brand and brand.v2_schema:
                brand_description = brand.v2_schema.get("description", "")
                brand_competitors = brand.v2_schema.get("competitors", [])

            # Also use competitors from Reddit config
            if config.competitors:
                brand_competitors = list(
                    set(brand_competitors + [str(c) for c in config.competitors])
                )

            search_keywords: list[str] = [str(k) for k in config.search_keywords]
            target_subreddits: list[str] = [str(s) for s in config.target_subreddits] if config.target_subreddits else []
            banned_subreddits: list[str] = [str(s) for s in config.banned_subreddits] if config.banned_subreddits else []

        progress.total_keywords = len(search_keywords)

        # --- Step 2: Search SerpAPI ---
        serpapi = await get_serpapi()
        all_posts: list[SerpResult] = []

        for keyword in search_keywords:
            try:
                results = await serpapi.search(
                    keyword=keyword,
                    subreddits=target_subreddits if target_subreddits else None,
                    time_range=time_range,
                )
                # Tag each result with the keyword that found it
                for r in results:
                    r.search_keyword = keyword
                all_posts.extend(results)
            except Exception as e:
                logger.error(
                    "SerpAPI search failed for keyword",
                    extra={"keyword": keyword, "error": str(e)},
                )

            progress.keywords_searched += 1
            progress.total_posts_found = len(all_posts)

        logger.info(
            "SERP search phase complete",
            extra={
                "project_id": project_id,
                "keywords": len(search_keywords),
                "total_raw_results": len(all_posts),
            },
        )

        # --- Step 3: Deduplicate ---
        unique_posts = _deduplicate_posts(all_posts)

        # --- Step 4: Filter ---
        filtered_posts = [
            p for p in unique_posts
            if not is_excluded_post(p, banned_subreddits)
        ]

        logger.info(
            "Filtering complete",
            extra={
                "project_id": project_id,
                "unique": len(unique_posts),
                "after_filter": len(filtered_posts),
                "excluded": len(unique_posts) - len(filtered_posts),
            },
        )

        if not filtered_posts:
            progress.status = "complete"
            progress.completed_at = datetime.now(UTC).isoformat()
            return {
                "total_found": len(all_posts),
                "unique": len(unique_posts),
                "filtered": len(filtered_posts),
                "scored": 0,
                "stored": 0,
            }

        # --- Step 5: Intent classification ---
        intent_results = [
            classify_intent(post, brand_competitors) for post in filtered_posts
        ]

        # --- Step 6: Claude Sonnet scoring ---
        progress.status = "scoring"

        def _update_scoring_progress(scored: int, total: int) -> None:
            progress.posts_scored = scored

        claude = ClaudeClient(api_key=get_api_key())
        scoring_results = await score_posts_batch(
            posts=filtered_posts,
            claude_client=claude,
            brand_name=brand_name,
            brand_description=brand_description,
            competitors=brand_competitors,
            on_progress=_update_scoring_progress,
        )
        await claude.close()

        # --- Step 7: Store results ---
        progress.status = "storing"

        async with db_manager.session_factory() as db:
            stored_count = await store_discovered_posts(
                project_id=project_id,
                posts=filtered_posts,
                intent_results=intent_results,
                scoring_results=scoring_results,
                keywords_used=search_keywords,
                db=db,
            )

        progress.posts_stored = stored_count
        progress.status = "complete"
        progress.completed_at = datetime.now(UTC).isoformat()

        summary = {
            "total_found": len(all_posts),
            "unique": len(unique_posts),
            "filtered": len(filtered_posts),
            "scored": len(scoring_results),
            "stored": stored_count,
        }

        logger.info(
            "Discovery pipeline complete",
            extra={"project_id": project_id, **summary},
        )

        return summary

    except Exception as e:
        logger.error(
            "Discovery pipeline failed",
            extra={
                "project_id": project_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        progress.status = "failed"
        progress.error = str(e)
        progress.completed_at = datetime.now(UTC).isoformat()
        raise
