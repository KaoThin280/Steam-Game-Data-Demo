"""
Config - Đọc biến môi trường (.env)
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    HOST = os.getenv("APP_HOST", "0.0.0.0")
    PORT = int(os.getenv("APP_PORT", "5000"))

    # Admin root credentials
    ADMIN_ROOT_USERNAME = os.getenv("ADMIN_ROOT_USERNAME", "admin_root")
    ADMIN_ROOT_PASSWORD = os.getenv("ADMIN_ROOT_PASSWORD", "AdminRoot@2024")

    # PostgreSQL
    DATABASE_URL = os.getenv("DATABASE_URL", "")

    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "")

