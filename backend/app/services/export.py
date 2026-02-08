"""Export service for generating CSV exports with Shopify handle extraction.

Provides utilities for:
- Extracting Shopify handles from page URLs
- Sanitizing project names for filenames
"""

import re
from urllib.parse import urlparse


class ExportService:
    """Service for export-related operations."""

    @staticmethod
    def extract_handle(url: str) -> str:
        """Extract a Shopify handle from a URL path.

        If the path contains /collections/, uses the segment(s) after it.
        Otherwise uses the last non-empty path segment.

        Args:
            url: Full URL string (e.g. "https://store.com/collections/running-shoes")

        Returns:
            The extracted handle string.

        Examples:
            >>> ExportService.extract_handle("https://store.com/collections/running-shoes")
            'running-shoes'
            >>> ExportService.extract_handle("https://store.com/shoes/hiking")
            'hiking'
            >>> ExportService.extract_handle("https://store.com/collections/sandals?sort=price")
            'sandals'
        """
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")

        if not path:
            return ""

        # If path contains /collections/, use segment(s) after it
        collections_prefix = "/collections/"
        collections_idx = path.find(collections_prefix)
        if collections_idx != -1:
            after = path[collections_idx + len(collections_prefix) :]
            if after:
                return after

        # Otherwise use last non-empty path segment
        segments = [s for s in path.split("/") if s]
        if segments:
            return segments[-1]

        return ""

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Convert a project name to a safe filename.

        Converts to lowercase and replaces non-alphanumeric characters with hyphens.
        Collapses multiple consecutive hyphens and strips leading/trailing hyphens.

        Args:
            name: Project name string.

        Returns:
            Sanitized filename string (lowercase alphanumeric + hyphens).

        Examples:
            >>> ExportService.sanitize_filename("My Cool Project")
            'my-cool-project'
            >>> ExportService.sanitize_filename("Project #1 (Test)")
            'project-1-test'
        """
        result = name.lower()
        result = re.sub(r"[^a-z0-9]+", "-", result)
        result = result.strip("-")
        return result
