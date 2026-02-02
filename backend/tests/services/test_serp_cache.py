"""Tests for SERP cache service.

Tests cover:
- Exception classes
- CacheStats dataclass
- CachedSerpData dataclass and conversion
- SerpCacheService operations (get, set, delete, get_ttl)
- Cache key generation
- Serialization/deserialization
- Statistics tracking
- Graceful degradation when Redis unavailable
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from app.services.serp_cache import (
    CacheStats,
    CachedSerpData,
    SerpCacheResult,
    SerpCacheService,
    SerpCacheServiceError,
    SerpCacheValidationError,
    get_serp_cache_service,
    cache_serp_result,
    get_cached_serp,
    CACHE_KEY_PREFIX,
    DEFAULT_TTL_HOURS,
)
from app.integrations.dataforseo import SerpResult, SerpSearchResult


# =============================================================================
# EXCEPTION TESTS
# =============================================================================


class TestSerpCacheServiceError:
    """Tests for SerpCacheServiceError."""

    def test_base_exception_creation(self):
        """Test creating base exception."""
        error = SerpCacheServiceError("Test error")
        assert str(error) == "Test error"

    def test_exception_inheritance(self):
        """Test exception inherits from Exception."""
        error = SerpCacheServiceError("Test")
        assert isinstance(error, Exception)


class TestSerpCacheValidationError:
    """Tests for SerpCacheValidationError."""

    def test_validation_error_attributes(self):
        """Test validation error has correct attributes."""
        error = SerpCacheValidationError("keyword", "test_value", "cannot be empty")
        assert error.field_name == "keyword"
        assert error.value == "test_value"
        assert error.message == "cannot be empty"
        assert "keyword" in str(error)
        assert "cannot be empty" in str(error)

    def test_validation_error_inheritance(self):
        """Test validation error inherits from service error."""
        error = SerpCacheValidationError("field", "val", "msg")
        assert isinstance(error, SerpCacheServiceError)


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


class TestCachedSerpData:
    """Tests for CachedSerpData dataclass."""

    def test_default_values(self):
        """Test default cached data values."""
        data = CachedSerpData(keyword="test")
        assert data.keyword == "test"
        assert data.results == []
        assert data.total_results is None
        assert data.location_code == 2840
        assert data.language_code == "en"
        assert data.search_engine == "google"
        assert data.cached_at > 0

    def test_custom_values(self):
        """Test cached data with custom values."""
        data = CachedSerpData(
            keyword="hiking boots",
            results=[{"position": 1, "url": "https://example.com", "title": "Test"}],
            total_results=1000,
            location_code=2826,
            language_code="de",
            search_engine="bing",
            cached_at=1234567890.0,
        )
        assert data.keyword == "hiking boots"
        assert len(data.results) == 1
        assert data.total_results == 1000
        assert data.location_code == 2826
        assert data.language_code == "de"
        assert data.search_engine == "bing"
        assert data.cached_at == 1234567890.0

    def test_to_serp_result(self):
        """Test conversion to SerpSearchResult."""
        data = CachedSerpData(
            keyword="test keyword",
            results=[
                {
                    "position": 1,
                    "url": "https://example.com",
                    "title": "Example",
                    "description": "Test description",
                    "domain": "example.com",
                },
                {
                    "position": 2,
                    "url": "https://test.com",
                    "title": "Test",
                    "description": None,
                    "domain": None,
                },
            ],
            total_results=100,
        )
        result = data.to_serp_result()
        assert result.success is True
        assert result.keyword == "test keyword"
        assert len(result.results) == 2
        assert result.results[0].position == 1
        assert result.results[0].url == "https://example.com"
        assert result.results[0].title == "Example"
        assert result.total_results == 100


class TestSerpCacheResult:
    """Tests for SerpCacheResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = SerpCacheResult(success=True)
        assert result.success is True
        assert result.data is None
        assert result.error is None
        assert result.cache_hit is False
        assert result.duration_ms == 0.0

    def test_cache_hit_result(self):
        """Test result with cache hit."""
        data = CachedSerpData(keyword="test")
        result = SerpCacheResult(
            success=True,
            data=data,
            cache_hit=True,
            duration_ms=5.5,
        )
        assert result.success is True
        assert result.data is not None
        assert result.cache_hit is True
        assert result.duration_ms == 5.5


# =============================================================================
# SERVICE TESTS
# =============================================================================


class TestSerpCacheService:
    """Tests for SerpCacheService."""

    def test_initialization_default_ttl(self):
        """Test service initialization with default TTL."""
        service = SerpCacheService()
        assert service._ttl_seconds == DEFAULT_TTL_HOURS * 3600

    def test_initialization_custom_ttl(self):
        """Test service initialization with custom TTL."""
        service = SerpCacheService(ttl_hours=12)
        assert service._ttl_seconds == 12 * 3600

    def test_hash_keyword_consistency(self):
        """Test keyword hashing is consistent."""
        service = SerpCacheService()
        hash1 = service._hash_keyword("test keyword")
        hash2 = service._hash_keyword("test keyword")
        assert hash1 == hash2

    def test_hash_keyword_case_insensitive(self):
        """Test keyword hashing is case insensitive."""
        service = SerpCacheService()
        hash1 = service._hash_keyword("Test Keyword")
        hash2 = service._hash_keyword("test keyword")
        assert hash1 == hash2

    def test_hash_keyword_strips_whitespace(self):
        """Test keyword hashing strips whitespace."""
        service = SerpCacheService()
        hash1 = service._hash_keyword("  test keyword  ")
        hash2 = service._hash_keyword("test keyword")
        assert hash1 == hash2

    def test_build_cache_key_format(self):
        """Test cache key format."""
        service = SerpCacheService()
        key = service._build_cache_key(
            keyword="test",
            location_code=2840,
            language_code="en",
            search_engine="google",
        )
        assert key.startswith(CACHE_KEY_PREFIX)
        assert "google:" in key
        assert "2840:" in key
        assert "en:" in key

    def test_build_cache_key_different_engines(self):
        """Test cache keys differ for different search engines."""
        service = SerpCacheService()
        key_google = service._build_cache_key("test", search_engine="google")
        key_bing = service._build_cache_key("test", search_engine="bing")
        assert key_google != key_bing

    def test_build_cache_key_different_locations(self):
        """Test cache keys differ for different locations."""
        service = SerpCacheService()
        key_us = service._build_cache_key("test", location_code=2840)
        key_uk = service._build_cache_key("test", location_code=2826)
        assert key_us != key_uk

    def test_serialize_deserialize_roundtrip(self):
        """Test serialization roundtrip."""
        service = SerpCacheService()
        original = CachedSerpData(
            keyword="test",
            results=[{"position": 1, "url": "https://test.com", "title": "Test"}],
            total_results=100,
            location_code=2840,
            language_code="en",
            search_engine="google",
            cached_at=1234567890.0,
        )
        serialized = service._serialize_data(original)
        deserialized = service._deserialize_data(serialized)
        assert deserialized.keyword == original.keyword
        assert deserialized.results == original.results
        assert deserialized.total_results == original.total_results
        assert deserialized.location_code == original.location_code
        assert deserialized.cached_at == original.cached_at

    def test_stats_property(self):
        """Test stats property."""
        service = SerpCacheService()
        assert isinstance(service.stats, CacheStats)

    def test_get_stats_summary(self):
        """Test get_stats_summary method."""
        service = SerpCacheService()
        service._stats.hits = 10
        service._stats.misses = 5
        service._stats.errors = 1
        summary = service.get_stats_summary()
        assert summary["hits"] == 10
        assert summary["misses"] == 5
        assert summary["errors"] == 1
        assert summary["hit_rate"] == round(10 / 15, 3)
        assert summary["total_requests"] == 15


class TestSerpCacheServiceAsync:
    """Async tests for SerpCacheService."""

    @pytest.mark.asyncio
    async def test_get_redis_unavailable(self):
        """Test get when Redis is unavailable."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = False

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.get("test keyword")
            assert result.success is True
            assert result.cache_hit is False
            assert result.error == "Redis unavailable"

    @pytest.mark.asyncio
    async def test_get_cache_miss(self):
        """Test get with cache miss."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.get("test keyword")
            assert result.success is True
            assert result.cache_hit is False
            assert service._stats.misses == 1

    @pytest.mark.asyncio
    async def test_get_cache_hit(self):
        """Test get with cache hit."""
        service = SerpCacheService()
        cached_data = CachedSerpData(
            keyword="test keyword",
            results=[{"position": 1, "url": "https://test.com", "title": "Test"}],
            total_results=100,
        )
        serialized = service._serialize_data(cached_data)

        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.get = AsyncMock(return_value=serialized.encode("utf-8"))

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.get("test keyword")
            assert result.success is True
            assert result.cache_hit is True
            assert result.data is not None
            assert result.data.keyword == "test keyword"
            assert service._stats.hits == 1

    @pytest.mark.asyncio
    async def test_get_json_decode_error(self):
        """Test get with corrupted cached data."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.get = AsyncMock(return_value=b"not valid json")
        mock_redis.delete = AsyncMock(return_value=True)

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.get("test keyword")
            assert result.success is False
            assert result.cache_hit is False
            assert "deserialization" in result.error.lower()
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_redis_unavailable(self):
        """Test set when Redis is unavailable."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = False

        serp_data = SerpSearchResult(
            success=True,
            keyword="test",
            results=[],
        )
        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.set(serp_data)
            assert result is False

    @pytest.mark.asyncio
    async def test_set_empty_keyword_validation(self):
        """Test set with empty keyword raises validation error."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = True

        serp_data = SerpSearchResult(
            success=True,
            keyword="",
            results=[],
        )
        with patch("app.services.serp_cache.redis_manager", mock_redis):
            with pytest.raises(SerpCacheValidationError) as exc_info:
                await service.set(serp_data)
            assert exc_info.value.field_name == "keyword"

    @pytest.mark.asyncio
    async def test_set_success(self):
        """Test successful cache set."""
        service = SerpCacheService()
        serp_data = SerpSearchResult(
            success=True,
            keyword="test keyword",
            results=[
                SerpResult(
                    position=1,
                    url="https://test.com",
                    title="Test",
                    description="Test desc",
                    domain="test.com",
                )
            ],
            total_results=100,
        )

        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.set = AsyncMock(return_value=True)

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.set(serp_data)
            assert result is True
            mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_redis_unavailable(self):
        """Test delete when Redis is unavailable."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = False

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.delete("test")
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful cache delete."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.delete("test keyword")
            assert result is True

    @pytest.mark.asyncio
    async def test_get_ttl_redis_unavailable(self):
        """Test get_ttl when Redis is unavailable."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = False

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.get_ttl("test")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_ttl_key_exists(self):
        """Test get_ttl for existing key."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.ttl = AsyncMock(return_value=3600)

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.get_ttl("test keyword")
            assert result == 3600

    @pytest.mark.asyncio
    async def test_get_ttl_key_not_exists(self):
        """Test get_ttl for non-existing key."""
        service = SerpCacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.ttl = AsyncMock(return_value=-2)

        with patch("app.services.serp_cache.redis_manager", mock_redis):
            result = await service.get_ttl("test keyword")
            assert result is None


# =============================================================================
# SINGLETON AND CONVENIENCE FUNCTION TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_serp_cache_service_returns_instance(self):
        """Test get_serp_cache_service returns a service instance."""
        with patch("app.services.serp_cache._serp_cache_service", None):
            service = get_serp_cache_service()
            assert isinstance(service, SerpCacheService)


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_cache_serp_result(self):
        """Test cache_serp_result convenience function."""
        serp_data = SerpSearchResult(
            success=True,
            keyword="test",
            results=[],
        )

        mock_service = MagicMock(spec=SerpCacheService)
        mock_service.set = AsyncMock(return_value=True)

        with patch("app.services.serp_cache.get_serp_cache_service", return_value=mock_service):
            result = await cache_serp_result(serp_data)
            assert result is True
            mock_service.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_cached_serp(self):
        """Test get_cached_serp convenience function."""
        mock_result = SerpCacheResult(success=True, cache_hit=False)
        mock_service = MagicMock(spec=SerpCacheService)
        mock_service.get = AsyncMock(return_value=mock_result)

        with patch("app.services.serp_cache.get_serp_cache_service", return_value=mock_service):
            result = await get_cached_serp("test keyword")
            assert result.success is True
            mock_service.get.assert_called_once()
