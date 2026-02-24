"""Tests for export service: handle extraction, filename sanitization, CSV generation."""

import csv
import io
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawled_page import CrawledPage
from app.models.page_content import PageContent
from app.services.export import ExportService


class TestExtractHandle:
    """Tests for ExportService.extract_handle."""

    def test_standard_collections_url(self):
        """Standard /collections/ URL returns the handle after it."""
        result = ExportService.extract_handle(
            "https://store.com/collections/running-shoes"
        )
        assert result == "running-shoes"

    def test_url_without_collections(self):
        """URL without /collections/ returns last path segment."""
        result = ExportService.extract_handle("https://store.com/shoes/hiking")
        assert result == "hiking"

    def test_query_params_stripped(self):
        """Query parameters are stripped from the handle."""
        result = ExportService.extract_handle(
            "https://store.com/collections/sandals?sort=price&page=2"
        )
        assert result == "sandals"

    def test_trailing_slash_stripped(self):
        """Trailing slash is stripped from the handle."""
        result = ExportService.extract_handle(
            "https://store.com/collections/boots/"
        )
        assert result == "boots"

    def test_nested_path_after_collections(self):
        """Nested path after /collections/ preserves sub-path."""
        result = ExportService.extract_handle(
            "https://store.com/collections/mens/running-shoes"
        )
        assert result == "mens/running-shoes"

    def test_empty_path(self):
        """URL with no path returns empty string."""
        result = ExportService.extract_handle("https://store.com")
        assert result == ""

    def test_trailing_slash_and_query_params(self):
        """Both trailing slash and query params are handled."""
        result = ExportService.extract_handle(
            "https://store.com/collections/jackets/?sort=new"
        )
        assert result == "jackets"


class TestSanitizeFilename:
    """Tests for ExportService.sanitize_filename."""

    def test_special_characters_replaced(self):
        """Special characters become hyphens, result is alphanumeric + hyphens."""
        result = ExportService.sanitize_filename("Project #1 (Test)")
        assert result == "project-1-test"

    def test_spaces_replaced(self):
        """Spaces are converted to hyphens."""
        result = ExportService.sanitize_filename("My Cool Project")
        assert result == "my-cool-project"

    def test_consecutive_special_chars_collapsed(self):
        """Multiple consecutive special characters collapse to single hyphen."""
        result = ExportService.sanitize_filename("hello---world!!!foo")
        assert result == "hello-world-foo"

    def test_leading_trailing_stripped(self):
        """Leading and trailing hyphens are stripped."""
        result = ExportService.sanitize_filename("  --Project-- ")
        assert result == "project"


class TestGenerateCSV:
    """Tests for ExportService.generate_csv with DB fixtures."""

    @pytest.fixture
    async def project_id(self):
        """Return a consistent project UUID for tests."""
        return str(uuid4())

    @pytest.fixture
    async def approved_page_with_content(self, db_session: AsyncSession, project_id):
        """Create a CrawledPage + PageContent that is approved and complete."""
        page = CrawledPage(
            id=str(uuid4()),
            project_id=project_id,
            normalized_url="https://store.com/collections/running-shoes",
            status="completed",
            labels=[],
        )
        db_session.add(page)
        await db_session.flush()

        content = PageContent(
            id=str(uuid4()),
            crawled_page_id=page.id,
            page_title="Running Shoes Collection",
            meta_description="Shop the best running shoes",
            top_description="Top picks for runners",
            bottom_description="<p>Full HTML body content</p>",
            status="complete",
            is_approved=True,
        )
        db_session.add(content)
        await db_session.flush()

        return page, content

    @pytest.fixture
    async def approved_page_with_null_fields(
        self, db_session: AsyncSession, project_id
    ):
        """Create a CrawledPage + PageContent with null content fields."""
        page = CrawledPage(
            id=str(uuid4()),
            project_id=project_id,
            normalized_url="https://store.com/collections/hiking-boots",
            status="completed",
            labels=[],
        )
        db_session.add(page)
        await db_session.flush()

        content = PageContent(
            id=str(uuid4()),
            crawled_page_id=page.id,
            page_title=None,
            meta_description=None,
            top_description=None,
            bottom_description=None,
            status="complete",
            is_approved=True,
        )
        db_session.add(content)
        await db_session.flush()

        return page, content

    async def test_csv_all_fields_populated(
        self, db_session: AsyncSession, project_id, approved_page_with_content
    ):
        """CSV has correct columns and values when all fields are populated."""
        page, content = approved_page_with_content

        csv_string, row_count = await ExportService.generate_csv(
            db_session, project_id, command="UPDATE", shopify_placeholder_tag="my-tag"
        )

        assert row_count == 1

        # Strip BOM for parsing
        clean = csv_string.lstrip("\ufeff")
        reader = csv.reader(io.StringIO(clean))
        rows = list(reader)

        # Header row
        assert rows[0] == ExportService.CSV_HEADERS

        # Data row
        assert rows[1][0] == "UPDATE"  # Command
        assert rows[1][1] == "running-shoes"  # Handle extracted from URL
        assert rows[1][2] == "Running Shoes Collection"  # Title
        assert rows[1][3] == "<p>Full HTML body content</p>"  # Body (HTML)
        assert rows[1][4] == "Shop the best running shoes"  # SEO Description
        assert rows[1][5] == "Top picks for runners"  # Metafield
        assert rows[1][6] == "Best Selling"  # Sort Order
        assert rows[1][7] == "FALSE"  # Published
        assert rows[1][8] == "all conditions"  # Must Match
        assert rows[1][9] == "Tag"  # Rule: Product Column
        assert rows[1][10] == "Equals"  # Rule: Relation
        assert rows[1][11] == "my-tag"  # Rule: Condition

    async def test_csv_null_fields_render_empty(
        self, db_session: AsyncSession, project_id, approved_page_with_null_fields
    ):
        """Null content fields render as empty strings, not 'None'."""
        csv_string, row_count = await ExportService.generate_csv(
            db_session, project_id
        )

        assert row_count == 1

        clean = csv_string.lstrip("\ufeff")
        reader = csv.reader(io.StringIO(clean))
        rows = list(reader)

        data_row = rows[1]
        # Command is first column
        assert data_row[0] == "UPDATE"
        # Handle should still be extracted
        assert data_row[1] == "hiking-boots"
        # All content fields should be empty strings
        assert data_row[2] == ""
        assert data_row[3] == ""
        assert data_row[4] == ""
        assert data_row[5] == ""
        # Verify no 'None' strings
        assert "None" not in csv_string

    async def test_csv_new_command_for_clusters(
        self, db_session: AsyncSession, project_id, approved_page_with_content
    ):
        """CSV uses NEW command when specified (for cluster exports)."""
        csv_string, row_count = await ExportService.generate_csv(
            db_session, project_id, command="NEW"
        )

        clean = csv_string.lstrip("\ufeff")
        reader = csv.reader(io.StringIO(clean))
        rows = list(reader)
        assert rows[1][0] == "NEW"

    async def test_csv_has_utf8_bom(
        self, db_session: AsyncSession, project_id, approved_page_with_content
    ):
        """CSV starts with UTF-8 BOM for Excel compatibility."""
        csv_string, _ = await ExportService.generate_csv(db_session, project_id)
        assert csv_string.startswith("\ufeff")
