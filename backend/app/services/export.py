"""Export service for generating CSV exports with Shopify handle extraction.

Provides utilities for:
- Extracting Shopify handles from page URLs
- Sanitizing project names for filenames
- Generating Matrixify-format CSV exports
"""

import csv
import io
import re
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawled_page import CrawledPage
from app.models.page_content import PageContent


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
    async def generate_csv(
        db: AsyncSession,
        project_id: str,
        page_ids: list[str] | None = None,
    ) -> tuple[str, int]:
        """Generate a Matrixify-format CSV for approved page content.

        Queries CrawledPage joined with PageContent where is_approved=True
        and status=complete. If page_ids is provided, filters to only those
        pages (silently skipping non-approved ones).

        Args:
            db: Async database session.
            project_id: UUID of the project.
            page_ids: Optional list of CrawledPage IDs to filter to.

        Returns:
            Tuple of (csv_string with UTF-8 BOM, row_count).
        """
        stmt = (
            select(CrawledPage, PageContent)
            .join(PageContent, PageContent.crawled_page_id == CrawledPage.id)
            .where(
                CrawledPage.project_id == project_id,
                PageContent.is_approved.is_(True),
                PageContent.status == "complete",
            )
        )

        if page_ids is not None:
            stmt = stmt.where(CrawledPage.id.in_(page_ids))

        result = await db.execute(stmt)
        rows = result.all()

        output = io.StringIO()
        # UTF-8 BOM for Excel compatibility
        output.write("\ufeff")

        writer = csv.writer(output)
        writer.writerow([
            "Handle",
            "Title",
            "Body (HTML)",
            "SEO Description",
            "Metafield: custom.top_description [single_line_text_field]",
        ])

        row_count = 0
        for page, content in rows:
            writer.writerow([
                ExportService.extract_handle(page.normalized_url),
                content.page_title or "",
                content.bottom_description or "",
                content.meta_description or "",
                content.top_description or "",
            ])
            row_count += 1

        csv_string = output.getvalue()
        output.close()
        return csv_string, row_count

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
