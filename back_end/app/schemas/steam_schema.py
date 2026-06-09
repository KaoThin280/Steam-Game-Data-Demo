"""
Steam Schema - Pydantic models cho GameMeta, GameReview.
Đồng bộ với model trong app/models/steam.py.
"""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============ GameMeta ============
class GameMetaBase(BaseModel):
    app_id: int = Field(..., ge=0)
    name: str = Field(..., min_length=1, max_length=500)


class GameMetaOut(GameMetaBase):
    id: int
    short_description: Optional[str] = None
    detailed_description: Optional[str] = None
    about_the_game: Optional[str] = None
    header_image: Optional[str] = None
    capsule_image: Optional[str] = None
    capsule_imagev5: Optional[str] = None
    website: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    genres: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    windows: bool = False
    mac: bool = False
    linux: bool = False
    release_date: Optional[datetime] = None
    coming_soon: bool = False
    price_initial: Optional[float] = None
    price_final: Optional[float] = None
    currency: Optional[str] = None
    discount_percent: Optional[int] = None
    is_free: bool = False
    total_reviews: int = 0
    total_positive: int = 0
    total_negative: int = 0
    review_score: Optional[int] = None
    review_score_desc: Optional[str] = None
    positive_percent: Optional[float] = None
    pc_requirements_min: Optional[dict] = None
    pc_requirements_rec: Optional[dict] = None
    mac_requirements_min: Optional[dict] = None
    linux_requirements_min: Optional[dict] = None
    supported_languages: Optional[List[str]] = None
    full_audio_languages: Optional[List[str]] = None
    screenshots: Optional[List[str]] = None
    movies: Optional[List[str]] = None
    required_age: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GameMetaListResponse(BaseModel):
    items: List[GameMetaOut]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


class GameMetaFilter(BaseModel):
    search: Optional[str] = None
    genre: Optional[str] = None
    tag: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    is_free: Optional[bool] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_positive_percent: Optional[float] = None
    sort_by: str = "total_reviews"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20

    model_config = ConfigDict(extra="forbid")


# ============ GameReview ============
class GameReviewOut(BaseModel):
    id: int
    game_id: int
    recommendation_id: Optional[str] = None
    review_text: Optional[str] = None
    language: Optional[str] = None
    voted_up: bool
    votes_up: int = 0
    votes_funny: int = 0
    comment_count: int = 0
    steam_purchase: bool = False
    received_for_free: bool = False
    written_during_early_access: bool = False
    primarily_steam_deck: bool = False
    refunded: bool = False
    author_steamid: Optional[str] = None
    author_personaname: Optional[str] = None
    author_num_games_owned: Optional[int] = None
    author_num_reviews: Optional[int] = None
    author_playtime_forever: Optional[int] = None
    author_playtime_at_review: Optional[int] = None
    author_playtime_last_two_weeks: Optional[int] = 0
    timestamp_created: Optional[datetime] = None
    timestamp_updated: Optional[datetime] = None
    app_release_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GameReviewListResponse(BaseModel):
    items: List[GameReviewOut]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


class GameReviewFilter(BaseModel):
    language: Optional[str] = None
    voted_up: Optional[bool] = None
    steam_purchase: Optional[bool] = None
    min_playtime: Optional[int] = None
    page: int = 1
    page_size: int = 20

    model_config = ConfigDict(extra="forbid")


# ============ Import Data ============
class SteamDataImport(BaseModel):
    """Schema import dữ liệu Steam từ JSON gốc. Cấu trúc: { meta, reviews }"""

    meta: dict
    reviews: List[dict] = []

    model_config = ConfigDict(extra="forbid")
