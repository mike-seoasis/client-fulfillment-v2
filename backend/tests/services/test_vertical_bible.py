"""Tests for VerticalBible service layer.

Tests slug generation, bible matching, frontmatter parsing/export,
and CRUD operations.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.vertical_bible import VerticalBible
from app.schemas.vertical_bible import VerticalBibleCreate, VerticalBibleUpdate
from app.services.vertical_bible import VerticalBibleService, _parse_frontmatter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    """Create a test project."""
    project = Project(
        id=str(uuid.uuid4()),
        name="Test Project",
        site_url="https://example.com",
        status="active",
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest.fixture
async def bible(db_session: AsyncSession, project: Project) -> VerticalBible:
    """Create a test bible."""
    bible = VerticalBible(
        id=str(uuid.uuid4()),
        project_id=project.id,
        name="Tattoo Cartridge Needles",
        slug="tattoo-cartridge-needles",
        content_md="## Domain Overview\nCartridge needles are...",
        trigger_keywords=["cartridge needle", "membrane", "round liner"],
        qa_rules={
            "preferred_terms": [
                {"use": "needle grouping", "instead_of": "needle configuration"}
            ],
            "banned_claims": [],
            "feature_attribution": [],
            "term_context_rules": [],
        },
        sort_order=0,
        is_active=True,
    )
    db_session.add(bible)
    await db_session.flush()
    return bible


# =============================================================================
# SLUG GENERATION
# =============================================================================


class TestSlugGeneration:
    def test_slug_from_simple_name(self):
        assert (
            VerticalBibleService.generate_slug("Tattoo Cartridge Needles")
            == "tattoo-cartridge-needles"
        )

    def test_slug_strips_special_chars(self):
        assert (
            VerticalBibleService.generate_slug("Ink & Pigment Guide!")
            == "ink-pigment-guide"
        )

    def test_slug_handles_unicode(self):
        assert (
            VerticalBibleService.generate_slug("Crème Brûlée Recipe")
            == "creme-brulee-recipe"
        )

    def test_slug_collapses_hyphens(self):
        assert (
            VerticalBibleService.generate_slug("Too   Many   Spaces")
            == "too-many-spaces"
        )

    def test_slug_empty_name_fallback(self):
        assert VerticalBibleService.generate_slug("!!!") == "bible"


# =============================================================================
# BIBLE MATCHING
# =============================================================================


class TestBibleMatching:
    async def test_match_exact_keyword(
        self, db_session: AsyncSession, project: Project, bible: VerticalBible
    ):
        result = await VerticalBibleService.match_bibles(
            db_session, project.id, "cartridge needle"
        )
        assert len(result) == 1
        assert result[0].id == bible.id

    async def test_match_substring_in_primary(
        self, db_session: AsyncSession, project: Project, bible: VerticalBible
    ):
        result = await VerticalBibleService.match_bibles(
            db_session, project.id, "best cartridge needles for lining"
        )
        assert len(result) == 1
        assert result[0].id == bible.id

    async def test_match_primary_in_trigger(
        self, db_session: AsyncSession, project: Project
    ):
        bible2 = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Long Trigger",
            slug="long-trigger",
            trigger_keywords=["tattoo cartridge needle guide"],
            is_active=True,
        )
        db_session.add(bible2)
        await db_session.flush()

        result = await VerticalBibleService.match_bibles(
            db_session, project.id, "cartridge needle"
        )
        assert any(b.id == bible2.id for b in result)

    async def test_no_match_unrelated(
        self, db_session: AsyncSession, project: Project, bible: VerticalBible
    ):
        result = await VerticalBibleService.match_bibles(
            db_session, project.id, "best tattoo inks"
        )
        assert len(result) == 0

    async def test_match_case_insensitive(
        self, db_session: AsyncSession, project: Project, bible: VerticalBible
    ):
        result = await VerticalBibleService.match_bibles(
            db_session, project.id, "CARTRIDGE NEEDLE guide"
        )
        assert len(result) == 1

    async def test_match_via_secondary_keyword(
        self, db_session: AsyncSession, project: Project, bible: VerticalBible
    ):
        result = await VerticalBibleService.match_bibles(
            db_session,
            project.id,
            "needle guide",
            secondary_keywords=["membrane types"],
        )
        assert len(result) == 1

    async def test_inactive_bible_excluded(
        self, db_session: AsyncSession, project: Project
    ):
        inactive = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Inactive",
            slug="inactive",
            trigger_keywords=["test keyword"],
            is_active=False,
        )
        db_session.add(inactive)
        await db_session.flush()

        result = await VerticalBibleService.match_bibles(
            db_session, project.id, "test keyword"
        )
        assert len(result) == 0

    async def test_empty_trigger_keywords_no_match(
        self, db_session: AsyncSession, project: Project
    ):
        empty_kw = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="No Keywords",
            slug="no-keywords",
            trigger_keywords=[],
            is_active=True,
        )
        db_session.add(empty_kw)
        await db_session.flush()

        result = await VerticalBibleService.match_bibles(
            db_session, project.id, "anything"
        )
        # Should not include the empty-keyword bible
        assert not any(b.id == empty_kw.id for b in result)

    async def test_multiple_bibles_sorted_by_order(
        self, db_session: AsyncSession, project: Project
    ):
        bible_a = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Alpha",
            slug="alpha",
            trigger_keywords=["shared term"],
            sort_order=1,
            is_active=True,
        )
        bible_b = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Beta",
            slug="beta",
            trigger_keywords=["shared term"],
            sort_order=0,
            is_active=True,
        )
        db_session.add_all([bible_a, bible_b])
        await db_session.flush()

        result = await VerticalBibleService.match_bibles(
            db_session, project.id, "shared term"
        )
        # Beta (sort_order=0) should come before Alpha (sort_order=1)
        ids = [b.id for b in result]
        assert ids.index(bible_b.id) < ids.index(bible_a.id)

    async def test_no_bibles_returns_empty(
        self, db_session: AsyncSession, project: Project
    ):
        # Use a project with no bibles at all
        empty_project = Project(
            id=str(uuid.uuid4()),
            name="Empty Project",
            site_url="https://empty.com",
            status="active",
        )
        db_session.add(empty_project)
        await db_session.flush()

        result = await VerticalBibleService.match_bibles(
            db_session, empty_project.id, "anything"
        )
        assert result == []


# =============================================================================
# FRONTMATTER PARSING
# =============================================================================


class TestFrontmatterParsing:
    def test_parse_valid_frontmatter(self):
        md = """---
name: Test Bible
trigger_keywords:
  - keyword1
  - keyword2
sort_order: 5
---

## Content
Hello world"""
        fm, body = _parse_frontmatter(md)
        assert fm["name"] == "Test Bible"
        assert fm["trigger_keywords"] == ["keyword1", "keyword2"]
        assert fm["sort_order"] == 5
        assert "## Content" in body

    def test_parse_minimal_frontmatter(self):
        md = """---
name: Minimal
---

Body content"""
        fm, body = _parse_frontmatter(md)
        assert fm["name"] == "Minimal"
        assert "Body content" in body

    def test_parse_no_frontmatter(self):
        md = "Just plain markdown content"
        fm, body = _parse_frontmatter(md)
        assert fm == {}
        assert "Just plain markdown content" in body

    def test_parse_broken_yaml(self):
        md = """---
invalid: : yaml
---
Content"""
        fm, body = _parse_frontmatter(md)
        assert fm == {}

    def test_parse_missing_closing_delimiter(self):
        md = """---
name: Test
Content without closing"""
        fm, body = _parse_frontmatter(md)
        assert fm == {}

    def test_parse_unicode_content(self):
        md = """---
name: Unicode Test
---

Crème brûlée and naïve résumé"""
        fm, body = _parse_frontmatter(md)
        assert fm["name"] == "Unicode Test"
        assert "Crème brûlée" in body

    def test_parse_empty_string(self):
        fm, body = _parse_frontmatter("")
        assert fm == {}
        assert body == ""


# =============================================================================
# FRONTMATTER EXPORT
# =============================================================================


class TestFrontmatterExport:
    def test_export_roundtrip(self):
        bible = VerticalBible(
            name="Test Bible",
            slug="test-bible",
            trigger_keywords=["kw1", "kw2"],
            qa_rules={
                "preferred_terms": [],
                "banned_claims": [],
                "feature_attribution": [],
                "term_context_rules": [],
            },
            sort_order=0,
            content_md="## Overview\nTest content",
        )
        exported = VerticalBibleService.export_to_markdown(bible)
        fm, body = _parse_frontmatter(exported)
        assert fm["name"] == "Test Bible"
        assert fm["slug"] == "test-bible"
        assert fm["trigger_keywords"] == ["kw1", "kw2"]
        assert "## Overview" in body

    def test_export_includes_qa_rules(self):
        bible = VerticalBible(
            name="QA Bible",
            slug="qa-bible",
            trigger_keywords=[],
            qa_rules={
                "preferred_terms": [
                    {"use": "correct", "instead_of": "wrong"}
                ],
                "banned_claims": [],
                "feature_attribution": [],
                "term_context_rules": [],
            },
            sort_order=0,
            content_md="Content",
        )
        exported = VerticalBibleService.export_to_markdown(bible)
        assert "qa_rules" in exported
        assert "preferred_terms" in exported

    def test_export_omits_empty_qa_rules(self):
        bible = VerticalBible(
            name="No QA",
            slug="no-qa",
            trigger_keywords=[],
            qa_rules={
                "preferred_terms": [],
                "banned_claims": [],
                "feature_attribution": [],
                "term_context_rules": [],
            },
            sort_order=0,
            content_md="Content",
        )
        exported = VerticalBibleService.export_to_markdown(bible)
        assert "qa_rules" not in exported

    def test_export_includes_nonzero_sort_order(self):
        bible = VerticalBible(
            name="Ordered",
            slug="ordered",
            trigger_keywords=[],
            qa_rules={},
            sort_order=5,
            content_md="Content",
        )
        exported = VerticalBibleService.export_to_markdown(bible)
        assert "sort_order: 5" in exported

    def test_export_omits_zero_sort_order(self):
        bible = VerticalBible(
            name="Default Order",
            slug="default-order",
            trigger_keywords=[],
            qa_rules={},
            sort_order=0,
            content_md="Content",
        )
        exported = VerticalBibleService.export_to_markdown(bible)
        assert "sort_order" not in exported


# =============================================================================
# CRUD OPERATIONS
# =============================================================================


class TestCRUDOperations:
    async def test_create_bible_auto_slug(
        self, db_session: AsyncSession, project: Project
    ):
        data = VerticalBibleCreate(name="Auto Slug Test")
        bible = await VerticalBibleService.create_bible(
            db_session, project.id, data
        )
        assert bible.slug == "auto-slug-test"

    async def test_create_bible_custom_slug(
        self, db_session: AsyncSession, project: Project
    ):
        data = VerticalBibleCreate(name="Custom", slug="my-custom-slug")
        bible = await VerticalBibleService.create_bible(
            db_session, project.id, data
        )
        assert bible.slug == "my-custom-slug"

    async def test_create_bible_slug_collision_appends_suffix(
        self, db_session: AsyncSession, project: Project
    ):
        data1 = VerticalBibleCreate(name="Duplicate Name")
        await VerticalBibleService.create_bible(db_session, project.id, data1)

        data2 = VerticalBibleCreate(name="Duplicate Name")
        bible2 = await VerticalBibleService.create_bible(
            db_session, project.id, data2
        )
        assert bible2.slug == "duplicate-name-2"

    async def test_get_bible_not_found(
        self, db_session: AsyncSession, project: Project
    ):
        with pytest.raises(HTTPException) as exc_info:
            await VerticalBibleService.get_bible(
                db_session, project.id, str(uuid.uuid4())
            )
        assert exc_info.value.status_code == 404

    async def test_list_bibles_ordered(
        self, db_session: AsyncSession, project: Project
    ):
        b1 = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Zeta",
            slug="zeta",
            sort_order=2,
            is_active=True,
        )
        b2 = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Alpha",
            slug="alpha-list",
            sort_order=1,
            is_active=True,
        )
        db_session.add_all([b1, b2])
        await db_session.flush()

        bibles = await VerticalBibleService.list_bibles(db_session, project.id)
        slugs = [b.slug for b in bibles]
        assert slugs.index("alpha-list") < slugs.index("zeta")

    async def test_list_bibles_active_only(
        self, db_session: AsyncSession, project: Project
    ):
        active = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Active One",
            slug="active-one",
            is_active=True,
        )
        inactive = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Inactive One",
            slug="inactive-one",
            is_active=False,
        )
        db_session.add_all([active, inactive])
        await db_session.flush()

        bibles = await VerticalBibleService.list_bibles(
            db_session, project.id, active_only=True
        )
        ids = [b.id for b in bibles]
        assert active.id in ids
        assert inactive.id not in ids

    async def test_update_bible_partial(
        self, db_session: AsyncSession, project: Project, bible: VerticalBible
    ):
        data = VerticalBibleUpdate(name="Updated Name")
        updated = await VerticalBibleService.update_bible(
            db_session, project.id, bible.id, data
        )
        assert updated.name == "Updated Name"
        assert updated.slug == "tattoo-cartridge-needles"  # unchanged

    async def test_update_bible_slug_collision(
        self, db_session: AsyncSession, project: Project, bible: VerticalBible
    ):
        # Create another bible
        other = VerticalBible(
            id=str(uuid.uuid4()),
            project_id=project.id,
            name="Other Bible",
            slug="other-bible",
            is_active=True,
        )
        db_session.add(other)
        await db_session.flush()

        # Try to update the first bible's slug to the other's slug
        # _ensure_unique_slug will append suffix, not raise
        data = VerticalBibleUpdate(slug="other-bible")
        updated = await VerticalBibleService.update_bible(
            db_session, project.id, bible.id, data
        )
        assert updated.slug == "other-bible-2"

    async def test_delete_bible(
        self, db_session: AsyncSession, project: Project, bible: VerticalBible
    ):
        bible_id = bible.id
        await VerticalBibleService.delete_bible(db_session, project.id, bible_id)

        with pytest.raises(HTTPException) as exc_info:
            await VerticalBibleService.get_bible(
                db_session, project.id, bible_id
            )
        assert exc_info.value.status_code == 404

    async def test_delete_bible_not_found(
        self, db_session: AsyncSession, project: Project
    ):
        with pytest.raises(HTTPException) as exc_info:
            await VerticalBibleService.delete_bible(
                db_session, project.id, str(uuid.uuid4())
            )
        assert exc_info.value.status_code == 404
