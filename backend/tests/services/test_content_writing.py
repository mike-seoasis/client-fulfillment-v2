"""Tests for content writing service: prompt builder and generate_content.

Tests cover:
- Prompt builder: with brief (includes LSI terms), without brief (fallback mode),
  brand config injection (ai_prompt_snippet, banned words)
- Content writing: successful generation stores PageContent, invalid JSON triggers retry,
  PromptLog records created
"""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.claude import CompletionResult
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.page_content import ContentStatus, PageContent
from app.models.project import Project
from app.models.prompt_log import PromptLog
from app.services.content_writing import (
    PromptPair,
    _apply_parsed_content,
    _build_blog_output_format_section,
    _build_entity_association_section,
    _build_freshness_section,
    _detect_content_type,
    _parse_content_json,
    build_blog_content_prompt,
    build_content_prompt,
    generate_content,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    """Create a test project."""
    project = Project(
        name="Content Writing Test",
        site_url="https://cw-test.example.com",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def crawled_page(db_session: AsyncSession, project: Project) -> CrawledPage:
    """Create a test crawled page."""
    page = CrawledPage(
        project_id=project.id,
        normalized_url="https://cw-test.example.com/boots",
        status="completed",
        title="Winter Boots Collection",
        meta_description="Shop winter boots",
        product_count=42,
    )
    db_session.add(page)
    await db_session.commit()
    # Set labels in-memory (JSONB defaults not supported in SQLite test env)
    page.labels = ["footwear", "winter"]
    # Pre-set relationship to avoid lazy-load MissingGreenlet in generate_content
    page.page_content = None  # type: ignore[assignment]
    return page


@pytest.fixture
def brand_config() -> dict[str, Any]:
    """Brand config with ai_prompt_snippet and vocabulary."""
    return {
        "ai_prompt_snippet": {
            "full_prompt": "Write in a warm, friendly tone. Focus on quality and durability."
        },
        "vocabulary": {
            "banned_words": ["cheap", "guarantee", "best"]
        },
    }


@pytest.fixture
def content_brief_with_lsi(crawled_page: CrawledPage) -> ContentBrief:
    """Create a ContentBrief with LSI terms."""
    brief = ContentBrief(
        page_id=crawled_page.id,
        keyword="winter boots",
        lsi_terms=[
            {"phrase": "snow boots", "weight": 85, "averageCount": 3.0, "targetCount": 4},
            {"phrase": "waterproof boots", "weight": 70, "averageCount": 2.0, "targetCount": 3},
        ],
        related_searches=["mens winter boots", "warm boots for women"],
        word_count_target=500,
    )
    return brief


@pytest.fixture
def content_brief_enriched(crawled_page: CrawledPage) -> ContentBrief:
    """Create a ContentBrief with full 3-step POP data including cleanedContentBrief."""
    brief = ContentBrief(
        page_id=crawled_page.id,
        keyword="winter boots",
        lsi_terms=[
            {"phrase": "snow boots", "weight": 85, "averageCount": 3.0, "targetCount": 4},
            {"phrase": "waterproof boots", "weight": 70, "averageCount": 2.0, "targetCount": 3},
        ],
        related_searches=["mens winter boots", "warm boots for women"],
        word_count_target=800,
        word_count_min=600,
        word_count_max=1200,
        competitors=[
            {"url": "https://comp1.com/boots", "pageScore": 80.0, "wordCount": 900, "h2Texts": [], "h3Texts": []},
            {"url": "https://comp2.com/boots", "pageScore": 70.0, "wordCount": 700, "h2Texts": [], "h3Texts": []},
        ],
        related_questions=[
            "What are the best winter boots?",
            "How to choose winter boots?",
            "Are winter boots waterproof?",
        ],
        heading_targets=[
            {"tag": "H1 Tag Total", "target": 1, "min": 1, "max": 1, "source": "recommendations"},
            {"tag": "H2 Tag Total", "target": 5, "min": 3, "max": 8, "source": "recommendations"},
            {"tag": "H3 Tag Total", "target": 8, "min": 4, "max": 12, "source": "recommendations"},
        ],
        keyword_targets=[
            {"signal": "Meta Title", "target": 1, "comment": "Include keyword in title", "type": "exact"},
            {"signal": "H1", "target": 1, "comment": "Use keyword in H1", "type": "exact"},
            {"signal": "Paragraph Text", "phrase": "winter boots", "target": 3, "type": "lsi"},
        ],
        page_score_target=85.0,
        raw_response={
            "cleanedContentBrief": {
                "title": [
                    {"term": {"type": "keyword", "phrase": "winter boots", "weight": 1}, "contentBrief": {"target": 1, "current": 0}},
                ],
                "titleTotal": {"min": 1, "max": 2, "current": 0},
                "subHeadings": [
                    {"term": {"type": "lsi", "phrase": "snow boots", "weight": 0.8}, "contentBrief": {"current": 0, "targetMin": 1, "targetMax": 2}},
                ],
                "subHeadingsTotal": {"min": 2, "max": 5, "current": 0},
                "p": [
                    {"term": {"type": "keyword", "phrase": "winter boots", "weight": 1}, "contentBrief": {"target": 3, "current": 0}},
                    {"term": {"type": "lsi", "phrase": "snow boots", "weight": 0.8}, "contentBrief": {"current": 0, "targetMin": 2, "targetMax": 4}},
                    {"term": {"type": "lsi", "phrase": "waterproof boots", "weight": 0.7}, "contentBrief": {"current": 0, "targetMin": 1, "targetMax": 3}},
                ],
                "pTotal": {"min": 10, "max": 25, "current": 0},
                "pageScore": {"pageScore": 85.0},
            },
            "relatedSearches": [
                {"query": "best winter boots 2026", "link": ""},
                {"query": "warm boots for cold weather", "link": ""},
            ],
        },
    )
    return brief


@pytest.fixture
def valid_json_response() -> str:
    """Valid JSON response from Claude."""
    return json.dumps({
        "page_title": "Winter Boots Collection | Shop Now",
        "meta_description": "Discover our curated winter boots collection for men and women.",
        "top_description": "Browse our selection of winter boots built for warmth and durability.",
        "bottom_description": "<h2>Why Choose Our Winter Boots</h2><p>High quality materials.</p>",
    })


# ---------------------------------------------------------------------------
# Prompt Builder: with brief
# ---------------------------------------------------------------------------


class TestBuildContentPromptWithBrief:
    """Tests for build_content_prompt when ContentBrief is provided."""

    def test_includes_lsi_terms(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_with_lsi: ContentBrief
    ) -> None:
        """User prompt includes LSI terms with weights when brief is provided."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_with_lsi)

        assert isinstance(result, PromptPair)
        assert "snow boots" in result.user_prompt
        assert "weight: 85" in result.user_prompt
        assert "waterproof boots" in result.user_prompt
        assert "target count: 2.0" in result.user_prompt

    def test_includes_variations(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_with_lsi: ContentBrief
    ) -> None:
        """User prompt includes keyword variations from brief."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_with_lsi)

        assert "mens winter boots" in result.user_prompt
        assert "warm boots for women" in result.user_prompt


# ---------------------------------------------------------------------------
# Prompt Builder: with enriched brief (3-step data)
# ---------------------------------------------------------------------------


class TestBuildContentPromptWithEnrichedBrief:
    """Tests for build_content_prompt when ContentBrief has 3-step data."""

    def test_includes_related_questions(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_enriched: ContentBrief
    ) -> None:
        """User prompt includes related questions for FAQ generation."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_enriched)
        assert "Related Questions" in result.user_prompt
        assert "What are the best winter boots?" in result.user_prompt
        assert "How to choose winter boots?" in result.user_prompt

    def test_includes_cleaned_brief_sections(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_enriched: ContentBrief
    ) -> None:
        """User prompt includes per-location term targets from cleanedContentBrief."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_enriched)
        assert "Title Tag Targets" in result.user_prompt
        assert "Subheading Targets" in result.user_prompt
        assert "Paragraph Text Targets" in result.user_prompt
        assert "snow boots" in result.user_prompt
        assert "waterproof boots" in result.user_prompt
        assert "Total term count" in result.user_prompt

    def test_includes_related_searches(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_enriched: ContentBrief
    ) -> None:
        """User prompt includes related searches from POP."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_enriched)
        assert "Related Searches" in result.user_prompt
        assert "best winter boots 2026" in result.user_prompt


    def test_includes_exact_keyword_placement(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_enriched: ContentBrief
    ) -> None:
        """User prompt includes exact keyword placement targets."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_enriched)
        assert "Exact Keyword Placement" in result.user_prompt
        assert "Meta Title" in result.user_prompt
        assert "Include keyword in title" in result.user_prompt

    def test_includes_heading_structure(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_enriched: ContentBrief
    ) -> None:
        """User prompt includes heading structure targets from pageStructure."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_enriched)
        assert "Heading Structure" in result.user_prompt
        assert "H2 Tag Total: 5" in result.user_prompt
        assert "H3 Tag Total: 8" in result.user_prompt

    def test_subheading_and_paragraph_targets_use_min(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_enriched: ContentBrief
    ) -> None:
        """Subheading and paragraph targets use min counts (floor of 1) for leaner content."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_enriched)

        # Subheading targets should use "at least N" format (from targetMin)
        assert "at least 1 time" in result.user_prompt
        # Paragraph targets: "winter boots" has target=3 (title format), but
        # "snow boots" has targetMin=2, "waterproof boots" has targetMin=1
        assert "at least 2 times" in result.user_prompt

    def test_includes_competitor_context(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_enriched: ContentBrief
    ) -> None:
        """User prompt includes competitor context summary."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_enriched)
        assert "Competitor Context" in result.user_prompt
        assert "2 competitors" in result.user_prompt


# ---------------------------------------------------------------------------
# Prompt Builder: without brief (fallback mode)
# ---------------------------------------------------------------------------


class TestBuildContentPromptWithoutBrief:
    """Tests for build_content_prompt when ContentBrief is None."""

    def test_fallback_no_lsi_terms(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """Without brief, prompt indicates LSI terms not available."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        assert "not available" in result.user_prompt.lower()
        assert "snow boots" not in result.user_prompt


# ---------------------------------------------------------------------------
# Prompt Builder: brand config injection
# ---------------------------------------------------------------------------


class TestBuildContentPromptBrandConfig:
    """Tests for brand config injection into prompts."""

    def test_system_prompt_includes_ai_snippet(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """System prompt includes ai_prompt_snippet.full_prompt and writing rules."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        assert "warm, friendly tone" in result.system_prompt
        assert "Brand Guidelines" in result.system_prompt
        # Skill bible sections
        assert "Writing Rules" in result.system_prompt
        assert "AI Writing Avoidance" in result.system_prompt
        assert "Benefits over features" in result.system_prompt

    def test_user_prompt_includes_banned_words(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """User prompt includes banned words from vocabulary."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        assert "cheap" in result.user_prompt
        assert "guarantee" in result.user_prompt
        assert "Banned Words" in result.user_prompt

    def test_no_brand_config_still_works(
        self, crawled_page: CrawledPage
    ) -> None:
        """Empty brand config produces valid prompts with writing rules but no brand sections."""
        result = build_content_prompt(crawled_page, "winter boots", {}, None)

        assert "SEO copywriter" in result.system_prompt
        # Writing rules still present even without brand config
        assert "Writing Rules" in result.system_prompt
        assert "AI Writing Avoidance" in result.system_prompt
        assert "## Task" in result.user_prompt
        # Brand Voice section should be omitted entirely
        assert "Banned Words" not in result.user_prompt
        # Brand Guidelines section should be omitted
        assert "Brand Guidelines" not in result.system_prompt

    def test_page_context_included(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """User prompt includes page context (URL, title, product count, labels)."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        assert "cw-test.example.com/boots" in result.user_prompt
        assert "Winter Boots Collection" in result.user_prompt
        assert "42" in result.user_prompt
        assert "footwear" in result.user_prompt


# ---------------------------------------------------------------------------
# Prompt Builder: dynamic output format
# ---------------------------------------------------------------------------


class TestBuildContentPromptOutputFormat:
    """Tests for dynamic output format template from POP heading data."""

    def test_output_format_has_dynamic_template(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_enriched: ContentBrief
    ) -> None:
        """With enriched brief, output format uses POP heading min counts."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_enriched)

        # Uses min heading counts from POP (min=3 for H2, min=4 for H3)
        assert "3 H2 sections" in result.user_prompt
        assert "4 H3 subsections" in result.user_prompt
        # No word count target — length is driven by structure
        assert "words)" not in result.user_prompt
        # 120-word max per paragraph
        assert "120 words max" in result.user_prompt
        # Brevity instruction
        assert "Brevity is valued" in result.user_prompt
        # Formatting rules from bible
        assert "Title Case" in result.user_prompt
        assert "Max 7 Words" in result.user_prompt

    def test_output_format_fallback_without_brief(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """Without brief, output format uses sensible default structure."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        # Default heading counts
        assert "3 H2 sections" in result.user_prompt
        assert "4 H3 subsections" in result.user_prompt
        # No word count target
        assert "words)" not in result.user_prompt
        # Formatting rules always present
        assert "Title Case" in result.user_prompt
        assert "Max 7 Words" in result.user_prompt

    def test_output_format_page_title_spec(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """Output format includes enriched page_title spec."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        assert "benefit-driven" in result.user_prompt
        assert "under 60 chars" in result.user_prompt

    def test_output_format_meta_description_spec(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """Output format includes enriched meta_description spec."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        assert "150-160 chars" in result.user_prompt
        assert "CTA" in result.user_prompt

    def test_output_format_semantic_html_rules(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """Output format includes semantic HTML rules."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        assert "semantic HTML only" in result.user_prompt
        assert "No inline styles" in result.user_prompt
        assert "No div wrappers" in result.user_prompt



# ---------------------------------------------------------------------------
# _parse_content_json tests
# ---------------------------------------------------------------------------


class TestParseContentJson:
    """Tests for JSON parsing with various response formats."""

    def test_parses_valid_json(self) -> None:
        text = json.dumps({
            "page_title": "Title",
            "meta_description": "Meta",
            "top_description": "Top",
            "bottom_description": "Bottom",
        })
        result = _parse_content_json(text)
        assert result is not None
        assert result["page_title"] == "Title"

    def test_strips_markdown_fences(self) -> None:
        text = '```json\n{"page_title":"T","meta_description":"M","top_description":"Tp","bottom_description":"B"}\n```'
        result = _parse_content_json(text)
        assert result is not None
        assert result["page_title"] == "T"

    def test_extracts_json_from_surrounding_text(self) -> None:
        text = 'Here is the content:\n{"page_title":"T","meta_description":"M","top_description":"Tp","bottom_description":"B"}\nDone!'
        result = _parse_content_json(text)
        assert result is not None

    def test_returns_none_for_invalid_json(self) -> None:
        assert _parse_content_json("not json at all") is None

    def test_returns_none_for_missing_keys(self) -> None:
        text = json.dumps({"page_title": "T", "meta_description": "M"})
        assert _parse_content_json(text) is None

    def test_returns_none_for_non_dict(self) -> None:
        assert _parse_content_json("[1, 2, 3]") is None


# ---------------------------------------------------------------------------
# _apply_parsed_content tests
# ---------------------------------------------------------------------------


class TestApplyParsedContent:
    """Tests for applying parsed content to PageContent."""

    def test_sets_fields_and_word_count(self) -> None:
        pc = PageContent(crawled_page_id="test-id")
        parsed = {
            "page_title": "Test Title",
            "meta_description": "Short description here",
            "top_description": "A brief intro sentence.",
            "bottom_description": "<h2>Heading</h2><p>Three words here.</p>",
        }
        _apply_parsed_content(pc, parsed)

        assert pc.page_title == "Test Title"
        assert pc.meta_description == "Short description here"
        assert pc.top_description == "A brief intro sentence."
        assert pc.bottom_description == "<h2>Heading</h2><p>Three words here.</p>"
        assert pc.word_count is not None
        assert pc.word_count > 0


# ---------------------------------------------------------------------------
# generate_content tests (async, requires db)
# ---------------------------------------------------------------------------


class TestGenerateContent:
    """Tests for generate_content service function."""

    @pytest.mark.asyncio
    async def test_successful_generation_stores_page_content(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        valid_json_response: str,
    ) -> None:
        """Successful generation creates PageContent with correct fields."""
        mock_result = CompletionResult(
            success=True,
            text=valid_json_response,
            input_tokens=1000,
            output_tokens=500,
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.complete = AsyncMock(return_value=mock_result)
        mock_client_instance.close = AsyncMock()

        with patch("app.services.content_writing.ClaudeClient", return_value=mock_client_instance):
            result = await generate_content(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=None,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.success is True
        assert result.page_content is not None
        pc = result.page_content
        assert pc.page_title == "Winter Boots Collection | Shop Now"
        assert pc.meta_description is not None
        assert pc.status == ContentStatus.COMPLETE.value
        assert pc.generation_started_at is not None
        assert pc.generation_completed_at is not None
        assert pc.word_count is not None
        assert pc.word_count > 0

    @pytest.mark.asyncio
    async def test_prompt_logs_created(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        valid_json_response: str,
    ) -> None:
        """PromptLog records are created for system and user prompts."""
        mock_result = CompletionResult(
            success=True,
            text=valid_json_response,
            input_tokens=1000,
            output_tokens=500,
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.complete = AsyncMock(return_value=mock_result)
        mock_client_instance.close = AsyncMock()

        with patch("app.services.content_writing.ClaudeClient", return_value=mock_client_instance):
            result = await generate_content(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=None,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.success is True
        assert result.page_content is not None

        # Check PromptLog records were created
        from sqlalchemy import select
        logs_stmt = select(PromptLog).where(
            PromptLog.page_content_id == result.page_content.id
        )
        logs_result = await db_session.execute(logs_stmt)
        logs = logs_result.scalars().all()

        assert len(logs) == 2
        roles = {log.role for log in logs}
        assert "system" in roles
        assert "user" in roles

        # Both logs should have response metadata
        for log in logs:
            assert log.step == "content_writing"
            assert log.input_tokens == 1000
            assert log.output_tokens == 500
            assert log.model is not None

        # Only the user log should have response_text (avoids duplication in inspector)
        system_log = next(l for l in logs if l.role == "system")
        user_log = next(l for l in logs if l.role == "user")
        assert system_log.response_text is None
        assert user_log.response_text is not None

    @pytest.mark.asyncio
    async def test_invalid_json_triggers_retry(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        valid_json_response: str,
    ) -> None:
        """Invalid JSON on first attempt triggers retry with strict prompt."""
        # First call returns invalid JSON, retry returns valid
        invalid_result = CompletionResult(
            success=True,
            text="Not valid JSON at all",
            input_tokens=800,
            output_tokens=400,
        )
        valid_result = CompletionResult(
            success=True,
            text=valid_json_response,
            input_tokens=900,
            output_tokens=450,
        )

        # First ClaudeClient for initial call
        mock_client_1 = AsyncMock()
        mock_client_1.complete = AsyncMock(return_value=invalid_result)
        mock_client_1.close = AsyncMock()

        # Second ClaudeClient for retry
        mock_client_2 = AsyncMock()
        mock_client_2.complete = AsyncMock(return_value=valid_result)
        mock_client_2.close = AsyncMock()

        call_count = 0

        def client_factory(*args: Any, **kwargs: Any) -> AsyncMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_client_1
            return mock_client_2

        with patch("app.services.content_writing.ClaudeClient", side_effect=client_factory):
            result = await generate_content(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=None,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.success is True
        assert result.page_content is not None
        assert result.page_content.status == ContentStatus.COMPLETE.value

        # Should have created 4 PromptLog records (2 for initial + 2 for retry)
        from sqlalchemy import select
        logs_stmt = select(PromptLog).where(
            PromptLog.page_content_id == result.page_content.id
        )
        logs_result = await db_session.execute(logs_stmt)
        logs = logs_result.scalars().all()
        assert len(logs) == 4

        # Retry logs should have step "content_writing_retry"
        retry_logs = [l for l in logs if l.step == "content_writing_retry"]
        assert len(retry_logs) == 2

    @pytest.mark.asyncio
    async def test_claude_api_error_marks_failed(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
    ) -> None:
        """Claude API error marks PageContent as failed."""
        error_result = CompletionResult(
            success=False,
            error="Rate limit exceeded",
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.complete = AsyncMock(return_value=error_result)
        mock_client_instance.close = AsyncMock()

        with patch("app.services.content_writing.ClaudeClient", return_value=mock_client_instance):
            result = await generate_content(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=None,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.success is False
        assert result.error is not None
        assert "Rate limit" in result.error
        assert result.page_content is not None
        assert result.page_content.status == ContentStatus.FAILED.value
        assert result.page_content.qa_results is not None
        assert "error" in result.page_content.qa_results

    @pytest.mark.asyncio
    async def test_claude_exception_marks_failed(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
    ) -> None:
        """Claude client raising exception marks PageContent as failed."""
        mock_client_instance = AsyncMock()
        mock_client_instance.complete = AsyncMock(side_effect=RuntimeError("Connection reset"))
        mock_client_instance.close = AsyncMock()

        with patch("app.services.content_writing.ClaudeClient", return_value=mock_client_instance):
            result = await generate_content(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=None,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.success is False
        assert result.page_content is not None
        assert result.page_content.status == ContentStatus.FAILED.value


# ---------------------------------------------------------------------------
# Blog prompt: direct-answer-first instructions (Step 1)
# ---------------------------------------------------------------------------


class TestBlogPromptDirectAnswer:
    """Tests for direct-answer-first instructions in blog prompts."""

    def test_blog_prompt_includes_direct_answer_instruction(self) -> None:
        """Blog output format includes direct answer instruction in Introduction."""
        result = _build_blog_output_format_section(None, keyword="how to clean boots")
        assert "direct answer" in result.lower()
        assert "AI systems extract" in result

    def test_blog_prompt_includes_question_based_headings(self) -> None:
        """Blog output format instructs question-based H2 headings."""
        result = _build_blog_output_format_section(None, keyword="boot care guide")
        assert "question-based H2 headings" in result


# ---------------------------------------------------------------------------
# Blog prompt: entity association (Step 2)
# ---------------------------------------------------------------------------


class TestBlogPromptEntityAssociation:
    """Tests for entity association injection in blog prompts."""

    def test_entity_association_with_full_config(self) -> None:
        """Entity association section includes company + products + location."""
        config: dict[str, Any] = {
            "brand_foundation": {
                "company_overview": {
                    "company_name": "BootCo",
                    "location": "Portland, OR",
                },
                "what_they_sell": {
                    "primary_products_services": "premium leather boots",
                },
            },
        }
        result = _build_entity_association_section(config)
        assert result is not None
        assert "BootCo" in result
        assert "premium leather boots" in result
        assert "Portland, OR" in result
        assert "Brand Positioning" in result

    def test_entity_association_without_location(self) -> None:
        """Entity association works without location."""
        config: dict[str, Any] = {
            "brand_foundation": {
                "company_overview": {"company_name": "BootCo"},
                "what_they_sell": {"primary_products_services": "boots"},
            },
        }
        result = _build_entity_association_section(config)
        assert result is not None
        assert "BootCo" in result

    def test_entity_association_returns_none_without_brand(self) -> None:
        """Returns None when no brand foundation is configured."""
        result = _build_entity_association_section({})
        assert result is None

    def test_entity_association_in_blog_prompt(self) -> None:
        """Entity association appears in the full blog user prompt."""
        from app.models.blog import BlogPost as BP

        fake_post = MagicMock(spec=BP)
        fake_post.primary_keyword = "boot care"
        fake_post.url_slug = "boot-care"
        fake_post.search_volume = 500

        config: dict[str, Any] = {
            "brand_foundation": {
                "company_overview": {"company_name": "BootCo"},
                "what_they_sell": {"primary_products_services": "leather boots"},
            },
        }
        result = build_blog_content_prompt(fake_post, "boot care", config, None)
        assert "Brand Positioning" in result.user_prompt
        assert "BootCo" in result.user_prompt


# ---------------------------------------------------------------------------
# Blog prompt: freshness section (Step 4)
# ---------------------------------------------------------------------------


class TestBlogPromptFreshness:
    """Tests for freshness/trend section in blog prompts."""

    def test_freshness_section_with_trends(self) -> None:
        """Freshness section renders trend data and citations."""
        trend_ctx = {
            "trends": "Boot conditioning increased 20% in 2026.",
            "citations": ["https://example.com/trends"],
            "fetched_at": "2026-02-15T00:00:00",
        }
        result = _build_freshness_section(trend_ctx)
        assert result is not None
        assert "Recent Trends" in result
        assert "Boot conditioning" in result
        assert "https://example.com/trends" in result
        assert "current year" in result.lower()

    def test_freshness_section_returns_none_without_context(self) -> None:
        """Returns None when no trend context."""
        assert _build_freshness_section(None) is None
        assert _build_freshness_section({}) is None

    def test_freshness_section_in_blog_prompt(self) -> None:
        """Freshness section appears in full blog prompt when trend_context provided."""
        from app.models.blog import BlogPost as BP

        fake_post = MagicMock(spec=BP)
        fake_post.primary_keyword = "boot care"
        fake_post.url_slug = "boot-care"
        fake_post.search_volume = 500

        trend_ctx = {
            "trends": "Leather care is trending.",
            "citations": [],
            "fetched_at": "2026-02-15T00:00:00",
        }
        result = build_blog_content_prompt(
            fake_post, "boot care", {}, None, trend_context=trend_ctx,
        )
        assert "Recent Trends" in result.user_prompt
        assert "Leather care is trending" in result.user_prompt


# ---------------------------------------------------------------------------
# Content type detection (Step 6)
# ---------------------------------------------------------------------------


class TestDetectContentType:
    """Tests for keyword-based content type detection."""

    def test_how_to(self) -> None:
        assert _detect_content_type("how to clean leather boots") == "how-to"

    def test_how_do(self) -> None:
        assert _detect_content_type("how do you waterproof boots") == "how-to"

    def test_best_comparison(self) -> None:
        assert _detect_content_type("best hiking boots for beginners") == "comparison"

    def test_vs_comparison(self) -> None:
        assert _detect_content_type("timberland vs red wing") == "comparison"

    def test_what_is_explainer(self) -> None:
        assert _detect_content_type("what is goodyear welt") == "explainer"

    def test_guide(self) -> None:
        assert _detect_content_type("winter boots buying guide") == "guide"

    def test_review(self) -> None:
        assert _detect_content_type("red wing iron ranger review") == "review"

    def test_default_to_guide(self) -> None:
        assert _detect_content_type("leather boots care") == "guide"


class TestBlogOutputFormatContentType:
    """Tests for content-type-adapted output format."""

    def test_how_to_format(self) -> None:
        """How-to keyword produces numbered steps instruction."""
        result = _build_blog_output_format_section(None, keyword="how to clean boots")
        assert "Content Type: How-To" in result
        assert "numbered steps" in result

    def test_comparison_format(self) -> None:
        """Comparison keyword produces comparison table instruction."""
        result = _build_blog_output_format_section(None, keyword="best boots vs shoes")
        assert "Content Type: Comparison" in result
        assert "comparison table" in result

    def test_explainer_format(self) -> None:
        """Explainer keyword produces progressive understanding instruction."""
        result = _build_blog_output_format_section(None, keyword="what is goodyear welt")
        assert "Content Type: Explainer" in result
        assert "core concept" in result

    def test_review_format(self) -> None:
        """Review keyword produces pros/cons instruction."""
        result = _build_blog_output_format_section(None, keyword="red wing review")
        assert "Content Type: Review" in result
        assert "pros/cons" in result

    def test_guide_no_extra_section(self) -> None:
        """Guide (default) type doesn't add an extra Content Type section."""
        result = _build_blog_output_format_section(None, keyword="boot care guide")
        assert "Content Type:" not in result
