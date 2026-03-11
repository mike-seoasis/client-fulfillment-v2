"""Tests for the Prompt A/B Testing Tool server.

Tests cover:
- LSI term matching logic (case-insensitive, HTML stripping, counting)
- JSON parsing (clean, markdown-fenced, invalid)
- Word count calculation
- API endpoints (with mocked DB + Claude dependencies)
- Variant persistence (save/load/delete on disk)
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Path setup — mirror the server's sys.path manipulation so imports resolve
# ---------------------------------------------------------------------------
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# Import the functions and app under test
from server import (  # noqa: E402
    VARIANTS_FILE,
    _compute_lsi_coverage,
    _compute_related_questions_coverage,
    _compute_related_searches_coverage,
    _count_words,
    _load_variants,
    _parse_content_json,
    _save_variants,
    _strip_html,
    app,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def sample_lsi_terms() -> list[dict[str, Any]]:
    """LSI terms resembling real POP brief data."""
    return [
        {"phrase": "neck cream", "weight": 9, "targetCount": 3, "averageCount": 2},
        {"phrase": "sagging skin", "weight": 7, "targetCount": 2, "averageCount": 1},
        {"phrase": "Anti-Aging", "weight": 5, "targetCount": 1, "averageCount": 1},
        {"phrase": "firming serum", "weight": 4, "targetCount": 1, "averageCount": 1},
    ]


@pytest.fixture
def sample_content() -> dict[str, str]:
    """Content dict matching the shape returned by Claude."""
    return {
        "page_title": "Best Neck Cream for Sagging Skin | Dr. Brandt",
        "meta_description": "Discover our firming serum and neck cream for anti-aging.",
        "top_description": "Our neck cream collection targets sagging skin with clinically proven ingredients.",
        "bottom_description": (
            "<h2>Why Choose Our Neck Cream?</h2>"
            "<p>Our anti-aging formulas address sagging skin effectively. "
            "The firming serum penetrates deep layers for visible results.</p>"
        ),
    }


@pytest.fixture
def mock_brief_dict(sample_lsi_terms: list[dict[str, Any]]) -> dict[str, Any]:
    """A plain dict ContentBrief (as used by the refactored server)."""
    return {
        "id": "test-brief-id",
        "page_id": "test-page-id",
        "keyword": "neck cream",
        "lsi_terms": sample_lsi_terms,
        "heading_targets": [{"level": "h2", "text": "Why Neck Cream?"}],
        "keyword_targets": [],
        "related_questions": ["What is the best neck cream?"],
        "related_searches": ["neck cream for sagging skin"],
        "competitors": [],
        "word_count_target": 800,
        "word_count_min": 600,
        "word_count_max": 1000,
        "page_score_target": None,
        "raw_response": {},
    }


@pytest.fixture
def mock_brief_orm(sample_lsi_terms: list[dict[str, Any]]) -> MagicMock:
    """A mock ORM ContentBrief (used by prompt builder functions)."""
    brief = MagicMock()
    brief.lsi_terms = sample_lsi_terms
    brief.keyword = "neck cream"
    brief.word_count_target = 800
    brief.word_count_min = 600
    brief.word_count_max = 1000
    brief.heading_targets = [{"level": "h2", "text": "Why Neck Cream?"}]
    brief.keyword_targets = []
    brief.related_questions = ["What is the best neck cream?"]
    brief.related_searches = ["neck cream for sagging skin"]
    brief.competitors = []
    brief.page_id = "test-page-id"
    brief.raw_response = {}
    return brief


@pytest.fixture
def mock_page_dict() -> dict[str, Any]:
    """A plain dict CrawledPage (as used by the refactored server)."""
    return {
        "id": "test-page-id",
        "normalized_url": "https://example.com/neck-cream",
        "title": "Neck Cream Collection",
        "meta_description": "Shop our neck cream collection",
        "product_count": 12,
        "labels": [],
    }


@pytest.fixture
def variants_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect VARIANTS_FILE to a temp directory for isolation."""
    tmp_variants = tmp_path / "variants.json"
    monkeypatch.setattr("server.VARIANTS_FILE", tmp_variants)
    return tmp_variants


@pytest.fixture
def fake_claude_response() -> dict[str, str]:
    """A well-formed JSON response from Claude."""
    return {
        "page_title": "Neck Cream for Sagging Skin",
        "meta_description": "Shop the best neck cream to fight sagging skin and signs of aging.",
        "top_description": "Explore our neck cream collection.",
        "bottom_description": "<h2>About Neck Cream</h2><p>Great for sagging skin.</p>",
    }


# ===========================================================================
# 1. LSI Term Matching Logic
# ===========================================================================


class TestLsiTermCoverage:
    """Tests for _compute_lsi_coverage."""

    def test_basic_case_insensitive_matching(
        self,
        sample_content: dict[str, str],
        mock_brief_dict: dict[str, Any],
    ) -> None:
        """All four terms appear in the sample content (case-insensitive)."""
        result = _compute_lsi_coverage(sample_content, mock_brief_dict)

        assert result["total_terms"] == 4
        assert result["terms_hit"] == 4
        assert result["terms_missed"] == 0

        # Check that each term is found
        for detail in result["details"]:
            assert detail["found"] is True, f"Expected '{detail['phrase']}' to be found"
            assert detail["count"] > 0

    def test_html_stripped_before_matching(self, mock_brief_dict: dict[str, Any]) -> None:
        """Terms inside HTML tags should still be matched after stripping."""
        content = {
            "page_title": "",
            "meta_description": "",
            "top_description": "",
            "bottom_description": "<h2>Neck Cream</h2><p>Sagging skin solutions. Anti-aging firming serum.</p>",
        }
        result = _compute_lsi_coverage(content, mock_brief_dict)

        assert result["terms_hit"] == 4

    def test_count_occurrences_correctly(self, mock_brief_dict: dict[str, Any]) -> None:
        """Multiple occurrences should be counted accurately."""
        content = {
            "page_title": "neck cream",
            "meta_description": "neck cream benefits",
            "top_description": "Our neck cream is the best neck cream.",
            "bottom_description": "",
        }
        result = _compute_lsi_coverage(content, mock_brief_dict)

        neck_cream_detail = next(
            d for d in result["details"] if d["phrase"] == "neck cream"
        )
        # "neck cream" appears 4 times across the fields
        assert neck_cream_detail["count"] == 4

    def test_partial_match_across_fields(self, mock_brief_dict: dict[str, Any]) -> None:
        """A term found in only one field but not others still counts as hit."""
        content = {
            "page_title": "Firming Serum",
            "meta_description": "",
            "top_description": "",
            "bottom_description": "",
        }
        result = _compute_lsi_coverage(content, mock_brief_dict)

        firming_detail = next(
            d for d in result["details"] if d["phrase"] == "firming serum"
        )
        assert firming_detail["found"] is True
        assert firming_detail["count"] == 1

    def test_terms_with_special_characters(self) -> None:
        """Terms with hyphens or other punctuation should match correctly."""
        brief = {
            "lsi_terms": [
                {"phrase": "anti-aging", "weight": 5, "targetCount": 1},
                {"phrase": "vitamin C (ascorbic acid)", "weight": 3, "targetCount": 1},
            ],
        }
        content = {
            "page_title": "Anti-Aging Solutions",
            "meta_description": "Contains Vitamin C (ascorbic acid) for youthful skin.",
            "top_description": "",
            "bottom_description": "",
        }
        result = _compute_lsi_coverage(content, brief)

        assert result["terms_hit"] == 2
        assert result["total_terms"] == 2

    def test_empty_content_returns_zero_hits(
        self,
        mock_brief_dict: dict[str, Any],
    ) -> None:
        """All empty content fields should yield zero hits."""
        content = {
            "page_title": "",
            "meta_description": "",
            "top_description": "",
            "bottom_description": "",
        }
        result = _compute_lsi_coverage(content, mock_brief_dict)

        assert result["terms_hit"] == 0
        assert result["terms_missed"] == 4

    def test_no_brief_returns_empty_coverage(self) -> None:
        """When brief is None, return zeroed-out structure."""
        result = _compute_lsi_coverage({"page_title": "test"}, None)
        assert result == {
            "total_terms": 0,
            "terms_hit": 0,
            "terms_missed": 0,
            "details": [],
        }

    def test_brief_with_no_lsi_terms(self) -> None:
        """Brief exists but has empty lsi_terms list."""
        brief: dict[str, Any] = {"lsi_terms": []}
        result = _compute_lsi_coverage({"page_title": "test"}, brief)
        assert result["total_terms"] == 0
        assert result["details"] == []

    def test_brief_with_none_lsi_terms(self) -> None:
        """Brief exists but lsi_terms is None."""
        brief: dict[str, Any] = {"lsi_terms": None}
        result = _compute_lsi_coverage({"page_title": "test"}, brief)
        assert result["total_terms"] == 0

    def test_weight_and_target_count_passed_through(
        self,
        sample_lsi_terms: list[dict[str, Any]],
    ) -> None:
        """Details should include weight and targetCount from brief."""
        brief: dict[str, Any] = {"lsi_terms": sample_lsi_terms}
        content = {
            "page_title": "neck cream",
            "meta_description": "",
            "top_description": "",
            "bottom_description": "",
        }
        result = _compute_lsi_coverage(content, brief)
        neck_detail = next(
            d for d in result["details"] if d["phrase"] == "neck cream"
        )
        assert neck_detail["weight"] == 9
        assert neck_detail["targetCount"] == 3

    def test_target_count_falls_back_to_average_count(self) -> None:
        """When targetCount is missing, averageCount is used."""
        brief: dict[str, Any] = {
            "lsi_terms": [
                {"phrase": "retinol", "weight": 3, "averageCount": 5},
            ],
        }
        content = {
            "page_title": "retinol",
            "meta_description": "",
            "top_description": "",
            "bottom_description": "",
        }
        result = _compute_lsi_coverage(content, brief)
        assert result["details"][0]["targetCount"] == 5


# ===========================================================================
# 1b. Related Searches Coverage
# ===========================================================================


class TestRelatedSearchesCoverage:
    """Tests for _compute_related_searches_coverage."""

    def test_basic_substring_match(self, sample_content: dict[str, str]) -> None:
        brief = {"related_searches": ["neck cream", "anti-aging serum"]}
        result = _compute_related_searches_coverage(sample_content, brief)
        assert result["total"] == 2
        assert result["hit"] == 1  # "neck cream" found, "anti-aging serum" not
        assert result["missed"] == 1

    def test_case_insensitive(self, sample_content: dict[str, str]) -> None:
        brief = {"related_searches": ["NECK CREAM"]}
        result = _compute_related_searches_coverage(sample_content, brief)
        assert result["hit"] == 1

    def test_no_brief_returns_empty(self, sample_content: dict[str, str]) -> None:
        result = _compute_related_searches_coverage(sample_content, None)
        assert result == {"total": 0, "hit": 0, "missed": 0, "details": []}

    def test_empty_searches_list(self, sample_content: dict[str, str]) -> None:
        result = _compute_related_searches_coverage(sample_content, {"related_searches": []})
        assert result["total"] == 0

    def test_all_found(self) -> None:
        content = {
            "page_title": "neck cream",
            "meta_description": "sagging skin",
            "top_description": "",
            "bottom_description": "",
        }
        brief = {"related_searches": ["neck cream", "sagging skin"]}
        result = _compute_related_searches_coverage(content, brief)
        assert result["hit"] == 2
        assert result["missed"] == 0

    def test_html_stripped_in_bottom_desc(self) -> None:
        content = {
            "page_title": "",
            "meta_description": "",
            "top_description": "",
            "bottom_description": "<p>firming cream for neck</p>",
        }
        brief = {"related_searches": ["firming cream"]}
        result = _compute_related_searches_coverage(content, brief)
        assert result["hit"] == 1


# ===========================================================================
# 1c. Related Questions Coverage
# ===========================================================================


class TestRelatedQuestionsCoverage:
    """Tests for _compute_related_questions_coverage."""

    def test_question_answered_by_key_terms(self) -> None:
        content = {
            "page_title": "Best Neck Cream",
            "meta_description": "",
            "top_description": "Our cream is the best choice for your neck.",
            "bottom_description": "",
        }
        brief = {"related_questions": ["What is the best neck cream?"]}
        result = _compute_related_questions_coverage(content, brief)
        assert result["total"] == 1
        assert result["hit"] == 1  # key terms: "best", "neck", "cream" all present

    def test_question_not_answered(self) -> None:
        content = {
            "page_title": "Lip Gloss Collection",
            "meta_description": "Shop lip gloss",
            "top_description": "Beautiful lip gloss options.",
            "bottom_description": "",
        }
        brief = {"related_questions": ["What is the best neck cream?"]}
        result = _compute_related_questions_coverage(content, brief)
        assert result["hit"] == 0

    def test_partial_match_below_threshold(self) -> None:
        content = {
            "page_title": "Neck Care",
            "meta_description": "",
            "top_description": "",
            "bottom_description": "",
        }
        # key terms: "best", "neck", "cream" — only "neck" present = 33% < 60%
        brief = {"related_questions": ["What is the best neck cream?"]}
        result = _compute_related_questions_coverage(content, brief)
        assert result["hit"] == 0

    def test_no_brief_returns_empty(self) -> None:
        content = {"page_title": "", "meta_description": "", "top_description": "", "bottom_description": ""}
        result = _compute_related_questions_coverage(content, None)
        assert result == {"total": 0, "hit": 0, "missed": 0, "details": []}

    def test_empty_questions_list(self) -> None:
        content = {"page_title": "", "meta_description": "", "top_description": "", "bottom_description": ""}
        result = _compute_related_questions_coverage(content, {"related_questions": []})
        assert result["total"] == 0

    def test_multiple_questions_mixed(self) -> None:
        content = {
            "page_title": "Neck Firming Cream",
            "meta_description": "Best firming cream for sagging neck skin",
            "top_description": "Tighten and firm your neck skin.",
            "bottom_description": "<p>Our cream reduces wrinkles and firms sagging neck skin.</p>",
        }
        brief = {"related_questions": [
            "What is the best neck firming cream?",  # key terms: best, neck, firming, cream — all present
            "How to apply retinol serum?",  # key terms: apply, retinol, serum — none present
        ]}
        result = _compute_related_questions_coverage(content, brief)
        assert result["hit"] == 1
        assert result["missed"] == 1

    def test_details_include_key_terms(self) -> None:
        content = {
            "page_title": "Neck Cream",
            "meta_description": "Best neck cream",
            "top_description": "",
            "bottom_description": "",
        }
        brief = {"related_questions": ["What is the best neck cream?"]}
        result = _compute_related_questions_coverage(content, brief)
        detail = result["details"][0]
        assert "key_terms" in detail
        assert "matched_terms" in detail
        assert "match_ratio" in detail


# ===========================================================================
# 2. JSON Parsing
# ===========================================================================


class TestParseContentJson:
    """Tests for _parse_content_json."""

    def test_clean_json(self) -> None:
        """Well-formed JSON object parses successfully."""
        raw = json.dumps({"page_title": "Test", "meta_description": "Desc"})
        result = _parse_content_json(raw)
        assert result is not None
        assert result["page_title"] == "Test"

    def test_json_with_markdown_fencing(self) -> None:
        """JSON wrapped in ```json ... ``` should parse."""
        inner = json.dumps({"page_title": "Fenced"})
        raw = f"```json\n{inner}\n```"
        result = _parse_content_json(raw)
        assert result is not None
        assert result["page_title"] == "Fenced"

    def test_json_with_generic_fence(self) -> None:
        """JSON wrapped in ``` ... ``` (no language tag) should parse."""
        inner = json.dumps({"page_title": "Generic"})
        raw = f"```\n{inner}\n```"
        result = _parse_content_json(raw)
        assert result is not None
        assert result["page_title"] == "Generic"

    def test_json_with_leading_trailing_whitespace(self) -> None:
        """Whitespace around JSON should be handled."""
        raw = "   \n\n  " + json.dumps({"page_title": "Trimmed"}) + "  \n  "
        result = _parse_content_json(raw)
        assert result is not None
        assert result["page_title"] == "Trimmed"

    def test_invalid_json_returns_none(self) -> None:
        """Completely invalid JSON returns None."""
        assert _parse_content_json("this is not json at all") is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert _parse_content_json("") is None

    def test_json_array_returns_none(self) -> None:
        """A JSON array (not an object) returns None."""
        assert _parse_content_json('[1, 2, 3]') is None

    def test_json_embedded_in_text(self) -> None:
        """JSON object embedded in surrounding prose should be extracted."""
        inner = json.dumps({"page_title": "Embedded"})
        raw = f"Here is the response:\n{inner}\nHope that helps!"
        result = _parse_content_json(raw)
        assert result is not None
        assert result["page_title"] == "Embedded"

    def test_missing_keys_still_parses(self) -> None:
        """JSON without expected keys still parses (validation is caller's job)."""
        raw = json.dumps({"unexpected_key": "value"})
        result = _parse_content_json(raw)
        assert result is not None
        assert "page_title" not in result
        assert result["unexpected_key"] == "value"

    def test_nested_json_objects(self) -> None:
        """Nested structures should parse fine."""
        raw = json.dumps({"page_title": "Nested", "meta": {"nested": True}})
        result = _parse_content_json(raw)
        assert result is not None
        assert result["meta"]["nested"] is True


# ===========================================================================
# 3. Word Count Calculation
# ===========================================================================


class TestWordCount:
    """Tests for _count_words and _strip_html."""

    def test_basic_word_counting(self) -> None:
        assert _count_words("one two three") == 3

    def test_multiple_spaces(self) -> None:
        assert _count_words("one   two   three") == 3

    def test_empty_string(self) -> None:
        # "".split() => [], so len == 0
        assert _count_words("") == 0

    def test_single_word(self) -> None:
        assert _count_words("hello") == 1

    def test_strip_html_basic(self) -> None:
        assert _strip_html("<p>Hello</p>") == "Hello"

    def test_strip_html_nested(self) -> None:
        result = _strip_html("<div><h2>Title</h2><p>Body text</p></div>")
        assert "Title" in result
        assert "Body text" in result
        assert "<" not in result

    def test_strip_html_with_attributes(self) -> None:
        result = _strip_html('<a href="https://example.com" class="link">Click here</a>')
        assert result == "Click here"

    def test_strip_html_empty(self) -> None:
        assert _strip_html("") == ""

    def test_strip_html_no_tags(self) -> None:
        assert _strip_html("plain text") == "plain text"

    def test_html_stripped_word_count(self) -> None:
        """Word counting on HTML content should strip tags first.

        Note: _strip_html removes tags without inserting spaces, so adjacent
        tags like </h2><p> cause words to merge (e.g. "WordsThree").
        """
        html = "<h2>Two Words</h2> <p>Three more words here.</p>"
        plain = _strip_html(html)
        # Space between </h2> and <p> prevents word merging
        assert _count_words(plain) == 6


# ===========================================================================
# 4. Variant Persistence (file I/O)
# ===========================================================================


class TestVariantPersistence:
    """Tests for _load_variants, _save_variants."""

    def test_save_and_load_variants(self, variants_file: Path) -> None:
        """Save variants then load them back."""
        data = [
            {"label": "Variant A", "notes": "first"},
            {"label": "Variant B", "notes": "second"},
        ]
        _save_variants(data)
        loaded = _load_variants()
        assert len(loaded) == 2
        assert loaded[0]["label"] == "Variant A"
        assert loaded[1]["notes"] == "second"

    def test_load_missing_file(self, variants_file: Path) -> None:
        """Loading when file doesn't exist returns empty list."""
        # variants_file doesn't exist yet (tmp_path is fresh)
        assert _load_variants() == []

    def test_load_corrupt_json(self, variants_file: Path) -> None:
        """Corrupt JSON on disk returns empty list."""
        variants_file.write_text("{not valid json!!")
        assert _load_variants() == []

    def test_load_non_array_json(self, variants_file: Path) -> None:
        """If file contains an object instead of array, return empty list."""
        variants_file.write_text('{"key": "value"}')
        assert _load_variants() == []

    def test_save_overwrites_existing(self, variants_file: Path) -> None:
        """Saving replaces previous content entirely."""
        _save_variants([{"label": "old"}])
        _save_variants([{"label": "new"}])
        loaded = _load_variants()
        assert len(loaded) == 1
        assert loaded[0]["label"] == "new"


# ===========================================================================
# 5. API Endpoints (with mocked dependencies)
# ===========================================================================


@dataclass
class FakeCompletionResult:
    """Mimics CompletionResult from the claude integration."""
    success: bool
    text: str | None = None
    error: str | None = None
    stop_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    status_code: int | None = None
    duration_ms: float = 0.0
    request_id: str | None = None


@pytest.fixture
def _patch_cached_context(
    mock_page_dict: dict[str, Any],
    mock_brief_dict: dict[str, Any],
    mock_brief_orm: MagicMock,
) -> Any:
    """Patch module-level cached context so endpoints work without a DB."""
    with (
        patch("server._cached_page", mock_page_dict),
        patch("server._cached_brief", mock_brief_dict),
        patch("server._cached_brief_orm", mock_brief_orm),
        patch("server._cached_keyword", "neck cream"),
        patch("server._cached_brand_config", {"brand_name": "Dr. Brandt"}),
    ):
        yield


@pytest.fixture
def _patch_no_context() -> Any:
    """Patch module-level cached context to None (no data loaded)."""
    with (
        patch("server._cached_page", None),
        patch("server._cached_brief", None),
        patch("server._cached_brief_orm", None),
        patch("server._cached_keyword", ""),
        patch("server._cached_brand_config", None),
    ):
        yield


class TestGetContextEndpoint:
    """Tests for GET /api/context."""

    @pytest.mark.asyncio
    async def test_returns_correct_shape(
        self,
        _patch_cached_context: Any,
    ) -> None:
        """Should return keyword, page info, brief summary, prompts."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/context")

        assert resp.status_code == 200
        body = resp.json()
        assert body["keyword"] == "neck cream"
        assert "page" in body
        assert body["page"]["url"] == "https://example.com/neck-cream"
        assert "brief_summary" in body
        assert "system_prompt" in body
        assert "fixed_user_prompt" in body
        assert "default_variants" in body
        assert len(body["default_variants"]) == 3

    @pytest.mark.asyncio
    async def test_returns_500_when_no_data(
        self,
        _patch_no_context: Any,
    ) -> None:
        """Should return 500 when no page/brief is loaded."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/context")

        assert resp.status_code == 500
        body = resp.json()
        assert "error" in body


class TestGenerateEndpoint:
    """Tests for POST /api/generate."""

    @pytest.mark.asyncio
    async def test_successful_generation(
        self,
        _patch_cached_context: Any,
        fake_claude_response: dict[str, str],
    ) -> None:
        """Should return aggregated stats across runs."""
        mock_result = FakeCompletionResult(
            success=True,
            text=json.dumps(fake_claude_response),
        )
        mock_client_instance = AsyncMock()
        mock_client_instance.complete = AsyncMock(return_value=mock_result)
        mock_client_instance.close = AsyncMock()

        with patch("server.ClaudeClient", return_value=mock_client_instance):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                timeout=60.0,
            ) as client:
                resp = await client.post(
                    "/api/generate",
                    json={
                        "task_section_text": "## Task\nReturn JSON.",
                        "variant_label": "Test Variant",
                        "num_runs": 2,
                    },
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["num_runs"] == 2
        assert body["successful_runs"] == 2
        assert body["variant_label"] == "Test Variant"
        assert "avg_word_count" in body
        assert body["avg_word_count"]["total"] > 0
        assert "avg_lsi_coverage" in body
        assert "shortest" in body
        assert "longest" in body
        assert body["shortest"]["content"]["page_title"] == "Neck Cream for Sagging Skin"
        assert len(body["all_runs"]) == 2

    @pytest.mark.asyncio
    async def test_all_runs_fail(
        self,
        _patch_cached_context: Any,
    ) -> None:
        """Should return 502 when all runs fail."""
        mock_client_instance = AsyncMock()
        mock_client_instance.complete = AsyncMock(
            side_effect=Exception("Connection timeout")
        )
        mock_client_instance.close = AsyncMock()

        with patch("server.ClaudeClient", return_value=mock_client_instance):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                timeout=60.0,
            ) as client:
                resp = await client.post(
                    "/api/generate",
                    json={
                        "task_section_text": "## Task\nReturn JSON.",
                        "num_runs": 2,
                    },
                )

        assert resp.status_code == 502
        body = resp.json()
        assert "All runs failed" in body["error"]

    @pytest.mark.asyncio
    async def test_partial_failures(
        self,
        _patch_cached_context: Any,
        fake_claude_response: dict[str, str],
    ) -> None:
        """Some runs succeed, some fail — should return aggregated successes."""
        good_result = FakeCompletionResult(
            success=True,
            text=json.dumps(fake_claude_response),
        )
        bad_result = FakeCompletionResult(
            success=False,
            error="Rate limited",
        )
        mock_client_instance = AsyncMock()
        # Alternate: first call succeeds, second fails
        mock_client_instance.complete = AsyncMock(
            side_effect=[good_result, bad_result]
        )
        mock_client_instance.close = AsyncMock()

        with patch("server.ClaudeClient", return_value=mock_client_instance):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                timeout=60.0,
            ) as client:
                resp = await client.post(
                    "/api/generate",
                    json={
                        "task_section_text": "## Task\nReturn JSON.",
                        "num_runs": 2,
                    },
                )

        assert resp.status_code == 200
        body = resp.json()
        assert body["successful_runs"] == 1
        assert body["failed_runs"] == 1

    @pytest.mark.asyncio
    async def test_generate_with_no_context_loaded(
        self,
        _patch_no_context: Any,
    ) -> None:
        """Should return 500 when no page/brief is cached."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(
                "/api/generate",
                json={
                    "task_section_text": "## Output Format\nReturn JSON.",
                },
            )

        assert resp.status_code == 500
        assert "error" in resp.json()


class TestVariantEndpoints:
    """Tests for /api/variants CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_list_variants_empty(self, variants_file: Path) -> None:
        """GET /api/variants returns empty list when no variants saved."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/api/variants")

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_save_and_list_variant(self, variants_file: Path) -> None:
        """POST /api/variants saves, then GET returns it."""
        payload = {
            "label": "My Variant",
            "task_section_text": "## Output Format\nJSON please.",
            "result": {"content": {"page_title": "Test"}},
            "notes": "Looks good.",
        }
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            post_resp = await client.post("/api/variants", json=payload)
            assert post_resp.status_code == 200
            post_body = post_resp.json()
            assert "id" in post_body
            assert post_body["saved"]["label"] == "My Variant"
            assert "timestamp" in post_body["saved"]

            # Verify it appears in GET
            get_resp = await client.get("/api/variants")
            assert get_resp.status_code == 200
            variants = get_resp.json()
            assert len(variants) == 1
            assert variants[0]["label"] == "My Variant"
            assert variants[0]["notes"] == "Looks good."

    @pytest.mark.asyncio
    async def test_save_multiple_variants(self, variants_file: Path) -> None:
        """Saving multiple variants appends correctly."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            for i in range(3):
                resp = await client.post(
                    "/api/variants",
                    json={
                        "label": f"Variant {i}",
                        "task_section_text": f"Format {i}",
                        "result": {},
                    },
                )
                assert resp.status_code == 200
                assert "id" in resp.json()

            get_resp = await client.get("/api/variants")
            assert len(get_resp.json()) == 3

    @pytest.mark.asyncio
    async def test_delete_variant(self, variants_file: Path) -> None:
        """DELETE /api/variants/{id} removes the correct variant."""
        # Seed two variants with IDs
        _save_variants([
            {"id": "aaa111", "label": "Keep", "task_section_text": "a", "result": {}},
            {"id": "bbb222", "label": "Delete Me", "task_section_text": "b", "result": {}},
        ])

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            del_resp = await client.delete("/api/variants/bbb222")
            assert del_resp.status_code == 200
            assert del_resp.json()["deleted"]["label"] == "Delete Me"

            # Verify only one remains
            get_resp = await client.get("/api/variants")
            remaining = get_resp.json()
            assert len(remaining) == 1
            assert remaining[0]["label"] == "Keep"

    @pytest.mark.asyncio
    async def test_delete_variant_not_found(
        self,
        variants_file: Path,
    ) -> None:
        """DELETE with non-existent ID returns 404."""
        _save_variants([{"id": "aaa111", "label": "Only One", "result": {}}])

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.delete("/api/variants/nonexistent")
            assert resp.status_code == 404
            assert "not found" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_delete_from_empty_list(self, variants_file: Path) -> None:
        """DELETE on empty variants list returns 404."""
        _save_variants([])

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.delete("/api/variants/anything")
            assert resp.status_code == 404
