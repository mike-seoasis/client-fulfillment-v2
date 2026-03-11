"""Unit tests for Shopify GraphQL client.

Tests cover:
- Authenticated request sends correct headers
- Adaptive rate limiting pauses when points low
- Retry on 429/502/503/504 with backoff
- ShopifyAuthError raised on 401 (no retry)
- Cursor pagination fetches all pages
- Bulk operation submission, polling, JSONL download
- Mock httpx responses throughout

Uses unittest.mock for mocking httpx async client.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.shopify import (
    ShopifyAPIError,
    ShopifyAuthError,
    ShopifyGraphQLClient,
    ShopifyPage as ShopifyPageData,
)


# ---------------------------------------------------------------------------
# Mock Response Helpers
# ---------------------------------------------------------------------------


def make_graphql_response(
    data: dict,
    status_code: int = 200,
    currently_available: int = 500,
    restore_rate: float = 50.0,
) -> httpx.Response:
    """Create a mock httpx response for a GraphQL query."""
    body = {
        "data": data,
        "extensions": {
            "cost": {
                "throttleStatus": {
                    "currentlyAvailable": currently_available,
                    "restoreRate": restore_rate,
                    "maximumAvailable": 1000,
                }
            }
        },
    }
    return httpx.Response(
        status_code=status_code,
        json=body,
        request=httpx.Request("POST", "https://test.myshopify.com/admin/api/2024-10/graphql.json"),
    )


def make_error_response(status_code: int, body: str = "Error") -> httpx.Response:
    """Create a mock httpx error response."""
    return httpx.Response(
        status_code=status_code,
        text=body,
        request=httpx.Request("POST", "https://test.myshopify.com/admin/api/2024-10/graphql.json"),
    )


def make_paginated_response(
    items: list[dict],
    has_next_page: bool = False,
    end_cursor: str | None = None,
    resource_key: str = "products",
    currently_available: int = 500,
) -> httpx.Response:
    """Create a paginated GraphQL response."""
    edges = [{"node": item, "cursor": f"cursor_{i}"} for i, item in enumerate(items)]
    data = {
        resource_key: {
            "edges": edges,
            "pageInfo": {
                "hasNextPage": has_next_page,
                "endCursor": end_cursor or (f"cursor_{len(items) - 1}" if items else None),
            },
        }
    }
    return make_graphql_response(data, currently_available=currently_available)


# ---------------------------------------------------------------------------
# Test: Authenticated Requests
# ---------------------------------------------------------------------------


class TestAuthenticatedRequests:
    """Tests for authenticated GraphQL request handling."""

    async def test_sends_correct_auth_header(self) -> None:
        """Test that the client sends X-Shopify-Access-Token header."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="shpat_test_token_123",
        )

        # The internal httpx client should have the auth header
        assert client._client.headers["X-Shopify-Access-Token"] == "shpat_test_token_123"

        await client.close()

    async def test_targets_correct_graphql_endpoint(self) -> None:
        """Test that queries target the correct store GraphQL endpoint."""
        client = ShopifyGraphQLClient(
            store_domain="acmestore.myshopify.com",
            access_token="token",
        )

        assert "acmestore.myshopify.com" in client._endpoint
        assert "graphql.json" in client._endpoint
        assert "2024-10" in client._endpoint

        await client.close()


# ---------------------------------------------------------------------------
# Test: Adaptive Rate Limiting
# ---------------------------------------------------------------------------


class TestAdaptiveRateLimiting:
    """Tests for adaptive rate limiting based on throttle status."""

    async def test_pauses_when_points_low(self) -> None:
        """Test client pauses when currentlyAvailable points are below 100."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        # Response with low available points
        low_points_response = make_graphql_response(
            data={"shop": {"name": "Test"}},
            currently_available=50,  # Below 100 threshold
            restore_rate=50.0,
        )

        client._client.post = AsyncMock(return_value=low_points_response)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client._execute("{ shop { name } }")

            # Should have slept: (100 - 50) / 50.0 = 1.0 seconds
            mock_sleep.assert_called()
            sleep_duration = mock_sleep.call_args[0][0]
            assert abs(sleep_duration - 1.0) < 0.1

        await client.close()

    async def test_no_pause_when_points_sufficient(self) -> None:
        """Test client does not pause when points are above threshold."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        response = make_graphql_response(
            data={"shop": {"name": "Test"}},
            currently_available=500,  # Well above 100
        )

        client._client.post = AsyncMock(return_value=response)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client._execute("{ shop { name } }")

            # Should NOT have slept for rate limiting
            mock_sleep.assert_not_called()

        await client.close()


# ---------------------------------------------------------------------------
# Test: Retry Logic
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Tests for retry behavior on transient errors."""

    @pytest.mark.parametrize("status_code", [429, 502, 503, 504])
    async def test_retries_on_transient_errors(self, status_code: int) -> None:
        """Test client retries on transient status codes."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        error_response = make_error_response(status_code)
        success_response = make_graphql_response({"shop": {"name": "Test"}})

        client._client.post = AsyncMock(
            side_effect=[error_response, error_response, success_response]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._execute("{ shop { name } }")

        assert result is not None
        assert result["data"]["shop"]["name"] == "Test"
        assert client._client.post.call_count == 3

        await client.close()

    async def test_raises_after_max_retries_exhausted(self) -> None:
        """Test client raises ShopifyAPIError after all retries are exhausted."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        error_response = make_error_response(503)

        # All attempts fail (initial + MAX_RETRIES = 4 total)
        client._client.post = AsyncMock(return_value=error_response)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ShopifyAPIError):
                await client._execute("{ shop { name } }")

        await client.close()

    async def test_uses_exponential_backoff(self) -> None:
        """Test retry uses exponential backoff between attempts."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        error_response = make_error_response(503)
        success_response = make_graphql_response({"shop": {"name": "Test"}})

        client._client.post = AsyncMock(
            side_effect=[error_response, error_response, success_response]
        )

        sleep_durations: list[float] = []
        original_sleep = asyncio.sleep

        async def track_sleep(duration: float) -> None:
            sleep_durations.append(duration)

        with patch("asyncio.sleep", side_effect=track_sleep):
            await client._execute("{ shop { name } }")

        # Should have 2 sleeps (before retry 1 and retry 2)
        assert len(sleep_durations) == 2
        # Backoff: 2.0 * 2^0 = 2.0, 2.0 * 2^1 = 4.0
        assert sleep_durations[0] == 2.0
        assert sleep_durations[1] == 4.0

        await client.close()


# ---------------------------------------------------------------------------
# Test: Auth Error Handling
# ---------------------------------------------------------------------------


class TestAuthErrorHandling:
    """Tests for ShopifyAuthError on 401 responses."""

    async def test_raises_auth_error_on_401(self) -> None:
        """Test ShopifyAuthError is raised on 401 Unauthorized."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="revoked_token",
        )

        error_response = make_error_response(401, "Unauthorized")
        client._client.post = AsyncMock(return_value=error_response)

        with pytest.raises(ShopifyAuthError):
            await client._execute("{ shop { name } }")

        await client.close()

    async def test_does_not_retry_on_401(self) -> None:
        """Test client does NOT retry on 401 Unauthorized."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="revoked_token",
        )

        error_response = make_error_response(401, "Unauthorized")
        client._client.post = AsyncMock(return_value=error_response)

        with pytest.raises(ShopifyAuthError):
            await client._execute("{ shop { name } }")

        # Should only call once, no retries
        assert client._client.post.call_count == 1

        await client.close()


# ---------------------------------------------------------------------------
# Test: Cursor Pagination
# ---------------------------------------------------------------------------


class TestCursorPagination:
    """Tests for cursor-based pagination across all page types."""

    async def test_fetch_products_multiple_pages(self) -> None:
        """Test fetch_products paginates until hasNextPage is false."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        page1 = make_paginated_response(
            items=[{
                "id": "gid://shopify/Product/1",
                "title": "Product 1",
                "handle": "p1",
                "status": "ACTIVE",
                "productType": "Shoes",
                "tags": ["tag1"],
                "publishedAt": "2025-01-01T00:00:00Z",
                "updatedAt": "2025-06-01T00:00:00Z",
            }],
            has_next_page=True,
            end_cursor="cursor_page1",
            resource_key="products",
        )
        page2 = make_paginated_response(
            items=[{
                "id": "gid://shopify/Product/2",
                "title": "Product 2",
                "handle": "p2",
                "status": "ACTIVE",
                "productType": "Shoes",
                "tags": [],
                "publishedAt": "2025-02-01T00:00:00Z",
                "updatedAt": "2025-06-01T00:00:00Z",
            }],
            has_next_page=False,
            resource_key="products",
        )

        client._client.post = AsyncMock(side_effect=[page1, page2])

        results = await client.fetch_products()

        assert len(results) == 2
        assert all(isinstance(r, ShopifyPageData) for r in results)
        assert results[0].shopify_id == "gid://shopify/Product/1"
        assert results[1].shopify_id == "gid://shopify/Product/2"
        assert client._client.post.call_count == 2

        await client.close()

    async def test_fetch_collections_single_page(self) -> None:
        """Test fetch_collections with a single page of results."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        page = make_paginated_response(
            items=[
                {
                    "id": "gid://shopify/Collection/1",
                    "title": "Collection 1",
                    "handle": "c1",
                    "updatedAt": "2025-06-01T00:00:00Z",
                    "productsCount": {"count": 10},
                },
                {
                    "id": "gid://shopify/Collection/2",
                    "title": "Collection 2",
                    "handle": "c2",
                    "updatedAt": "2025-06-01T00:00:00Z",
                    "productsCount": {"count": 5},
                },
            ],
            has_next_page=False,
            resource_key="collections",
        )

        client._client.post = AsyncMock(return_value=page)

        results = await client.fetch_collections()

        assert len(results) == 2
        assert results[0].page_type == "collection"
        assert results[0].product_count == 10
        assert client._client.post.call_count == 1

        await client.close()

    async def test_fetch_articles(self) -> None:
        """Test fetch_articles extracts blog metadata."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        page = make_paginated_response(
            items=[{
                "id": "gid://shopify/Article/1",
                "title": "Blog Post 1",
                "handle": "post-1",
                "publishedAt": "2025-03-01T00:00:00Z",
                "tags": ["running", "tips"],
                "updatedAt": "2025-06-01T00:00:00Z",
                "blog": {"title": "News", "handle": "news"},
            }],
            has_next_page=False,
            resource_key="articles",
        )

        client._client.post = AsyncMock(return_value=page)

        results = await client.fetch_articles()

        assert len(results) == 1
        assert results[0].page_type == "article"
        assert results[0].blog_name == "News"
        assert results[0].blog_handle == "news"
        assert results[0].tags == ["running", "tips"]

        await client.close()

    async def test_fetch_pages_empty(self) -> None:
        """Test fetch_pages handles empty results."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        page = make_paginated_response(
            items=[],
            has_next_page=False,
            resource_key="pages",
        )

        client._client.post = AsyncMock(return_value=page)

        results = await client.fetch_pages()

        assert len(results) == 0

        await client.close()

    async def test_fetch_pages_with_published_status(self) -> None:
        """Test fetch_pages correctly maps isPublished to status."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        page = make_paginated_response(
            items=[
                {
                    "id": "gid://shopify/Page/1",
                    "title": "Published Page",
                    "handle": "published",
                    "publishedAt": "2025-01-01T00:00:00Z",
                    "isPublished": True,
                    "updatedAt": "2025-06-01T00:00:00Z",
                },
                {
                    "id": "gid://shopify/Page/2",
                    "title": "Draft Page",
                    "handle": "draft",
                    "publishedAt": None,
                    "isPublished": False,
                    "updatedAt": "2025-06-01T00:00:00Z",
                },
            ],
            has_next_page=False,
            resource_key="pages",
        )

        client._client.post = AsyncMock(return_value=page)

        results = await client.fetch_pages()

        assert len(results) == 2
        assert results[0].status == "active"
        assert results[1].status == "draft"

        await client.close()


# ---------------------------------------------------------------------------
# Test: Bulk Operations
# ---------------------------------------------------------------------------


class TestBulkOperations:
    """Tests for bulk operation submission, polling, and JSONL download."""

    async def test_submit_bulk_query(self) -> None:
        """Test bulk operation query submission returns operation ID."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        submit_response = make_graphql_response({
            "bulkOperationRunQuery": {
                "bulkOperation": {
                    "id": "gid://shopify/BulkOperation/1",
                    "status": "CREATED",
                },
                "userErrors": [],
            }
        })

        client._client.post = AsyncMock(return_value=submit_response)

        result = await client.start_bulk_query("{ products { edges { node { id title } } } }")

        assert result == "gid://shopify/BulkOperation/1"

        await client.close()

    async def test_submit_bulk_query_with_user_errors_raises(self) -> None:
        """Test bulk operation raises on user errors."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        error_response = make_graphql_response({
            "bulkOperationRunQuery": {
                "bulkOperation": None,
                "userErrors": [{"field": "query", "message": "Invalid query"}],
            }
        })

        client._client.post = AsyncMock(return_value=error_response)

        with pytest.raises(ShopifyAPIError):
            await client.start_bulk_query("{ invalid }")

        await client.close()

    async def test_poll_bulk_operation_until_completed(self) -> None:
        """Test polling bulk operation until COMPLETED status."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        running_response = make_graphql_response({
            "currentBulkOperation": {
                "id": "gid://shopify/BulkOperation/1",
                "status": "RUNNING",
                "errorCode": None,
                "objectCount": "50",
                "url": None,
            }
        })
        completed_response = make_graphql_response({
            "currentBulkOperation": {
                "id": "gid://shopify/BulkOperation/1",
                "status": "COMPLETED",
                "errorCode": None,
                "objectCount": "100",
                "url": "https://storage.shopify.com/bulk/results.jsonl",
            }
        })

        client._client.post = AsyncMock(
            side_effect=[running_response, running_response, completed_response]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.poll_bulk_operation(poll_interval=0.01)

        assert result["status"] == "COMPLETED"
        assert result["url"] == "https://storage.shopify.com/bulk/results.jsonl"
        assert client._client.post.call_count == 3

        await client.close()

    async def test_poll_bulk_operation_failed(self) -> None:
        """Test polling returns FAILED status."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        failed_response = make_graphql_response({
            "currentBulkOperation": {
                "id": "gid://shopify/BulkOperation/1",
                "status": "FAILED",
                "errorCode": "INTERNAL_SERVER_ERROR",
                "objectCount": "0",
                "url": None,
            }
        })

        client._client.post = AsyncMock(return_value=failed_response)

        result = await client.poll_bulk_operation()

        assert result["status"] == "FAILED"

        await client.close()

    async def test_download_jsonl(self) -> None:
        """Test downloading and parsing JSONL bulk operation results."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        jsonl_content = (
            '{"id":"gid://1","title":"Product 1"}\n'
            '{"id":"gid://2","title":"Product 2"}\n'
        )

        mock_download_response = httpx.Response(
            status_code=200,
            text=jsonl_content,
            request=httpx.Request("GET", "https://storage.shopify.com/results.jsonl"),
        )

        client._client.get = AsyncMock(return_value=mock_download_response)

        results = await client.download_jsonl("https://storage.shopify.com/results.jsonl")

        assert len(results) == 2
        assert results[0]["id"] == "gid://1"
        assert results[0]["title"] == "Product 1"
        assert results[1]["id"] == "gid://2"
        assert results[1]["title"] == "Product 2"

        await client.close()

    async def test_download_jsonl_empty(self) -> None:
        """Test downloading empty JSONL returns empty list."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        mock_download_response = httpx.Response(
            status_code=200,
            text="",
            request=httpx.Request("GET", "https://storage.shopify.com/results.jsonl"),
        )

        client._client.get = AsyncMock(return_value=mock_download_response)

        results = await client.download_jsonl("https://storage.shopify.com/results.jsonl")

        assert len(results) == 0

        await client.close()


# ---------------------------------------------------------------------------
# Test: GraphQL Error Handling
# ---------------------------------------------------------------------------


class TestGraphQLErrors:
    """Tests for GraphQL-level error handling."""

    async def test_graphql_errors_in_response_raises(self) -> None:
        """Test GraphQL errors in response body raise ShopifyAPIError."""
        client = ShopifyGraphQLClient(
            store_domain="test.myshopify.com",
            access_token="token",
        )

        error_response = httpx.Response(
            status_code=200,
            json={
                "errors": [{"message": "Invalid query syntax"}],
                "extensions": {
                    "cost": {"throttleStatus": {"currentlyAvailable": 500, "restoreRate": 50}}
                },
            },
            request=httpx.Request("POST", "https://test.myshopify.com/admin/api/2024-10/graphql.json"),
        )

        client._client.post = AsyncMock(return_value=error_response)

        with pytest.raises(ShopifyAPIError, match="GraphQL errors"):
            await client._execute("{ invalid { query } }")

        await client.close()
