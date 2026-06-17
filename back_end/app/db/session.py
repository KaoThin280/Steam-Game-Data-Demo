"""
Database Session - PostgreSQL (Supabase) + Redis (Upstash).
Optimised for free-tier (1GB RAM).

Schema: public (per SCHEMA_DOCUMENTATION.md).

Supports both:
  - Direct connection:   postgresql://...@db.xxx.supabase.co:5432/postgres
  - Supabase Pooler:     postgresql://...@aws-0-xxx.pooler.supabase.com:6543/postgres
                         (Transaction mode - disables prepared statements to be safe)
"""
import re
from typing import AsyncGenerator
from urllib.parse import quote, urlparse, urlunparse

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.rate_limit import set_redis_client


def _normalize_db_url(raw_url: str) -> str:
    """
    Normalise the DATABASE_URL so it can be safely fed into asyncpg.

    Operations performed (in order):
      1. Strip leading "DATABASE_URL=" duplicates (in case the user pasted it twice).
      2. Convert "postgresql://" -> "postgresql+asyncpg://" so SQLAlchemy uses asyncpg.
      3. URL-encode the password component so special characters like @,
         : / ? # [ ] % are safe.
      4. Strip any query string (asyncpg accepts connect_args for SSL instead).

    The returned URL is always safe to pass to `create_async_engine`.
    """
    if not raw_url:
        return raw_url

    # 1) Handle duplicated prefix (defensive).
    url = raw_url.strip()
    while url.startswith("DATABASE_URL="):
        url = url[len("DATABASE_URL="):].lstrip()

    # 2) Translate scheme.
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]

    # 3) Encode password.
    parsed = urlparse(url)
    if parsed.password:
        # quote() with safe="" encodes everything reserved.
        encoded_pw = quote(parsed.password, safe="")
        # Re-build netloc with the encoded password.
        userinfo = ""
        if parsed.username:
            userinfo = quote(parsed.username, safe="")
        if encoded_pw:
            userinfo = f"{userinfo}:{encoded_pw}" if userinfo else f":{encoded_pw}"
        netloc = parsed.hostname or ""
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        new_netloc = f"{userinfo}@{netloc}" if userinfo else netloc
        url = urlunparse(parsed._replace(netloc=new_netloc))

    # 4) Strip query (asyncpg takes ssl via connect_args).
    parsed = urlparse(url)
    if parsed.query:
        url = urlunparse(parsed._replace(query=""))

    return url


# ============== PostgreSQL (Async) ==============
_db_url = _normalize_db_url(settings.DATABASE_URL)

_POOL_SIZE = min(settings.DB_POOL_SIZE, 5)
_MAX_OVERFLOW = min(settings.DB_MAX_OVERFLOW, 10)

_connect_args: dict = {
    "server_settings": {
        "application_name": "steam-game-api",
        "statement_timeout": "30000",
        "lock_timeout": "10000",
    },
}

# Detect Supabase pooler (Transaction mode on port 6543). asyncpg's prepared
# statement cache breaks in Transaction mode pooler -> disable it.
_is_pooler = (
    "pooler.supabase.com" in _db_url
    or ":6543" in _db_url
)
if _is_pooler:
    _connect_args["prepared_statement_cache_size"] = 0
    _connect_args["statement_cache_size"] = 0

# Supabase requires SSL; pass a TLS context via connect_args.
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
    Trong production, hãy dùng db_extra_tables.sql + db_init_supabase.sql.
    """
    from app.db.base import Base  # noqa: F401
    from app.models import steam, user  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Đóng kết nối database khi shutdown app."""
    await async_engine.dispose()