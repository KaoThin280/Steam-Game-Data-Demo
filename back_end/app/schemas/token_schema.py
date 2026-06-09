"""
Token Schema - Pydantic models cho JWT Token
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TokenPayload(BaseModel):
    """Payload của JWT token."""

    sub: Optional[str] = None
    exp: Optional[int] = None
    type: Optional[str] = None


class TokenResponse(BaseModel):
    """Schema response khi login/refresh thành công."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Thời gian sống của access token (giây)")


class RefreshTokenRequest(BaseModel):
    """Schema yêu cầu refresh token."""

    refresh_token: str

    model_config = ConfigDict(extra="forbid")


class AccessTokenResponse(BaseModel):
    """Schema trả về access token mới."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
