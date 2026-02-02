"""Tests for PAA cache service.

Tests cover:
- Exception classes
- CacheStats dataclass
- CachedPAAData dataclass
- PAACacheService operations (get, set, delete, get_ttl)
- Cache key generation
- Serialization/deserialization
- Statistics tracking
- Graceful degradation when Redis unavailable
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from app.services.paa_cache import (
    CacheStats,
    CachedPAAData,
    PAACacheResult,
    PAACacheService,
    PAACacheServiceError,
    PAACacheValidationError,
    get_paa_cache_service,
    CACHE_KEY_PREFIX,
    DEFAULT_TTL_HOURS,
)


# =============================================================================
# EXCEPTION TESTS
# =============================================================================


class TestPAACacheServiceError:
    """Tests for PAACacheServiceError."""

    def test_base_exception_creation(self):
        """Test creating base exception."""
        error = PAACacheServiceError("Test error")
        assert str(error) == "Test error"

    def test_exception_inheritance(self):
        """Test exception inherits from Exception."""
        error = PAACacheServiceError("Test")
        assert isinstance(error, Exception)


class TestPAACacheValidationError:
    """Tests for PAACacheValidationError."""

    def test_validation_error_attributes(self):
        """Test validation error has correct attributes."""
        error = PAACacheValidationError("keyword", "test_value", "cannot be empty")
        assert error.field_name == "keyword"
        assert error.value == "test_value"
        assert error.message == "cannot be empty"
        assert "keyword" in str(error)
        assert "cannot be empty" in str(error)

    def test_validation_error_inheritance(self):
        """Test validation error inherits from service error."""
        error = PAACacheValidationError("field", "val", "msg")
        assert isinstance(error, PAACacheServiceError)


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


class TestCachedPAAData:
    """Tests for CachedPAAData dataclass."""

    def test_default_values(self):
        """Test default cached data values."""
        data = CachedPAAData(keyword="test")
        assert data.keyword == "test"
        assert data.questions == []
        assert data.initial_count == 0
        assert data.nested_count == 0
        assert data.location_code == 2840
        assert data.language_code == "en"
        assert data.cached_at > 0

    def test_custom_values(self):
        """Test cached data with custom values."""
        data = CachedPAAData(
            keyword="hiking boots",
            questions=[{"question": "What are hiking boots?", "intent": "informational"}],
            initial_count=5,
            nested_count=10,
            location_code=2826,
            language_code="de",
            cached_at=1234567890.0,
        )
        assert data.keyword == "hiking boots"
        assert len(data.questions) == 1
        assert data.initial_count == 5
        assert data.nested_count == 10
        assert data.location_code == 2826
        assert data.language_code == "de"
        assert data.cached_at == 1234567890.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        data = CachedPAAData(
            keyword="test keyword",
            questions=[{"question": "What is test?", "intent": "informational"}],
            initial_count=3,
            nested_count=7,
            location_code=2840,
            language_code="en",
            cached_at=1234567890.0,
        )
        result = data.to_dict()
        assert result["keyword"] == "test keyword"
        assert len(result["questions"]) == 1
        assert result["initial_count"] == 3
        assert result["nested_count"] == 7
        assert result["location_code"] == 2840
        assert result["language_code"] == "en"
        assert result["cached_at"] == 1234567890.0


class TestPAACacheResult:
    """Tests for PAACacheResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = PAACacheResult(success=True)
        assert result.success is True
        assert result.data is None
        assert result.error is None
        assert result.cache_hit is False
        assert result.duration_ms == 0.0

    def test_cache_hit_result(self):
        """Test result with cache hit."""
        data = CachedPAAData(keyword="test")
        result = PAACacheResult(
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


class TestPAACacheService:
    """Tests for PAACacheService."""

    def test_initialization_default_ttl(self):
        """Test service initialization with default TTL."""
        service = PAACacheService()
        assert service._ttl_seconds == DEFAULT_TTL_HOURS * 3600

    def test_initialization_custom_ttl(self):
        """Test service initialization with custom TTL."""
        service = PAACacheService(ttl_hours=12)
        assert service._ttl_seconds == 12 * 3600

    def test_hash_keyword_consistency(self):
        """Test keyword hashing is consistent."""
        service = PAACacheService()
        hash1 = service._hash_keyword("test keyword")
        hash2 = service._hash_keyword("test keyword")
        assert hash1 == hash2

    def test_hash_keyword_case_insensitive(self):
        """Test keyword hashing is case insensitive."""
        service = PAACacheService()
        hash1 = service._hash_keyword("Test Keyword")
        hash2 = service._hash_keyword("test keyword")
        assert hash1 == hash2

    def test_hash_keyword_strips_whitespace(self):
        """Test keyword hashing strips whitespace."""
        service = PAACacheService()
        hash1 = service._hash_keyword("  test keyword  ")
        hash2 = service._hash_keyword("test keyword")
        assert hash1 == hash2

    def test_build_cache_key_format(self):
        """Test cache key format."""
        service = PAACacheService()
        key = service._build_cache_key(
            keyword="test",
            location_code=2840,
            language_code="en",
        )
        assert key.startswith(CACHE_KEY_PREFIX)
        assert "2840:" in key
        assert "en:" in key

    def test_build_cache_key_different_locations(self):
        """Test cache keys differ for different locations."""
        service = PAACacheService()
        key_us = service._build_cache_key("test", location_code=2840)
        key_uk = service._build_cache_key("test", location_code=2826)
        assert key_us != key_uk

    def test_build_cache_key_different_languages(self):
        """Test cache keys differ for different languages."""
        service = PAACacheService()
        key_en = service._build_cache_key("test", language_code="en")
        key_de = service._build_cache_key("test", language_code="de")
        assert key_en != key_de

    def test_serialize_deserialize_roundtrip(self):
        """Test serialization roundtrip."""
        service = PAACacheService()
        original = CachedPAAData(
            keyword="test",
            questions=[{"question": "What is test?", "intent": "informational"}],
            initial_count=3,
            nested_count=7,
            location_code=2840,
            language_code="en",
            cached_at=1234567890.0,
        )
        serialized = service._serialize_data(original)
        deserialized = service._deserialize_data(serialized)
        assert deserialized.keyword == original.keyword
        assert deserialized.questions == original.questions
        assert deserialized.initial_count == original.initial_count
        assert deserialized.nested_count == original.nested_count
        assert deserialized.location_code == original.location_code
        assert deserialized.cached_at == original.cached_at

    def test_stats_property(self):
        """Test stats property."""
        service = PAACacheService()
        assert isinstance(service.stats, CacheStats)

    def test_get_stats_summary(self):
        """Test get_stats_summary method."""
        service = PAACacheService()
        service._stats.hits = 10
        service._stats.misses = 5
        service._stats.errors = 1
        summary = service.get_stats_summary()
        assert summary["hits"] == 10
        assert summary["misses"] == 5
        assert summary["errors"] == 1
        assert summary["hit_rate"] == round(10 / 15, 3)
        assert summary["total_requests"] == 15


class TestPAACacheServiceAsync:
    """Async tests for PAACacheService."""

    @pytest.mark.asyncio
    async def test_get_redis_unavailable(self):
        """Test get when Redis is unavailable."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = False

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.get("test keyword")
            assert result.success is True
            assert result.cache_hit is False
            assert result.error == "Redis unavailable"

    @pytest.mark.asyncio
    async def test_get_cache_miss(self):
        """Test get with cache miss."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.get("test keyword")
            assert result.success is True
            assert result.cache_hit is False
            assert service._stats.misses == 1

    @pytest.mark.asyncio
    async def test_get_cache_hit(self):
        """Test get with cache hit."""
        service = PAACacheService()
        cached_data = CachedPAAData(
            keyword="test keyword",
            questions=[{"question": "What is test?", "intent": "informational"}],
            initial_count=3,
            nested_count=7,
        )
        serialized = service._serialize_data(cached_data)

        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.get = AsyncMock(return_value=serialized.encode("utf-8"))

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.get("test keyword")
            assert result.success is True
            assert result.cache_hit is True
            assert result.data is not None
            assert result.data.keyword == "test keyword"
            assert service._stats.hits == 1

    @pytest.mark.asyncio
    async def test_get_json_decode_error(self):
        """Test get with corrupted cached data."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.get = AsyncMock(return_value=b"not valid json")
        mock_redis.delete = AsyncMock(return_value=True)

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.get("test keyword")
            assert result.success is False
            assert result.cache_hit is False
            assert "deserialization" in result.error.lower()
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_with_project_page_ids(self):
        """Test get with project and page IDs for logging."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.get(
                "test keyword",
                project_id="proj-123",
                page_id="page-456",
            )
            assert result.success is True
            assert result.cache_hit is False

    @pytest.mark.asyncio
    async def test_set_redis_unavailable(self):
        """Test set when Redis is unavailable."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = False

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.set(
                keyword="test",
                questions=[],
                initial_count=0,
                nested_count=0,
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_set_empty_keyword_validation(self):
        """Test set with empty keyword raises validation error."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            with pytest.raises(PAACacheValidationError) as exc_info:
                await service.set(
                    keyword="",
                    questions=[],
                    initial_count=0,
                    nested_count=0,
                )
            assert exc_info.value.field_name == "keyword"

    @pytest.mark.asyncio
    async def test_set_success(self):
        """Test successful cache set."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.set = AsyncMock(return_value=True)

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.set(
                keyword="test keyword",
                questions=[{"question": "What is test?", "intent": "informational"}],
                initial_count=3,
                nested_count=7,
            )
            assert result is True
            mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_with_project_page_ids(self):
        """Test set with project and page IDs for logging."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.set = AsyncMock(return_value=True)

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.set(
                keyword="test keyword",
                questions=[],
                initial_count=0,
                nested_count=0,
                project_id="proj-123",
                page_id="page-456",
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_redis_unavailable(self):
        """Test delete when Redis is unavailable."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = False

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.delete("test")
            assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful cache delete."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.delete("test keyword")
            assert result is True

    @pytest.mark.asyncio
    async def test_get_ttl_redis_unavailable(self):
        """Test get_ttl when Redis is unavailable."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = False

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.get_ttl("test")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_ttl_key_exists(self):
        """Test get_ttl for existing key."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.ttl = AsyncMock(return_value=3600)

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.get_ttl("test keyword")
            assert result == 3600

    @pytest.mark.asyncio
    async def test_get_ttl_key_not_exists(self):
        """Test get_ttl for non-existing key."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.ttl = AsyncMock(return_value=-2)

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.get_ttl("test keyword")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_ttl_no_ttl_set(self):
        """Test get_ttl when key exists but has no TTL."""
        service = PAACacheService()
        mock_redis = MagicMock()
        mock_redis.available = True
        mock_redis.ttl = AsyncMock(return_value=-1)

        with patch("app.services.paa_cache.redis_manager", mock_redis):
            result = await service.get_ttl("test keyword")
            assert result is None


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_paa_cache_service_returns_instance(self):
        """Test get_paa_cache_service returns a service instance."""
        with patch("app.services.paa_cache._paa_cache_service", None):
            service = get_paa_cache_service()
            assert isinstance(service, PAACacheService)
