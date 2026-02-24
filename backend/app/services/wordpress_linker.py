"""WordPress blog internal linking orchestration service.

7-step wizard: Connect → Import → Analyze → Label → Plan → Review → Export.

Maps WordPress posts to existing DB models (CrawledPage, PageContent, etc.)
and reuses the existing link planning pipeline for per-silo link generation.
"""

import asyncio
import json
import re
from itertools import combinations
from typing import Any, cast

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_api_key
from app.integrations.wordpress import WordPressClient, WPSiteInfo
from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.internal_link import InternalLink
from app.models.keyword_cluster import ClusterPage, KeywordCluster
from app.models.page_content import ContentStatus, PageContent
from app.models.page_keywords import PageKeywords
from app.models.project import Project
from app.services.link_injection import LinkInjector, LinkValidator
from app.services.link_planning import (
    AnchorTextSelector,
    _LinkProxy,
    _load_bottom_description,
    _load_page_content_text,
    _load_word_counts,
    calculate_budget,
    select_targets_onboarding,
)
from app.services.pop_content_brief import fetch_content_brief

logger = get_logger(__name__)

# Module-level progress dict: job_id → progress state
_wp_progress: dict[str, dict[str, Any]] = {}

# Concurrency limits
POP_SEMAPHORE_LIMIT = 3
EXPORT_SEMAPHORE_LIMIT = 5

# LLM settings for blog labeling
LABEL_LLM_MODEL = "claude-sonnet-4-5"
LABEL_LLM_MAX_TOKENS = 4000
LABEL_LLM_TEMPERATURE = 0.1


def get_wp_progress(job_id: str) -> dict[str, Any] | None:
    """Return progress for a job, or None if not found."""
    return _wp_progress.get(job_id)


# =============================================================================
# BLOG-SPECIFIC LABELING PROMPTS
# =============================================================================

BLOG_TAXONOMY_SYSTEM_PROMPT = """You are a content strategist analyzing blog posts. Generate a taxonomy of TOPIC labels for internal linking silos. Labels should represent distinct content themes/topics (e.g., "seo-strategy", "content-marketing", "technical-seo", "link-building").

Focus on topical clusters that benefit from internal linking. Each label should group posts that readers would naturally want to explore together.

Rules:
1. Use lowercase, hyphenated names (e.g., "content-marketing")
2. Create 5-15 labels that cover the blog's main topics
3. Each label should apply to at least 2 posts (preferably 3+)
4. Labels should be specific enough to be meaningful but broad enough to group multiple posts
5. Focus on WHAT the posts are about, not their format

Respond ONLY with valid JSON:
{
  "labels": [
    {
      "name": "label-name",
      "description": "What topic this covers",
      "examples": ["example post topics"]
    }
  ],
  "reasoning": "Brief explanation of the taxonomy structure"
}"""

BLOG_ASSIGNMENT_SYSTEM_PROMPT = """You are a content strategist. Assign 2-4 topic labels to this blog post from the taxonomy. Consider: the POP primary keyword, keyword variations, headings, and content theme.

The PRIMARY label (first in your list) determines the post's silo group for internal linking. Choose the most relevant topic as the primary label.

Rules:
1. Assign exactly 2-4 labels from the taxonomy
2. The FIRST label is the primary (most relevant) topic
3. Additional labels represent secondary topics covered
4. ONLY use labels from the provided taxonomy

Respond ONLY with valid JSON:
{
  "labels": ["primary-label", "secondary-label"],
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation"
}"""


# =============================================================================
# STEP 1: CONNECT
# =============================================================================


async def step1_connect(
    site_url: str,
    username: str,
    app_password: str,
) -> WPSiteInfo:
    """Validate WordPress credentials and return site info."""
    client = WordPressClient(site_url, username, app_password)
    try:
        return await client.validate_credentials()
    finally:
        await client.close()


# =============================================================================
# STEP 2: IMPORT
# =============================================================================


async def step2_import(
    db: AsyncSession,
    site_url: str,
    username: str,
    app_password: str,
    job_id: str,
    title_filter: list[str] | None = None,
    post_status: str = "publish",
    existing_project_id: str | None = None,
) -> dict[str, Any]:
    """Import WordPress posts into Project + CrawledPage + PageContent records.

    If existing_project_id is provided, WP posts are added to that project
    alongside its existing onboarding pages. Otherwise a new standalone project is created.
    """
    progress = {
        "step": "import",
        "step_label": "Fetching posts from WordPress...",
        "status": "running",
        "current": 0,
        "total": 0,
    }
    _wp_progress[job_id] = progress

    try:
        # Fetch posts from WordPress (can take several seconds for large sites)
        client = WordPressClient(site_url, username, app_password)
        try:
            posts, total_fetched = await client.fetch_all_posts(
                title_filter=title_filter, post_status=post_status
            )
        finally:
            await client.close()

        progress["step_label"] = "Saving posts to database"
        progress["total"] = len(posts)

        if not posts:
            progress["status"] = "complete"
            progress["result"] = {
                "project_id": None,
                "posts_imported": 0,
                "total_fetched": total_fetched,
                "title_filter": title_filter,
            }
            return cast(dict[str, Any], progress["result"])

        # Use existing project or create a new one
        if existing_project_id:
            project = await db.get(Project, existing_project_id)
            if not project:
                raise ValueError(f"Project {existing_project_id} not found")
            # Store WP metadata on the existing project
            if "wordpress" not in (project.phase_status or {}):
                project.phase_status = {**(project.phase_status or {}), "wordpress": {}}
            project.phase_status["wordpress"]["source"] = "wordpress"
            project.phase_status["wordpress"]["import_count"] = len(posts)
            flag_modified(project, "phase_status")
            await db.flush()
        else:
            project = Project(
                name=f"WP Blog: {site_url}",
                site_url=site_url,
                status="active",
                phase_status={
                    "wordpress": {"source": "wordpress", "import_count": len(posts)}
                },
            )
            db.add(project)
            await db.flush()

        # Create CrawledPage + PageContent for each post
        for i, post in enumerate(posts):
            page = CrawledPage(
                project_id=project.id,
                normalized_url=post.url,
                raw_url=str(post.id),  # Store WP post ID for export
                title=post.title,
                source="wordpress",
                status=CrawlStatus.COMPLETED.value,
                body_content=post.content_html,
                word_count=post.word_count,
                headings=_extract_headings(post.content_html),
                labels=post.tag_names if post.tag_names else [],
            )
            db.add(page)
            await db.flush()

            # Create PageContent with post body as bottom_description
            content = PageContent(
                crawled_page_id=page.id,
                page_title=post.title,
                bottom_description=post.content_html,
                word_count=post.word_count,
                status=ContentStatus.COMPLETE.value,
            )
            db.add(content)

            progress["current"] = i + 1

        await db.commit()

        result = {"project_id": project.id, "posts_imported": len(posts)}
        progress["status"] = "complete"
        progress["result"] = result

        logger.info(
            "WordPress import complete",
            extra={"project_id": project.id, "posts": len(posts)},
        )
        return result

    except Exception as e:
        progress["status"] = "failed"
        progress["error"] = str(e)
        logger.error("WordPress import failed", exc_info=True)
        raise


# =============================================================================
# STEP 3: ANALYZE (POP)
# =============================================================================


async def step3_analyze(
    db: AsyncSession,
    project_id: str,
    job_id: str,
) -> dict[str, Any]:
    """Run POP content brief analysis on all imported posts."""
    progress = {
        "step": "analyze",
        "step_label": "Analyzing posts with POP",
        "status": "running",
        "current": 0,
        "total": 0,
    }
    _wp_progress[job_id] = progress

    try:
        # Load all pages for the project
        stmt = select(CrawledPage).where(
            CrawledPage.project_id == project_id,
            CrawledPage.source == "wordpress",
        )
        result = await db.execute(stmt)
        pages = list(result.scalars().all())
        progress["total"] = len(pages)

        semaphore = asyncio.Semaphore(POP_SEMAPHORE_LIMIT)
        success_count = 0
        fail_count = 0

        async def analyze_page(page: CrawledPage) -> None:
            nonlocal success_count, fail_count
            async with semaphore:
                try:
                    # Use post title as the keyword seed
                    keyword = page.title or "blog post"
                    target_url = page.normalized_url

                    brief_result = await fetch_content_brief(
                        db=db,
                        crawled_page=page,
                        keyword=keyword,
                        target_url=target_url,
                    )

                    if brief_result.success:
                        # Auto-approve the keyword (POP primary keyword = title)
                        pk_stmt = select(PageKeywords).where(
                            PageKeywords.crawled_page_id == page.id
                        )
                        pk_result = await db.execute(pk_stmt)
                        pk = pk_result.scalar_one_or_none()
                        if pk:
                            pk.is_approved = True

                        success_count += 1
                    else:
                        fail_count += 1
                        logger.warning(
                            "POP analysis failed for page",
                            extra={"page_id": page.id, "error": brief_result.error},
                        )

                except Exception:
                    fail_count += 1
                    logger.error(
                        "POP analysis error",
                        extra={"page_id": page.id},
                        exc_info=True,
                    )
                finally:
                    progress["current"] = success_count + fail_count

        # Run all analyses concurrently with semaphore
        await asyncio.gather(*[analyze_page(page) for page in pages])
        await db.commit()

        result_data = {
            "analyzed": success_count,
            "failed": fail_count,
            "total": len(pages),
        }
        progress["status"] = "complete"
        progress["result"] = result_data

        logger.info("POP analysis complete", extra=result_data)
        return result_data

    except Exception as e:
        progress["status"] = "failed"
        progress["error"] = str(e)
        logger.error("POP analysis failed", exc_info=True)
        raise


# =============================================================================
# STEP 4: LABEL (TAXONOMY + ASSIGNMENT + SILO CREATION)
# =============================================================================


async def step4_label(
    db: AsyncSession,
    project_id: str,
    job_id: str,
) -> dict[str, Any]:
    """Generate blog topic taxonomy, assign labels, and create silo groups."""
    progress = {
        "step": "label",
        "step_label": "Generating topic taxonomy",
        "status": "running",
        "current": 0,
        "total": 3,  # 3 sub-steps: taxonomy, assign, silo creation
    }
    _wp_progress[job_id] = progress

    try:
        # Load pages with their POP data
        stmt = (
            select(CrawledPage)
            .options(
                joinedload(CrawledPage.content_brief),
                joinedload(CrawledPage.keywords),
            )
            .where(
                CrawledPage.project_id == project_id,
                CrawledPage.source == "wordpress",
            )
        )
        result = await db.execute(stmt)
        pages = list(result.unique().scalars().all())

        if not pages:
            progress["status"] = "failed"
            progress["error"] = "No pages found"
            return {"error": "No pages found"}

        # --- Sub-step A: Generate blog topic taxonomy ---
        progress["step_label"] = "Generating topic taxonomy"
        progress["current"] = 0

        taxonomy = await _generate_blog_taxonomy(db, project_id, pages)
        if not taxonomy:
            progress["status"] = "failed"
            progress["error"] = "Failed to generate taxonomy"
            return {"error": "Failed to generate taxonomy"}

        progress["current"] = 1

        # --- Sub-step B: Assign labels to each post ---
        progress["step_label"] = "Assigning labels to posts"

        assignments = await _assign_blog_labels(db, pages, taxonomy)
        await db.flush()
        progress["current"] = 2

        # --- Sub-step C: Create silo groups ---
        progress["step_label"] = "Creating silo groups"

        silo_stats = await _create_silo_groups(db, project_id, pages)
        await db.commit()
        progress["current"] = 3

        result_data = {
            "taxonomy_labels": len(taxonomy["labels"]),
            "posts_labeled": sum(1 for a in assignments if a["success"]),
            "silo_groups": len(silo_stats),
        }
        progress["status"] = "complete"
        progress["result"] = result_data

        logger.info("Blog labeling complete", extra=result_data)
        return result_data

    except Exception as e:
        progress["status"] = "failed"
        progress["error"] = str(e)
        logger.error("Blog labeling failed", exc_info=True)
        raise


async def _generate_blog_taxonomy(
    db: AsyncSession,
    project_id: str,
    pages: list[CrawledPage],
) -> dict[str, Any] | None:
    """Generate a blog-specific topic taxonomy using Claude."""
    # Build page summaries with POP data
    page_summaries = []
    for page in pages:
        summary = f"- URL: {page.normalized_url}\n  Title: {page.title or 'Untitled'}"

        # Add POP primary keyword if available
        if page.keywords and page.keywords.primary_keyword:
            summary += f"\n  Primary keyword: {page.keywords.primary_keyword}"

        # Add POP keyword targets (top 5)
        if page.content_brief and page.content_brief.keyword_targets:
            targets = page.content_brief.keyword_targets[:5]
            kw_list = [
                t.get("keyword", "") if isinstance(t, dict) else str(t) for t in targets
            ]
            if kw_list:
                summary += f"\n  Keyword targets: {', '.join(kw_list)}"

        # Add content excerpt
        if page.body_content:
            text = re.sub(r"<[^>]+>", " ", page.body_content)
            excerpt = " ".join(text.split()[:60])  # ~300 chars
            summary += f"\n  Excerpt: {excerpt}"

        if page.word_count:
            summary += f"\n  Word count: {page.word_count}"

        page_summaries.append(summary)

    # Check for existing collection page labels in the same project
    # (onboarding pages + cluster pages with approved content)
    onboarding_labels_section = ""
    onboarding_stmt = (
        select(CrawledPage)
        .outerjoin(PageContent, PageContent.crawled_page_id == CrawledPage.id)
        .where(
            CrawledPage.project_id == project_id,
            or_(
                CrawledPage.source == "onboarding",
                and_(
                    CrawledPage.source == "cluster",
                    PageContent.is_approved.is_(True),
                ),
            ),
        )
    )
    onboarding_result = await db.execute(onboarding_stmt)
    onboarding_pages = list(onboarding_result.scalars().all())

    if onboarding_pages:
        existing_labels: set[str] = set()
        for op in onboarding_pages:
            if op.labels:
                existing_labels.update(op.labels)
        if existing_labels:
            onboarding_labels_section = f"""

IMPORTANT: This blog exists alongside collection/product pages that already use these labels:
{", ".join(sorted(existing_labels))}

You MUST reuse these existing labels where they are topically relevant to blog posts. This creates label overlap between blog posts and collection pages, which enables cross-linking. You may also create new labels for blog topics not covered by existing labels."""

    user_prompt = f"""Analyze these {len(pages)} blog posts and generate a taxonomy of topic labels for internal linking silos:

{chr(10).join(page_summaries)}
{onboarding_labels_section}

Generate a taxonomy that captures the main topics. Each label should group posts that readers would naturally want to explore together."""

    client = ClaudeClient(api_key=get_api_key())
    try:
        completion = await client.complete(
            user_prompt=user_prompt,
            system_prompt=BLOG_TAXONOMY_SYSTEM_PROMPT,
            model=LABEL_LLM_MODEL,
            temperature=LABEL_LLM_TEMPERATURE,
            max_tokens=LABEL_LLM_MAX_TOKENS,
        )
    finally:
        await client.close()

    if not completion.success:
        logger.error(
            "Blog taxonomy generation failed", extra={"error": completion.error}
        )
        return None

    try:
        response_text = completion.text or ""
        json_text = _extract_json(response_text)
        parsed: dict[str, Any] = json.loads(json_text)

        # Store taxonomy in project phase_status
        project = await db.get(Project, project_id)
        if project:
            if "wordpress" not in project.phase_status:
                project.phase_status["wordpress"] = {}
            project.phase_status["wordpress"]["taxonomy"] = parsed
            flag_modified(project, "phase_status")
            await db.flush()

        logger.info(
            "Blog taxonomy generated",
            extra={
                "label_count": len(parsed.get("labels", [])),
                "labels": [label["name"] for label in parsed.get("labels", [])],
            },
        )
        return parsed

    except json.JSONDecodeError as e:
        logger.error("Failed to parse taxonomy response", extra={"error": str(e)})
        return None


async def _assign_blog_labels(
    db: AsyncSession,
    pages: list[CrawledPage],
    taxonomy: dict[str, Any],
) -> list[dict[str, Any]]:
    """Assign 2-4 topic labels to each blog post using Claude."""
    taxonomy_desc = "\n".join(
        f"- {label['name']}: {label.get('description', '')}"
        for label in taxonomy.get("labels", [])
    )
    valid_labels = {label["name"] for label in taxonomy.get("labels", [])}

    assignments: list[dict[str, Any]] = []

    client = ClaudeClient(api_key=get_api_key())
    try:
        for page in pages:
            # Build page info with POP data
            page_info = f"Title: {page.title or 'Untitled'}\nURL: {page.normalized_url}"

            if page.keywords and page.keywords.primary_keyword:
                page_info += f"\nPrimary keyword: {page.keywords.primary_keyword}"

            if page.content_brief and page.content_brief.keyword_targets:
                targets = page.content_brief.keyword_targets[:5]
                kw_list = [
                    t.get("keyword", "") if isinstance(t, dict) else str(t)
                    for t in targets
                ]
                if kw_list:
                    page_info += f"\nKeyword targets: {', '.join(kw_list)}"

            # Add headings
            if page.headings:
                h1s = page.headings.get("h1", [])
                h2s = page.headings.get("h2", [])
                if h1s:
                    page_info += f"\nH1: {', '.join(h1s[:3])}"
                if h2s:
                    page_info += f"\nH2: {', '.join(h2s[:5])}"

            # Add content excerpt (first 500 chars)
            if page.body_content:
                text = re.sub(r"<[^>]+>", " ", page.body_content)
                excerpt = " ".join(text.split()[:100])
                page_info += f"\nExcerpt: {excerpt}"

            if page.word_count:
                page_info += f"\nWord count: {page.word_count}"

            user_prompt = f"""Assign topic labels to this blog post from the taxonomy.

TAXONOMY:
{taxonomy_desc}

POST:
{page_info}

Respond with JSON only."""

            completion = await client.complete(
                user_prompt=user_prompt,
                system_prompt=BLOG_ASSIGNMENT_SYSTEM_PROMPT,
                model=LABEL_LLM_MODEL,
                temperature=0.0,
                max_tokens=500,
            )

            if not completion.success:
                assignments.append(
                    {
                        "page_id": page.id,
                        "labels": [],
                        "success": False,
                        "error": completion.error,
                    }
                )
                continue

            try:
                response_text = completion.text or ""
                json_text = _extract_json(response_text)
                parsed = json.loads(json_text)
                labels = parsed.get("labels", [])

                # Filter to valid labels only
                valid_assigned = [
                    label.strip().lower()
                    for label in labels
                    if label.strip().lower() in valid_labels
                ]

                # Ensure 2-4 labels
                if len(valid_assigned) < 2:
                    # Pad with the first available taxonomy label not already assigned
                    for tl in taxonomy.get("labels", []):
                        if tl["name"] not in valid_assigned:
                            valid_assigned.append(tl["name"])
                        if len(valid_assigned) >= 2:
                            break

                valid_assigned = valid_assigned[:4]

                # Update page labels
                page.labels = valid_assigned
                await db.flush()

                assignments.append(
                    {
                        "page_id": page.id,
                        "labels": valid_assigned,
                        "success": True,
                    }
                )

            except json.JSONDecodeError as e:
                assignments.append(
                    {
                        "page_id": page.id,
                        "labels": [],
                        "success": False,
                        "error": f"JSON parse error: {e}",
                    }
                )

    finally:
        await client.close()

    return assignments


async def _create_silo_groups(
    db: AsyncSession,
    project_id: str,
    pages: list[CrawledPage],
) -> dict[str, int]:
    """Create KeywordCluster + ClusterPage records from label assignments.

    Each unique primary label (first in labels array) becomes a silo group.
    Each post maps to its primary label's cluster.

    Returns:
        Dict mapping label name to post count in that silo.
    """
    # Collect primary labels
    label_pages: dict[str, list[CrawledPage]] = {}
    for page in pages:
        if page.labels and len(page.labels) > 0:
            primary = page.labels[0]
            if primary not in label_pages:
                label_pages[primary] = []
            label_pages[primary].append(page)

    # Create clusters and cluster pages
    silo_stats: dict[str, int] = {}
    for label_name, group_pages in label_pages.items():
        cluster = KeywordCluster(
            project_id=project_id,
            seed_keyword=label_name,
            name=label_name,
            status="approved",
        )
        db.add(cluster)
        await db.flush()

        for page in group_pages:
            cluster_page = ClusterPage(
                cluster_id=cluster.id,
                keyword=page.title or label_name,
                role="child",  # All blog posts are peers
                url_slug=page.normalized_url,
                is_approved=True,
                crawled_page_id=page.id,
            )
            db.add(cluster_page)

        silo_stats[label_name] = len(group_pages)

    await db.flush()

    logger.info(
        "Silo groups created",
        extra={"groups": len(silo_stats), "distribution": silo_stats},
    )
    return silo_stats


# =============================================================================
# STEP 5: PLAN LINKS (per silo)
# =============================================================================


async def step5_plan_links(
    db: AsyncSession,
    project_id: str,
    job_id: str,
) -> dict[str, Any]:
    """Build internal links for each silo group using the existing pipeline.

    If the project has onboarding pages (i.e., it's a mixed project), uses
    collection-aware graph building and target selection so blog posts link
    to collection pages as high-value targets.
    """
    progress = {
        "step": "plan",
        "step_label": "Planning internal links",
        "status": "running",
        "current": 0,
        "total": 0,
    }
    _wp_progress[job_id] = progress

    try:
        # Detect whether project has collection pages
        # (onboarding pages + cluster pages with approved content)
        coll_count_stmt = (
            select(func.count())
            .select_from(CrawledPage)
            .outerjoin(PageContent, PageContent.crawled_page_id == CrawledPage.id)
            .where(
                CrawledPage.project_id == project_id,
                or_(
                    CrawledPage.source == "onboarding",
                    and_(
                        CrawledPage.source == "cluster",
                        PageContent.is_approved.is_(True),
                    ),
                ),
            )
        )
        coll_count_result = await db.execute(coll_count_stmt)
        has_collection_pages = coll_count_result.scalar_one() > 0

        if has_collection_pages:
            logger.info("Mixed project detected — using collection-aware link planning")

        # Load all clusters (silo groups) for this project
        stmt = select(KeywordCluster).where(
            KeywordCluster.project_id == project_id,
        )
        result = await db.execute(stmt)
        clusters = list(result.scalars().all())
        progress["total"] = len(clusters)

        if not clusters:
            progress["status"] = "complete"
            progress["result"] = {"total_links": 0, "groups_processed": 0}
            return cast(dict[str, Any], progress["result"])

        # Pre-load collection pages if this is a mixed project
        collection_pages: list[CrawledPage] = []
        if has_collection_pages:
            coll_stmt = (
                select(CrawledPage)
                .outerjoin(PageContent, PageContent.crawled_page_id == CrawledPage.id)
                .where(
                    CrawledPage.project_id == project_id,
                    or_(
                        CrawledPage.source == "onboarding",
                        and_(
                            CrawledPage.source == "cluster",
                            PageContent.is_approved.is_(True),
                        ),
                    ),
                )
            )
            coll_result = await db.execute(coll_stmt)
            collection_pages = list(coll_result.scalars().all())

        total_links = 0
        injector = LinkInjector()
        validator = LinkValidator()
        anchor_selector = AnchorTextSelector()

        for i, cluster in enumerate(clusters):
            progress["step_label"] = f"Planning links: {cluster.name}"

            if has_collection_pages and collection_pages:
                links_in_group = await _plan_links_for_silo_with_collections(
                    db,
                    project_id,
                    cluster,
                    collection_pages,
                    injector,
                    validator,
                    anchor_selector,
                )
            else:
                links_in_group = await _plan_links_for_silo(
                    db, project_id, cluster, injector, validator, anchor_selector
                )
            total_links += links_in_group
            progress["current"] = i + 1

        await db.commit()

        result_data = {
            "total_links": total_links,
            "groups_processed": len(clusters),
        }
        progress["status"] = "complete"
        progress["result"] = result_data

        logger.info("Link planning complete", extra=result_data)
        return result_data

    except Exception as e:
        progress["status"] = "failed"
        progress["error"] = str(e)
        logger.error("Link planning failed", exc_info=True)
        raise


async def _plan_links_for_silo(
    db: AsyncSession,
    project_id: str,
    cluster: KeywordCluster,
    injector: LinkInjector,
    validator: LinkValidator,
    anchor_selector: AnchorTextSelector,
) -> int:
    """Plan and inject links for a single silo group. Returns link count."""
    # Load cluster pages with their CrawledPage data
    stmt = (
        select(ClusterPage)
        .options(joinedload(ClusterPage.crawled_page))
        .where(ClusterPage.cluster_id == cluster.id)
    )
    result = await db.execute(stmt)
    cluster_pages = [
        cp for cp in result.unique().scalars().all() if cp.crawled_page_id is not None
    ]

    if len(cluster_pages) < 2:
        logger.info(f"Silo '{cluster.name}' has <2 pages, skipping")
        return 0

    # 1. Build onboarding-style graph with label-overlap edges
    graph = _build_silo_graph(cluster_pages)

    # 2. Calculate budgets
    page_ids = [cp.crawled_page_id for cp in cluster_pages if cp.crawled_page_id]
    word_counts = await _load_word_counts(db, page_ids)
    budgets = {pid: calculate_budget(wc) for pid, wc in word_counts.items()}

    # 3. Select targets (reuse onboarding selector)
    targets_map = select_targets_onboarding(graph, budgets)

    # 4. Resolve URLs using project site_url
    project_obj = await db.get(Project, project_id)
    site_base = (project_obj.site_url or "").rstrip("/") if project_obj else ""

    # 5. Generate anchor text
    keyword_map: dict[str, str] = {}
    for page in graph["pages"]:
        pid = page["page_id"]
        kw = page.get("keyword", "")
        if kw:
            keyword_map[pid] = kw

    natural_phrases = await anchor_selector.generate_natural_phrases(keyword_map)

    usage_tracker: dict[str, dict[str, int]] = {}
    page_link_plans: dict[str, list[dict[str, Any]]] = {}

    for page in graph["pages"]:
        source_id = page["page_id"]
        page_targets = targets_map.get(source_id, [])
        planned_links: list[dict[str, Any]] = []

        source_content = await _load_page_content_text(db, source_id)

        for target in page_targets:
            target_id = target["page_id"]
            candidates = await anchor_selector.gather_candidates(target_id, db)

            if target_id in natural_phrases:
                candidates.extend(natural_phrases[target_id])

            anchor_result = anchor_selector.select_anchor(
                candidates, source_content, target_id, usage_tracker
            )

            if anchor_result is None:
                anchor_result = {
                    "anchor_text": target.get("keyword", "link"),
                    "anchor_type": "exact_match",
                    "score": 0.0,
                }

            target_url = target.get("url", "")
            if target_url and not target_url.startswith("http"):
                target_url = f"{site_base}/{target_url.lstrip('/')}"

            planned_links.append(
                {
                    **target,
                    "anchor_text": anchor_result["anchor_text"],
                    "anchor_type": anchor_result["anchor_type"],
                    "target_page_id": target_id,
                    "url": target_url,
                }
            )

        page_link_plans[source_id] = planned_links

    # 6. Inject links into content
    injection_results: list[dict[str, Any]] = []
    pages_html: dict[str, str] = {}

    for source_id, planned_links in page_link_plans.items():
        html = await _load_bottom_description(db, source_id)
        if not html:
            continue

        current_html = html
        for link_plan in planned_links:
            anchor_text = link_plan["anchor_text"]
            target_url = link_plan.get("url", "")
            target_id = link_plan["target_page_id"]

            modified_html, p_idx = injector.inject_rule_based(
                current_html, anchor_text, target_url
            )

            if p_idx is not None:
                current_html = modified_html
                injection_results.append(
                    {
                        "source_page_id": source_id,
                        "target_page_id": target_id,
                        "anchor_text": anchor_text,
                        "anchor_type": link_plan["anchor_type"],
                        "placement_method": "rule_based",
                        "position_in_content": p_idx,
                        "is_mandatory": False,
                    }
                )
            else:
                target_keyword = link_plan.get("keyword", "")
                modified_html, p_idx = await injector.inject_llm_fallback(
                    current_html, anchor_text, target_url, target_keyword
                )
                if p_idx is not None:
                    current_html = modified_html
                    injection_results.append(
                        {
                            "source_page_id": source_id,
                            "target_page_id": target_id,
                            "anchor_text": anchor_text,
                            "anchor_type": link_plan["anchor_type"],
                            "placement_method": "llm_fallback",
                            "position_in_content": p_idx,
                            "is_mandatory": False,
                        }
                    )

        pages_html[source_id] = current_html

    # 7. Validate
    temp_links = [_LinkProxy({**r, "scope": "cluster"}) for r in injection_results]
    validation = validator.validate_links(temp_links, pages_html, "cluster")

    # 8. Persist InternalLink rows + update PageContent
    for result_dict in injection_results:
        source_id = result_dict["source_page_id"]
        link_status = "verified" if validation["passed"] else "injected"

        link = InternalLink(
            source_page_id=result_dict["source_page_id"],
            target_page_id=result_dict["target_page_id"],
            project_id=project_id,
            cluster_id=cluster.id,
            scope="cluster",
            anchor_text=result_dict["anchor_text"],
            anchor_type=result_dict["anchor_type"],
            position_in_content=result_dict.get("position_in_content"),
            is_mandatory=result_dict.get("is_mandatory", False),
            placement_method=result_dict["placement_method"],
            status=link_status,
        )
        db.add(link)

    # Update PageContent with injected HTML
    for page_id, html in pages_html.items():
        pc_stmt = select(PageContent).where(PageContent.crawled_page_id == page_id)
        pc_result = await db.execute(pc_stmt)
        pc = pc_result.scalar_one_or_none()
        if pc:
            pc.bottom_description = html

    await db.flush()

    logger.info(
        f"Silo '{cluster.name}' planned",
        extra={"links": len(injection_results), "pages": len(cluster_pages)},
    )
    return len(injection_results)


def _build_silo_graph(cluster_pages: list[ClusterPage]) -> dict[str, Any]:
    """Build an onboarding-style graph for a silo using label overlap for edge weights."""
    pages: list[dict[str, Any]] = []
    for cp in cluster_pages:
        crawled = cp.crawled_page
        if not crawled:
            continue
        pages.append(
            {
                "page_id": crawled.id,
                "keyword": crawled.title or cp.keyword,
                "url": crawled.normalized_url,
                "labels": crawled.labels or [],
                "is_priority": False,
            }
        )

    # Build edges from label overlap
    edges: list[dict[str, Any]] = []
    for a, b in combinations(pages, 2):
        labels_a = set(a.get("labels", []))
        labels_b = set(b.get("labels", []))
        overlap = len(labels_a & labels_b)
        # Always create an edge for pages in the same silo, min weight 1
        edges.append(
            {
                "source": a["page_id"],
                "target": b["page_id"],
                "weight": max(overlap, 1),
            }
        )

    return {"pages": pages, "edges": edges}


def _build_silo_graph_with_collections(
    cluster_pages: list[ClusterPage],
    collection_pages: list[CrawledPage],
) -> dict[str, Any]:
    """Build a mixed graph with WP blog nodes and onboarding collection page nodes.

    Edges:
    - WP → WP: label overlap (same as _build_silo_graph)
    - WP → collection: label overlap (one-directional — blogs link TO collections)
    - collection → WP: NEVER (collection pages are targets only)
    """
    wp_nodes: list[dict[str, Any]] = []
    for cp in cluster_pages:
        crawled = cp.crawled_page
        if not crawled:
            continue
        wp_nodes.append(
            {
                "page_id": crawled.id,
                "keyword": crawled.title or cp.keyword,
                "url": crawled.normalized_url,
                "labels": crawled.labels or [],
                "is_priority": False,
                "source": "wordpress",
            }
        )

    # Find collection pages that share labels with this silo's WP posts
    silo_labels: set[str] = set()
    for node in wp_nodes:
        silo_labels.update(node.get("labels", []))

    coll_nodes: list[dict[str, Any]] = []
    for coll_page in collection_pages:
        page_labels = set(coll_page.labels or [])
        if page_labels & silo_labels:  # Only include if there's label overlap
            coll_nodes.append(
                {
                    "page_id": coll_page.id,
                    "keyword": coll_page.title or coll_page.normalized_url,
                    "url": coll_page.normalized_url,
                    "labels": coll_page.labels or [],
                    "is_priority": bool(
                        coll_page.category
                        and coll_page.category.lower() in ("collection", "product")
                    ),
                    "source": "collection",
                }
            )

    all_nodes = wp_nodes + coll_nodes

    # Build edges — WP→WP and WP→collection only (never collection→WP)
    edges: list[dict[str, Any]] = []

    # WP → WP edges (bidirectional within silo)
    for a, b in combinations(wp_nodes, 2):
        labels_a = set(a.get("labels", []))
        labels_b = set(b.get("labels", []))
        overlap = len(labels_a & labels_b)
        edges.append(
            {
                "source": a["page_id"],
                "target": b["page_id"],
                "weight": max(overlap, 1),
            }
        )

    # WP → collection edges (one-directional)
    for wp_node in wp_nodes:
        wp_labels = set(wp_node.get("labels", []))
        for coll_node in coll_nodes:
            coll_labels = set(coll_node.get("labels", []))
            overlap = len(wp_labels & coll_labels)
            if overlap > 0:
                edges.append(
                    {
                        "source": wp_node["page_id"],
                        "target": coll_node["page_id"],
                        "weight": overlap,
                    }
                )

    return {"pages": all_nodes, "edges": edges}


def select_targets_wp_with_collections(
    graph: dict[str, Any],
    budgets: dict[str, int],
) -> dict[str, list[dict[str, Any]]]:
    """Select link targets for WP pages in a mixed graph with collection pages.

    Collection pages get a bonus score (collection_bonus=4.0 + priority_bonus=3.0).
    Budget is split: ~half for collection targets, ~half for sibling blogs.
    Only WP pages are sources — collection pages never have outbound links.
    """
    COLLECTION_BONUS = 4.0
    PRIORITY_BONUS = 3.0

    pages_by_id: dict[str, dict[str, Any]] = {p["page_id"]: p for p in graph["pages"]}

    # Build one-directional adjacency: source → {target: weight}
    adjacency: dict[str, dict[str, int]] = {p["page_id"]: {} for p in graph["pages"]}
    for edge in graph["edges"]:
        source_page = pages_by_id.get(edge["source"])
        if not source_page:
            continue
        # Only WP pages can be sources
        if source_page.get("source") == "wordpress":
            adjacency[edge["source"]][edge["target"]] = edge["weight"]
        # For WP→WP edges, also add reverse direction
        target_page = pages_by_id.get(edge["target"])
        if (
            target_page
            and target_page.get("source") == "wordpress"
            and source_page.get("source") == "wordpress"
        ):
            adjacency[edge["target"]][edge["source"]] = edge["weight"]

    inbound_counts: dict[str, int] = {p["page_id"]: 0 for p in graph["pages"]}
    result: dict[str, list[dict[str, Any]]] = {}

    for page in graph["pages"]:
        # Only WP pages are sources
        if page.get("source") != "wordpress":
            continue

        page_id = page["page_id"]
        budget = budgets.get(page_id, 3)
        neighbors = adjacency.get(page_id, {})

        if not neighbors:
            result[page_id] = []
            continue

        # Split budget: reserve slots for collection targets
        collection_targets_available = [
            tid for tid in neighbors if pages_by_id[tid].get("source") == "collection"
        ]
        collection_budget = min(len(collection_targets_available), max(1, budget // 2))

        total_inbound = sum(inbound_counts.values())
        page_count = len(graph["pages"])
        avg_inbound = total_inbound / page_count if page_count > 0 else 0.0

        # Score all targets
        scored_collection: list[tuple[float, str]] = []
        scored_blog: list[tuple[float, str]] = []

        for target_id, overlap in neighbors.items():
            target_page = pages_by_id[target_id]
            excess_inbound = inbound_counts[target_id] - avg_inbound
            diversity_penalty = max(0.0, excess_inbound * 0.5)

            if target_page.get("source") == "collection":
                # Collection page — boost score
                priority_bonus = (
                    PRIORITY_BONUS if target_page.get("is_priority") else 0.0
                )
                score = overlap + COLLECTION_BONUS + priority_bonus - diversity_penalty
                scored_collection.append((score, target_id))
            else:
                # Sibling blog post
                priority_bonus = 2.0 if target_page.get("is_priority") else 0.0
                score = overlap + priority_bonus - diversity_penalty
                scored_blog.append((score, target_id))

        scored_collection.sort(key=lambda x: (-x[0], x[1]))
        scored_blog.sort(key=lambda x: (-x[0], x[1]))

        targets: list[dict[str, Any]] = []

        # Fill collection slots first
        for score, target_id in scored_collection:
            if len(targets) >= collection_budget:
                break
            target_page = pages_by_id[target_id]
            targets.append(
                {
                    "page_id": target_id,
                    "keyword": target_page["keyword"],
                    "url": target_page["url"],
                    "is_priority": target_page.get("is_priority", False),
                    "label_overlap": neighbors[target_id],
                    "score": score,
                    "source": "collection",
                }
            )
            inbound_counts[target_id] += 1

        # Fill remaining with blog targets
        for score, target_id in scored_blog:
            if len(targets) >= budget:
                break
            target_page = pages_by_id[target_id]
            targets.append(
                {
                    "page_id": target_id,
                    "keyword": target_page["keyword"],
                    "url": target_page["url"],
                    "is_priority": target_page.get("is_priority", False),
                    "label_overlap": neighbors[target_id],
                    "score": score,
                    "source": "wordpress",
                }
            )
            inbound_counts[target_id] += 1

        result[page_id] = targets

    logger.info(
        "Selected WP+collection targets",
        extra={
            "page_count": len(result),
            "total_links": sum(len(t) for t in result.values()),
            "collection_links": sum(
                1
                for targets in result.values()
                for t in targets
                if t.get("source") == "collection"
            ),
        },
    )
    return result


async def _plan_links_for_silo_with_collections(
    db: AsyncSession,
    project_id: str,
    cluster: KeywordCluster,
    collection_pages: list[CrawledPage],
    injector: LinkInjector,
    validator: LinkValidator,
    anchor_selector: AnchorTextSelector,
) -> int:
    """Plan and inject links for a silo group including collection page targets.

    Same as _plan_links_for_silo but uses collection-aware graph and target selection.
    Only WP pages get links injected; collection pages are targets only.
    """
    # Load cluster pages with their CrawledPage data
    stmt = (
        select(ClusterPage)
        .options(joinedload(ClusterPage.crawled_page))
        .where(ClusterPage.cluster_id == cluster.id)
    )
    result = await db.execute(stmt)
    cluster_pages = [
        cp for cp in result.unique().scalars().all() if cp.crawled_page_id is not None
    ]

    if len(cluster_pages) < 2 and not collection_pages:
        logger.info(f"Silo '{cluster.name}' has <2 pages and no collections, skipping")
        return 0

    # 1. Build mixed graph with collection pages
    graph = _build_silo_graph_with_collections(cluster_pages, collection_pages)

    # 2. Calculate budgets (only for WP pages — they're the sources)
    wp_page_ids = [
        p["page_id"] for p in graph["pages"] if p.get("source") == "wordpress"
    ]
    word_counts = await _load_word_counts(db, wp_page_ids)
    budgets = {pid: calculate_budget(wc) for pid, wc in word_counts.items()}

    # 3. Select targets with collection awareness
    targets_map = select_targets_wp_with_collections(graph, budgets)

    # 4. Resolve URLs
    project_obj = await db.get(Project, project_id)
    site_base = (project_obj.site_url or "").rstrip("/") if project_obj else ""

    # 5. Generate anchor text
    keyword_map: dict[str, str] = {}
    for page in graph["pages"]:
        pid = page["page_id"]
        kw = page.get("keyword", "")
        if kw:
            keyword_map[pid] = kw

    natural_phrases = await anchor_selector.generate_natural_phrases(keyword_map)

    usage_tracker: dict[str, dict[str, int]] = {}
    page_link_plans: dict[str, list[dict[str, Any]]] = {}

    for page in graph["pages"]:
        if page.get("source") != "wordpress":
            continue  # Only WP pages are sources

        source_id = page["page_id"]
        page_targets = targets_map.get(source_id, [])
        planned_links: list[dict[str, Any]] = []

        source_content = await _load_page_content_text(db, source_id)

        for target in page_targets:
            target_id = target["page_id"]
            candidates = await anchor_selector.gather_candidates(target_id, db)

            if target_id in natural_phrases:
                candidates.extend(natural_phrases[target_id])

            anchor_result = anchor_selector.select_anchor(
                candidates, source_content, target_id, usage_tracker
            )

            if anchor_result is None:
                anchor_result = {
                    "anchor_text": target.get("keyword", "link"),
                    "anchor_type": "exact_match",
                    "score": 0.0,
                }

            target_url = target.get("url", "")
            if target_url and not target_url.startswith("http"):
                target_url = f"{site_base}/{target_url.lstrip('/')}"

            planned_links.append(
                {
                    **target,
                    "anchor_text": anchor_result["anchor_text"],
                    "anchor_type": anchor_result["anchor_type"],
                    "target_page_id": target_id,
                    "url": target_url,
                }
            )

        page_link_plans[source_id] = planned_links

    # 6. Inject links into WP content only
    injection_results: list[dict[str, Any]] = []
    pages_html: dict[str, str] = {}

    for source_id, planned_links in page_link_plans.items():
        html = await _load_bottom_description(db, source_id)
        if not html:
            continue

        current_html = html
        for link_plan in planned_links:
            anchor_text = link_plan["anchor_text"]
            target_url = link_plan.get("url", "")
            target_id = link_plan["target_page_id"]

            modified_html, p_idx = injector.inject_rule_based(
                current_html, anchor_text, target_url
            )

            if p_idx is not None:
                current_html = modified_html
                injection_results.append(
                    {
                        "source_page_id": source_id,
                        "target_page_id": target_id,
                        "anchor_text": anchor_text,
                        "anchor_type": link_plan["anchor_type"],
                        "placement_method": "rule_based",
                        "position_in_content": p_idx,
                        "is_mandatory": False,
                    }
                )
            else:
                target_keyword = link_plan.get("keyword", "")
                modified_html, p_idx = await injector.inject_llm_fallback(
                    current_html, anchor_text, target_url, target_keyword
                )
                if p_idx is not None:
                    current_html = modified_html
                    injection_results.append(
                        {
                            "source_page_id": source_id,
                            "target_page_id": target_id,
                            "anchor_text": anchor_text,
                            "anchor_type": link_plan["anchor_type"],
                            "placement_method": "llm_fallback",
                            "position_in_content": p_idx,
                            "is_mandatory": False,
                        }
                    )

        pages_html[source_id] = current_html

    # 7. Validate
    temp_links = [_LinkProxy({**r, "scope": "cluster"}) for r in injection_results]
    validation = validator.validate_links(temp_links, pages_html, "cluster")

    # 8. Persist InternalLink rows + update PageContent
    for result_dict in injection_results:
        link_status = "verified" if validation["passed"] else "injected"

        link = InternalLink(
            source_page_id=result_dict["source_page_id"],
            target_page_id=result_dict["target_page_id"],
            project_id=project_id,
            cluster_id=cluster.id,
            scope="cluster",
            anchor_text=result_dict["anchor_text"],
            anchor_type=result_dict["anchor_type"],
            position_in_content=result_dict.get("position_in_content"),
            is_mandatory=result_dict.get("is_mandatory", False),
            placement_method=result_dict["placement_method"],
            status=link_status,
        )
        db.add(link)

    # Update PageContent with injected HTML (WP pages only)
    for page_id, html in pages_html.items():
        pc_stmt = select(PageContent).where(PageContent.crawled_page_id == page_id)
        pc_result = await db.execute(pc_stmt)
        pc = pc_result.scalar_one_or_none()
        if pc:
            pc.bottom_description = html

    await db.flush()

    logger.info(
        f"Silo '{cluster.name}' planned (with collections)",
        extra={"links": len(injection_results), "pages": len(cluster_pages)},
    )
    return len(injection_results)


# =============================================================================
# STEP 6: REVIEW
# =============================================================================


async def step6_get_review(
    db: AsyncSession,
    project_id: str,
) -> dict[str, Any]:
    """Get link review stats grouped by silo."""
    # Load clusters with their link counts
    clusters_stmt = select(KeywordCluster).where(
        KeywordCluster.project_id == project_id,
    )
    clusters_result = await db.execute(clusters_stmt)
    clusters = list(clusters_result.scalars().all())

    groups: list[dict[str, Any]] = []
    total_links = 0
    total_posts = 0
    verified_count = 0
    total_link_count = 0

    # Pre-aggregate collection link counts in a single query
    # Include onboarding pages + cluster pages with approved content
    collection_ids_stmt = (
        select(CrawledPage.id)
        .outerjoin(PageContent, PageContent.crawled_page_id == CrawledPage.id)
        .where(
            CrawledPage.project_id == project_id,
            or_(
                CrawledPage.source == "onboarding",
                and_(
                    CrawledPage.source == "cluster",
                    PageContent.is_approved.is_(True),
                ),
            ),
        )
    )
    collection_ids_result = await db.execute(collection_ids_stmt)
    onboarding_page_ids = set(collection_ids_result.scalars().all())

    collection_counts_by_cluster: dict[str, int] = {}
    if onboarding_page_ids:
        coll_counts_stmt = (
            select(
                InternalLink.cluster_id,
                func.count().label("count"),
            )
            .where(InternalLink.target_page_id.in_(onboarding_page_ids))
            .group_by(InternalLink.cluster_id)
        )
        coll_counts_result = await db.execute(coll_counts_stmt)
        collection_counts_by_cluster = dict(coll_counts_result.all())  # type: ignore[arg-type]

    for cluster in clusters:
        # Count links for this cluster
        link_count_stmt = (
            select(func.count())
            .select_from(InternalLink)
            .where(
                InternalLink.cluster_id == cluster.id,
            )
        )
        link_count_result = await db.execute(link_count_stmt)
        link_count = link_count_result.scalar_one()

        # Count pages in cluster
        page_count_stmt = (
            select(func.count())
            .select_from(ClusterPage)
            .where(
                ClusterPage.cluster_id == cluster.id,
            )
        )
        page_count_result = await db.execute(page_count_stmt)
        page_count = page_count_result.scalar_one()

        # Count verified links
        verified_stmt = (
            select(func.count())
            .select_from(InternalLink)
            .where(
                InternalLink.cluster_id == cluster.id,
                InternalLink.status == "verified",
            )
        )
        verified_result = await db.execute(verified_stmt)
        verified = verified_result.scalar_one()

        groups.append(
            {
                "group_name": cluster.name,
                "post_count": page_count,
                "link_count": link_count,
                "avg_links_per_post": link_count / page_count if page_count > 0 else 0,
                "collection_link_count": collection_counts_by_cluster.get(
                    cluster.id, 0
                ),
            }
        )

        total_links += link_count
        total_posts += page_count
        verified_count += verified
        total_link_count += link_count

    validation_pass_rate = (
        (verified_count / total_link_count * 100) if total_link_count > 0 else 100.0
    )

    return {
        "total_posts": total_posts,
        "total_links": total_links,
        "avg_links_per_post": total_links / total_posts if total_posts > 0 else 0,
        "groups": groups,
        "validation_pass_rate": round(validation_pass_rate, 1),
    }


# =============================================================================
# STEP 7: EXPORT
# =============================================================================


async def step7_export(
    db: AsyncSession,
    project_id: str,
    site_url: str,
    username: str,
    app_password: str,
    job_id: str,
    title_filter: list[str] | None = None,
) -> dict[str, Any]:
    """Push updated content back to WordPress."""
    progress = {
        "step": "export",
        "step_label": "Exporting to WordPress",
        "status": "running",
        "current": 0,
        "total": 0,
    }
    _wp_progress[job_id] = progress

    try:
        # Load pages with updated content
        stmt = (
            select(CrawledPage)
            .options(joinedload(CrawledPage.page_content))
            .where(
                CrawledPage.project_id == project_id,
                CrawledPage.source == "wordpress",
            )
        )
        result = await db.execute(stmt)
        pages = list(result.unique().scalars().all())

        # Apply title filter
        if title_filter:
            pages = [
                p
                for p in pages
                if p.title and any(f.lower() in p.title.lower() for f in title_filter)
            ]

        # Filter to pages that have links (updated content)
        pages_to_export = [
            p
            for p in pages
            if p.page_content and p.page_content.bottom_description and p.raw_url
        ]
        progress["total"] = len(pages_to_export)

        client = WordPressClient(site_url, username, app_password)
        semaphore = asyncio.Semaphore(EXPORT_SEMAPHORE_LIMIT)
        success_count = 0
        fail_count = 0

        async def export_page(page: CrawledPage) -> None:
            nonlocal success_count, fail_count
            async with semaphore:
                try:
                    wp_post_id = int(page.raw_url or "0")
                    content = (
                        page.page_content.bottom_description
                        if page.page_content
                        else ""
                    )
                    await client.update_post_content(wp_post_id, content or "")
                    success_count += 1
                except Exception:
                    fail_count += 1
                    logger.error(
                        "Failed to export page",
                        extra={"page_id": page.id, "wp_id": page.raw_url},
                        exc_info=True,
                    )
                finally:
                    progress["current"] = success_count + fail_count

        try:
            await asyncio.gather(*[export_page(p) for p in pages_to_export])
        finally:
            await client.close()

        result_data = {
            "exported": success_count,
            "failed": fail_count,
            "total": len(pages_to_export),
        }
        progress["status"] = "complete"
        progress["result"] = result_data

        logger.info("WordPress export complete", extra=result_data)
        return result_data

    except Exception as e:
        progress["status"] = "failed"
        progress["error"] = str(e)
        logger.error("WordPress export failed", exc_info=True)
        raise


# =============================================================================
# HELPERS
# =============================================================================


def _extract_headings(html: str) -> dict[str, list[str]]:
    """Extract h1, h2, h3 headings from HTML content."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}

    for tag in ["h1", "h2", "h3"]:
        for el in soup.find_all(tag):
            text = el.get_text(strip=True)
            if text:
                headings[tag].append(text)

    return headings


def _extract_json(text: str) -> str:
    """Extract JSON from text that may contain markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # Remove opening ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
