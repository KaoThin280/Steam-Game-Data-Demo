"""
User Model - Bảng Users, Roles trong database
Đồng bộ với schema 'steam' trên Aiven PostgreSQL.
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class UserRole(str, PyEnum):
    """Enum cho role của user."""

    ADMIN = "admin"
    USER = "user"
    PREMIUM = "premium"


class User(Base, TimestampMixin):
    """Bảng Users (lưu trong schema 'steam')."""

    __tablename__ = "users"
    __table_args__ = {"schema": "steam"}

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Thông tin đăng nhập
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Thông tin cá nhân
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Phân quyền
    role: Mapped[str] = mapped_column(
        String(20), default=UserRole.USER.value, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Thời gian
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chat_histories: Mapped[List["ChatHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def role_enum(self) -> UserRole:
        """Helper lấy role dưới dạng enum."""
        try:
            return UserRole(self.role)
        except ValueError:
            return UserRole.USER

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class RefreshToken(Base, TimestampMixin):
    """Bảng lưu refresh token (để revoke khi cần)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "steam"}

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("steam.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(
        String(500), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id})>"


class ChatHistory(Base, TimestampMixin):
    """Bảng lưu lịch sử chat với AI agent."""

    __tablename__ = "chat_histories"
    __table_args__ = {"schema": "steam"}

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("steam.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' | 'assistant' | 'system'
    content: Mapped[str] = mapped_column(String(5000), nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="chat_histories")

    def __repr__(self) -> str:
        return f"<ChatHistory(id={self.id}, session_id={self.session_id})>"
