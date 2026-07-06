"""
User helper utilities - convert AppUser ORM model to Pydantic schema.

Centralised here to avoid drift between endpoints (was previously duplicated).
"""
from typing import List, Optional

from app.models.user import AppUser
from app.schemas.user_schema import UserMe, UserOut


def _collect_roles(user: AppUser) -> List[str]:
    """Flatten the user's role -> role_name list (deduped, preserves order)."""
    seen = set()
    out: List[str] = []
    for ur in (user.roles or []):
        if ur.role and ur.role.role_name and ur.role.role_name not in seen:
            seen.add(ur.role.role_name)
            out.append(ur.role.role_name)
    return out


def _collect_permissions(user: AppUser) -> List[str]:
    """Flatten the user's role -> permission list (deduped, preserves order)."""
    seen = set()
    out: List[str] = []
    for ur in (user.roles or []):
        if not ur.role:
            continue
        for rp in (ur.role.permissions or []):
            if rp.permission and rp.permission.permission_name:
                name = rp.permission.permission_name
                if name not in seen:
                    seen.add(name)
                    out.append(name)
    return out


def user_to_out(user: AppUser) -> UserOut:
    """Convert an AppUser ORM instance to the public UserOut schema.

    Includes `roles` and `permissions` so the front-end can use them
    directly without a second round-trip.
    """
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
        roles=_collect_roles(user),
        permissions=_collect_permissions(user),
    )


def user_to_me(user: AppUser, *, roles: Optional[List[str]] = None) -> UserMe:
    """Convert an AppUser ORM instance to UserMe (includes roles + permissions)."""
    base = user_to_out(user)
    if roles is not None:
        return UserMe(**base.model_dump(), roles=roles)
    return UserMe(**base.model_dump())
