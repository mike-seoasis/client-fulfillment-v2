"""URL normalization utility for canonicalizing URLs.

Provides consistent URL normalization for crawled pages:
- Removes fragments (#section)
- Handles trailing slashes consistently
- Normalizes/removes query parameters
- Lowercases scheme and hostname
- Removes default ports (80 for http, 443 for https)
- Handles URL encoding consistently

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Log validation failures with field names and rejected values
"""

from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.core.logging import get_logger

logger = get_logger("url_normalizer")


@dataclass
class URLNormalizationOptions:
    """Options for URL normalization behavior.

    Attributes:
        remove_fragments: Remove URL fragments (#section). Default True.
        remove_trailing_slash: Remove trailing slash from path. Default True.
        remove_query_params: Remove all query parameters. Default False.
        sort_query_params: Sort query parameters alphabetically. Default True.
        remove_default_port: Remove default ports (80/443). Default True.
        lowercase_scheme: Lowercase the URL scheme. Default True.
        lowercase_host: Lowercase the hostname. Default True.
        strip_www: Remove 'www.' prefix from hostname. Default False.
        allowed_query_params: Set of query params to keep (all others removed).
                             If None, all params are kept (unless remove_query_params is True).
        blocked_query_params: Set of query params to remove (e.g., tracking params).
                             Applied after allowed_query_params filter.
    """

    remove_fragments: bool = True
    remove_trailing_slash: bool = True
    remove_query_params: bool = False
    sort_query_params: bool = True
    remove_default_port: bool = True
    lowercase_scheme: bool = True
    lowercase_host: bool = True
    strip_www: bool = False
    allowed_query_params: set[str] | None = None
    blocked_query_params: set[str] = field(
        default_factory=lambda: {
            # Common tracking parameters to remove by default
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "msclkid",
            "ref",
            "source",
        }
    )


# Default options instance for convenience
DEFAULT_OPTIONS = URLNormalizationOptions()


class URLNormalizer:
    """URL normalizer with configurable options and logging.

    Provides consistent URL normalization for deduplication and comparison.
    All operations are logged at DEBUG level for debugging.
    """

    def __init__(self, options: URLNormalizationOptions | None = None) -> None:
        """Initialize normalizer with options.

        Args:
            options: Normalization options. Uses defaults if None.
        """
        self.options = options or DEFAULT_OPTIONS
        logger.debug(
            "URLNormalizer initialized",
            extra={
                "remove_fragments": self.options.remove_fragments,
                "remove_trailing_slash": self.options.remove_trailing_slash,
                "remove_query_params": self.options.remove_query_params,
                "sort_query_params": self.options.sort_query_params,
                "strip_www": self.options.strip_www,
            },
        )

    def normalize(self, url: str) -> str:
        """Normalize a URL according to configured options.

        Args:
            url: The URL to normalize.

        Returns:
            The normalized URL string.

        Raises:
            ValueError: If the URL is invalid or empty.
        """
        logger.debug("normalize() called", extra={"input_url": url[:200] if url else ""})

        if not url or not url.strip():
            logger.warning(
                "URL normalization failed: empty URL",
                extra={"field": "url", "rejected_value": repr(url)},
            )
            raise ValueError("URL cannot be empty")

        url = url.strip()

        try:
            parsed = urlparse(url)
        except Exception as e:
            logger.error(
                "URL parsing failed",
                extra={
                    "input_url": url[:200],
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )
            raise ValueError(f"Invalid URL: {e}") from e

        # Validate URL has required parts
        if not parsed.scheme:
            logger.warning(
                "URL normalization failed: missing scheme",
                extra={"field": "scheme", "rejected_value": url[:200]},
            )
            raise ValueError("URL must have a scheme (http/https)")

        if not parsed.netloc:
            logger.warning(
                "URL normalization failed: missing host",
                extra={"field": "netloc", "rejected_value": url[:200]},
            )
            raise ValueError("URL must have a host")

        # Normalize scheme
        scheme = parsed.scheme
        if self.options.lowercase_scheme:
            scheme = scheme.lower()

        # Normalize host and port
        netloc = self._normalize_netloc(parsed.netloc, scheme)

        # Normalize path
        path = self._normalize_path(parsed.path)

        # Normalize query string
        query = self._normalize_query(parsed.query)

        # Handle fragment
        fragment = "" if self.options.remove_fragments else parsed.fragment

        # Reconstruct URL
        normalized = urlunparse((scheme, netloc, path, "", query, fragment))

        logger.debug(
            "normalize() completed",
            extra={"input_url": url[:200], "output_url": normalized[:200]},
        )

        return normalized

    def _normalize_netloc(self, netloc: str, scheme: str) -> str:
        """Normalize the network location (host:port).

        Args:
            netloc: The original netloc string.
            scheme: The URL scheme (for default port removal).

        Returns:
            Normalized netloc string.
        """
        # Split host and port
        if ":" in netloc and not netloc.startswith("["):
            # IPv4 or hostname with port
            host, port_str = netloc.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                # Invalid port, keep as-is
                host = netloc
                port = None
        elif netloc.startswith("[") and "]:" in netloc:
            # IPv6 with port: [::1]:8080
            bracket_end = netloc.index("]")
            host = netloc[: bracket_end + 1]
            port_str = netloc[bracket_end + 2 :]
            try:
                port = int(port_str)
            except ValueError:
                port = None
        else:
            host = netloc
            port = None

        # Lowercase host
        if self.options.lowercase_host:
            # Handle IPv6 brackets
            if host.startswith("[") and host.endswith("]"):
                host = "[" + host[1:-1].lower() + "]"
            else:
                host = host.lower()

        # Strip www
        if self.options.strip_www and host.startswith("www."):
            host = host[4:]

        # Remove default port
        if self.options.remove_default_port and port is not None:
            default_ports = {"http": 80, "https": 443}
            if default_ports.get(scheme.lower()) == port:
                port = None

        # Reconstruct netloc
        if port is not None:
            return f"{host}:{port}"
        return host

    def _normalize_path(self, path: str) -> str:
        """Normalize the URL path.

        Args:
            path: The original path string.

        Returns:
            Normalized path string.
        """
        if not path:
            path = "/"

        # Remove trailing slash (except for root)
        if self.options.remove_trailing_slash and len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        # Normalize multiple slashes to single slash
        while "//" in path:
            path = path.replace("//", "/")

        return path

    def _normalize_query(self, query: str) -> str:
        """Normalize query parameters.

        Args:
            query: The original query string.

        Returns:
            Normalized query string.
        """
        if self.options.remove_query_params or not query:
            return ""

        try:
            params = parse_qs(query, keep_blank_values=True)
        except Exception as e:
            logger.warning(
                "Query string parsing failed, removing query",
                extra={"query": query[:100], "error": str(e)},
            )
            return ""

        # Filter allowed params
        if self.options.allowed_query_params is not None:
            params = {
                k: v for k, v in params.items() if k in self.options.allowed_query_params
            }

        # Remove blocked params
        if self.options.blocked_query_params:
            params = {
                k: v
                for k, v in params.items()
                if k not in self.options.blocked_query_params
            }

        if not params:
            return ""

        # Sort params if configured
        if self.options.sort_query_params:
            params = dict(sorted(params.items()))

        # Reconstruct query string
        # urlencode with doseq=True handles multiple values for same key
        return urlencode(params, doseq=True)

    def is_same_page(self, url1: str, url2: str) -> bool:
        """Check if two URLs refer to the same page after normalization.

        Args:
            url1: First URL to compare.
            url2: Second URL to compare.

        Returns:
            True if URLs normalize to the same string.
        """
        try:
            return self.normalize(url1) == self.normalize(url2)
        except ValueError:
            return False


def normalize_url(
    url: str,
    options: URLNormalizationOptions | None = None,
) -> str:
    """Normalize a URL with default or custom options.

    Convenience function that creates a normalizer and normalizes a single URL.

    Args:
        url: The URL to normalize.
        options: Optional normalization options.

    Returns:
        The normalized URL string.

    Raises:
        ValueError: If the URL is invalid or empty.

    Example:
        >>> normalize_url("https://WWW.Example.COM/path/?b=2&a=1#section")
        'https://www.example.com/path?a=1&b=2'

        >>> normalize_url("https://example.com/path/", URLNormalizationOptions(strip_www=True))
        'https://example.com/path'
    """
    normalizer = URLNormalizer(options)
    return normalizer.normalize(url)
