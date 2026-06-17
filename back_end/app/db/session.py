"""
Database Session - Khởi tạo kết nối PostgreSQL (Supabase) và Redis (Upstash).
Tối ưu cho môi trường free-tier (1GB RAM):
  - Pool size nhỏ (5-10), max_overflow thấp
  - statement_timeout chặn query treo

Schema: public (theo SCHEMA_DOCUMENTATION.md).
"""
from typing import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.rate_limit import set_redis_client

# ============== PostgreSQL (Async) ==============
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

_POOL_SIZE = min(settings.DB_POOL_SIZE, 5)
_MAX_OVERFLOW = min(settings.DB_MAX_OVERFLOW, 10)

_connect_args: dict = {
    "server_settings": {
        "application_name": "steam-game-api",
        "statement_timeout": "30000",
        "lock_timeout": "10000",
    },
}
# Supabase yêu cầu SSL; tách sslmode khỏi URL và dùng connect_args.
if "sslmode=require" in _db_url or "sslmode=prefer" in _db_url:
    _db_url = _db_url.split("?")[0]
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
    """FastAPI dependency cung cấp database session cho mỗi request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============== Redis (Async) ==============
_redis_url = settings.REDIS_URL
if _redis_url and _redis_url.startswith("redis://"):
    _redis_url = _redis_url.replace("redis://", "rediss://", 1)

redis_client: aioredis.Redis = aioredis.from_url(
    _redis_url,
    encoding="utf-8",
    decode_responses=True,
    max_connections=10,
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
    Khởi tạo database - tạo các bảng nếu chưa tồn tại (chỉ dành cho dev/test).
    Trong production, hãy dùng db_init_supabase.sql.
    """
    from app.db.base import Base  # noqa: F401
    from app.models import steam, user  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Đóng kết nối database khi shutdown app."""
    await async_engine.dispose()