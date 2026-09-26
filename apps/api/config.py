"""
Configuration and Environment Settings for SIGNAL API
"""
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application Settings
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "SIGNAL"
    APP_VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Authentication & Security
    SECRET_KEY: str = "signal-super-secret-key-production-change-me-32bytes"
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    @property
    def jwt_secret(self) -> str:
        return self.JWT_SECRET_KEY or self.SECRET_KEY

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Scheduler
    ENABLE_SCHEDULER: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./signal_dev.db"
    DATABASE_ECHO: bool = False

    # AI Gateway Providers
    AI_PRIMARY_PROVIDER: str = "mock"
    AI_SECONDARY_PROVIDER: str = "gemini"
    AI_FALLBACK_PROVIDER: str = "openai"

    # Task Routing Overrides
    AI_ROUTING_CLASSIFICATION: str = "mock"
    AI_ROUTING_EXTRACTION: str = "mock"
    AI_ROUTING_SUMMARIZATION: str = "mock"

    # API Keys
    NVIDIA_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Notifications & Personalization
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_DEFAULT_CHAT_ID: str = ""
    DISCORD_WEBHOOK_URL: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "alerts@signal.dev"
    SMTP_USE_TLS: bool = True
    SIGNAL_NOTIFICATION_PROVIDER: str = "mock"
    SIGNAL_DEFAULT_MIN_RELEVANCE_SCORE: int = 70
    SIGNAL_DEFAULT_DAILY_NOTIFICATION_LIMIT: int = 10
    SIGNAL_CRITICAL_ALERT_BYPASS_QUIET_HOURS: bool = True
    SIGNAL_CRITICAL_ALERT_BYPASS_RATE_LIMIT: bool = True

    # Ingestion Settings
    INGESTION_DEFAULT_INTERVAL: int = 300


settings = Settings()
