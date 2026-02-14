"""Blog content generation pipeline orchestrator.

Orchestrates the brief → write → check pipeline for each approved blog post
with concurrency control. Designed to be called from a FastAPI BackgroundTask.

Pipeline per post:
1. Set content_status='generating', fetch POP brief (page_not_built_yet=True),
   store as pop_brief JSONB
2. Call Claude via build_blog_content_prompt, parse JSON response into
   title/meta_description/content
3. Run quality checks (reuse content_quality.py), store qa_results
4. Set content_status='complete'

Key difference from content_generation.py: content is stored directly on
BlogPost (title, meta_description, content) not in a separate PageContent table.
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import db_manager
from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, CompletionResult, get_api_key
from app.models.blog import (
    BlogCampaign,
    BlogPost,
    CampaignStatus,
    ContentStatus,
)
from app.models.brand_config import BrandConfig
from app.models.content_brief import ContentBrief
from app.services.content_quality import (
    QualityResult,
    _check_ai_openers,
    _check_banned_words,
    _check_competitor_names,
    _check_em_dashes,
    _check_negation_contrast,
    _check_rhetorical_questions,
    _check_tier1_ai_words,
    _check_tier2_ai_words,
    _check_triplet_lists,
)
from app.services.content_writing import (
    CONTENT_WRITING_MAX_TOKENS,
    CONTENT_WRITING_MODEL,
    CONTENT_WRITING_TEMPERATURE,
    CONTENT_WRITING_TIMEOUT,
    build_blog_content_prompt,
)

logger = get_logger(__name__)

# Blog content requires 3 fields (vs 4 for collection pages)
BLOG_CONTENT_KEYS = {"page_title", "meta_description", "content"}

# Content fields to check for blog QA
BLOG_CONTENT_FIELDS = ("title", "meta_description", "content")


@dataclass
class BlogPipelinePostResult:
    """Result of processing a single blog post through the pipeline."""

    post_id: str
    keyword: str
    success: bool
    error: str | None = None
    skipped: bool = False


@dataclass
class BlogPipelineResult:
    """Result of running the blog content generation pipeline for a campaign."""

    campaign_id: str
    total_posts: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    post_results: list[BlogPipelinePostResult] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""


async def run_blog_content_pipeline(
    campaign_id: str,
    db: AsyncSession,  # noqa: ARG001 — kept for interface consistency
    force_refresh: bool = False,
    refresh_briefs: bool = False,
) -> BlogPipelineResult:
    """Run the blog content generation pipeline for all approved posts in a campaign.

    Processes each post through: brief → write → check. Uses asyncio.Semaphore
    for concurrency control (CONTENT_GENERATION_CONCURRENCY env var, default 1).

    Designed to be called from a FastAPI BackgroundTask — creates its own
    database sessions per-post for isolation.

    Args:
        campaign_id: UUID of the blog campaign.
        db: AsyncSession (unused — kept for interface consistency with callers).
        force_refresh: If True, regenerate content even for posts with
            content_status='complete'.
        refresh_briefs: If True, also re-fetch POP briefs (costs API credits).

    Returns:
        BlogPipelineResult with per-post results and aggregate counts.
    """
    settings = get_settings()
    concurrency = settings.content_generation_concurrency

    result = BlogPipelineResult(
        campaign_id=campaign_id,
        started_at=datetime.now(UTC).isoformat(),
    )

    logger.info(
        "Starting blog content generation pipeline",
        extra={
            "campaign_id": campaign_id,
            "concurrency": concurrency,
            "force_refresh": force_refresh,
        },
    )

    # Load approved posts and brand config in a read-only session
    async with db_manager.session_factory() as session:
        posts_data = await _load_approved_posts(session, campaign_id)
        brand_config = await _load_brand_config(session, campaign_id)

    if not posts_data:
        logger.info(
            "No approved posts found for blog content generation",
            extra={"campaign_id": campaign_id},
        )
        result.completed_at = datetime.now(UTC).isoformat()
        return result

    result.total_posts = len(posts_data)

    logger.info(
        "Found approved posts for blog content generation",
        extra={
            "campaign_id": campaign_id,
            "total_posts": result.total_posts,
        },
    )

    # Process posts with concurrency control
    semaphore = asyncio.Semaphore(concurrency)

    async def _process_with_semaphore(
        post_data: dict[str, Any],
    ) -> BlogPipelinePostResult:
        async with semaphore:
            return await _process_single_post(
                post_data=post_data,
                brand_config=brand_config,
                force_refresh=force_refresh,
                refresh_briefs=refresh_briefs,
            )

    tasks = [_process_with_semaphore(pd) for pd in posts_data]
    post_results = await asyncio.gather(*tasks)

    # Aggregate results
    for pr in post_results:
        result.post_results.append(pr)
        if pr.skipped:
            result.skipped += 1
        elif pr.success:
            result.succeeded += 1
        else:
            result.failed += 1

    result.completed_at = datetime.now(UTC).isoformat()

    # Update campaign status to 'review' when all posts complete
    await _update_campaign_status(campaign_id)

    logger.info(
        "Blog content generation pipeline complete",
        extra={
            "campaign_id": campaign_id,
            "total": result.total_posts,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "skipped": result.skipped,
        },
    )

    return result


async def _load_approved_posts(
    db: AsyncSession,
    campaign_id: str,
) -> list[dict[str, Any]]:
    """Load all approved blog posts for a campaign.

    Returns lightweight dicts so we can process each post in its own session.
    """
    stmt = select(BlogPost).where(
        BlogPost.campaign_id == campaign_id,
        BlogPost.is_approved.is_(True),
    )
    result = await db.execute(stmt)
    posts = result.scalars().all()

    posts_data: list[dict[str, Any]] = []
    for post in posts:
        posts_data.append(
            {
                "post_id": post.id,
                "campaign_id": post.campaign_id,
                "keyword": post.primary_keyword,
                "url_slug": post.url_slug,
                "existing_content_status": post.content_status,
            }
        )

    return posts_data


async def _load_brand_config(
    db: AsyncSession,
    campaign_id: str,
) -> dict[str, Any]:
    """Load brand config for the campaign's project.

    Returns empty dict if no brand config exists (services degrade gracefully).
    """
    stmt = (
        select(BrandConfig)
        .join(BlogCampaign, BlogCampaign.project_id == BrandConfig.project_id)
        .where(BlogCampaign.id == campaign_id)
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config is None:
        logger.warning(
            "No brand config found for campaign's project",
            extra={"campaign_id": campaign_id},
        )
        return {}

    return config.v2_schema or {}


async def _process_single_post(
    post_data: dict[str, Any],
    brand_config: dict[str, Any],
    force_refresh: bool,
    refresh_briefs: bool = False,
) -> BlogPipelinePostResult:
    """Process a single blog post through the brief → write → check pipeline.

    Creates its own database session for error isolation — if this post fails,
    the session is rolled back without affecting other posts.
    """
    post_id: str = post_data["post_id"]
    keyword: str = post_data["keyword"]
    url_slug: str = post_data["url_slug"]
    existing_status: str = post_data["existing_content_status"]

    # Skip posts that already have complete content (unless force_refresh)
    if not force_refresh and existing_status == ContentStatus.COMPLETE.value:
        logger.info(
            "Skipping blog post with complete content",
            extra={"post_id": post_id, "keyword": keyword[:50]},
        )
        return BlogPipelinePostResult(
            post_id=post_id,
            keyword=keyword,
            success=True,
            skipped=True,
        )

    logger.info(
        "Processing blog post through content pipeline",
        extra={"post_id": post_id, "keyword": keyword[:50]},
    )

    try:
        async with db_manager.session_factory() as db:
            # Re-load the BlogPost in this session
            stmt = select(BlogPost).where(BlogPost.id == post_id)
            result = await db.execute(stmt)
            blog_post = result.scalar_one_or_none()

            if blog_post is None:
                return BlogPipelinePostResult(
                    post_id=post_id,
                    keyword=keyword,
                    success=False,
                    error="BlogPost not found",
                )

            # --- Step 1: Set generating status + fetch POP brief ---
            blog_post.content_status = ContentStatus.GENERATING.value
            await db.commit()

            content_brief = await _fetch_blog_brief(
                db=db,
                blog_post=blog_post,
                keyword=keyword,
                url_slug=url_slug,
                refresh_briefs=refresh_briefs,
            )

            # --- Step 2: Generate content via Claude ---
            write_result = await _generate_blog_content(
                db=db,
                blog_post=blog_post,
                keyword=keyword,
                brand_config=brand_config,
                content_brief=content_brief,
            )

            if not write_result["success"]:
                blog_post.content_status = ContentStatus.FAILED.value
                blog_post.qa_results = {"error": write_result["error"]}
                await db.commit()
                return BlogPipelinePostResult(
                    post_id=post_id,
                    keyword=keyword,
                    success=False,
                    error=write_result["error"],
                )

            # --- Step 3: Run quality checks ---
            qa_result = _run_blog_quality_checks(blog_post, brand_config)
            blog_post.qa_results = qa_result.to_dict()

            # --- Step 4: Mark complete ---
            blog_post.content_status = ContentStatus.COMPLETE.value
            await db.commit()

            logger.info(
                "Blog post content generation complete",
                extra={
                    "post_id": post_id,
                    "keyword": keyword[:50],
                    "qa_passed": qa_result.passed,
                },
            )

            return BlogPipelinePostResult(
                post_id=post_id,
                keyword=keyword,
                success=True,
            )

    except Exception as exc:
        logger.error(
            "Blog content pipeline failed for post",
            extra={
                "post_id": post_id,
                "keyword": keyword[:50],
                "error": str(exc),
            },
            exc_info=True,
        )

        # Mark as failed in a new session (previous may be broken)
        try:
            async with db_manager.session_factory() as err_db:
                err_stmt = select(BlogPost).where(BlogPost.id == post_id)
                err_result = await err_db.execute(err_stmt)
                post = err_result.scalar_one_or_none()
                if post is not None:
                    post.content_status = ContentStatus.FAILED.value
                    post.qa_results = {"error": str(exc)}
                    await err_db.commit()
        except Exception:
            logger.error(
                "Failed to mark blog post as failed after pipeline error",
                extra={"post_id": post_id},
                exc_info=True,
            )

        return BlogPipelinePostResult(
            post_id=post_id,
            keyword=keyword,
            success=False,
            error=str(exc),
        )


async def _fetch_blog_brief(
    db: AsyncSession,
    blog_post: BlogPost,
    keyword: str,
    url_slug: str,
    refresh_briefs: bool,
) -> ContentBrief | None:
    """Fetch POP content brief for a blog post with page_not_built_yet=True.

    Blog posts don't have a CrawledPage, so we pass the url_slug as target_url.
    The POP brief data is stored in blog_post.pop_brief as JSONB.

    Returns the ContentBrief if available, None otherwise.
    """
    # Check for cached brief on the blog post
    if not refresh_briefs and blog_post.pop_brief:
        logger.info(
            "Using cached POP brief from blog post",
            extra={"post_id": blog_post.id, "keyword": keyword[:50]},
        )
        # Build a lightweight ContentBrief-like object from cached data
        return _brief_from_cached(db, blog_post.pop_brief)

    try:
        # Use POP client directly for blog posts since there's no CrawledPage
        from app.integrations.pop import get_pop_client

        pop_client = await get_pop_client()

        logger.info(
            "Fetching POP brief for blog post",
            extra={
                "post_id": blog_post.id,
                "keyword": keyword[:50],
                "client_type": type(pop_client).__name__,
            },
        )

        from app.integrations.pop import POPMockClient

        if isinstance(pop_client, POPMockClient):
            task_result = await pop_client.get_terms(
                keyword=keyword,
                url=url_slug,
            )
            if not task_result.success:
                logger.warning(
                    "POP brief fetch failed for blog post",
                    extra={"post_id": blog_post.id, "error": task_result.error},
                )
                return None
            response_data = task_result.data or {}
        else:
            from app.services.pop_content_brief import _run_real_3step_flow

            response_data, _ = await _run_real_3step_flow(pop_client, keyword, url_slug)

        # Store raw POP brief on blog post
        blog_post.pop_brief = response_data
        await db.flush()

        # Parse into ContentBrief-like structure for prompt building
        return _brief_from_cached(db, response_data)

    except Exception as exc:
        logger.warning(
            "POP brief fetch failed for blog post, continuing without brief",
            extra={
                "post_id": blog_post.id,
                "keyword": keyword[:50],
                "error": str(exc),
            },
        )
        return None


def _brief_from_cached(db: AsyncSession, data: dict[str, Any]) -> ContentBrief:  # noqa: ARG001
    """Build a transient ContentBrief from cached POP data.

    This creates an in-memory ContentBrief (not persisted to DB) from the
    blog post's pop_brief JSONB. Used so build_blog_content_prompt can read
    LSI terms, related searches, etc.
    """
    from app.services.pop_content_brief import (
        _parse_competitors,
        _parse_heading_targets,
        _parse_keyword_targets,
        _parse_lsi_terms,
        _parse_page_score,
        _parse_related_questions,
        _parse_related_searches,
        _parse_word_count_range,
        _parse_word_count_target,
    )

    brief = ContentBrief.__new__(ContentBrief)
    brief.lsi_terms = _parse_lsi_terms(data)
    brief.related_searches = _parse_related_searches(data)
    brief.word_count_target = _parse_word_count_target(data)
    brief.competitors = _parse_competitors(data)
    brief.related_questions = _parse_related_questions(data)
    brief.heading_targets = _parse_heading_targets(data)
    brief.keyword_targets = _parse_keyword_targets(data)
    brief.word_count_min, brief.word_count_max = _parse_word_count_range(data)
    brief.page_score_target = _parse_page_score(data)
    brief.raw_response = data
    return brief


async def _generate_blog_content(
    db: AsyncSession,
    blog_post: BlogPost,
    keyword: str,
    brand_config: dict[str, Any],
    content_brief: ContentBrief | None,
) -> dict[str, Any]:
    """Generate blog content via Claude and store on BlogPost.

    Returns dict with 'success' bool and optionally 'error' string.
    """
    # Build prompts
    prompts = build_blog_content_prompt(blog_post, keyword, brand_config, content_brief)

    # Call Claude
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

    logger.info(
        "Claude blog content call complete",
        extra={
            "post_id": blog_post.id,
            "success": result.success,
            "duration_ms": round(duration_ms),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        },
    )

    if not result.success:
        return {"success": False, "error": f"Claude API error: {result.error}"}

    # Parse JSON response (3 keys for blog: page_title, meta_description, content)
    parsed = _parse_blog_content_json(result.text or "")
    if parsed is None:
        return {
            "success": False,
            "error": "Failed to parse Claude response as valid blog content JSON",
        }

    # Apply parsed content to BlogPost
    blog_post.title = parsed["page_title"]
    blog_post.meta_description = parsed["meta_description"]
    blog_post.content = parsed["content"]
    await db.flush()

    return {"success": True}


def _parse_blog_content_json(text: str) -> dict[str, str] | None:
    """Parse Claude's response as JSON with the 3 required blog content keys.

    Handles markdown code fences and extracts JSON. Returns None if invalid.
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

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    # Validate required keys exist
    if not BLOG_CONTENT_KEYS.issubset(parsed.keys()):
        return None

    return {k: str(v) for k, v in parsed.items() if k in BLOG_CONTENT_KEYS}


def _run_blog_quality_checks(
    blog_post: BlogPost,
    brand_config: dict[str, Any],
) -> QualityResult:
    """Run deterministic quality checks on blog post content.

    Reuses the individual check functions from content_quality.py but operates
    on BlogPost fields (title, meta_description, content) instead of PageContent
    fields (page_title, meta_description, top_description, bottom_description).
    """
    # Gather field values
    fields: dict[str, str] = {}
    for field_name in BLOG_CONTENT_FIELDS:
        value = getattr(blog_post, field_name, None)
        if value:
            fields[field_name] = value

    issues = []

    # Run all checks from content_quality.py
    issues.extend(_check_banned_words(fields, brand_config))
    issues.extend(_check_em_dashes(fields))
    issues.extend(_check_ai_openers(fields))
    issues.extend(_check_triplet_lists(fields))
    issues.extend(_check_rhetorical_questions(fields))
    issues.extend(_check_tier1_ai_words(fields))
    issues.extend(_check_tier2_ai_words(fields))
    issues.extend(_check_negation_contrast(fields))
    issues.extend(_check_competitor_names(fields, brand_config))

    return QualityResult(
        passed=len(issues) == 0,
        issues=issues,
        checked_at=datetime.now(UTC).isoformat(),
    )


async def _update_campaign_status(campaign_id: str) -> None:
    """Update campaign status to 'review' when all posts are complete.

    Checks if every approved post has content_status='complete'. If so,
    transitions the campaign from 'writing' to 'review'.
    """
    try:
        async with db_manager.session_factory() as db:
            stmt = (
                select(BlogCampaign)
                .where(BlogCampaign.id == campaign_id)
                .options(selectinload(BlogCampaign.posts))
            )
            result = await db.execute(stmt)
            campaign = result.scalar_one_or_none()

            if campaign is None:
                return

            approved_posts = [p for p in campaign.posts if p.is_approved]
            if not approved_posts:
                return

            all_complete = all(
                p.content_status == ContentStatus.COMPLETE.value for p in approved_posts
            )

            if all_complete:
                campaign.status = CampaignStatus.REVIEW.value
                await db.commit()
                logger.info(
                    "Campaign status updated to review",
                    extra={"campaign_id": campaign_id},
                )
    except Exception:
        logger.error(
            "Failed to update campaign status",
            extra={"campaign_id": campaign_id},
            exc_info=True,
        )
