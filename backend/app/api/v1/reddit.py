"""Reddit account management API router.

REST endpoints for creating, listing, updating, and deleting Reddit accounts.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import cast

from app.core.database import get_session
from app.models.reddit_account import RedditAccount
from app.schemas.reddit import (
    RedditAccountCreate,
    RedditAccountResponse,
    RedditAccountUpdate,
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
