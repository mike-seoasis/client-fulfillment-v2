"""Clusters API router.

REST endpoints for creating and listing keyword clusters.
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
from app.models.keyword_cluster import ClusterPage, KeywordCluster
from app.schemas.cluster import ClusterCreate, ClusterListResponse, ClusterResponse
from app.services.cluster_keyword import ClusterKeywordService
from app.services.project import ProjectService

logger = get_logger(__name__)

router = APIRouter(prefix="/projects", tags=["Clusters"])

CLUSTER_GENERATION_TIMEOUT_SECONDS = 30


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

    Runs the 3-stage generation pipeline synchronously (~5-10s):
    1. LLM candidate generation
    2. DataForSEO volume enrichment
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
        HTTPException: 504 if generation exceeds 30s timeout.
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
            detail="Cluster generation timed out (>30s). Please try again.",
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
