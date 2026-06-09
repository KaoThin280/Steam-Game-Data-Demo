"""
Dashboard API - Thống kê số liệu cho biểu đồ.
Sửa lỗi: `regex` -> `pattern` (Pydantic v2 / FastAPI).
"""
from typing import List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.steam_schema import GameMetaOut
from app.services.steam_service import SteamService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_steam_service(db: AsyncSession = Depends(get_db)) -> SteamService:
    return SteamService(db)


# ============ Response schemas ============
class OverviewStats(BaseModel):
    total_games: int
    total_reviews: int
    free_games: int
    paid_games: int
    average_positive_percent: float


class GenreItem(BaseModel):
    genre: str
    count: int


class PriceBucket(BaseModel):
    bucket: str
    count: int


# ============ Endpoints ============
@router.get(
    "/overview",
    response_model=OverviewStats,
    summary="Thống kê tổng quan",
)
async def overview(
    _user: User = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    return await service.get_overview_stats()


@router.get(
    "/top-games",
    response_model=List[GameMetaOut],
    summary="Top games",
)
async def top_games(
    limit: int = Query(10, ge=1, le=50),
    sort_by: str = Query(
        "total_reviews",
        pattern="^(total_reviews|positive_percent|price_final)$",
    ),
    _user: User = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    items = await service.get_top_games(limit=limit, sort_by=sort_by)
    return [GameMetaOut.model_validate(i) for i in items]


@router.get(
    "/genres",
    response_model=List[GenreItem],
    summary="Phân bố game theo genre",
)
async def genre_distribution(
    _user: User = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    return await service.get_genre_distribution()


@router.get(
    "/prices",
    response_model=List[PriceBucket],
    summary="Phân bố game theo khoảng giá",
)
async def price_distribution(
    _user: User = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    return await service.get_price_distribution()
