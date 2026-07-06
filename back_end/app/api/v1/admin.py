"""
Admin API - User & role management.
All endpoints require admin role (or system_admin permission).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_auth_service, get_current_admin
from app.core.exceptions import NotFoundException
from app.db.session import get_db
from app.models.user import AppUser, Permission, Role
from app.schemas.user_schema import (
    AssignRoleRequest,
    UserAdminUpdate,
    UserOut,
)
from app.services.auth_service import AuthService
from app.utils.user_helpers import user_to_out

router = APIRouter(prefix="/admin", tags=["Admin"])


# ============ Schemas ============
class RoleOut(BaseModel):
    id: int
    role_name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class PermissionOut(BaseModel):
    id: int
    permission_name: str
    description: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: List[UserOut]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1



# ============ Roles & Permissions (read-only catalog) ============
@router.get(
    "/roles",
    response_model=List[RoleOut],
    summary="Danh sách roles trong hệ thống",
)
async def list_roles(
    _admin: AppUser = Depends(get_current_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    roles = await auth_service.list_roles()
    return [RoleOut.model_validate(r) for r in roles]


@router.get(
    "/permissions",
    response_model=List[PermissionOut],
    summary="Danh sách permissions trong hệ thống",
)
async def list_permissions(
    _admin: AppUser = Depends(get_current_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    perms = await auth_service.list_permissions()
    return [PermissionOut.model_validate(p) for p in perms]


# ============ Users management ============
@router.get(
    "/users",
    response_model=UserListResponse,
    summary="Danh sách users (admin)",
)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="Tìm theo email hoặc username"),
    role: Optional[str] = Query(None, description="Lọc theo role_name"),
    _admin: AppUser = Depends(get_current_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    items, total = await auth_service.list_users(
        page=page, page_size=page_size, search=search, role_name=role
    )
    return UserListResponse(
        items=[user_to_out(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


async def _get_user(auth_service: AuthService, user_id: int) -> AppUser:
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise NotFoundException(detail=f"User #{user_id} không tồn tại.")
    return user


@router.get(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Chi tiết 1 user (admin)",
)
async def get_user(
    user_id: int,
    _admin: AppUser = Depends(get_current_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    user = await _get_user(auth_service, user_id)
    return user_to_out(user)


@router.patch(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Cập nhật trạng thái user (active / inactive)",
)
async def update_user(
    user_id: int,
    payload: UserAdminUpdate,
    _admin: AppUser = Depends(get_current_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    user = await _get_user(auth_service, user_id)
    if payload.is_active is not None:
        user.is_active = payload.is_active
    await auth_service.db.commit()
    await auth_service.db.refresh(user)
    # Reload with roles
    reloaded = await auth_service.get_user_by_id(user.id)
    return user_to_out(reloaded or user)


@router.post(
    "/users/{user_id}/roles",
    response_model=UserOut,
    summary="Gán role cho user (admin)",
)
async def assign_role(
    user_id: int,
    payload: AssignRoleRequest,
    _admin: AppUser = Depends(get_current_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    user = await _get_user(auth_service, user_id)
    updated = await auth_service.assign_role(user, payload.role_name)
    return user_to_out(updated)


@router.delete(
    "/users/{user_id}/roles/{role_name}",
    response_model=UserOut,
    summary="Thu hồi role của user (admin)",
)
async def revoke_role(
    user_id: int,
    role_name: str,
    _admin: AppUser = Depends(get_current_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    user = await _get_user(auth_service, user_id)
    updated = await auth_service.revoke_role(user, role_name)
    return user_to_out(updated)