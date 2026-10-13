"""Validated environment settings; secrets never enter API responses."""

from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    APP_ENV: Literal["development", "test", "production"] = "development"
    DATABASE_URL: str = (
        "postgresql+asyncpg://miningintel:miningintel@localhost:5432/miningintel"
    )
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: SecretStr = SecretStr("")
    QDRANT_COLLECTION: str = "miningintel_articles"
    QDRANT_TIMEOUT: float = Field(default=10, gt=0, le=30)
    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_BASE_URL: str = "https://api.example.com/v1"
    LLM_MODEL: str = "configure-your-model"
    LLM_EXTRA_BODY: dict[str, Any] = Field(default_factory=dict)
    LLM_TIMEOUT: float = Field(default=90, gt=0, le=300)
    CHAT_LLM_MODEL: str = ""
    CHAT_LLM_EXTRA_BODY: dict[str, Any] = Field(default_factory=dict)
    CHAT_LLM_TIMEOUT: float = Field(default=90, gt=0, le=300)
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    EMBEDDING_DIM: Literal[1024] = 1024
    ML_ENABLED: bool = False
    MODEL_CACHE_DIR: str | None = None
    ML_DEVICE: str = "cpu"
    RATE_LIMIT_BACKEND: Literal["redis", "memory"] = "redis"
    API_RATE_LIMIT: str = "120/minute"
    CACHE_ENABLED: bool = True
    DIGEST_TIMEZONE: str = "Asia/Shanghai"
    SMTP_HOST: str = ""
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: SecretStr = SecretStr("")
    SMTP_FROM: str = ""
    SMTP_STARTTLS: bool = True
    SMTP_SSL: bool = False
    EMAIL_NOTIFICATIONS_ENABLED: bool = False
    WEBHOOK_NOTIFICATIONS_ENABLED: bool = False
    SLACK_WEBHOOK_URL: SecretStr = SecretStr("")
    FEISHU_WEBHOOK_URL: SecretStr = SecretStr("")
    FEISHU_WEBHOOK_SECRET: SecretStr = SecretStr("")
    WECOM_WEBHOOK_URL: SecretStr = SecretStr("")
    PUBLIC_SITE_URL: str = "http://localhost:3000"
    FETCH_INTERVAL: int = Field(default=900, ge=60)
    FETCH_TIMEOUT: float = Field(default=30, gt=0, le=120)
    FETCH_MAX_BYTES: int = Field(default=5_000_000, ge=1024)
    FETCH_RETRIES: int = Field(default=3, ge=1, le=5)
    FETCH_DNS_RESOLVER: str = ""
    FETCH_BROWSER_CHANNEL: str = ""
    FETCH_DISTRIBUTED_PACING: bool = False
    TRANSLATION_CHUNK_SIZE: int = Field(default=4000, ge=500, le=6000)
    SPACY_MODEL: str = ""
    ENTITY_MATCHER: Literal["spacy", "dictionary"] = "spacy"
    ENRICHMENT_MODE: Literal["full", "editorial"] = "full"
    USER_AGENT: str = "MiningIntel/0.1 (+https://example.com/contact)"
    SECRET_KEY: SecretStr = SecretStr("dev-only-change-this-32-character-secret")
    ACCESS_TOKEN_MINUTES: int = Field(default=60, ge=5, le=1440)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    AUTO_PUBLISH: bool = False
    PUBLISH_QUALITY_THRESHOLD: float = Field(default=70, ge=0, le=100)
    INITIALIZATION_QUALITY_THRESHOLD: float = Field(default=50, ge=0, le=100)
    RAG_TOP_K: int = Field(default=5, ge=1, le=20)
    RAG_CANDIDATES: int = Field(default=20, ge=10, le=200)
    RAG_RERANK_CANDIDATES: int = Field(default=20, ge=5, le=100)
    INDEX_BATCH_SIZE: int = Field(default=100, ge=1, le=1000)
    EVENT_SIMILARITY_THRESHOLD: float = Field(default=0.86, gt=0, lt=1)
    PRICE_ALERT_THRESHOLD: float = Field(default=3, gt=0)
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "artifacts/logs"
    LOG_RETENTION_DAYS: int = Field(default=14, ge=1, le=365)
    TASK_HISTORY_DAYS: int = Field(default=7, ge=1, le=90)
    TASK_HISTORY_LIMIT: int = Field(default=10000, ge=100, le=100000)

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        """Reject unsafe defaults before serving production traffic."""
        secret = self.SECRET_KEY.get_secret_value()
        if self.APP_ENV == "production":
            if self.RATE_LIMIT_BACKEND != "redis":
                raise ValueError("Production rate limiting requires Redis")
            if not self.FETCH_DISTRIBUTED_PACING:
                raise ValueError("Production collectors require Redis origin pacing")
            if len(secret) < 32 or secret.startswith(("dev-only", "REPLACE_")):
                raise ValueError("Production SECRET_KEY must be random and >=32 chars")
            if "*" in self.CORS_ORIGINS:
                raise ValueError("Production CORS_ORIGINS must list exact origins")
        return self


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""
    return Settings()
