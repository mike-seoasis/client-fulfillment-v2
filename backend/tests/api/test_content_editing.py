"""Tests for content editing, approval, recheck, and review endpoints.

Tests cover:
- PUT /projects/{id}/pages/{page_id}/content: partial update, word count recalc,
  approval cleared on edit, 404 for missing content
- POST /projects/{id}/pages/{page_id}/approve-content: approve/unapprove, 400 when
  status not complete, 404 for missing
- POST /projects/{id}/pages/{page_id}/recheck-content: re-runs quality checks,
  stores updated qa_results, 404 for missing
- POST /projects/{id}/bulk-approve-content: approves eligible pages, skips already
  approved, returns count, handles zero eligible
- GET /projects/{id}/pages/{page_id}/content: brief data included when ContentBrief
  exists, null when missing
- GET /projects/{id}/content-generation-status: pages_approved reflects actual count
- Integration: edit → recheck → approve flow in sequence
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_project(db: AsyncSession, name: str = "Test Project") -> "Project":  # noqa: F821
    """Create a project and return it refreshed."""
    from app.models.project import Project

    project = Project(name=name, site_url=f"https://{name.lower().replace(' ', '-')}.example.com")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def _create_page(db: AsyncSession, project_id: str, url_suffix: str = "/page1") -> "CrawledPage":  # noqa: F821
    """Create a crawled page for a project and return it refreshed."""
    from app.models.crawled_page import CrawledPage

    page = CrawledPage(
        project_id=project_id,
        normalized_url=f"https://test.example.com{url_suffix}",
        status="completed",
        title=f"Page {url_suffix}",
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


async def _create_content(
    db: AsyncSession,
    page_id: str,
    *,
    status: str = "complete",
    page_title: str = "Test Title",
    meta_description: str = "Test meta description",
    top_description: str = "Top description text",
    bottom_description: str = "<p>Bottom description content here</p>",
    word_count: int = 10,
    is_approved: bool = False,
    approved_at: datetime | None = None,
    qa_results: dict | None = None,
) -> "PageContent":  # noqa: F821
    """Create PageContent for a page and return it refreshed."""
    from app.models.page_content import PageContent

    content = PageContent(
        crawled_page_id=page_id,
        status=status,
        page_title=page_title,
        meta_description=meta_description,
        top_description=top_description,
        bottom_description=bottom_description,
        word_count=word_count,
        is_approved=is_approved,
        approved_at=approved_at,
        qa_results=qa_results,
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)
    return content


async def _create_keywords(
    db: AsyncSession, page_id: str, *, primary_keyword: str = "test keyword", is_approved: bool = True
) -> "PageKeywords":  # noqa: F821
    """Create approved PageKeywords for a page."""
    from app.models.page_keywords import PageKeywords

    kw = PageKeywords(crawled_page_id=page_id, primary_keyword=primary_keyword, is_approved=is_approved)
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_active_generations() -> None:
    """Clear the module-level active generations tracking before each test."""
    from app.api.v1.content_generation import _active_generations

    _active_generations.clear()


# ---------------------------------------------------------------------------
# PUT /projects/{id}/pages/{page_id}/content
# ---------------------------------------------------------------------------


class TestUpdatePageContent:
    """Tests for PUT /projects/{id}/pages/{page_id}/content endpoint."""

    @pytest.mark.asyncio
    async def test_partial_update_single_field(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PUT content with a single field updates only that field."""
        project = await _create_project(db_session, "Update Single Field")
        page = await _create_page(db_session, project.id)
        await _create_content(
            db_session,
            page.id,
            page_title="Original Title",
            meta_description="Original Meta",
            top_description="Original top",
            bottom_description="<p>Original bottom</p>",
        )

        response = await async_client.put(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
            json={"page_title": "Updated Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page_title"] == "Updated Title"
        # Other fields unchanged
        assert data["meta_description"] == "Original Meta"
        assert data["top_description"] == "Original top"
        assert data["bottom_description"] == "<p>Original bottom</p>"

    @pytest.mark.asyncio
    async def test_partial_update_multiple_fields(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PUT content with multiple fields updates all provided fields."""
        project = await _create_project(db_session, "Update Multi Fields")
        page = await _create_page(db_session, project.id)
        await _create_content(db_session, page.id)

        response = await async_client.put(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
            json={
                "page_title": "New Title",
                "meta_description": "New meta",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page_title"] == "New Title"
        assert data["meta_description"] == "New meta"

    @pytest.mark.asyncio
    async def test_word_count_recalculated(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PUT content recalculates word_count from all 4 fields."""
        project = await _create_project(db_session, "Word Count Recalc")
        page = await _create_page(db_session, project.id)
        await _create_content(
            db_session,
            page.id,
            page_title="one two",
            meta_description="three four",
            top_description="five six",
            bottom_description="<p>seven eight</p>",
            word_count=99,  # deliberately wrong
        )

        # Update only bottom_description to have more words
        response = await async_client.put(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
            json={"bottom_description": "<p>seven eight nine ten eleven</p>"},
        )

        assert response.status_code == 200
        data = response.json()
        # 2 (title) + 2 (meta) + 2 (top) + 5 (bottom) = 11
        assert data["word_count"] == 11

    @pytest.mark.asyncio
    async def test_approval_cleared_on_edit(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PUT content clears is_approved and approved_at."""
        project = await _create_project(db_session, "Approval Clear")
        page = await _create_page(db_session, project.id)
        await _create_content(
            db_session,
            page.id,
            is_approved=True,
            approved_at=datetime.now(UTC),
        )

        response = await async_client.put(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
            json={"page_title": "Edited Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_approved"] is False
        assert data["approved_at"] is None

    @pytest.mark.asyncio
    async def test_404_missing_content(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PUT content returns 404 when no PageContent exists."""
        project = await _create_project(db_session, "No Content Update")
        page = await _create_page(db_session, project.id)
        # No PageContent created

        response = await async_client.put(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
            json={"page_title": "New Title"},
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_missing_page(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """PUT content returns 404 for non-existent page."""
        project = await _create_project(db_session, "Missing Page Update")
        fake_page_id = str(uuid.uuid4())

        response = await async_client.put(
            f"/api/v1/projects/{project.id}/pages/{fake_page_id}/content",
            json={"page_title": "New Title"},
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /projects/{id}/pages/{page_id}/approve-content
# ---------------------------------------------------------------------------


class TestApproveContent:
    """Tests for POST /projects/{id}/pages/{page_id}/approve-content endpoint."""

    @pytest.mark.asyncio
    async def test_approve_sets_fields(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST approve-content sets is_approved=True and approved_at."""
        project = await _create_project(db_session, "Approve Set")
        page = await _create_page(db_session, project.id)
        await _create_content(db_session, page.id, status="complete")

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/approve-content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_approved"] is True
        assert data["approved_at"] is not None

    @pytest.mark.asyncio
    async def test_unapprove_clears_fields(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST approve-content?value=false clears is_approved and approved_at."""
        project = await _create_project(db_session, "Unapprove Clear")
        page = await _create_page(db_session, project.id)
        await _create_content(
            db_session,
            page.id,
            status="complete",
            is_approved=True,
            approved_at=datetime.now(UTC),
        )

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/approve-content?value=false",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_approved"] is False
        assert data["approved_at"] is None

    @pytest.mark.asyncio
    async def test_400_when_status_not_complete(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST approve-content returns 400 when content status is not 'complete'."""
        project = await _create_project(db_session, "Approve Non-Complete")
        page = await _create_page(db_session, project.id)
        await _create_content(db_session, page.id, status="pending")

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/approve-content",
        )

        assert response.status_code == 400
        assert "complete" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_404_missing_content(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST approve-content returns 404 when no PageContent exists."""
        project = await _create_project(db_session, "Approve No Content")
        page = await _create_page(db_session, project.id)

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/approve-content",
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_missing_page(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST approve-content returns 404 for non-existent page."""
        project = await _create_project(db_session, "Approve Missing Page")
        fake_page_id = str(uuid.uuid4())

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{fake_page_id}/approve-content",
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /projects/{id}/pages/{page_id}/recheck-content
# ---------------------------------------------------------------------------


class TestRecheckContent:
    """Tests for POST /projects/{id}/pages/{page_id}/recheck-content endpoint."""

    @pytest.mark.asyncio
    async def test_recheck_runs_quality_checks(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST recheck-content re-runs quality checks and stores qa_results."""
        project = await _create_project(db_session, "Recheck QA")
        page = await _create_page(db_session, project.id)
        # Content with clean text — should pass QA
        await _create_content(
            db_session,
            page.id,
            status="complete",
            page_title="Simple Clean Title",
            meta_description="A straightforward description",
            top_description="Clean top content",
            bottom_description="<p>Clean bottom content</p>",
            qa_results=None,
        )

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/recheck-content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["qa_results"] is not None
        assert "passed" in data["qa_results"]
        assert "issues" in data["qa_results"]
        assert "checked_at" in data["qa_results"]

    @pytest.mark.asyncio
    async def test_recheck_detects_issues(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST recheck-content detects AI trope issues in content."""
        project = await _create_project(db_session, "Recheck Detect")
        page = await _create_page(db_session, project.id)
        # Content with AI trope words — should fail QA
        await _create_content(
            db_session,
            page.id,
            status="complete",
            page_title="Delve into the landscape",
            meta_description="Unlock the power and unleash potential",
            top_description="In today's world, navigate the realm",
            bottom_description="<p>This is a game-changer that will harness results</p>",
            qa_results={"passed": True, "issues": [], "checked_at": "old"},
        )

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/recheck-content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["qa_results"]["passed"] is False
        assert len(data["qa_results"]["issues"]) > 0
        # checked_at should be updated
        assert data["qa_results"]["checked_at"] != "old"

    @pytest.mark.asyncio
    async def test_404_missing_content(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST recheck-content returns 404 when no PageContent exists."""
        project = await _create_project(db_session, "Recheck No Content")
        page = await _create_page(db_session, project.id)

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/recheck-content",
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_404_missing_page(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST recheck-content returns 404 for non-existent page."""
        project = await _create_project(db_session, "Recheck Missing Page")
        fake_page_id = str(uuid.uuid4())

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{fake_page_id}/recheck-content",
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /projects/{id}/bulk-approve-content
# ---------------------------------------------------------------------------


class TestBulkApproveContent:
    """Tests for POST /projects/{id}/bulk-approve-content endpoint."""

    @pytest.mark.asyncio
    async def test_approves_eligible_pages(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Bulk approve approves pages that are complete, QA passed, not yet approved."""
        project = await _create_project(db_session, "Bulk Approve Eligible")
        page1 = await _create_page(db_session, project.id, "/p1")
        page2 = await _create_page(db_session, project.id, "/p2")
        await _create_keywords(db_session, page1.id)
        await _create_keywords(db_session, page2.id, primary_keyword="kw2")

        # Both complete with QA passed, not approved
        await _create_content(
            db_session,
            page1.id,
            status="complete",
            is_approved=False,
            qa_results={"passed": True, "issues": [], "checked_at": "2026-01-01"},
        )
        await _create_content(
            db_session,
            page2.id,
            status="complete",
            is_approved=False,
            qa_results={"passed": True, "issues": [], "checked_at": "2026-01-01"},
        )

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/bulk-approve-content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["approved_count"] == 2

    @pytest.mark.asyncio
    async def test_skips_already_approved(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Bulk approve skips pages that are already approved."""
        project = await _create_project(db_session, "Bulk Skip Approved")
        page1 = await _create_page(db_session, project.id, "/p1")
        page2 = await _create_page(db_session, project.id, "/p2")
        await _create_keywords(db_session, page1.id)
        await _create_keywords(db_session, page2.id, primary_keyword="kw2")

        # page1: eligible
        await _create_content(
            db_session,
            page1.id,
            status="complete",
            is_approved=False,
            qa_results={"passed": True, "issues": [], "checked_at": "2026-01-01"},
        )
        # page2: already approved
        await _create_content(
            db_session,
            page2.id,
            status="complete",
            is_approved=True,
            approved_at=datetime.now(UTC),
            qa_results={"passed": True, "issues": [], "checked_at": "2026-01-01"},
        )

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/bulk-approve-content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["approved_count"] == 1

    @pytest.mark.asyncio
    async def test_returns_zero_when_none_eligible(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Bulk approve returns approved_count=0 when no pages are eligible."""
        project = await _create_project(db_session, "Bulk Zero Eligible")
        page = await _create_page(db_session, project.id)
        await _create_keywords(db_session, page.id)

        # QA failed — not eligible
        await _create_content(
            db_session,
            page.id,
            status="complete",
            is_approved=False,
            qa_results={"passed": False, "issues": [{"type": "tier1_ai_word"}], "checked_at": "2026-01-01"},
        )

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/bulk-approve-content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["approved_count"] == 0

    @pytest.mark.asyncio
    async def test_skips_non_complete_status(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Bulk approve skips pages with status != 'complete'."""
        project = await _create_project(db_session, "Bulk Non-Complete")
        page = await _create_page(db_session, project.id)
        await _create_keywords(db_session, page.id)

        await _create_content(
            db_session,
            page.id,
            status="pending",
            is_approved=False,
            qa_results={"passed": True, "issues": [], "checked_at": "2026-01-01"},
        )

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/bulk-approve-content",
        )

        assert response.status_code == 200
        assert response.json()["approved_count"] == 0


# ---------------------------------------------------------------------------
# GET /projects/{id}/pages/{page_id}/content — brief data
# ---------------------------------------------------------------------------


class TestGetContentWithBrief:
    """Tests for GET content endpoint brief data population."""

    @pytest.mark.asyncio
    async def test_brief_included_when_exists(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET content includes brief data when ContentBrief exists."""
        from app.models.content_brief import ContentBrief

        project = await _create_project(db_session, "Brief Included")
        page = await _create_page(db_session, project.id)
        await _create_content(db_session, page.id, status="complete")

        # Create ContentBrief
        brief = ContentBrief(
            page_id=page.id,
            keyword="target keyword",
            lsi_terms=["term1", "term2"],
            heading_targets=[{"level": "h2", "text": "Heading A", "priority": 1}],
            keyword_targets=[{"keyword": "target keyword", "count_min": 3, "count_max": 5}],
        )
        db_session.add(brief)
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["brief"] is not None
        assert data["brief"]["keyword"] == "target keyword"
        assert data["brief"]["lsi_terms"] == ["term1", "term2"]
        assert len(data["brief"]["heading_targets"]) == 1
        assert len(data["brief"]["keyword_targets"]) == 1

    @pytest.mark.asyncio
    async def test_brief_null_when_missing(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """GET content returns brief=null when no ContentBrief exists."""
        project = await _create_project(db_session, "Brief Missing")
        page = await _create_page(db_session, project.id)
        await _create_content(db_session, page.id, status="complete")
        # No ContentBrief created

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["brief"] is None


# ---------------------------------------------------------------------------
# GET /projects/{id}/content-generation-status — approval count
# ---------------------------------------------------------------------------


class TestStatusApprovalCount:
    """Tests for GET content-generation-status pages_approved field."""

    @pytest.mark.asyncio
    async def test_pages_approved_reflects_count(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Status endpoint reflects actual approved count."""
        project = await _create_project(db_session, "Status Approved Count")
        page1 = await _create_page(db_session, project.id, "/p1")
        page2 = await _create_page(db_session, project.id, "/p2")
        page3 = await _create_page(db_session, project.id, "/p3")
        await _create_keywords(db_session, page1.id, primary_keyword="kw1")
        await _create_keywords(db_session, page2.id, primary_keyword="kw2")
        await _create_keywords(db_session, page3.id, primary_keyword="kw3")

        # page1: approved
        await _create_content(
            db_session, page1.id, status="complete", is_approved=True, approved_at=datetime.now(UTC)
        )
        # page2: approved
        await _create_content(
            db_session, page2.id, status="complete", is_approved=True, approved_at=datetime.now(UTC)
        )
        # page3: not approved
        await _create_content(db_session, page3.id, status="complete", is_approved=False)

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/content-generation-status",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pages_approved"] == 2
        assert data["pages_total"] == 3
        assert data["pages_completed"] == 3

    @pytest.mark.asyncio
    async def test_pages_approved_zero_when_none_approved(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Status endpoint returns pages_approved=0 when no pages are approved."""
        project = await _create_project(db_session, "Status Zero Approved")
        page = await _create_page(db_session, project.id)
        await _create_keywords(db_session, page.id)
        await _create_content(db_session, page.id, status="complete", is_approved=False)

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/content-generation-status",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pages_approved"] == 0


# ---------------------------------------------------------------------------
# Integration: edit → recheck → approve
# ---------------------------------------------------------------------------


class TestEditRecheckApproveFlow:
    """Integration test for the full edit → recheck → approve workflow."""

    @pytest.mark.asyncio
    async def test_full_edit_recheck_approve_flow(
        self, async_client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Edit content, recheck quality, then approve — full workflow."""
        project = await _create_project(db_session, "Integration Flow")
        page = await _create_page(db_session, project.id)
        await _create_keywords(db_session, page.id)
        await _create_content(
            db_session,
            page.id,
            status="complete",
            page_title="Original Title",
            meta_description="Original meta",
            top_description="Original top",
            bottom_description="<p>Original bottom</p>",
            is_approved=True,
            approved_at=datetime.now(UTC),
            qa_results={"passed": True, "issues": [], "checked_at": "old"},
        )

        # Step 1: Edit — should clear approval
        edit_response = await async_client.put(
            f"/api/v1/projects/{project.id}/pages/{page.id}/content",
            json={"page_title": "Clean Updated Title"},
        )
        assert edit_response.status_code == 200
        edit_data = edit_response.json()
        assert edit_data["is_approved"] is False
        assert edit_data["approved_at"] is None
        assert edit_data["page_title"] == "Clean Updated Title"

        # Step 2: Recheck — should run QA on updated content
        recheck_response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/recheck-content",
        )
        assert recheck_response.status_code == 200
        recheck_data = recheck_response.json()
        assert recheck_data["qa_results"] is not None
        assert "passed" in recheck_data["qa_results"]
        assert recheck_data["qa_results"]["checked_at"] != "old"

        # Step 3: Approve — should set approval
        approve_response = await async_client.post(
            f"/api/v1/projects/{project.id}/pages/{page.id}/approve-content",
        )
        assert approve_response.status_code == 200
        approve_data = approve_response.json()
        assert approve_data["is_approved"] is True
        assert approve_data["approved_at"] is not None

        # Step 4: Verify status reflects approval
        status_response = await async_client.get(
            f"/api/v1/projects/{project.id}/content-generation-status",
        )
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["pages_approved"] == 1
