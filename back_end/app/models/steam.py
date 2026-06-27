"""
Steam Game models - aligned with SCHEMA_DOCUMENTATION.md
Tables:
  - games   (Steam game metadata, flattened)
  - users   (Steam reviewers)
  - reviews (Steam reviews)

Note: These tables don't have updated_at columns, so we don't use the
TimestampMixin (which would create them via Base.metadata.create_all).
We still use Base to register them.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Game(Base):
    """public.games - Steam game metadata (flattened, simplified schema).

    The CSV columns (genres / categories / supported_languages) have been
    removed from the live schema to save storage. If needed, dedicated
    junction tables can be added later.
    """

    __tablename__ = "games"

    steam_appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    required_age: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    release_date: Mapped[Optional[date]] = mapped_column(Date)
    publishers: Mapped[Optional[str]] = mapped_column(Text)
    developers: Mapped[Optional[str]] = mapped_column(Text)
    price_text: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Game(steam_appid={self.steam_appid}, name={self.name})>"


class SteamUser(Base):
    """public.users - Steam reviewer profiles."""

    __tablename__ = "users"

    steamid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    personaname: Mapped[Optional[str]] = mapped_column(Text)
    num_games_owned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SteamUser(steamid={self.steamid}, personaname={self.personaname})>"


class Review(Base):
    """public.reviews - Steam user reviews."""

    __tablename__ = "reviews"

    recommendationid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    steam_appid: Mapped[int] = mapped_column(
        Integer, ForeignKey("games.steam_appid", ondelete="CASCADE"), nullable=False
    )
    steamid: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.steamid", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[Optional[str]] = mapped_column(String(20))
    review_text: Mapped[Optional[str]] = mapped_column(Text)
    timestamp_created: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    timestamp_updated: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    refunded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    received_for_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    written_during_early_access: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    primarily_steam_deck: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    playtime_at_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    playtime_last_two_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    playtime_forever: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    game: Mapped["Game"] = relationship(back_populates="reviews")
    user: Mapped["SteamUser"] = relationship(back_populates="reviews")

    def __repr__(self) -> str:
        return f"<Review(recommendationid={self.recommendationid})>"