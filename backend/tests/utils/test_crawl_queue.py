"""Unit tests for URLPriorityQueue."""

import pytest

from app.utils.crawl_queue import (
    QueuedURL,
    URLPriority,
    URLPriorityQueue,
)


class TestURLPriority:
    """Tests for URLPriority enum."""

    def test_priority_values(self) -> None:
        """Test priority values are ordered correctly."""
        assert URLPriority.HOMEPAGE == 0
        assert URLPriority.INCLUDE == 1
        assert URLPriority.OTHER == 2

    def test_priority_ordering(self) -> None:
        """Test that HOMEPAGE < INCLUDE < OTHER."""
        assert URLPriority.HOMEPAGE < URLPriority.INCLUDE
        assert URLPriority.INCLUDE < URLPriority.OTHER
        assert URLPriority.HOMEPAGE < URLPriority.OTHER


class TestQueuedURL:
    """Tests for QueuedURL dataclass."""

    def test_queued_url_creation(self) -> None:
        """Test creating a QueuedURL."""
        queued = QueuedURL(
            priority=0,
            depth=1,
            timestamp=1000.0,
            url="https://example.com/page",
            normalized_url="https://example.com/page",
            parent_url="https://example.com",
        )
        assert queued.priority == 0
        assert queued.depth == 1
        assert queued.url == "https://example.com/page"
        assert queued.parent_url == "https://example.com"

    def test_queued_url_ordering_by_priority(self) -> None:
        """Test QueuedURLs are ordered by priority first."""
        homepage = QueuedURL(
            priority=0, depth=0, timestamp=100.0,
            url="https://example.com", normalized_url="https://example.com",
        )
        include = QueuedURL(
            priority=1, depth=0, timestamp=50.0,  # Earlier timestamp
            url="https://example.com/products", normalized_url="https://example.com/products",
        )
        other = QueuedURL(
            priority=2, depth=0, timestamp=25.0,  # Even earlier
            url="https://example.com/about", normalized_url="https://example.com/about",
        )

        # Sort should order by priority, not timestamp
        sorted_urls = sorted([other, include, homepage])
        assert sorted_urls[0].priority == 0  # homepage first
        assert sorted_urls[1].priority == 1  # include second
        assert sorted_urls[2].priority == 2  # other last

    def test_queued_url_ordering_by_depth(self) -> None:
        """Test same-priority URLs are ordered by depth."""
        shallow = QueuedURL(
            priority=2, depth=1, timestamp=100.0,
            url="https://example.com/a", normalized_url="https://example.com/a",
        )
        deep = QueuedURL(
            priority=2, depth=3, timestamp=50.0,
            url="https://example.com/b", normalized_url="https://example.com/b",
        )

        sorted_urls = sorted([deep, shallow])
        assert sorted_urls[0].depth == 1  # shallow first
        assert sorted_urls[1].depth == 3  # deep second

    def test_queued_url_ordering_fifo(self) -> None:
        """Test same priority/depth URLs are FIFO by timestamp."""
        first = QueuedURL(
            priority=2, depth=1, timestamp=100.0,
            url="https://example.com/a", normalized_url="https://example.com/a",
        )
        second = QueuedURL(
            priority=2, depth=1, timestamp=200.0,
            url="https://example.com/b", normalized_url="https://example.com/b",
        )

        sorted_urls = sorted([second, first])
        assert sorted_urls[0].timestamp == 100.0  # first added
        assert sorted_urls[1].timestamp == 200.0  # second added


class TestURLPriorityQueueInit:
    """Tests for URLPriorityQueue initialization."""

    def test_init_with_start_url(self) -> None:
        """Test basic initialization with start URL."""
        queue = URLPriorityQueue(start_url="https://example.com")
        assert len(queue) == 1
        assert queue.start_url == "https://example.com"
        assert queue.start_domain == "example.com"

    def test_init_empty_start_url_raises(self) -> None:
        """Test empty start URL raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            URLPriorityQueue(start_url="")

    def test_init_whitespace_start_url_raises(self) -> None:
        """Test whitespace-only start URL raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            URLPriorityQueue(start_url="   ")

    def test_init_invalid_start_url_raises(self) -> None:
        """Test invalid start URL raises ValueError."""
        with pytest.raises(ValueError):
            URLPriorityQueue(start_url="not-a-url")

    def test_init_with_patterns(self) -> None:
        """Test initialization with include/exclude patterns."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            include_patterns=["/products/*"],
            exclude_patterns=["/admin/*"],
        )
        stats = queue.get_stats()
        assert stats["include_patterns"] == ["/products/*"]
        assert stats["exclude_patterns"] == ["/admin/*"]

    def test_start_url_added_as_homepage_priority(self) -> None:
        """Test start URL is added with HOMEPAGE priority."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queued = queue.pop()
        assert queued is not None
        assert queued.priority == URLPriority.HOMEPAGE
        assert queued.depth == 0


class TestURLPriorityQueueAdd:
    """Tests for adding URLs to the queue."""

    def test_add_url(self) -> None:
        """Test adding a URL."""
        queue = URLPriorityQueue(start_url="https://example.com")
        result = queue.add("https://example.com/page1")
        assert result is True
        assert len(queue) == 2  # start + page1

    def test_add_returns_false_for_duplicate(self) -> None:
        """Test adding duplicate URL returns False."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1")
        result = queue.add("https://example.com/page1")
        assert result is False
        assert len(queue) == 2  # start + page1 (not duplicated)

    def test_add_normalizes_urls_for_dedup(self) -> None:
        """Test URLs are normalized for deduplication."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1/")  # trailing slash
        result = queue.add("https://example.com/page1")  # no trailing slash
        assert result is False  # Should be duplicate after normalization

    def test_add_empty_url_returns_false(self) -> None:
        """Test adding empty URL returns False."""
        queue = URLPriorityQueue(start_url="https://example.com")
        result = queue.add("")
        assert result is False

    def test_add_invalid_url_returns_false(self) -> None:
        """Test adding invalid URL returns False."""
        queue = URLPriorityQueue(start_url="https://example.com")
        result = queue.add("not-a-url")
        assert result is False

    def test_add_different_domain_returns_false(self) -> None:
        """Test adding URL from different domain returns False."""
        queue = URLPriorityQueue(start_url="https://example.com")
        result = queue.add("https://other-domain.com/page")
        assert result is False

    def test_add_subdomain_returns_false(self) -> None:
        """Test adding URL from subdomain returns False (strict domain matching)."""
        queue = URLPriorityQueue(start_url="https://example.com")
        result = queue.add("https://sub.example.com/page")
        assert result is False

    def test_add_with_parent_url(self) -> None:
        """Test adding URL with parent URL tracking."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1", parent_url="https://example.com")
        queue.pop()  # pop start URL
        queued = queue.pop()
        assert queued is not None
        assert queued.parent_url == "https://example.com"

    def test_add_with_depth(self) -> None:
        """Test adding URL with explicit depth."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1", depth=2)
        queue.pop()  # pop start URL
        queued = queue.pop()
        assert queued is not None
        assert queued.depth == 2


class TestURLPriorityQueueExcludePatterns:
    """Tests for exclude pattern filtering."""

    def test_exclude_pattern_blocks_url(self) -> None:
        """Test URL matching exclude pattern is not added."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            exclude_patterns=["/admin/*"],
        )
        result = queue.add("https://example.com/admin/dashboard")
        assert result is False

    def test_excluded_url_is_marked_seen(self) -> None:
        """Test excluded URL is still marked as seen."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            exclude_patterns=["/admin/*"],
        )
        queue.add("https://example.com/admin/dashboard")
        # Should be marked as seen even though excluded
        assert queue.has_seen("https://example.com/admin/dashboard")

    def test_multiple_exclude_patterns(self) -> None:
        """Test multiple exclude patterns work correctly."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            exclude_patterns=["/admin/*", "/api/*", "/internal/*"],
        )
        assert queue.add("https://example.com/admin/users") is False
        assert queue.add("https://example.com/api/v1/data") is False
        assert queue.add("https://example.com/internal/config") is False
        assert queue.add("https://example.com/public/page") is True


class TestURLPriorityQueueIncludePatterns:
    """Tests for include pattern priority."""

    def test_include_pattern_sets_priority(self) -> None:
        """Test URL matching include pattern gets INCLUDE priority."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            include_patterns=["/products/*"],
        )
        queue.add("https://example.com/products/item1")
        queue.pop()  # pop start URL
        queued = queue.pop()
        assert queued is not None
        assert queued.priority == URLPriority.INCLUDE

    def test_non_matching_url_gets_other_priority(self) -> None:
        """Test URL not matching include pattern gets OTHER priority."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            include_patterns=["/products/*"],
        )
        queue.add("https://example.com/about")
        queue.pop()  # pop start URL
        queued = queue.pop()
        assert queued is not None
        assert queued.priority == URLPriority.OTHER


class TestURLPriorityQueuePop:
    """Tests for popping URLs from the queue."""

    def test_pop_returns_highest_priority_first(self) -> None:
        """Test pop returns URLs in priority order."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            include_patterns=["/products/*"],
        )
        queue.add("https://example.com/about")  # OTHER
        queue.add("https://example.com/products/item1")  # INCLUDE

        first = queue.pop()
        assert first is not None
        assert first.priority == URLPriority.HOMEPAGE

        second = queue.pop()
        assert second is not None
        assert second.priority == URLPriority.INCLUDE

        third = queue.pop()
        assert third is not None
        assert third.priority == URLPriority.OTHER

    def test_pop_empty_queue_returns_none(self) -> None:
        """Test popping from empty queue returns None."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.pop()  # Remove start URL
        result = queue.pop()
        assert result is None

    def test_pop_maintains_fifo_within_priority(self) -> None:
        """Test same-priority URLs are popped in FIFO order."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1")
        queue.add("https://example.com/page2")
        queue.add("https://example.com/page3")

        queue.pop()  # pop start URL

        # Should get pages in order added
        first = queue.pop()
        assert first is not None
        assert first.url == "https://example.com/page1"

        second = queue.pop()
        assert second is not None
        assert second.url == "https://example.com/page2"


class TestURLPriorityQueuePeek:
    """Tests for peeking at the queue."""

    def test_peek_returns_next_without_removing(self) -> None:
        """Test peek returns next URL without removing it."""
        queue = URLPriorityQueue(start_url="https://example.com")
        first_peek = queue.peek()
        second_peek = queue.peek()
        assert first_peek == second_peek
        assert len(queue) == 1

    def test_peek_empty_queue_returns_none(self) -> None:
        """Test peeking empty queue returns None."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.pop()
        result = queue.peek()
        assert result is None


class TestURLPriorityQueueAddMany:
    """Tests for adding multiple URLs."""

    def test_add_many_urls(self) -> None:
        """Test adding multiple URLs at once."""
        queue = URLPriorityQueue(start_url="https://example.com")
        urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]
        added = queue.add_many(urls)
        assert added == 3
        assert len(queue) == 4  # start + 3 pages

    def test_add_many_with_duplicates(self) -> None:
        """Test add_many handles duplicates correctly."""
        queue = URLPriorityQueue(start_url="https://example.com")
        urls = [
            "https://example.com/page1",
            "https://example.com/page1",  # duplicate
            "https://example.com/page2",
        ]
        added = queue.add_many(urls)
        assert added == 2  # Only 2 unique added

    def test_add_many_with_parent_and_depth(self) -> None:
        """Test add_many passes parent_url and depth."""
        queue = URLPriorityQueue(start_url="https://example.com")
        urls = ["https://example.com/page1", "https://example.com/page2"]
        queue.add_many(urls, parent_url="https://example.com", depth=2)

        queue.pop()  # pop start URL
        queued = queue.pop()
        assert queued is not None
        assert queued.parent_url == "https://example.com"
        assert queued.depth == 2


class TestURLPriorityQueueHelpers:
    """Tests for helper methods."""

    def test_empty_returns_true_when_empty(self) -> None:
        """Test empty() returns True for empty queue."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.pop()
        assert queue.empty() is True

    def test_empty_returns_false_when_not_empty(self) -> None:
        """Test empty() returns False for non-empty queue."""
        queue = URLPriorityQueue(start_url="https://example.com")
        assert queue.empty() is False

    def test_len_returns_queue_size(self) -> None:
        """Test __len__ returns queue size."""
        queue = URLPriorityQueue(start_url="https://example.com")
        assert len(queue) == 1
        queue.add("https://example.com/page1")
        assert len(queue) == 2

    def test_bool_returns_true_when_not_empty(self) -> None:
        """Test __bool__ returns True when queue has items."""
        queue = URLPriorityQueue(start_url="https://example.com")
        assert bool(queue) is True

    def test_bool_returns_false_when_empty(self) -> None:
        """Test __bool__ returns False when queue is empty."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.pop()
        assert bool(queue) is False

    def test_seen_count(self) -> None:
        """Test seen_count returns total URLs seen."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1")
        queue.add("https://example.com/page2")
        queue.pop()  # Popped URLs are still "seen"
        assert queue.seen_count() == 3

    def test_has_seen_returns_true_for_seen_url(self) -> None:
        """Test has_seen returns True for URLs in seen set."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1")
        assert queue.has_seen("https://example.com/page1") is True

    def test_has_seen_returns_false_for_unseen_url(self) -> None:
        """Test has_seen returns False for URLs not in seen set."""
        queue = URLPriorityQueue(start_url="https://example.com")
        assert queue.has_seen("https://example.com/unseen") is False

    def test_has_seen_handles_invalid_url(self) -> None:
        """Test has_seen returns False for invalid URLs."""
        queue = URLPriorityQueue(start_url="https://example.com")
        assert queue.has_seen("not-a-url") is False


class TestURLPriorityQueueStats:
    """Tests for queue statistics."""

    def test_get_stats_returns_all_fields(self) -> None:
        """Test get_stats returns expected fields."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            include_patterns=["/products/*"],
            exclude_patterns=["/admin/*"],
        )
        stats = queue.get_stats()

        assert "queue_size" in stats
        assert "seen_count" in stats
        assert "priority_counts" in stats
        assert "start_url" in stats
        assert "start_domain" in stats
        assert "include_patterns" in stats
        assert "exclude_patterns" in stats

    def test_get_stats_priority_counts(self) -> None:
        """Test priority counts in stats."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            include_patterns=["/products/*"],
        )
        queue.add("https://example.com/products/item1")  # INCLUDE
        queue.add("https://example.com/about")  # OTHER

        stats = queue.get_stats()
        assert stats["priority_counts"]["homepage"] == 1
        assert stats["priority_counts"]["include"] == 1
        assert stats["priority_counts"]["other"] == 1


class TestURLPriorityQueueIteration:
    """Tests for queue iteration."""

    def test_iter_yields_in_priority_order(self) -> None:
        """Test iterating yields URLs in priority order."""
        queue = URLPriorityQueue(
            start_url="https://example.com",
            include_patterns=["/products/*"],
        )
        queue.add("https://example.com/about")  # OTHER
        queue.add("https://example.com/products/item")  # INCLUDE

        urls = list(queue)
        assert len(urls) == 3
        assert urls[0].priority == URLPriority.HOMEPAGE
        assert urls[1].priority == URLPriority.INCLUDE
        assert urls[2].priority == URLPriority.OTHER

    def test_iter_empties_queue(self) -> None:
        """Test iteration empties the queue."""
        queue = URLPriorityQueue(start_url="https://example.com")
        list(queue)  # Consume all items
        assert queue.empty()


class TestURLPriorityQueueClear:
    """Tests for clearing the queue."""

    def test_clear_empties_queue(self) -> None:
        """Test clear removes all items from queue."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1")
        queue.clear()
        assert len(queue) == 0
        assert queue.empty()

    def test_clear_keeps_seen_set(self) -> None:
        """Test clear preserves the seen set."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1")
        seen_before = queue.seen_count()
        queue.clear()
        assert queue.seen_count() == seen_before

    def test_reset_clears_queue_and_seen(self) -> None:
        """Test reset clears both queue and seen set, re-adds start URL."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page1")
        queue.add("https://example.com/page2")
        queue.reset()

        # Queue should have only start URL
        assert len(queue) == 1
        # Seen set should have only start URL
        assert queue.seen_count() == 1
        # Should be able to re-add previously seen URLs
        assert queue.add("https://example.com/page1") is True


class TestURLPriorityQueueEdgeCases:
    """Tests for edge cases."""

    def test_homepage_variant_detection(self) -> None:
        """Test homepage variants are detected correctly."""
        queue = URLPriorityQueue(start_url="https://example.com/")
        # Same page after normalization should be homepage priority
        # Note: The start URL is already added, so this returns False (duplicate)
        result = queue.add("https://example.com")
        assert result is False  # Already seen as homepage

    def test_url_with_query_params(self) -> None:
        """Test URLs with query parameters are handled."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page?foo=bar")
        assert len(queue) == 2

    def test_url_with_fragment_normalized(self) -> None:
        """Test URLs with fragments are normalized (fragment removed)."""
        queue = URLPriorityQueue(start_url="https://example.com")
        queue.add("https://example.com/page#section1")
        queue.add("https://example.com/page#section2")  # Should be duplicate
        assert len(queue) == 2  # start + page (not duplicated by fragment)
