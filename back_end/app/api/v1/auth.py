"""
Auth API - Đăng ký, Đăng nhập, Refresh Token, Profile.
Có rate limit riêng cho login/register (chống brute force).
"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_auth_service,
    get_current_active_user,
    verify_refresh_token,
)
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.token_schema import (
    AccessTokenResponse,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.user_schema import (
    UserCreate,
    UserLogin,
    UserMe,
    UserOut,
    UserPasswordUpdate,
    UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký tài khoản mới",
)
async def register(
    request: Request,
    payload: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Đăng ký user mới và trả về thông tin."""
    await rate_limit(
        request,
        limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        window=60,
        bucket="auth-register",
    )
    user = await auth_service.register(payload)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Đăng nhập",
)
async def login(
    request: Request,
    payload: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Đăng nhập, trả về access_token và refresh_token."""
    await rate_limit(
        request,
        limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        window=60,
        bucket="auth-login",
    )
    return await auth_service.login(payload)


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Làm mới access token",
)
async def refresh_token(
    request: Request,
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Dùng refresh token để lấy access token mới."""
    await rate_limit(
        request,
        limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        window=60,
        bucket="auth-refresh",
    )
    result = await auth_service.refresh_access_token(payload.refresh_token)
    return AccessTokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đăng xuất",
)
async def logout(
    token: str = Depends(verify_refresh_token),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Revoke refresh token."""
    await auth_service.logout(token)
    return None


# ============ Profile ============
@router.get(
    "/me",
    response_model=UserMe,
    summary="Thông tin user hiện tại",
)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.put(
    "/me",
    response_model=UserMe,
    summary="Cập nhật thông tin cá nhân",
)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    return await auth_service.update_profile(current_user, payload)


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đổi mật khẩu",
)
async def change_password(
    payload: UserPasswordUpdate,
    current_user: User = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    if payload.new_password != payload.confirm_new_password:
        from app.core.exceptions import UnauthorizedException

        raise UnauthorizedException(detail="Mật khẩu xác nhận không khớp.")
    await auth_service.change_password(
        current_user, payload.old_password, payload.new_password
    )
    return None
