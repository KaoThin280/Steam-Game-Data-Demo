"""
Auth Cookie utilities - httpOnly secure cookies for JWT tokens.

Benefits over localStorage:
  - XSS-resistant: JavaScript cannot read httpOnly cookies
  - Auto-sent with same-origin requests
  - Configurable SameSite, Secure, Domain

Usage in FastAPI endpoint:
    response = JSONResponse(content={...})
    set_auth_cookies(response, access_token, refresh_token)
    return response
"""
from typing import Optional

from fastapi import Response

from app.core.config import settings


# Cookie names - align with the frontend middleware (sgd_access_token).
COOKIE_ACCESS = "sgd_access_token"
COOKIE_REFRESH = "sgd_refresh_token"

# Default cookie settings (sensible for free-tier deploys on Vercel/Cloud Run).
def _cookie_kwargs(max_age: int) -> dict:
    """
    Build cookie kwargs based on settings.

    - httpOnly: True (XSS protection)
    - secure:   True in production (HTTPS only)
    - samesite: "lax" (allows top-level navigations)
    - path:     "/" (available across app)
    - max_age:  token lifetime in seconds
    - domain:   None = exact host (most secure for free tier)
    """
    return {
        "httponly": True,
        "secure": not settings.DEBUG,
        "samesite": "lax",
        "path": "/",
        "max_age": max_age,
    }


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    access_expires_seconds: int,
    refresh_expires_seconds: int,
) -> None:
    """
    Set both access and refresh tokens as httpOnly cookies on the response.
    """
    response.set_cookie(
        key=COOKIE_ACCESS,
        value=access_token,
        **_cookie_kwargs(access_expires_seconds),
    )
    response.set_cookie(
        key=COOKIE_REFRESH,
        value=refresh_token,
        **_cookie_kwargs(refresh_expires_seconds),
    )


def set_access_cookie(
    response: Response, access_token: str, expires_seconds: int
) -> None:
    """Set only the access token (used on refresh)."""
    response.set_cookie(
        key=COOKIE_ACCESS,
        value=access_token,
        **_cookie_kwargs(expires_seconds),
    )


def clear_auth_cookies(response: Response) -> None:
    """
    Clear both auth cookies (logout).
    """
    response.delete_cookie(key=COOKIE_ACCESS, path="/")
    response.delete_cookie(key=COOKIE_REFRESH, path="/")