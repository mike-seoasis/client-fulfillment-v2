"""Shopify integration API routes.

Handles OAuth install/callback, GDPR webhooks, app uninstall webhook,
and CRUD endpoints for Shopify pages, sync, and connection status.
"""

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session
from app.core.logging import get_logger
from app.core.shopify_crypto import encrypt_token
from app.models.project import Project
from app.models.shopify_page import ShopifyPage
from app.services.shopify_sync import sync_immediate

logger = get_logger(__name__)

# Authenticated endpoints (included via the v1 auth router)
router = APIRouter(tags=["Shopify"])

# Unauthenticated endpoints (OAuth redirects + webhooks, registered directly on app)
shopify_public_router = APIRouter(prefix="/api/v1", tags=["Shopify"])

# In-memory OAuth state store (short-lived, cleared after use)
# In production with multiple workers, use Redis. For single-worker Railway, this is fine.
_oauth_states: dict[str, str] = {}  # state -> project_id

SHOPIFY_SCOPES = "read_products,read_content"


# -------------------------------------------------------------------------
# Pydantic schemas for responses
# -------------------------------------------------------------------------


class ShopifyStatusResponse(BaseModel):
    connected: bool
    store_domain: str | None = None
    last_sync_at: datetime | None = None
    sync_status: str | None = None
    connected_at: datetime | None = None


class ShopifyPageResponse(BaseModel):
    id: str
    shopify_id: str
    page_type: str
    title: str | None = None
    handle: str | None = None
    full_url: str | None = None
    status: str | None = None
    published_at: datetime | None = None
    product_type: str | None = None
    product_count: int | None = None
    blog_name: str | None = None
    tags: list[str] | None = None
    shopify_updated_at: datetime | None = None
    last_synced_at: datetime | None = None

    class Config:
        from_attributes = True


class ShopifyPagesListResponse(BaseModel):
    items: list[ShopifyPageResponse]
    total: int
    page: int
    per_page: int


class ShopifyPageCounts(BaseModel):
    collection: int = 0
    product: int = 0
    article: int = 0
    page: int = 0


class SyncTriggerResponse(BaseModel):
    status: str = Field(description="syncing")


# -------------------------------------------------------------------------
# Helper utilities
# -------------------------------------------------------------------------


def _validate_shop_domain(shop: str) -> bool:
    """Validate that shop is a valid *.myshopify.com domain."""
    return bool(re.match(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$", shop))


def verify_shopify_hmac(query_params: dict[str, str], secret: str) -> bool:
    """Verify Shopify OAuth callback HMAC signature.

    Shopify sends an HMAC of all query params (excluding 'hmac' itself),
    sorted alphabetically, joined with &.
    """
    received_hmac = query_params.get("hmac", "")
    if not received_hmac:
        return False

    # Build message from sorted params excluding hmac
    params = {k: v for k, v in query_params.items() if k != "hmac"}
    message = "&".join(f"{k}={v}" for k, v in sorted(params.items()))

    computed = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(computed, received_hmac)


def verify_webhook_hmac(body: bytes, hmac_header: str, secret: str) -> bool:
    """Verify Shopify webhook HMAC (X-Shopify-Hmac-SHA256)."""
    import base64

    computed = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    computed_b64 = base64.b64encode(computed).decode()
    return hmac.compare_digest(computed_b64, hmac_header)


async def _get_project_or_404(project_id: str, db: AsyncSession) -> Project:
    """Load a project or raise 404."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# -------------------------------------------------------------------------
# OAuth endpoints
# -------------------------------------------------------------------------


@shopify_public_router.get("/shopify/auth/install")
async def shopify_auth_install(
    shop: str = Query(...),
    project_id: str = Query(...),
    db: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Initiate Shopify OAuth by redirecting to Shopify's authorization page."""
    settings = get_settings()

    if not settings.shopify_api_key or not settings.shopify_api_secret:
        raise HTTPException(status_code=500, detail="Shopify app not configured")

    if not _validate_shop_domain(shop):
        raise HTTPException(status_code=400, detail="Invalid Shopify store domain")

    # Verify project exists
    await _get_project_or_404(project_id, db)

    # Generate cryptographic state parameter
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = project_id

    # Build redirect URI — prefer explicit env var, fall back to constructed URL
    if settings.shopify_redirect_uri:
        redirect_uri = settings.shopify_redirect_uri
    elif settings.backend_url:
        redirect_uri = (
            f"{settings.backend_url.rstrip('/')}/api/v1/shopify/auth/callback"
        )
    else:
        redirect_uri = "http://localhost:8000/api/v1/shopify/auth/callback"

    auth_url = (
        f"https://{shop}/admin/oauth/authorize"
        f"?client_id={settings.shopify_api_key}"
        f"&scope={SHOPIFY_SCOPES}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )

    return RedirectResponse(url=auth_url, status_code=302)


@shopify_public_router.get("/shopify/auth/callback")
async def shopify_auth_callback(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle Shopify OAuth callback — exchange code for token, store encrypted."""
    settings = get_settings()
    params = dict(request.query_params)

    # Verify HMAC
    if not verify_shopify_hmac(params, settings.shopify_api_secret or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Verify state
    state = params.get("state", "")
    project_id = _oauth_states.pop(state, None)
    if not project_id:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    shop = params.get("shop", "")
    code = params.get("code", "")

    if not shop or not code:
        raise HTTPException(status_code=400, detail="Missing shop or code parameter")

    # Exchange code for access token
    import httpx

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            f"https://{shop}/admin/oauth/access_token",
            json={
                "client_id": settings.shopify_api_key,
                "client_secret": settings.shopify_api_secret,
                "code": code,
            },
        )

    if token_resp.status_code != 200:
        logger.error(
            "Shopify token exchange failed",
            extra={"status": token_resp.status_code, "body": token_resp.text},
        )
        raise HTTPException(
            status_code=502, detail="Failed to exchange Shopify authorization code"
        )

    token_data = token_resp.json()
    access_token = token_data.get("access_token", "")
    scopes = token_data.get("scope", "")

    if not access_token:
        raise HTTPException(
            status_code=502, detail="No access token in Shopify response"
        )

    # Encrypt and store
    encrypted_token = encrypt_token(access_token)

    project = await _get_project_or_404(project_id, db)
    project.shopify_store_domain = shop
    project.shopify_access_token_encrypted = encrypted_token
    project.shopify_scopes = scopes
    project.shopify_connected_at = datetime.now(UTC)
    project.shopify_sync_status = "idle"
    await db.commit()  # Explicit commit before redirect to prevent data loss

    # Register nightly sync job
    _register_sync_job(project_id)

    # Redirect to project's Pages tab
    frontend_url = settings.frontend_url or "http://localhost:3000"
    redirect_url = f"{frontend_url}/projects/{project_id}?tab=pages"
    return RedirectResponse(url=redirect_url, status_code=302)


# -------------------------------------------------------------------------
# GDPR webhook endpoints (required by Shopify, return 200)
# -------------------------------------------------------------------------


async def _verify_gdpr_webhook(request: Request) -> None:
    """Verify HMAC on GDPR webhook requests."""
    settings = get_settings()
    body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_webhook_hmac(body, hmac_header, settings.shopify_api_secret or ""):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@shopify_public_router.post("/shopify/webhooks/customers/data_request", status_code=200)
async def gdpr_customers_data_request(request: Request) -> dict[str, Any]:
    """Handle Shopify GDPR customer data request. No customer data stored."""
    await _verify_gdpr_webhook(request)
    return {"status": "ok"}


@shopify_public_router.post("/shopify/webhooks/customers/redact", status_code=200)
async def gdpr_customers_redact(request: Request) -> dict[str, Any]:
    """Handle Shopify GDPR customer data redaction. No customer data stored."""
    await _verify_gdpr_webhook(request)
    return {"status": "ok"}


@shopify_public_router.post("/shopify/webhooks/shop/redact", status_code=200)
async def gdpr_shop_redact(request: Request) -> dict[str, Any]:
    """Handle Shopify GDPR shop data redaction."""
    await _verify_gdpr_webhook(request)
    return {"status": "ok"}


# -------------------------------------------------------------------------
# App uninstall webhook
# -------------------------------------------------------------------------


@shopify_public_router.post("/shopify/webhooks/app/uninstalled", status_code=200)
async def shopify_app_uninstalled(request: Request) -> dict[str, Any]:
    """Handle app/uninstalled webhook — clear Shopify connection."""
    settings = get_settings()

    # Verify webhook HMAC
    body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if not verify_webhook_hmac(body, hmac_header, settings.shopify_api_secret or ""):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")

    if not shop_domain:
        logger.warning("Uninstall webhook missing shop domain header")
        return {"status": "ok"}

    # Find and disconnect the project
    from app.core.database import db_manager

    async with db_manager.session_factory() as session:
        result = await session.execute(
            select(Project).where(Project.shopify_store_domain == shop_domain)
        )
        project = result.scalar_one_or_none()

        if project:
            project.shopify_store_domain = None
            project.shopify_access_token_encrypted = None
            project.shopify_scopes = None
            project.shopify_sync_status = "disconnected"
            project.shopify_connected_at = None
            project.shopify_last_sync_at = None
            await session.commit()

            _remove_sync_job(project.id)
            logger.info(
                "Shopify app uninstalled",
                extra={"project_id": project.id, "shop": shop_domain},
            )
        else:
            logger.warning(
                "Uninstall webhook for unknown shop", extra={"shop": shop_domain}
            )

    return {"status": "ok"}


# -------------------------------------------------------------------------
# API endpoints: status, pages, sync, disconnect
# -------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/shopify/status", response_model=ShopifyStatusResponse
)
async def get_shopify_status(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> ShopifyStatusResponse:
    """Get Shopify connection status for a project."""
    project = await _get_project_or_404(project_id, db)

    if not project.shopify_store_domain:
        return ShopifyStatusResponse(connected=False)

    return ShopifyStatusResponse(
        connected=True,
        store_domain=project.shopify_store_domain,
        last_sync_at=project.shopify_last_sync_at,
        sync_status=project.shopify_sync_status,
        connected_at=project.shopify_connected_at,
    )


@router.get(
    "/projects/{project_id}/shopify/pages", response_model=ShopifyPagesListResponse
)
async def list_shopify_pages(
    project_id: str,
    type: str | None = Query(None, description="Filter by page_type"),
    search: str | None = Query(None, description="Search by title (case-insensitive)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> ShopifyPagesListResponse:
    """List Shopify pages for a project, paginated and filtered."""
    await _get_project_or_404(project_id, db)

    # Build query
    query = select(ShopifyPage).where(
        ShopifyPage.project_id == project_id,
        ShopifyPage.is_deleted == False,  # noqa: E712
    )
    count_query = (
        select(func.count())
        .select_from(ShopifyPage)
        .where(
            ShopifyPage.project_id == project_id,
            ShopifyPage.is_deleted == False,  # noqa: E712
        )
    )

    if type:
        query = query.where(ShopifyPage.page_type == type)
        count_query = count_query.where(ShopifyPage.page_type == type)

    if search:
        query = query.where(ShopifyPage.title.ilike(f"%{search}%"))
        count_query = count_query.where(ShopifyPage.title.ilike(f"%{search}%"))

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results
    offset = (page - 1) * per_page
    query = query.order_by(ShopifyPage.title).offset(offset).limit(per_page)
    result = await db.execute(query)
    pages = result.scalars().all()

    return ShopifyPagesListResponse(
        items=[ShopifyPageResponse.model_validate(p) for p in pages],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/projects/{project_id}/shopify/pages/counts", response_model=ShopifyPageCounts
)
async def get_shopify_page_counts(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> ShopifyPageCounts:
    """Get count of Shopify pages per type (excluding soft-deleted)."""
    await _get_project_or_404(project_id, db)

    result = await db.execute(
        select(ShopifyPage.page_type, func.count())
        .where(
            ShopifyPage.project_id == project_id,
            ShopifyPage.is_deleted == False,  # noqa: E712
        )
        .group_by(ShopifyPage.page_type)
    )
    counts = {row[0]: row[1] for row in result.all()}

    return ShopifyPageCounts(
        collection=counts.get("collection", 0),
        product=counts.get("product", 0),
        article=counts.get("article", 0),
        page=counts.get("page", 0),
    )


@router.post(
    "/projects/{project_id}/shopify/sync",
    response_model=SyncTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_shopify_sync(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
) -> SyncTriggerResponse:
    """Trigger an immediate Shopify sync as a background task."""
    project = await _get_project_or_404(project_id, db)

    if not project.shopify_store_domain or not project.shopify_access_token_encrypted:
        raise HTTPException(status_code=400, detail="Shopify not connected")

    if project.shopify_sync_status == "syncing":
        raise HTTPException(status_code=409, detail="Sync already in progress")

    # Mark as syncing
    project.shopify_sync_status = "syncing"
    await db.flush()

    background_tasks.add_task(sync_immediate, project_id)

    return SyncTriggerResponse(status="syncing")


@router.delete("/projects/{project_id}/shopify", status_code=200)
async def disconnect_shopify(
    project_id: str,
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Disconnect Shopify from a project."""
    project = await _get_project_or_404(project_id, db)

    # Clear all Shopify fields (idempotent)
    project.shopify_store_domain = None
    project.shopify_access_token_encrypted = None
    project.shopify_scopes = None
    project.shopify_last_sync_at = None
    project.shopify_sync_status = None
    project.shopify_connected_at = None
    await db.flush()

    _remove_sync_job(project_id)

    return {"status": "disconnected"}


# -------------------------------------------------------------------------
# Scheduler helpers
# -------------------------------------------------------------------------


def _register_sync_job(project_id: str) -> None:
    """Register a nightly sync cron job for a project."""
    from app.core.scheduler import get_scheduler

    scheduler = get_scheduler()
    if not scheduler.is_running:
        logger.warning("Scheduler not running, skipping sync job registration")
        return

    # Stagger start time by hashing project_id to a minute offset (0-59)
    minute_offset = int(hashlib.md5(project_id.encode()).hexdigest(), 16) % 60

    job_id = f"shopify_sync_{project_id}"

    # APScheduler runs jobs in a thread pool. We must create a fresh event loop
    # since asyncio.run() fails if a loop is already running in the thread.
    def _sync_wrapper() -> None:
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(sync_nightly_wrapper(project_id))
        finally:
            loop.close()

    scheduler.add_job(
        _sync_wrapper,
        trigger="cron",
        id=job_id,
        name=f"Shopify nightly sync ({project_id[:8]})",
        replace_existing=True,
        hour=3,
        minute=minute_offset,
    )
    logger.info(
        "Registered nightly sync job",
        extra={"project_id": project_id, "minute": minute_offset},
    )


def _remove_sync_job(project_id: str) -> None:
    """Remove the nightly sync job for a project (idempotent)."""
    from apscheduler.jobstores.base import JobLookupError

    from app.core.scheduler import get_scheduler

    scheduler = get_scheduler()
    job_id = f"shopify_sync_{project_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info("Removed nightly sync job", extra={"project_id": project_id})
    except JobLookupError:
        logger.debug("No sync job to remove", extra={"project_id": project_id})


async def sync_nightly_wrapper(project_id: str) -> None:
    """Wrapper for calling async sync_nightly from APScheduler thread."""
    from app.services.shopify_sync import sync_nightly

    await sync_nightly(project_id)


async def restore_sync_jobs_on_startup() -> None:
    """Restore nightly sync jobs for all connected projects on backend startup."""
    from app.core.database import db_manager

    async with db_manager.session_factory() as session:
        result = await session.execute(
            select(Project.id).where(Project.shopify_store_domain.isnot(None))
        )
        project_ids = [row[0] for row in result.all()]

    for pid in project_ids:
        _register_sync_job(pid)

    if project_ids:
        logger.info(
            "Restored Shopify sync jobs on startup",
            extra={"count": len(project_ids)},
        )
