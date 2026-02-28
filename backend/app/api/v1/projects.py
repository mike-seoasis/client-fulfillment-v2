"""Projects API router.

REST endpoints for managing projects with CRUD operations.
"""

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_session
from app.core.logging import get_logger
from app.integrations.crawl4ai import Crawl4AIClient, get_crawl4ai
from app.integrations.s3 import S3Client, get_s3
from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.page_keywords import PageKeywords
from app.models.project import Project
from app.schemas.crawled_page import (
    BulkDeleteRequest,
    BulkDeleteResponse,
    CrawledPageResponse,
    CrawlStatusResponse,
    PageLabelsUpdate,
    PageSummary,
    ProgressCounts,
    TaxonomyLabel,
    TaxonomyResponse,
    UrlsUploadRequest,
    UrlUploadResponse,
)
from app.schemas.keyword_research import (
    BulkApproveResponse,
    PageKeywordsData,
    PageWithKeywords,
    PrimaryKeywordGenerationStatus,
    UpdatePrimaryKeywordRequest,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.crawling import CrawlingService
from app.services.label_taxonomy import validate_page_labels
from app.services.project import ProjectService

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: AsyncSession = Depends(get_session),
) -> ProjectListResponse:
    """List all projects.

    Returns projects ordered by most recently updated.
    """
    projects = await ProjectService.list_projects(db)
    items = await ProjectService.to_response_list(db, projects)
    return ProjectListResponse(
        items=items,
        total=len(projects),
        limit=max(len(projects), 1),  # Minimum of 1 to satisfy schema constraint
        offset=0,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Create a new project.

    Args:
        data: Project creation data with name and site_url (required).

    Returns:
        The newly created project.
    """
    project = await ProjectService.create_project(db, data)
    return await ProjectService.to_response(db, project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Get a project by ID.

    Args:
        project_id: UUID of the project.

    Returns:
        The project if found.

    Raises:
        HTTPException: 404 if project not found.
    """
    project = await ProjectService.get_project(db, project_id)
    return await ProjectService.to_response(db, project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    """Update a project.

    Args:
        project_id: UUID of the project.
        data: Fields to update (all optional).

    Returns:
        The updated project.

    Raises:
        HTTPException: 404 if project not found.
    """
    project = await ProjectService.update_project(db, project_id, data)
    return await ProjectService.to_response(db, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_session),
    s3: S3Client = Depends(get_s3),
) -> None:
    """Delete a project and all associated files from storage.

    This endpoint:
    1. Deletes all project files from S3 storage
    2. Deletes the project record (cascades to delete ProjectFile records)

    Args:
        project_id: UUID of the project.

    Raises:
        HTTPException: 404 if project not found.
    """
    await ProjectService.delete_project(db, project_id, s3_client=s3)


def _normalize_url(url: str) -> str:
    """Normalize a URL for deduplication.

    Strips whitespace and removes trailing slashes (except for root paths).

    Args:
        url: Raw URL string.

    Returns:
        Normalized URL.
    """
    url = url.strip()
    # Remove trailing slash unless it's the root path
    if url.endswith("/") and not url.endswith("://"):
        # Count slashes after protocol
        protocol_end = url.find("://")
        if protocol_end != -1:
            path_part = url[protocol_end + 3 :]
            # Only strip if there's more than just the domain
            if "/" in path_part and path_part != "/":
                url = url.rstrip("/")
    return url


@router.post(
    "/{project_id}/urls",
    response_model=UrlUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_urls(
    project_id: str,
    data: UrlsUploadRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    crawl4ai: Crawl4AIClient = Depends(get_crawl4ai),
) -> UrlUploadResponse:
    """Upload URLs for crawling.

    Creates CrawledPage records for each new URL and starts a background
    task to crawl them. Duplicate URLs (already exist for this project)
    are skipped.

    Args:
        project_id: UUID of the project.
        data: Request with list of URLs to upload.
        background_tasks: FastAPI background tasks.
        db: AsyncSession for database operations.
        crawl4ai: Crawl4AI client for crawling.

    Returns:
        Response with task_id, pages_created count, and pages_skipped count.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Normalize URLs
    normalized_urls = [_normalize_url(url) for url in data.urls]

    # Find existing URLs for this project
    stmt = select(CrawledPage.normalized_url).where(
        CrawledPage.project_id == project_id,
        CrawledPage.normalized_url.in_(normalized_urls),
    )
    result = await db.execute(stmt)
    existing_urls = set(result.scalars().all())

    # Compute next batch number for onboarding pages
    max_batch_result = await db.execute(
        select(func.max(CrawledPage.onboarding_batch)).where(
            CrawledPage.project_id == project_id,
            CrawledPage.source == "onboarding",
        )
    )
    next_batch = (max_batch_result.scalar_one_or_none() or 0) + 1

    # Create CrawledPage records for new URLs only
    new_page_ids: list[str] = []
    pages_created = 0
    pages_skipped = 0

    for i, normalized_url in enumerate(normalized_urls):
        if normalized_url in existing_urls:
            pages_skipped += 1
            logger.debug(
                "Skipping duplicate URL",
                extra={"url": normalized_url, "project_id": project_id},
            )
            continue

        # Create new CrawledPage record
        page = CrawledPage(
            project_id=project_id,
            normalized_url=normalized_url,
            raw_url=data.urls[i],  # Store original URL
            status=CrawlStatus.PENDING.value,
            onboarding_batch=next_batch,
        )
        db.add(page)
        await db.flush()  # Get the page ID
        new_page_ids.append(page.id)
        pages_created += 1

        # Add to existing set to handle duplicates within the batch
        existing_urls.add(normalized_url)

    # Commit all new pages
    await db.commit()

    # If we created new pages, update project phase_status to 'crawling'
    if pages_created > 0:
        project = await db.get(Project, project_id)
        if project:
            if "onboarding" not in project.phase_status:
                project.phase_status["onboarding"] = {}
            project.phase_status["onboarding"]["status"] = "crawling"
            # Initialize crawl progress tracking
            project.phase_status["onboarding"]["crawl"] = {
                "total": pages_created,
                "completed": 0,
                "failed": 0,
                "started_at": datetime.now().isoformat(),
            }
            flag_modified(project, "phase_status")
            await db.commit()

    # Generate task ID for tracking
    task_id = str(uuid4())

    logger.info(
        "URLs uploaded for crawling",
        extra={
            "project_id": project_id,
            "task_id": task_id,
            "total_urls": len(data.urls),
            "pages_created": pages_created,
            "pages_skipped": pages_skipped,
        },
    )

    # Start background crawl task if there are new pages
    if new_page_ids:
        background_tasks.add_task(
            _crawl_pages_background,
            project_id=project_id,
            page_ids=new_page_ids,
            task_id=task_id,
            crawl4ai_client=crawl4ai,
        )

    return UrlUploadResponse(
        task_id=task_id,
        pages_created=pages_created,
        pages_skipped=pages_skipped,
        total_urls=len(data.urls),
        batch=next_batch,
    )


async def _crawl_pages_background(
    project_id: str,
    page_ids: list[str],
    task_id: str,
    crawl4ai_client: Crawl4AIClient,
) -> None:
    """Background task to crawl pages.

    This function runs outside the request context, so it creates
    its own database session.

    After crawling completes, if all pages for the project are done
    (completed or failed), this task automatically triggers:
    1. Taxonomy generation
    2. Label assignment to all pages

    Args:
        project_id: Project ID for logging.
        page_ids: List of CrawledPage IDs to crawl.
        task_id: Task ID for tracking/logging.
        crawl4ai_client: Crawl4AI client instance.
    """
    from app.core.database import db_manager
    from app.integrations.claude import get_claude
    from app.services.label_taxonomy import LabelTaxonomyService

    logger.info(
        "Starting background crawl task",
        extra={
            "project_id": project_id,
            "task_id": task_id,
            "page_count": len(page_ids),
        },
    )

    try:
        async with db_manager.session_factory() as db:
            service = CrawlingService(crawl4ai_client)
            results = await service.crawl_urls(db, page_ids)
            await db.commit()

            success_count = sum(1 for r in results.values() if r.success)
            failed_count = len(page_ids) - success_count

            logger.info(
                "Background crawl task completed",
                extra={
                    "project_id": project_id,
                    "task_id": task_id,
                    "total_pages": len(page_ids),
                    "successful": success_count,
                    "failed": failed_count,
                },
            )

            # Update crawl progress in phase_status
            project = await db.get(Project, project_id)
            if project:
                if "onboarding" not in project.phase_status:
                    project.phase_status["onboarding"] = {}
                if "crawl" not in project.phase_status["onboarding"]:
                    project.phase_status["onboarding"]["crawl"] = {
                        "total": len(page_ids),
                        "completed": 0,
                        "failed": 0,
                    }
                # Increment progress (handles incremental crawling)
                crawl_progress = project.phase_status["onboarding"]["crawl"]
                crawl_progress["completed"] = (
                    crawl_progress.get("completed", 0) + success_count
                )
                crawl_progress["failed"] = (
                    crawl_progress.get("failed", 0) + failed_count
                )
                flag_modified(project, "phase_status")
                await db.commit()

            # Check if all pages for this project are done (no pending or crawling)
            stmt = select(CrawledPage).where(CrawledPage.project_id == project_id)
            result = await db.execute(stmt)
            all_pages = list(result.scalars().all())

            pending_or_crawling = sum(
                1
                for p in all_pages
                if p.status in (CrawlStatus.PENDING.value, CrawlStatus.CRAWLING.value)
            )

            if pending_or_crawling > 0:
                logger.info(
                    "Not all pages complete, skipping taxonomy generation",
                    extra={
                        "project_id": project_id,
                        "task_id": task_id,
                        "pending_or_crawling": pending_or_crawling,
                    },
                )
                return

            # All pages are done - trigger taxonomy generation and label assignment
            logger.info(
                "All pages complete, starting taxonomy generation",
                extra={
                    "project_id": project_id,
                    "task_id": task_id,
                },
            )

            # Update project phase_status to 'labeling'
            project = await db.get(Project, project_id)
            if project:
                if "onboarding" not in project.phase_status:
                    project.phase_status["onboarding"] = {}
                project.phase_status["onboarding"]["status"] = "labeling"
                flag_modified(project, "phase_status")
                await db.commit()

            # Get Claude client and create taxonomy service
            claude_client = await get_claude()
            taxonomy_service = LabelTaxonomyService(claude_client)

            # Generate taxonomy
            taxonomy = await taxonomy_service.generate_taxonomy(db, project_id)
            await db.commit()

            if not taxonomy:
                logger.error(
                    "Taxonomy generation failed",
                    extra={
                        "project_id": project_id,
                        "task_id": task_id,
                    },
                )
                return

            logger.info(
                "Taxonomy generated, starting label assignment",
                extra={
                    "project_id": project_id,
                    "task_id": task_id,
                    "label_count": len(taxonomy.labels),
                },
            )

            # Assign labels to all pages
            assignments = await taxonomy_service.assign_labels(db, project_id, taxonomy)
            await db.commit()

            # Update project phase_status to 'labels_complete'
            project = await db.get(Project, project_id)
            if project:
                project.phase_status["onboarding"]["status"] = "labels_complete"
                flag_modified(project, "phase_status")
                await db.commit()

            successful_assignments = sum(1 for a in assignments if a.success)
            logger.info(
                "Label assignment completed",
                extra={
                    "project_id": project_id,
                    "task_id": task_id,
                    "total_assignments": len(assignments),
                    "successful": successful_assignments,
                    "failed": len(assignments) - successful_assignments,
                },
            )

    except Exception as e:
        logger.error(
            "Background crawl task failed",
            extra={
                "project_id": project_id,
                "task_id": task_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )


def _compute_overall_status(
    pending: int, crawling: int, completed: int, failed: int, has_labels: bool
) -> str:
    """Compute overall crawl status from page counts.

    Args:
        pending: Number of pending pages.
        crawling: Number of crawling pages.
        completed: Number of completed pages.
        failed: Number of failed pages.
        has_labels: Whether any completed pages have labels assigned.

    Returns:
        Overall status: "crawling", "labeling", or "complete"
    """
    # If any pages are still being crawled or pending, status is "crawling"
    if crawling > 0 or pending > 0:
        return "crawling"

    # If all pages are done (completed or failed) but no labels yet, status is "labeling"
    # (labeling happens after crawling completes)
    if not has_labels and completed > 0:
        return "labeling"

    # All done with labels assigned
    return "complete"


@router.get("/{project_id}/pages", response_model=list[CrawledPageResponse])
async def list_project_pages(
    project_id: str,
    status: str | None = None,
    db: AsyncSession = Depends(get_session),
) -> list[CrawledPageResponse]:
    """List all crawled pages for a project.

    Returns all pages with their full details including labels, content,
    and crawl status. Optionally filter by crawl status.

    Args:
        project_id: UUID of the project.
        status: Optional status filter (pending, crawling, completed, failed).
        db: AsyncSession for database operations.

    Returns:
        List of CrawledPageResponse objects.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Build query
    stmt = select(CrawledPage).where(CrawledPage.project_id == project_id)

    # Apply optional status filter
    if status is not None:
        stmt = stmt.where(CrawledPage.status == status)

    result = await db.execute(stmt)
    pages = result.scalars().all()

    return [CrawledPageResponse.model_validate(page) for page in pages]


@router.get("/{project_id}/onboarding-batches")
async def list_onboarding_batches(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> list[dict]:
    """List all onboarding batches for a project with per-batch pipeline status.

    Returns batch number, page counts, pipeline status, and creation timestamp.
    """
    from app.models.page_content import PageContent
    from app.models.page_keywords import PageKeywords as PK

    await ProjectService.get_project(db, project_id)

    # Load all onboarding pages with keywords and content eagerly
    from sqlalchemy.orm import selectinload

    stmt = (
        select(CrawledPage)
        .where(
            CrawledPage.project_id == project_id,
            CrawledPage.source == "onboarding",
            CrawledPage.onboarding_batch.isnot(None),
        )
        .options(
            selectinload(CrawledPage.keywords),
            selectinload(CrawledPage.page_content),
        )
        .order_by(CrawledPage.onboarding_batch, CrawledPage.created_at)
    )
    result = await db.execute(stmt)
    pages = result.scalars().unique().all()

    # Group pages by batch
    batches: dict[int, list] = {}
    for page in pages:
        b = page.onboarding_batch
        if b not in batches:
            batches[b] = []
        batches[b].append(page)

    # Compute per-batch status
    summaries = []
    for batch_num in sorted(batches.keys()):
        batch_pages = batches[batch_num]
        total = len(batch_pages)
        completed = sum(
            1
            for p in batch_pages
            if p.page_content and p.page_content.is_approved
        )

        # Determine pipeline status
        any_pending_crawl = any(
            p.status in ("pending", "crawling") for p in batch_pages
        )
        all_crawled = all(p.status == "completed" for p in batch_pages)
        has_keywords = any(p.keywords and p.keywords.primary_keyword for p in batch_pages)
        all_have_keywords = all(
            p.keywords and p.keywords.primary_keyword for p in batch_pages
        )
        has_content = any(p.page_content for p in batch_pages)
        all_approved_content = all(
            p.page_content and p.page_content.is_approved for p in batch_pages
        )

        if any_pending_crawl or not all_crawled:
            pipeline_status = "crawling"
        elif not all_have_keywords:
            pipeline_status = "keywords"
        elif not all_approved_content:
            pipeline_status = "content"
        else:
            pipeline_status = "complete"

        # Earliest created_at in the batch
        created_at = min(p.created_at for p in batch_pages).isoformat()

        summaries.append(
            {
                "batch": batch_num,
                "total_pages": total,
                "completed_pages": completed,
                "pipeline_status": pipeline_status,
                "created_at": created_at,
            }
        )

    return summaries


@router.get("/{project_id}/crawl-status", response_model=CrawlStatusResponse)
async def get_crawl_status(
    project_id: str,
    batch: int | None = Query(None, description="Filter by onboarding batch number"),
    db: AsyncSession = Depends(get_session),
) -> CrawlStatusResponse:
    """Get crawl status for a project.

    Returns the overall crawl status, progress counts by status, and a summary
    of each page including id, url, status, and extracted data summary.

    This endpoint is designed to be polled frequently (every 2 seconds) by the
    frontend to track crawl progress.

    Args:
        project_id: UUID of the project.
        db: AsyncSession for database operations.

    Returns:
        CrawlStatusResponse with status, progress counts, and pages array.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Get onboarding pages for this project (crawl status is for onboarding flow only)
    stmt = select(CrawledPage).where(
        CrawledPage.project_id == project_id,
        CrawledPage.source == "onboarding",
    )
    if batch is not None:
        stmt = stmt.where(CrawledPage.onboarding_batch == batch)
    result = await db.execute(stmt)
    pages = result.scalars().all()

    # Count pages by status
    pending_count = 0
    crawling_count = 0
    completed_count = 0
    failed_count = 0
    has_labels = False

    for page in pages:
        if page.status == CrawlStatus.PENDING.value:
            pending_count += 1
        elif page.status == CrawlStatus.CRAWLING.value:
            crawling_count += 1
        elif page.status == CrawlStatus.COMPLETED.value:
            completed_count += 1
            if page.labels:
                has_labels = True
        elif page.status == CrawlStatus.FAILED.value:
            failed_count += 1

    # Compute overall status
    overall_status = _compute_overall_status(
        pending=pending_count,
        crawling=crawling_count,
        completed=completed_count,
        failed=failed_count,
        has_labels=has_labels,
    )

    # Build page summaries
    page_summaries = [
        PageSummary(
            id=page.id,
            url=page.normalized_url,
            status=page.status,
            title=page.title,
            word_count=page.word_count,
            headings=page.headings,
            product_count=page.product_count,
            labels=page.labels or [],
            crawl_error=page.crawl_error,
        )
        for page in pages
    ]

    return CrawlStatusResponse(
        project_id=project_id,
        status=overall_status,
        progress=ProgressCounts(
            total=len(pages),
            completed=completed_count,
            failed=failed_count,
            pending=pending_count,
        ),
        pages=page_summaries,
    )


@router.get("/{project_id}/taxonomy", response_model=TaxonomyResponse)
async def get_project_taxonomy(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> TaxonomyResponse:
    """Get the label taxonomy for a project.

    Returns the generated taxonomy with labels and their definitions.
    The taxonomy is generated by analyzing all crawled pages for the project.

    Args:
        project_id: UUID of the project.
        db: AsyncSession for database operations.

    Returns:
        TaxonomyResponse with labels array and generated_at timestamp.

    Raises:
        HTTPException: 404 if project not found or taxonomy not yet generated.
    """
    # Get project (raises 404 if not found)
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Get taxonomy from phase_status
    taxonomy_data = project.phase_status.get("onboarding", {}).get("taxonomy")
    if not taxonomy_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Taxonomy not yet generated for this project",
        )

    # Parse labels
    labels = [
        TaxonomyLabel(
            name=label.get("name", ""),
            description=label.get("description", ""),
            examples=label.get("examples", []),
        )
        for label in taxonomy_data.get("labels", [])
    ]

    # Parse generated_at timestamp
    generated_at_str = taxonomy_data.get("generated_at")
    if generated_at_str:
        generated_at = datetime.fromisoformat(generated_at_str)
    else:
        # Fallback for old data without timestamp
        generated_at = datetime.now()

    return TaxonomyResponse(
        labels=labels,
        generated_at=generated_at,
    )


@router.post(
    "/{project_id}/taxonomy/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_taxonomy(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Regenerate the label taxonomy and reassign labels to all pages.

    This will:
    1. Generate a new taxonomy based on all completed pages
    2. Reassign labels to all pages using the new taxonomy
    3. Update the project phase_status

    Args:
        project_id: UUID of the project.
        background_tasks: FastAPI background tasks.
        db: AsyncSession for database operations.

    Returns:
        Dict with status message.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Set status to indicate labeling is in progress
    if "onboarding" not in project.phase_status:
        project.phase_status["onboarding"] = {}
    project.phase_status["onboarding"]["status"] = "labeling"

    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(project, "phase_status")
    await db.commit()

    # Run taxonomy regeneration in background
    async def regenerate_labels_task() -> None:
        from app.core.database import db_manager
        from app.integrations.claude import ClaudeClient, get_api_key
        from app.services.label_taxonomy import LabelTaxonomyService

        async with db_manager.session_factory() as task_db:
            try:
                claude_client = ClaudeClient(api_key=get_api_key())
                taxonomy_service = LabelTaxonomyService(claude_client)

                # Generate new taxonomy
                taxonomy = await taxonomy_service.generate_taxonomy(task_db, project_id)
                if not taxonomy:
                    logger.error(
                        "Failed to regenerate taxonomy",
                        extra={"project_id": project_id},
                    )
                    return

                # Assign labels to all pages
                await taxonomy_service.assign_labels(task_db, project_id, taxonomy)

                # Update phase_status
                task_project = await task_db.get(Project, project_id)
                if task_project:
                    task_project.phase_status["onboarding"]["status"] = (
                        "labels_complete"
                    )
                    flag_modified(task_project, "phase_status")

                await task_db.commit()

                logger.info(
                    "Taxonomy regeneration complete",
                    extra={
                        "project_id": project_id,
                        "label_count": len(taxonomy.labels),
                    },
                )

            except Exception as e:
                logger.error(
                    "Error during taxonomy regeneration",
                    extra={"project_id": project_id, "error": str(e)},
                )

    background_tasks.add_task(regenerate_labels_task)

    return {"status": "Taxonomy regeneration started"}


@router.post(
    "/{project_id}/pages/{page_id}/retry",
    response_model=CrawledPageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_page_crawl(
    project_id: str,
    page_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    crawl4ai: Crawl4AIClient = Depends(get_crawl4ai),
) -> CrawledPageResponse:
    """Retry crawling a failed page.

    Resets the page status to 'pending', clears any crawl error, and starts
    a background task to crawl the page.

    Args:
        project_id: UUID of the project.
        page_id: UUID of the crawled page.
        background_tasks: FastAPI background tasks.
        db: AsyncSession for database operations.
        crawl4ai: Crawl4AI client for crawling.

    Returns:
        Updated CrawledPageResponse with status reset to 'pending'.

    Raises:
        HTTPException: 404 if project or page not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Get the page
    page = await db.get(CrawledPage, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )

    # Verify page belongs to this project
    if page.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found in project {project_id}",
        )

    # Reset page status to pending and clear error
    page.status = CrawlStatus.PENDING.value
    page.crawl_error = None
    await db.commit()
    await db.refresh(page)

    logger.info(
        "Page retry initiated",
        extra={
            "project_id": project_id,
            "page_id": page_id,
            "url": page.normalized_url,
        },
    )

    # Start background crawl task for this single page
    background_tasks.add_task(
        _crawl_pages_background,
        project_id=project_id,
        page_ids=[page_id],
        task_id=str(uuid4()),
        crawl4ai_client=crawl4ai,
    )

    return CrawledPageResponse.model_validate(page)


@router.post(
    "/{project_id}/pages/retry-pending",
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_pending_pages(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    crawl4ai: Crawl4AIClient = Depends(get_crawl4ai),
) -> dict[str, int]:
    """Retry crawling all pending pages for a project.

    Finds all pages with 'pending' status and starts a background task
    to crawl them.

    Args:
        project_id: UUID of the project.
        background_tasks: FastAPI background tasks.
        db: AsyncSession for database operations.
        crawl4ai: Crawl4AI client for crawling.

    Returns:
        Dict with count of pages being retried.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Find all pending pages
    stmt = (
        select(CrawledPage.id)
        .where(CrawledPage.project_id == project_id)
        .where(CrawledPage.status == CrawlStatus.PENDING.value)
    )
    result = await db.execute(stmt)
    page_ids = list(result.scalars().all())

    if not page_ids:
        return {"pages_queued": 0}

    logger.info(
        "Retry pending pages initiated",
        extra={
            "project_id": project_id,
            "page_count": len(page_ids),
        },
    )

    # Start background crawl task for all pending pages
    background_tasks.add_task(
        _crawl_pages_background,
        project_id=project_id,
        page_ids=page_ids,
        task_id=str(uuid4()),
        crawl4ai_client=crawl4ai,
    )

    return {"pages_queued": len(page_ids)}


@router.post(
    "/{project_id}/pages/recrawl-all",
    status_code=status.HTTP_202_ACCEPTED,
)
async def recrawl_all_pages(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    crawl4ai: Crawl4AIClient = Depends(get_crawl4ai),
) -> dict[str, int]:
    """Re-crawl all pages for a project.

    Resets all pages to 'pending' status and starts a background task
    to crawl them. Useful for refreshing data after extraction improvements.

    Args:
        project_id: UUID of the project.
        background_tasks: FastAPI background tasks.
        db: AsyncSession for database operations.
        crawl4ai: Crawl4AI client for crawling.

    Returns:
        Dict with count of pages being re-crawled.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Reset all pages to pending
    stmt = select(CrawledPage).where(CrawledPage.project_id == project_id)
    result = await db.execute(stmt)
    pages = list(result.scalars().all())

    if not pages:
        return {"pages_queued": 0}

    page_ids = []
    for page in pages:
        page.status = CrawlStatus.PENDING.value
        page.crawl_error = None
        page_ids.append(page.id)

    # Update project phase status
    if "onboarding" not in project.phase_status:
        project.phase_status["onboarding"] = {}
    project.phase_status["onboarding"]["status"] = "crawling"

    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(project, "phase_status")

    await db.commit()

    logger.info(
        "Recrawl all pages initiated",
        extra={
            "project_id": project_id,
            "page_count": len(page_ids),
        },
    )

    # Start background crawl task
    background_tasks.add_task(
        _crawl_pages_background,
        project_id=project_id,
        page_ids=page_ids,
        task_id=str(uuid4()),
        crawl4ai_client=crawl4ai,
    )

    return {"pages_queued": len(page_ids)}


@router.post(
    "/{project_id}/generate-primary-keywords",
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_primary_keywords(
    project_id: str,
    background_tasks: BackgroundTasks,
    batch: int | None = Query(None, description="Filter by onboarding batch number"),
    db: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Start primary keyword generation for all completed pages in a project.

    This endpoint:
    1. Validates project exists and has crawled pages with status=completed
    2. Updates project.phase_status to 'generating_keywords'
    3. Starts a background task to generate keywords for all pages
    4. Returns 202 Accepted with a task_id for tracking

    Args:
        project_id: UUID of the project.
        background_tasks: FastAPI background tasks.
        db: AsyncSession for database operations.

    Returns:
        Dict with task_id and status message.

    Raises:
        HTTPException: 404 if project not found.
        HTTPException: 400 if no completed pages exist.
    """
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Check for completed pages
    stmt = select(CrawledPage).where(
        CrawledPage.project_id == project_id,
        CrawledPage.status == CrawlStatus.COMPLETED.value,
    )
    if batch is not None:
        stmt = stmt.where(CrawledPage.onboarding_batch == batch)
    result = await db.execute(stmt)
    completed_pages = list(result.scalars().all())

    if not completed_pages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed pages found. Please crawl pages first.",
        )

    # Generate task ID
    task_id = str(uuid4())

    # Update project phase_status to indicate keyword generation starting
    if "onboarding" not in project.phase_status:
        project.phase_status["onboarding"] = {}
    project.phase_status["onboarding"]["status"] = "generating_keywords"
    project.phase_status["onboarding"]["keywords"] = {
        "status": "pending",
        "total": len(completed_pages),
        "completed": 0,
        "failed": 0,
        "current_page": None,
        "task_id": task_id,
    }
    flag_modified(project, "phase_status")
    await db.commit()

    logger.info(
        "Starting primary keyword generation",
        extra={
            "project_id": project_id,
            "task_id": task_id,
            "page_count": len(completed_pages),
        },
    )

    # Start background task
    background_tasks.add_task(
        _generate_keywords_background,
        project_id=project_id,
        task_id=task_id,
        batch=batch,
    )

    return {
        "task_id": task_id,
        "status": "Keyword generation started",
        "page_count": str(len(completed_pages)),
    }


async def _generate_keywords_background(
    project_id: str,
    task_id: str,
    batch: int | None = None,
) -> None:
    """Background task to generate primary keywords for all pages.

    This function runs outside the request context, so it creates
    its own database session and client instances.

    Args:
        project_id: Project ID.
        task_id: Task ID for tracking/logging.
    """
    from app.core.database import db_manager
    from app.integrations.claude import ClaudeClient
    from app.integrations.dataforseo import DataForSEOClient
    from app.services.primary_keyword import PrimaryKeywordService

    logger.info(
        "Starting background keyword generation task",
        extra={
            "project_id": project_id,
            "task_id": task_id,
        },
    )

    try:
        async with db_manager.session_factory() as db:
            # Create clients — explicit api_key for background task context
            from app.integrations.claude import get_api_key

            claude_client = ClaudeClient(api_key=get_api_key())
            dataforseo_client = DataForSEOClient()

            # Create service
            keyword_service = PrimaryKeywordService(
                claude_client=claude_client,
                dataforseo_client=dataforseo_client,
            )

            # Run generation for the project
            result = await keyword_service.generate_for_project(project_id, db, batch=batch)

            logger.info(
                "Background keyword generation completed",
                extra={
                    "project_id": project_id,
                    "task_id": task_id,
                    "status": result.get("status"),
                    "total": result.get("total"),
                    "completed": result.get("completed"),
                    "failed": result.get("failed"),
                },
            )

    except Exception as e:
        logger.error(
            "Background keyword generation failed",
            extra={
                "project_id": project_id,
                "task_id": task_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )

        # Try to update phase_status with failure
        try:
            async with db_manager.session_factory() as db:
                project = await db.get(Project, project_id)
                if project:
                    if "onboarding" not in project.phase_status:
                        project.phase_status["onboarding"] = {}
                    project.phase_status["onboarding"]["keywords"] = {
                        "status": "failed",
                        "error": str(e),
                    }
                    flag_modified(project, "phase_status")
                    await db.commit()
        except Exception as update_error:
            logger.error(
                "Failed to update project phase_status after error",
                extra={
                    "project_id": project_id,
                    "error": str(update_error),
                },
            )


@router.get(
    "/{project_id}/primary-keywords-status",
    response_model=PrimaryKeywordGenerationStatus,
)
async def get_primary_keywords_status(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> PrimaryKeywordGenerationStatus:
    """Get status of primary keyword generation for a project.

    Returns the current generation status including progress counts
    and the page currently being processed. This endpoint is designed
    to be polled by the frontend during keyword generation.

    Args:
        project_id: UUID of the project.
        db: AsyncSession for database operations.

    Returns:
        PrimaryKeywordGenerationStatus with status, progress, and current_page.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Get project (raises 404 if not found)
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Extract keyword generation status from phase_status
    onboarding = project.phase_status.get("onboarding", {})
    keywords_status = onboarding.get("keywords", {})

    # Build response with defaults for missing fields
    return PrimaryKeywordGenerationStatus(
        status=keywords_status.get("status", "pending"),
        total=keywords_status.get("total", 0),
        completed=keywords_status.get("completed", 0),
        failed=keywords_status.get("failed", 0),
        current_page=keywords_status.get("current_page"),
        error=keywords_status.get("error"),
    )


@router.get(
    "/{project_id}/pages-with-keywords",
    response_model=list[PageWithKeywords],
)
async def list_pages_with_keywords(
    project_id: str,
    batch: int | None = Query(None, description="Filter by onboarding batch number"),
    db: AsyncSession = Depends(get_session),
) -> list[PageWithKeywords]:
    """List all completed pages with their keyword research data.

    Returns crawled pages (status=completed) with their associated PageKeywords
    data, including primary keyword, scores, and alternative keywords.

    This endpoint is used by the keyword approval interface to display
    all pages that have completed keyword generation.

    Args:
        project_id: UUID of the project.
        db: AsyncSession for database operations.

    Returns:
        List of PageWithKeywords objects ordered by URL.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Query completed pages with their keywords using joinedload for efficiency
    stmt = (
        select(CrawledPage)
        .options(joinedload(CrawledPage.keywords))
        .where(
            CrawledPage.project_id == project_id,
            CrawledPage.status == CrawlStatus.COMPLETED.value,
        )
        .order_by(CrawledPage.normalized_url)
    )
    if batch is not None:
        stmt = stmt.where(CrawledPage.onboarding_batch == batch)

    result = await db.execute(stmt)
    pages = result.scalars().unique().all()

    # Map to response schema
    response_pages: list[PageWithKeywords] = []
    for page in pages:
        # Build PageKeywordsData from the relationship if it exists
        keywords_data = None
        if page.keywords:
            keywords_data = PageKeywordsData(
                id=page.keywords.id,
                primary_keyword=page.keywords.primary_keyword,
                secondary_keywords=page.keywords.secondary_keywords or [],
                alternative_keywords=page.keywords.alternative_keywords or [],
                is_approved=page.keywords.is_approved,
                is_priority=page.keywords.is_priority,
                composite_score=page.keywords.composite_score,
                relevance_score=page.keywords.relevance_score,
                ai_reasoning=page.keywords.ai_reasoning,
                search_volume=page.keywords.search_volume,
                difficulty_score=page.keywords.difficulty_score,
            )

        response_pages.append(
            PageWithKeywords(
                id=page.id,
                url=page.normalized_url,
                title=page.title,
                labels=page.labels or [],
                product_count=page.product_count,
                keywords=keywords_data,
            )
        )

    return response_pages


@router.put(
    "/{project_id}/pages/{page_id}/primary-keyword",
    response_model=PageKeywordsData,
)
async def update_primary_keyword(
    project_id: str,
    page_id: str,
    data: UpdatePrimaryKeywordRequest,
    db: AsyncSession = Depends(get_session),
) -> PageKeywordsData:
    """Update the primary keyword for a page.

    Allows users to select a different keyword from the alternatives or
    type a custom keyword. For custom keywords, fetches volume data from
    DataForSEO and calculates a composite score automatically.

    Args:
        project_id: UUID of the project.
        page_id: UUID of the crawled page.
        data: UpdatePrimaryKeywordRequest with keyword field.
        db: AsyncSession for database operations.

    Returns:
        Updated PageKeywordsData with the new primary keyword.

    Raises:
        HTTPException: 404 if project, page, or page keywords not found.
    """
    import math

    from app.integrations.dataforseo import get_dataforseo

    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Get the page with keywords relationship
    stmt = (
        select(CrawledPage)
        .options(joinedload(CrawledPage.keywords))
        .where(
            CrawledPage.id == page_id,
            CrawledPage.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    page = result.scalar_one_or_none()

    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found in project {project_id}",
        )

    if not page.keywords:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keywords not yet generated for page {page_id}",
        )

    page_keywords: PageKeywords = page.keywords
    new_keyword = data.keyword.strip().lower()

    # Check if keyword is from alternatives (normalize for comparison)
    alternative_keywords = page_keywords.alternative_keywords or []
    is_from_alternatives = False

    for alt in alternative_keywords:
        # Handle both dict format (KeywordCandidate) and string format
        if isinstance(alt, dict):
            alt_keyword = alt.get("keyword", "").strip().lower()
        else:
            alt_keyword = str(alt).strip().lower()

        if alt_keyword == new_keyword:
            is_from_alternatives = True
            # If from alternatives, use the volume data from that alternative
            if isinstance(alt, dict):
                page_keywords.search_volume = alt.get("volume")
                page_keywords.composite_score = alt.get("composite_score")
                page_keywords.relevance_score = alt.get("relevance_score")
            break

    # Update primary keyword
    page_keywords.primary_keyword = data.keyword.strip()

    # For custom keywords, fetch volume data from DataForSEO and score
    if not is_from_alternatives:
        dataforseo_client = await get_dataforseo()

        if dataforseo_client.available:
            try:
                volume_result = await dataforseo_client.get_keyword_volume(
                    [new_keyword]
                )

                if volume_result.success and volume_result.keywords:
                    kw_data = volume_result.keywords[0]
                    page_keywords.search_volume = kw_data.search_volume

                    # Calculate composite score (same formula as PrimaryKeywordService)
                    volume = kw_data.search_volume
                    competition = kw_data.competition
                    relevance = 0.8  # User-chosen keyword gets high default relevance

                    if volume is None or volume <= 0:
                        volume_score = 0.0
                    else:
                        volume_score = min(50.0, max(0.0, math.log10(volume) * 10))

                    if competition is None:
                        competition_score = 50.0
                    else:
                        norm_comp = (
                            competition / 100.0 if competition > 1.0 else competition
                        )
                        competition_score = (1.0 - norm_comp) * 100

                    relevance_score = relevance * 100
                    composite = (
                        (volume_score * 0.50)
                        + (relevance_score * 0.35)
                        + (competition_score * 0.15)
                    )

                    page_keywords.composite_score = round(composite, 2)
                    page_keywords.relevance_score = relevance

                    logger.info(
                        "Custom keyword enriched with volume data",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "keyword": new_keyword,
                            "search_volume": kw_data.search_volume,
                            "composite_score": round(composite, 2),
                        },
                    )
                else:
                    # DataForSEO lookup failed, clear metrics
                    page_keywords.search_volume = None
                    page_keywords.composite_score = None
                    page_keywords.relevance_score = None
                    logger.warning(
                        "Custom keyword volume lookup failed",
                        extra={
                            "project_id": project_id,
                            "page_id": page_id,
                            "keyword": new_keyword,
                            "error": volume_result.error,
                        },
                    )
            except Exception as e:
                # Don't fail the update if volume lookup fails
                page_keywords.search_volume = None
                page_keywords.composite_score = None
                page_keywords.relevance_score = None
                logger.warning(
                    "Custom keyword volume lookup error",
                    extra={
                        "project_id": project_id,
                        "page_id": page_id,
                        "keyword": new_keyword,
                        "error": str(e),
                    },
                )
        else:
            # DataForSEO not configured, clear metrics
            page_keywords.search_volume = None
            page_keywords.composite_score = None
            page_keywords.relevance_score = None
            logger.info(
                "Custom keyword set, DataForSEO not available for volume lookup",
                extra={
                    "project_id": project_id,
                    "page_id": page_id,
                    "keyword": new_keyword,
                },
            )

    await db.commit()
    await db.refresh(page_keywords)

    logger.info(
        "Primary keyword updated",
        extra={
            "project_id": project_id,
            "page_id": page_id,
            "keyword": data.keyword,
            "is_from_alternatives": is_from_alternatives,
        },
    )

    return PageKeywordsData(
        id=page_keywords.id,
        primary_keyword=page_keywords.primary_keyword,
        secondary_keywords=page_keywords.secondary_keywords or [],
        alternative_keywords=page_keywords.alternative_keywords or [],
        is_approved=page_keywords.is_approved,
        is_priority=page_keywords.is_priority,
        composite_score=page_keywords.composite_score,
        relevance_score=page_keywords.relevance_score,
        ai_reasoning=page_keywords.ai_reasoning,
        search_volume=page_keywords.search_volume,
        difficulty_score=page_keywords.difficulty_score,
    )


@router.post(
    "/{project_id}/pages/{page_id}/approve-keyword",
    response_model=PageKeywordsData,
)
async def approve_keyword(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
    value: bool = True,
) -> PageKeywordsData:
    """Approve or unapprove the primary keyword for a page.

    By default, sets is_approved=true. Pass value=false to unapprove.
    This allows users to undo an accidental approval.

    Args:
        project_id: UUID of the project.
        page_id: UUID of the crawled page.
        db: AsyncSession for database operations.
        value: Approval state to set (default: true).

    Returns:
        Updated PageKeywordsData with new is_approved value.

    Raises:
        HTTPException: 404 if project, page, or page keywords not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Get the page with keywords relationship
    stmt = (
        select(CrawledPage)
        .options(joinedload(CrawledPage.keywords))
        .where(
            CrawledPage.id == page_id,
            CrawledPage.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    page = result.scalar_one_or_none()

    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found in project {project_id}",
        )

    if not page.keywords:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keywords not yet generated for page {page_id}",
        )

    page_keywords: PageKeywords = page.keywords

    # Set is_approved to the specified value
    page_keywords.is_approved = value

    await db.commit()
    await db.refresh(page_keywords)

    logger.info(
        "Keyword approval updated",
        extra={
            "project_id": project_id,
            "page_id": page_id,
            "primary_keyword": page_keywords.primary_keyword,
            "is_approved": value,
        },
    )

    return PageKeywordsData(
        id=page_keywords.id,
        primary_keyword=page_keywords.primary_keyword,
        secondary_keywords=page_keywords.secondary_keywords or [],
        alternative_keywords=page_keywords.alternative_keywords or [],
        is_approved=page_keywords.is_approved,
        is_priority=page_keywords.is_priority,
        composite_score=page_keywords.composite_score,
        relevance_score=page_keywords.relevance_score,
        ai_reasoning=page_keywords.ai_reasoning,
        search_volume=page_keywords.search_volume,
        difficulty_score=page_keywords.difficulty_score,
    )


@router.post(
    "/{project_id}/approve-all-keywords",
    response_model=BulkApproveResponse,
)
async def approve_all_keywords(
    project_id: str,
    batch: int | None = Query(None, description="Filter by onboarding batch number"),
    db: AsyncSession = Depends(get_session),
) -> BulkApproveResponse:
    """Approve all keywords for pages in a project.

    Sets is_approved=true for all PageKeywords records in the project
    that have keywords generated. This is idempotent - calling multiple
    times has the same effect.

    Args:
        project_id: UUID of the project.
        db: AsyncSession for database operations.

    Returns:
        BulkApproveResponse with count of approved keywords.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Find all PageKeywords records for completed pages in this project
    stmt = (
        select(PageKeywords)
        .join(CrawledPage, PageKeywords.crawled_page_id == CrawledPage.id)
        .where(
            CrawledPage.project_id == project_id,
            CrawledPage.status == CrawlStatus.COMPLETED.value,
        )
    )
    if batch is not None:
        stmt = stmt.where(CrawledPage.onboarding_batch == batch)
    result = await db.execute(stmt)
    page_keywords_list = list(result.scalars().all())

    # Set is_approved=true for all records
    approved_count = 0
    for page_keywords in page_keywords_list:
        if not page_keywords.is_approved:
            page_keywords.is_approved = True
            approved_count += 1

    await db.commit()

    logger.info(
        "Bulk keyword approval completed",
        extra={
            "project_id": project_id,
            "approved_count": approved_count,
            "total_pages_with_keywords": len(page_keywords_list),
        },
    )

    return BulkApproveResponse(approved_count=approved_count)


@router.put(
    "/{project_id}/pages/{page_id}/priority",
    response_model=PageKeywordsData,
)
async def toggle_priority(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
    value: bool | None = None,
) -> PageKeywordsData:
    """Toggle or set the priority flag for a page's keywords.

    By default, toggles the is_priority value (true->false, false->true).
    If a value is provided in the query parameter, sets is_priority to that value.

    Priority pages will receive more internal links in Phase 5.

    Args:
        project_id: UUID of the project.
        page_id: UUID of the crawled page.
        db: AsyncSession for database operations.
        value: Optional explicit value to set (true/false). If not provided, toggles.

    Returns:
        Updated PageKeywordsData with the new is_priority value.

    Raises:
        HTTPException: 404 if project, page, or page keywords not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Get the page with keywords relationship
    stmt = (
        select(CrawledPage)
        .options(joinedload(CrawledPage.keywords))
        .where(
            CrawledPage.id == page_id,
            CrawledPage.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    page = result.scalar_one_or_none()

    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found in project {project_id}",
        )

    if not page.keywords:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keywords not yet generated for page {page_id}",
        )

    page_keywords: PageKeywords = page.keywords

    # Toggle or set the priority value
    if value is not None:
        page_keywords.is_priority = value
    else:
        page_keywords.is_priority = not page_keywords.is_priority

    await db.commit()
    await db.refresh(page_keywords)

    logger.info(
        "Priority toggled",
        extra={
            "project_id": project_id,
            "page_id": page_id,
            "is_priority": page_keywords.is_priority,
        },
    )

    return PageKeywordsData(
        id=page_keywords.id,
        primary_keyword=page_keywords.primary_keyword,
        secondary_keywords=page_keywords.secondary_keywords or [],
        alternative_keywords=page_keywords.alternative_keywords or [],
        is_approved=page_keywords.is_approved,
        is_priority=page_keywords.is_priority,
        composite_score=page_keywords.composite_score,
        relevance_score=page_keywords.relevance_score,
        ai_reasoning=page_keywords.ai_reasoning,
        search_volume=page_keywords.search_volume,
        difficulty_score=page_keywords.difficulty_score,
    )


@router.put(
    "/{project_id}/pages/{page_id}/labels",
    response_model=CrawledPageResponse,
)
async def update_page_labels(
    project_id: str,
    page_id: str,
    data: PageLabelsUpdate,
    db: AsyncSession = Depends(get_session),
) -> CrawledPageResponse:
    """Update labels for a crawled page.

    Validates that all labels exist in the project's taxonomy and that
    the label count is within the allowed range (2-5 labels).

    Args:
        project_id: UUID of the project.
        page_id: UUID of the crawled page.
        data: PageLabelsUpdate with labels array.
        db: AsyncSession for database operations.

    Returns:
        Updated CrawledPageResponse with new labels.

    Raises:
        HTTPException: 404 if project or page not found.
        HTTPException: 400 if labels fail validation.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Get the page
    page = await db.get(CrawledPage, page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found",
        )

    # Verify page belongs to this project
    if page.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found in project {project_id}",
        )

    # Validate labels against taxonomy
    validation_result = await validate_page_labels(db, project_id, data.labels)

    if not validation_result.valid:
        # Format error messages for response
        error_messages = validation_result.error_messages
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(error_messages),
        )

    # Update the page labels
    page.labels = validation_result.labels
    await db.commit()
    await db.refresh(page)

    logger.info(
        "Page labels updated",
        extra={
            "project_id": project_id,
            "page_id": page_id,
            "labels": validation_result.labels,
        },
    )

    return CrawledPageResponse.model_validate(page)


@router.get("/{project_id}/export")
async def export_csv(
    project_id: str,
    page_ids: str | None = None,
    export_label: str = "Onboarding",
    db: AsyncSession = Depends(get_session),
) -> Response:
    """Export approved content as a Matrixify-format CSV file.

    Args:
        project_id: UUID of the project.
        page_ids: Optional comma-separated list of CrawledPage UUIDs to filter.
        export_label: Label for the export task (e.g. "Onboarding" or a cluster name).
        db: AsyncSession for database operations.

    Returns:
        CSV file download with Content-Disposition header.

    Raises:
        HTTPException: 404 if project not found.
        HTTPException: 400 if no approved pages available for export.
    """
    from app.services.export import ExportService

    # Get project (raises 404 if not found)
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Parse optional page_ids filter
    parsed_page_ids: list[str] | None = None
    if page_ids:
        parsed_page_ids = [pid.strip() for pid in page_ids.split(",") if pid.strip()]

    # Extract placeholder tag from BrandConfig.v2_schema.vocabulary
    from app.models.brand_config import BrandConfig

    shopify_tag = ""
    bc_stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
    bc_result = await db.execute(bc_stmt)
    brand_config = bc_result.scalar_one_or_none()
    if brand_config:
        vocabulary = brand_config.v2_schema.get("vocabulary", {})
        shopify_tag = vocabulary.get("shopify_placeholder_tag", "")

    # Generate CSV (onboarding = UPDATE, clusters will use NEW)
    csv_string, row_count = await ExportService.generate_csv(
        db,
        project_id,
        parsed_page_ids,
        command="UPDATE",
        shopify_placeholder_tag=shopify_tag,
    )

    if row_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No approved pages available for export",
        )

    # Build filename: "Project Name - Task - Matrixify Export via Grove.csv"
    safe_project = ExportService.safe_filename_part(project.name)
    safe_label = ExportService.safe_filename_part(export_label)
    filename = f"{safe_project} - {safe_label} - Matrixify Export via Grove.csv"

    return Response(
        content=csv_string,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ---------------------------------------------------------------------------
# Page deletion endpoints
# ---------------------------------------------------------------------------


@router.delete(
    "/{project_id}/pages/{page_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_page(
    project_id: str,
    page_id: str,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a single crawled page.

    Verifies the page belongs to the given project before deleting.
    Cascade rules on the CrawledPage model will remove related records.

    Args:
        project_id: UUID of the project.
        page_id: UUID of the page to delete.

    Raises:
        HTTPException: 404 if project or page not found.
    """
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Fetch the page and verify it belongs to this project
    page = await db.get(CrawledPage, page_id)
    if not page or page.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page_id} not found in project {project_id}",
        )

    await db.delete(page)
    await db.commit()


@router.post(
    "/{project_id}/pages/bulk-delete",
    response_model=BulkDeleteResponse,
)
async def bulk_delete_pages(
    project_id: str,
    data: BulkDeleteRequest,
    db: AsyncSession = Depends(get_session),
) -> BulkDeleteResponse:
    """Bulk-delete crawled pages by ID.

    Deletes all pages whose IDs are in the request body *and* belong to the
    specified project.  Pages that don't exist or belong to a different
    project are silently ignored.

    Uses POST instead of DELETE so the frontend apiClient can pass a body.

    Args:
        project_id: UUID of the project.
        data: Request body with list of page IDs to delete.

    Returns:
        Number of pages actually deleted.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    stmt = (
        delete(CrawledPage)
        .where(
            CrawledPage.project_id == project_id,
            CrawledPage.id.in_(data.page_ids),
        )
    )
    result = await db.execute(stmt)
    await db.commit()

    return BulkDeleteResponse(deleted_count=result.rowcount)


@router.post(
    "/{project_id}/onboarding/reset",
    response_model=BulkDeleteResponse,
)
async def reset_onboarding_pages(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> BulkDeleteResponse:
    """Reset onboarding by deleting all onboarding-sourced pages.

    Removes every CrawledPage for the project where ``source == 'onboarding'``.
    This allows the user to re-run the onboarding crawl from scratch.

    Args:
        project_id: UUID of the project.

    Returns:
        Number of pages deleted.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    stmt = (
        delete(CrawledPage)
        .where(
            CrawledPage.project_id == project_id,
            CrawledPage.source == "onboarding",
        )
    )
    result = await db.execute(stmt)
    await db.commit()

    return BulkDeleteResponse(deleted_count=result.rowcount)
