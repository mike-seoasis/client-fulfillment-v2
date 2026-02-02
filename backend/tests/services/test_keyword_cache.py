"""Tests for Keyword cache service.

Tests cover:
- Exception classes
- CacheStats dataclass
- CachedKeywordData dataclass
- KeywordCacheService operations (get, get_many, set, set_many, delete)
- Cache key generation
- Serialization/deserialization
- Statistics tracking
- Graceful degradation when Redis unavailable
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from app.services.keyword_cache import (
    CacheStats,
    CachedKeywordData,
    KeywordCacheResult,
    KeywordCacheService,
    KeywordCacheServiceError,
    KeywordCacheValidationError,
    CACHE_KEY_PREFIX,
)
from app.integrations.keywords_everywhere import KeywordData


# =============================================================================
# EXCEPTION TESTS
# =============================================================================


class TestKeywordCacheServiceError:
    """Tests for KeywordCacheServiceError."""

    def test_base_exception_creation(self):
        """Test creating base exception."""
        error = KeywordCacheServiceError("Test error")
        assert str(error) == "Test error"

    def test_exception_inheritance(self):
        """Test exception inherits from Exception."""
        error = KeywordCacheServiceError("Test")
        assert isinstance(error, Exception)


class TestKeywordCacheValidationError:
    """Tests for KeywordCacheValidationError."""

    def test_validation_error_attributes(self):
        """Test validation error has correct attributes."""
        error = KeywordCacheValidationError("keyword", "test_value", "cannot be empty")
        assert error.field == "keyword"
        assert error.value == "test_value"
        assert error.message == "cannot be empty"
        assert "keyword" in str(error)
        assert "cannot be empty" in str(error)

    def test_validation_error_inheritance(self):
        """Test validation error inherits from service error."""
        error = KeywordCacheValidationError("field", "val", "msg")
        assert isinstance(error, KeywordCacheServiceError)


# =============================================================================
# DATACLASS TESTS
# =============================================================================


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_default_values(self):
        """Test default stats values."""
        stats = CacheStats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.errors == 0

    def test_hit_rate_zero_requests(self):
        """Test hit rate with no requests."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        """Test hit rate calculation."""
        stats = CacheStats(hits=75, misses=25)
        assert stats.hit_rate == 0.75

    def test_hit_rate_all_hits(self):
        """Test hit rate with all hits."""
        stats = CacheStats(hits=100, misses=0)
        assert stats.hit_rate == 1.0

    def test_hit_rate_all_misses(self):
        """Test hit rate with all misses."""
        stats = CacheStats(hits=0, misses=100)
        assert stats.hit_rate == 0.0


class TestCachedKeywordData:
    """Tests for CachedKeywordData dataclass."""

    def test_default_values(self):
        """Test default cached data values."""
        data = CachedKeywordData(keyword="test")
        assert data.keyword == "test"
        assert data.volume is None
        assert data.cpc is None
        assert data.competition is None
        assert data.trend is None
        assert data.country == "us"
        assert data.data_source == "gkp"
        assert data.cached_at > 0

    def test_custom_values(self):
        """Test cached data with custom values."""
        data = CachedKeywordData(
            keyword="hiking boots",
            volume=5000,
            cpc=1.50,
            competition=0.65,
            trend=[100, 120, 90, 110],
            country="uk",
            data_source="cli",
            cached_at=1234567890.0,
        )
        assert data.keyword == "hiking boots"
        assert data.volume == 5000
        assert data.cpc == 1.50
        assert data.competition == 0.65
        assert data.trend == [100, 120, 90, 110]
        assert data.country == "uk"
        assert data.data_source == "cli"
        assert data.cached_at == 1234567890.0

    def test_to_keyword_data(self):
        """Test conversion to KeywordData."""
        data = CachedKeywordData(
            keyword="test keyword",
            volume=1000,
            cpc=2.5,
            competition=0.5,
            trend=[90, 100, 110],
        )
        result = data.to_keyword_data()
        assert result.keyword == "test keyword"
        assert result.volume == 1000
        assert result.cpc == 2.5
        assert result.competition == 0.5
        assert result.trend == [90, 100, 110]


class TestKeywordCacheResult:
    """Tests for KeywordCacheResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = KeywordCacheResult(success=True)
        assert result.success is True
        assert result.data == []
        assert result.error is None
        assert result.cache_hit is False
        assert result.duration_ms == 0.0

    def test_cache_hit_result(self):
        """Test result with cache hit."""
        data = [CachedKeywordData(keyword="test")]
        result = KeywordCacheResult(
            success=True,
            data=data,
            cache_hit=True,
            duration_ms=5.5,
        )
        assert result.success is True
        assert len(result.data) == 1
        assert result.cache_hit is True
        assert result.duration_ms == 5.5


# =============================================================================
# SERVICE TESTS
# =============================================================================


class TestKeywordCacheService:
    """Tests for KeywordCacheService."""

    def test_initialization(self):
        """Test service initialization."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()
            assert service._ttl_seconds == 30 * 86400

    def test_initialization_custom_ttl(self):
        """Test service initialization with custom TTL."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService(ttl_days=7)
            assert service._ttl_seconds == 7 * 86400

    def test_build_cache_key_format(self):
        """Test cache key format."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()
            key = service._build_cache_key(
                keyword="test keyword",
                country="us",
                data_source="gkp",
            )
            assert key.startswith(CACHE_KEY_PREFIX)
            assert "us:" in key
            assert "gkp:" in key
            assert "test keyword" in key

    def test_build_cache_key_normalizes_keyword(self):
        """Test cache key normalizes keyword."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()
            key1 = service._build_cache_key("Test Keyword")
            key2 = service._build_cache_key("test keyword")
            key3 = service._build_cache_key("  test keyword  ")
            assert key1 == key2 == key3

    def test_build_cache_key_different_countries(self):
        """Test cache keys differ for different countries."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()
            key_us = service._build_cache_key("test", country="us")
            key_uk = service._build_cache_key("test", country="uk")
            assert key_us != key_uk

    def test_serialize_deserialize_roundtrip(self):
        """Test serialization roundtrip."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()
            original = CachedKeywordData(
                keyword="test",
                volume=1000,
                cpc=1.5,
                competition=0.5,
                trend=[100, 110, 90],
                country="us",
                data_source="gkp",
                cached_at=1234567890.0,
            )
            serialized = service._serialize_data(original)
            deserialized = service._deserialize_data(serialized)
            assert deserialized.keyword == original.keyword
            assert deserialized.volume == original.volume
            assert deserialized.cpc == original.cpc
            assert deserialized.competition == original.competition
            assert deserialized.trend == original.trend
            assert deserialized.country == original.country
            assert deserialized.data_source == original.data_source
            assert deserialized.cached_at == original.cached_at

    def test_stats_property(self):
        """Test stats property."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()
            assert isinstance(service.stats, CacheStats)


class TestKeywordCacheServiceAsync:
    """Async tests for KeywordCacheService."""

    @pytest.mark.asyncio
    async def test_get_redis_unavailable(self):
        """Test get when Redis is unavailable."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = False

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                result = await service.get("test keyword")
                assert result.success is True
                assert result.cache_hit is False
                assert result.error == "Redis unavailable"

    @pytest.mark.asyncio
    async def test_get_cache_miss(self):
        """Test get with cache miss."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = True
            mock_redis.get = AsyncMock(return_value=None)

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                result = await service.get("test keyword")
                assert result.success is True
                assert result.cache_hit is False
                assert service._stats.misses == 1

    @pytest.mark.asyncio
    async def test_get_cache_hit(self):
        """Test get with cache hit."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()
            cached_data = CachedKeywordData(
                keyword="test keyword",
                volume=5000,
                cpc=1.5,
            )
            serialized = service._serialize_data(cached_data)

            mock_redis = MagicMock()
            mock_redis.available = True
            mock_redis.get = AsyncMock(return_value=serialized.encode("utf-8"))

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                result = await service.get("test keyword")
                assert result.success is True
                assert result.cache_hit is True
                assert len(result.data) == 1
                assert result.data[0].keyword == "test keyword"
                assert result.data[0].volume == 5000
                assert service._stats.hits == 1

    @pytest.mark.asyncio
    async def test_set_redis_unavailable(self):
        """Test set when Redis is unavailable."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = False

            keyword_data = KeywordData(keyword="test", volume=1000)

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                result = await service.set(keyword_data)
                assert result is False

    @pytest.mark.asyncio
    async def test_set_success(self):
        """Test successful cache set."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = True
            mock_redis.set = AsyncMock(return_value=True)

            keyword_data = KeywordData(
                keyword="test keyword",
                volume=1000,
                cpc=1.5,
                competition=0.5,
            )

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                result = await service.set(keyword_data)
                assert result is True
                mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_redis_unavailable(self):
        """Test delete when Redis is unavailable."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = False

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                result = await service.delete("test")
                assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful cache delete."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = True
            mock_redis.delete = AsyncMock(return_value=1)

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                result = await service.delete("test keyword")
                assert result is True

    @pytest.mark.asyncio
    async def test_get_many_redis_unavailable(self):
        """Test get_many when Redis is unavailable."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = False

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                # get_many returns tuple (cached_data, missed_keywords)
                cached_data, missed = await service.get_many(["kw1", "kw2"])
                assert cached_data == []
                assert missed == ["kw1", "kw2"]

    @pytest.mark.asyncio
    async def test_get_many_empty_keywords(self):
        """Test get_many with empty keyword list."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = True

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                cached_data, missed = await service.get_many([])
                assert cached_data == []
                assert missed == []

    @pytest.mark.asyncio
    async def test_get_many_all_hits(self):
        """Test get_many when all keywords are cached."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            # Mock the get method directly to simulate cache hits
            cached_data1 = CachedKeywordData(keyword="keyword1", volume=100)
            cached_data2 = CachedKeywordData(keyword="keyword2", volume=200)

            mock_redis = MagicMock()
            mock_redis.available = True

            # Mock get to return cached results
            call_count = [0]
            serialized1 = service._serialize_data(cached_data1)
            serialized2 = service._serialize_data(cached_data2)

            async def mock_get(key):
                call_count[0] += 1
                if call_count[0] == 1:
                    return serialized1.encode("utf-8")
                return serialized2.encode("utf-8")

            mock_redis.get = mock_get

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                cached, missed = await service.get_many(["keyword1", "keyword2"])
                # Both should be cached
                assert len(cached) == 2
                assert len(missed) == 0

    @pytest.mark.asyncio
    async def test_set_many_redis_unavailable(self):
        """Test set_many when Redis is unavailable."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = False

            keywords = [KeywordData(keyword="test", volume=100)]

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                count = await service.set_many(keywords)
                assert count == 0

    @pytest.mark.asyncio
    async def test_set_many_empty_keywords(self):
        """Test set_many with empty keyword list."""
        with patch("app.services.keyword_cache.get_settings") as mock_settings:
            mock_settings.return_value.keyword_cache_ttl_days = 30
            service = KeywordCacheService()

            mock_redis = MagicMock()
            mock_redis.available = True

            with patch("app.services.keyword_cache.redis_manager", mock_redis):
                count = await service.set_many([])
                assert count == 0
