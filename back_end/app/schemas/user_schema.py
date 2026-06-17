"""
User Schema - Pydantic models for application users (public.app_users)
Aligned with SCHEMA_DOCUMENTATION.md.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ============ Base ============
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=255)


# ============ Create / Register ============
class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


# ============ Update ============
class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None

    model_config = ConfigDict(extra="forbid")


class UserPasswordUpdate(BaseModel):
    old_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_new_password: str = Field(..., min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


# ============ Login ============
class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


# ============ Output / Response ============
class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class UserMe(UserOut):
    """Same shape as UserOut for the /me endpoint."""

    pass


# ============ Admin ============
class UserAdminUpdate(BaseModel):
    """Admin updates a user's flags (NOT roles - those go through dedicated endpoint)."""

    is_active: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")


class AssignRoleRequest(BaseModel):
    role_name: str = Field(..., description="Role name to attach (admin, analyst, scientist, viewer)")

    model_config = ConfigDict(extra="forbid")