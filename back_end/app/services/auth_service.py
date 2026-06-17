"""
Auth Service - register, login, refresh, profile, role/permission helpers.
Aligned with SCHEMA_DOCUMENTATION.md (public.app_users + RBAC tables).
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
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
from app.models.user import (
    AppUser,
    Permission,
    RefreshToken,
    Role,
    RoleName,
    RolePermission,
    UserRole,
)
from app.schemas.token_schema import TokenResponse
from app.schemas.user_schema import UserCreate, UserUpdate


class AuthService:
    """Service xử lý authentication và authorization."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ============ Helpers ============
    async def _load_user(self, user_id: int) -> Optional[AppUser]:
        """Load user kèm roles + permissions để tránh N+1."""
        result = await self.db.execute(
            select(AppUser)
            .options(
                selectinload(AppUser.roles)
                .selectinload(UserRole.role)
                .selectinload(Role.permissions)
                .selectinload(RolePermission.permission),
            )
            .where(AppUser.id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_role_by_name(self, name: str) -> Optional[Role]:
        result = await self.db.execute(select(Role).where(Role.role_name == name))
        return result.scalar_one_or_none()

    # ============ Register ============
    async def register(
        self, payload: UserCreate, default_role: str = RoleName.VIEWER.value
    ) -> AppUser:
        """Đăng ký user mới. Mặc định gán role 'viewer'."""
        if payload.password != payload.confirm_password:
            raise UnauthorizedException(detail="Mật khẩu xác nhận không khớp.")

        existing = await self.db.execute(
            select(AppUser).where(
                (AppUser.email == payload.email)
                | (AppUser.username == payload.username)
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(detail="Email hoặc username đã tồn tại.")

        new_user = AppUser(
            email=payload.email,
            username=payload.username,
            full_name=payload.full_name,
            password_hash=get_password_hash(payload.password),
            is_active=True,
        )
        self.db.add(new_user)
        await self.db.flush()

        # Attach default role
        role = await self._get_role_by_name(default_role)
        if role is None:
            raise BadRequestException(
                detail=f"Role mặc định '{default_role}' chưa được seed."
            )
        self.db.add(UserRole(user_id=new_user.id, role_id=role.id))

        await self.db.commit()
        loaded = await self._load_user(new_user.id)
        return loaded or new_user

    # ============ Login ============
    async def login(self, payload) -> TokenResponse:
        """Đăng nhập và trả về access_token + refresh_token."""
        result = await self.db.execute(
            select(AppUser).where(AppUser.email == payload.email)
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(payload.password, user.password_hash):
            raise InvalidCredentialsException()
        if not user.is_active:
            raise UnauthorizedException(detail="Tài khoản đã bị khóa.")

        user.last_login = datetime.now(timezone.utc)
        await self.db.commit()

        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        self.db.add(
            RefreshToken(
                user_id=user.id,
                token=refresh_token,
                expires_at=expires_at,
                is_revoked=False,
                created_at=datetime.now(timezone.utc),
            )
        )
        await self.db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # ============ Refresh ============
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

        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token == refresh_token,
                RefreshToken.is_revoked == False,  # noqa: E712
            )
        )
        db_token = result.scalar_one_or_none()
        if not db_token:
            raise UnauthorizedException(
                detail="Refresh token không hợp lệ hoặc đã bị thu hồi."
            )
        if db_token.expires_at < datetime.now(timezone.utc):
            raise TokenExpiredException()

        user = await self._load_user(int(user_id))
        if not user or not user.is_active:
            raise UnauthorizedException()

        new_access = create_access_token(subject=str(user.id))
        return TokenResponse(
            access_token=new_access,
            refresh_token=refresh_token,
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

    # ============ User lookups ============
    async def get_user_by_id(self, user_id: int) -> Optional[AppUser]:
        return await self._load_user(user_id)

    async def get_user_by_email(self, email: str) -> Optional[AppUser]:
        result = await self.db.execute(
            select(AppUser).where(AppUser.email == email)
        )
        return result.scalar_one_or_none()

    async def get_current_user_from_token(self, token: str) -> AppUser:
        try:
            payload = decode_token(token)
        except JWTError as e:
            raise UnauthorizedException(detail=str(e)) from e

        if payload.get("type") != "access":
            raise UnauthorizedException(detail="Token không phải access token.")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException()

        user = await self._load_user(int(user_id))
        if not user:
            raise NotFoundException(detail="Không tìm thấy user.")
        if not user.is_active:
            raise UnauthorizedException(detail="Tài khoản đã bị khóa.")
        return user

    # ============ Profile ============
    async def update_profile(self, user: AppUser, payload: UserUpdate) -> AppUser:
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        await self.db.commit()
        await self.db.refresh(user)
        return await self._load_user(user.id) or user

    async def change_password(
        self,
        user: AppUser,
        old_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(old_password, user.password_hash):
            raise InvalidCredentialsException(detail="Mật khẩu cũ không chính xác.")
        user.password_hash = get_password_hash(new_password)
        await self.db.commit()

    # ============ Admin: role/permission management ============
    async def list_roles(self) -> List[Role]:
        result = await self.db.execute(
            select(Role).order_by(Role.role_name.asc())
        )
        return list(result.scalars().all())

    async def list_permissions(self) -> List[Permission]:
        result = await self.db.execute(
            select(Permission).order_by(Permission.permission_name.asc())
        )
        return list(result.scalars().all())

    async def assign_role(self, user: AppUser, role_name: str) -> AppUser:
        role = await self._get_role_by_name(role_name)
        if role is None:
            raise NotFoundException(detail=f"Role '{role_name}' không tồn tại.")
        existing = await self.db.execute(
            select(UserRole).where(
                UserRole.user_id == user.id, UserRole.role_id == role.id
            )
        )
        if existing.scalar_one_or_none():
            return await self._load_user(user.id) or user
        self.db.add(UserRole(user_id=user.id, role_id=role.id))
        await self.db.commit()
        return await self._load_user(user.id) or user

    async def revoke_role(self, user: AppUser, role_name: str) -> AppUser:
        role = await self._get_role_by_name(role_name)
        if role is None:
            raise NotFoundException(detail=f"Role '{role_name}' không tồn tại.")
        result = await self.db.execute(
            select(UserRole).where(
                UserRole.user_id == user.id, UserRole.role_id == role.id
            )
        )
        link = result.scalar_one_or_none()
        if link:
            await self.db.delete(link)
            await self.db.commit()
        return await self._load_user(user.id) or user

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        role_name: Optional[str] = None,
    ) -> Tuple[List[AppUser], int]:
        offset = (page - 1) * page_size
        query = select(AppUser).options(
            selectinload(AppUser.roles)
            .selectinload(UserRole.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission),
        )
        count_q = select(AppUser)

        if search:
            kw = f"%{search}%"
            query = query.where(
                (AppUser.email.ilike(kw)) | (AppUser.username.ilike(kw))
            )
            count_q = count_q.where(
                (AppUser.email.ilike(kw)) | (AppUser.username.ilike(kw))
            )

        if role_name:
            role = await self._get_role_by_name(role_name)
            if role is None:
                return [], 0
            ids_q = select(UserRole.user_id).where(UserRole.role_id == role.id)
            query = query.where(AppUser.id.in_(ids_q))
            count_q = count_q.where(AppUser.id.in_(ids_q))

        query = query.order_by(AppUser.id.asc()).offset(offset).limit(page_size)
        items = list((await self.db.execute(query)).scalars().all())
        total = (await self.db.execute(count_q)).scalar() or 0
        return items, int(total)