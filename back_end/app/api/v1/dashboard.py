"""
Dashboard API - Thống kê số liệu cho biểu đồ.
RBAC: viewer / analyst / scientist / admin (read-only).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db
from app.models.user import AppUser, RoleName
from app.core.exceptions import ForbiddenException
from app.schemas.steam_schema import (
    GenreBucket,
    LanguageBucket,
    OverviewStats,
    YearBucket,
    GameOut,
)
from app.services.steam_service import SteamService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_steam_service(db: AsyncSession = Depends(get_db)) -> SteamService:
    return SteamService(db)


async def _require_viewer(user: AppUser) -> None:
    if user.has_role(
        RoleName.ADMIN.value,
        RoleName.SCIENTIST.value,
        RoleName.ANALYST.value,
        RoleName.VIEWER.value,
    ):
        return
    raise ForbiddenException(detail="Yêu cầu quyền xem dashboard.")


@router.get(
    "/overview",
    response_model=OverviewStats,
    summary="Thống kê tổng quan",
)
async def overview(
    user: AppUser = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    await _require_viewer(user)
    return await service.get_overview_stats()


@router.get(
    "/top-games",
    summary="Top games theo số review",
)
async def top_games(
    limit: int = Query(10, ge=1, le=50),
    user: AppUser = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    await _require_viewer(user)
    items = await service.get_top_games(limit=limit)
    return [GameOut.model_validate(i) for i in items]


@router.get(
    "/genres",
    response_model=list[GenreBucket],
    summary="Phân bố game theo genre",
)
async def genre_distribution(
    limit: int = Query(20, ge=1, le=100),
    user: AppUser = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    await _require_viewer(user)
    return await service.get_genre_distribution(limit=limit)


@router.get(
    "/years",
    response_model=list[YearBucket],
    summary="Số game phát hành theo năm",
)
async def year_distribution(
    limit: int = Query(30, ge=1, le=100),
    user: AppUser = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    await _require_viewer(user)
    return await service.get_year_distribution(limit=limit)


@router.get(
    "/languages",
    response_model=list[LanguageBucket],
    summary="Phân bố game theo ngôn ngữ hỗ trợ",
)
async def language_distribution(
    limit: int = Query(15, ge=1, le=100),
    user: AppUser = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    await _require_viewer(user)
    return await service.get_language_distribution(limit=limit)