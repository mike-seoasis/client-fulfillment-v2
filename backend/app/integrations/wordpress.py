"""WordPress REST API client for fetching and updating blog posts.

Uses httpx with HTTP Basic Auth (application passwords). Handles paginated
post fetching with _embed for inline terms, and single-post content updates.
"""

import asyncio
import html
from dataclasses import dataclass
from typing import Any, cast

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

# WordPress REST API pagination limit
WP_PER_PAGE = 100

# Retry settings for rate-limited requests
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry


@dataclass
class WPSiteInfo:
    """Basic site information from WordPress."""

    name: str
    url: str
    total_posts: int


@dataclass
class WPPost:
    """A single WordPress post with embedded data."""

    id: int
    title: str
    url: str
    content_html: str
    excerpt: str
    slug: str
    categories: list[int]
    tags: list[int]
    tag_names: list[str]
    word_count: int


class WordPressClient:
    """WordPress REST API client using httpx + Basic Auth.

    Args:
        site_url: The WordPress site URL (e.g. https://example.com).
        username: WordPress username.
        app_password: WordPress application password.
    """

    def __init__(self, site_url: str, username: str, app_password: str) -> None:
        self._site_url = site_url.rstrip("/")
        self._api_base = f"{self._site_url}/wp-json/wp/v2"
        self._client = httpx.AsyncClient(
            auth=(username, app_password),
            timeout=30.0,
            follow_redirects=True,
        )

    async def validate_credentials(self) -> WPSiteInfo:
        """Validate credentials and return site info.

        Raises:
            httpx.HTTPStatusError: If credentials are invalid (401/403).
            httpx.ConnectError: If site is unreachable.
        """
        # Fetch site info (no auth needed but tests connectivity)
        site_resp = await self._client.get(f"{self._site_url}/wp-json")
        site_resp.raise_for_status()
        site_data = site_resp.json()

        # Fetch post count (auth needed for full access)
        posts_resp = await self._client.get(
            f"{self._api_base}/posts",
            params={"per_page": 1, "status": "publish"},
        )
        posts_resp.raise_for_status()
        total_posts = int(posts_resp.headers.get("X-WP-Total", "0"))

        return WPSiteInfo(
            name=site_data.get("name", ""),
            url=site_data.get("url", self._site_url),
            total_posts=total_posts,
        )

    async def _get_with_retry(self, url: str, params: dict[str, Any]) -> httpx.Response:
        """GET request with retry on 429 Too Many Requests."""
        for attempt in range(MAX_RETRIES + 1):
            resp = await self._client.get(url, params=params)
            if resp.status_code == 429 and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "WP API rate limited, retrying",
                    extra={"attempt": attempt + 1, "delay": delay, "url": url},
                )
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return resp
        # Should not reach here, but satisfy type checker
        resp.raise_for_status()
        return resp

    async def _fetch_posts_paginated(
        self,
        status: str,
        title_filter: list[str] | None = None,
    ) -> tuple[list[WPPost], int]:
        """Fetch all posts for a single status value, with pagination.

        Uses WP ``search`` param for server-side filtering when the title
        filter is a single term.  Falls back to client-side filtering for
        multi-term filters (WP ``search`` only accepts one string).

        Returns:
            Tuple of (matched posts, total posts fetched before filtering).
        """
        all_posts: list[WPPost] = []
        total_fetched = 0
        page = 1

        # Single-term filter → let WP do server-side search
        use_server_search = title_filter and len(title_filter) == 1
        # Multi-term → client-side filtering after fetch
        use_client_filter = title_filter and len(title_filter) > 1

        while True:
            params: dict[str, Any] = {
                "per_page": WP_PER_PAGE,
                "page": page,
                "status": status,
                "_embed": "wp:term",
            }
            if use_server_search and title_filter:
                params["search"] = title_filter[0]

            resp = await self._get_with_retry(
                f"{self._api_base}/posts",
                params=params,
            )
            posts_data = resp.json()

            if not posts_data:
                break

            for post in posts_data:
                total_fetched += 1
                wp_post = self._parse_post(post)

                # Client-side title filter for multi-term queries
                if use_client_filter and title_filter:
                    title_lower = html.unescape(wp_post.title).lower()
                    if not any(
                        html.unescape(f).lower() in title_lower for f in title_filter
                    ):
                        continue

                all_posts.append(wp_post)

            total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
            if page >= total_pages:
                break
            page += 1

        return all_posts, total_fetched

    async def fetch_all_posts(
        self,
        title_filter: list[str] | None = None,
        post_status: str = "publish",
    ) -> tuple[list[WPPost], int]:
        """Fetch posts by status, optionally filtered by title substring.

        Uses _embed to inline taxonomy terms (tags/categories) in a single
        request per page. Paginates automatically with retry on rate limits.

        Args:
            title_filter: Optional list of title substrings. Only posts whose
                title contains any of these substrings (case-insensitive) are
                returned.
            post_status: WP post status to fetch. 'publish', 'private', or
                'any' (fetches both publish and private).

        Returns:
            Tuple of (matched posts, total posts fetched before filtering).

        Raises:
            ValueError: If ``post_status='private'`` and the authenticated
                user lacks ``read_private_posts`` capability.
        """
        if post_status == "any":
            # Always fetch published posts first (works for any role)
            all_posts, total_fetched = await self._fetch_posts_paginated(
                "publish", title_filter
            )

            # Try private posts — may fail if user lacks read_private_posts
            try:
                private_posts, private_total = await self._fetch_posts_paginated(
                    "private", title_filter
                )
                all_posts.extend(private_posts)
                total_fetched += private_total
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (400, 403):
                    logger.warning(
                        "Could not fetch private posts — user may lack "
                        "read_private_posts capability. Returning published "
                        "posts only.",
                        extra={"status_code": exc.response.status_code},
                    )
                else:
                    raise

        elif post_status == "private":
            try:
                all_posts, total_fetched = await self._fetch_posts_paginated(
                    "private", title_filter
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (400, 403):
                    raise ValueError(
                        "Cannot fetch private posts: the WordPress user does "
                        "not have the read_private_posts capability. Use an "
                        "Editor or Administrator role, or switch to "
                        "'Published' status."
                    ) from exc
                raise

        else:
            # 'publish' or any other single status value
            all_posts, total_fetched = await self._fetch_posts_paginated(
                post_status, title_filter
            )

        logger.info(
            "Fetched WordPress posts",
            extra={
                "matched": len(all_posts),
                "total_fetched": total_fetched,
                "status": post_status,
                "filter": title_filter,
            },
        )
        return all_posts, total_fetched

    async def fetch_categories(self) -> list[dict[str, Any]]:
        """Fetch all categories."""
        resp = await self._client.get(
            f"{self._api_base}/categories",
            params={"per_page": WP_PER_PAGE},
        )
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    async def fetch_tags(self) -> list[dict[str, Any]]:
        """Fetch all tags."""
        resp = await self._client.get(
            f"{self._api_base}/tags",
            params={"per_page": WP_PER_PAGE},
        )
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    async def update_post_content(self, post_id: int, content: str) -> dict[str, Any]:
        """Update a post's content HTML.

        Args:
            post_id: WordPress post ID.
            content: New HTML content for the post body.

        Returns:
            Updated post data from WP API.
        """
        resp = await self._client.post(
            f"{self._api_base}/posts/{post_id}",
            json={"content": content},
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()

    def _parse_post(self, post: dict[str, Any]) -> WPPost:
        """Parse a WP REST API post response into a WPPost dataclass."""
        title = html.unescape(post.get("title", {}).get("rendered", ""))
        content_html = post.get("content", {}).get("rendered", "")
        excerpt = post.get("excerpt", {}).get("rendered", "")

        # Extract tag names from embedded terms
        tag_names: list[str] = []
        embedded = post.get("_embedded", {})
        wp_terms = embedded.get("wp:term", [])
        for term_group in wp_terms:
            if isinstance(term_group, list):
                for term in term_group:
                    if term.get("taxonomy") == "post_tag":
                        tag_names.append(term.get("name", ""))

        # Rough word count from content
        import re

        text = re.sub(r"<[^>]+>", " ", content_html)
        word_count = len(text.split())

        return WPPost(
            id=post.get("id", 0),
            title=title,
            url=post.get("link", ""),
            content_html=content_html,
            excerpt=excerpt,
            slug=post.get("slug", ""),
            categories=post.get("categories", []),
            tags=post.get("tags", []),
            tag_names=tag_names,
            word_count=word_count,
        )
