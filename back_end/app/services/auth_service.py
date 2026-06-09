"""
Auth Service - Xử lý logic đăng ký, đăng nhập, phân quyền
"""
from datetime import datetime, timezone
from typing import Optional

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictException,
    InvalidCredentialsException,
    NotFoundException,
    TokenExpiredException,
    UnauthorizedException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import RefreshToken, User, UserRole
from app.schemas.token_schema import TokenResponse
from app.schemas.user_schema import UserCreate, UserLogin, UserUpdate


class AuthService:
    """Service xử lý authentication và authorization."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ============ Đăng ký ============
    async def register(self, payload: UserCreate) -> User:
        """Đăng ký user mới."""
        # Validate password match
        if payload.password != payload.confirm_password:
            raise UnauthorizedException(detail="Mật khẩu xác nhận không khớp.")

        # Kiểm tra email/username đã tồn tại
        existing = await self.db.execute(
            select(User).where(
                (User.email == payload.email) | (User.username == payload.username)
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(detail="Email hoặc username đã tồn tại.")

        # Tạo user mới
        new_user = User(
            email=payload.email,
            username=payload.username,
            full_name=payload.full_name,
            hashed_password=get_password_hash(payload.password),
            role=UserRole.USER.value,
            is_active=True,
            is_verified=False,
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    # ============ Đăng nhập ============
    async def login(self, payload: UserLogin) -> TokenResponse:
        """Đăng nhập và trả về access_token + refresh_token."""
        result = await self.db.execute(
            select(User).where(User.email == payload.email)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(payload.password, user.hashed_password):
            raise InvalidCredentialsException()

        if not user.is_active:
            raise UnauthorizedException(detail="Tài khoản đã bị khóa.")

        # Cập nhật last_login
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()

        # Tạo tokens
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        # Lưu refresh token vào DB
        from datetime import timedelta

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        db_refresh = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            expires_at=expires_at,
            is_revoked=False,
        )
        self.db.add(db_refresh)
        await self.db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ============ Refresh token ============
    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Tạo access token mới từ refresh token."""
        try:
            payload = decode_token(refresh_token)
        except JWTError as e:
            raise TokenExpiredException(detail=str(e)) from e

        if payload.get("type") != "refresh":
            raise UnauthorizedException(detail="Token không hợp lệ.")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException()

        # Kiểm tra refresh token còn trong DB và chưa bị revoke
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token == refresh_token,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
        )
        db_token = result.scalar_one_or_none()
        if not db_token:
            raise UnauthorizedException(detail="Refresh token không hợp lệ hoặc đã bị thu hồi.")
        if db_token.expires_at < datetime.now(timezone.utc):
            raise TokenExpiredException()

        # Lấy user
        user = await self.get_user_by_id(int(user_id))
        if not user or not user.is_active:
            raise UnauthorizedException()

        # Tạo access token mới
        new_access = create_access_token(subject=str(user.id))
        return TokenResponse(
            access_token=new_access,
            refresh_token=refresh_token,  # giữ nguyên refresh
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ============ Logout ============
    async def logout(self, refresh_token: str) -> None:
        """Revoke refresh token."""
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        db_token = result.scalar_one_or_none()
        if db_token:
            db_token.is_revoked = True
            await self.db.commit()

    # ============ User helpers ============
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Lấy user theo id."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Lấy user theo email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_current_user_from_token(self, token: str) -> User:
        """Lấy user hiện tại từ access token."""
        try:
            payload = decode_token(token)
        except JWTError as e:
            raise UnauthorizedException(detail=str(e)) from e

        if payload.get("type") != "access":
            raise UnauthorizedException(detail="Token không phải access token.")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException()

        user = await self.get_user_by_id(int(user_id))
        if not user:
            raise NotFoundException(detail="Không tìm thấy user.")
        if not user.is_active:
            raise UnauthorizedException(detail="Tài khoản đã bị khóa.")
        return user

    # ============ Update profile ============
    async def update_profile(self, user: User, payload: UserUpdate) -> User:
        """Cập nhật thông tin user."""
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str,
    ) -> None:
        """Đổi mật khẩu."""
        if not verify_password(old_password, user.hashed_password):
            raise InvalidCredentialsException(detail="Mật khẩu cũ không chính xác.")
        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()
