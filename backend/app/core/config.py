"""Application configuration loaded from environment variables.

All configuration is via environment variables for Railway deployment.
No hardcoded URLs, ports, or credentials.
"""

from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="Client Fulfillment App V2")
    app_version: str = Field(default="2.0.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development")

    # Server - PORT is set dynamically by Railway
    port: int = Field(default=8000, description="Port to bind to (Railway sets this)")
    host: str = Field(default="0.0.0.0", description="Host to bind to")

    # Database
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL connection string",
    )
    db_pool_size: int = Field(default=5, description="Database connection pool size")
    db_max_overflow: int = Field(default=10, description="Max overflow connections")
    db_pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    db_slow_query_threshold_ms: int = Field(
        default=100, description="Threshold for slow query warnings (ms)"
    )
    db_connect_timeout: int = Field(
        default=60, description="Connection timeout in seconds (Railway cold-start)"
    )
    db_command_timeout: int = Field(
        default=60, description="Command timeout in seconds"
    )

    # Redis
    redis_url: RedisDsn | None = Field(
        default=None,
        description="Redis connection string for caching/queues",
    )
    redis_pool_size: int = Field(default=10, description="Redis connection pool size")
    redis_connect_timeout: float = Field(
        default=10.0, description="Redis connection timeout in seconds"
    )
    redis_socket_timeout: float = Field(
        default=5.0, description="Redis socket timeout in seconds"
    )
    redis_retry_on_timeout: bool = Field(
        default=True, description="Retry Redis operations on timeout"
    )
    redis_health_check_interval: int = Field(
        default=30, description="Redis health check interval in seconds"
    )
    # Circuit breaker settings
    redis_circuit_failure_threshold: int = Field(
        default=5, description="Failures before circuit opens"
    )
    redis_circuit_recovery_timeout: float = Field(
        default=30.0, description="Seconds before attempting recovery"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format: json or text")

    # Crawl4AI
    crawl4ai_api_url: str | None = Field(
        default=None,
        description="Crawl4AI API base URL (e.g., http://localhost:11235)",
    )
    crawl4ai_api_token: str | None = Field(
        default=None,
        description="Crawl4AI API token for authentication",
    )
    crawl4ai_timeout: float = Field(
        default=300.0, description="Crawl4AI request timeout in seconds (5 min for Railway)"
    )
    crawl4ai_max_retries: int = Field(
        default=3, description="Maximum retry attempts for Crawl4AI requests"
    )
    crawl4ai_retry_delay: float = Field(
        default=1.0, description="Base delay between retries in seconds"
    )
    # Circuit breaker settings for Crawl4AI
    crawl4ai_circuit_failure_threshold: int = Field(
        default=5, description="Failures before circuit opens"
    )
    crawl4ai_circuit_recovery_timeout: float = Field(
        default=60.0, description="Seconds before attempting recovery"
    )

    # Claude/Anthropic LLM
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key for Claude models",
    )
    claude_model: str = Field(
        default="claude-3-haiku-20240307",
        description="Claude model to use for categorization (default: Haiku for speed/cost)",
    )
    claude_timeout: float = Field(
        default=60.0, description="Claude API request timeout in seconds"
    )
    claude_max_retries: int = Field(
        default=3, description="Maximum retry attempts for Claude API requests"
    )
    claude_retry_delay: float = Field(
        default=1.0, description="Base delay between retries in seconds"
    )
    claude_max_tokens: int = Field(
        default=1024, description="Maximum tokens in Claude response"
    )
    # Circuit breaker settings for Claude
    claude_circuit_failure_threshold: int = Field(
        default=5, description="Failures before circuit opens"
    )
    claude_circuit_recovery_timeout: float = Field(
        default=60.0, description="Seconds before attempting recovery"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
