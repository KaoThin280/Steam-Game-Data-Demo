"""
Core Config - Đọc biến môi trường (.env)
Hỗ trợ cả 2 format Redis (REDIS_URL hoặc REDIS_HOST/PORT/PASSWORD).
"""
from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ============== App Info ==============
    APP_NAME: str = "Steam Game Data API"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ============== Server ==============
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ============== Security / JWT ==============
    SECRET_KEY: str = "change-me-to-a-random-secret-key-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ============== Database (Aiven PostgreSQL) ==============
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # ============== Redis (Upstash) ==============
    # Hỗ trợ 1 trong 2 format
    REDIS_URL: Optional[str] = None
    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[int] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_TTL: int = 3600

    @model_validator(mode="after")
    def _build_redis_url(self) -> "Settings":
        """Nếu không có REDIS_URL thì dựng từ HOST/PORT/PASSWORD (Upstash)."""
        if not self.REDIS_URL and self.REDIS_HOST and self.REDIS_PASSWORD:
            port = self.REDIS_PORT or 6379
            self.REDIS_URL = f"rediss://default:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{port}"
        return self

    # ============== Rate Limit ==============
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AI_PER_MINUTE: int = 10          # Chat AI đắt hơn
    RATE_LIMIT_AUTH_PER_MINUTE: int = 20        # Auth endpoints giới hạn chặt

    # ============== CORS ==============
    CORS_ORIGINS: List[str] = ["*"]

    # ============== OpenRouter AI ==============
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "deepseek/deepseek-v4-flash"
    OPENROUTER_FALLBACK_MODEL: str = "openrouter/owl-alpha"

    # ============== E2B Sandbox ==============
    E2B_API_KEY: str = ""
    E2B_TEMPLATE: str = "base"
    E2B_TIMEOUT: int = 60

    # Sandbox artifacts dir (used by the agentic workflow)
    TEMP_DATA_DIR: str = "temp_data"

    # ============== Steam (optional) ==============
    STEAM_API_KEY: str = ""

    # ============== Bootstrap admin (tạo admin khi chạy lần đầu) ==============
    BOOTSTRAP_ADMIN_EMAIL: str = ""
    BOOTSTRAP_ADMIN_PASSWORD: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
