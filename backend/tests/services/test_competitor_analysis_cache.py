"""Tests for Competitor analysis cache service.

Tests cover:
- Exception classes
- CacheStats dataclass
- CachedAnalysisData dataclass
- CompetitorAnalysisCacheService operations
- Cache key generation
- Serialization/deserialization
- Statistics tracking
- Graceful degradation when Redis unavailable
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.competitor_analysis_cache import (
    CacheStats,
    CachedAnalysisData,
    CompetitorAnalysisCacheResult,
    CompetitorAnalysisCacheService,
    CompetitorAnalysisCacheError,
    CompetitorAnalysisCacheValidationError,
    CACHE_KEY_PREFIX,
    DEFAULT_TTL_DAYS,
)


# =============================================================================
# EXCEPTION TESTS
# =============================================================================


class TestCompetitorAnalysisCacheError:
    """Tests for CompetitorAnalysisCacheError."""

    def test_base_exception_creation(self):
        """Test creating base exception."""
        error = CompetitorAnalysisCacheError("Test error")
        assert str(error) == "Test error"

    def test_exception_inheritance(self):
        """Test exception inherits from Exception."""
        error = CompetitorAnalysisCacheError("Test")
        assert isinstance(error, Exception)


class TestCompetitorAnalysisCacheValidationError:
    """Tests for CompetitorAnalysisCacheValidationError."""

    def test_validation_error_attributes(self):
        """Test validation error has correct attributes."""
        error = CompetitorAnalysisCacheValidationError(
            "competitor_id", "test_value", "cannot be empty"
        )
        assert error.field_name == "competitor_id"
        assert error.value == "test_value"
        assert error.message == "cannot be empty"
        assert "competitor_id" in str(error)
        assert "cannot be empty" in str(error)

    def test_validation_error_inheritance(self):
        """Test validation error inherits from cache error."""
        error = CompetitorAnalysisCacheValidationError("field", "val", "msg")
        assert isinstance(error, CompetitorAnalysisCacheError)


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


class TestCachedAnalysisData:
    """Tests for CachedAnalysisData dataclass."""

    def test_default_values(self):
        """Test default cached data values."""
        data = CachedAnalysisData(
            competitor_id="comp-123",
            url="https://example.com",
            analysis_type="content",
        )
        assert data.competitor_id == "comp-123"
        assert data.url == "https://example.com"
        assert data.analysis_type == "content"
        assert data.analysis_data == {}
        assert data.project_id is None
        assert data.cached_at > 0

    def test_custom_values(self):
        """Test cached data with custom values."""
        data = CachedAnalysisData(
            competitor_id="comp-456",
            url="https://test.com",
            analysis_type="seo",
            analysis_data={"score": 85, "keywords": ["test"]},
            project_id="proj-123",
            cached_at=1234567890.0,
        )
        assert data.competitor_id == "comp-456"
        assert data.analysis_type == "seo"
        assert data.analysis_data["score"] == 85
        assert data.project_id == "proj-123"
        assert data.cached_at == 1234567890.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        data = CachedAnalysisData(
            competitor_id="comp-123",
            url="https://example.com",
            analysis_type="content",
            analysis_data={"key": "value"},
            project_id="proj-456",
            cached_at=1234567890.0,
        )
        result = data.to_dict()
        assert result["competitor_id"] == "comp-123"
        assert result["url"] == "https://example.com"
        assert result["analysis_type"] == "content"
        assert result["analysis_data"] == {"key": "value"}
        assert result["project_id"] == "proj-456"
        assert result["cached_at"] == 1234567890.0


class TestCompetitorAnalysisCacheResult:
    """Tests for CompetitorAnalysisCacheResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = CompetitorAnalysisCacheResult(success=True)
        assert result.success is True
        assert result.data is None
        assert result.error is None
        assert result.cache_hit is False
        assert result.duration_ms == 0.0

    def test_cache_hit_result(self):
        """Test result with cache hit."""
        data = CachedAnalysisData(
            competitor_id="comp-123",
            url="https://example.com",
            analysis_type="content",
        )
        result = CompetitorAnalysisCacheResult(
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


class TestCompetitorAnalysisCacheService:
    """Tests for CompetitorAnalysisCacheService."""

    def test_initialization(self):
        """Test service initialization."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()
            assert service._ttl_seconds == DEFAULT_TTL_DAYS * 86400

    def test_initialization_custom_ttl(self):
        """Test service initialization with custom TTL."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService(ttl_days=14)
            assert service._ttl_seconds == 14 * 86400

    def test_hash_url_consistency(self):
        """Test URL hashing is consistent."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()
            hash1 = service._hash_url("https://example.com")
            hash2 = service._hash_url("https://example.com")
            assert hash1 == hash2

    def test_hash_url_different_urls(self):
        """Test different URLs produce different hashes."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()
            hash1 = service._hash_url("https://example.com")
            hash2 = service._hash_url("https://other.com")
            assert hash1 != hash2

    def test_build_cache_key_format(self):
        """Test cache key format."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()
            key = service._build_cache_key(
                competitor_id="comp-123",
                analysis_type="content",
                url="https://example.com",
            )
            assert key.startswith(CACHE_KEY_PREFIX)
            assert "comp-123:" in key
            assert "content:" in key

    def test_stats_property(self):
        """Test stats property."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()
            assert isinstance(service.stats, CacheStats)


class TestCompetitorAnalysisCacheServiceAsync:
    """Async tests for CompetitorAnalysisCacheService."""

    @pytest.mark.asyncio
    async def test_get_redis_unavailable(self):
        """Test get when Redis is unavailable."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()

            mock_redis = MagicMock()
            mock_redis.available = False

            with patch("app.services.competitor_analysis_cache.redis_manager", mock_redis):
                result = await service.get(
                    competitor_id="comp-123",
                    analysis_type="content",
                    url="https://example.com",
                )
                assert result.success is True
                assert result.cache_hit is False
                assert result.error == "Redis unavailable"

    @pytest.mark.asyncio
    async def test_get_cache_miss(self):
        """Test get with cache miss."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()

            mock_redis = MagicMock()
            mock_redis.available = True
            mock_redis.get = AsyncMock(return_value=None)

            with patch("app.services.competitor_analysis_cache.redis_manager", mock_redis):
                result = await service.get(
                    competitor_id="comp-123",
                    analysis_type="content",
                    url="https://example.com",
                )
                assert result.success is True
                assert result.cache_hit is False
                assert service._stats.misses == 1

    @pytest.mark.asyncio
    async def test_set_redis_unavailable(self):
        """Test set when Redis is unavailable."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()

            mock_redis = MagicMock()
            mock_redis.available = False

            with patch("app.services.competitor_analysis_cache.redis_manager", mock_redis):
                result = await service.set(
                    competitor_id="comp-123",
                    analysis_type="content",
                    url="https://example.com",
                    analysis_data={"score": 85},
                )
                assert result is False

    @pytest.mark.asyncio
    async def test_set_success(self):
        """Test successful cache set."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()

            mock_redis = MagicMock()
            mock_redis.available = True
            mock_redis.set = AsyncMock(return_value=True)

            with patch("app.services.competitor_analysis_cache.redis_manager", mock_redis):
                result = await service.set(
                    competitor_id="comp-123",
                    analysis_type="content",
                    url="https://example.com",
                    analysis_data={"score": 85},
                )
                assert result is True
                mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_redis_unavailable(self):
        """Test delete when Redis is unavailable."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()

            mock_redis = MagicMock()
            mock_redis.available = False

            with patch("app.services.competitor_analysis_cache.redis_manager", mock_redis):
                result = await service.delete(
                    competitor_id="comp-123",
                    analysis_type="content",
                    url="https://example.com",
                )
                assert result is False

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful cache delete."""
        with patch("app.services.competitor_analysis_cache.get_settings") as mock_settings:
            mock_settings.return_value.competitor_analysis_cache_ttl_days = DEFAULT_TTL_DAYS
            service = CompetitorAnalysisCacheService()

            mock_redis = MagicMock()
            mock_redis.available = True
            mock_redis.delete = AsyncMock(return_value=1)

            with patch("app.services.competitor_analysis_cache.redis_manager", mock_redis):
                result = await service.delete(
                    competitor_id="comp-123",
                    analysis_type="content",
                    url="https://example.com",
                )
                assert result is True
