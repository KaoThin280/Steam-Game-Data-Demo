"""
Rate Limit - Sử dụng Redis (Upstash) để giới hạn số lượng request.
Hỗ trợ:
  - Rate limit theo IP (mặc định)
  - Rate limit theo user_id (nếu đã đăng nhập, ưu tiên hơn)
  - Pipeline INCR + EXPIRE (atomic, tránh race condition)
  - Sliding window option (key theo giây)
"""
import time
from functools import wraps
from typing import Callable, Optional

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, status

from app.core.config import settings

# Redis client sẽ được khởi tạo trong db/session.py
# và import vào đây để dùng
_redis_client: aioredis.Redis | None = None


def set_redis_client(client: aioredis.Redis) -> None:
    """Inject redis client từ db/session.py."""
    global _redis_client
    _redis_client = client


def get_redis_client() -> aioredis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis client chưa được khởi tạo.")
    return _redis_client


def _client_identifier(request: Request) -> str:
    """
    Lấy định danh để tính rate limit.
    Ưu tiên: user_id (nếu có) > IP.
    """
    # Lấy user_id từ state nếu auth middleware đã chạy
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    # Fallback IP
    if request.client:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        return f"ip:{request.client.host}"
    return "ip:unknown"


async def rate_limit(
    request: Request,
    limit: Optional[int] = None,
    window: int = 60,
    bucket: str = "default",
) -> None:
    """
    Dependency kiểm tra rate limit.

    Args:
        request: FastAPI request
        limit: Số request tối đa (None = dùng settings)
        window: Khoảng thời gian (giây)
        bucket: Tên bucket (vd: "auth", "ai", "default")
    """
    client = get_redis_client()
    identifier = _client_identifier(request)
    limit = limit or settings.RATE_LIMIT_PER_MINUTE
    key = f"rate_limit:{bucket}:{identifier}"

    # Pipeline atomic: INCR + EXPIRE (lần đầu set TTL)
    pipe = client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window, nx=True)  # chỉ set TTL nếu chưa có
    count, _ = await pipe.execute()

    if int(count) > limit:
        ttl = await client.ttl(key)
        if ttl < 0:
            ttl = window
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Quá nhiều request. Thử lại sau {ttl} giây.",
            headers={
                "Retry-After": str(ttl),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(ttl),
            },
        )

    # Set header cho client biết
    request.state.rate_limit_remaining = limit - int(count)
    request.state.rate_limit_limit = limit


def rate_limit_decorator(
    limit: int, window: int = 60, bucket: str = "custom"
) -> Callable:
    """
    Decorator dùng cho từng endpoint nếu cần custom limit.
    Ví dụ: @rate_limit_decorator(limit=10, window=60, bucket="ai")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request") or args[0]
            await rate_limit(request, limit=limit, window=window, bucket=bucket)
            return await func(*args, **kwargs)

        return wrapper

    return decorator
