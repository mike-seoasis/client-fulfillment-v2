"""Unit tests for change detection algorithm.

Tests cover:
- ContentHasher: Content hash computation with various inputs
- ChangeDetector: Page comparison and change detection
- ChangeSummary: Summary generation and significance detection
- Edge cases: Empty inputs, None values, large datasets
"""

import pytest

from app.utils.change_detection import (
    VALID_CHANGE_TYPES,
    ChangeDetector,
    ChangeSummary,
    ChangeType,
    ContentHasher,
    PageChange,
    PageSnapshot,
    compute_content_hash,
    detect_changes,
    get_change_detector,
    get_content_hasher,
)


class TestContentHasher:
    """Tests for ContentHasher class."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        hasher = ContentHasher()
        assert hasher.max_content_length == 5000

    def test_init_custom_length(self) -> None:
        """Test initialization with custom content length."""
        hasher = ContentHasher(max_content_length=1000)
        assert hasher.max_content_length == 1000

    def test_compute_hash_all_fields(self) -> None:
        """Test hash computation with all fields."""
        hasher = ContentHasher()
        result = hasher.compute_hash(
            title="Test Title",
            h1="Test Heading",
            meta_description="Test description",
            body_text="Test body content",
        )

        assert result is not None
        assert len(result) == 32  # MD5 hex digest length
        assert result.isalnum()

    def test_compute_hash_empty_fields(self) -> None:
        """Test hash computation with empty fields."""
        hasher = ContentHasher()
        result = hasher.compute_hash()

        assert result is not None
        assert len(result) == 32

    def test_compute_hash_none_fields(self) -> None:
        """Test hash computation with None fields."""
        hasher = ContentHasher()
        result = hasher.compute_hash(
            title=None,
            h1=None,
            meta_description=None,
            body_text=None,
        )

        assert result is not None
        assert len(result) == 32

    def test_compute_hash_partial_fields(self) -> None:
        """Test hash computation with some fields."""
        hasher = ContentHasher()
        result = hasher.compute_hash(
            title="Test Title",
            body_text="Test body",
        )

        assert result is not None
        assert len(result) == 32

    def test_compute_hash_consistency(self) -> None:
        """Test that same input produces same hash."""
        hasher = ContentHasher()
        hash1 = hasher.compute_hash(
            title="Title",
            h1="Heading",
            meta_description="Description",
            body_text="Body",
        )
        hash2 = hasher.compute_hash(
            title="Title",
            h1="Heading",
            meta_description="Description",
            body_text="Body",
        )

        assert hash1 == hash2

    def test_compute_hash_different_inputs(self) -> None:
        """Test that different inputs produce different hashes."""
        hasher = ContentHasher()
        hash1 = hasher.compute_hash(title="Title A")
        hash2 = hasher.compute_hash(title="Title B")

        assert hash1 != hash2

    def test_compute_hash_whitespace_normalization(self) -> None:
        """Test whitespace normalization in hashing."""
        hasher = ContentHasher(include_whitespace=False)
        hash1 = hasher.compute_hash(title="Test  Title")
        hash2 = hasher.compute_hash(title="Test Title")

        assert hash1 == hash2

    def test_compute_hash_case_normalization(self) -> None:
        """Test case normalization in hashing."""
        hasher = ContentHasher()
        hash1 = hasher.compute_hash(title="Test Title")
        hash2 = hasher.compute_hash(title="test title")

        assert hash1 == hash2

    def test_compute_hash_body_truncation(self) -> None:
        """Test body text truncation."""
        hasher = ContentHasher(max_content_length=100)
        long_body = "x" * 1000

        # Hash with truncated body
        hash1 = hasher.compute_hash(body_text=long_body)

        # Hash with exactly max length body
        hash2 = hasher.compute_hash(body_text="x" * 100)

        assert hash1 == hash2

    def test_compute_hash_with_ids(self) -> None:
        """Test hash computation with logging IDs."""
        hasher = ContentHasher()
        result = hasher.compute_hash(
            title="Test",
            project_id="proj-123",
            page_id="page-456",
        )

        assert result is not None
        assert len(result) == 32

    def test_compute_hash_from_dict(self) -> None:
        """Test hash computation from dictionary."""
        hasher = ContentHasher()

        data = {
            "title": "Test Title",
            "h1": "Test Heading",
            "meta_description": "Test description",
            "body_text": "Test body",
        }

        result = hasher.compute_hash_from_dict(data)
        expected = hasher.compute_hash(
            title="Test Title",
            h1="Test Heading",
            meta_description="Test description",
            body_text="Test body",
        )

        assert result == expected

    def test_compute_hash_from_dict_alternative_keys(self) -> None:
        """Test hash computation from dict with alternative keys."""
        hasher = ContentHasher()

        data = {
            "page_title": "Test Title",
            "heading": "Test Heading",
            "description": "Test description",
            "content": "Test body",
        }

        result = hasher.compute_hash_from_dict(data)

        assert result is not None
        assert len(result) == 32

    def test_compute_hash_from_dict_with_headings_list(self) -> None:
        """Test hash from dict with headings list."""
        hasher = ContentHasher()

        data = {
            "title": "Test Title",
            "headings": ["First Heading", "Second Heading"],
            "body_text": "Test body",
        }

        result = hasher.compute_hash_from_dict(data)

        assert result is not None
        assert len(result) == 32

    def test_compute_hash_preserves_whitespace_when_enabled(self) -> None:
        """Test that whitespace is preserved when include_whitespace=True."""
        hasher = ContentHasher(include_whitespace=True)
        hash1 = hasher.compute_hash(title="Test  Title")
        hash2 = hasher.compute_hash(title="Test Title")

        assert hash1 != hash2


class TestPageSnapshot:
    """Tests for PageSnapshot dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic PageSnapshot creation."""
        snapshot = PageSnapshot(
            url="https://example.com/page",
            content_hash="abc123",
        )

        assert snapshot.url == "https://example.com/page"
        assert snapshot.content_hash == "abc123"
        assert snapshot.title is None
        assert snapshot.page_id is None

    def test_full_creation(self) -> None:
        """Test PageSnapshot with all fields."""
        snapshot = PageSnapshot(
            url="https://example.com/page",
            content_hash="abc123",
            title="Test Page",
            page_id="page-456",
        )

        assert snapshot.title == "Test Page"
        assert snapshot.page_id == "page-456"

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        snapshot = PageSnapshot(
            url="https://example.com/page",
            content_hash="abc123",
            title="Test Page",
            page_id="page-456",
        )

        result = snapshot.to_dict()

        assert result["url"] == "https://example.com/page"
        assert result["content_hash"] == "abc123"
        assert result["title"] == "Test Page"
        assert result["page_id"] == "page-456"

    def test_to_dict_truncates_long_title(self) -> None:
        """Test that long titles are truncated in dict."""
        long_title = "x" * 200
        snapshot = PageSnapshot(
            url="https://example.com/page",
            content_hash="abc123",
            title=long_title,
        )

        result = snapshot.to_dict()

        assert len(result["title"]) == 100


class TestPageChange:
    """Tests for PageChange dataclass."""

    def test_new_page_change(self) -> None:
        """Test PageChange for new page."""
        change = PageChange(
            url="https://example.com/new",
            change_type=ChangeType.NEW,
            new_hash="abc123",
        )

        assert change.change_type == ChangeType.NEW
        assert change.old_hash is None
        assert change.new_hash == "abc123"

    def test_removed_page_change(self) -> None:
        """Test PageChange for removed page."""
        change = PageChange(
            url="https://example.com/removed",
            change_type=ChangeType.REMOVED,
            old_hash="abc123",
        )

        assert change.change_type == ChangeType.REMOVED
        assert change.old_hash == "abc123"
        assert change.new_hash is None

    def test_changed_page_change(self) -> None:
        """Test PageChange for changed page."""
        change = PageChange(
            url="https://example.com/changed",
            change_type=ChangeType.CHANGED,
            old_hash="old123",
            new_hash="new456",
        )

        assert change.change_type == ChangeType.CHANGED
        assert change.old_hash == "old123"
        assert change.new_hash == "new456"

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        change = PageChange(
            url="https://example.com/page",
            change_type=ChangeType.CHANGED,
            old_hash="old",
            new_hash="new",
            title="Test",
            page_id="page-123",
        )

        result = change.to_dict()

        assert result["change_type"] == "changed"
        assert result["url"] == "https://example.com/page"


class TestChangeSummary:
    """Tests for ChangeSummary dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic ChangeSummary creation."""
        summary = ChangeSummary(
            crawl_id="crawl-new",
            compared_to="crawl-old",
        )

        assert summary.crawl_id == "crawl-new"
        assert summary.compared_to == "crawl-old"
        assert summary.computed_at is not None

    def test_total_pages(self) -> None:
        """Test total_pages property."""
        summary = ChangeSummary(
            crawl_id="new",
            compared_to="old",
            new_pages=5,
            changed_pages=3,
            unchanged_pages=10,
        )

        assert summary.total_pages == 18  # 5 + 3 + 10

    def test_total_changes(self) -> None:
        """Test total_changes property."""
        summary = ChangeSummary(
            crawl_id="new",
            compared_to="old",
            new_pages=5,
            removed_pages=2,
            changed_pages=3,
        )

        assert summary.total_changes == 10  # 5 + 2 + 3

    def test_change_percentage(self) -> None:
        """Test change_percentage calculation."""
        summary = ChangeSummary(
            crawl_id="new",
            compared_to="old",
            changed_pages=10,
            unchanged_pages=90,
        )

        assert summary.change_percentage == 0.1  # 10%

    def test_change_percentage_zero_pages(self) -> None:
        """Test change_percentage with no comparable pages."""
        summary = ChangeSummary(
            crawl_id="new",
            compared_to="old",
            changed_pages=0,
            unchanged_pages=0,
        )

        assert summary.change_percentage == 0.0

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        summary = ChangeSummary(
            crawl_id="new",
            compared_to="old",
            new_pages=5,
            removed_pages=2,
            changed_pages=10,
            unchanged_pages=83,
            new_page_urls=["url1", "url2"],
            removed_page_urls=["url3"],
            changed_page_urls=["url4", "url5"],
            is_significant=True,
        )

        result = summary.to_dict()

        assert result["crawl_id"] == "new"
        assert result["compared_to"] == "old"
        assert result["summary"]["new_pages"] == 5
        assert result["summary"]["removed_pages"] == 2
        assert result["summary"]["changed_pages"] == 10
        assert result["summary"]["unchanged_pages"] == 83
        assert result["is_significant"] is True
        assert result["total_pages"] == 98
        assert result["total_changes"] == 17

    def test_to_dict_truncates_urls(self) -> None:
        """Test that URL lists are truncated in dict."""
        urls = [f"url{i}" for i in range(200)]
        summary = ChangeSummary(
            crawl_id="new",
            compared_to="old",
            new_page_urls=urls,
        )

        result = summary.to_dict()

        assert len(result["new_page_urls"]) == 100


class TestChangeDetector:
    """Tests for ChangeDetector class."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        detector = ChangeDetector()
        assert detector.new_page_threshold == 5
        assert detector.change_percentage_threshold == 0.10

    def test_init_custom_thresholds(self) -> None:
        """Test initialization with custom thresholds."""
        detector = ChangeDetector(
            new_page_threshold=10,
            change_percentage_threshold=0.20,
        )

        assert detector.new_page_threshold == 10
        assert detector.change_percentage_threshold == 0.20

    def test_init_invalid_new_page_threshold(self) -> None:
        """Test initialization with invalid new_page_threshold."""
        with pytest.raises(ValueError, match="non-negative"):
            ChangeDetector(new_page_threshold=-1)

    def test_init_invalid_change_percentage_threshold(self) -> None:
        """Test initialization with invalid change_percentage_threshold."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            ChangeDetector(change_percentage_threshold=1.5)

    def test_compare_empty_crawls(self) -> None:
        """Test comparison of empty crawls."""
        detector = ChangeDetector()

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=[],
            current_pages=[],
        )

        assert result.new_pages == 0
        assert result.removed_pages == 0
        assert result.changed_pages == 0
        assert result.unchanged_pages == 0

    def test_compare_all_new_pages(self) -> None:
        """Test comparison where all pages are new."""
        detector = ChangeDetector()

        current = [
            PageSnapshot(url="url1", content_hash="hash1"),
            PageSnapshot(url="url2", content_hash="hash2"),
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=[],
            current_pages=current,
        )

        assert result.new_pages == 2
        assert result.removed_pages == 0
        assert result.changed_pages == 0
        assert "url1" in result.new_page_urls
        assert "url2" in result.new_page_urls

    def test_compare_all_removed_pages(self) -> None:
        """Test comparison where all pages are removed."""
        detector = ChangeDetector()

        previous = [
            PageSnapshot(url="url1", content_hash="hash1"),
            PageSnapshot(url="url2", content_hash="hash2"),
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=[],
        )

        assert result.new_pages == 0
        assert result.removed_pages == 2
        assert "url1" in result.removed_page_urls
        assert "url2" in result.removed_page_urls

    def test_compare_unchanged_pages(self) -> None:
        """Test comparison with unchanged pages."""
        detector = ChangeDetector()

        pages = [
            PageSnapshot(url="url1", content_hash="hash1"),
            PageSnapshot(url="url2", content_hash="hash2"),
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=pages,
            current_pages=pages,
        )

        assert result.new_pages == 0
        assert result.removed_pages == 0
        assert result.changed_pages == 0
        assert result.unchanged_pages == 2

    def test_compare_changed_pages(self) -> None:
        """Test comparison with changed pages."""
        detector = ChangeDetector()

        previous = [
            PageSnapshot(url="url1", content_hash="hash1"),
            PageSnapshot(url="url2", content_hash="hash2"),
        ]

        current = [
            PageSnapshot(url="url1", content_hash="hash1-modified"),
            PageSnapshot(url="url2", content_hash="hash2-modified"),
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        assert result.changed_pages == 2
        assert result.unchanged_pages == 0
        assert "url1" in result.changed_page_urls
        assert "url2" in result.changed_page_urls

    def test_compare_mixed_changes(self) -> None:
        """Test comparison with mixed changes."""
        detector = ChangeDetector()

        previous = [
            PageSnapshot(url="unchanged", content_hash="hash1"),
            PageSnapshot(url="changed", content_hash="hash2"),
            PageSnapshot(url="removed", content_hash="hash3"),
        ]

        current = [
            PageSnapshot(url="unchanged", content_hash="hash1"),
            PageSnapshot(url="changed", content_hash="hash2-modified"),
            PageSnapshot(url="new", content_hash="hash4"),
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        assert result.new_pages == 1
        assert result.removed_pages == 1
        assert result.changed_pages == 1
        assert result.unchanged_pages == 1
        assert "new" in result.new_page_urls
        assert "removed" in result.removed_page_urls
        assert "changed" in result.changed_page_urls

    def test_significance_by_new_pages(self) -> None:
        """Test significance detection by new page count."""
        detector = ChangeDetector(new_page_threshold=5)

        current = [
            PageSnapshot(url=f"url{i}", content_hash=f"hash{i}")
            for i in range(5)
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=[],
            current_pages=current,
        )

        assert result.is_significant is True

    def test_significance_below_new_page_threshold(self) -> None:
        """Test non-significance when below new page threshold."""
        detector = ChangeDetector(new_page_threshold=5)

        current = [
            PageSnapshot(url=f"url{i}", content_hash=f"hash{i}")
            for i in range(4)
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=[],
            current_pages=current,
        )

        assert result.is_significant is False

    def test_significance_by_change_percentage(self) -> None:
        """Test significance detection by change percentage."""
        detector = ChangeDetector(change_percentage_threshold=0.10)

        previous = [
            PageSnapshot(url=f"url{i}", content_hash=f"hash{i}")
            for i in range(10)
        ]

        current = [
            PageSnapshot(url=f"url{i}", content_hash=f"hash{i}-modified" if i == 0 else f"hash{i}")
            for i in range(10)
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        # 1 changed out of 10 = 10% = threshold
        assert result.is_significant is True

    def test_significance_below_change_percentage(self) -> None:
        """Test non-significance when below change percentage."""
        detector = ChangeDetector(change_percentage_threshold=0.20)

        previous = [
            PageSnapshot(url=f"url{i}", content_hash=f"hash{i}")
            for i in range(10)
        ]

        current = [
            PageSnapshot(url=f"url{i}", content_hash=f"hash{i}-modified" if i == 0 else f"hash{i}")
            for i in range(10)
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        # 1 changed out of 10 = 10% < 20% threshold
        assert result.is_significant is False

    def test_compare_with_project_id(self) -> None:
        """Test comparison with project_id for logging."""
        detector = ChangeDetector()

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=[],
            current_pages=[],
            project_id="proj-123",
        )

        assert result.crawl_id == "new"

    def test_compare_from_dicts(self) -> None:
        """Test comparison from dictionary representations."""
        detector = ChangeDetector()

        previous = [
            {"normalized_url": "url1", "content_hash": "hash1", "title": "Page 1", "id": "id1"},
            {"normalized_url": "url2", "content_hash": "hash2", "title": "Page 2", "id": "id2"},
        ]

        current = [
            {"normalized_url": "url1", "content_hash": "hash1-modified", "title": "Page 1 Updated", "id": "id1"},
            {"normalized_url": "url3", "content_hash": "hash3", "title": "Page 3", "id": "id3"},
        ]

        result = detector.compare_from_dicts(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        assert result.new_pages == 1
        assert result.removed_pages == 1
        assert result.changed_pages == 1
        assert result.unchanged_pages == 0

    def test_compare_from_dicts_custom_keys(self) -> None:
        """Test comparison from dicts with custom keys."""
        detector = ChangeDetector()

        previous = [
            {"url": "url1", "hash": "hash1"},
        ]

        current = [
            {"url": "url1", "hash": "hash1-modified"},
        ]

        result = detector.compare_from_dicts(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
            url_key="url",
            hash_key="hash",
        )

        assert result.changed_pages == 1

    def test_compare_changes_list(self) -> None:
        """Test that changes list contains all changes."""
        detector = ChangeDetector()

        previous = [
            PageSnapshot(url="unchanged", content_hash="hash1"),
            PageSnapshot(url="changed", content_hash="hash2"),
            PageSnapshot(url="removed", content_hash="hash3"),
        ]

        current = [
            PageSnapshot(url="unchanged", content_hash="hash1"),
            PageSnapshot(url="changed", content_hash="hash2-modified"),
            PageSnapshot(url="new", content_hash="hash4"),
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        # Should have 4 changes (1 new, 1 removed, 1 changed, 1 unchanged)
        assert len(result.changes) == 4

        # Check change types
        change_types = {c.change_type for c in result.changes}
        assert ChangeType.NEW in change_types
        assert ChangeType.REMOVED in change_types
        assert ChangeType.CHANGED in change_types
        assert ChangeType.UNCHANGED in change_types

    def test_compare_none_hash_treated_as_change(self) -> None:
        """Test that None hash vs non-None hash is detected as change."""
        detector = ChangeDetector()

        previous = [
            PageSnapshot(url="url1", content_hash=None),
        ]

        current = [
            PageSnapshot(url="url1", content_hash="hash1"),
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        assert result.changed_pages == 1

    def test_compare_both_none_hash_is_unchanged(self) -> None:
        """Test that both None hashes is treated as unchanged."""
        detector = ChangeDetector()

        previous = [
            PageSnapshot(url="url1", content_hash=None),
        ]

        current = [
            PageSnapshot(url="url1", content_hash=None),
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        assert result.unchanged_pages == 1


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_get_content_hasher_singleton(self) -> None:
        """Test that get_content_hasher returns singleton."""
        hasher1 = get_content_hasher()
        hasher2 = get_content_hasher()

        assert hasher1 is hasher2

    def test_get_change_detector_singleton(self) -> None:
        """Test that get_change_detector returns singleton."""
        detector1 = get_change_detector()
        detector2 = get_change_detector()

        assert detector1 is detector2

    def test_compute_content_hash(self) -> None:
        """Test compute_content_hash function."""
        result = compute_content_hash(
            title="Test Title",
            h1="Test Heading",
            meta_description="Test description",
            body_text="Test body",
        )

        assert result is not None
        assert len(result) == 32

    def test_detect_changes(self) -> None:
        """Test detect_changes function."""
        previous = [
            PageSnapshot(url="url1", content_hash="hash1"),
        ]

        current = [
            PageSnapshot(url="url1", content_hash="hash1-modified"),
            PageSnapshot(url="url2", content_hash="hash2"),
        ]

        result = detect_changes(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        assert result.new_pages == 1
        assert result.changed_pages == 1


class TestChangeType:
    """Tests for ChangeType enum."""

    def test_valid_change_types(self) -> None:
        """Test VALID_CHANGE_TYPES constant."""
        assert "new" in VALID_CHANGE_TYPES
        assert "removed" in VALID_CHANGE_TYPES
        assert "changed" in VALID_CHANGE_TYPES
        assert "unchanged" in VALID_CHANGE_TYPES

    def test_change_type_values(self) -> None:
        """Test ChangeType enum values."""
        assert ChangeType.NEW.value == "new"
        assert ChangeType.REMOVED.value == "removed"
        assert ChangeType.CHANGED.value == "changed"
        assert ChangeType.UNCHANGED.value == "unchanged"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_large_number_of_pages(self) -> None:
        """Test comparison with large number of pages."""
        detector = ChangeDetector()

        previous = [
            PageSnapshot(url=f"url{i}", content_hash=f"hash{i}")
            for i in range(1000)
        ]

        current = [
            PageSnapshot(url=f"url{i}", content_hash=f"hash{i}-modified" if i < 100 else f"hash{i}")
            for i in range(1000)
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        assert result.changed_pages == 100
        assert result.unchanged_pages == 900

    def test_unicode_content_hash(self) -> None:
        """Test hash computation with unicode content."""
        hasher = ContentHasher()

        result = hasher.compute_hash(
            title="日本語タイトル",
            h1="中文标题",
            meta_description="Descripción en español",
            body_text="Контент на русском языке",
        )

        assert result is not None
        assert len(result) == 32

    def test_special_characters_in_content(self) -> None:
        """Test hash computation with special characters."""
        hasher = ContentHasher()

        result = hasher.compute_hash(
            title="Title with <html> & \"quotes\"",
            body_text="Body with\n\ttabs and newlines",
        )

        assert result is not None
        assert len(result) == 32

    def test_duplicate_urls_in_pages(self) -> None:
        """Test comparison handles duplicate URLs (last one wins)."""
        detector = ChangeDetector()

        previous = [
            PageSnapshot(url="url1", content_hash="hash1"),
            PageSnapshot(url="url1", content_hash="hash1-dup"),  # Duplicate
        ]

        current = [
            PageSnapshot(url="url1", content_hash="hash1-dup"),  # Matches second
        ]

        result = detector.compare(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        # Last duplicate wins, so should be unchanged
        assert result.unchanged_pages == 1

    def test_empty_url_filtered_in_compare_from_dicts(self) -> None:
        """Test that empty URLs are filtered in compare_from_dicts."""
        detector = ChangeDetector()

        previous = [
            {"normalized_url": "url1", "content_hash": "hash1"},
            {"normalized_url": "", "content_hash": "hash2"},  # Empty URL
        ]

        current = [
            {"normalized_url": "url1", "content_hash": "hash1"},
        ]

        result = detector.compare_from_dicts(
            crawl_id="new",
            previous_crawl_id="old",
            previous_pages=previous,
            current_pages=current,
        )

        # Empty URL page should be filtered out
        assert result.unchanged_pages == 1
        assert result.removed_pages == 0
