"""
Core Config - Đọc biến môi trường (.env)
Hỗ trợ cả 2 format Redis (REDIS_URL hoặc REDIS_HOST/PORT/PASSWORD).
"""
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ============== App Info ==============
    APP_NAME: str = "Steam Game Data API"
    APP_VERSION: str = "1.1.0"
    DEBUG: bool = False
    ENABLE_LEGACY_AI: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ============== Server ==============
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ============== Security / JWT ==============
    SECRET_KEY: str = "change-me-to-a-random-secret-key-min-32-chars"
    ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "steam-game-data-api"
    JWT_AUDIENCE: str = "steam-game-data-client"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ============== Database (Aiven PostgreSQL) ==============
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    # Read-only DB user for AI SQL execution (defense-in-depth)
    # If empty, AI queries use the main DATABASE_URL
    DATABASE_URL_READONLY: Optional[str] = None
    DB_SSL_VERIFY: bool = True

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
    CORS_ORIGINS: List[str] = []

    # ============== OpenRouter AI ==============
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "~deepseek/deepseek-v4-flash-latest"
    OPENROUTER_FALLBACK_MODEL: str = "openrouter/owl-alpha"
    LLM_TIMEOUT: float = 120.0  # seconds, OpenRouter request timeout

    # ============== Bounded Agent Harness ==============
    AGENT_MAX_STEPS: int = 8
    AGENT_TOOL_TIMEOUT: float = 12.0
    AGENT_HISTORY_RUNS: int = 20
    AGENT_EVENT_MAX_BYTES: int = 65536
    MCP_SERVER_URL: str = "http://127.0.0.1:8001/mcp"
    MCP_SHARED_SECRET: str = ""

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

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _security_invariants(self) -> "Settings":
        if not self.DEBUG:
            if self.SECRET_KEY == "change-me-to-a-random-secret-key-min-32-chars" or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "Production SECRET_KEY must be random and at least 32 characters"
                )
            if "*" in self.CORS_ORIGINS:
                raise ValueError("Wildcard CORS is forbidden with credentials")
        if self.ALGORITHM not in {"HS256", "HS384", "HS512"}:
            raise ValueError("Unsupported JWT algorithm")
        if not self.DATABASE_URL_READONLY:
            raise ValueError(
                "DATABASE_URL_READONLY is required so AI tools cannot use the application owner connection"
            )
        if not self.DEBUG and not self.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is required in production")
        if not 1 <= self.AGENT_MAX_STEPS <= 30:
            raise ValueError("AGENT_MAX_STEPS must be between 1 and 30")
        if not 1 <= self.AGENT_TOOL_TIMEOUT <= 60:
            raise ValueError("AGENT_TOOL_TIMEOUT must be between 1 and 60 seconds")
        if not self.DEBUG and len(self.MCP_SHARED_SECRET) < 32:
            raise ValueError("Production MCP_SHARED_SECRET must be random and at least 32 characters")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
