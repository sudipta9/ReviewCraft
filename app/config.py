"""
Configuration Management Module

This module provides a centralized, type-safe configuration system using Pydantic.
It follows the 12-factor app methodology for configuration management.

Features:
- Environment-based configuration
- Type validation and casting
- Default values with documentation
- Multiple environment support (dev, test, prod)
"""

import os
from enum import Enum
from functools import lru_cache
from typing import Optional, List

from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Environment(str, Enum):
    """Supported application environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class CeleryConfig(BaseModel):
    """Celery-specific configuration."""

    broker_url: str = Field(
        default="amqp://guest:guest@localhost:5672//",
        description="Celery message broker URL",
    )
    result_backend: str = Field(
        default="redis://localhost:6379/0", description="Celery result backend URL"
    )
    task_track_started: bool = Field(
        default=True, description="Track when tasks are started"
    )
    task_serializer: str = Field(
        default="json", description="Task serialization format"
    )
    result_serializer: str = Field(
        default="json", description="Result serialization format"
    )
    accept_content: List[str] = Field(
        default=["json"], description="Accepted content types"
    )
    timezone: str = Field(default="UTC", description="Celery timezone")

    @classmethod
    def from_env(cls) -> "CeleryConfig":
        """Create configuration from environment variables."""
        return cls(
            broker_url=os.getenv(
                "CELERY_BROKER_URL", cls.model_fields["broker_url"].default
            ),
            result_backend=os.getenv(
                "CELERY_RESULT_BACKEND", cls.model_fields["result_backend"].default
            ),
            task_track_started=os.getenv("CELERY_TASK_TRACK_STARTED", "true").lower()
            == "true",
            task_serializer=os.getenv(
                "CELERY_TASK_SERIALIZER", cls.model_fields["task_serializer"].default
            ),
            result_serializer=os.getenv(
                "CELERY_RESULT_SERIALIZER",
                cls.model_fields["result_serializer"].default,
            ),
            timezone=os.getenv("CELERY_TIMEZONE", cls.model_fields["timezone"].default),
        )


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/code_review_db",
        description="Database connection URL",
    )
    echo: bool = Field(default=False, description="Enable SQLAlchemy query logging")
    pool_size: int = Field(default=10, description="Database connection pool size")
    max_overflow: int = Field(default=20, description="Maximum overflow connections")

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create configuration from environment variables."""
        return cls(
            url=os.getenv("DATABASE_URL", cls.model_fields["url"].default),
            echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
            pool_size=int(
                os.getenv(
                    "DATABASE_POOL_SIZE", str(cls.model_fields["pool_size"].default)
                )
            ),
            max_overflow=int(
                os.getenv(
                    "DATABASE_MAX_OVERFLOW",
                    str(cls.model_fields["max_overflow"].default),
                )
            ),
        )


class GitHubConfig(BaseModel):
    """GitHub API configuration."""

    token: Optional[str] = Field(
        default=None, description="GitHub personal access token"
    )
    api_url: str = Field(
        default="https://api.github.com", description="GitHub API base URL"
    )
    rate_limit_retry: bool = Field(
        default=True, description="Enable rate limit retry logic"
    )
    max_retries: int = Field(default=3, description="Maximum retry attempts")

    @classmethod
    def from_env(cls) -> "GitHubConfig":
        """Create configuration from environment variables."""
        return cls(
            token=os.getenv("GITHUB_TOKEN"),
            api_url=os.getenv("GITHUB_API_URL", cls.model_fields["api_url"].default),
            rate_limit_retry=os.getenv("GITHUB_RATE_LIMIT_RETRY", "true").lower()
            == "true",
            max_retries=int(
                os.getenv(
                    "GITHUB_MAX_RETRIES", str(cls.model_fields["max_retries"].default)
                )
            ),
        )


class AIConfig(BaseModel):
    """AI/LLM configuration."""

    # OpenRouter Configuration
    openrouter_api_key: Optional[str] = Field(
        default=None, description="OpenRouter API key"
    )
    openrouter_model: str = Field(
        default="qwen/qwen3-coder:free", description="OpenRouter model to use"
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter API base URL"
    )
    temperature: float = Field(default=0.1, description="Model temperature setting")
    max_tokens: int = Field(default=4000, description="Maximum tokens for AI responses")

    @classmethod
    def from_env(cls) -> "AIConfig":
        """Create configuration from environment variables."""
        return cls(
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            openrouter_model=os.getenv(
                "AI_OPENROUTER_MODEL", cls.model_fields["openrouter_model"].default
            ),
            openrouter_base_url=os.getenv(
                "AI_OPENROUTER_BASE_URL",
                cls.model_fields["openrouter_base_url"].default,
            ),
            temperature=float(
                os.getenv(
                    "AI_TEMPERATURE",
                    str(cls.model_fields["temperature"].default),
                )
            ),
            max_tokens=int(
                os.getenv("AI_MAX_TOKENS", str(cls.model_fields["max_tokens"].default))
            ),
        )


class RedisConfig(BaseModel):
    """Redis configuration."""

    url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )
    cache_ttl: int = Field(default=3600, description="Default cache TTL in seconds")
    max_connections: int = Field(default=10, description="Maximum Redis connections")

    @classmethod
    def from_env(cls) -> "RedisConfig":
        """Create configuration from environment variables."""
        return cls(
            url=os.getenv("REDIS_URL", cls.model_fields["url"].default),
            cache_ttl=int(
                os.getenv("REDIS_CACHE_TTL", str(cls.model_fields["cache_ttl"].default))
            ),
            max_connections=int(
                os.getenv(
                    "REDIS_MAX_CONNECTIONS",
                    str(cls.model_fields["max_connections"].default),
                )
            ),
        )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )
    structured: bool = Field(default=True, description="Use structured logging (JSON)")

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Create configuration from environment variables."""
        return cls(
            level=os.getenv("LOG_LEVEL", cls.model_fields["level"].default),
            format=os.getenv("LOG_FORMAT", cls.model_fields["format"].default),
            structured=os.getenv("LOG_STRUCTURED", "true").lower() == "true",
        )


class Settings(BaseModel):
    """Main application settings."""

    # Application
    app_name: str = Field(default="Code Review Agent", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Application environment"
    )
    debug: bool = Field(default=True, description="Enable debug mode")

    # API
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_prefix: str = Field(default="/api/v1", description="API prefix")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")

    # Security
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT and other security features",
    )
    access_token_expire_minutes: int = Field(
        default=30, description="Access token expiration time in minutes"
    )

    # Rate Limiting
    rate_limit_requests: int = Field(
        default=100, description="Rate limit requests per minute"
    )
    rate_limit_window: int = Field(
        default=60, description="Rate limit window in seconds"
    )

    # Sub-configurations
    celery: CeleryConfig
    database: DatabaseConfig
    github: GitHubConfig
    ai: AIConfig
    redis: RedisConfig
    logging: LoggingConfig

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        env_str = os.getenv("ENVIRONMENT", "development").lower()
        try:
            environment = Environment(env_str)
        except ValueError:
            environment = Environment.DEVELOPMENT

        return cls(
            app_name=os.getenv("APP_NAME", cls.model_fields["app_name"].default),
            app_version=os.getenv(
                "APP_VERSION", cls.model_fields["app_version"].default
            ),
            environment=environment,
            debug=os.getenv("DEBUG", "true").lower() == "true",
            api_host=os.getenv("API_HOST", cls.model_fields["api_host"].default),
            api_port=int(
                os.getenv("API_PORT", str(cls.model_fields["api_port"].default))
            ),
            api_prefix=os.getenv("API_PREFIX", cls.model_fields["api_prefix"].default),
            cors_origins=os.getenv("CORS_ORIGINS", "*").split(","),
            secret_key=os.getenv("SECRET_KEY", cls.model_fields["secret_key"].default),
            access_token_expire_minutes=int(
                os.getenv(
                    "ACCESS_TOKEN_EXPIRE_MINUTES",
                    str(cls.model_fields["access_token_expire_minutes"].default),
                )
            ),
            rate_limit_requests=int(
                os.getenv(
                    "RATE_LIMIT_REQUESTS",
                    str(cls.model_fields["rate_limit_requests"].default),
                )
            ),
            rate_limit_window=int(
                os.getenv(
                    "RATE_LIMIT_WINDOW",
                    str(cls.model_fields["rate_limit_window"].default),
                )
            ),
            celery=CeleryConfig.from_env(),
            database=DatabaseConfig.from_env(),
            github=GitHubConfig.from_env(),
            ai=AIConfig.from_env(),
            redis=RedisConfig.from_env(),
            logging=LoggingConfig.from_env(),
        )

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.environment == Environment.TESTING

    def get_database_url(self, async_driver: bool = True) -> str:
        """Get database URL with appropriate driver."""
        url = self.database.url
        if not async_driver and "asyncpg" in url:
            return url.replace("postgresql+asyncpg", "postgresql+psycopg2")
        return url


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.

    This function uses LRU cache to ensure settings are loaded only once
    and reused throughout the application lifecycle.

    Returns:
        Settings: Application configuration object
    """
    return Settings.from_env()


# Global settings instance
settings = get_settings()
