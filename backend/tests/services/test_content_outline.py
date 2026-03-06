"""Tests for content outline service: generate_outline and generate_content_from_outline.

Tests cover:
- generate_outline: builds correct prompts, stores outline_json, sets statuses,
  creates PromptLog records, handles Claude API errors
- generate_content_from_outline: produces standard 4 content fields, includes
  outline in prompt, creates PromptLog records, handles missing outline
"""

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.claude import CompletionResult
from app.models.content_brief import ContentBrief
from app.models.crawled_page import CrawledPage
from app.models.page_content import ContentStatus, PageContent
from app.models.project import Project
from app.models.prompt_log import PromptLog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    """Create a test project."""
    project = Project(
        name="Outline Test",
        site_url="https://outline-test.example.com",
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
        normalized_url="https://outline-test.example.com/boots",
        status="completed",
        title="Winter Boots Collection",
        meta_description="Shop winter boots",
        product_count=42,
    )
    db_session.add(page)
    await db_session.commit()
    page.labels = ["footwear", "winter"]
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
def content_brief(crawled_page: CrawledPage) -> ContentBrief:
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
def valid_outline_json() -> dict[str, Any]:
    """Valid outline JSON structure matching _parse_outline_json expectations."""
    return {
        "page_name": "Winter Boots Collection",
        "primary_keyword": "winter boots",
        "secondary_keywords": ["snow boots", "cold weather boots"],
        "date": "2026-03-02",
        "audience": "Shoppers looking for quality winter footwear.",
        "keyword_reference": {
            "lsi_terms": [{"term": "snow boots", "target_count": 3}],
            "keyword_variations": [{"variation": "cold weather boots", "verbatim_required": True}],
        },
        "people_also_ask": ["What are the warmest winter boots?"],
        "top_ranked_results": [{"url": "https://comp.com/boots", "title": "Competitor", "word_count": 1200}],
        "page_progression": [
            {"order": 1, "question_answered": "Why choose our boots?", "label": "why-choose", "tag": "h2", "headline": "Why Choose Our Winter Boots"},
            {"order": 2, "question_answered": "What styles are available?", "label": "shop-style", "tag": "h2", "headline": "Shop By Style"},
        ],
        "section_details": [
            {
                "label": "why-choose",
                "tag": "h2",
                "headline": "Why Choose Our Winter Boots",
                "purpose": "Convince visitors of product quality",
                "key_points": [
                    "Premium materials for lasting warmth",
                    "Waterproof construction keeps feet dry",
                ],
                "client_notes": "",
            },
            {
                "label": "shop-style",
                "tag": "h2",
                "headline": "Shop By Style",
                "purpose": "Help visitors find what they need",
                "key_points": ["Hiking boots", "Casual winter boots", "Dress boots"],
                "client_notes": "",
            },
        ],
    }


@pytest.fixture
def valid_content_response() -> str:
    """Valid JSON response from Claude for content generation."""
    return json.dumps({
        "page_title": "Winter Boots Collection | Shop Now",
        "meta_description": "Discover our curated winter boots collection for men and women.",
        "top_description": "Browse our selection of winter boots built for warmth and durability.",
        "bottom_description": "<h2>Why Choose Our Winter Boots</h2><p>High quality materials.</p>",
    })


# ---------------------------------------------------------------------------
# generate_outline tests
# ---------------------------------------------------------------------------


class TestGenerateOutline:
    """Tests for generate_outline service function."""

    @pytest.mark.asyncio
    async def test_stores_outline_json(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_outline_json: dict,
    ) -> None:
        """Successful outline generation stores outline_json on PageContent."""
        mock_result = CompletionResult(
            success=True,
            text=json.dumps(valid_outline_json),
            input_tokens=800,
            output_tokens=400,
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_outline

            result = await generate_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.success is True
        assert result.page_content is not None
        pc = result.page_content
        assert pc.outline_json is not None
        assert "section_details" in pc.outline_json
        assert "page_name" in pc.outline_json

    @pytest.mark.asyncio
    async def test_sets_outline_status_draft(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_outline_json: dict,
    ) -> None:
        """Successful outline generation sets outline_status to 'draft'."""
        mock_result = CompletionResult(
            success=True,
            text=json.dumps(valid_outline_json),
            input_tokens=800,
            output_tokens=400,
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_outline

            result = await generate_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.page_content is not None
        assert result.page_content.outline_status == "draft"

    @pytest.mark.asyncio
    async def test_sets_content_status_complete(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_outline_json: dict,
    ) -> None:
        """Successful outline generation sets PageContent status to 'complete'."""
        mock_result = CompletionResult(
            success=True,
            text=json.dumps(valid_outline_json),
            input_tokens=800,
            output_tokens=400,
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_outline

            result = await generate_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.page_content is not None
        assert result.page_content.status == ContentStatus.COMPLETE.value

    @pytest.mark.asyncio
    async def test_creates_prompt_logs(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_outline_json: dict,
    ) -> None:
        """PromptLog records are created with step='write_outline'."""
        mock_result = CompletionResult(
            success=True,
            text=json.dumps(valid_outline_json),
            input_tokens=800,
            output_tokens=400,
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_outline

            result = await generate_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.success is True
        assert result.page_content is not None

        from sqlalchemy import select

        logs_stmt = select(PromptLog).where(
            PromptLog.page_content_id == result.page_content.id
        )
        logs_result = await db_session.execute(logs_stmt)
        logs = logs_result.scalars().all()

        assert len(logs) >= 1
        steps = {log.step for log in logs}
        assert "write_outline" in steps

        for log in logs:
            if log.step == "write_outline":
                assert log.input_tokens == 800
                assert log.output_tokens == 400

    @pytest.mark.asyncio
    async def test_claude_api_error_marks_failed(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
    ) -> None:
        """Claude API error returns failure result."""
        error_result = CompletionResult(
            success=False,
            error="Rate limit exceeded",
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=error_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_outline

            result = await generate_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
            )

        assert result.success is False
        assert result.error is not None
        assert "Rate limit" in result.error

    @pytest.mark.asyncio
    async def test_builds_system_and_user_prompts(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_outline_json: dict,
    ) -> None:
        """Claude client is called with system and user prompts."""
        mock_result = CompletionResult(
            success=True,
            text=json.dumps(valid_outline_json),
            input_tokens=800,
            output_tokens=400,
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_outline

            await generate_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
            )

        # Verify Claude was called with both system and user prompts
        mock_client.complete.assert_called_once()
        call_kwargs = mock_client.complete.call_args
        assert call_kwargs.kwargs.get("system_prompt") or (
            len(call_kwargs.args) >= 2 and call_kwargs.args[1]
        )
        user_prompt = call_kwargs.kwargs.get("user_prompt") or call_kwargs.args[0]
        assert "winter boots" in user_prompt


# ---------------------------------------------------------------------------
# generate_content_from_outline tests
# ---------------------------------------------------------------------------


class TestGenerateContentFromOutline:
    """Tests for generate_content_from_outline service function."""

    @pytest.mark.asyncio
    async def test_produces_standard_content_fields(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_outline_json: dict,
        valid_content_response: str,
    ) -> None:
        """Generates standard 4 content fields from approved outline."""
        mock_result = CompletionResult(
            success=True,
            text=valid_content_response,
            input_tokens=1200,
            output_tokens=600,
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_content_from_outline

            result = await generate_content_from_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
                outline_json=valid_outline_json,
            )

        assert result.success is True
        assert result.page_content is not None
        pc = result.page_content
        assert pc.page_title == "Winter Boots Collection | Shop Now"
        assert pc.meta_description is not None
        assert pc.top_description is not None
        assert pc.bottom_description is not None

    @pytest.mark.asyncio
    async def test_creates_prompt_logs_with_correct_step(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_outline_json: dict,
        valid_content_response: str,
    ) -> None:
        """PromptLog records are created with step='write_from_outline'."""
        mock_result = CompletionResult(
            success=True,
            text=valid_content_response,
            input_tokens=1200,
            output_tokens=600,
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_content_from_outline

            result = await generate_content_from_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
                outline_json=valid_outline_json,
            )

        assert result.success is True
        assert result.page_content is not None

        from sqlalchemy import select

        logs_stmt = select(PromptLog).where(
            PromptLog.page_content_id == result.page_content.id
        )
        logs_result = await db_session.execute(logs_stmt)
        logs = logs_result.scalars().all()

        assert len(logs) >= 1
        steps = {log.step for log in logs}
        assert "write_from_outline" in steps

    @pytest.mark.asyncio
    async def test_includes_outline_in_prompt(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_outline_json: dict,
        valid_content_response: str,
    ) -> None:
        """User prompt includes the outline structure."""
        mock_result = CompletionResult(
            success=True,
            text=valid_content_response,
            input_tokens=1200,
            output_tokens=600,
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_content_from_outline

            await generate_content_from_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
                outline_json=valid_outline_json,
            )

        mock_client.complete.assert_called_once()
        call_kwargs = mock_client.complete.call_args
        user_prompt = call_kwargs.kwargs.get("user_prompt") or call_kwargs.args[0]
        # The outline content should be embedded in the prompt
        assert "Why Choose Our Winter Boots" in user_prompt or "outline" in user_prompt.lower()

    @pytest.mark.asyncio
    async def test_handles_claude_error(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_outline_json: dict,
    ) -> None:
        """Claude API error returns failure result."""
        error_result = CompletionResult(
            success=False,
            error="Server error (500)",
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=error_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_content_from_outline

            result = await generate_content_from_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
                outline_json=valid_outline_json,
            )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_handles_empty_outline(
        self,
        db_session: AsyncSession,
        crawled_page: CrawledPage,
        brand_config: dict,
        content_brief: ContentBrief,
        valid_content_response: str,
    ) -> None:
        """Passing an empty dict outline still produces a prompt and calls Claude."""
        mock_result = CompletionResult(
            success=True,
            text=valid_content_response,
            input_tokens=1200,
            output_tokens=600,
        )

        mock_client = AsyncMock()
        mock_client.complete = AsyncMock(return_value=mock_result)
        mock_client.close = AsyncMock()

        with patch(
            "app.services.content_outline.ClaudeClient",
            return_value=mock_client,
        ), patch(
            "app.services.content_outline.get_api_key",
            return_value="test-api-key",
        ):
            from app.services.content_outline import generate_content_from_outline

            result = await generate_content_from_outline(
                db=db_session,
                crawled_page=crawled_page,
                content_brief=content_brief,
                brand_config=brand_config,
                keyword="winter boots",
                outline_json={},
            )

        # Even with empty outline, Claude is called and content parsed
        assert result.success is True
        mock_client.complete.assert_called_once()
