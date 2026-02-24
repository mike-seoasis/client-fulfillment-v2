"""Tests for ContentPlan service.

Tests cover:
- Exception classes
- Data classes (Benefit, PriorityQuestion, ContentPlanResult)
- ContentPlanService initialization and methods
- Benefits parsing (JSON and fallback)
- PAA to priority questions conversion
- Singleton and convenience functions
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.services.content_plan import (
    Benefit,
    PriorityQuestion,
    ContentPlanResult,
    ContentPlanService,
    ContentPlanServiceError,
    ContentPlanValidationError,
    get_content_plan_service,
    build_content_plan,
    _build_benefits_prompt,
    DEFAULT_MAX_BENEFITS,
    DEFAULT_MAX_PRIORITY_QUESTIONS,
)


# =============================================================================
# EXCEPTION TESTS
# =============================================================================


class TestContentPlanServiceError:
    """Tests for ContentPlanServiceError."""

    def test_base_exception_creation(self):
        """Test creating base exception."""
        error = ContentPlanServiceError("Test error")
        assert str(error) == "Test error"

    def test_exception_with_project_page_ids(self):
        """Test exception with project and page IDs."""
        error = ContentPlanServiceError(
            "Test error",
            project_id="proj-123",
            page_id="page-456",
        )
        assert error.project_id == "proj-123"
        assert error.page_id == "page-456"

    def test_exception_inheritance(self):
        """Test exception inherits from Exception."""
        error = ContentPlanServiceError("Test")
        assert isinstance(error, Exception)


class TestContentPlanValidationError:
    """Tests for ContentPlanValidationError."""

    def test_validation_error_attributes(self):
        """Test validation error has correct attributes."""
        error = ContentPlanValidationError(
            "keyword",
            "test_value",
            "cannot be empty",
            project_id="proj-123",
            page_id="page-456",
        )
        assert error.field_name == "keyword"
        assert error.value == "test_value"
        assert error.project_id == "proj-123"
        assert error.page_id == "page-456"
        assert "keyword" in str(error)
        assert "cannot be empty" in str(error)

    def test_validation_error_inheritance(self):
        """Test validation error inherits from service error."""
        error = ContentPlanValidationError("field", "val", "msg")
        assert isinstance(error, ContentPlanServiceError)


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestBenefit:
    """Tests for Benefit dataclass."""

    def test_default_values(self):
        """Test default benefit values."""
        benefit = Benefit(benefit="Test benefit")
        assert benefit.benefit == "Test benefit"
        assert benefit.source is None
        assert benefit.confidence == 1.0

    def test_custom_values(self):
        """Test benefit with custom values."""
        benefit = Benefit(
            benefit="Improves efficiency",
            source="https://example.com",
            confidence=0.85,
        )
        assert benefit.benefit == "Improves efficiency"
        assert benefit.source == "https://example.com"
        assert benefit.confidence == 0.85

    def test_to_dict(self):
        """Test conversion to dictionary."""
        benefit = Benefit(
            benefit="Test benefit",
            source="research",
            confidence=0.756,
        )
        result = benefit.to_dict()
        assert result["benefit"] == "Test benefit"
        assert result["source"] == "research"
        assert result["confidence"] == 0.76  # Rounded to 2 decimal places


class TestPriorityQuestion:
    """Tests for PriorityQuestion dataclass."""

    def test_default_values(self):
        """Test default priority question values."""
        question = PriorityQuestion(
            question="What is test?",
            intent="informational",
            priority_rank=1,
        )
        assert question.question == "What is test?"
        assert question.intent == "informational"
        assert question.priority_rank == 1
        assert question.answer_snippet is None
        assert question.source_url is None

    def test_custom_values(self):
        """Test priority question with custom values."""
        question = PriorityQuestion(
            question="How to do test?",
            intent="navigational",
            priority_rank=2,
            answer_snippet="Here is how...",
            source_url="https://example.com",
        )
        assert question.question == "How to do test?"
        assert question.intent == "navigational"
        assert question.priority_rank == 2
        assert question.answer_snippet == "Here is how..."
        assert question.source_url == "https://example.com"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        question = PriorityQuestion(
            question="What is test?",
            intent="informational",
            priority_rank=1,
            answer_snippet="Test answer",
            source_url="https://test.com",
        )
        result = question.to_dict()
        assert result["question"] == "What is test?"
        assert result["intent"] == "informational"
        assert result["priority_rank"] == 1
        assert result["answer_snippet"] == "Test answer"
        assert result["source_url"] == "https://test.com"


class TestContentPlanResult:
    """Tests for ContentPlanResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = ContentPlanResult(success=True, keyword="test")
        assert result.success is True
        assert result.keyword == "test"
        assert result.main_angle is None
        assert result.benefits == []
        assert result.priority_questions == []
        assert result.intent_distribution == {}
        assert result.total_questions_analyzed == 0
        assert result.perplexity_used is False
        assert result.perplexity_citations == []
        assert result.error is None
        assert result.partial_success is False
        assert result.duration_ms == 0.0
        assert result.project_id is None
        assert result.page_id is None

    def test_custom_values(self):
        """Test result with custom values."""
        benefit = Benefit(benefit="Test benefit")
        question = PriorityQuestion(
            question="Test?",
            intent="informational",
            priority_rank=1,
        )
        result = ContentPlanResult(
            success=True,
            keyword="hiking boots",
            benefits=[benefit],
            priority_questions=[question],
            intent_distribution={"informational": 0.6, "transactional": 0.4},
            total_questions_analyzed=10,
            perplexity_used=True,
            perplexity_citations=["https://example.com"],
            duration_ms=1500.5,
            project_id="proj-123",
            page_id="page-456",
        )
        assert result.success is True
        assert result.keyword == "hiking boots"
        assert len(result.benefits) == 1
        assert len(result.priority_questions) == 1
        assert result.perplexity_used is True
        assert result.project_id == "proj-123"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ContentPlanResult(
            success=True,
            keyword="test",
            benefits=[Benefit(benefit="Test benefit")],
            priority_questions=[
                PriorityQuestion(
                    question="Test?",
                    intent="informational",
                    priority_rank=1,
                )
            ],
            duration_ms=100.567,
        )
        dict_result = result.to_dict()
        assert dict_result["success"] is True
        assert dict_result["keyword"] == "test"
        assert len(dict_result["benefits"]) == 1
        assert len(dict_result["priority_questions"]) == 1
        assert dict_result["duration_ms"] == 100.57  # Rounded

    def test_to_dict_with_main_angle(self):
        """Test to_dict includes main_angle when present."""
        # Mock ContentAngleRecommendation
        mock_angle = MagicMock()
        mock_angle.to_dict.return_value = {"primary_angle": "how-to"}

        result = ContentPlanResult(
            success=True,
            keyword="test",
            main_angle=mock_angle,
        )
        dict_result = result.to_dict()
        assert dict_result["main_angle"] == {"primary_angle": "how-to"}


# =============================================================================
# SERVICE TESTS
# =============================================================================


class TestContentPlanService:
    """Tests for ContentPlanService."""

    def test_initialization_defaults(self):
        """Test service initialization with defaults."""
        service = ContentPlanService()
        assert service._max_benefits == DEFAULT_MAX_BENEFITS
        assert service._max_priority_questions == DEFAULT_MAX_PRIORITY_QUESTIONS

    def test_initialization_custom(self):
        """Test service initialization with custom values."""
        service = ContentPlanService(max_benefits=10, max_priority_questions=8)
        assert service._max_benefits == 10
        assert service._max_priority_questions == 8

    def test_parse_benefits_response_json_array(self):
        """Test parsing valid JSON array response."""
        service = ContentPlanService()
        response = '["Benefit 1", "Benefit 2", "Benefit 3"]'
        citations = ["https://source1.com", "https://source2.com"]

        benefits = service._parse_benefits_response(
            response, citations, None, None
        )

        assert len(benefits) == 3
        assert benefits[0].benefit == "Benefit 1"
        assert benefits[0].source == "https://source1.com"
        assert benefits[1].source == "https://source2.com"
        assert benefits[2].source == "research"  # No citation for 3rd

    def test_parse_benefits_response_with_markdown_code_block(self):
        """Test parsing JSON within markdown code block."""
        service = ContentPlanService()
        response = '```json\n["Benefit 1", "Benefit 2"]\n```'

        benefits = service._parse_benefits_response(
            response, [], None, None
        )

        assert len(benefits) == 2
        assert benefits[0].benefit == "Benefit 1"

    def test_parse_benefits_response_with_json_label(self):
        """Test parsing JSON with 'json' label."""
        service = ContentPlanService()
        response = 'json\n["Benefit 1", "Benefit 2"]'

        benefits = service._parse_benefits_response(
            response, [], None, None
        )

        assert len(benefits) == 2

    def test_parse_benefits_response_fallback(self):
        """Test fallback parsing for non-JSON response."""
        service = ContentPlanService()
        response = """Here are the benefits:
- First benefit that is long enough
- Second benefit that is also long enough
* Third benefit using asterisk
1. Fourth benefit using numbered list
"""
        benefits = service._parse_benefits_response(
            response, [], None, None
        )

        assert len(benefits) >= 3
        assert all(b.confidence == 0.6 for b in benefits)  # Fallback confidence

    def test_extract_benefits_fallback_filters_short(self):
        """Test fallback extraction filters short fragments."""
        service = ContentPlanService()
        text = """
- Short
- This is a long enough benefit text
- x
"""
        benefits = service._extract_benefits_fallback(text)
        assert len(benefits) == 1
        assert "long enough" in benefits[0].benefit

    def test_extract_benefits_fallback_bullet_formats(self):
        """Test fallback extraction handles different bullet formats."""
        service = ContentPlanService()
        text = """
- Dash bullet benefit text here
* Asterisk bullet benefit text here
• Unicode bullet benefit text here
1. Numbered list benefit text here
2) Numbered paren benefit text here
"""
        benefits = service._extract_benefits_fallback(text)
        assert len(benefits) == 5


class TestContentPlanServicePAAConversion:
    """Tests for PAA to priority questions conversion."""

    def test_convert_paa_to_priority_questions(self):
        """Test converting PAA questions to priority questions."""
        service = ContentPlanService()

        # Create mock PAA questions
        @dataclass
        class MockIntent:
            value: str

        @dataclass
        class MockPAAQuestion:
            question: str
            intent: MockIntent
            answer_snippet: str | None = None
            source_url: str | None = None

        paa_questions = [
            MockPAAQuestion(
                question="What is test?",
                intent=MockIntent(value="informational"),
                answer_snippet="Test answer",
                source_url="https://example.com",
            ),
            MockPAAQuestion(
                question="How to test?",
                intent=MockIntent(value="navigational"),
            ),
            MockPAAQuestion(
                question="Where to buy test?",
                intent=MockIntent(value="transactional"),
            ),
        ]

        priority_questions = service._convert_paa_to_priority_questions(
            paa_questions, max_questions=2
        )

        assert len(priority_questions) == 2  # Limited by max_questions
        assert priority_questions[0].question == "What is test?"
        assert priority_questions[0].intent == "informational"
        assert priority_questions[0].priority_rank == 1
        assert priority_questions[0].answer_snippet == "Test answer"
        assert priority_questions[1].priority_rank == 2


class TestContentPlanServiceAsync:
    """Async tests for ContentPlanService."""

    @pytest.mark.asyncio
    async def test_build_content_plan_empty_keyword(self):
        """Test build_content_plan with empty keyword raises error."""
        service = ContentPlanService()

        with pytest.raises(ContentPlanValidationError) as exc_info:
            await service.build_content_plan(keyword="")

        assert exc_info.value.field_name == "keyword"

    @pytest.mark.asyncio
    async def test_build_content_plan_whitespace_keyword(self):
        """Test build_content_plan with whitespace keyword raises error."""
        service = ContentPlanService()

        with pytest.raises(ContentPlanValidationError):
            await service.build_content_plan(keyword="   ")

    @pytest.mark.asyncio
    async def test_build_content_plan_success(self):
        """Test successful content plan building."""
        service = ContentPlanService()

        # Mock PAA enrichment and analysis
        mock_enrichment_result = MagicMock()
        mock_enrichment_result.success = True
        mock_enrichment_result.questions = []

        mock_analysis_result = MagicMock()
        mock_analysis_result.success = True
        mock_analysis_result.content_angle = None
        mock_analysis_result.intent_distribution = {"informational": 0.8}
        mock_analysis_result.total_questions = 5
        mock_analysis_result.priority_questions = []

        # Mock Perplexity
        mock_perplexity = MagicMock()
        mock_perplexity.available = True
        mock_perplexity.complete = AsyncMock(
            return_value=MagicMock(
                success=True,
                text='["Benefit 1", "Benefit 2"]',
                citations=["https://source.com"],
            )
        )

        with patch.object(
            service,
            "_enrich_and_analyze_paa",
            new_callable=AsyncMock,
            return_value=(mock_enrichment_result, mock_analysis_result),
        ):
            with patch(
                "app.services.content_plan.get_perplexity",
                new_callable=AsyncMock,
                return_value=mock_perplexity,
            ):
                result = await service.build_content_plan(
                    keyword="hiking boots",
                    project_id="proj-123",
                )

        assert result.success is True
        assert result.keyword == "hiking boots"
        assert result.project_id == "proj-123"

    @pytest.mark.asyncio
    async def test_build_content_plan_without_perplexity(self):
        """Test content plan building without Perplexity research."""
        service = ContentPlanService()

        mock_enrichment_result = MagicMock()
        mock_enrichment_result.success = True
        mock_enrichment_result.questions = []

        mock_analysis_result = MagicMock()
        mock_analysis_result.success = True
        mock_analysis_result.content_angle = None
        mock_analysis_result.intent_distribution = {}
        mock_analysis_result.total_questions = 0
        mock_analysis_result.priority_questions = []

        with patch.object(
            service,
            "_enrich_and_analyze_paa",
            new_callable=AsyncMock,
            return_value=(mock_enrichment_result, mock_analysis_result),
        ):
            result = await service.build_content_plan(
                keyword="test",
                include_perplexity_research=False,
            )

        assert result.success is True
        assert result.perplexity_used is False
        assert result.benefits == []

    @pytest.mark.asyncio
    async def test_build_content_plan_partial_success(self):
        """Test content plan with partial success (enrichment but no analysis)."""
        service = ContentPlanService()

        mock_enrichment_result = MagicMock()
        mock_enrichment_result.success = True
        mock_enrichment_result.questions = [MagicMock(), MagicMock()]

        # Analysis failed
        mock_analysis_result = None

        with patch.object(
            service,
            "_enrich_and_analyze_paa",
            new_callable=AsyncMock,
            return_value=(mock_enrichment_result, mock_analysis_result),
        ):
            result = await service.build_content_plan(
                keyword="test",
                include_perplexity_research=False,
            )

        assert result.partial_success is True
        assert result.total_questions_analyzed == 2

    @pytest.mark.asyncio
    async def test_build_content_plan_exception_handling(self):
        """Test content plan handles unexpected exceptions."""
        service = ContentPlanService()

        with patch.object(
            service,
            "_enrich_and_analyze_paa",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Unexpected error"),
        ):
            result = await service.build_content_plan(
                keyword="test",
                include_perplexity_research=False,
            )

        assert result.success is False
        assert "Unexpected error" in result.error

    @pytest.mark.asyncio
    async def test_build_content_plans_batch_empty(self):
        """Test batch building with empty keyword list."""
        service = ContentPlanService()
        results = await service.build_content_plans_batch(keywords=[])
        assert results == []

    @pytest.mark.asyncio
    async def test_build_content_plans_batch(self):
        """Test batch content plan building."""
        service = ContentPlanService()

        # Mock the build_content_plan method
        mock_result = ContentPlanResult(success=True, keyword="test")

        with patch.object(
            service,
            "build_content_plan",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            results = await service.build_content_plans_batch(
                keywords=["keyword1", "keyword2", "keyword3"],
                max_concurrent=2,
            )

        assert len(results) == 3
        assert all(r.success for r in results)


class TestResearchBenefits:
    """Tests for _research_benefits method."""

    @pytest.mark.asyncio
    async def test_research_benefits_perplexity_unavailable(self):
        """Test research when Perplexity is unavailable."""
        service = ContentPlanService()

        mock_perplexity = MagicMock()
        mock_perplexity.available = False

        with patch(
            "app.services.content_plan.get_perplexity",
            new_callable=AsyncMock,
            return_value=mock_perplexity,
        ):
            benefits, citations = await service._research_benefits(
                keyword="test",
                max_benefits=5,
                project_id=None,
                page_id=None,
            )

        assert benefits == []
        assert citations == []

    @pytest.mark.asyncio
    async def test_research_benefits_api_failure(self):
        """Test research when Perplexity API fails."""
        service = ContentPlanService()

        mock_perplexity = MagicMock()
        mock_perplexity.available = True
        mock_perplexity.complete = AsyncMock(
            return_value=MagicMock(success=False, error="API error")
        )

        with patch(
            "app.services.content_plan.get_perplexity",
            new_callable=AsyncMock,
            return_value=mock_perplexity,
        ):
            benefits, citations = await service._research_benefits(
                keyword="test",
                max_benefits=5,
                project_id=None,
                page_id=None,
            )

        assert benefits == []
        assert citations == []

    @pytest.mark.asyncio
    async def test_research_benefits_exception(self):
        """Test research handles exceptions gracefully."""
        service = ContentPlanService()

        with patch(
            "app.services.content_plan.get_perplexity",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Connection error"),
        ):
            benefits, citations = await service._research_benefits(
                keyword="test",
                max_benefits=5,
                project_id=None,
                page_id=None,
            )

        assert benefits == []
        assert citations == []


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestBuildBenefitsPrompt:
    """Tests for _build_benefits_prompt function."""

    def test_prompt_includes_keyword(self):
        """Test prompt includes the keyword."""
        prompt = _build_benefits_prompt("hiking boots", 5)
        assert "hiking boots" in prompt

    def test_prompt_includes_max_benefits(self):
        """Test prompt includes max benefits count."""
        prompt = _build_benefits_prompt("test", 3)
        assert "3" in prompt


# =============================================================================
# SINGLETON AND CONVENIENCE FUNCTION TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_content_plan_service_returns_instance(self):
        """Test get_content_plan_service returns a service instance."""
        with patch("app.services.content_plan._content_plan_service", None):
            service = get_content_plan_service()
            assert isinstance(service, ContentPlanService)


class TestConvenienceFunction:
    """Tests for build_content_plan convenience function."""

    @pytest.mark.asyncio
    async def test_build_content_plan_function(self):
        """Test build_content_plan convenience function."""
        mock_result = ContentPlanResult(success=True, keyword="test")
        mock_service = MagicMock(spec=ContentPlanService)
        mock_service.build_content_plan = AsyncMock(return_value=mock_result)

        with patch(
            "app.services.content_plan.get_content_plan_service",
            return_value=mock_service,
        ):
            result = await build_content_plan(
                keyword="test keyword",
                project_id="proj-123",
            )

        assert result.success is True
        mock_service.build_content_plan.assert_called_once()
