"""Shopify sync service for immediate and nightly syncs.

Handles upserting Shopify page data into the shopify_pages table,
URL construction per page type, and sync metadata on projects.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import db_manager
from app.core.logging import get_logger
from app.core.shopify_crypto import decrypt_token
from app.integrations.shopify import (
    ShopifyAuthError,
    ShopifyGraphQLClient,
)
from app.integrations.shopify import (
    ShopifyPage as ShopifyPageData,
)
from app.models.project import Project
from app.models.shopify_page import ShopifyPage

logger = get_logger(__name__)


def _build_full_url(store_domain: str, page: ShopifyPageData) -> str | None:
    """Construct the full public URL for a Shopify page.

    URL patterns:
        collection: {store}/collections/{handle}
        product:    {store}/products/{handle}
        article:    {store}/blogs/{blog_handle}/{handle}
        page:       {store}/pages/{handle}
    """
    if not page.handle:
        return None

    base = f"https://{store_domain}"

    if page.page_type == "collection":
        return f"{base}/collections/{page.handle}"
    elif page.page_type == "product":
        return f"{base}/products/{page.handle}"
    elif page.page_type == "article":
        blog_handle = page.blog_handle or "news"
        return f"{base}/blogs/{blog_handle}/{page.handle}"
    elif page.page_type == "page":
        return f"{base}/pages/{page.handle}"
    return None


async def _upsert_pages(
    session: AsyncSession,
    project_id: str,
    store_domain: str,
    pages: list[ShopifyPageData],
) -> int:
    """Upsert Shopify pages into the database.

    Uses PostgreSQL ON CONFLICT ... DO UPDATE for idempotent upserts.

    Returns:
        Number of rows upserted.
    """
    if not pages:
        return 0

    now = datetime.now(UTC)

    for page in pages:
        full_url = _build_full_url(store_domain, page)
        stmt = pg_insert(ShopifyPage).values(
            project_id=project_id,
            shopify_id=page.shopify_id,
            page_type=page.page_type,
            title=page.title,
            handle=page.handle,
            full_url=full_url,
            status=page.status,
            published_at=page.published_at,
            product_type=page.product_type,
            product_count=page.product_count,
            blog_name=page.blog_name,
            tags=page.tags,
            shopify_updated_at=page.shopify_updated_at,
            last_synced_at=now,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_shopify_pages_project_shopify",
            set_={
                "title": stmt.excluded.title,
                "handle": stmt.excluded.handle,
                "full_url": stmt.excluded.full_url,
                "status": stmt.excluded.status,
                "published_at": stmt.excluded.published_at,
                "product_type": stmt.excluded.product_type,
                "product_count": stmt.excluded.product_count,
                "blog_name": stmt.excluded.blog_name,
                "tags": stmt.excluded.tags,
                "shopify_updated_at": stmt.excluded.shopify_updated_at,
                "last_synced_at": stmt.excluded.last_synced_at,
                "is_deleted": False,
                "updated_at": now,
            },
        )
        await session.execute(stmt)

    return len(pages)


async def _update_project_sync_status(
    session: AsyncSession,
    project_id: str,
    sync_status: str,
    last_sync_at: datetime | None = None,
) -> None:
    """Update sync metadata on the project."""
    values: dict[str, Any] = {"shopify_sync_status": sync_status}
    if last_sync_at is not None:
        values["shopify_last_sync_at"] = last_sync_at
    stmt = update(Project).where(Project.id == project_id).values(**values)
    await session.execute(stmt)
    await session.commit()


async def sync_immediate(project_id: str) -> None:
    """Run an immediate sync using paginated GraphQL queries.

    Called during onboarding or manual "Sync Now" action.
    Fetches all 4 resource types and upserts to the database.
    """
    async with db_manager.session_factory() as session:
        # Load project
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if (
            not project
            or not project.shopify_store_domain
            or not project.shopify_access_token_encrypted
        ):
            logger.error(
                "Cannot sync: project not found or Shopify not connected",
                extra={"project_id": project_id},
            )
            return

        store_domain = project.shopify_store_domain
        access_token = decrypt_token(project.shopify_access_token_encrypted)

        # Set syncing status
        await _update_project_sync_status(session, project_id, "syncing")

    client = ShopifyGraphQLClient(store_domain, access_token)
    try:
        # Fetch all resource types
        collections = await client.fetch_collections()
        products = await client.fetch_products()
        articles = await client.fetch_articles()
        pages = await client.fetch_pages()

        all_pages = collections + products + articles + pages

        # Upsert to database
        async with db_manager.session_factory() as session:
            count = await _upsert_pages(session, project_id, store_domain, all_pages)
            await session.commit()

            now = datetime.now(UTC)
            await _update_project_sync_status(session, project_id, "idle", now)

        logger.info(
            "Immediate sync completed",
            extra={"project_id": project_id, "total_pages": count},
        )

    except ShopifyAuthError:
        logger.error(
            "Shopify auth error during sync — token may be revoked",
            extra={"project_id": project_id},
        )
        async with db_manager.session_factory() as session:
            await _update_project_sync_status(session, project_id, "error")

    except Exception as e:
        logger.error(
            "Sync failed",
            extra={"project_id": project_id, "error": str(e)},
            exc_info=True,
        )
        async with db_manager.session_factory() as session:
            await _update_project_sync_status(session, project_id, "error")

    finally:
        await client.close()


async def sync_nightly(project_id: str) -> None:
    """Run a nightly sync using the Bulk Operations API.

    Submits bulk queries sequentially (one per resource type),
    polls for completion, downloads JSONL, and upserts to DB.
    Soft-deletes pages not seen in the current sync.
    """
    async with db_manager.session_factory() as session:
        result = await session.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if (
            not project
            or not project.shopify_store_domain
            or not project.shopify_access_token_encrypted
        ):
            logger.error(
                "Cannot nightly sync: project not connected",
                extra={"project_id": project_id},
            )
            return

        store_domain = project.shopify_store_domain
        access_token = decrypt_token(project.shopify_access_token_encrypted)
        await _update_project_sync_status(session, project_id, "syncing")

    client = ShopifyGraphQLClient(store_domain, access_token)
    seen_shopify_ids: set[str] = set()

    bulk_queries = {
        "collection": "{ collections { edges { node { id title handle updatedAt productsCount { count } } } } }",
        "product": "{ products { edges { node { id title handle status productType tags publishedAt updatedAt } } } }",
        "article": "{ articles { edges { node { id title handle publishedAt tags updatedAt blog { title handle } } } } }",
        "page": "{ pages { edges { node { id title handle publishedAt isPublished updatedAt } } } }",
    }

    try:
        for page_type, query in bulk_queries.items():
            logger.info(
                f"Starting bulk operation for {page_type}",
                extra={"project_id": project_id},
            )

            op_id = await client.start_bulk_query(query)
            if not op_id:
                logger.warning(f"No bulk operation ID returned for {page_type}")
                continue

            op_result = await client.poll_bulk_operation()
            status = op_result.get("status", "")

            if status != "COMPLETED":
                logger.warning(
                    f"Bulk operation for {page_type} ended with status {status}",
                    extra={
                        "project_id": project_id,
                        "error_code": op_result.get("errorCode"),
                    },
                )
                continue

            url = op_result.get("url")
            if not url:
                logger.info(f"No results for {page_type} (empty store segment)")
                continue

            jsonl_records = await client.download_jsonl(url)
            pages = _parse_bulk_results(page_type, jsonl_records)

            async with db_manager.session_factory() as session:
                await _upsert_pages(session, project_id, store_domain, pages)
                await session.commit()

            for p in pages:
                seen_shopify_ids.add(p.shopify_id)

        # Soft-delete pages not seen in this sync
        async with db_manager.session_factory() as session:
            if seen_shopify_ids:
                stmt = (
                    update(ShopifyPage)
                    .where(
                        ShopifyPage.project_id == project_id,
                        ShopifyPage.is_deleted == False,  # noqa: E712
                        ~ShopifyPage.shopify_id.in_(seen_shopify_ids),
                    )
                    .values(is_deleted=True, updated_at=datetime.now(UTC))
                )
                await session.execute(stmt)
                await session.commit()

            now = datetime.now(UTC)
            await _update_project_sync_status(session, project_id, "idle", now)

        logger.info(
            "Nightly sync completed",
            extra={"project_id": project_id, "synced_ids": len(seen_shopify_ids)},
        )

    except ShopifyAuthError:
        logger.error(
            "Shopify auth error during nightly sync", extra={"project_id": project_id}
        )
        async with db_manager.session_factory() as session:
            await _update_project_sync_status(session, project_id, "error")

    except Exception as e:
        logger.error(
            "Nightly sync failed",
            extra={"project_id": project_id, "error": str(e)},
            exc_info=True,
        )
        async with db_manager.session_factory() as session:
            await _update_project_sync_status(session, project_id, "error")

    finally:
        await client.close()


def _parse_bulk_results(
    page_type: str, records: list[dict[str, Any]]
) -> list[ShopifyPageData]:
    """Parse JSONL records from a bulk operation into ShopifyPageData objects.

    Handles parent-child relationships via __parentId for articles (blog parent).
    """
    # Build parent lookup for articles (blog → articles)
    parents: dict[str, dict[str, Any]] = {}
    children: list[dict[str, Any]] = []

    for record in records:
        parent_id = record.get("__parentId")
        if parent_id:
            children.append(record)
        else:
            parents[record.get("id", "")] = record

    pages: list[ShopifyPageData] = []

    if page_type == "article":
        # Articles have blog as parent in bulk results
        for child in children:
            parent = parents.get(child.get("__parentId", ""), {})
            pages.append(
                ShopifyPageData(
                    shopify_id=child["id"],
                    page_type="article",
                    title=child.get("title"),
                    handle=child.get("handle"),
                    status="active" if child.get("publishedAt") else "draft",
                    published_at=child.get("publishedAt"),
                    shopify_updated_at=child.get("updatedAt"),
                    blog_name=parent.get("title"),
                    blog_handle=parent.get("handle"),
                    tags=child.get("tags"),
                )
            )
        # Also handle articles without parent (flat structure)
        for record in records:
            if (
                not record.get("__parentId")
                and page_type == "article"
                and record.get("id", "").startswith("gid://shopify/Article")
            ):
                pages.append(
                    ShopifyPageData(
                        shopify_id=record["id"],
                        page_type="article",
                        title=record.get("title"),
                        handle=record.get("handle"),
                        status="active" if record.get("publishedAt") else "draft",
                        published_at=record.get("publishedAt"),
                        shopify_updated_at=record.get("updatedAt"),
                        tags=record.get("tags"),
                    )
                )
    else:
        # For non-article types, all records are top-level
        for record in records:
            if record.get("__parentId"):
                continue
            if page_type == "collection":
                products_count = record.get("productsCount", {})
                pages.append(
                    ShopifyPageData(
                        shopify_id=record["id"],
                        page_type="collection",
                        title=record.get("title"),
                        handle=record.get("handle"),
                        status="active",
                        published_at=None,
                        shopify_updated_at=record.get("updatedAt"),
                        product_count=products_count.get("count")
                        if isinstance(products_count, dict)
                        else products_count,
                    )
                )
            elif page_type == "product":
                status_val = record.get("status", "").lower()
                pages.append(
                    ShopifyPageData(
                        shopify_id=record["id"],
                        page_type="product",
                        title=record.get("title"),
                        handle=record.get("handle"),
                        status=status_val if status_val else None,
                        published_at=record.get("publishedAt"),
                        shopify_updated_at=record.get("updatedAt"),
                        product_type=record.get("productType") or None,
                        tags=record.get("tags"),
                    )
                )
            elif page_type == "page":
                pages.append(
                    ShopifyPageData(
                        shopify_id=record["id"],
                        page_type="page",
                        title=record.get("title"),
                        handle=record.get("handle"),
                        status="active" if record.get("isPublished") else "draft",
                        published_at=record.get("publishedAt"),
                        shopify_updated_at=record.get("updatedAt"),
                    )
                )

    return pages
