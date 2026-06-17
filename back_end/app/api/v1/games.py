"""
Games API - CRUD + Reviews của 1 game.
RBAC:
  - GET (read)    : viewer / analyst / scientist / admin
  - POST/PATCH    : scientist / admin  (games_write / reviews_write)
  - DELETE        : admin               (games_delete / reviews_delete)
"""
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_active_user,
    require_permission,
)
from app.core.exceptions import ForbiddenException
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import AppUser, RoleName
from app.schemas.steam_schema import (
    GameCreate,
    GameFilter,
    GameListResponse,
    GameOut,
    ReviewCreate,
    ReviewFilter,
    ReviewListResponse,
    ReviewOut,
)
from app.services.steam_service import SteamService

router = APIRouter(prefix="/games", tags=["Games"])


def get_steam_service(db: AsyncSession = Depends(get_db)) -> SteamService:
    return SteamService(db)


# ===== Helpers =====
async def _require_read_games(user: AppUser) -> None:
    if user.has_role(RoleName.ADMIN.value, RoleName.SCIENTIST.value,
                      RoleName.ANALYST.value, RoleName.VIEWER.value):
        return
    raise ForbiddenException(detail="Yêu cầu quyền games_read.")


# ===== Games =====
@router.get(
    "",
    response_model=GameListResponse,
    summary="Danh sách games (cần games_read)",
)
async def list_games(
    search: Optional[str] = Query(None, description="Tìm theo tên/developer/publisher"),
    genre: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    developer: Optional[str] = Query(None),
    publisher: Optional[str] = Query(None),
    is_free: Optional[bool] = Query(None),
    year: Optional[int] = Query(None, ge=1970, le=2100),
    sort_by: str = Query("release_date", pattern="^(release_date|name|required_age)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: AppUser = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    await _require_read_games(user)
    flt = GameFilter(
        search=search, genre=genre, category=category,
        developer=developer, publisher=publisher, is_free=is_free,
        year=year, sort_by=sort_by, sort_order=sort_order,
        page=page, page_size=page_size,
    )
    items, total = await service.list_games(flt)
    return GameListResponse(
        items=[GameOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get(
    "/{steam_appid}",
    response_model=GameOut,
    summary="Chi tiết 1 game",
)
async def get_game(
    steam_appid: int,
    user: AppUser = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    await _require_read_games(user)
    game = await service.get_game_by_appid(steam_appid)
    return GameOut.model_validate(game)


@router.post(
    "",
    response_model=GameOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo / cập nhật 1 game (cần games_write: scientist / admin)",
)
async def upsert_game(
    request: Request,
    payload: GameCreate,
    user: AppUser = Depends(require_permission("games_write")),
    service: SteamService = Depends(get_steam_service),
):
    await rate_limit(request, limit=60, window=60, bucket="games-write")
    game = await service.upsert_game(payload)
    return GameOut.model_validate(game)


@router.delete(
    "/{steam_appid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa 1 game (cần games_delete: admin)",
)
async def delete_game(
    steam_appid: int,
    request: Request,
    user: AppUser = Depends(require_permission("games_delete")),
    service: SteamService = Depends(get_steam_service),
):
    await rate_limit(request, limit=30, window=60, bucket="games-delete")
    await service.delete_game(steam_appid)
    return None


# ===== Reviews of a game =====
@router.get(
    "/{steam_appid}/reviews",
    response_model=ReviewListResponse,
    summary="Danh sách reviews của 1 game (cần reviews_read)",
)
async def list_reviews(
    steam_appid: int,
    language: Optional[str] = Query(None, description="VD: english, vietnamese"),
    refunded: Optional[bool] = Query(None),
    received_for_free: Optional[bool] = Query(None),
    primarily_steam_deck: Optional[bool] = Query(None),
    min_playtime_forever: Optional[int] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: AppUser = Depends(get_current_active_user),
    service: SteamService = Depends(get_steam_service),
):
    await _require_read_games(user)
    flt = ReviewFilter(
        language=language, refunded=refunded,
        received_for_free=received_for_free,
        primarily_steam_deck=primarily_steam_deck,
        min_playtime_forever=min_playtime_forever,
        page=page, page_size=page_size,
    )
    items, total = await service.list_reviews(steam_appid, flt)
    return ReviewListResponse(
        items=[ReviewOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "/{steam_appid}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo 1 review cho game (cần reviews_write)",
)
async def create_review(
    steam_appid: int,
    payload: ReviewCreate,
    request: Request,
    user: AppUser = Depends(require_permission("reviews_write")),
    service: SteamService = Depends(get_steam_service),
):
    await rate_limit(request, limit=60, window=60, bucket="reviews-write")
    if payload.steam_appid != steam_appid:
        from app.core.exceptions import BadRequestException

        raise BadRequestException(
            detail="steam_appid trong URL không khớp với payload."
        )
    review = await service.create_review(payload)
    return ReviewOut.model_validate(review)


@router.delete(
    "/{steam_appid}/reviews/{recommendationid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Xóa 1 review (cần reviews_delete: admin)",
)
async def delete_review(
    steam_appid: int,
    recommendationid: int,
    request: Request,
    user: AppUser = Depends(require_permission("reviews_delete")),
    service: SteamService = Depends(get_steam_service),
):
    await rate_limit(request, limit=30, window=60, bucket="reviews-delete")
    await service.delete_review(recommendationid)
    return None