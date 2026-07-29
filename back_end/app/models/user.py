"""
Application user models with RBAC.
Aligned with SCHEMA_DOCUMENTATION.md
Tables:
  - app_users       (login accounts)
  - roles           (system roles)
  - permissions     (granular permissions)
  - role_permissions(role ↔ permission)
  - user_roles      (user ↔ role)
  - refresh_tokens  (JWT refresh tokens)
  - chat_histories  (AI chat sessions)
  - ai_chart_history(Charting tool logs)
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# ============ Role / Permission enums ============
class RoleName(str, PyEnum):
    """Canonical system role names (per SCHEMA_DOCUMENTATION.md)."""

    ADMIN = "admin"
    ANALYST = "analyst"
    SCIENTIST = "scientist"
    VIEWER = "viewer"


class PermissionName(str, PyEnum):
    """Canonical permission names (per SCHEMA_DOCUMENTATION.md)."""

    GAMES_READ = "games_read"
    GAMES_WRITE = "games_write"
    GAMES_DELETE = "games_delete"
    REVIEWS_READ = "reviews_read"
    REVIEWS_WRITE = "reviews_write"
    REVIEWS_DELETE = "reviews_delete"
    USERS_READ = "users_read"
    USERS_WRITE = "users_write"
    USERS_DELETE = "users_delete"
    USERS_MANAGE_ROLES = "users_manage_roles"
    SYSTEM_ADMIN = "system_admin"


# ============ RBAC tables ============
class Role(Base):
    """public.roles"""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    permissions: Mapped[List["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    users: Mapped[List["UserRole"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, role_name={self.role_name})>"


class Permission(Base):
    """public.permissions"""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    permission_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    resource: Mapped[Optional[str]] = mapped_column(Text)
    action: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    roles: Mapped[List["RolePermission"]] = relationship(
        back_populates="permission", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, permission_name={self.permission_name})>"


class RolePermission(Base):
    """public.role_permissions"""

    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    role: Mapped["Role"] = relationship(back_populates="permissions")
    permission: Mapped["Permission"] = relationship(back_populates="roles")


# ============ App user ============
class AppUser(Base):
    """public.app_users - login accounts."""

    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    roles: Mapped[List["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chat_histories: Mapped[List["ChatHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chart_histories: Mapped[List["AIChartHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # ---------- helpers ----------
    @property
    def role_names(self) -> List[str]:
        """All role names attached to this user."""
        return [r.role.role_name for r in (self.roles or []) if r.role]

    def has_permission(self, perm: str) -> bool:
        """Return True if user owns the given permission via any role."""
        for ur in (self.roles or []):
            if ur.role is None:
                continue
            for rp in (ur.role.permissions or []):
                if rp.permission and rp.permission.permission_name == perm:
                    return True
        return False

    def has_role(self, *role_names: str) -> bool:
        rs = set(self.role_names)
        return any(r in rs for r in role_names)

    def __repr__(self) -> str:
        return f"<AppUser(id={self.id}, email={self.email})>"


class UserRole(Base):
    """public.user_roles"""

    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["AppUser"] = relationship(back_populates="roles")
    role: Mapped["Role"] = relationship(back_populates="users")


# ============ Refresh tokens ============
class RefreshToken(Base):
    """public.refresh_tokens - revoked-token support."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["AppUser"] = relationship(back_populates="refresh_tokens")


# ============ AI chat history ============
class ChatHistory(Base):
    """public.chat_histories - AI agent conversation log."""

    __tablename__ = "chat_histories"
    __table_args__ = (
        UniqueConstraint("user_id", "session_id", name="uq_chat_session"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["AppUser"] = relationship(back_populates="chat_histories")


# ============ AI chart history ============
class AIChartHistory(Base):
    """public.ai_chart_history - Charting tool outputs."""

    __tablename__ = "ai_chart_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("app_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    chart_type: Mapped[str] = mapped_column(String(20), nullable=False)
    chart_title: Mapped[Optional[str]] = mapped_column(Text)
    x_axis_label: Mapped[Optional[str]] = mapped_column(Text)
    y_axis_label: Mapped[Optional[str]] = mapped_column(Text)
    series_label: Mapped[Optional[str]] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_query: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["AppUser"] = relationship(back_populates="chart_histories")