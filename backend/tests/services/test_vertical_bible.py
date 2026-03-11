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


# =============================================================================
# TRANSCRIPT EXTRACTION
# =============================================================================

import json

from app.integrations.claude import CompletionResult
from app.services.vertical_bible import (
    _build_extraction_user_prompt,
    _validate_qa_rules,
    _parse_extraction_response,
    generate_bible_from_transcript,
)


class TestBuildExtractionUserPrompt:
    """Test _build_extraction_user_prompt."""

    def test_includes_vertical_name(self):
        prompt = _build_extraction_user_prompt("some transcript", "Tattoo Needles")
        assert 'about "Tattoo Needles"' in prompt

    def test_includes_transcript(self):
        prompt = _build_extraction_user_prompt("Expert: membranes prevent backflow", "Test")
        assert "membranes prevent backflow" in prompt

    def test_includes_json_schema(self):
        prompt = _build_extraction_user_prompt("test", "Test")
        assert "trigger_keywords" in prompt
        assert "content_md" in prompt
        assert "qa_rules" in prompt
        assert "preferred_terms" in prompt
        assert "banned_claims" in prompt


class TestValidateQaRules:
    """Test _validate_qa_rules validation and sanitization."""

    def test_valid_preferred_terms(self):
        rules = {
            "preferred_terms": [
                {"use": "needle grouping", "instead_of": "needle configuration"}
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["preferred_terms"]) == 1
        assert result["preferred_terms"][0]["use"] == "needle grouping"

    def test_invalid_preferred_term_stripped(self):
        rules = {
            "preferred_terms": [
                {"instead_of": "needle configuration"}  # missing 'use'
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["preferred_terms"]) == 0

    def test_empty_string_values_stripped(self):
        rules = {
            "preferred_terms": [
                {"use": "", "instead_of": "something"}
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["preferred_terms"]) == 0

    def test_valid_banned_claims(self):
        rules = {
            "banned_claims": [
                {"claim": "only brand", "context": "membrane", "reason": "All brands have it"}
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["banned_claims"]) == 1

    def test_valid_feature_attribution(self):
        rules = {
            "feature_attribution": [
                {
                    "feature": "membrane",
                    "correct_component": "cartridge needle",
                    "wrong_components": ["tattoo pen", ""],
                }
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["feature_attribution"]) == 1
        assert result["feature_attribution"][0]["wrong_components"] == ["tattoo pen"]

    def test_valid_term_context_rules(self):
        rules = {
            "term_context_rules": [
                {
                    "term": "membrane",
                    "correct_context": ["recoil", "protection"],
                    "wrong_contexts": ["ink savings"],
                    "explanation": "Membranes prevent backflow",
                }
            ]
        }
        result = _validate_qa_rules(rules)
        assert len(result["term_context_rules"]) == 1

    def test_missing_categories_default_to_empty(self):
        result = _validate_qa_rules({})
        assert result == {
            "preferred_terms": [],
            "banned_claims": [],
            "feature_attribution": [],
            "term_context_rules": [],
        }

    def test_non_dict_input_handled(self):
        rules = {"preferred_terms": "not a list"}
        result = _validate_qa_rules(rules)
        assert result["preferred_terms"] == []

    def test_whitespace_stripped(self):
        rules = {
            "preferred_terms": [
                {"use": "  needle grouping  ", "instead_of": " config "}
            ]
        }
        result = _validate_qa_rules(rules)
        assert result["preferred_terms"][0]["use"] == "needle grouping"
        assert result["preferred_terms"][0]["instead_of"] == "config"



class TestParseExtractionResponse:
    """Test _parse_extraction_response JSON parsing."""

    def test_valid_json(self):
        json_str = '{"name": "Test", "slug": "test", "trigger_keywords": []}'
        result = _parse_extraction_response(json_str)
        assert result is not None
        assert result["name"] == "Test"

    def test_json_with_code_fences(self):
        text = '```json\n{"name": "Test"}\n```'
        result = _parse_extraction_response(text)
        assert result is not None
        assert result["name"] == "Test"

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"name": "Test"}\nDone!'
        result = _parse_extraction_response(text)
        assert result is not None

    def test_invalid_json_returns_none(self):
        result = _parse_extraction_response("not json at all")
        assert result is None

    def test_non_dict_returns_none(self):
        result = _parse_extraction_response('["list", "not", "dict"]')
        assert result is None


class TestGenerateBibleFromTranscript:
    """Integration tests for generate_bible_from_transcript."""

    @pytest.mark.asyncio
    async def test_empty_transcript_raises(self, db_session):
        with pytest.raises(ValueError, match="empty"):
            await generate_bible_from_transcript("", "Test", "project-id", db_session)

    @pytest.mark.asyncio
    async def test_empty_name_raises(self, db_session):
        with pytest.raises(ValueError, match="Vertical name"):
            await generate_bible_from_transcript("some text", "", "project-id", db_session)

    @pytest.mark.asyncio
    async def test_transcript_too_long_raises(self, db_session):
        long_text = "x" * 100_001
        with pytest.raises(ValueError, match="maximum length"):
            await generate_bible_from_transcript(long_text, "Test", "project-id", db_session)

    def _mock_claude(self, mocker, completion_result):
        """Helper to mock get_claude() returning a client with a given complete() result."""
        from unittest.mock import AsyncMock

        mock_client = AsyncMock()
        mock_client.complete.return_value = completion_result
        mocker.patch(
            "app.services.vertical_bible.get_claude",
            return_value=mock_client,
        )
        return mock_client

    @pytest.mark.asyncio
    async def test_successful_extraction(self, db_session, mocker):
        """Mock Claude and verify the bible is created correctly."""
        mock_response = json.dumps({
            "name": "Tattoo Needles",
            "slug": "tattoo-needles",
            "trigger_keywords": ["cartridge needle", "membrane"],
            "content_md": "## Domain Overview\nCartridge needles are...",
            "qa_rules": {
                "preferred_terms": [
                    {"use": "needle grouping", "instead_of": "needle config"}
                ],
                "banned_claims": [],
                "feature_attribution": [],
                "term_context_rules": [],
            },
        })

        self._mock_claude(mocker, CompletionResult(
            success=True,
            text=mock_response,
            input_tokens=1000,
            output_tokens=500,
            duration_ms=5000,
        ))

        bible = await generate_bible_from_transcript(
            transcript="Expert: cartridge needles have membranes...",
            vertical_name="Tattoo Needles",
            project_id="test-project-id",
            db=db_session,
        )

        assert bible.name == "Tattoo Needles"
        assert bible.is_active is False
        assert len(bible.trigger_keywords) == 2
        assert len(bible.qa_rules["preferred_terms"]) == 1
        assert "Domain Overview" in bible.content_md

    @pytest.mark.asyncio
    async def test_claude_failure_raises_runtime_error(self, db_session, mocker):
        self._mock_claude(mocker, CompletionResult(
            success=False,
            error="Rate limit exceeded",
        ))

        with pytest.raises(RuntimeError, match="AI extraction failed"):
            await generate_bible_from_transcript(
                transcript="some transcript content here",
                vertical_name="Test",
                project_id="test-project-id",
                db=db_session,
            )

    @pytest.mark.asyncio
    async def test_unparseable_response_raises(self, db_session, mocker):
        self._mock_claude(mocker, CompletionResult(
            success=True,
            text="This is not JSON at all",
            input_tokens=100,
            output_tokens=50,
        ))

        with pytest.raises(RuntimeError, match="invalid response"):
            await generate_bible_from_transcript(
                transcript="some transcript content here",
                vertical_name="Test",
                project_id="test-project-id",
                db=db_session,
            )
