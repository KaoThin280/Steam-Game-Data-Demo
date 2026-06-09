"""
Database Session - Khởi tạo kết nối PostgreSQL (Aiven) và Redis (Upstash)
Tối ưu cho môi trường free-tier (1GB RAM):
  - Pool size nhỏ (5-10), max_overflow thấp
  - Đặt search_path = steam để truy vấn gọn
"""
from typing import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.rate_limit import set_redis_client

# ============== PostgreSQL (Async) ==============
# Chuyển URL từ postgresql:// sang postgresql+asyncpg:// nếu cần
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Pool size giảm cho free-tier (1GB RAM)
_POOL_SIZE = min(settings.DB_POOL_SIZE, 5)
_MAX_OVERFLOW = min(settings.DB_MAX_OVERFLOW, 10)

# Xử lý sslmode trong URL (chuyển sang connect_args cho asyncpg)
_connect_args: dict = {
    "server_settings": {
        "application_name": "steam-game-api",
        "search_path": "steam,public",
        "statement_timeout": "30000",
        "lock_timeout": "10000",
    },
}
# Nếu URL chứa sslmode=require, tách ra connect_args ssl
# Aiven dùng self-signed cert -> dùng ssl=False để skip verify (vẫn mã hoá TLS
# nếu server yêu cầu, nhưng không verify chain). Nếu muốn verify, set ssl=context.
if "sslmode=require" in _db_url or "sslmode=prefer" in _db_url:
    _db_url = _db_url.split("?")[0]  # bỏ query string
    # Dùng create_default_context nhưng không verify (Aiven self-signed)
    import ssl as _ssl
    _ssl_ctx = _ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx

async_engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,
    pool_size=_POOL_SIZE,
    max_overflow=_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
    connect_args=_connect_args,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency cung cấp database session cho mỗi request.
    Tự động đóng session khi request kết thúc.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============== Redis (Async) ==============
# Upstash yêu cầu SSL, dùng rediss://
_redis_url = settings.REDIS_URL
if _redis_url and _redis_url.startswith("redis://"):
    _redis_url = _redis_url.replace("redis://", "rediss://", 1)

redis_client: aioredis.Redis = aioredis.from_url(
    _redis_url,
    encoding="utf-8",
    decode_responses=True,
    max_connections=10,         # free-tier giới hạn
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True,
)


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency trả về redis client."""
    return redis_client


async def init_redis() -> None:
    """Khởi tạo và test redis connection, inject vào rate_limit module."""
    try:
        await redis_client.ping()
        set_redis_client(redis_client)
    except Exception as e:
        raise RuntimeError(f"Không thể kết nối Redis: {e}") from e


async def close_redis() -> None:
    """Đóng kết nối redis khi shutdown app."""
    await redis_client.close()


async def init_db() -> None:
    """
    Khởi tạo database - tạo các bảng nếu chưa tồn tại.
    Lưu ý: Nên dùng db_init.sql cho production, function này chỉ để dev/test.
    """
    # Import models để SQLAlchemy nhận diện
    from app.db.base import Base  # noqa: F401
    from app.models import steam, user  # noqa: F401

    async with async_engine.begin() as conn:
        # Tạo schema trước
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS steam"))
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Đóng kết nối database khi shutdown app."""
    await async_engine.dispose()
