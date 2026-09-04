"""
Auth API - Đăng ký, Đăng nhập, Refresh Token, Profile.
Tokens được set dưới dạng httpOnly cookies để bảo mật (Item #5).
Có rate limit riêng cho login/register (chống brute force).
"""
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_auth_service,
    get_current_active_user,
    verify_refresh_token,
)
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import AppUser
from app.schemas.token_schema import (
    AccessTokenResponse,
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
from app.utils.auth_cookies import (
    clear_auth_cookies,
    set_access_cookie,
    set_auth_cookies,
)
from app.utils.user_helpers import user_to_out

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============ Helpers ============
def _me_to_out(user: AppUser) -> UserMe:
    base = user_to_out(user)
    return UserMe(**base.model_dump())


def _build_token_payload(tokens: TokenResponse) -> dict:
    """Return access token only; refresh credentials stay in httpOnly cookies."""
    return {
        "access_token": tokens.access_token,
        "token_type": tokens.token_type,
        "expires_in": tokens.expires_in,
    }


# ============ Register / Login / Logout / Refresh ============
@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Đăng ký tài khoản mới (mặc định role: viewer)",
)
async def register(
    request: Request,
    payload: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
):
    await rate_limit(
        request,
        limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        window=60,
        bucket="auth-register",
    )
    user = await auth_service.register(payload)
    return user_to_out(user)


@router.post(
    "/login",
    summary="Đăng nhập (refresh token chỉ nằm trong httpOnly cookie)",
)
async def login(
    request: Request,
    payload: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Access token is returned for API clients. The refresh token is only stored
    in an httpOnly cookie and is never exposed to JavaScript.
    """
    await rate_limit(
        request,
        limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        window=60,
        bucket="auth-login",
    )
    tokens = await auth_service.login(payload)
    response = JSONResponse(content=_build_token_payload(tokens))
    set_auth_cookies(
        response,
        tokens.access_token,
        tokens.refresh_token,
        access_expires_seconds=tokens.expires_in,
        refresh_expires_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Làm mới access token (set httpOnly cookie mới)",
)
async def refresh_token(
    request: Request,
    response: Response,
    token: str = Depends(verify_refresh_token),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    Refresh access token. Cookie mới được set tự động.
    """
    await rate_limit(
        request,
        limit=settings.RATE_LIMIT_AUTH_PER_MINUTE,
        window=60,
        bucket="auth-refresh",
    )
    result = await auth_service.refresh_access_token(token)
    set_auth_cookies(
        response,
        result.access_token,
        result.refresh_token,
        access_expires_seconds=result.expires_in,
        refresh_expires_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    response.headers["Cache-Control"] = "no-store"
    return AccessTokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=result.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đăng xuất (revoke refresh token + clear cookies)",
)
async def logout(
    response: Response,
    token: str = Depends(verify_refresh_token),
    auth_service: AuthService = Depends(get_auth_service),
):
    await auth_service.logout(token)
    clear_auth_cookies(response)
    return None


# ============ Profile ============
@router.get(
    "/me",
    response_model=UserMe,
    summary="Thông tin user hiện tại (kèm roles + permissions)",
)
async def get_me(current_user: AppUser = Depends(get_current_active_user)):
    return _me_to_out(current_user)


@router.put(
    "/me",
    response_model=UserMe,
    summary="Cập nhật thông tin cá nhân",
)
async def update_me(
    payload: UserUpdate,
    current_user: AppUser = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    user = await auth_service.update_profile(current_user, payload)
    return _me_to_out(user)


@router.put(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đổi mật khẩu",
)
async def change_password(
    payload: UserPasswordUpdate,
    current_user: AppUser = Depends(get_current_active_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    from app.core.exceptions import UnauthorizedException

    if payload.new_password != payload.confirm_new_password:
        raise UnauthorizedException(detail="Mật khẩu xác nhận không khớp.")
    await auth_service.change_password(
        current_user, payload.old_password, payload.new_password
    )
    return None
