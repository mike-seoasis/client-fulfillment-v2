"""Clusters API router.

REST endpoints for creating, listing, updating, approving, and deleting keyword clusters.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_claude
from app.integrations.dataforseo import DataForSEOClient, get_dataforseo
from app.models.brand_config import BrandConfig
from app.models.crawled_page import CrawledPage, CrawlStatus
from app.models.keyword_cluster import ClusterPage, ClusterStatus, KeywordCluster
from app.models.page_keywords import PageKeywords
from app.schemas.cluster import (
    ClusterCreate,
    ClusterListResponse,
    ClusterPageResponse,
    ClusterPageUpdate,
    ClusterResponse,
)
from app.services.cluster_keyword import ClusterKeywordService
from app.services.project import ProjectService

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["Clusters"])

CLUSTER_GENERATION_TIMEOUT_SECONDS = 90


@router.post(
    "/{project_id}/clusters",
    response_model=ClusterResponse,
    status_code=status.HTTP_200_OK,
)
async def create_cluster(
    project_id: str,
    data: ClusterCreate,
    db: AsyncSession = Depends(get_session),
    claude: ClaudeClient = Depends(get_claude),
    dataforseo: DataForSEOClient = Depends(get_dataforseo),
) -> ClusterResponse:
    """Create a new keyword cluster from a seed keyword.

    Runs the iterative generation pipeline synchronously:
    1. LLM candidate generation (loops until 20+ with volume, max 4 iterations)
    2. DataForSEO volume enrichment (per iteration)
    3. LLM filtering and role assignment

    Args:
        project_id: UUID of the project.
        data: ClusterCreate with seed_keyword and optional name.
        db: AsyncSession for database operations.
        claude: Claude client for LLM calls.
        dataforseo: DataForSEO client for volume data.

    Returns:
        ClusterResponse with the created cluster and its pages.

    Raises:
        HTTPException: 404 if project not found.
        HTTPException: 422 if request body is invalid.
        HTTPException: 504 if generation exceeds 90s timeout.
        HTTPException: 500 if generation fails.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Fetch brand config for the project
    bc_stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
    bc_result = await db.execute(bc_stmt)
    brand_config_row = bc_result.scalar_one_or_none()
    brand_config: dict = brand_config_row.v2_schema if brand_config_row else {}

    # Run generation with timeout
    service = ClusterKeywordService(claude, dataforseo)
    try:
        result = await asyncio.wait_for(
            service.generate_cluster(
                seed_keyword=data.seed_keyword,
                project_id=project_id,
                brand_config=brand_config,
                db=db,
                name=data.name,
            ),
            timeout=CLUSTER_GENERATION_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Cluster generation timed out (>90s). Please try again.",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Load the created cluster with pages for response
    cluster_id = result["cluster_id"]
    stmt = (
        select(KeywordCluster)
        .options(selectinload(KeywordCluster.pages))
        .where(KeywordCluster.id == cluster_id)
    )
    cluster_result = await db.execute(stmt)
    cluster = cluster_result.scalar_one()

    return ClusterResponse.model_validate(cluster)


@router.get(
    "/{project_id}/clusters",
    response_model=list[ClusterListResponse],
)
async def list_clusters(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> list[ClusterListResponse]:
    """List all keyword clusters for a project.

    Returns clusters with computed page_count and approved_count
    from their ClusterPage records.

    Args:
        project_id: UUID of the project.
        db: AsyncSession for database operations.

    Returns:
        List of ClusterListResponse summaries.

    Raises:
        HTTPException: 404 if project not found.
    """
    # Verify project exists (raises 404 if not)
    await ProjectService.get_project(db, project_id)

    # Query clusters with page counts computed via subquery
    stmt = (
        select(
            KeywordCluster,
            func.count(ClusterPage.id).label("page_count"),
            func.count(
                func.nullif(ClusterPage.is_approved, False)  # noqa: E712
            ).label("approved_count"),
        )
        .outerjoin(ClusterPage, ClusterPage.cluster_id == KeywordCluster.id)
        .where(KeywordCluster.project_id == project_id)
        .group_by(KeywordCluster.id)
        .order_by(KeywordCluster.created_at.desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        ClusterListResponse(
            id=cluster.id,
            seed_keyword=cluster.seed_keyword,
            name=cluster.name,
            status=cluster.status,
            page_count=page_count,
            approved_count=approved_count,
            created_at=cluster.created_at,
        )
        for cluster, page_count, approved_count in rows
    ]


@router.get(
    "/{project_id}/clusters/{cluster_id}",
    response_model=ClusterResponse,
)
async def get_cluster(
    project_id: str,
    cluster_id: str,
    db: AsyncSession = Depends(get_session),
) -> ClusterResponse:
    """Get a single cluster with all its pages.

    Args:
        project_id: UUID of the project.
        cluster_id: UUID of the cluster.
        db: AsyncSession for database operations.

    Returns:
        ClusterResponse with nested ClusterPageResponse records.

    Raises:
        HTTPException: 404 if project or cluster not found.
    """
    await ProjectService.get_project(db, project_id)

    stmt = (
        select(KeywordCluster)
        .options(selectinload(KeywordCluster.pages))
        .where(
            KeywordCluster.id == cluster_id,
            KeywordCluster.project_id == project_id,
        )
    )
    result = await db.execute(stmt)
    cluster = result.scalar_one_or_none()

    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    return ClusterResponse.model_validate(cluster)


@router.patch(
    "/{project_id}/clusters/{cluster_id}/pages/{page_id}",
    response_model=ClusterPageResponse,
)
async def update_cluster_page(
    project_id: str,
    cluster_id: str,
    page_id: str,
    data: ClusterPageUpdate,
    db: AsyncSession = Depends(get_session),
) -> ClusterPageResponse:
    """Update editable fields on a cluster page.

    When setting role='parent', the current parent in the same cluster
    is automatically reassigned to 'child' (only one parent per cluster).

    Args:
        project_id: UUID of the project.
        cluster_id: UUID of the cluster.
        page_id: UUID of the cluster page.
        data: ClusterPageUpdate with optional fields to update.
        db: AsyncSession for database operations.

    Returns:
        Updated ClusterPageResponse.

    Raises:
        HTTPException: 404 if project, cluster, or page not found.
    """
    await ProjectService.get_project(db, project_id)

    # Verify cluster belongs to project
    cluster_stmt = select(KeywordCluster).where(
        KeywordCluster.id == cluster_id,
        KeywordCluster.project_id == project_id,
    )
    cluster_result = await db.execute(cluster_stmt)
    cluster = cluster_result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    # Load the target page
    page_stmt = select(ClusterPage).where(
        ClusterPage.id == page_id,
        ClusterPage.cluster_id == cluster_id,
    )
    page_result = await db.execute(page_stmt)
    page = page_result.scalar_one_or_none()
    if page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster page {page_id} not found",
        )

    # Handle parent reassignment
    if data.role == "parent" and page.role != "parent":
        current_parent_stmt = select(ClusterPage).where(
            ClusterPage.cluster_id == cluster_id,
            ClusterPage.role == "parent",
        )
        current_parent_result = await db.execute(current_parent_stmt)
        current_parent = current_parent_result.scalar_one_or_none()
        if current_parent is not None:
            current_parent.role = "child"

    # Apply updates
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(page, field, value)

    # Sync approval state to content pipeline
    if data.is_approved is not None:
        if page.crawled_page_id is not None:
            # Page already bridged — sync PageKeywords.is_approved
            pk_stmt = select(PageKeywords).where(
                PageKeywords.crawled_page_id == page.crawled_page_id
            )
            pk_result = await db.execute(pk_stmt)
            page_keywords = pk_result.scalar_one_or_none()
            if page_keywords is not None:
                page_keywords.is_approved = data.is_approved
                logger.info(
                    "Synced PageKeywords.is_approved=%s for crawled_page_id=%s",
                    data.is_approved,
                    page.crawled_page_id,
                )
            else:
                logger.warning(
                    "No PageKeywords found for crawled_page_id=%s during approval sync",
                    page.crawled_page_id,
                )
        elif data.is_approved and cluster.status in {
            ClusterStatus.APPROVED.value,
            ClusterStatus.CONTENT_GENERATING.value,
            ClusterStatus.COMPLETE.value,
        }:
            # Page approved after initial bulk approve — bridge it now
            existing_stmt = select(CrawledPage).where(
                CrawledPage.project_id == project_id,
                CrawledPage.normalized_url == page.url_slug,
            )
            existing_result = await db.execute(existing_stmt)
            crawled_page = existing_result.scalar_one_or_none()

            if crawled_page is None:
                crawled_page = CrawledPage(
                    project_id=project_id,
                    normalized_url=page.url_slug,
                    source="cluster",
                    status=CrawlStatus.COMPLETED.value,
                    category="collection",
                    title=page.keyword,
                )
                db.add(crawled_page)
                await db.flush()

            pk = PageKeywords(
                crawled_page_id=crawled_page.id,
                primary_keyword=page.keyword,
                is_approved=True,
                is_priority=page.role == "parent",
                search_volume=page.search_volume,
                composite_score=page.composite_score,
            )
            db.add(pk)

            page.crawled_page_id = crawled_page.id
            logger.info(
                "Bridged newly approved page %s → crawled_page_id=%s",
                page.id,
                crawled_page.id,
            )

    await db.commit()
    await db.refresh(page)

    return ClusterPageResponse.model_validate(page)


@router.post(
    "/{project_id}/clusters/{cluster_id}/regenerate",
    response_model=ClusterResponse,
    status_code=status.HTTP_200_OK,
)
async def regenerate_cluster(
    project_id: str,
    cluster_id: str,
    db: AsyncSession = Depends(get_session),
    claude: ClaudeClient = Depends(get_claude),
    dataforseo: DataForSEOClient = Depends(get_dataforseo),
) -> ClusterResponse:
    """Regenerate unapproved keywords in a cluster.

    Keeps approved pages, deletes unapproved ones, and re-runs the
    keyword generation pipeline to produce fresh suggestions.

    Args:
        project_id: UUID of the project.
        cluster_id: UUID of the cluster.
        db: AsyncSession for database operations.
        claude: Claude client for LLM calls.
        dataforseo: DataForSEO client for volume data.

    Returns:
        ClusterResponse with updated pages.

    Raises:
        HTTPException: 404 if project or cluster not found.
        HTTPException: 409 if cluster already approved.
        HTTPException: 504 if generation exceeds timeout.
    """
    await ProjectService.get_project(db, project_id)

    # Verify cluster belongs to project
    cluster_stmt = select(KeywordCluster).where(
        KeywordCluster.id == cluster_id,
        KeywordCluster.project_id == project_id,
    )
    cluster_result = await db.execute(cluster_stmt)
    cluster = cluster_result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    # Fetch brand config
    bc_stmt = select(BrandConfig).where(BrandConfig.project_id == project_id)
    bc_result = await db.execute(bc_stmt)
    brand_config_row = bc_result.scalar_one_or_none()
    brand_config: dict = brand_config_row.v2_schema if brand_config_row else {}

    service = ClusterKeywordService(claude, dataforseo)
    try:
        await asyncio.wait_for(
            service.regenerate_unapproved(
                cluster_id=cluster_id,
                brand_config=brand_config,
                db=db,
            ),
            timeout=CLUSTER_GENERATION_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Cluster regeneration timed out (>90s). Please try again.",
        )
    except ValueError as e:
        error_msg = str(e)
        if "Cannot regenerate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )

    # Reload cluster with pages for response
    stmt = (
        select(KeywordCluster)
        .options(selectinload(KeywordCluster.pages))
        .where(KeywordCluster.id == cluster_id)
    )
    reload_result = await db.execute(stmt)
    updated_cluster = reload_result.scalar_one()

    return ClusterResponse.model_validate(updated_cluster)


@router.post(
    "/{project_id}/clusters/{cluster_id}/approve",
    status_code=status.HTTP_200_OK,
)
async def approve_cluster(
    project_id: str,
    cluster_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Bulk-approve a cluster, bridging approved pages into the content pipeline.

    Calls ClusterKeywordService.bulk_approve_cluster() which creates
    CrawledPage and PageKeywords records for each approved ClusterPage.

    Args:
        project_id: UUID of the project.
        cluster_id: UUID of the cluster.
        db: AsyncSession for database operations.

    Returns:
        Dict with bridged_count.

    Raises:
        HTTPException: 404 if project or cluster not found.
        HTTPException: 400 if no approved pages.
        HTTPException: 409 if cluster already approved.
    """
    await ProjectService.get_project(db, project_id)

    # Verify cluster belongs to project
    cluster_stmt = select(KeywordCluster).where(
        KeywordCluster.id == cluster_id,
        KeywordCluster.project_id == project_id,
    )
    cluster_result = await db.execute(cluster_stmt)
    cluster = cluster_result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    try:
        result = await ClusterKeywordService.bulk_approve_cluster(cluster_id, db)
    except ValueError as e:
        error_msg = str(e)
        if "cannot re-approve" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg,
            )
        if "No approved pages" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )

    return {"bridged_count": result["bridged_count"]}


@router.delete(
    "/{project_id}/clusters/{cluster_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_cluster(
    project_id: str,
    cluster_id: str,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a cluster and its associated bridged content pipeline data.

    Args:
        project_id: UUID of the project.
        cluster_id: UUID of the cluster.
        db: AsyncSession for database operations.

    Raises:
        HTTPException: 404 if project or cluster not found.
    """
    await ProjectService.get_project(db, project_id)

    stmt = select(KeywordCluster).where(
        KeywordCluster.id == cluster_id,
        KeywordCluster.project_id == project_id,
    )
    result = await db.execute(stmt)
    cluster = result.scalar_one_or_none()

    if cluster is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cluster {cluster_id} not found",
        )

    await db.delete(cluster)
    await db.commit()
