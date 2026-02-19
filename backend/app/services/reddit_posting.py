"""Reddit comment posting service.

Submits approved comments to CrowdReply and handles webhook-based status tracking.
Follows the same background task + in-memory progress pattern as reddit_comment_generation.py.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import db_manager
from app.core.logging import get_logger
from app.integrations.crowdreply import get_crowdreply
from app.models.crowdreply_task import CrowdReplyTask, CrowdReplyTaskStatus, CrowdReplyTaskType
from app.models.reddit_comment import CommentStatus, RedditComment
from app.models.reddit_post import RedditPost

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Status mapping: CrowdReply status -> (CrowdReplyTaskStatus, CommentStatus)
# ---------------------------------------------------------------------------

CROWDREPLY_STATUS_MAP: dict[str, tuple[CrowdReplyTaskStatus, CommentStatus]] = {
    "published": (CrowdReplyTaskStatus.PUBLISHED, CommentStatus.POSTED),
    "mod-removed": (CrowdReplyTaskStatus.MOD_REMOVED, CommentStatus.MOD_REMOVED),
    "cancelled": (CrowdReplyTaskStatus.CANCELLED, CommentStatus.FAILED),
    "assigned": (CrowdReplyTaskStatus.ASSIGNED, CommentStatus.SUBMITTING),
    "pending": (CrowdReplyTaskStatus.PENDING, CommentStatus.SUBMITTING),
    "submitted": (CrowdReplyTaskStatus.SUBMITTED, CommentStatus.SUBMITTING),
    "failed": (CrowdReplyTaskStatus.FAILED, CommentStatus.FAILED),
}


# ---------------------------------------------------------------------------
# Submission progress tracking (in-memory)
# ---------------------------------------------------------------------------


@dataclass
class SubmissionProgress:
    """Real-time progress data for a running submission."""

    status: str = "submitting"  # submitting | complete | failed | idle
    total_comments: int = 0
    comments_submitted: int = 0
    comments_failed: int = 0
    errors: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""


_active_submissions: dict[str, SubmissionProgress] = {}


def get_submission_progress(project_id: str) -> SubmissionProgress | None:
    return _active_submissions.get(project_id)


def is_submission_active(project_id: str) -> bool:
    progress = _active_submissions.get(project_id)
    if progress is None:
        return False
    return progress.status == "submitting"


# ---------------------------------------------------------------------------
# Submit approved comments
# ---------------------------------------------------------------------------


async def submit_approved_comments(
    project_id: str,
    comment_ids: list[str] | None = None,
    upvotes_per_comment: int | None = None,
) -> None:
    """Submit approved comments to CrowdReply.

    Designed to run in a FastAPI BackgroundTask. Creates its own DB sessions.

    Args:
        project_id: UUID of the project.
        comment_ids: Optional list of specific comment IDs. If None, submits all approved.
        upvotes_per_comment: Optional upvotes to request per comment.
    """
    progress = SubmissionProgress(
        status="submitting",
        started_at=datetime.now(UTC).isoformat(),
    )
    _active_submissions[project_id] = progress

    try:
        client = await get_crowdreply()

        async with db_manager.session_factory() as db:
            # Query approved comments, join RedditPost for thread URL
            stmt = (
                select(RedditComment)
                .options(selectinload(RedditComment.post))
                .where(
                    RedditComment.project_id == project_id,
                    RedditComment.status == CommentStatus.APPROVED.value,
                )
            )
            if comment_ids:
                stmt = stmt.where(RedditComment.id.in_(comment_ids))

            result = await db.execute(stmt)
            comments = list(result.scalars().all())

            progress.total_comments = len(comments)

            if not comments:
                progress.status = "complete"
                progress.completed_at = datetime.now(UTC).isoformat()
                return

            for comment in comments:
                try:
                    post: RedditPost | None = comment.post
                    if not post:
                        progress.comments_failed += 1
                        progress.errors.append(
                            f"Comment {comment.id}: no associated post"
                        )
                        continue

                    thread_url = post.url

                    # Call CrowdReply
                    task_result = await client.create_comment_task(
                        thread_url=thread_url,
                        content=comment.body,
                        upvotes=upvotes_per_comment,
                    )

                    if task_result.success:
                        # Create CrowdReplyTask record
                        cr_task = CrowdReplyTask(
                            comment_id=comment.id,
                            external_task_id=task_result.external_task_id,
                            task_type=CrowdReplyTaskType.COMMENT.value,
                            status=CrowdReplyTaskStatus.SUBMITTED.value,
                            target_url=thread_url,
                            content=comment.body,
                            crowdreply_project_id=client._project_id
                            if hasattr(client, "_project_id")
                            else None,
                            request_payload=task_result.request_payload,
                            submitted_at=datetime.now(UTC),
                        )
                        db.add(cr_task)

                        # Update comment status
                        comment.status = CommentStatus.SUBMITTING.value
                        comment.crowdreply_task_id = task_result.external_task_id

                        # Commit after each to save partial progress
                        await db.commit()
                        progress.comments_submitted += 1

                        logger.info(
                            "Comment submitted to CrowdReply",
                            extra={
                                "comment_id": comment.id,
                                "external_task_id": task_result.external_task_id,
                            },
                        )
                    else:
                        progress.comments_failed += 1
                        progress.errors.append(
                            f"Comment {comment.id}: {task_result.error}"
                        )
                        logger.error(
                            "Failed to submit comment to CrowdReply",
                            extra={
                                "comment_id": comment.id,
                                "error": task_result.error,
                            },
                        )

                except Exception as e:
                    progress.comments_failed += 1
                    progress.errors.append(f"Comment {comment.id}: {e}")
                    logger.error(
                        "Exception submitting comment",
                        extra={
                            "comment_id": comment.id,
                            "error": str(e),
                        },
                        exc_info=True,
                    )

        progress.status = "complete"
        progress.completed_at = datetime.now(UTC).isoformat()

        logger.info(
            "Submission batch complete",
            extra={
                "project_id": project_id,
                "total": progress.total_comments,
                "submitted": progress.comments_submitted,
                "failed": progress.comments_failed,
            },
        )

    except Exception as e:
        logger.error(
            "Submission batch failed",
            extra={
                "project_id": project_id,
                "error": str(e),
            },
            exc_info=True,
        )
        progress.status = "failed"
        progress.errors.append(str(e))
        progress.completed_at = datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Webhook handler
# ---------------------------------------------------------------------------


async def handle_crowdreply_webhook(
    payload: dict,
    db: AsyncSession,
) -> bool:
    """Process a CrowdReply webhook payload.

    Finds the CrowdReplyTask by external_task_id, maps the status,
    and updates both the task and the associated comment.

    Returns True if processed successfully, False otherwise.
    """
    external_id = payload.get("_id") or payload.get("id", "")
    cr_status = payload.get("status", "")
    thread_url = payload.get("threadUrl", "")
    content = payload.get("content", "")
    task_submission = payload.get("taskSubmission", [])
    published_at_str = payload.get("publishedAt")
    client_price = payload.get("clientPrice")

    # Find CrowdReplyTask by external_task_id (use first() to handle duplicates)
    stmt = (
        select(CrowdReplyTask)
        .where(CrowdReplyTask.external_task_id == external_id)
        .order_by(CrowdReplyTask.created_at.desc())
    )
    result = await db.execute(stmt)
    cr_task = result.scalars().first()

    # Fallback: match by target_url + content
    if cr_task is None and thread_url and content:
        fallback_stmt = (
            select(CrowdReplyTask)
            .where(
                CrowdReplyTask.target_url == thread_url,
                CrowdReplyTask.content == content,
            )
            .order_by(CrowdReplyTask.created_at.desc())
        )
        fallback_result = await db.execute(fallback_stmt)
        cr_task = fallback_result.scalars().first()

    if cr_task is None:
        logger.warning(
            "CrowdReply webhook: no matching task found",
            extra={"external_id": external_id, "thread_url": thread_url},
        )
        return False

    # Map status
    status_tuple = CROWDREPLY_STATUS_MAP.get(cr_status)
    if status_tuple is None:
        logger.warning(
            "CrowdReply webhook: unknown status",
            extra={"cr_status": cr_status, "external_id": external_id},
        )
        return False

    task_status, comment_status = status_tuple

    # Update CrowdReplyTask
    cr_task.status = task_status.value
    cr_task.response_payload = payload
    if external_id and not cr_task.external_task_id:
        cr_task.external_task_id = external_id
    if client_price is not None:
        cr_task.price = float(client_price)
    if published_at_str:
        try:
            cr_task.published_at = datetime.fromisoformat(
                published_at_str.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass

    # Update associated comment
    if cr_task.comment_id:
        comment_stmt = select(RedditComment).where(
            RedditComment.id == cr_task.comment_id
        )
        comment_result = await db.execute(comment_stmt)
        comment = comment_result.scalar_one_or_none()

        if comment:
            comment.status = comment_status.value

            # If published, extract posted_url from taskSubmission
            if comment_status == CommentStatus.POSTED and task_submission:
                submission_url = task_submission[0].get("submissionUrl", "")
                if submission_url:
                    comment.posted_url = submission_url
                comment.posted_at = datetime.now(UTC)

    await db.commit()

    logger.info(
        "CrowdReply webhook processed",
        extra={
            "external_id": external_id,
            "cr_status": cr_status,
            "task_status": task_status.value,
            "comment_status": comment_status.value,
            "comment_id": cr_task.comment_id,
        },
    )

    return True


# ---------------------------------------------------------------------------
# Webhook simulator
# ---------------------------------------------------------------------------


async def simulate_webhook(
    comment_id: str,
    status: str,
    submission_url: str | None,
    db: AsyncSession,
) -> bool:
    """Build a fake webhook payload from comment data and process it.

    For development/staging only.
    """
    # Load comment with its CrowdReply task
    comment_stmt = select(RedditComment).where(RedditComment.id == comment_id)
    comment_result = await db.execute(comment_stmt)
    comment = comment_result.scalar_one_or_none()

    if not comment:
        logger.warning("Simulate webhook: comment not found", extra={"comment_id": comment_id})
        return False

    # Find the CrowdReplyTask for this comment (most recent if duplicates)
    task_stmt = (
        select(CrowdReplyTask)
        .where(CrowdReplyTask.comment_id == comment_id)
        .order_by(CrowdReplyTask.created_at.desc())
    )
    task_result = await db.execute(task_stmt)
    cr_task = task_result.scalars().first()

    external_id = cr_task.external_task_id if cr_task else f"sim_{comment_id[:8]}"

    # Build fake payload
    fake_payload: dict = {
        "_id": external_id,
        "threadUrl": cr_task.target_url if cr_task else "",
        "taskType": "comment",
        "status": status,
        "content": comment.body,
        "clientPrice": 5.0,
        "taskSubmission": [],
        "publishedAt": datetime.now(UTC).isoformat() if status == "published" else None,
    }

    if status == "published":
        url = submission_url or f"https://reddit.com/r/example/comments/sim/{comment_id[:8]}"
        fake_payload["taskSubmission"] = [{"submissionUrl": url}]

    return await handle_crowdreply_webhook(fake_payload, db)
