"""
API Dependencies - Các hàm inject (current_user, verify token, ...)
"""
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

# OAuth2 scheme cho Swagger docs
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Lấy user hiện tại từ access token (Bearer trong header).
    """
    if not token:
        raise UnauthorizedException(detail="Thiếu access token.")

    auth_service = AuthService(db)
    return await auth_service.get_current_user_from_token(token)


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """User phải đang active."""
    if not user.is_active:
        raise UnauthorizedException(detail="Tài khoản đã bị khóa.")
    return user


async def get_current_admin(
    user: User = Depends(get_current_active_user),
) -> User:
    """User phải có role admin."""
    if user.role != UserRole.ADMIN.value:
        raise ForbiddenException(detail="Yêu cầu quyền admin.")
    return user


async def get_current_premium_or_admin(
    user: User = Depends(get_current_active_user),
) -> User:
    """User phải là premium hoặc admin."""
    if user.role not in (UserRole.ADMIN.value, UserRole.PREMIUM.value):
        raise ForbiddenException(
            detail="Yêu cầu quyền premium hoặc admin."
        )
    return user


async def verify_refresh_token(
    authorization: Optional[str] = Header(None),
) -> str:
    """Lấy refresh token từ header Authorization."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiếu refresh token.",
        )
    return authorization.split(" ", 1)[1]


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Inject AuthService."""
    return AuthService(db)
