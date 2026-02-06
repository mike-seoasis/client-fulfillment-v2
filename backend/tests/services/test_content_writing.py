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
    _parse_content_json,
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
        assert "target count: 3" in result.user_prompt

    def test_includes_variations(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_with_lsi: ContentBrief
    ) -> None:
        """User prompt includes keyword variations from brief."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_with_lsi)

        assert "mens winter boots" in result.user_prompt
        assert "warm boots for women" in result.user_prompt

    def test_includes_word_count_target(
        self, crawled_page: CrawledPage, brand_config: dict, content_brief_with_lsi: ContentBrief
    ) -> None:
        """User prompt includes word count target from brief."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, content_brief_with_lsi)

        assert "~500 words" in result.user_prompt


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

    def test_fallback_default_word_count(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """Without brief, prompt uses default 300-400 word count target."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        assert "300-400 words" in result.user_prompt


# ---------------------------------------------------------------------------
# Prompt Builder: brand config injection
# ---------------------------------------------------------------------------


class TestBuildContentPromptBrandConfig:
    """Tests for brand config injection into prompts."""

    def test_system_prompt_includes_ai_snippet(
        self, crawled_page: CrawledPage, brand_config: dict
    ) -> None:
        """System prompt includes ai_prompt_snippet.full_prompt."""
        result = build_content_prompt(crawled_page, "winter boots", brand_config, None)

        assert "warm, friendly tone" in result.system_prompt
        assert "Brand Guidelines" in result.system_prompt

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
        """Empty brand config produces valid prompts without brand sections."""
        result = build_content_prompt(crawled_page, "winter boots", {}, None)

        assert "SEO copywriter" in result.system_prompt
        assert "## Task" in result.user_prompt
        # Brand Voice section should be omitted entirely
        assert "Banned Words" not in result.user_prompt

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

        # Logs should have response metadata
        for log in logs:
            assert log.step == "content_writing"
            assert log.response_text is not None
            assert log.input_tokens == 1000
            assert log.output_tokens == 500
            assert log.model is not None

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
