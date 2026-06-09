"""
User Schema - Pydantic models cho User
Dùng để validate input/output cho API.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


# ============ Base ============
class UserBase(BaseModel):
    """Schema cơ sở cho User."""

    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)


# ============ Create / Register ============
class UserCreate(UserBase):
    """Schema cho đăng ký user mới."""

    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


# ============ Update ============
class UserUpdate(BaseModel):
    """Schema cho cập nhật thông tin user."""

    full_name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=500)
    email: Optional[EmailStr] = None

    model_config = ConfigDict(extra="forbid")


class UserPasswordUpdate(BaseModel):
    """Schema cho đổi mật khẩu."""

    old_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_new_password: str = Field(..., min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


# ============ Login ============
class UserLogin(BaseModel):
    """Schema cho đăng nhập."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


# ============ Output / Response ============
class UserOut(UserBase):
    """Schema trả về thông tin user."""

    id: int
    role: str  # admin | user | premium
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserMe(UserOut):
    """Schema trả về thông tin user hiện tại (kèm extra)."""

    pass


# ============ Admin ============
class UserAdminUpdate(BaseModel):
    """Schema admin cập nhật user."""

    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")
