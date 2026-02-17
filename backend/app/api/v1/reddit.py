"""Reddit API routers.

REST endpoints for Reddit account CRUD and per-project Reddit configuration.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import cast

from app.core.database import get_session
from app.models.project import Project
from app.models.reddit_account import RedditAccount
from app.models.reddit_config import RedditProjectConfig
from app.schemas.reddit import (
    RedditAccountCreate,
    RedditAccountResponse,
    RedditAccountUpdate,
    RedditProjectConfigCreate,
    RedditProjectConfigResponse,
)

reddit_router = APIRouter(prefix="/reddit", tags=["Reddit"])
reddit_project_router = APIRouter(prefix="/projects", tags=["Reddit"])


@reddit_router.get(
    "/accounts",
    response_model=list[RedditAccountResponse],
)
async def list_accounts(
    niche: str | None = Query(None, description="Filter by niche tag (JSONB contains)"),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by account status"
    ),
    warmup_stage: str | None = Query(None, description="Filter by warmup stage"),
    db: AsyncSession = Depends(get_session),
) -> list[RedditAccountResponse]:
    """List all Reddit accounts with optional filters."""
    stmt = select(RedditAccount).order_by(RedditAccount.created_at.desc())

    if niche is not None:
        stmt = stmt.where(
            RedditAccount.niche_tags.op("@>")(cast([niche], JSONB))
        )

    if status_filter is not None:
        stmt = stmt.where(RedditAccount.status == status_filter)

    if warmup_stage is not None:
        stmt = stmt.where(RedditAccount.warmup_stage == warmup_stage)

    result = await db.execute(stmt)
    accounts = result.scalars().all()

    return [RedditAccountResponse.model_validate(a) for a in accounts]


@reddit_router.post(
    "/accounts",
    response_model=RedditAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account(
    data: RedditAccountCreate,
    db: AsyncSession = Depends(get_session),
) -> RedditAccountResponse:
    """Create a new Reddit account. Returns 409 if username already exists."""
    existing_stmt = select(RedditAccount).where(
        RedditAccount.username == data.username
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Reddit account with username '{data.username}' already exists",
        )

    account = RedditAccount(
        username=data.username,
        niche_tags=data.niche_tags,
        warmup_stage=data.warmup_stage,
        notes=data.notes,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    return RedditAccountResponse.model_validate(account)


@reddit_router.patch(
    "/accounts/{account_id}",
    response_model=RedditAccountResponse,
)
async def update_account(
    account_id: str,
    data: RedditAccountUpdate,
    db: AsyncSession = Depends(get_session),
) -> RedditAccountResponse:
    """Update a Reddit account. Returns 404 if not found."""
    stmt = select(RedditAccount).where(RedditAccount.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reddit account {account_id} not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)

    return RedditAccountResponse.model_validate(account)


@reddit_router.delete(
    "/accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a Reddit account. Returns 404 if not found."""
    stmt = select(RedditAccount).where(RedditAccount.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reddit account {account_id} not found",
        )

    await db.delete(account)
    await db.commit()


# ---------------------------------------------------------------------------
# Project Reddit config endpoints (on reddit_project_router)
# ---------------------------------------------------------------------------


@reddit_project_router.get(
    "/{project_id}/reddit/config",
    response_model=RedditProjectConfigResponse,
)
async def get_project_reddit_config(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> RedditProjectConfigResponse:
    """Get Reddit config for a project. Returns 404 if none exists."""
    stmt = select(RedditProjectConfig).where(
        RedditProjectConfig.project_id == project_id
    )
    result = await db.execute(stmt)
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reddit config for project {project_id} not found",
        )

    return RedditProjectConfigResponse.model_validate(config)


@reddit_project_router.post(
    "/{project_id}/reddit/config",
    response_model=RedditProjectConfigResponse,
    responses={
        200: {"description": "Config updated"},
        201: {"description": "Config created"},
        404: {"description": "Project not found"},
    },
)
async def upsert_project_reddit_config(
    project_id: str,
    data: RedditProjectConfigCreate,
    response: Response,
    db: AsyncSession = Depends(get_session),
) -> RedditProjectConfigResponse:
    """Create or update Reddit config for a project.

    Returns 201 if created, 200 if updated. Returns 404 if project doesn't exist.
    """
    # Verify project exists
    project_stmt = select(Project.id).where(Project.id == project_id)
    project_result = await db.execute(project_stmt)
    if project_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    # Check for existing config
    stmt = select(RedditProjectConfig).where(
        RedditProjectConfig.project_id == project_id
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing is not None:
        # Update existing config
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)
        await db.commit()
        await db.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return RedditProjectConfigResponse.model_validate(existing)

    # Create new config
    config = RedditProjectConfig(
        project_id=project_id,
        **data.model_dump(),
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    response.status_code = status.HTTP_201_CREATED
    return RedditProjectConfigResponse.model_validate(config)
