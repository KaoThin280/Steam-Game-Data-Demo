"""
Games API - Truy xuất dữ liệu Steam Meta/Reviews.
Sửa lỗi: FastAPI/Pydantic v2 dùng `pattern` thay vì `regex` trong Query.
"""
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_active_user,
    get_current_admin,
)
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.steam_schema import (
    GameMetaFilter,
    GameMetaListResponse,
    GameMetaOut,
    GameReviewFilter,
    GameReviewListResponse,
    GameReviewOut,
    SteamDataImport,
)
from app.services.steam_service import SteamService

router = APIRouter(prefix="/games", tags=["Games"])


def get_steam_service(db: AsyncSession = Depends(get_db)) -> SteamService:
    return SteamService(db)


@router.get(
    "",
    response_model=GameMetaListResponse,
    summary="Danh sách games (yêu cầu đăng nhập)",
)
async def list_games(
    search: Optional[str] = Query(None, description="Tìm theo tên/dev/publisher"),
    genre: Optional[str] = Query(None, description="Lọc theo genre"),
    tag: Optional[str] = Query(None, description="Lọc theo tag"),
    developer: Optional[str] = Query(None),
    publisher: Optional[str] = Query(None),
    is_free: Optional[bool] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_positive_percent: Optional[float] = Query(None, ge=0, le=100),
    sort_by: str = Query(
        "total_reviews",
        pattern="^(total_reviews|positive_percent|release_date|price_final|name)$",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    """Lấy danh sách games với filter, sort, phân trang."""
    filter_ = GameMetaFilter(
        search=search,
        genre=genre,
        tag=tag,
        developer=developer,
        publisher=publisher,
        is_free=is_free,
        min_price=min_price,
        max_price=max_price,
        min_positive_percent=min_positive_percent,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    items, total = await service.list_games(filter_)
    return GameMetaListResponse(
        items=[GameMetaOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get(
    "/{game_id}",
    response_model=GameMetaOut,
    summary="Chi tiết một game",
)
async def get_game(
    game_id: int,
    _current_user: User = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    game = await service.get_game_by_id(game_id)
    return GameMetaOut.model_validate(game)


@router.get(
    "/{game_id}/reviews",
    response_model=GameReviewListResponse,
    summary="Danh sách reviews của game",
)
async def list_reviews(
    game_id: int,
    language: Optional[str] = Query(None, description="VD: english, vietnamese"),
    voted_up: Optional[bool] = Query(None),
    steam_purchase: Optional[bool] = Query(None),
    min_playtime: Optional[int] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _current_user: User = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    filter_ = GameReviewFilter(
        language=language,
        voted_up=voted_up,
        steam_purchase=steam_purchase,
        min_playtime=min_playtime,
        page=page,
        page_size=page_size,
    )
    items, total = await service.list_reviews(game_id, filter_)
    return GameReviewListResponse(
        items=[GameReviewOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "/import",
    response_model=GameMetaOut,
    status_code=201,
    summary="Import dữ liệu Steam từ JSON (chỉ admin)",
)
async def import_data(
    request: Request,
    payload: SteamDataImport,
    _admin: User = Depends(get_current_admin),
    service: SteamService = Depends(get_steam_service),
):
    """
    Import dữ liệu Steam từ JSON. Chỉ admin mới có quyền.
    Body: { "meta": {...}, "reviews": [...] }
    """
    # Rate limit riêng cho import (1 phút / 30 lần / user)
    await rate_limit(request, limit=30, window=60, bucket="import")
    game = await service.import_steam_data(
        {"meta": payload.meta, "reviews": payload.reviews}
    )
    return GameMetaOut.model_validate(game)
