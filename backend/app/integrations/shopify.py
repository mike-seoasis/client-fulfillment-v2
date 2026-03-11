"""Shopify Admin GraphQL API client.

Uses httpx.AsyncClient for authenticated GraphQL queries with adaptive
rate limiting based on extensions.cost.throttleStatus. Supports cursor
pagination for immediate sync and bulk operations for nightly sync.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, cast

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

SHOPIFY_API_VERSION = "2024-10"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}


class ShopifyAuthError(Exception):
    """Raised when the Shopify API returns 401 (token revoked/invalid)."""


class ShopifyAPIError(Exception):
    """Raised for non-retryable Shopify API errors."""


@dataclass
class ShopifyPage:
    """Raw page data fetched from Shopify before DB upsert."""

    shopify_id: str
    page_type: str
    title: str | None
    handle: str | None
    status: str | None
    published_at: str | None
    shopify_updated_at: str | None
    product_type: str | None = None
    product_count: int | None = None
    blog_name: str | None = None
    blog_handle: str | None = None
    tags: list[str] | None = None


class ShopifyGraphQLClient:
    """Async Shopify Admin GraphQL API client.

    Args:
        store_domain: The myshopify.com domain (e.g. acmestore.myshopify.com).
        access_token: Decrypted offline access token.
    """

    def __init__(self, store_domain: str, access_token: str) -> None:
        self._store_domain = store_domain.rstrip("/")
        self._endpoint = (
            f"https://{self._store_domain}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
        )
        self._client = httpx.AsyncClient(
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    async def _execute(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query with retry and adaptive rate limiting.

        Returns:
            The parsed JSON response body.

        Raises:
            ShopifyAuthError: On 401 responses.
            ShopifyAPIError: On non-retryable errors or exhausted retries.
        """
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._client.post(self._endpoint, json=payload)
            except httpx.HTTPError as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "Shopify request failed, retrying",
                        extra={"attempt": attempt + 1, "delay": delay, "error": str(e)},
                    )
                    await asyncio.sleep(delay)
                    continue
                raise ShopifyAPIError(
                    f"Request failed after {MAX_RETRIES} retries: {e}"
                ) from e

            if resp.status_code == 401:
                raise ShopifyAuthError("Shopify access token is invalid or revoked")

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "Shopify API returned retryable status",
                    extra={
                        "status": resp.status_code,
                        "attempt": attempt + 1,
                        "delay": delay,
                    },
                )
                await asyncio.sleep(delay)
                continue

            if resp.status_code >= 400:
                raise ShopifyAPIError(
                    f"Shopify API error: {resp.status_code} — {resp.text}"
                )

            data: dict[str, Any] = resp.json()

            # Adaptive rate limiting
            extensions = data.get("extensions", {})
            cost = extensions.get("cost", {})
            throttle = cost.get("throttleStatus", {})
            currently_available = throttle.get("currentlyAvailable", 1000)
            restore_rate = throttle.get("restoreRate", 50)

            if currently_available < 100 and restore_rate > 0:
                wait = (100 - currently_available) / restore_rate
                logger.debug(
                    "Shopify rate limit throttle",
                    extra={"available": currently_available, "wait": wait},
                )
                await asyncio.sleep(wait)

            # Check for GraphQL-level errors
            if "errors" in data and data["errors"]:
                error_messages = [e.get("message", "") for e in data["errors"]]
                raise ShopifyAPIError(f"GraphQL errors: {error_messages}")

            return data

        raise ShopifyAPIError(
            f"Request failed after {MAX_RETRIES} retries"
        ) from last_error

    # -------------------------------------------------------------------------
    # Paginated fetch methods (for immediate sync)
    # -------------------------------------------------------------------------

    async def fetch_collections(self) -> list[ShopifyPage]:
        """Fetch all collections via cursor pagination."""
        query = """
        query($cursor: String) {
            collections(first: 250, after: $cursor) {
                edges {
                    node {
                        id
                        title
                        handle
                        updatedAt
                        productsCount { count }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
        """
        results: list[ShopifyPage] = []
        cursor: str | None = None

        while True:
            data = await self._execute(query, {"cursor": cursor})
            collections = data.get("data", {}).get("collections", {})
            edges = collections.get("edges", [])

            for edge in edges:
                node = edge["node"]
                products_count_obj = node.get("productsCount", {})
                results.append(
                    ShopifyPage(
                        shopify_id=node["id"],
                        page_type="collection",
                        title=node.get("title"),
                        handle=node.get("handle"),
                        status="active",
                        published_at=None,
                        shopify_updated_at=node.get("updatedAt"),
                        product_count=products_count_obj.get("count")
                        if products_count_obj
                        else None,
                    )
                )

            page_info = collections.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        logger.info("Fetched Shopify collections", extra={"count": len(results)})
        return results

    async def fetch_products(self) -> list[ShopifyPage]:
        """Fetch all products via cursor pagination."""
        query = """
        query($cursor: String) {
            products(first: 250, after: $cursor) {
                edges {
                    node {
                        id
                        title
                        handle
                        status
                        productType
                        tags
                        publishedAt
                        updatedAt
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
        """
        results: list[ShopifyPage] = []
        cursor: str | None = None

        while True:
            data = await self._execute(query, {"cursor": cursor})
            products = data.get("data", {}).get("products", {})
            edges = products.get("edges", [])

            for edge in edges:
                node = edge["node"]
                status_val = node.get("status", "").lower()
                # Shopify product status: ACTIVE, ARCHIVED, DRAFT
                results.append(
                    ShopifyPage(
                        shopify_id=node["id"],
                        page_type="product",
                        title=node.get("title"),
                        handle=node.get("handle"),
                        status=status_val if status_val else None,
                        published_at=node.get("publishedAt"),
                        shopify_updated_at=node.get("updatedAt"),
                        product_type=node.get("productType") or None,
                        tags=node.get("tags") or None,
                    )
                )

            page_info = products.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        logger.info("Fetched Shopify products", extra={"count": len(results)})
        return results

    async def fetch_articles(self) -> list[ShopifyPage]:
        """Fetch all blog articles via cursor pagination."""
        query = """
        query($cursor: String) {
            articles(first: 250, after: $cursor) {
                edges {
                    node {
                        id
                        title
                        handle
                        publishedAt
                        tags
                        updatedAt
                        blog {
                            title
                            handle
                        }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
        """
        results: list[ShopifyPage] = []
        cursor: str | None = None

        while True:
            data = await self._execute(query, {"cursor": cursor})
            articles = data.get("data", {}).get("articles", {})
            edges = articles.get("edges", [])

            for edge in edges:
                node = edge["node"]
                blog = node.get("blog", {}) or {}
                results.append(
                    ShopifyPage(
                        shopify_id=node["id"],
                        page_type="article",
                        title=node.get("title"),
                        handle=node.get("handle"),
                        status="active" if node.get("publishedAt") else "draft",
                        published_at=node.get("publishedAt"),
                        shopify_updated_at=node.get("updatedAt"),
                        blog_name=blog.get("title"),
                        blog_handle=blog.get("handle"),
                        tags=node.get("tags") or None,
                    )
                )

            page_info = articles.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        logger.info("Fetched Shopify articles", extra={"count": len(results)})
        return results

    async def fetch_pages(self) -> list[ShopifyPage]:
        """Fetch all static pages via cursor pagination."""
        query = """
        query($cursor: String) {
            pages(first: 250, after: $cursor) {
                edges {
                    node {
                        id
                        title
                        handle
                        publishedAt
                        isPublished
                        updatedAt
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
        """
        results: list[ShopifyPage] = []
        cursor: str | None = None

        while True:
            data = await self._execute(query, {"cursor": cursor})
            pages = data.get("data", {}).get("pages", {})
            edges = pages.get("edges", [])

            for edge in edges:
                node = edge["node"]
                results.append(
                    ShopifyPage(
                        shopify_id=node["id"],
                        page_type="page",
                        title=node.get("title"),
                        handle=node.get("handle"),
                        status="active" if node.get("isPublished") else "draft",
                        published_at=node.get("publishedAt"),
                        shopify_updated_at=node.get("updatedAt"),
                    )
                )

            page_info = pages.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        logger.info("Fetched Shopify pages", extra={"count": len(results)})
        return results

    # -------------------------------------------------------------------------
    # Bulk operation methods (for nightly sync)
    # -------------------------------------------------------------------------

    async def start_bulk_query(self, query: str) -> str:
        """Submit a bulk operation query.

        Args:
            query: The inner query for bulkOperationRunQuery.

        Returns:
            The bulk operation ID.
        """
        mutation = """
        mutation($query: String!) {
            bulkOperationRunQuery(query: $query) {
                bulkOperation {
                    id
                    status
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        data = await self._execute(mutation, {"query": query})
        result = data.get("data", {}).get("bulkOperationRunQuery", {})

        user_errors = result.get("userErrors", [])
        if user_errors:
            raise ShopifyAPIError(f"Bulk operation errors: {user_errors}")

        op = result.get("bulkOperation", {})
        return cast(str, op.get("id", ""))

    async def poll_bulk_operation(self, poll_interval: float = 10.0) -> dict[str, Any]:
        """Poll until the current bulk operation completes.

        Args:
            poll_interval: Seconds between polls.

        Returns:
            The bulk operation result dict with status, url, etc.
        """
        query = """
        {
            currentBulkOperation {
                id
                status
                errorCode
                objectCount
                url
            }
        }
        """
        while True:
            data = await self._execute(query)
            op = data.get("data", {}).get("currentBulkOperation", {})
            status = op.get("status", "")

            if status in ("COMPLETED", "FAILED", "CANCELED"):
                return cast(dict[str, Any], op)

            await asyncio.sleep(poll_interval)

    async def download_jsonl(self, url: str) -> list[dict[str, Any]]:
        """Download and parse a JSONL file from a bulk operation result URL.

        Args:
            url: The JSONL download URL from the bulk operation.

        Returns:
            List of parsed JSON objects.
        """
        import json

        resp = await self._client.get(url)
        resp.raise_for_status()

        results: list[dict[str, Any]] = []
        for line in resp.text.strip().split("\n"):
            if line.strip():
                results.append(json.loads(line))
        return results
