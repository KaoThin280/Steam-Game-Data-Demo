"""
API Dependencies - FastAPI dependencies:
  - Authentication (JWT access token via httpOnly cookie OR Bearer header)
  - Active user check
  - Role-based authorization (admin, analyst, scientist, viewer)
  - Permission-based authorization (granular perms)
"""
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.db.session import get_db
from app.models.user import AppUser, RoleName
from app.services.auth_service import AuthService
from app.utils.auth_cookies import COOKIE_ACCESS, COOKIE_REFRESH

# OAuth2 scheme cho Swagger docs
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


# ============ Authentication ============
async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    sgd_access_token: Optional[str] = Cookie(default=None, alias=COOKIE_ACCESS),
    db: AsyncSession = Depends(get_db),
) -> AppUser:
    """
    Lấy user hiện tại từ access token.

    Ưu tiên: httpOnly cookie (an toàn hơn) → Bearer header (backward compat).
    """
    # Cookie takes precedence (set by login endpoint).
    access_token = sgd_access_token or token
    if not access_token:
        raise UnauthorizedException(detail="Thiếu access token.")

    auth_service = AuthService(db)
    return await auth_service.get_current_user_from_token(access_token)


async def get_current_active_user(
    user: AppUser = Depends(get_current_user),
) -> AppUser:
    """User phải đang active (is_active=True)."""
    if not user.is_active:
        raise UnauthorizedException(detail="Tài khoản đã bị khóa.")
    return user


# ============ Role-based dependencies ============
def require_role(*role_names: str):
    """
    Factory trả về dependency kiểm tra user có ít nhất 1 trong các role.

    Example:
        @router.post(..., dependencies=[Depends(require_role(RoleName.ADMIN.value))])
    """

    allowed = set(role_names)

    async def _checker(
        user: AppUser = Depends(get_current_active_user),
    ) -> AppUser:
        if not user.has_role(*allowed):
            raise ForbiddenException(
                detail=f"Yêu cầu role: {', '.join(sorted(allowed))}."
            )
        return user

    return _checker


def require_permission(*permission_names: str):
    """
    Factory trả về dependency kiểm tra user có permission cụ thể.

    Example:
        @router.post(..., dependencies=[Depends(require_permission("games_delete"))])
    """
    required = list(permission_names)

    async def _checker(
        user: AppUser = Depends(get_current_active_user),
    ) -> AppUser:
        # System admin bypass everything
        if user.has_permission("system_admin") or user.has_role(RoleName.ADMIN.value):
            return user
        for perm in required:
            if not user.has_permission(perm):
                raise ForbiddenException(
                    detail=f"Thiếu permission: {perm}."
                )
        return user

    return _checker


# Common shortcuts (admin only)
get_current_admin = require_role(RoleName.ADMIN.value)
get_current_admin_or_scientist = require_role(
    RoleName.ADMIN.value, RoleName.SCIENTIST.value
)


# ============ Refresh-token dep ============
async def verify_refresh_token(
    sgd_refresh_token: Optional[str] = Cookie(default=None, alias=COOKIE_REFRESH),
    authorization: Optional[str] = Header(None),
) -> str:
    """
    Lấy refresh token: ưu tiên httpOnly cookie, fallback Bearer header.
    """
    if sgd_refresh_token:
        return sgd_refresh_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Thiếu refresh token.",
    )


# ============ Service injection ============
def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)