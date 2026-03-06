"""Tests for content generation pipeline with outline_first mode.

Tests cover:
- run_content_pipeline with outline_first=True:
  - Calls generate_outline instead of generate_content
  - Skips quality checks
  - Skips link planning
- run_generate_from_outline:
  - Calls generate_content_from_outline with correct data
  - Runs quality checks after generating content
  - Handles page-not-found errors
"""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.page_content import ContentStatus, PageContent
from app.models.page_keywords import PageKeywords
from app.models.project import Project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    """Create a test project."""
    project = Project(
        name=f"Pipeline Outline Test {uuid.uuid4().hex[:8]}",
        site_url=f"https://pipeline-outline-{uuid.uuid4().hex[:8]}.example.com",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def approved_page(
    db_session: AsyncSession, project: Project
) -> CrawledPage:
    """Create a crawled page with approved keyword."""
    page = CrawledPage(
        project_id=project.id,
        normalized_url=f"{project.site_url}/boots",
        status="completed",
        title="Boots Collection",
    )
    db_session.add(page)
    await db_session.commit()
    await db_session.refresh(page)

    kw = PageKeywords(
        crawled_page_id=page.id,
        primary_keyword="winter boots",
        is_approved=True,
    )
    db_session.add(kw)
    await db_session.commit()
    return page


@pytest.fixture
async def page_with_approved_outline(
    db_session: AsyncSession, approved_page: CrawledPage
) -> tuple[CrawledPage, PageContent]:
    """Create a page with an approved outline ready for content generation."""
    outline_data = {
        "page_name": "Boots Collection Title",
        "primary_keyword": "winter boots",
        "secondary_keywords": [],
        "section_details": [
            {
                "label": "winter-boot-selection",
                "tag": "h2",
                "headline": "Winter Boot Selection",
                "purpose": "Help visitors browse",
                "key_points": ["Quality", "Warmth"],
                "client_notes": "",
            }
        ],
        "page_progression": [
            {
                "order": 1,
                "question_answered": "What boots to choose?",
                "label": "winter-boot-selection",
                "tag": "h2",
                "headline": "Winter Boot Selection",
            },
        ],
    }
    pc = PageContent(
        crawled_page_id=approved_page.id,
        status=ContentStatus.COMPLETE.value,
        outline_json=outline_data,
        outline_status="approved",
    )
    db_session.add(pc)
    await db_session.commit()
    await db_session.refresh(pc)
    return approved_page, pc


# ---------------------------------------------------------------------------
# run_content_pipeline with outline_first=True
# ---------------------------------------------------------------------------


class TestRunContentPipelineOutlineFirst:
    """Tests for run_content_pipeline when outline_first=True.

    These tests call the REAL run_content_pipeline and patch only the
    internal functions it delegates to (generate_outline, generate_content,
    fetch_content_brief, run_quality_checks, _auto_link_planning).
    """

    @pytest.mark.asyncio
    async def test_calls_generate_outline_instead_of_content(
        self,
        db_session: AsyncSession,
        project: Project,
        approved_page: CrawledPage,
        mock_db_manager,
    ) -> None:
        """When outline_first=True, pipeline calls generate_outline, not generate_content."""
        mock_outline_result = MagicMock()
        mock_outline_result.success = True
        mock_outline_result.page_content = MagicMock()
        mock_outline_result.error = None

        mock_brief_result = MagicMock()
        mock_brief_result.success = True
        mock_brief_result.content_brief = None
        mock_brief_result.error = None

        mock_generate_outline = AsyncMock(return_value=mock_outline_result)
        mock_generate_content = AsyncMock()

        with (
            patch(
                "app.services.content_generation.generate_outline",
                mock_generate_outline,
            ),
            patch(
                "app.services.content_generation.generate_content",
                mock_generate_content,
            ),
            patch(
                "app.services.content_generation.fetch_content_brief",
                AsyncMock(return_value=mock_brief_result),
            ),
            patch(
                "app.services.content_generation._auto_link_planning",
                AsyncMock(),
            ),
        ):
            from app.services.content_generation import run_content_pipeline

            result = await run_content_pipeline(
                project_id=project.id,
                outline_first=True,
            )

        # generate_outline should have been called, generate_content should NOT
        mock_generate_outline.assert_called_once()
        mock_generate_content.assert_not_called()
        assert result.succeeded >= 1

    @pytest.mark.asyncio
    async def test_skips_quality_checks_in_outline_mode(
        self,
        db_session: AsyncSession,
        project: Project,
        approved_page: CrawledPage,
        mock_db_manager,
    ) -> None:
        """When outline_first=True, quality checks are not run."""
        mock_outline_result = MagicMock()
        mock_outline_result.success = True
        mock_outline_result.page_content = MagicMock()
        mock_outline_result.error = None

        mock_brief_result = MagicMock()
        mock_brief_result.success = True
        mock_brief_result.content_brief = None
        mock_brief_result.error = None

        mock_quality_checks = MagicMock()

        with (
            patch(
                "app.services.content_generation.generate_outline",
                AsyncMock(return_value=mock_outline_result),
            ),
            patch(
                "app.services.content_generation.fetch_content_brief",
                AsyncMock(return_value=mock_brief_result),
            ),
            patch(
                "app.services.content_generation.run_quality_checks",
                mock_quality_checks,
            ),
            patch(
                "app.services.content_generation._auto_link_planning",
                AsyncMock(),
            ),
        ):
            from app.services.content_generation import run_content_pipeline

            await run_content_pipeline(
                project_id=project.id,
                outline_first=True,
            )

        # Quality checks should NOT have been called in outline mode
        mock_quality_checks.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_link_planning_in_outline_mode(
        self,
        db_session: AsyncSession,
        project: Project,
        approved_page: CrawledPage,
        mock_db_manager,
    ) -> None:
        """When outline_first=True, link planning is not triggered."""
        mock_outline_result = MagicMock()
        mock_outline_result.success = True
        mock_outline_result.page_content = MagicMock()
        mock_outline_result.error = None

        mock_brief_result = MagicMock()
        mock_brief_result.success = True
        mock_brief_result.content_brief = None
        mock_brief_result.error = None

        mock_link_planning = AsyncMock()

        with (
            patch(
                "app.services.content_generation.generate_outline",
                AsyncMock(return_value=mock_outline_result),
            ),
            patch(
                "app.services.content_generation.fetch_content_brief",
                AsyncMock(return_value=mock_brief_result),
            ),
            patch(
                "app.services.content_generation._auto_link_planning",
                mock_link_planning,
            ),
        ):
            from app.services.content_generation import run_content_pipeline

            await run_content_pipeline(
                project_id=project.id,
                outline_first=True,
            )

        # Link planning should not be called in outline mode
        mock_link_planning.assert_not_called()


# ---------------------------------------------------------------------------
# run_generate_from_outline
# ---------------------------------------------------------------------------


class TestRunGenerateFromOutline:
    """Tests for run_generate_from_outline per-page pipeline.

    These tests call the REAL run_generate_from_outline with actual DB
    fixtures, patching only the Claude-calling functions.
    """

    @pytest.mark.asyncio
    async def test_calls_generate_content_from_outline(
        self,
        db_session: AsyncSession,
        project: Project,
        page_with_approved_outline: tuple[CrawledPage, PageContent],
        mock_db_manager,
    ) -> None:
        """run_generate_from_outline calls generate_content_from_outline with the outline data."""
        page, pc = page_with_approved_outline

        mock_content_result = MagicMock()
        mock_content_result.success = True
        mock_content_result.page_content = pc
        mock_content_result.error = None

        mock_gen_from_outline = AsyncMock(return_value=mock_content_result)

        with (
            patch(
                "app.services.content_generation.generate_content_from_outline",
                mock_gen_from_outline,
            ),
            patch(
                "app.services.content_generation.run_quality_checks",
            ),
            patch(
                "app.services.content_generation._auto_link_planning",
                AsyncMock(),
            ),
        ):
            from app.services.content_generation import run_generate_from_outline

            result = await run_generate_from_outline(
                project_id=project.id,
                page_id=page.id,
            )

        mock_gen_from_outline.assert_called_once()
        # Verify the outline_json was passed through
        call_kwargs = mock_gen_from_outline.call_args
        assert call_kwargs.kwargs.get("outline_json") is not None
        assert result.success is True

    @pytest.mark.asyncio
    async def test_runs_quality_checks_after_content(
        self,
        db_session: AsyncSession,
        project: Project,
        page_with_approved_outline: tuple[CrawledPage, PageContent],
        mock_db_manager,
    ) -> None:
        """run_generate_from_outline runs quality checks after generating content."""
        page, pc = page_with_approved_outline

        mock_content_result = MagicMock()
        mock_content_result.success = True
        mock_content_result.page_content = pc
        mock_content_result.error = None

        mock_quality_checks = MagicMock()

        with (
            patch(
                "app.services.content_generation.generate_content_from_outline",
                AsyncMock(return_value=mock_content_result),
            ),
            patch(
                "app.services.content_generation.run_quality_checks",
                mock_quality_checks,
            ),
            patch(
                "app.services.content_generation._auto_link_planning",
                AsyncMock(),
            ),
        ):
            from app.services.content_generation import run_generate_from_outline

            result = await run_generate_from_outline(
                project_id=project.id,
                page_id=page.id,
            )

        # Quality checks SHOULD be called for content generated from outline
        mock_quality_checks.assert_called_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_returns_error_for_nonexistent_page(
        self,
        project: Project,
        mock_db_manager,
    ) -> None:
        """run_generate_from_outline returns error for a page that doesn't exist."""
        from app.services.content_generation import run_generate_from_outline

        result = await run_generate_from_outline(
            project_id=project.id,
            page_id=str(uuid.uuid4()),
        )

        assert result.success is False
        assert "not found" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_returns_error_when_outline_not_approved(
        self,
        db_session: AsyncSession,
        project: Project,
        approved_page: CrawledPage,
        mock_db_manager,
    ) -> None:
        """run_generate_from_outline returns error when outline_status is not 'approved'."""
        # Create page content with draft outline (not approved)
        pc = PageContent(
            crawled_page_id=approved_page.id,
            status=ContentStatus.COMPLETE.value,
            outline_json={"page_name": "test"},
            outline_status="draft",
        )
        db_session.add(pc)
        await db_session.commit()

        from app.services.content_generation import run_generate_from_outline

        result = await run_generate_from_outline(
            project_id=project.id,
            page_id=approved_page.id,
        )

        assert result.success is False
        assert "approved" in (result.error or "").lower()
