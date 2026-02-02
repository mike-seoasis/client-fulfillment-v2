"""Tests for PAA analysis service.

Tests cover:
- Exception classes
- Data classes (IntentGroup, ContentAngleRecommendation, PAAAnalysisResult)
- PAAAnalysisService initialization and methods
- Intent grouping
- Priority question selection
- Content angle recommendation
- Singleton and convenience functions
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from enum import Enum

from app.services.paa_analysis import (
    IntentGroup,
    ContentAngleRecommendation,
    PAAAnalysisResult,
    PAAAnalysisService,
    PAAAnalysisServiceError,
    PAAAnalysisValidationError,
    get_paa_analysis_service,
    DEFAULT_TOP_PRIORITY_COUNT,
)
from app.services.paa_enrichment import PAAQuestion, PAAQuestionIntent


# =============================================================================
# EXCEPTION TESTS
# =============================================================================


class TestPAAAnalysisServiceError:
    """Tests for PAAAnalysisServiceError."""

    def test_base_exception_creation(self):
        """Test creating base exception."""
        error = PAAAnalysisServiceError("Test error")
        assert str(error) == "Test error"

    def test_exception_with_project_page_ids(self):
        """Test exception with project and page IDs."""
        error = PAAAnalysisServiceError(
            "Test error",
            project_id="proj-123",
            page_id="page-456",
        )
        assert error.project_id == "proj-123"
        assert error.page_id == "page-456"

    def test_exception_inheritance(self):
        """Test exception inherits from Exception."""
        error = PAAAnalysisServiceError("Test")
        assert isinstance(error, Exception)


class TestPAAAnalysisValidationError:
    """Tests for PAAAnalysisValidationError."""

    def test_validation_error_attributes(self):
        """Test validation error has correct attributes."""
        error = PAAAnalysisValidationError(
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
        error = PAAAnalysisValidationError("field", "val", "msg")
        assert isinstance(error, PAAAnalysisServiceError)


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestIntentGroup:
    """Tests for IntentGroup dataclass."""

    def test_default_values(self):
        """Test default intent group values."""
        group = IntentGroup(intent=PAAQuestionIntent.BUYING)
        assert group.intent == PAAQuestionIntent.BUYING
        assert group.questions == []
        assert group.count == 0
        assert group.percentage == 0.0

    def test_custom_values(self):
        """Test intent group with custom values."""
        question = PAAQuestion(
            question="What are the best hiking boots?",
            intent=PAAQuestionIntent.BUYING,
        )
        group = IntentGroup(
            intent=PAAQuestionIntent.BUYING,
            questions=[question],
            count=1,
            percentage=25.0,
        )
        assert group.intent == PAAQuestionIntent.BUYING
        assert len(group.questions) == 1
        assert group.count == 1
        assert group.percentage == 25.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        question = PAAQuestion(
            question="Test question?",
            intent=PAAQuestionIntent.USAGE,
        )
        group = IntentGroup(
            intent=PAAQuestionIntent.USAGE,
            questions=[question],
            count=1,
            percentage=33.333,
        )
        result = group.to_dict()
        assert result["intent"] == "usage"
        assert len(result["questions"]) == 1
        assert result["count"] == 1
        assert result["percentage"] == 33.33  # Rounded to 2 decimal places


class TestContentAngleRecommendation:
    """Tests for ContentAngleRecommendation dataclass."""

    def test_default_values(self):
        """Test default content angle values."""
        angle = ContentAngleRecommendation(
            primary_angle="buying-guide",
            reasoning="High percentage of buying intent questions",
        )
        assert angle.primary_angle == "buying-guide"
        assert angle.reasoning == "High percentage of buying intent questions"
        assert angle.focus_areas == []

    def test_custom_values(self):
        """Test content angle with custom values."""
        angle = ContentAngleRecommendation(
            primary_angle="how-to",
            reasoning="Most questions are about usage",
            focus_areas=["setup", "maintenance", "troubleshooting"],
        )
        assert angle.primary_angle == "how-to"
        assert len(angle.focus_areas) == 3
        assert "setup" in angle.focus_areas

    def test_to_dict(self):
        """Test conversion to dictionary."""
        angle = ContentAngleRecommendation(
            primary_angle="comparison",
            reasoning="Users want to compare options",
            focus_areas=["price", "features"],
        )
        result = angle.to_dict()
        assert result["primary_angle"] == "comparison"
        assert result["reasoning"] == "Users want to compare options"
        assert result["focus_areas"] == ["price", "features"]


class TestPAAAnalysisResult:
    """Tests for PAAAnalysisResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = PAAAnalysisResult(success=True, keyword="test")
        assert result.success is True
        assert result.keyword == "test"
        assert result.total_questions == 0
        assert result.categorized_count == 0
        assert result.uncategorized_count == 0
        assert result.intent_groups == {}
        assert result.priority_questions == []
        assert result.content_angle is None
        assert result.intent_distribution == {}
        assert result.error is None
        assert result.duration_ms == 0.0
        assert result.project_id is None
        assert result.page_id is None

    def test_custom_values(self):
        """Test result with custom values."""
        angle = ContentAngleRecommendation(
            primary_angle="buying-guide",
            reasoning="Test",
        )
        result = PAAAnalysisResult(
            success=True,
            keyword="hiking boots",
            total_questions=10,
            categorized_count=8,
            uncategorized_count=2,
            content_angle=angle,
            intent_distribution={"buying": 0.4, "usage": 0.3, "care": 0.2, "comparison": 0.1},
            duration_ms=150.5,
            project_id="proj-123",
            page_id="page-456",
        )
        assert result.success is True
        assert result.keyword == "hiking boots"
        assert result.total_questions == 10
        assert result.categorized_count == 8
        assert result.content_angle is not None
        assert result.project_id == "proj-123"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        angle = ContentAngleRecommendation(
            primary_angle="how-to",
            reasoning="Test reasoning",
        )
        question = PAAQuestion(
            question="How to tie?",
            intent=PAAQuestionIntent.USAGE,
        )
        result = PAAAnalysisResult(
            success=True,
            keyword="test",
            total_questions=5,
            priority_questions=[question],
            content_angle=angle,
            duration_ms=100.567,
        )
        dict_result = result.to_dict()
        assert dict_result["success"] is True
        assert dict_result["keyword"] == "test"
        assert dict_result["total_questions"] == 5
        assert len(dict_result["priority_questions"]) == 1
        assert dict_result["content_angle"]["primary_angle"] == "how-to"
        assert dict_result["duration_ms"] == 100.57  # Rounded

    def test_to_dict_none_content_angle(self):
        """Test to_dict with None content_angle."""
        result = PAAAnalysisResult(
            success=True,
            keyword="test",
            content_angle=None,
        )
        dict_result = result.to_dict()
        assert dict_result["content_angle"] is None


# =============================================================================
# SERVICE TESTS
# =============================================================================


class TestPAAAnalysisService:
    """Tests for PAAAnalysisService."""

    def test_initialization_defaults(self):
        """Test service initialization with defaults."""
        service = PAAAnalysisService()
        assert service._top_priority_count == DEFAULT_TOP_PRIORITY_COUNT

    def test_initialization_custom(self):
        """Test service initialization with custom values."""
        service = PAAAnalysisService(top_priority_count=10)
        assert service._top_priority_count == 10


class TestPAAAnalysisServiceGroupByIntent:
    """Tests for _group_by_intent method."""

    def test_group_by_intent_empty_questions(self):
        """Test grouping empty question list."""
        service = PAAAnalysisService()
        groups = service._group_by_intent([])
        # Should have all intent types initialized
        assert "buying" in groups
        assert "usage" in groups
        assert "care" in groups
        assert "comparison" in groups
        assert "unknown" in groups
        # All should be empty
        for group in groups.values():
            assert group.count == 0
            assert group.percentage == 0.0

    def test_group_by_intent_single_intent(self):
        """Test grouping questions with single intent."""
        service = PAAAnalysisService()
        questions = [
            PAAQuestion(question="Q1?", intent=PAAQuestionIntent.BUYING),
            PAAQuestion(question="Q2?", intent=PAAQuestionIntent.BUYING),
            PAAQuestion(question="Q3?", intent=PAAQuestionIntent.BUYING),
        ]
        groups = service._group_by_intent(questions)
        assert groups["buying"].count == 3
        assert groups["buying"].percentage == 100.0
        assert groups["usage"].count == 0

    def test_group_by_intent_mixed_intents(self):
        """Test grouping questions with mixed intents."""
        service = PAAAnalysisService()
        questions = [
            PAAQuestion(question="Q1?", intent=PAAQuestionIntent.BUYING),
            PAAQuestion(question="Q2?", intent=PAAQuestionIntent.USAGE),
            PAAQuestion(question="Q3?", intent=PAAQuestionIntent.CARE),
            PAAQuestion(question="Q4?", intent=PAAQuestionIntent.COMPARISON),
        ]
        groups = service._group_by_intent(questions)
        assert groups["buying"].count == 1
        assert groups["usage"].count == 1
        assert groups["care"].count == 1
        assert groups["comparison"].count == 1
        assert groups["buying"].percentage == 25.0


class TestPAAAnalysisServicePrioritySelection:
    """Tests for _select_priority_questions method."""

    def test_select_priority_questions_empty(self):
        """Test selecting from empty groups."""
        service = PAAAnalysisService()
        groups = {
            intent.value: IntentGroup(intent=intent)
            for intent in PAAQuestionIntent
        }
        priority = service._select_priority_questions(groups, top_count=5)
        assert priority == []

    def test_select_priority_questions_buying_first(self):
        """Test buying questions are prioritized first."""
        service = PAAAnalysisService()
        buying_q = PAAQuestion(question="Best to buy?", intent=PAAQuestionIntent.BUYING)
        usage_q = PAAQuestion(question="How to use?", intent=PAAQuestionIntent.USAGE)

        groups = {
            intent.value: IntentGroup(intent=intent)
            for intent in PAAQuestionIntent
        }
        groups["buying"].questions = [buying_q]
        groups["usage"].questions = [usage_q]

        priority = service._select_priority_questions(groups, top_count=5)
        assert len(priority) == 2
        assert priority[0].intent == PAAQuestionIntent.BUYING

    def test_select_priority_questions_limited(self):
        """Test priority selection respects limit."""
        service = PAAAnalysisService()
        questions = [
            PAAQuestion(question=f"Q{i}?", intent=PAAQuestionIntent.BUYING)
            for i in range(10)
        ]

        groups = {
            intent.value: IntentGroup(intent=intent)
            for intent in PAAQuestionIntent
        }
        groups["buying"].questions = questions

        priority = service._select_priority_questions(groups, top_count=3)
        assert len(priority) == 3


class TestPAAAnalysisServiceContentAngle:
    """Tests for _determine_content_angle method."""

    def _create_groups_with_counts(self, buying=0, usage=0, care=0, comparison=0, unknown=0):
        """Helper to create groups with specific counts."""
        groups = {}
        for intent in PAAQuestionIntent:
            groups[intent.value] = IntentGroup(intent=intent)

        # Add questions to groups based on counts
        for i in range(buying):
            groups["buying"].questions.append(
                PAAQuestion(question=f"Buy Q{i}?", intent=PAAQuestionIntent.BUYING)
            )
        groups["buying"].count = buying

        for i in range(usage):
            groups["usage"].questions.append(
                PAAQuestion(question=f"Use Q{i}?", intent=PAAQuestionIntent.USAGE)
            )
        groups["usage"].count = usage

        for i in range(care):
            groups["care"].questions.append(
                PAAQuestion(question=f"Care Q{i}?", intent=PAAQuestionIntent.CARE)
            )
        groups["care"].count = care

        for i in range(comparison):
            groups["comparison"].questions.append(
                PAAQuestion(question=f"Compare Q{i}?", intent=PAAQuestionIntent.COMPARISON)
            )
        groups["comparison"].count = comparison

        for i in range(unknown):
            groups["unknown"].questions.append(
                PAAQuestion(question=f"Unknown Q{i}?", intent=PAAQuestionIntent.UNKNOWN)
            )
        groups["unknown"].count = unknown

        return groups

    def test_determine_content_angle_buying_dominant(self):
        """Test content angle when buying is dominant."""
        service = PAAAnalysisService()
        groups = self._create_groups_with_counts(buying=5, usage=2, care=2, comparison=1)
        angle = service._determine_content_angle(groups, keyword="test")
        assert angle is not None
        assert "purchase" in angle.primary_angle.lower()

    def test_determine_content_angle_usage_dominant(self):
        """Test content angle when usage is dominant."""
        service = PAAAnalysisService()
        groups = self._create_groups_with_counts(buying=1, usage=6, care=2, comparison=1)
        angle = service._determine_content_angle(groups, keyword="test")
        assert angle is not None
        assert "practical" in angle.primary_angle.lower() or "benefit" in angle.primary_angle.lower()

    def test_determine_content_angle_care_dominant(self):
        """Test content angle when care is dominant."""
        service = PAAAnalysisService()
        groups = self._create_groups_with_counts(buying=1, usage=2, care=6, comparison=1)
        angle = service._determine_content_angle(groups, keyword="test")
        assert angle is not None
        assert "longevity" in angle.primary_angle.lower() or "maintenance" in angle.primary_angle.lower()

    def test_determine_content_angle_balanced(self):
        """Test content angle when distribution is balanced."""
        service = PAAAnalysisService()
        groups = self._create_groups_with_counts(buying=2, usage=2, care=2, comparison=2)
        angle = service._determine_content_angle(groups, keyword="test")
        assert angle is not None
        # Should still make a recommendation

    def test_determine_content_angle_empty(self):
        """Test content angle with empty groups."""
        service = PAAAnalysisService()
        groups = self._create_groups_with_counts(buying=0, usage=0, care=0, comparison=0)
        angle = service._determine_content_angle(groups, keyword="test")
        assert angle is not None
        # Should still provide a recommendation even with no questions

    def test_determine_content_angle_with_comparison_focus(self):
        """Test content angle adds comparison focus when many comparison questions."""
        service = PAAAnalysisService()
        groups = self._create_groups_with_counts(buying=5, usage=2, care=2, comparison=4)
        angle = service._determine_content_angle(groups, keyword="test")
        assert angle is not None
        # Should include comparison in focus areas
        assert any("comparison" in area.lower() for area in angle.focus_areas)


class TestPAAAnalysisServiceAsync:
    """Async tests for PAAAnalysisService."""

    @pytest.mark.asyncio
    async def test_analyze_paa_questions_empty(self):
        """Test analyzing empty question list."""
        service = PAAAnalysisService()
        result = await service.analyze_paa_questions(
            questions=[],
            keyword="test",
        )
        assert result.success is True
        assert result.total_questions == 0

    @pytest.mark.asyncio
    async def test_analyze_paa_questions_success(self):
        """Test successful PAA analysis."""
        service = PAAAnalysisService()
        questions = [
            PAAQuestion(question="Best boots?", intent=PAAQuestionIntent.BUYING),
            PAAQuestion(question="How to clean?", intent=PAAQuestionIntent.CARE),
            PAAQuestion(question="How to tie?", intent=PAAQuestionIntent.USAGE),
        ]
        result = await service.analyze_paa_questions(
            questions=questions,
            keyword="hiking boots",
            project_id="proj-123",
        )
        assert result.success is True
        assert result.keyword == "hiking boots"
        assert result.total_questions == 3
        assert result.project_id == "proj-123"
        assert len(result.intent_distribution) > 0

    @pytest.mark.asyncio
    async def test_analyze_paa_questions_with_priority(self):
        """Test PAA analysis includes priority questions."""
        service = PAAAnalysisService(top_priority_count=2)
        questions = [
            PAAQuestion(question="Q1?", intent=PAAQuestionIntent.BUYING),
            PAAQuestion(question="Q2?", intent=PAAQuestionIntent.CARE),
            PAAQuestion(question="Q3?", intent=PAAQuestionIntent.USAGE),
            PAAQuestion(question="Q4?", intent=PAAQuestionIntent.COMPARISON),
        ]
        result = await service.analyze_paa_questions(
            questions=questions,
            keyword="test",
        )
        assert result.success is True
        assert len(result.priority_questions) <= 2


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_paa_analysis_service_returns_instance(self):
        """Test get_paa_analysis_service returns a service instance."""
        with patch("app.services.paa_analysis._paa_analysis_service", None):
            service = get_paa_analysis_service()
            assert isinstance(service, PAAAnalysisService)
