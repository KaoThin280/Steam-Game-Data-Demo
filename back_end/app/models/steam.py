"""
Steam Models - Bảng GameMeta, GameReviews
Đồng bộ với schema 'steam' trên Aiven PostgreSQL.
Ánh xạ theo cấu trúc JSON dữ liệu Steam.
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class GameMeta(Base, TimestampMixin):
    """
    Bảng GameMeta - Lưu thông tin meta của game trên Steam.
    Ánh xạ với key 'meta' trong JSON dữ liệu Steam.
    """

    __tablename__ = "game_metas"
    __table_args__ = (
        Index("idx_game_meta_release_price", "release_date", "price_final"),
        Index("idx_game_meta_positive_percent", "positive_percent"),
        {"schema": "steam"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Steam identifiers
    app_id: Mapped[int] = mapped_column(
        Integer, unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(500), index=True, nullable=False)

    # Mô tả
    short_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detailed_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    about_the_game: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Hình ảnh
    header_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    capsule_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    capsule_imagev5: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Nhà phát triển / Nhà phát hành
    developer: Mapped[Optional[str]] = mapped_column(
        String(255), index=True, nullable=True
    )
    publisher: Mapped[Optional[str]] = mapped_column(
        String(255), index=True, nullable=True
    )

    # Thể loại / Tags
    genres: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(100)), nullable=True
    )
    categories: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(100)), nullable=True
    )
    tags: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(100)), nullable=True
    )

    # Hỗ trợ nền tảng
    windows: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mac: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    linux: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Ngày phát hành
    release_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    coming_soon: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Giá (lưu số thực - chia 100 từ JSON Steam khi import)
    price_initial: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    price_final: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2), nullable=True, index=True
    )
    currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    discount_percent: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True
    )
    is_free: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    # Đánh giá
    total_reviews: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, index=True
    )
    total_positive: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    total_negative: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    review_score: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True
    )
    review_score_desc: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    positive_percent: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, index=True
    )

    # Yêu cầu hệ thống (lưu dạng JSON)
    pc_requirements_min: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pc_requirements_rec: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    mac_requirements_min: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    linux_requirements_min: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )

    # Metadata khác
    supported_languages: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(50)), nullable=True
    )
    full_audio_languages: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(50)), nullable=True
    )
    screenshots: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(500)), nullable=True
    )
    movies: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String(500)), nullable=True
    )

    # Toàn bộ dữ liệu gốc (backup)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Age rating
    required_age: Mapped[int] = mapped_column(
        SmallInteger, default=0, nullable=False
    )

    # Relationships
    reviews: Mapped[List["GameReview"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GameMeta(app_id={self.app_id}, name={self.name})>"


class GameReview(Base, TimestampMixin):
    """
    Bảng GameReview - Lưu các review chi tiết từ người chơi Steam.
    Ánh xạ với key 'reviews' trong JSON dữ liệu Steam.
    """

    __tablename__ = "game_reviews"
    __table_args__ = (
        Index("idx_game_review_game_voted", "game_id", "voted_up"),
        Index("idx_game_review_created", "timestamp_created"),
        {"schema": "steam"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("steam.game_metas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )

    # Nội dung review
    review_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, index=True
    )

    # Đánh giá
    voted_up: Mapped[bool] = mapped_column(
        Boolean, nullable=False, index=True
    )
    votes_up: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    votes_funny: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    steam_purchase: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    received_for_free: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    written_during_early_access: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    primarily_steam_deck: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    refunded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Thông tin người review
    author_steamid: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )
    author_personaname: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    author_num_games_owned: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    author_num_reviews: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    author_playtime_forever: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    author_playtime_at_review: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    author_playtime_last_two_weeks: Mapped[Optional[int]] = mapped_column(
        Integer, default=0, nullable=False
    )

    # Thời gian
    timestamp_created: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    timestamp_updated: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    app_release_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    game: Mapped["GameMeta"] = relationship(back_populates="reviews")

    def __repr__(self) -> str:
        return f"<GameReview(id={self.id}, game_id={self.game_id})>"
