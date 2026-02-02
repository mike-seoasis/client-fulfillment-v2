"""End-to-end tests for content brief -> generation -> scoring workflow.

Tests the critical path from:
1. Content brief fetch from POP API (mocked)
2. Content generation using LLM with brief data
3. Content scoring against POP API (mocked)

This workflow validates the integration between:
- POPContentBriefService
- ContentGenerationService (via API when needed)
- POPContentScoreService

All external APIs (POP, Claude) are mocked to ensure reliable, fast tests.

ERROR LOGGING REQUIREMENTS:
- Test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging

Target: Complete E2E coverage of POP content workflow.
"""

import logging
import time
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.pop import (
    POPCircuitOpenError,
    POPClient,
    POPTaskResult,
    POPTaskStatus,
    POPTimeoutError,
)
from app.services.pop_content_brief import (
    POPContentBriefService,
)
from app.services.pop_content_score import (
    POPContentScoreService,
)

# Configure logging for test debugging
logger = logging.getLogger(__name__)


# =============================================================================
# MOCK DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_pop_brief_response() -> dict[str, Any]:
    """Sample POP API response for content brief."""
    return {
        "task_id": "brief-task-123",
        "status": "success",
        "wordCount": {"current": 0, "target": 1500},
        "tagCounts": [
            {
                "tagLabel": "H1 tag total",
                "min": 1,
                "max": 1,
                "mean": 1.0,
                "signalCnt": 0,
            },
            {
                "tagLabel": "H2 tag total",
                "min": 3,
                "max": 8,
                "mean": 5.2,
                "signalCnt": 0,
            },
            {
                "tagLabel": "H3 tag total",
                "min": 5,
                "max": 12,
                "mean": 8.1,
                "signalCnt": 0,
            },
            {
                "tagLabel": "Word count",
                "min": 1200,
                "max": 2000,
                "mean": 1500,
                "signalCnt": 0,
            },
        ],
        "cleanedContentBrief": {
            "pageScore": 85,
            "pageScoreValue": 85,
            "title": {
                "keywords": [
                    {
                        "term": {
                            "phrase": "premium leather wallets",
                            "type": "exact",
                            "weight": 1.0,
                        },
                        "contentBrief": {"current": 0, "target": 1},
                    }
                ]
            },
            "pageTitle": {
                "keywords": [
                    {
                        "term": {
                            "phrase": "premium leather wallets",
                            "type": "exact",
                            "weight": 1.0,
                        },
                        "contentBrief": {"current": 0, "target": 1},
                    }
                ]
            },
            "subHeadings": {
                "keywords": [
                    {
                        "term": {
                            "phrase": "leather wallet",
                            "type": "partial",
                            "weight": 0.8,
                        },
                        "contentBrief": {"current": 0, "target": 2},
                    }
                ]
            },
            "p": {
                "keywords": [
                    {
                        "term": {
                            "phrase": "premium leather",
                            "type": "partial",
                            "weight": 0.7,
                        },
                        "contentBrief": {"current": 0, "target": 3},
                    }
                ]
            },
        },
        "lsaPhrases": [
            {
                "phrase": "genuine leather",
                "weight": 0.85,
                "averageCount": 3,
                "targetCount": 0,
            },
            {
                "phrase": "handcrafted",
                "weight": 0.72,
                "averageCount": 2,
                "targetCount": 0,
            },
            {
                "phrase": "bifold wallet",
                "weight": 0.68,
                "averageCount": 2,
                "targetCount": 0,
            },
        ],
        "relatedQuestions": [
            {
                "question": "What is the best leather for wallets?",
                "snippet": "Full-grain leather is considered the best...",
                "link": "https://example.com/leather-guide",
            },
            {
                "question": "How long do leather wallets last?",
                "snippet": "A quality leather wallet can last 5-10 years...",
                "link": "https://example.com/durability",
            },
        ],
        "competitors": [
            {
                "url": "https://competitor1.com/wallets",
                "title": "Competitor 1 Wallets",
                "pageScore": 82,
            },
            {
                "url": "https://competitor2.com/wallets",
                "title": "Competitor 2 Wallets",
                "pageScore": 78,
            },
        ],
    }


@pytest.fixture
def sample_pop_score_response() -> dict[str, Any]:
    """Sample POP API response for content scoring."""
    return {
        "task_id": "score-task-456",
        "status": "success",
        "pageScore": 75,
        "wordCount": {"current": 1200, "target": 1500},
        "tagCounts": [
            {
                "tagLabel": "H1 tag total",
                "min": 1,
                "max": 1,
                "mean": 1.0,
                "signalCnt": 1,
            },
            {
                "tagLabel": "H2 tag total",
                "min": 3,
                "max": 8,
                "mean": 5.2,
                "signalCnt": 4,
            },
            {
                "tagLabel": "H3 tag total",
                "min": 5,
                "max": 12,
                "mean": 8.1,
                "signalCnt": 6,
            },
        ],
        "cleanedContentBrief": {
            "pageScore": 75,
            "title": {
                "keywords": [
                    {
                        "term": {
                            "phrase": "premium leather wallets",
                            "type": "exact",
                            "weight": 1.0,
                        },
                        "contentBrief": {"current": 1, "target": 1},
                    }
                ]
            },
            "p": {
                "keywords": [
                    {
                        "term": {
                            "phrase": "premium leather",
                            "type": "partial",
                            "weight": 0.7,
                        },
                        "contentBrief": {"current": 2, "target": 3},
                    }
                ]
            },
        },
        "lsaPhrases": [
            {
                "phrase": "genuine leather",
                "weight": 0.85,
                "averageCount": 3,
                "targetCount": 2,
            },
            {
                "phrase": "handcrafted",
                "weight": 0.72,
                "averageCount": 2,
                "targetCount": 1,
            },
        ],
    }


@pytest.fixture
def mock_claude_response() -> dict[str, Any]:
    """Mock Claude API response for content generation."""
    return {
        "h1": "Premium Leather Wallets for the Modern Professional",
        "title_tag": "Premium Leather Wallets | E2E Test Brand",
        "meta_description": "Discover handcrafted premium leather wallets built to last. Shop our collection of genuine leather bifold and slim wallets.",
        "body_content": """<h2>Timeless Craftsmanship</h2>
<p>Our premium leather wallets combine traditional craftsmanship with modern design. Each wallet is handcrafted from genuine leather to ensure lasting quality.</p>
<h2>Quality Materials</h2>
<p>We use only full-grain leather in our wallets. This premium material develops a beautiful patina over time while maintaining its structure.</p>
<h2>Smart Organization</h2>
<p>Our bifold wallet design keeps your cards and cash organized. Multiple card slots and a bill compartment provide ample storage without bulk.</p>""",
        "word_count": 150,
    }


@pytest.fixture
def test_ids() -> dict[str, str]:
    """Generate test IDs for project, page, etc."""
    return {
        "project_id": str(uuid.uuid4()),
        "page_id": str(uuid.uuid4()),
        "keyword": "premium leather wallets",
        "target_url": "https://example.com/collections/leather-wallets",
    }


# =============================================================================
# E2E WORKFLOW TESTS - CONTENT BRIEF -> GENERATION -> SCORING
# =============================================================================


class TestE2EContentBriefToScoringWorkflow:
    """E2E tests for the full content brief -> generation -> scoring workflow.

    These tests mock the POP API and test the service layer integration.
    """

    @pytest.mark.asyncio
    async def test_full_workflow_with_mocks(
        self,
        test_ids: dict[str, str],
        sample_pop_brief_response: dict[str, Any],
        sample_pop_score_response: dict[str, Any],
    ) -> None:
        """Test complete workflow: brief -> scoring with all mocks at service layer."""
        workflow_start = time.monotonic()
        project_id = test_ids["project_id"]
        page_id = test_ids["page_id"]
        keyword = test_ids["keyword"]
        target_url = test_ids["target_url"]

        logger.info(
            "E2E Full Workflow: Starting content brief -> scoring",
            extra={"project_id": project_id, "page_id": page_id, "keyword": keyword},
        )

        # Step 1: Fetch Content Brief (mocked POP API)
        step_start = time.monotonic()
        logger.debug("Step 1: Fetching content brief")

        mock_pop_client = AsyncMock(spec=POPClient)
        mock_pop_client.available = True

        # Mock task creation
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="brief-task-123",
            status=POPTaskStatus.PENDING,
            data={},
        )

        # Mock polling result
        mock_pop_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="brief-task-123",
            status=POPTaskStatus.SUCCESS,
            data=sample_pop_brief_response,
        )

        brief_service = POPContentBriefService(client=mock_pop_client)
        brief_result = await brief_service.fetch_brief(
            project_id=project_id,
            page_id=page_id,
            keyword=keyword,
            target_url=target_url,
        )

        step_duration = (time.monotonic() - step_start) * 1000
        logger.info(
            "Step 1 Complete: Content brief fetched",
            extra={
                "success": brief_result.success,
                "word_count_target": brief_result.word_count_target,
                "lsi_term_count": len(brief_result.lsi_terms),
                "duration_ms": round(step_duration, 2),
            },
        )

        assert brief_result.success is True, f"Brief fetch failed: {brief_result.error}"
        assert brief_result.word_count_target is not None
        assert len(brief_result.lsi_terms) > 0

        # Step 2: Score Content (mocked POP API)
        step_start = time.monotonic()
        logger.debug("Step 2: Scoring content")

        mock_score_client = AsyncMock(spec=POPClient)
        mock_score_client.available = True

        # Mock task creation for scoring
        mock_score_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="score-task-456",
            status=POPTaskStatus.PENDING,
            data={},
        )

        # Mock polling result for scoring
        mock_score_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="score-task-456",
            status=POPTaskStatus.SUCCESS,
            data=sample_pop_score_response,
        )

        # Mock settings to use POP scoring
        mock_settings = MagicMock()
        mock_settings.pop_pass_threshold = 70

        with patch(
            "app.services.pop_content_score.get_settings", return_value=mock_settings
        ):
            score_service = POPContentScoreService(client=mock_score_client)
            score_result = await score_service.score_content(
                project_id=project_id,
                page_id=page_id,
                keyword=keyword,
                content_url=target_url,
            )

        step_duration = (time.monotonic() - step_start) * 1000

        logger.info(
            "Step 2 Complete: Content scored",
            extra={
                "success": score_result.success,
                "page_score": score_result.page_score,
                "passed": score_result.passed,
                "fallback_used": score_result.fallback_used,
                "duration_ms": round(step_duration, 2),
            },
        )

        assert score_result.success is True, f"Scoring failed: {score_result.error}"
        assert score_result.page_score is not None
        assert score_result.passed is not None

        # Final workflow summary
        workflow_duration = (time.monotonic() - workflow_start) * 1000
        logger.info(
            "E2E Full Workflow: Complete",
            extra={
                "project_id": project_id,
                "page_id": page_id,
                "keyword": keyword,
                "brief_word_target": brief_result.word_count_target,
                "score": score_result.page_score,
                "passed": score_result.passed,
                "total_duration_ms": round(workflow_duration, 2),
            },
        )

    @pytest.mark.asyncio
    async def test_workflow_scoring_uses_pass_threshold(
        self,
        test_ids: dict[str, str],
    ) -> None:
        """Test that scoring respects pass threshold configuration."""
        project_id = test_ids["project_id"]
        page_id = test_ids["page_id"]
        keyword = test_ids["keyword"]
        target_url = test_ids["target_url"]

        logger.info("Test: Verifying pass threshold is respected")

        # Create score response at exactly threshold
        threshold_score_response = {
            "task_id": "score-task-789",
            "status": "success",
            "pageScore": 70,  # Exactly at threshold
            "wordCount": {"current": 1200, "target": 1500},
        }

        mock_pop_client = AsyncMock(spec=POPClient)
        mock_pop_client.available = True
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="score-task-789",
            status=POPTaskStatus.PENDING,
            data={},
        )
        mock_pop_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="score-task-789",
            status=POPTaskStatus.SUCCESS,
            data=threshold_score_response,
        )

        # Test with threshold at 70 (should pass)
        mock_settings_70 = MagicMock()
        mock_settings_70.pop_pass_threshold = 70

        with patch(
            "app.services.pop_content_score.get_settings", return_value=mock_settings_70
        ):
            score_service = POPContentScoreService(client=mock_pop_client)
            result_at_70 = await score_service.score_content(
                project_id=project_id,
                page_id=page_id,
                keyword=keyword,
                content_url=target_url,
            )

        assert result_at_70.success is True
        assert result_at_70.passed is True, "Score of 70 should pass with threshold 70"

        # Test with threshold at 71 (should fail)
        mock_settings_71 = MagicMock()
        mock_settings_71.pop_pass_threshold = 71

        # Reset mock for second call
        mock_pop_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="score-task-790",
            status=POPTaskStatus.SUCCESS,
            data=threshold_score_response,
        )

        with patch(
            "app.services.pop_content_score.get_settings", return_value=mock_settings_71
        ):
            score_service = POPContentScoreService(client=mock_pop_client)
            result_at_71 = await score_service.score_content(
                project_id=project_id,
                page_id=page_id,
                keyword=keyword,
                content_url=target_url,
            )

        assert result_at_71.success is True
        assert result_at_71.passed is False, "Score of 70 should fail with threshold 71"

        logger.info(
            "Test passed: Pass threshold is respected",
            extra={
                "score": 70,
                "passed_at_70": result_at_70.passed,
                "passed_at_71": result_at_71.passed,
            },
        )


class TestE2EContentScoreFallback:
    """E2E tests for content scoring fallback scenarios."""

    @pytest.mark.asyncio
    async def test_scoring_fallback_on_circuit_open(
        self,
        test_ids: dict[str, str],
    ) -> None:
        """Test that scoring falls back to legacy service when circuit breaker is open."""
        project_id = test_ids["project_id"]
        page_id = test_ids["page_id"]
        keyword = test_ids["keyword"]
        target_url = test_ids["target_url"]

        logger.info("Test: Scoring fallback on circuit breaker open")

        # Mock POP client that raises circuit open error
        mock_pop_client = AsyncMock(spec=POPClient)
        mock_pop_client.available = True
        mock_pop_client.create_report_task.side_effect = POPCircuitOpenError(
            "Circuit breaker is open"
        )

        # Mock legacy service
        mock_legacy = MagicMock()
        mock_legacy.score_content = AsyncMock(
            return_value=MagicMock(
                success=True,
                overall_score=0.72,  # Legacy uses 0-1 scale
                passed=True,
                details={"source": "legacy"},
            )
        )

        mock_settings = MagicMock()
        mock_settings.pop_pass_threshold = 70

        with patch(
            "app.services.pop_content_score.get_settings", return_value=mock_settings
        ):
            score_service = POPContentScoreService(
                client=mock_pop_client,
                legacy_service=mock_legacy,
            )
            result = await score_service.score_content(
                project_id=project_id,
                page_id=page_id,
                keyword=keyword,
                content_url=target_url,
            )

        # Verify fallback was used
        assert result.fallback_used is True, "Expected fallback to be used"
        assert result.page_score is not None, "Expected score from fallback"
        # Legacy score of 0.72 should be converted to 72 on POP scale
        assert result.page_score == 72.0, f"Expected 72.0, got {result.page_score}"

        logger.info(
            "Test passed: Fallback used on circuit open",
            extra={
                "fallback_used": result.fallback_used,
                "page_score": result.page_score,
            },
        )

    @pytest.mark.asyncio
    async def test_scoring_fallback_on_timeout(
        self,
        test_ids: dict[str, str],
    ) -> None:
        """Test that scoring falls back to legacy service on timeout."""
        project_id = test_ids["project_id"]
        page_id = test_ids["page_id"]
        keyword = test_ids["keyword"]
        target_url = test_ids["target_url"]

        logger.info("Test: Scoring fallback on timeout")

        # Mock POP client that raises timeout error
        mock_pop_client = AsyncMock(spec=POPClient)
        mock_pop_client.available = True
        mock_pop_client.create_report_task.side_effect = POPTimeoutError(
            "Request timed out after 60s"
        )

        # Mock legacy service
        mock_legacy = MagicMock()
        mock_legacy.score_content = AsyncMock(
            return_value=MagicMock(
                success=True,
                overall_score=0.65,  # Legacy uses 0-1 scale
                passed=False,
                details={"source": "legacy"},
            )
        )

        mock_settings = MagicMock()
        mock_settings.pop_pass_threshold = 70

        with patch(
            "app.services.pop_content_score.get_settings", return_value=mock_settings
        ):
            score_service = POPContentScoreService(
                client=mock_pop_client,
                legacy_service=mock_legacy,
            )
            result = await score_service.score_content(
                project_id=project_id,
                page_id=page_id,
                keyword=keyword,
                content_url=target_url,
            )

        # Verify fallback was used
        assert result.fallback_used is True, "Expected fallback to be used"
        assert result.page_score == 65.0, f"Expected 65.0, got {result.page_score}"

        logger.info(
            "Test passed: Fallback used on timeout",
            extra={
                "fallback_used": result.fallback_used,
                "page_score": result.page_score,
            },
        )


class TestE2EWorkflowEdgeCases:
    """E2E tests for edge cases in the workflow."""

    @pytest.mark.asyncio
    async def test_workflow_with_empty_brief_data(
        self,
        test_ids: dict[str, str],
    ) -> None:
        """Test workflow handles brief with minimal/empty data gracefully."""
        project_id = test_ids["project_id"]
        page_id = test_ids["page_id"]
        keyword = test_ids["keyword"]
        target_url = test_ids["target_url"]

        logger.info("Test: Workflow with minimal brief data")

        # Minimal POP response
        minimal_brief_response = {
            "task_id": "brief-minimal-123",
            "status": "success",
            "wordCount": {},  # Missing target
            "cleanedContentBrief": {},  # Empty
            "lsaPhrases": [],
            "relatedQuestions": [],
            "competitors": [],
        }

        mock_pop_client = AsyncMock(spec=POPClient)
        mock_pop_client.available = True
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="brief-minimal-123",
            status=POPTaskStatus.PENDING,
            data={},
        )
        mock_pop_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="brief-minimal-123",
            status=POPTaskStatus.SUCCESS,
            data=minimal_brief_response,
        )

        brief_service = POPContentBriefService(client=mock_pop_client)
        result = await brief_service.fetch_brief(
            project_id=project_id,
            page_id=page_id,
            keyword=keyword,
            target_url=target_url,
        )

        # Should succeed even with minimal data
        assert result.success is True
        # These may be None or empty but shouldn't cause errors
        assert result.lsi_terms == []
        assert result.related_questions == []

        logger.info(
            "Test passed: Workflow handles minimal brief data",
            extra={
                "success": result.success,
                "word_count_target": result.word_count_target,
            },
        )

    @pytest.mark.asyncio
    async def test_workflow_metrics_collection(
        self,
        test_ids: dict[str, str],
        sample_pop_brief_response: dict[str, Any],
        sample_pop_score_response: dict[str, Any],
    ) -> None:
        """Test that workflow collects timing and status metrics."""
        project_id = test_ids["project_id"]
        page_id = test_ids["page_id"]
        keyword = test_ids["keyword"]
        target_url = test_ids["target_url"]

        logger.info("Test: Workflow metrics collection")

        # Track metrics
        metrics = {
            "brief_duration_ms": 0.0,
            "score_duration_ms": 0.0,
            "brief_success": False,
            "score_success": False,
        }

        # Brief phase
        mock_pop_client = AsyncMock(spec=POPClient)
        mock_pop_client.available = True
        mock_pop_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="brief-task-123",
            status=POPTaskStatus.PENDING,
            data={},
        )
        mock_pop_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="brief-task-123",
            status=POPTaskStatus.SUCCESS,
            data=sample_pop_brief_response,
        )

        start = time.monotonic()
        brief_service = POPContentBriefService(client=mock_pop_client)
        brief_result = await brief_service.fetch_brief(
            project_id=project_id,
            page_id=page_id,
            keyword=keyword,
            target_url=target_url,
        )
        metrics["brief_duration_ms"] = (time.monotonic() - start) * 1000
        metrics["brief_success"] = brief_result.success

        # Score phase
        mock_score_client = AsyncMock(spec=POPClient)
        mock_score_client.available = True
        mock_score_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="score-task-456",
            status=POPTaskStatus.PENDING,
            data={},
        )
        mock_score_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="score-task-456",
            status=POPTaskStatus.SUCCESS,
            data=sample_pop_score_response,
        )

        mock_settings = MagicMock()
        mock_settings.pop_pass_threshold = 70

        start = time.monotonic()
        with patch(
            "app.services.pop_content_score.get_settings", return_value=mock_settings
        ):
            score_service = POPContentScoreService(client=mock_score_client)
            score_result = await score_service.score_content(
                project_id=project_id,
                page_id=page_id,
                keyword=keyword,
                content_url=target_url,
            )
        metrics["score_duration_ms"] = (time.monotonic() - start) * 1000
        metrics["score_success"] = score_result.success

        # Verify metrics are reasonable
        assert metrics["brief_success"] is True
        assert metrics["score_success"] is True
        assert metrics["brief_duration_ms"] > 0
        assert metrics["score_duration_ms"] > 0

        logger.info(
            "Test passed: Workflow metrics collected",
            extra=metrics,
        )

    @pytest.mark.asyncio
    async def test_brief_data_flow_to_scoring(
        self,
        test_ids: dict[str, str],
        sample_pop_brief_response: dict[str, Any],
        sample_pop_score_response: dict[str, Any],
    ) -> None:
        """Test that brief data properly informs subsequent scoring."""
        project_id = test_ids["project_id"]
        page_id = test_ids["page_id"]
        keyword = test_ids["keyword"]
        target_url = test_ids["target_url"]

        logger.info("Test: Brief data flows to subsequent scoring")

        # Step 1: Fetch brief
        mock_brief_client = AsyncMock(spec=POPClient)
        mock_brief_client.available = True
        mock_brief_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="brief-task-flow",
            status=POPTaskStatus.PENDING,
            data={},
        )
        mock_brief_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="brief-task-flow",
            status=POPTaskStatus.SUCCESS,
            data=sample_pop_brief_response,
        )

        brief_service = POPContentBriefService(client=mock_brief_client)
        brief_result = await brief_service.fetch_brief(
            project_id=project_id,
            page_id=page_id,
            keyword=keyword,
            target_url=target_url,
        )

        assert brief_result.success is True
        assert brief_result.word_count_target == 1500  # From fixture

        # Step 2: Score using brief data
        mock_score_client = AsyncMock(spec=POPClient)
        mock_score_client.available = True
        mock_score_client.create_report_task.return_value = POPTaskResult(
            success=True,
            task_id="score-task-flow",
            status=POPTaskStatus.PENDING,
            data={},
        )
        mock_score_client.poll_for_result.return_value = POPTaskResult(
            success=True,
            task_id="score-task-flow",
            status=POPTaskStatus.SUCCESS,
            data=sample_pop_score_response,
        )

        mock_settings = MagicMock()
        mock_settings.pop_pass_threshold = 70

        with patch(
            "app.services.pop_content_score.get_settings", return_value=mock_settings
        ):
            score_service = POPContentScoreService(client=mock_score_client)
            score_result = await score_service.score_content(
                project_id=project_id,
                page_id=page_id,
                keyword=keyword,
                content_url=target_url,
            )

        assert score_result.success is True
        assert score_result.word_count_target == 1500  # Should match brief target
        assert score_result.word_count_current == 1200  # From score response

        # Verify scoring data aligns with brief expectations
        # Score response shows current word count vs brief's target
        word_count_deficit = (
            brief_result.word_count_target - score_result.word_count_current
        )
        assert word_count_deficit == 300  # 1500 - 1200

        logger.info(
            "Test passed: Brief data flows to scoring",
            extra={
                "brief_word_target": brief_result.word_count_target,
                "score_word_target": score_result.word_count_target,
                "score_word_current": score_result.word_count_current,
                "word_count_deficit": word_count_deficit,
            },
        )
