"""
Steam Schema - Pydantic models for games / reviews / dashboard.
Aligned with SCHEMA_DOCUMENTATION.md (public.games / public.reviews).
"""
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============ Game ============
class GameBase(BaseModel):
    steam_appid: int = Field(..., ge=0)
    name: str = Field(..., min_length=1)


class GameOut(BaseModel):
    steam_appid: int
    name: str
    is_free: bool = False
    required_age: int = 0
    release_date: Optional[date] = None
    publishers: Optional[str] = None
    developers: Optional[str] = None
    price_text: Optional[str] = None
    created_at: Optional[datetime] = None
    # Populated from Game.genre_names property (loaded via game_genres -> genre)
    genres: List[str] = Field(default=[], alias="genre_names")

    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)


class GameListResponse(BaseModel):
    items: List[GameOut]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


class GameFilter(BaseModel):
    search: Optional[str] = None
    # The `genre` / `category` fields are kept for backwards compatibility
    # with the existing FE but are not applied, because the corresponding
    # CSV columns have been removed from the public.games schema.
    genre: Optional[str] = None
    category: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    is_free: Optional[bool] = None
    year: Optional[int] = None
    sort_by: str = "release_date"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20

    model_config = ConfigDict(extra="ignore")


class GameCreate(BaseModel):
    """Schema for admin to create/update a game (upsert).

    NOTE: the CSV fields (genres / categories / supported_languages) were
    removed because they are no longer in the public.games schema.
    """

    steam_appid: int = Field(..., ge=0)
    name: str = Field(..., min_length=1)
    is_free: bool = False
    required_age: int = 0
    release_date: Optional[date] = None
    publishers: Optional[str] = None
    developers: Optional[str] = None
    price_text: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


# ============ Review ============
class ReviewOut(BaseModel):
    recommendationid: int
    steam_appid: int
    steamid: int
    language: Optional[str] = None
    review_text: Optional[str] = None
    timestamp_created: Optional[datetime] = None
    timestamp_updated: Optional[datetime] = None
    refunded: bool = False
    received_for_free: bool = False
    written_during_early_access: bool = False
    primarily_steam_deck: bool = False
    playtime_at_review: int = 0
    playtime_last_two_weeks: int = 0
    playtime_forever: int = 0
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewListResponse(BaseModel):
    items: List[ReviewOut]
    total: int
    page: int = 1
    page_size: int = 20
    total_pages: int = 1


class ReviewFilter(BaseModel):
    language: Optional[str] = None
    refunded: Optional[bool] = None
    received_for_free: Optional[bool] = None
    primarily_steam_deck: Optional[bool] = None
    min_playtime_forever: Optional[int] = None
    page: int = 1
    page_size: int = 20

    model_config = ConfigDict(extra="forbid")


class ReviewCreate(BaseModel):
    recommendationid: int = Field(..., ge=0)
    steam_appid: int = Field(..., ge=0)
    steamid: int = Field(..., ge=0)
    language: Optional[str] = None
    review_text: Optional[str] = None
    timestamp_created: Optional[datetime] = None
    timestamp_updated: Optional[datetime] = None
    refunded: bool = False
    received_for_free: bool = False
    written_during_early_access: bool = False
    primarily_steam_deck: bool = False
    playtime_at_review: int = 0
    playtime_last_two_weeks: int = 0
    playtime_forever: int = 0

    model_config = ConfigDict(extra="forbid")


# ============ Dashboard ============
class OverviewStats(BaseModel):
    total_games: int
    total_reviews: int
    free_games: int
    paid_games: int
    total_developers: int
    total_languages: int


class GenreBucket(BaseModel):
    genre: str
    count: int


class YearBucket(BaseModel):
    year: int
    count: int


class LanguageBucket(BaseModel):
    language: str
    count: int


# ============ AI Charting tool ============
class ChartSpec(BaseModel):
    """
    Output spec from the AI Charting tool.
    Charts are rendered by the front-end (Chart.js) using `config`.
    """

    chart_type: str = Field(..., description="bar | line | pie | doughnut | scatter | radar | area")
    chart_title: str
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None
    series_label: Optional[str] = None
    x_rotation: Optional[int] = Field(None, description="Rotation angle (deg) cho nhãn trục X")
    y_unit: Optional[str] = Field(None, description="Đơn vị cho trục Y (vd: 'USD', '%', 'reviews')")
    # Chart.js-style payload
    config: dict = Field(..., description="Chart.js config (labels, datasets, options)")
    source_query: Optional[str] = Field(None, description="SQL đã được dùng để tạo chart")
    notes: Optional[str] = None

    model_config = ConfigDict(extra="forbid")
