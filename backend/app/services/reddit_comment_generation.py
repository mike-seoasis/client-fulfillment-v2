"""Reddit comment generation service.

Generates AI comments for discovered Reddit posts using brand context.
Follows the same background task + poll status pattern as reddit_discovery.py.

Key design decisions:
- Uses Claude Sonnet (ClaudeClient default) for generation
- Temperature 0.7 for natural variation
- Re-generation creates NEW comment rows (never overwrites)
- Default is_promotional=True
- Sequential Claude calls in batch (no parallel)
"""

import random
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import db_manager
from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_api_key
from app.models.brand_config import BrandConfig
from app.models.reddit_comment import CommentStatus, RedditComment
from app.models.reddit_config import RedditProjectConfig
from app.models.reddit_post import RedditPost

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Comment approach types
# ---------------------------------------------------------------------------

# Promotional approaches (brand mention)
PROMOTIONAL_APPROACHES = {
    "Sandwich": "Start with helpful advice, share your personal experience including what helped you, then add more tips.",
    "Story-Based": "Share a story about a problem you faced, what you tried, what finally worked for you.",
    "Skeptic Converted": "Mention you were skeptical at first, explain what changed your mind, share your honest experience.",
    "Comparison": "Compare a few options you've tried, share pros/cons of each, explain your preference.",
    "Quick Tip": "Share a quick, actionable tip that worked for you.",
    "Problem-Solution": "Describe the problem you had, explain how you solved it.",
    "Before/After": "Share what things were like before and how they improved after.",
    "Question-Based": "Start with a question, then share what worked for you.",
    "List-Based": "Share a few options/tips in a casual list format.",
    "Technical Deep-Dive": "Explain the details of what worked and why.",
}

# Non-promotional approaches (community building, no brand mention)
ORGANIC_APPROACHES = {
    "Simple Reaction": "Give a brief, authentic reaction to the post.",
    "Appreciation": "Express genuine appreciation for what they shared.",
    "Follow-Up Question": "Ask a relevant follow-up question to understand better.",
    "Agree + Add": "Agree with them and add a related insight.",
    "Relate Personal Experience": "Share a brief related personal experience.",
    "Helpful Tip": "Offer a specific, actionable tip.",
    "Empathy": "Show understanding for their situation.",
    "Validation": "Validate their feelings or experience.",
    "Encouragement": "Offer supportive encouragement.",
    "Agree + Nuance": "Agree but add some nuance or caveat.",
    "Suggest Alternative Approach": "Suggest a different approach they might try.",
}


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def _extract_brand_context(brand_config: BrandConfig) -> dict[str, Any]:
    """Extract brand context from v2_schema, handling varying key structures.

    The v2_schema structure varies depending on how it was generated.
    This function normalises the data into a consistent shape for the prompt.
    """
    v2 = brand_config.v2_schema or {}

    # --- Brand name ---
    # Try multiple paths: brand_foundation → company_overview → top-level
    bf = v2.get("brand_foundation", {})
    company = bf.get("company_overview", {})
    brand_name = (
        company.get("company_name")
        or bf.get("brand_name")
        or v2.get("company_name")
        or brand_config.brand_name  # model-level field, always present
    )

    # --- Brand description ---
    positioning = bf.get("brand_positioning", {})
    brand_desc = (
        positioning.get("one_sentence_description") or bf.get("brand_description") or ""
    )

    # --- What they sell (for context) ---
    products = bf.get("what_they_sell", {})
    primary_products = products.get("primary_products_services", "")

    # --- Key differentiators ---
    diffs = bf.get("differentiators", {})
    primary_usp = diffs.get("primary_usp", "")
    supporting_diffs = diffs.get("supporting_differentiators", [])

    # --- Voice ---
    voice_dims = v2.get("voice_dimensions", {})
    voice_summary = voice_dims.get("voice_summary", "")
    formality = voice_dims.get("formality", {})
    humor = voice_dims.get("humor", {})

    # Fallback to older key name
    voice_chars = v2.get("voice_characteristics", {})
    if not voice_summary:
        voice_summary = voice_chars.get("overall_tone", "friendly and conversational")

    # --- Vocabulary ---
    vocab = v2.get("vocabulary", {})
    power_words = vocab.get("power_words", vocab.get("preferred_terms", []))
    banned_words = vocab.get("banned_words", vocab.get("terms_to_avoid", []))
    signature_phrases = vocab.get("signature_phrases", {})
    words_we_prefer = vocab.get("words_we_prefer", [])

    # --- Mission ---
    mission = bf.get("mission_and_values", {})

    return {
        "brand_name": brand_name,
        "brand_desc": brand_desc,
        "primary_products": primary_products,
        "primary_usp": primary_usp,
        "supporting_diffs": supporting_diffs,
        "voice_summary": voice_summary,
        "formality_desc": formality.get("description", ""),
        "humor_desc": humor.get("description", ""),
        "power_words": power_words or [],
        "banned_words": banned_words or [],
        "signature_phrases": signature_phrases,
        "words_we_prefer": words_we_prefer,
        "mission_statement": mission.get("mission_statement", ""),
        "brand_promise": mission.get("brand_promise", ""),
    }


async def build_comment_prompt(
    post: RedditPost,
    brand_config: BrandConfig,
    comment_instructions: str | None,
    approach: str,
    is_promotional: bool,
) -> str:
    """Build the LLM prompt for comment generation.

    Uses BrandConfig.v2_schema for brand voice. Mirrors the original
    generate_comment.py "sandwich technique" prompt quality while
    adapting to the V2 data model.
    """
    ctx = _extract_brand_context(brand_config)

    # --- Voice / persona section ---
    voice_lines = [
        "You are a helpful Reddit user who genuinely wants to help people find solutions.",
    ]
    if ctx["voice_summary"]:
        voice_lines.append(f"Your communication style: {ctx['voice_summary']}")
    if ctx["formality_desc"]:
        voice_lines.append(f"Formality: {ctx['formality_desc']}")
    if ctx["power_words"]:
        voice_lines.append(
            f"Words that resonate with you: {', '.join(ctx['power_words'][:8])}"
        )
    if ctx["banned_words"]:
        voice_lines.append(f"Words you NEVER use: {', '.join(ctx['banned_words'][:8])}")
    if ctx["words_we_prefer"]:
        pref_strs = [
            f'say "{wp["we_say"]}" instead of "{wp["instead_of"]}"'
            for wp in ctx["words_we_prefer"][:4]
            if isinstance(wp, dict) and "we_say" in wp
        ]
        if pref_strs:
            voice_lines.append(f"Language preferences: {'; '.join(pref_strs)}")
    if comment_instructions:
        voice_lines.append(f"Special instructions: {comment_instructions}")

    voice_desc = "\n".join(voice_lines)

    # --- Post context ---
    post_context = f"""REDDIT POST TO REPLY TO:
Subreddit: r/{post.subreddit}
Post Title: "{post.title}"
Context/Preview: {(post.snippet or "No content available")[:500]}

IMPORTANT: You are writing a TOP-LEVEL REPLY to the original post (responding to the title/question).
The "Context/Preview" above may include text from other comments - ignore those and focus on the post title."""

    # --- Approach instructions ---
    approach_instruction = (
        PROMOTIONAL_APPROACHES.get(approach)
        or ORGANIC_APPROACHES.get(approach)
        or "Respond naturally and helpfully."
    )
    template_instructions = f"COMMENT APPROACH: {approach_instruction}"

    # --- Brand section ---
    brand_name = ctx["brand_name"]

    if is_promotional:
        # Build rich brand context
        brand_lines = [
            "\nBRAND TO MENTION (naturally, as part of your experience):",
            f"- Brand: {brand_name}",
        ]
        if ctx["brand_desc"]:
            brand_lines.append(f"- What it is: {ctx['brand_desc']}")
        if ctx["primary_products"]:
            brand_lines.append(f"- Products: {ctx['primary_products']}")
        if ctx["primary_usp"]:
            brand_lines.append(f"- What makes it special: {ctx['primary_usp']}")
        if ctx["supporting_diffs"]:
            brand_lines.append(
                f"- Key differentiators: {'; '.join(ctx['supporting_diffs'][:3])}"
            )

        brand_lines.append(f"""
COMMENT STYLE - "SANDWICH" TECHNIQUE:
1. Start with genuine empathy, agreement, or shared experience related to the post
2. In the MIDDLE, naturally mention {brand_name} as something you came across or tried
3. End with additional helpful context or general advice

CRITICAL RULES:
- Sound like a REAL person, not a marketer
- Use casual Reddit language (lowercase ok, contractions, natural flow)
- DON'T use promotional phrases ("check out", "highly recommend", "game changer", "amazing product")
- DO use natural, varied phrasing like:
  * "I came across {brand_name} while researching this"
  * "{brand_name} kept popping up in my searches"
  * "saw {brand_name} recommended in a few threads"
  * "stumbled on {brand_name} when I had the same issue"
  * "heard decent things about {brand_name}"
- Mention the brand ONCE, casually in the middle
- The brand mention should feel organic - like you're sharing something that genuinely helped you, not advertising""")

        brand_section = "\n".join(brand_lines)
    else:
        brand_section = f"""
NOTE: This is a NON-PROMOTIONAL comment. Do NOT mention any brands, products, or companies.
Focus purely on being helpful and engaging with the community.
Draw on general knowledge relevant to r/{post.subreddit}."""

    # --- Assemble final prompt ---
    prompt = f"""{voice_desc}

{post_context}

{template_instructions}
{brand_section}

LENGTH: approximately 50-150 words (2-4 sentences)

CRITICAL FORMATTING RULES:
- Write ONLY the raw comment text - no headers, labels, or formatting markers
- Do NOT use **Bold Headers:** or any markdown section headers
- Write as a natural Reddit comment - just flowing text as a real user would type
- Respond to the POST TITLE, not to other comments in the thread
- Match the subreddit's culture and tone (r/{post.subreddit})
- Use lowercase, contractions, and casual language where appropriate

Write your Reddit comment now:"""

    return prompt


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------


async def _get_brand_config(project_id: str, db: AsyncSession) -> BrandConfig:
    """Load brand config for a project."""
    stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
    result = await db.execute(stmt)
    brand = result.scalar_one_or_none()
    if not brand:
        raise ValueError(f"No BrandConfig found for project {project_id}")
    return brand


async def _get_reddit_config(project_id: str, db: AsyncSession) -> RedditProjectConfig:
    """Load Reddit project config."""
    stmt = select(RedditProjectConfig).where(
        RedditProjectConfig.project_id == project_id
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()
    if not config:
        raise ValueError(f"No RedditProjectConfig found for project {project_id}")
    return config


# ---------------------------------------------------------------------------
# Single comment generation
# ---------------------------------------------------------------------------


async def generate_comment(
    post: RedditPost,
    project_id: str,
    db: AsyncSession,
    is_promotional: bool = True,
) -> RedditComment:
    """Generate a single comment for a post.

    Creates a NEW comment row each time (re-generation never overwrites).
    Uses Claude Sonnet via ClaudeClient default model.
    """
    brand_config = await _get_brand_config(project_id, db)
    reddit_config = await _get_reddit_config(project_id, db)

    # Select approach (random from appropriate set)
    if is_promotional:
        approach = random.choice(list(PROMOTIONAL_APPROACHES.keys()))
    else:
        approach = random.choice(list(ORGANIC_APPROACHES.keys()))

    # Build prompt
    prompt = await build_comment_prompt(
        post=post,
        brand_config=brand_config,
        comment_instructions=reddit_config.comment_instructions,
        approach=approach,
        is_promotional=is_promotional,
    )

    # Generate with Claude Sonnet (default model), temperature 0.7
    claude = ClaudeClient(api_key=get_api_key())
    try:
        result = await claude.complete(
            user_prompt=prompt,
            temperature=0.7,
            max_tokens=500,
        )
    finally:
        await claude.close()

    if not result.success:
        raise RuntimeError(f"Claude generation failed: {result.error}")

    comment_text = (result.text or "").strip()

    # Strip quote wrapping
    if comment_text.startswith('"') and comment_text.endswith('"'):
        comment_text = comment_text[1:-1]

    # Store as DRAFT
    comment = RedditComment(
        post_id=post.id,
        project_id=project_id,
        body=comment_text,
        original_body=comment_text,
        is_promotional=is_promotional,
        approach_type=approach,
        status=CommentStatus.DRAFT.value,
        generation_metadata={
            "model": claude.model,
            "approach": approach,
            "is_promotional": is_promotional,
            "generated_at": datetime.now(UTC).isoformat(),
        },
    )
    db.add(comment)
    await db.flush()

    logger.info(
        "Comment generated",
        extra={
            "post_id": post.id,
            "project_id": project_id,
            "approach": approach,
            "is_promotional": is_promotional,
            "comment_id": comment.id,
        },
    )

    return comment


# ---------------------------------------------------------------------------
# Generation progress tracking (in-memory)
# ---------------------------------------------------------------------------


@dataclass
class GenerationProgress:
    """Real-time progress data for a running batch generation."""

    status: str = "generating"  # generating | complete | failed
    total_posts: int = 0
    posts_generated: int = 0
    error: str | None = None
    started_at: str = ""
    completed_at: str = ""


# In-memory dict keyed by project_id -> GenerationProgress
_active_generations: dict[str, GenerationProgress] = {}


def get_generation_progress(project_id: str) -> GenerationProgress | None:
    """Get the current generation progress for a project, if any."""
    return _active_generations.get(project_id)


def is_generation_active(project_id: str) -> bool:
    """Check if a batch generation is currently running for a project."""
    progress = _active_generations.get(project_id)
    if progress is None:
        return False
    return progress.status == "generating"


def _set_generation_progress(project_id: str, progress: GenerationProgress) -> None:
    """Store progress in the in-memory dict."""
    _active_generations[project_id] = progress


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------


async def generate_batch(
    project_id: str,
    post_ids: list[str] | None = None,
) -> None:
    """Generate comments for multiple posts.

    Designed to run in a FastAPI BackgroundTask. Creates its own DB sessions.
    Sequential Claude calls (no parallel) with progress tracking.

    Args:
        project_id: UUID of the project.
        post_ids: Optional list of specific post IDs. If None, generates
                  for all relevant posts without existing comments.
    """
    progress = GenerationProgress(
        status="generating",
        started_at=datetime.now(UTC).isoformat(),
    )
    _set_generation_progress(project_id, progress)

    try:
        async with db_manager.session_factory() as db:
            # Determine which posts to generate for
            if post_ids:
                stmt = select(RedditPost).where(
                    RedditPost.id.in_(post_ids),
                    RedditPost.project_id == project_id,
                )
            else:
                # All relevant posts that don't have comments yet
                posts_with_comments = (
                    select(RedditComment.post_id)
                    .where(RedditComment.project_id == project_id)
                    .distinct()
                )
                stmt = select(RedditPost).where(
                    RedditPost.project_id == project_id,
                    RedditPost.filter_status == "relevant",
                    ~RedditPost.id.in_(posts_with_comments),
                )

            result = await db.execute(stmt)
            posts = list(result.scalars().all())

            progress.total_posts = len(posts)

            if not posts:
                progress.status = "complete"
                progress.completed_at = datetime.now(UTC).isoformat()
                return

            # Generate sequentially
            for post in posts:
                try:
                    await generate_comment(
                        post=post,
                        project_id=project_id,
                        db=db,
                    )
                    progress.posts_generated += 1
                except Exception as e:
                    logger.error(
                        "Failed to generate comment for post",
                        extra={
                            "post_id": post.id,
                            "project_id": project_id,
                            "error": str(e),
                        },
                    )
                    # Continue with remaining posts

            await db.commit()

        progress.status = "complete"
        progress.completed_at = datetime.now(UTC).isoformat()

        logger.info(
            "Batch generation complete",
            extra={
                "project_id": project_id,
                "total_posts": progress.total_posts,
                "posts_generated": progress.posts_generated,
            },
        )

    except Exception as e:
        logger.error(
            "Batch generation failed",
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
