"""Projects API router.

REST endpoints for managing projects with CRUD operations.
"""

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_session
from app.core.logging import get_logger
from app.integrations.crawl4ai import Crawl4AIClient, get_crawl4ai
from app.integrations.s3 import S3Client, get_s3
from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.project import Project
from app.schemas.crawled_page import (
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
                crawl_progress["completed"] = crawl_progress.get("completed", 0) + success_count
                crawl_progress["failed"] = crawl_progress.get("failed", 0) + failed_count
                flag_modified(project, "phase_status")
                await db.commit()

            # Check if all pages for this project are done (no pending or crawling)
            stmt = select(CrawledPage).where(CrawledPage.project_id == project_id)
            result = await db.execute(stmt)
            all_pages = list(result.scalars().all())

            pending_or_crawling = sum(
                1 for p in all_pages
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
            assignments = await taxonomy_service.assign_labels(
                db, project_id, taxonomy
            )
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


@router.get("/{project_id}/crawl-status", response_model=CrawlStatusResponse)
async def get_crawl_status(
    project_id: str,
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

    # Get all pages for this project
    stmt = select(CrawledPage).where(CrawledPage.project_id == project_id)
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
