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

    # CORS - Frontend URL for production
    frontend_url: str | None = Field(
        default=None,
        description="Frontend URL for CORS (e.g., https://app.example.com). If not set, allows all origins.",
    )

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
        default=300.0,
        description="Crawl4AI request timeout in seconds (5 min for Railway)",
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

    # Scheduler (APScheduler)
    scheduler_enabled: bool = Field(
        default=True, description="Enable/disable the scheduler"
    )
    scheduler_job_coalesce: bool = Field(
        default=True, description="Coalesce missed job executions into one"
    )
    scheduler_max_instances: int = Field(
        default=3, description="Max concurrent instances per job"
    )
    scheduler_misfire_grace_time: int = Field(
        default=60, description="Seconds to allow job execution after scheduled time"
    )
    scheduler_job_default_max_instances: int = Field(
        default=1, description="Default max instances for jobs without explicit setting"
    )

    # Perplexity API
    perplexity_api_key: str | None = Field(
        default=None,
        description="Perplexity API key for website analysis",
    )
    perplexity_model: str = Field(
        default="sonar",
        description="Perplexity model to use (sonar for web-connected queries)",
    )
    perplexity_timeout: float = Field(
        default=60.0, description="Perplexity API request timeout in seconds"
    )
    perplexity_max_retries: int = Field(
        default=3, description="Maximum retry attempts for Perplexity API requests"
    )
    perplexity_retry_delay: float = Field(
        default=1.0, description="Base delay between retries in seconds"
    )
    perplexity_max_tokens: int = Field(
        default=2048, description="Maximum tokens in Perplexity response"
    )
    # Circuit breaker settings for Perplexity
    perplexity_circuit_failure_threshold: int = Field(
        default=5, description="Failures before circuit opens"
    )
    perplexity_circuit_recovery_timeout: float = Field(
        default=60.0, description="Seconds before attempting recovery"
    )

    # Keywords Everywhere API
    keywords_everywhere_api_key: str | None = Field(
        default=None,
        description="Keywords Everywhere API key for keyword data",
    )
    keywords_everywhere_timeout: float = Field(
        default=30.0, description="Keywords Everywhere API request timeout in seconds"
    )
    keywords_everywhere_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for Keywords Everywhere API requests",
    )
    keywords_everywhere_retry_delay: float = Field(
        default=1.0, description="Base delay between retries in seconds"
    )
    keywords_everywhere_default_country: str = Field(
        default="us", description="Default country code for keyword data"
    )
    keywords_everywhere_default_currency: str = Field(
        default="USD", description="Default currency for CPC data"
    )
    keywords_everywhere_default_data_source: str = Field(
        default="gkp",
        description="Default data source (gkp=Google Keyword Planner, cli=clickstream)",
    )
    # Circuit breaker settings for Keywords Everywhere
    keywords_everywhere_circuit_failure_threshold: int = Field(
        default=5, description="Failures before circuit opens"
    )
    keywords_everywhere_circuit_recovery_timeout: float = Field(
        default=60.0, description="Seconds before attempting recovery"
    )

    # Keyword cache settings
    keyword_cache_ttl_days: int = Field(
        default=30, description="TTL for cached keyword data in days"
    )

    # Competitor analysis cache settings
    competitor_analysis_cache_ttl_days: int = Field(
        default=7, description="TTL for cached competitor analysis data in days"
    )

    # Email/SMTP Configuration
    smtp_host: str | None = Field(
        default=None,
        description="SMTP server hostname",
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port (587 for TLS, 465 for SSL)",
    )
    smtp_username: str | None = Field(
        default=None,
        description="SMTP authentication username",
    )
    smtp_password: str | None = Field(
        default=None,
        description="SMTP authentication password",
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS for SMTP connection",
    )
    smtp_use_ssl: bool = Field(
        default=False,
        description="Use SSL for SMTP connection (alternative to TLS)",
    )
    smtp_timeout: float = Field(
        default=30.0,
        description="SMTP connection timeout in seconds",
    )
    smtp_from_email: str | None = Field(
        default=None,
        description="Default sender email address",
    )
    smtp_from_name: str = Field(
        default="Client Onboarding",
        description="Default sender display name",
    )
    # Circuit breaker settings for email
    email_circuit_failure_threshold: int = Field(
        default=5,
        description="Failures before email circuit opens",
    )
    email_circuit_recovery_timeout: float = Field(
        default=60.0,
        description="Seconds before attempting email recovery",
    )

    # Webhook Configuration
    webhook_timeout: float = Field(
        default=30.0,
        description="Webhook request timeout in seconds",
    )
    webhook_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for webhook requests",
    )
    webhook_retry_delay: float = Field(
        default=1.0,
        description="Base delay between webhook retries in seconds",
    )
    # Circuit breaker settings for webhooks
    webhook_circuit_failure_threshold: int = Field(
        default=5,
        description="Failures before webhook circuit opens",
    )
    webhook_circuit_recovery_timeout: float = Field(
        default=60.0,
        description="Seconds before attempting webhook recovery",
    )

    # Google Cloud NLP API (entity extraction)
    google_nlp_api_key: str | None = Field(
        default=None,
        description="Google Cloud NLP API key for entity extraction",
    )
    google_nlp_project_id: str | None = Field(
        default=None,
        description="Google Cloud project ID (required for some operations)",
    )
    google_nlp_timeout: float = Field(
        default=30.0, description="Google Cloud NLP API request timeout in seconds"
    )
    google_nlp_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for Google Cloud NLP API requests",
    )
    google_nlp_retry_delay: float = Field(
        default=1.0, description="Base delay between retries in seconds"
    )
    # Circuit breaker settings for Google Cloud NLP
    google_nlp_circuit_failure_threshold: int = Field(
        default=5, description="Failures before circuit opens"
    )
    google_nlp_circuit_recovery_timeout: float = Field(
        default=60.0, description="Seconds before attempting recovery"
    )

    # DataForSEO API (primary SERP/keyword data provider)
    dataforseo_api_login: str | None = Field(
        default=None,
        description="DataForSEO API login (email)",
    )
    dataforseo_api_password: str | None = Field(
        default=None,
        description="DataForSEO API password",
    )
    dataforseo_timeout: float = Field(
        default=60.0, description="DataForSEO API request timeout in seconds"
    )
    dataforseo_max_retries: int = Field(
        default=3, description="Maximum retry attempts for DataForSEO API requests"
    )
    dataforseo_retry_delay: float = Field(
        default=1.0, description="Base delay between retries in seconds"
    )
    dataforseo_default_location_code: int = Field(
        default=2840, description="Default location code (2840=United States)"
    )
    dataforseo_default_language_code: str = Field(
        default="en", description="Default language code"
    )
    # Circuit breaker settings for DataForSEO
    dataforseo_circuit_failure_threshold: int = Field(
        default=5, description="Failures before circuit opens"
    )
    dataforseo_circuit_recovery_timeout: float = Field(
        default=60.0, description="Seconds before attempting recovery"
    )

    # PageOptimizer Pro (POP) API (content optimization scoring)
    pop_api_key: str | None = Field(
        default=None,
        description="PageOptimizer Pro API key for content scoring",
    )
    pop_api_url: str = Field(
        default="https://api.pageoptimizer.pro",
        description="PageOptimizer Pro API base URL",
    )
    pop_task_poll_interval: float = Field(
        default=2.0, description="Interval in seconds between task status polls"
    )
    pop_task_timeout: float = Field(
        default=300.0, description="Maximum time in seconds to wait for task completion"
    )
    pop_max_retries: int = Field(
        default=3, description="Maximum retry attempts for POP API requests"
    )
    pop_retry_delay: float = Field(
        default=1.0, description="Base delay between retries in seconds"
    )
    # Circuit breaker settings for POP
    pop_circuit_failure_threshold: int = Field(
        default=5, description="Failures before circuit opens"
    )
    pop_circuit_recovery_timeout: float = Field(
        default=60.0, description="Seconds before attempting recovery"
    )
    # POP content scoring threshold
    pop_pass_threshold: int = Field(
        default=70,
        description="Minimum page score (0-100) for content to pass quality gate",
    )
    # POP feature flags for safe rollout
    use_pop_content_brief: bool = Field(
        default=False,
        description="Enable POP integration for content briefs (default: disabled for safe rollout)",
    )
    use_pop_scoring: bool = Field(
        default=False,
        description="Enable POP integration for content scoring (default: disabled for safe rollout)",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
