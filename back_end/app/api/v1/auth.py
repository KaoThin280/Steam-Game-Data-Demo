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
from app.models.user import AppUser, Role, Permission
from app.schemas.token_schema import (
    AccessTokenResponse,
    RefreshTokenRequest,
    TokenResponse,
)
from app.schemas.user_schema import (
    AssignRoleRequest,
    UserCreate,
    UserLogin,
    UserMe,
    UserOut,
    UserPasswordUpdate,
    UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============ Helpers ============
def _user_to_out(user: AppUser) -> UserOut:
    """Convert AppUser ORM -> UserOut schema (flatten roles + permissions)."""
    role_names = []
    perm_names = []
    seen_perms = set()
    for ur in (user.roles or []):
        if ur.role is None:
            continue
        role_names.append(ur.role.role_name)
        for rp in (ur.role.permissions or []):
            if rp.permission and rp.permission.permission_name not in seen_perms:
                seen_perms.add(rp.permission.permission_name)
                perm_names.append(rp.permission.permission_name)
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
        roles=role_names,
        permissions=sorted(perm_names),
    )


def _me_to_out(user: AppUser) -> UserMe:
    base = _user_to_out(user)
    return UserMe(**base.model_dump())


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
    return _user_to_out(user)


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
    summary="Đăng xuất (revoke refresh token)",
)
async def logout(
    token: str = Depends(verify_refresh_token),
    auth_service: AuthService = Depends(get_auth_service),
):
    await auth_service.logout(token)
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
    if payload.new_password != payload.confirm_new_password:
        from app.core.exceptions import UnauthorizedException

        raise UnauthorizedException(detail="Mật khẩu xác nhận không khớp.")
    await auth_service.change_password(
        current_user, payload.old_password, payload.new_password
    )
    return None