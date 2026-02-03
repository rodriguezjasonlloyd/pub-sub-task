from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Redis Configuration
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)

    # MongoDB Configuration
    mongodb_uri: str = Field(default="mongodb://localhost:27017/article_pipeline")

    # Discord Webhook
    discord_webhook_url: HttpUrl | None = Field(None)

    # Application Settings
    log_level: str = Field(default="INFO")
    max_retries: int = Field(default=3)
    retry_backoff_base: int = Field(default=1)

    # Queue names
    queue_name: str = Field(default="article_queue")
    dlq_name: str = Field(default="article_queue:failed")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Singleton instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the settings singleton instance."""
    global _settings

    if _settings is None:
        _settings = Settings()

    return _settings
